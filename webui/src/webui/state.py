from __future__ import annotations

import base64
import gc
import logging
import os
import queue
import re
import shutil
import asyncio
import tarfile
import tempfile
import time
import zipfile
import yaml
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Callable, Dict, Generator, List, Optional, Sequence, Union

import polars as pl
import reflex as rx
from reflex.event import EventSpec
from pydantic import BaseModel
from dagster import DagsterInstance, AssetKey, AssetMaterialization, AssetRecordsFilter, DagsterRunStatus, RunsFilter, MetadataValue
from just_dna_pipelines.agents.module_creator import read_spec_meta
from just_dna_pipelines.annotation.assets import user_vcf_partitions
from just_dna_pipelines.annotation.definitions import defs
from just_dna_pipelines.annotation.hf_logic import prepare_vcf_for_module_annotation
from just_dna_pipelines.annotation.hf_modules import DISCOVERED_MODULES, MODULE_INFOS, HF_DEFAULT_REPOS
from just_dna_pipelines.annotation.resources import (
    get_user_output_dir, get_user_input_dir, get_generated_modules_dir,
    download_vcf_from_zenodo, ensure_vcf_in_user_input_dir,
    validate_zenodo_record, resolve_default_samples,
)
from just_dna_pipelines.module_config import (
    build_module_metadata_dict, _load_config,
    is_immutable_mode as _is_immutable_mode,
    get_immutable_config,
    has_lead_table,
    spec_version,
    DefaultSample,
    LEAD_TABLE_CSVS,
    RegistryStore,
    default_registry_store,
    get_registry_store,
)
from just_dna_pipelines.module_registry import (
    CUSTOM_MODULES_DIR,
    register_custom_module,
    register_downloaded_module,
    unregister_custom_module,
    list_custom_modules,
    refresh_module_registry,
)
from just_dna_registry import RegistryClient, RegistryError
from just_dna_registry.client import VersionMismatchError
from just_dna_format.identity import is_valid_namespace
from just_dna_compiler.compiler import ARTIFACT_PARQUETS
from just_dna_compiler.compiler import content_signature
from just_dna_format.integrity import IntegrityError, build_artifact
from just_dna_format.manifest import read_manifest
from webui.compute.jobs import await_job, forget_job, submit_job
from webui.dagster_env import get_dagster_instance
from webui.features import MODULE_CREATOR_ENABLED, REGISTRY_PUBLICATION_ENABLED
from webui.grid import SafeGridMixin, filter_model_fingerprint, is_stale_grid_view_replay
from webui.registry_identity import (
    ensure_install_id, load_store_identity, save_store_identity, derive_handle, set_env_var,
)

# Display name → safe token (latin letters/digits/underscore); injection-safe, drives the handle.
_DISPLAY_NAME_RE = re.compile(r"^[A-Za-z0-9_]{2,32}$")

# Shown when the catalog server's contract (API / just-dna-format / compiler) is newer than
# this app's client — swapping compiled artifacts would collide, so we refuse and tell the user.
_REGISTRY_MISMATCH_HINT: str = (
    "This app is out of date with the catalog server — update just-dna-lite to continue."
)
from reflex_mui_datagrid import LazyFrameGridMixin, extract_vcf_descriptions, scan_file
from webui.deployment_urls import resolve_dagster_web_public_url, resolve_public_backend_base_url

logger = logging.getLogger(__name__)

GENERATED_MODULES_DIR: Path = get_generated_modules_dir()

_OUTPUT_PREVIEW_SCROLL_SCRIPT: str = (
    "window.setTimeout(() => document.getElementById('output-preview-heading')"
    "?.scrollIntoView({behavior: 'smooth', block: 'start'}), 150)"
)


def _find_default_sample(zenodo_url: str, filename: str) -> Optional[DefaultSample]:
    """Match a Zenodo import against the pre-configured public genomes.

    Matches by record URL or by the published VCF filename, so both the
    one-click import buttons and a manually pasted URL pick up the curated
    metadata (label, subject id, sex) from ``modules.yaml``.
    """
    for sample in get_immutable_config().default_samples:
        if sample.zenodo_url.rstrip("/") == zenodo_url.rstrip("/"):
            return sample
        if sample.filename and sample.filename == filename:
            return sample
    return None


def _backend_api_url() -> str:
    """Return the browser-reachable Reflex backend URL for custom API routes.

    In production FULLSTACK mode, ``DEPLOY_URL``/``PUBLIC_APP_URL`` is enough
    because frontend and backend share one origin.  ``PUBLIC_BACKEND_URL`` is
    still available for explicit split-backend deployments.  Locally the port
    comes from ``API_URL`` / ``REFLEX_BACKEND_PORT``, never a hardcoded 8000.
    """
    return resolve_public_backend_base_url()


# Module metadata with titles, descriptions, and icons
# This maps module names to human-readable information
# Species options for VCF metadata (Latin/scientific names)
SPECIES_OPTIONS: List[str] = [
    "Homo sapiens",       # Human
    "Mus musculus",       # Mouse
    "Rattus norvegicus",  # Rat
    "Canis lupus familiaris",  # Dog
    "Felis catus",        # Cat
    "Danio rerio",        # Zebrafish
    "Other",
]

# Reference genome options by species (Latin names)
# For humans: GRCh38 and T2T-CHM13 are the main modern assemblies
REFERENCE_GENOMES: Dict[str, List[str]] = {
    "Homo sapiens": ["GRCh38", "T2T-CHM13v2.0", "GRCh37"],
    "Mus musculus": ["GRCm39", "GRCm38"],
    "Rattus norvegicus": ["mRatBN7.2", "Rnor_6.0"],
    "Canis lupus familiaris": ["ROS_Cfam_1.0", "CanFam3.1"],
    "Felis catus": ["Felis_catus_9.0", "Felis_catus_8.0"],
    "Danio rerio": ["GRCz11", "GRCz10"],
    "Other": ["custom"],
}

# Sex options (biological sex for genomic analysis)
SEX_OPTIONS: List[str] = [
    "N/A",      # Sample tissue/applicable
    "Male",
    "Female",
    "Other",
]

# Tissue source options (common sample sources)
TISSUE_OPTIONS: List[str] = [
    "Sample tissue",
    "Saliva",
    "Blood",
    "Buccal swab",
    "Skin",
    "Hair follicle",
    "Muscle",
    "Liver",
    "Brain",
    "Tumor",
    "Cell line",
    "Other",
]


# Module metadata is loaded from modules.yaml via module_config.
# Colors map to Fomantic UI named colors derived from the DNA logo palette.
# Modules not listed in modules.yaml get auto-generated defaults.
MODULE_METADATA: Dict[str, Dict[str, str]] = build_module_metadata_dict(DISCOVERED_MODULES)


# Dagster instance resolution lives in webui.dagster_env so compute-tier children can
# reach the same instance without importing this module (and with it reflex, agno and
# the module registry). get_dagster_instance is imported above for existing callers.


def get_dagster_web_url() -> str:
    """Get the URL for the Dagster web UI from environment or default."""
    return resolve_dagster_web_public_url()


class AuthState(rx.State):
    """Session-based authentication state."""

    is_authenticated: bool = False
    user_email: str = ""

    @rx.var
    def login_disabled(self) -> bool:
        """Check if login is disabled via env var."""
        return os.getenv("JUST_DNA_PIPELINES_LOGIN", "false").lower() == "none"

    def login(self, form_data: dict[str, Any]) -> EventSpec:
        """Set the session auth flag."""
        login_config = os.getenv("JUST_DNA_PIPELINES_LOGIN", "false").lower()
        
        email_raw = form_data.get("email")
        password_raw = form_data.get("password")
        email = (str(email_raw) if email_raw is not None else "").strip()
        password = (str(password_raw) if password_raw is not None else "").strip()

        if not email:
            return rx.toast.error("Email is required")

        # Handle restricted login if JUST_DNA_PIPELINES_LOGIN=user:pass
        if login_config != "false" and ":" in login_config:
            valid_user, valid_pass = login_config.split(":", 1)
            if email != valid_user or password != valid_pass:
                return rx.toast.error("Invalid credentials")

        self.is_authenticated = True
        self.user_email = email
        return rx.toast.success(f"Welcome, {email}!")

    def logout(self) -> EventSpec:
        self.is_authenticated = False
        self.user_email = ""
        return rx.toast.info("Logged out")


_RSID_DBSNP_BASE_URL = "https://www.ncbi.nlm.nih.gov/snp/"


def _inject_rsid_link_renderer(state_instance: Any) -> None:
    """Patch lf_grid_columns so rsid/id columns become clickable dbSNP links.

    Uses the built-in ``cellRendererType: "url"`` renderer so that rsid values
    become ``<a>`` links to the NCBI dbSNP variant page, opening in a new tab.
    Applied to columns named ``rsid`` or ``id``.
    """
    cols = state_instance.lf_grid_columns
    if not cols:
        return

    updated = False
    new_cols = []
    for col in cols:
        if col.get("field") in ("rsid", "id"):
            col = dict(col)
            col["cellRendererType"] = "url"
            col["cellRendererConfig"] = {
                "baseUrl": _RSID_DBSNP_BASE_URL,
                "target": "_blank",
                "color": "#1a73e8",
            }
            updated = True
        new_cols.append(col)

    if updated:
        state_instance.lf_grid_columns = new_cols


def _parquet_is_empty(path: Path) -> bool:
    """Return True when the parquet is missing, invalid, or has zero rows.

    Uses parquet metadata only (no full read), so it is cheap to call on the
    hot path. Any error reading the file is treated as "empty/invalid" so the
    caller regenerates it.
    """
    if not path.exists():
        return True
    try:
        return pl.scan_parquet(path).select(pl.len()).collect().item() == 0
    except Exception:
        return True


def _parquet_is_ready(path: Path) -> bool:
    """Return whether a parquet exists, is readable, and contains rows."""
    return not _parquet_is_empty(path)


def _vcf_sample_stem(filename: str) -> str:
    """Sample folder name used under the user output directory."""
    if filename.endswith(".vcf.gz"):
        return filename[: -len(".vcf.gz")]
    if filename.endswith(".vcf"):
        return filename[: -len(".vcf")]
    return Path(filename).stem


def _sample_choice_label(display_name: str, filename: str) -> str:
    """Dropdown text: sample name with the VCF filename when they differ."""
    if not display_name or display_name in {filename, _vcf_sample_stem(filename)}:
        return filename
    return f"{display_name} ({filename})"


def _normalized_parquet_for_vcf(safe_user_id: str, filename: str) -> Path:
    """Canonical normalized parquet path for a left-panel VCF filename."""
    return (
        get_user_output_dir()
        / safe_user_id
        / _vcf_sample_stem(filename)
        / "user_vcf_normalized.parquet"
    )


def comparable_prs_samples(
    files: Sequence[str],
    selected_file: str,
    file_metadata: Dict[str, Dict[str, Any]],
    is_ready: Callable[[str], bool],
    display_names: Dict[str, str] | None = None,
) -> List[Dict[str, str]]:
    """Left-panel samples that can join the current genome in a PRS comparison.

    A peer must share species and reference genome with the selected file and
    already have a prepared genotype table. The selected file is never returned.
    ``display_names`` is the left-panel map (curated label / subject ID / stem).
    """
    if not selected_file:
        return []
    current = file_metadata.get(selected_file, {})
    species = str(current.get("species") or "Homo sapiens")
    genome = str(current.get("reference_genome") or "GRCh38")
    names = display_names or {}
    peers: List[Dict[str, str]] = []
    for filename in files:
        if filename == selected_file:
            continue
        meta = file_metadata.get(filename, {})
        if str(meta.get("species") or "Homo sapiens") != species:
            continue
        if str(meta.get("reference_genome") or "GRCh38") != genome:
            continue
        if not is_ready(filename):
            continue
        display_name = str(
            names.get(filename)
            or meta.get("sample_name")
            or _vcf_sample_stem(filename)
        )
        peers.append(
            {
                "filename": filename,
                "label": display_name,
                "display_name": display_name,
                "choice_label": _sample_choice_label(display_name, filename),
                "species": species,
                "reference_genome": genome,
            }
        )
    return peers


def _prs_result_cache_key(row: dict) -> str:
    """Index cached PRS rows by PGS ID, and by sample when comparing genomes."""
    pgs_id = str(row.get("pgs_id") or "")
    sample = str(row.get("sample") or "")
    if sample:
        return f"{pgs_id}::{sample}"
    return pgs_id


def _normalize_run_config_if_stale(
    safe_user_id: str, selected_file: str, partition_key: str
) -> dict | None:
    """Return a ``normalize_vcf_job`` run config if normalization is needed, else None.

    Only the *decision* happens here — Dagster metadata plus a parquet footer read, both
    cheap.  Running the job is the caller's job, via ``webui.compute.jobs``, so the
    normalization pipeline never executes inside the ASGI process.

    Pure function, no Reflex state: safe to call from ``run_in_executor``.
    """
    from just_dna_pipelines.module_config import _load_config

    current_hash = _load_config().quality_filters.config_hash()
    sample_name = selected_file.replace(".vcf.gz", "").replace(".vcf", "")
    normalized_path = get_user_output_dir() / safe_user_id / sample_name / "user_vcf_normalized.parquet"

    instance = get_dagster_instance()

    needs_normalize = True
    result = instance.fetch_materializations(
        records_filter=AssetRecordsFilter(
            asset_key=AssetKey("user_vcf_normalized"),
            asset_partitions=[partition_key],
        ),
        limit=1,
    )
    if result.records:
        mat = result.records[0].asset_materialization
        if mat and mat.metadata:
            h = mat.metadata.get("quality_filters_hash")
            stored_hash = str(h.value) if h and hasattr(h, "value") else ""
            if stored_hash == current_hash and normalized_path.exists():
                needs_normalize = False

    # Guard against a stale/empty cached parquet. A normalized genome is never
    # legitimately 0 rows; an empty file is the signature of a prior buggy run
    # whose config hash did not change (so the hash check above won't catch it).
    # Treat it as stale so the fix self-heals without manual cache wiping.
    if not needs_normalize and _parquet_is_empty(normalized_path):
        needs_normalize = True

    if not needs_normalize:
        return None

    vcf_path = get_user_input_dir() / safe_user_id / selected_file
    if not vcf_path.exists():
        return None

    return {
        "ops": {
            "user_vcf_normalized": {
                "config": {"vcf_path": str(vcf_path.absolute())}
            }
        }
    }


# Canonical tab order — single source of truth used both as the default for the
# tab_order state var and as the validation set in move_tab.
DEFAULT_TAB_ORDER: list[str] = ["input", "prs", "annotated_files", "reports", "analysis"]


class UploadState(SafeGridMixin, LazyFrameGridMixin, rx.State):
    """Handle VCF uploads and Dagster lineage."""

    uploading: bool = False
    # Note: `running` is maintained for internal state tracking, but UI should use
    # `selected_file_is_running` computed var for per-file logic (allows concurrent jobs)
    running: bool = False
    console_output: str = ""
    files: list[str] = []
    
    # Track asset status for the UI
    asset_statuses: Dict[str, Dict[str, str]] = {}
    
    # Cache user info to avoid async get_state in computed vars
    safe_user_id: str = ""
    
    # HF Module selection - all modules selected by default
    available_modules: list[str] = DISCOVERED_MODULES.copy()
    selected_modules: list[str] = DISCOVERED_MODULES.copy()
    
    # Ensembl annotation toggle (DuckDB-based, optional)
    include_ensembl: bool = False

    # Custom module registry (managed by AgentState slot, kept here for remove/refresh)

    # Class variable to track active in-process runs (for SIGTERM cleanup)
    # Maps token/run_id -> partition_key for jobs running in compute children
    _active_inproc_runs: Dict[str, str] = {}

    # Zenodo import state
    zenodo_url_input: str = ""
    zenodo_importing: bool = False

    # Progress feedback for long operations (download, normalize, load)
    progress_status: str = ""

    # ============================================================
    # NEW SAMPLE FORM STATE - for adding samples with metadata
    # ============================================================
    new_sample_subject_id: str = ""
    new_sample_sex: str = "N/A"
    new_sample_tissue: str = "Sample tissue"
    new_sample_species: str = "Homo sapiens"
    new_sample_reference_genome: str = "GRCh38"
    new_sample_study_name: str = ""
    new_sample_notes: str = ""

    # Public remount token for the Add Sample form. Uncontrolled inputs
    # (default_value) keep their DOM value when state resets; bumping this
    # key destroys and recreates those nodes. Must be a frontend var — a
    # leading underscore would make it backend-only and the client would
    # never remount.
    form_key: int = 0

    @rx.var
    def is_immutable_mode(self) -> bool:
        """True when the app is in immutable (public demo) mode."""
        return _is_immutable_mode()

    @rx.var
    def allow_zenodo_import(self) -> bool:
        """True when Zenodo URL import is available.

        Always true in normal mode.  In immutable mode, controlled by
        ``immutable_mode.allow_zenodo_import`` in modules.yaml.
        """
        if not _is_immutable_mode():
            return True
        return get_immutable_config().allow_zenodo_import

    @rx.var
    def immutable_disclaimer(self) -> str:
        """Disclaimer text for immutable mode (from modules.yaml config)."""
        return get_immutable_config().disclaimer

    @rx.var
    def has_progress_status(self) -> bool:
        """True when a long operation is in progress."""
        return bool(self.progress_status)

    @rx.var
    def default_sample_list(self) -> List[Dict[str, str]]:
        """Return the list of default samples for the public genome hint."""
        config = get_immutable_config()
        return [
            {
                "label": s.label,
                "zenodo_url": s.zenodo_url,
                "license": s.license,
            }
            for s in config.default_samples
        ]

    @rx.var
    def dagster_web_url(self) -> str:
        """Get the Dagster web UI URL."""
        return get_dagster_web_url()

    @rx.var
    def module_details(self) -> Dict[str, Dict[str, Any]]:
        """Return details (logo, repo, etc.) for each available module."""
        return {
            name: MODULE_INFOS[name].model_dump()
            for name in self.available_modules
            if name in MODULE_INFOS
        }

    @rx.var
    def repo_info_list(self) -> List[Dict[str, Any]]:
        """Return info about each module source, grouped by origin.

        For HuggingFace sources the URL points to the HF web page.
        For local/file sources the URL is the filesystem path and
        ``is_local`` is True so the UI can render a remove button.

        Iterates ``self.available_modules`` (a state var) so Reflex
        knows to recompute when modules are added/removed.
        """
        repos: Dict[str, Dict[str, Any]] = {}
        for name in self.available_modules:
            info = MODULE_INFOS.get(name)
            if info is None:
                continue
            repo_id = info.repo_id
            is_local = info.source_url.startswith("/") or info.source_url.startswith("file://")
            if repo_id not in repos:
                if is_local:
                    url = info.source_url
                else:
                    url = f"https://huggingface.co/datasets/{repo_id}"
                repos[repo_id] = {
                    "repo_id": repo_id,
                    "url": url,
                    "modules": [],
                    "module_count": 0,
                    "is_local": is_local,
                }
            repos[repo_id]["modules"].append(name)
            repos[repo_id]["module_count"] = len(repos[repo_id]["modules"])
        return list(repos.values())

    # ============================================================
    # NEW SAMPLE FORM: Computed properties for dropdowns
    # ============================================================
    @rx.var
    def new_sample_available_genomes(self) -> List[str]:
        """Get available reference genomes for the new sample's species."""
        return REFERENCE_GENOMES.get(self.new_sample_species, ["custom"])

    # Note: species_options, sex_options, tissue_options are defined below
    # (shared with file metadata editing)

    # ============================================================
    # NEW SAMPLE FORM: Setters
    # ============================================================
    def set_new_sample_subject_id(self, value: str):
        """Set subject ID for new sample."""
        self.new_sample_subject_id = value

    def set_new_sample_sex(self, value: str):
        """Set sex for new sample."""
        self.new_sample_sex = value

    def set_new_sample_tissue(self, value: str):
        """Set tissue for new sample."""
        self.new_sample_tissue = value

    def set_new_sample_species(self, value: str):
        """Set species for new sample and reset reference genome."""
        self.new_sample_species = value
        self.new_sample_reference_genome = REFERENCE_GENOMES.get(value, ["custom"])[0]

    def set_new_sample_reference_genome(self, value: str):
        """Set reference genome for new sample."""
        self.new_sample_reference_genome = value

    def set_new_sample_study_name(self, value: str):
        """Set study name for new sample."""
        self.new_sample_study_name = value

    def set_new_sample_notes(self, value: str):
        """Set notes for new sample."""
        self.new_sample_notes = value

    def set_zenodo_url_input(self, value: str) -> None:
        """Explicit setter for zenodo_url_input (avoids deprecation warning)."""
        self.zenodo_url_input = value

    def _reset_new_sample_form(self):
        """Reset new sample form to defaults and remount uncontrolled inputs."""
        self.new_sample_subject_id = ""
        self.new_sample_sex = "N/A"
        self.new_sample_tissue = "Sample tissue"
        self.new_sample_species = "Homo sapiens"
        self.new_sample_reference_genome = "GRCh38"
        self.new_sample_study_name = ""
        self.new_sample_notes = ""
        self.form_key = self.form_key + 1

    def _get_safe_user_id(self, auth_email: str) -> str:
        """Sanitize user_id for path and partition key."""
        user_id = auth_email or "anonymous"
        return "".join([c if c.isalnum() else "_" for c in user_id])

    @staticmethod
    def _detect_build(file_path) -> Optional[str]:
        """Detect the genome build from a saved VCF, or None if undetermined.

        Reads the VCF header via just-prs (``##reference=``/``##assembly=``,
        DRAGEN command lines, then contig-length voting). Never raises — a
        detection failure falls back to the user's manual selection.
        """
        try:
            from just_prs.vcf import detect_genome_build
            return detect_genome_build(file_path)
        except Exception:
            return None

    async def handle_upload(self, files: list[rx.UploadFile]) -> list[EventSpec]:
        """Handle the upload of VCF files and register them in Dagster.

        Returns follow-up events instead of yielding them. Reflex 0.9 marks a
        generator's EventFuture done when it exhausts; a later ``yield
        EventSpec`` is then re-dispatched as a child of that finished future
        and raises ``Cannot add a child to an EventFuture that is already done``.
        """
        if _is_immutable_mode():
            return [rx.toast.warning("File upload is disabled in public demo mode. Install locally to analyze your own genome.")]
        self.uploading = True
        new_files = []
        try:
            auth_state = await self.get_state(AuthState)
            self.safe_user_id = self._get_safe_user_id(auth_state.user_email)

            upload_dir = get_user_input_dir() / self.safe_user_id
            upload_dir.mkdir(parents=True, exist_ok=True)

            instance = get_dagster_instance()

            for file in files:
                if not file.filename:
                    continue

                # Save the file
                content = await file.read()
                if not content:
                    continue

                file_path = upload_dir / file.filename
                file_path.write_bytes(content)

                # Register in Dagster
                sample_name = file.filename.replace(".vcf.gz", "").replace(".vcf", "")
                partition_key = f"{self.safe_user_id}/{sample_name}"
                upload_date = datetime.now().strftime("%Y-%m-%d %H:%M")

                # 1. Add partition if missing
                from just_dna_pipelines.annotation.assets import user_vcf_partitions
                existing = instance.get_dynamic_partitions(user_vcf_partitions.name)
                if partition_key not in existing:
                    instance.add_dynamic_partitions(user_vcf_partitions.name, [partition_key])

                # 2. Materialize user_vcf_source (the source asset). This quick
                # path carries no metadata form, so the header is the only build
                # signal — record it when detectable.
                source_metadata: Dict[str, Any] = {
                    "path": str(file_path.absolute()),
                    "size_bytes": len(content),
                    "uploaded_via": "webui",
                    "upload_date": upload_date,
                }
                detected_build = self._detect_build(file_path)
                if detected_build:
                    source_metadata["reference_genome"] = detected_build
                    source_metadata["reference_genome_source"] = "header"

                instance.report_runless_asset_event(
                    AssetMaterialization(
                        asset_key="user_vcf_source",
                        partition=partition_key,
                        metadata=source_metadata,
                    )
                )

                # Move re-uploaded files to front (newest first)
                if file.filename in self.files:
                    self.files.remove(file.filename)
                self.files.insert(0, file.filename)
                new_files.append(file.filename)

                # Update status
                self.asset_statuses[partition_key] = {
                    "source": "materialized",
                    "annotated": "uploaded"
                }

        except Exception as exc:
            self.uploading = False
            return [rx.toast.error(f"Upload failed: {exc}")]
        self.uploading = False
        if new_files:
            return [
                *self.select_file(new_files[-1]),
                rx.toast.success(f"Uploaded and registered {len(new_files)} files."),
            ]
        return [rx.toast.warning("No files were uploaded")]

    async def handle_upload_with_metadata(self, files: list[rx.UploadFile]) -> list[EventSpec]:
        """Handle upload of VCF files with metadata from the new sample form.

        This combines file upload and metadata registration in a single operation.
        The metadata from the form (subject_id, sex, tissue, species, etc.) is
        stored in the Dagster asset materialization.

        Returns follow-up events (select file, toasts) instead of yielding them.
        See ``handle_upload`` for why a generator crashes Reflex 0.9 here.
        """
        if _is_immutable_mode():
            return [rx.toast.warning("File upload is disabled in public demo mode. Install locally to analyze your own genome.")]
        if not files:
            return [rx.toast.warning("No files selected for upload")]
            
        self.uploading = True
        new_files = []
        build_warnings: list[str] = []
        try:
            auth_state = await self.get_state(AuthState)
            self.safe_user_id = self._get_safe_user_id(auth_state.user_email)

            upload_dir = get_user_input_dir() / self.safe_user_id
            upload_dir.mkdir(parents=True, exist_ok=True)

            instance = get_dagster_instance()

            for file in files:
                if not file.filename:
                    continue

                content = await file.read()
                if not content:
                    continue

                file_path = upload_dir / file.filename
                file_path.write_bytes(content)

                sample_name = file.filename.replace(".vcf.gz", "").replace(".vcf", "")
                partition_key = f"{self.safe_user_id}/{sample_name}"
                upload_date = datetime.now().strftime("%Y-%m-%d %H:%M")

                # Add partition if missing
                from just_dna_pipelines.annotation.assets import user_vcf_partitions
                existing = instance.get_dynamic_partitions(user_vcf_partitions.name)
                if partition_key not in existing:
                    instance.add_dynamic_partitions(user_vcf_partitions.name, [partition_key])

                # Detect the genome build from the VCF header. The header is
                # authoritative evidence, so it overrides the dropdown selection;
                # we warn when the two disagree so the user notices a wrong pick.
                detected_build = self._detect_build(file_path)
                effective_genome = self.new_sample_reference_genome
                if detected_build:
                    if detected_build != self.new_sample_reference_genome:
                        build_warnings.append(
                            f"{file.filename}: detected {detected_build} from the VCF "
                            f"header — overriding your selection of "
                            f"{self.new_sample_reference_genome}."
                        )
                    effective_genome = detected_build

                # Build complete metadata dict with form values
                metadata: Dict[str, Any] = {
                    "path": MetadataValue.path(str(file_path.absolute())),
                    "size_bytes": MetadataValue.int(len(content)),
                    "uploaded_via": MetadataValue.text("webui"),
                    "upload_date": MetadataValue.text(upload_date),
                    "species": MetadataValue.text(self.new_sample_species),
                    "reference_genome": MetadataValue.text(effective_genome),
                    "reference_genome_source": MetadataValue.text(
                        "header" if detected_build else "manual"
                    ),
                    "sex": MetadataValue.text(self.new_sample_sex),
                    "tissue": MetadataValue.text(self.new_sample_tissue),
                }

                # Add optional fields only if provided
                if self.new_sample_subject_id.strip():
                    metadata["subject_id"] = MetadataValue.text(self.new_sample_subject_id.strip())
                if self.new_sample_study_name.strip():
                    metadata["study_name"] = MetadataValue.text(self.new_sample_study_name.strip())
                if self.new_sample_notes.strip():
                    metadata["notes"] = MetadataValue.text(self.new_sample_notes.strip())

                # Materialize user_vcf_source with all metadata
                instance.report_runless_asset_event(
                    AssetMaterialization(
                        asset_key="user_vcf_source",
                        partition=partition_key,
                        metadata=metadata,
                    )
                )

                # Move re-uploaded files to front (newest first)
                if file.filename in self.files:
                    self.files.remove(file.filename)
                self.files.insert(0, file.filename)
                new_files.append(file.filename)

                # Store in local file_metadata for immediate UI access (full replace, not merge)
                self.file_metadata[file.filename] = {
                    "filename": file.filename,
                    "sample_name": sample_name,
                    "upload_date": upload_date,
                    "species": self.new_sample_species,
                    "reference_genome": effective_genome,
                    "sex": self.new_sample_sex,
                    "tissue": self.new_sample_tissue,
                    "subject_id": self.new_sample_subject_id.strip() if self.new_sample_subject_id else "",
                    "study_name": self.new_sample_study_name.strip() if self.new_sample_study_name else "",
                    "notes": self.new_sample_notes.strip() if self.new_sample_notes else "",
                    "size_mb": round(len(content) / (1024 * 1024), 2),
                    "path": str(file_path),
                    "custom_fields": {},
                }

                # Update status
                self.asset_statuses[partition_key] = {
                    "source": "materialized",
                    "annotated": "uploaded"
                }

        except Exception as exc:
            self.uploading = False
            return [rx.toast.error(f"Upload failed: {exc}")]
        self.uploading = False

        events: list[EventSpec] = [rx.toast.warning(warning) for warning in build_warnings]
        if new_files:
            self._reset_new_sample_form()
            events.append(rx.clear_selected_files("vcf_upload"))
            events.extend(self.select_file(new_files[-1]))
            events.append(rx.toast.success(f"Added {len(new_files)} sample(s) with metadata"))
        else:
            events.append(rx.toast.warning("No files were uploaded"))
        return events

    @rx.event(background=True)
    async def handle_zenodo_import(self) -> list[EventSpec] | None:
        """Import a VCF file from a Zenodo record URL.

        Validates the record (open access, permissive license, has VCF),
        downloads it, places it in the user input directory, and registers
        it as a Dagster asset with Zenodo metadata.
        """
        async with self:
            url = self.zenodo_url_input.strip()
            if not url:
                return
            self.zenodo_importing = True
            self.progress_status = "Validating Zenodo record..."
            safe_user_id = self.safe_user_id

        if not safe_user_id:
            async with self:
                auth_state = await self.get_state(AuthState)
                safe_user_id = self._get_safe_user_id(auth_state.user_email)
                self.safe_user_id = safe_user_id

        loop = asyncio.get_event_loop()

        # 1. Validate
        zenodo_meta: Optional[dict] = None
        try:
            zenodo_meta = await loop.run_in_executor(None, validate_zenodo_record, url)
        except (ValueError, Exception) as exc:
            async with self:
                self.zenodo_importing = False
                self.progress_status = ""
            return [rx.toast.error(str(exc))]

        size_mb = zenodo_meta["vcf_size_bytes"] / (1024 * 1024)

        # 2. Download
        async with self:
            self.progress_status = f"Downloading from Zenodo ({size_mb:.0f} MB)..."

        try:
            cached_path = await loop.run_in_executor(None, download_vcf_from_zenodo, url)
        except Exception as exc:
            async with self:
                self.zenodo_importing = False
                self.progress_status = ""
            return [rx.toast.error(f"Download failed: {exc}")]

        # 3. Place in user input dir
        async with self:
            self.progress_status = "Registering sample..."

        placed_path = await loop.run_in_executor(
            None, ensure_vcf_in_user_input_dir, cached_path, safe_user_id,
        )

        filename = placed_path.name
        sample_name = filename.replace(".vcf.gz", "").replace(".vcf", "")
        partition_key = f"{safe_user_id}/{sample_name}"
        upload_date = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Curated metadata for known public genomes (label, subject id, sex)
        default_sample = _find_default_sample(url, filename)
        subject_id = default_sample.subject_id if default_sample and default_sample.subject_id else sample_name
        sex = default_sample.sex if default_sample else "N/A"
        species = default_sample.species if default_sample else "Homo sapiens"
        reference_genome = default_sample.reference_genome if default_sample else "GRCh38"

        # 4. Register in Dagster
        instance = get_dagster_instance()
        existing = instance.get_dynamic_partitions(user_vcf_partitions.name)
        if partition_key not in existing:
            instance.add_dynamic_partitions(user_vcf_partitions.name, [partition_key])

        metadata: Dict[str, Any] = {
            "path": MetadataValue.path(str(placed_path.absolute())),
            "size_bytes": MetadataValue.int(placed_path.stat().st_size),
            "uploaded_via": MetadataValue.text("zenodo_import"),
            "upload_date": MetadataValue.text(upload_date),
            "source": MetadataValue.text("zenodo"),
            "zenodo_url": MetadataValue.url(url),
            "zenodo_doi": MetadataValue.text(zenodo_meta.get("doi", "")),
            "zenodo_license": MetadataValue.text(zenodo_meta.get("license", "")),
            "zenodo_creator": MetadataValue.text(zenodo_meta.get("creator", "")),
            "zenodo_title": MetadataValue.text(zenodo_meta.get("title", "")),
            "species": MetadataValue.text(species),
            "reference_genome": MetadataValue.text(reference_genome),
            "sex": MetadataValue.text(sex),
            "subject_id": MetadataValue.text(subject_id),
        }

        instance.report_runless_asset_event(
            AssetMaterialization(
                asset_key="user_vcf_source",
                partition=partition_key,
                metadata=metadata,
            )
        )

        # 5. Update UI state
        async with self:
            if filename in self.files:
                self.files.remove(filename)
            self.files.insert(0, filename)

            self.file_metadata[filename] = {
                "filename": filename,
                "sample_name": sample_name,
                "upload_date": upload_date,
                "species": species,
                "reference_genome": reference_genome,
                "sex": sex,
                "tissue": "Sample tissue",
                "subject_id": subject_id,
                "study_name": zenodo_meta.get("title", ""),
                "notes": f"Imported from Zenodo: {url} (License: {zenodo_meta.get('license', 'unknown')})",
                "size_mb": round(placed_path.stat().st_size / (1024 * 1024), 2),
                "path": str(placed_path),
                "custom_fields": {},
                "source": "zenodo",
                "zenodo_url": url,
                "zenodo_license": zenodo_meta.get("license", ""),
            }

            self.zenodo_importing = False
            self.zenodo_url_input = ""
            self.progress_status = ""

        async with self:
            followups = self.select_file(filename)
        return [
            rx.toast.success(f"Imported {filename} from Zenodo ({zenodo_meta.get('creator', 'Unknown')})"),
            *followups,
        ]

    def import_default_sample(self, zenodo_url: str):
        """Set Zenodo URL and trigger import (for one-click buttons)."""
        self.zenodo_url_input = zenodo_url
        return UploadState.handle_zenodo_import

    @rx.event(background=True)
    async def execute_job_in_compute(
        self,
        job_name: str,
        run_config: dict,
        partition_key: str,
        sample_name: str,
        status_field: str,
        label: str = "",
    ):
        """Run a Dagster job in a compute child, tracking ``asset_statuses``.

        The job used to run via ``execute_in_process`` directly inside the event
        handler, which put the entire annotation pipeline — Polars ``sink_parquet``,
        ``polars_bio.scan_vcf`` and its Tokio runtime, DuckDB joins — on the single ASGI
        worker's event loop for minutes at a time.  Now it runs in a spawned child and
        this handler only polls, so the UI stays responsive and the run is killable.
        """
        token = f"{status_field}:{partition_key}"
        handle = submit_job(
            token, job_name, run_config, partition_key, user_vcf_partitions.name
        )
        async with self:
            UploadState._active_inproc_runs[token] = partition_key
        try:
            result = await await_job(handle)
        finally:
            forget_job(token)
            async with self:
                UploadState._active_inproc_runs.pop(token, None)

        async with self:
            statuses = dict(self.asset_statuses)
            per_partition = dict(statuses.get(partition_key, {}))
            per_partition[status_field] = "completed" if result.success else "failed"
            statuses[partition_key] = per_partition
            self.asset_statuses = statuses

        suffix = f" with {label}" if label else ""
        if result.success:
            yield rx.toast.success(f"Annotation completed for {sample_name}{suffix}")
        else:
            detail = f": {result.error}" if result.error else ""
            yield rx.toast.error(f"Annotation failed for {sample_name}{detail}")

    async def run_annotation(self, filename: str = ""):
        """Trigger materialization of user_annotated_vcf_duckdb for a file."""
        if not filename:
            filename = self.selected_file
        if not filename:
            return

        if not self.safe_user_id:
            auth_state = await self.get_state(AuthState)
            self.safe_user_id = self._get_safe_user_id(auth_state.user_email)
        
        sample_name = filename.replace(".vcf.gz", "").replace(".vcf", "")
        partition_key = f"{self.safe_user_id}/{sample_name}"
        
        vcf_path = get_user_input_dir() / self.safe_user_id / filename

        # Update status to running immediately
        if partition_key not in self.asset_statuses:
            self.asset_statuses[partition_key] = {}
        self.asset_statuses[partition_key]["annotated"] = "running"
        yield

        run_config = {
            "ops": {
                "annotate_user_vcf_duckdb_op": {
                    "config": {
                        "vcf_path": str(vcf_path.absolute()),
                        "user_name": self.safe_user_id,
                        "sample_name": sample_name
                    }
                }
            }
        }

        # Hand off to a compute child; execute_job_in_compute polls it without blocking.
        yield UploadState.execute_job_in_compute(
            "annotate_vcf_duckdb_job",
            run_config,
            partition_key,
            sample_name,
            "annotated",
        )

    def toggle_module(self, module: str) -> Any:
        """Toggle a module on/off in the selection."""
        self.last_run_success = False
        if module in self.selected_modules:
            self.selected_modules = [m for m in self.selected_modules if m != module]
        else:
            if module not in MODULE_INFOS:
                yield rx.toast.error(f"Module '{module}' not found in registry — it may have been removed")
                return
            self.selected_modules = self.selected_modules + [module]

    def select_all_modules(self):
        """Select all available modules."""
        self.last_run_success = False
        self.selected_modules = self.available_modules.copy()

    def deselect_all_modules(self):
        """Deselect all modules."""
        self.last_run_success = False
        self.selected_modules = []

    # ============================================================
    # Custom Module Registry
    # ============================================================

    def remove_custom_module(self, module_name: str):
        """Remove a custom module, update modules.yaml, refresh UI."""
        removed = unregister_custom_module(module_name)
        if not removed:
            yield rx.toast.error(f"Module '{module_name}' not found in custom modules")
            return

        self._refresh_module_ui_state()
        yield
        yield rx.toast.info(f"Module '{module_name}' removed")

    def _refresh_module_ui_state(self):
        """Re-read MODULE_INFOS globals and update UI state vars."""
        # Snapshot keys once to avoid reading a dict being mutated by another thread
        current_keys = list(MODULE_INFOS.keys())
        MODULE_METADATA.update(build_module_metadata_dict(current_keys))
        for stale in list(MODULE_METADATA.keys()):
            if stale not in current_keys:
                MODULE_METADATA.pop(stale, None)
        old_available = set(self.available_modules)
        self.available_modules = sorted(current_keys)
        new_available = set(self.available_modules)
        # Keep existing selections (removing modules no longer available)
        kept = [m for m in self.selected_modules if m in new_available]
        # Auto-select newly discovered modules
        newly_added = sorted(new_available - old_available)
        self.selected_modules = kept + [m for m in newly_added if m not in kept]

    def refresh_module_registry_state(self):
        """Public event: refresh discovery from disk and re-sync UI state.

        Used by the module manager page on load so hard refreshes reflect the
        mutable modules.yaml instead of import-time defaults.
        """
        refresh_module_registry()
        self._refresh_module_ui_state()

    def load_modules_page(self):
        """Initialize the module manager page."""
        self.refresh_module_registry_state()

    def toggle_ensembl(self):
        """Toggle Ensembl variation annotation on/off."""
        self.last_run_success = False
        self.include_ensembl = not self.include_ensembl

    async def run_hf_annotation(self, filename: str = ""):
        """
        Trigger HF module annotation for a file.
        
        Uses the selected_modules list to determine which modules to use.
        If no modules are selected, uses all available modules.
        """
        if not filename:
            filename = self.selected_file
        if not filename:
            return

        if not self.safe_user_id:
            auth_state = await self.get_state(AuthState)
            self.safe_user_id = self._get_safe_user_id(auth_state.user_email)
        
        sample_name = filename.replace(".vcf.gz", "").replace(".vcf", "")
        partition_key = f"{self.safe_user_id}/{sample_name}"
        
        root = Path(__file__).resolve().parents[3]
        vcf_path = get_user_input_dir() / self.safe_user_id / filename
        
        instance = get_dagster_instance()
        
        # Update status to running immediately
        if partition_key not in self.asset_statuses:
            self.asset_statuses[partition_key] = {}
        self.asset_statuses[partition_key]["hf_annotated"] = "running"
        yield
        
        has_hf_modules = bool(self.selected_modules)
        has_ensembl = self.include_ensembl
        
        # Determine job based on what's selected
        if has_hf_modules and has_ensembl:
            job_name = "annotate_all_job"
        elif has_ensembl:
            job_name = "annotate_ensembl_only_job"
        else:
            job_name = "annotate_and_report_job"
        
        modules_to_use = self.selected_modules if has_hf_modules else None
        
        # Get file metadata for the selected file
        file_info = self.file_metadata.get(filename, {})
        custom_metadata = file_info.get("custom_fields", {}) or {}
        
        normalize_config: dict = {
            "vcf_path": str(vcf_path.absolute()),
        }
        sex_value = file_info.get("sex") or None
        if sex_value:
            normalize_config["sex"] = sex_value

        run_config: dict = {
            "ops": {
                "user_vcf_normalized": {
                    "config": normalize_config,
                },
            }
        }

        if has_hf_modules:
            run_config["ops"]["user_hf_module_annotations"] = {
                "config": {
                    "vcf_path": str(vcf_path.absolute()),
                    "user_name": self.safe_user_id,
                    "sample_name": sample_name,
                    "modules": modules_to_use,
                    "species": file_info.get("species", "Homo sapiens"),
                    "reference_genome": file_info.get("reference_genome", "GRCh38"),
                    "subject_id": file_info.get("subject_id") or None,
                    "sex": sex_value,
                    "tissue": file_info.get("tissue") or None,
                    "study_name": file_info.get("study_name") or None,
                    "description": file_info.get("notes") or None,
                    "custom_metadata": custom_metadata if custom_metadata else None,
                }
            }
            run_config["ops"]["user_longevity_report"] = {
                "config": {
                    "user_name": self.safe_user_id,
                    "sample_name": sample_name,
                    "modules": modules_to_use,
                }
            }

        if has_ensembl:
            run_config["ops"]["user_annotated_vcf_duckdb"] = {
                "config": {
                    "vcf_path": str(vcf_path.absolute()),
                    "user_name": self.safe_user_id,
                    "sample_name": sample_name,
                }
            }

        modules_info = ", ".join(modules_to_use) if modules_to_use else ("Ensembl only" if has_ensembl else "all modules")
        yield UploadState.execute_job_in_compute(
            job_name,
            run_config,
            partition_key,
            sample_name,
            "hf_annotated",
            modules_info,
        )

    vcf_exporting: bool = False
    vcf_export_run_id: str = ""

    @rx.var
    def vcf_export_dagster_url(self) -> str:
        """Dagster UI link for the active VCF export run."""
        if not self.vcf_export_run_id:
            return ""
        return f"{get_dagster_web_url()}/runs/{self.vcf_export_run_id}"

    async def run_vcf_export(self):
        """Manually trigger VCF export for the currently selected file.

        Uses the same daemon-with-fallback pattern as ``start_annotation_run``
        so that ``poll_run_status`` picks up completion and clears the spinner.
        """
        if not self.selected_file:
            yield rx.toast.error("Please select a file")
            return
        if self.vcf_exporting:
            yield rx.toast.warning("VCF export already in progress")
            return

        self.vcf_exporting = True
        self._add_log("Starting VCF export...")
        yield

        if not self.safe_user_id:
            auth_state = await self.get_state(AuthState)
            self.safe_user_id = self._get_safe_user_id(auth_state.user_email)

        sample_name = self.selected_file.replace(".vcf.gz", "").replace(".vcf", "")
        partition_key = f"{self.safe_user_id}/{sample_name}"

        instance = get_dagster_instance()
        job_name = "export_vcf_job"

        run_config: dict = {
            "ops": {
                "user_vcf_exports": {
                    "config": {
                        "user_name": self.safe_user_id,
                        "sample_name": sample_name,
                    }
                }
            }
        }

        try:
            job_def = defs.resolve_job_def(job_name)
            run = instance.create_run_for_job(
                job_def=job_def,
                run_config=run_config,
                tags={
                    "dagster/partition": partition_key,
                    "source": "webui",
                },
            )
            run_id = run.run_id
            self._add_log(f"Created VCF export run: {run_id}")
        except Exception as e:
            self._add_log(f"Failed to create VCF export run: {e}")
            self.vcf_exporting = False
            yield rx.toast.error(f"VCF export failed: {e}")
            return

        run_info = {
            "run_id": run_id,
            "filename": self.selected_file,
            "sample_name": sample_name,
            "modules": [],
            "status": "QUEUED",
            "started_at": datetime.now().isoformat(),
            "ended_at": None,
            "output_path": None,
            "error": None,
            "dagster_url": f"{get_dagster_web_url()}/runs/{run_id}",
            "job_type": "vcf_export",
        }
        self.runs = [run_info] + self.runs
        self.active_run_id = run_id
        self.vcf_export_run_id = run_id
        self.polling_active = True
        yield

        daemon_success, daemon_error = self._try_submit_to_daemon(instance, run_id)

        if daemon_success:
            self._add_log(f"VCF export run {run_id} submitted to daemon.")
            yield rx.toast.info(f"VCF export started for {sample_name}")
        else:
            self._add_log(f"Daemon submission failed: {daemon_error}")
            self._add_log("Running VCF export in-process...")
            yield rx.toast.info(f"Exporting VCF for {sample_name} — please wait...")

            instance.delete_run(run_id)

            self._inproc_discover_partition = partition_key
            self._inproc_discover_since = time.time()
            self._inproc_original_run_id = run_id

            updated_runs = []
            for r in self.runs:
                if r["run_id"] == run_id:
                    r["status"] = "RUNNING"
                updated_runs.append(r)
            self.runs = updated_runs

            yield UploadState.execute_job_with_run_discovery(
                job_name, run_config, partition_key, run_id, sample_name
            )

    @rx.var
    def file_statuses(self) -> Dict[str, str]:
        """Map filenames to their annotation status for the UI."""
        res = {}
        for f in self.files:
            sample_name = f.replace(".vcf.gz", "").replace(".vcf", "")
            pk = f"{self.safe_user_id}/{sample_name}"
            status = self.asset_statuses.get(pk, {}).get("annotated", "uploaded")
            res[f] = status
        return res

    # Currently selected file for annotation
    selected_file: str = ""
    # Staged by select_file so sibling grids reset before this remounts the workspace.
    _pending_selected_file: str = ""
    
    # File metadata cache: filename -> {size_mb, upload_date, reference_genome, sample_name}
    file_metadata: Dict[str, Dict[str, Any]] = {}
    
    # Run history tracking
    runs: List[Dict[str, Any]] = []
    active_run_id: str = ""
    run_logs: List[str] = []
    polling_active: bool = False
    # When set, poll_run_status will search for the real run created in the compute child
    _inproc_discover_partition: str = ""
    _inproc_discover_since: float = 0.0
    _inproc_original_run_id: str = ""
    
    # Tracking for the UI button state
    last_run_success: bool = False
    focused_output_path: str = ""
    
    # Tab management for two-panel layout (legacy, kept for backwards compatibility)
    active_tab: str = "params"  # "params", "history", "outputs"
    
    # Output files for the selected sample
    output_files: List[Dict[str, Any]] = []
    report_files: List[Dict[str, Any]] = []  # HTML report files
    outputs_loaded_for_file: str = ""

    # Data preview state (server-side grid state is managed by LazyFrameGridMixin)
    vcf_preview_loading: bool = False
    vcf_preview_error: str = ""
    preview_source_label: str = ""  # e.g. "input.vcf.gz"

    # Normalization filter stats (loaded from Dagster materialization metadata)
    norm_rows_before: int = 0
    norm_rows_after: int = 0
    norm_rows_removed: int = 0
    norm_filters_hash: str = ""
    norm_stats_loaded: bool = False
    
    # Run-centric UI state
    vcf_preview_expanded: bool = True  # Whether the VCF preview section is expanded
    outputs_expanded: bool = True  # Whether the outputs section is expanded
    run_history_expanded: bool = True  # Whether the run history section is expanded
    new_analysis_expanded: bool = True  # Whether the new analysis section is expanded
    right_panel_active_tab: str = "input"  # "input", "prs", "annotated_files", "reports", "analysis"
    tab_order: list[str] = DEFAULT_TAB_ORDER  # drag-reorderable tab list
    _drag_tab_id: str = ""  # internal: id of the tab being dragged (cleared after drop)
    show_input_tab_info: bool = True
    show_prs_tab_info: bool = True
    show_annotated_files_tab_info: bool = True
    show_reports_tab_info: bool = True
    show_analysis_tab_info: bool = True
    show_welcome_disclaimer: bool = True
    expanded_run_id: str = ""  # Which run in the timeline is expanded to show logs
    show_outputs_modal: bool = False  # Whether to show the outputs modal (legacy, kept for compatibility)
    
    # Metadata editing mode - when False, shows read-only view
    metadata_edit_mode: bool = False


    def toggle_metadata_edit_mode(self):
        """Toggle between read-only and edit mode for metadata."""
        self.metadata_edit_mode = not self.metadata_edit_mode

    def enable_metadata_edit_mode(self):
        """Enable edit mode for metadata."""
        self.metadata_edit_mode = True

    def disable_metadata_edit_mode(self):
        """Disable edit mode (back to read-only)."""
        self.metadata_edit_mode = False

    @rx.var
    def has_vcf_preview(self) -> bool:
        """Check if data grid has been loaded (VCF or output file)."""
        return bool(self.lf_grid_loaded)

    @rx.var
    def vcf_preview_row_count(self) -> int:
        """Get total filtered row count in the data grid."""
        return int(self.lf_grid_row_count)

    @rx.var
    def has_vcf_preview_error(self) -> bool:
        """Check if data preview failed to load."""
        return bool(self.vcf_preview_error)

    @rx.var
    def has_norm_stats(self) -> bool:
        """True when normalization filter stats are available."""
        return self.norm_stats_loaded and self.norm_rows_before > 0

    @rx.var
    def norm_removed_pct(self) -> str:
        """Percentage of rows removed by quality filters."""
        if self.norm_rows_before == 0:
            return "0.0"
        pct = (self.norm_rows_removed / self.norm_rows_before) * 100
        return f"{pct:.1f}"

    @rx.var
    def norm_filters_active(self) -> bool:
        """True when quality filters actually removed rows."""
        return self.norm_rows_removed > 0

    @rx.var
    def sample_display_names(self) -> Dict[str, str]:
        """
        Map filenames to display names.

        Known public genomes (configured as default samples in modules.yaml)
        show their curated label (e.g. "Livia Zaharia" instead of the
        provider's anonymized filename). Otherwise Subject ID if available,
        otherwise the filename stem.
        """
        default_labels = {
            s.filename: s.label
            for s in get_immutable_config().default_samples
            if s.filename
        }
        result = {}
        for filename in self.files:
            meta = self.file_metadata.get(filename, {})
            subject_id = (meta.get("subject_id") or "").strip()
            if filename in default_labels:
                result[filename] = default_labels[filename]
            elif subject_id:
                result[filename] = subject_id
            else:
                result[filename] = _vcf_sample_stem(filename)
        return result

    @rx.var
    def default_public_samples(self) -> List[Dict[str, Any]]:
        """Public genomes from modules.yaml with per-sample imported status.

        Drives the "Try a public genome" hint so the list (and the Zenodo
        URLs) live in config, not in the UI code.
        """
        return [
            {
                "label": sample.label,
                "license": sample.license,
                "zenodo_url": sample.zenodo_url,
                "imported": bool(sample.filename and sample.filename in self.files),
            }
            for sample in get_immutable_config().default_samples
        ]

    @rx.var
    def sample_upload_dates(self) -> Dict[str, str]:
        """Map filenames to their upload date strings for display."""
        result = {}
        for filename in self.files:
            meta = self.file_metadata.get(filename, {})
            result[filename] = meta.get("upload_date", "")
        return result

    def _load_file_metadata(self, filename: str):
        """Load metadata for a single VCF file."""
        if not self.safe_user_id:
            return
            
        root = Path(__file__).resolve().parents[3]
        file_path = get_user_input_dir() / self.safe_user_id / filename
        
        if not file_path.exists():
            return
        
        # Get file stats
        stat = file_path.stat()
        size_mb = round(stat.st_size / (1024 * 1024), 2)
        upload_date = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        
        # Derive sample name
        sample_name = filename.replace(".vcf.gz", "").replace(".vcf", "")
        
        # Default species and reference genome (Latin names)
        species = "Homo sapiens"
        reference_genome = "GRCh38"
        
        self.file_metadata[filename] = {
            "filename": filename,
            "sample_name": sample_name,
            "size_mb": size_mb,
            "upload_date": upload_date,
            "species": species,
            "reference_genome": reference_genome,
            "path": str(file_path),
            # User-editable fields (required fields have defaults)
            "subject_id": "",  # Required - subject/patient identifier
            "sex": "N/A",  # Required - biological sex
            "tissue": "Sample tissue",  # Required - sample tissue source
            # Optional fields
            "study_name": "",
            "notes": "",
            # Custom key-value fields (user can add their own)
            "custom_fields": {},  # Dict[str, str] for user-defined fields
        }

    def _clear_vcf_preview(self):
        """Clear data preview and reset server-side grid state."""
        self.reset_grid_view_state()
        self.lf_grid_rows = []
        self.lf_grid_columns = []
        self.lf_grid_row_count = 0
        self.lf_grid_loading = False
        self.lf_grid_loaded = False
        self.lf_grid_stats = ""
        self.lf_grid_selected_info = "Click a row to see details."
        self.clear_grid_source()
        self.vcf_preview_error = ""
        self.vcf_preview_loading = False
        self.preview_source_label = ""
        self._clear_norm_stats()

    def _clear_sample_outputs(self) -> None:
        """Drop annotation and report lists so another genome cannot inherit them."""
        self.output_files = []
        self.report_files = []
        self.outputs_loaded_for_file = ""
        self.focused_output_path = ""

    def _clear_norm_stats(self):
        """Reset normalization filter statistics."""
        self.norm_rows_before = 0
        self.norm_rows_after = 0
        self.norm_rows_removed = 0
        self.norm_filters_hash = ""
        self.norm_stats_loaded = False


    def _load_norm_stats_from_dagster(self):
        """Load normalization filter stats from the latest Dagster materialization.

        Also detects stale parquets: if the stored quality_filters_hash differs
        from the current config hash, re-runs normalization automatically.
        """
        if not self.selected_file or not self.safe_user_id:
            self._clear_norm_stats()
            return

        sample_name = self.selected_file.replace(".vcf.gz", "").replace(".vcf", "")
        partition_key = f"{self.safe_user_id}/{sample_name}"
        instance = get_dagster_instance()

        result = instance.fetch_materializations(
            records_filter=AssetRecordsFilter(
                asset_key=AssetKey("user_vcf_normalized"),
                asset_partitions=[partition_key],
            ),
            limit=1,
        )
        if not result.records:
            self._clear_norm_stats()
            return

        mat = result.records[0].asset_materialization
        if not mat or not mat.metadata:
            self._clear_norm_stats()
            return

        def _int(key: str) -> int:
            v = mat.metadata.get(key)
            return int(v.value) if v and hasattr(v, "value") else 0

        def _str(key: str) -> str:
            v = mat.metadata.get(key)
            return str(v.value) if v and hasattr(v, "value") else ""

        self.norm_rows_before = _int("rows_before_filter")
        self.norm_rows_after = _int("rows_after_filter")
        self.norm_rows_removed = _int("rows_removed")
        self.norm_filters_hash = _str("quality_filters_hash")
        self.norm_stats_loaded = True

    def _get_expected_normalized_parquet_path(self) -> Optional[Path]:
        """Return the canonical normalized parquet path regardless of whether it exists yet."""
        if not self.selected_file or not self.safe_user_id:
            return None
        sample_name = self.selected_file.replace(".vcf.gz", "").replace(".vcf", "")
        return get_user_output_dir() / self.safe_user_id / sample_name / "user_vcf_normalized.parquet"

    def _get_normalized_parquet_path(self) -> Optional[Path]:
        """Return the normalized parquet path only if it is readable and non-empty."""
        path = self._get_expected_normalized_parquet_path()
        if path is not None and _parquet_is_ready(path):
            return path
        return None

    def _yield_prs_init_events(self) -> List[EventSpec]:
        """Initialize PRS after select_file has already reset sample/grid state."""
        normalized_parquet = self._get_normalized_parquet_path()
        parquet_str = str(normalized_parquet) if normalized_parquet is not None else ""
        ref_genome = self.file_metadata.get(self.selected_file, {}).get("reference_genome", "GRCh38")
        # Grid/sample reset already ran in select_file before remount.
        # Resetting again here would replace the remount-replay fingerprint
        # with an empty model and let the previous filter write itself back.
        if parquet_str:
            return [PRSState.initialize_prs_for_file(parquet_str, ref_genome)]
        return []

    def update_file_species(self, species: str):
        """Update species for the selected file and reset reference genome to default."""
        if not self.selected_file or self.selected_file not in self.file_metadata:
            return
        
        # Get default reference genome for this species
        default_ref = REFERENCE_GENOMES.get(species, ["custom"])[0]
        
        # Update metadata - need to create new dict for reactivity
        updated = dict(self.file_metadata)
        updated[self.selected_file] = dict(updated[self.selected_file])
        updated[self.selected_file]["species"] = species
        updated[self.selected_file]["reference_genome"] = default_ref
        self.file_metadata = updated
        
        # Auto-save to Dagster
        self.save_metadata_to_dagster()

    def update_file_reference_genome(self, ref_genome: str):
        """Update reference genome for the selected file."""
        if not self.selected_file or self.selected_file not in self.file_metadata:
            return
        # Create new dict for reactivity
        updated = dict(self.file_metadata)
        updated[self.selected_file] = dict(updated[self.selected_file])
        updated[self.selected_file]["reference_genome"] = ref_genome
        self.file_metadata = updated
        
        # Auto-save to Dagster
        self.save_metadata_to_dagster()

    def update_file_subject_id(self, subject_id: str):
        """Update subject/patient ID for the selected file."""
        if not self.selected_file or self.selected_file not in self.file_metadata:
            return
        updated = dict(self.file_metadata)
        updated[self.selected_file] = dict(updated[self.selected_file])
        updated[self.selected_file]["subject_id"] = subject_id
        self.file_metadata = updated

    def update_file_sex(self, sex: str):
        """Update biological sex for the selected file."""
        if not self.selected_file or self.selected_file not in self.file_metadata:
            return
        updated = dict(self.file_metadata)
        updated[self.selected_file] = dict(updated[self.selected_file])
        updated[self.selected_file]["sex"] = sex
        self.file_metadata = updated

    def update_file_tissue(self, tissue: str):
        """Update tissue source for the selected file."""
        if not self.selected_file or self.selected_file not in self.file_metadata:
            return
        updated = dict(self.file_metadata)
        updated[self.selected_file] = dict(updated[self.selected_file])
        updated[self.selected_file]["tissue"] = tissue
        self.file_metadata = updated

    def update_file_study_name(self, study_name: str):
        """Update study/project name for the selected file."""
        if not self.selected_file or self.selected_file not in self.file_metadata:
            return
        updated = dict(self.file_metadata)
        updated[self.selected_file] = dict(updated[self.selected_file])
        updated[self.selected_file]["study_name"] = study_name
        self.file_metadata = updated

    def update_file_notes(self, notes: str):
        """Update notes for the selected file."""
        if not self.selected_file or self.selected_file not in self.file_metadata:
            return
        updated = dict(self.file_metadata)
        updated[self.selected_file] = dict(updated[self.selected_file])
        updated[self.selected_file]["notes"] = notes
        self.file_metadata = updated

    def add_custom_field(self, field_name: str, field_value: str):
        """Add or update a custom field for the selected file."""
        if not self.selected_file or self.selected_file not in self.file_metadata:
            return
        updated = dict(self.file_metadata)
        updated[self.selected_file] = dict(updated[self.selected_file])
        custom_fields = dict(updated[self.selected_file].get("custom_fields", {}))
        custom_fields[field_name] = field_value
        updated[self.selected_file]["custom_fields"] = custom_fields
        self.file_metadata = updated
        
        # Auto-save to Dagster when custom fields change
        self.save_metadata_to_dagster()

    def remove_custom_field(self, field_name: str):
        """Remove a custom field from the selected file."""
        if not self.selected_file or self.selected_file not in self.file_metadata:
            return
        updated = dict(self.file_metadata)
        updated[self.selected_file] = dict(updated[self.selected_file])
        custom_fields = dict(updated[self.selected_file].get("custom_fields", {}))
        if field_name in custom_fields:
            del custom_fields[field_name]
        updated[self.selected_file]["custom_fields"] = custom_fields
        self.file_metadata = updated
        
        # Auto-save to Dagster when custom fields change
        self.save_metadata_to_dagster()

    # State for adding new custom field
    new_custom_field_name: str = ""
    new_custom_field_value: str = ""

    def set_new_field_name(self, name: str):
        """Set the name for a new custom field."""
        self.new_custom_field_name = name

    def set_new_field_value(self, value: str):
        """Set the value for a new custom field."""
        self.new_custom_field_value = value

    def save_new_custom_field(self):
        """Save the new custom field to the file metadata."""
        if self.new_custom_field_name.strip():
            self.add_custom_field(self.new_custom_field_name.strip(), self.new_custom_field_value)
            self.new_custom_field_name = ""
            self.new_custom_field_value = ""

    def _build_dagster_metadata(self, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build Dagster metadata dict from file_info.
        
        Returns a dict suitable for AssetMaterialization.metadata.
        All values are wrapped in MetadataValue types.
        """
        metadata: Dict[str, Any] = {}
        
        # Well-known fields
        if file_info.get("filename"):
            metadata["filename"] = MetadataValue.text(file_info["filename"])
        if file_info.get("sample_name"):
            metadata["sample_name"] = MetadataValue.text(file_info["sample_name"])
        if file_info.get("species"):
            metadata["species"] = MetadataValue.text(file_info["species"])
        if file_info.get("reference_genome"):
            metadata["reference_genome"] = MetadataValue.text(file_info["reference_genome"])
        if file_info.get("subject_id"):
            metadata["subject_id"] = MetadataValue.text(file_info["subject_id"])
        if file_info.get("sex"):
            metadata["sex"] = MetadataValue.text(file_info["sex"])
        if file_info.get("tissue"):
            metadata["tissue"] = MetadataValue.text(file_info["tissue"])
        if file_info.get("study_name"):
            metadata["study_name"] = MetadataValue.text(file_info["study_name"])
        if file_info.get("notes"):
            metadata["description"] = MetadataValue.text(file_info["notes"])
        if file_info.get("path"):
            metadata["path"] = MetadataValue.path(file_info["path"])
        if file_info.get("size_mb"):
            metadata["size_mb"] = MetadataValue.float(file_info["size_mb"])
        if file_info.get("upload_date"):
            metadata["upload_date"] = MetadataValue.text(file_info["upload_date"])
        
        # Custom fields - store as JSON and also individually
        custom_fields = file_info.get("custom_fields", {})
        if custom_fields:
            metadata["custom_metadata"] = MetadataValue.json(custom_fields)
            for key, value in custom_fields.items():
                safe_key = "".join(c if c.isalnum() or c == "_" else "_" for c in key)
                metadata[f"custom/{safe_key}"] = MetadataValue.text(str(value))
        
        if file_info.get("source"):
            metadata["source"] = MetadataValue.text(file_info["source"])
        if file_info.get("zenodo_url"):
            metadata["zenodo_url"] = MetadataValue.url(file_info["zenodo_url"])
        if file_info.get("zenodo_license"):
            metadata["zenodo_license"] = MetadataValue.text(file_info["zenodo_license"])

        # Mark as saved from UI
        metadata["saved_from"] = MetadataValue.text("webui")
        
        return metadata

    def _extract_metadata_from_materialization(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract file_info dict from Dagster materialization metadata.
        
        Converts MetadataValue objects back to plain Python values.
        """
        file_info: Dict[str, Any] = {}
        
        def get_value(mv: Any) -> Any:
            """Extract value from MetadataValue or return as-is."""
            if hasattr(mv, 'value'):
                return mv.value
            return mv
        
        # Well-known fields
        if "filename" in metadata:
            file_info["filename"] = get_value(metadata["filename"])
        if "sample_name" in metadata:
            file_info["sample_name"] = get_value(metadata["sample_name"])
        if "species" in metadata:
            file_info["species"] = get_value(metadata["species"])
        if "reference_genome" in metadata:
            file_info["reference_genome"] = get_value(metadata["reference_genome"])
        if "subject_id" in metadata:
            file_info["subject_id"] = get_value(metadata["subject_id"])
        if "sex" in metadata:
            file_info["sex"] = get_value(metadata["sex"])
        if "tissue" in metadata:
            file_info["tissue"] = get_value(metadata["tissue"])
        if "study_name" in metadata:
            file_info["study_name"] = get_value(metadata["study_name"])
        if "description" in metadata:
            file_info["notes"] = get_value(metadata["description"])
        if "path" in metadata:
            file_info["path"] = get_value(metadata["path"])
        if "size_mb" in metadata:
            file_info["size_mb"] = get_value(metadata["size_mb"])
        if "upload_date" in metadata:
            file_info["upload_date"] = get_value(metadata["upload_date"])
        if "source" in metadata:
            file_info["source"] = get_value(metadata["source"])
        if "zenodo_url" in metadata:
            file_info["zenodo_url"] = get_value(metadata["zenodo_url"])
        if "zenodo_license" in metadata:
            file_info["zenodo_license"] = get_value(metadata["zenodo_license"])

        # Custom fields - prefer the JSON blob if available
        if "custom_metadata" in metadata:
            custom = get_value(metadata["custom_metadata"])
            if isinstance(custom, dict):
                file_info["custom_fields"] = custom
        else:
            # Fallback: extract from individual custom/* keys
            custom_fields = {}
            for key, value in metadata.items():
                if key.startswith("custom/"):
                    field_name = key[7:]  # Remove "custom/" prefix
                    custom_fields[field_name] = get_value(value)
            if custom_fields:
                file_info["custom_fields"] = custom_fields
        
        return file_info

    def save_metadata_to_dagster(self):
        """
        Persist current file metadata to Dagster as an AssetMaterialization.
        
        This creates a new materialization event for user_vcf_source with the
        current metadata. The metadata is then visible in the Dagster UI and
        survives UI restarts.
        """
        if not self.selected_file or self.selected_file not in self.file_metadata:
            return
        
        file_info = self.file_metadata[self.selected_file]
        sample_name = file_info.get("sample_name", self.selected_file.replace(".vcf.gz", "").replace(".vcf", ""))
        partition_key = f"{self.safe_user_id}/{sample_name}"
        
        instance = get_dagster_instance()
        metadata = self._build_dagster_metadata(file_info)
        
        instance.report_runless_asset_event(
            AssetMaterialization(
                asset_key="user_vcf_source",
                partition=partition_key,
                metadata=metadata,
            )
        )
        
        return rx.toast.success(f"Metadata saved for {sample_name}")

    def _load_metadata_from_dagster(self):
        """
        Load file metadata from Dagster materializations.
        
        Queries all user_vcf_source partitions for the current user and
        extracts metadata from the latest materialization of each.
        """
        if not self.safe_user_id:
            return
        
        instance = get_dagster_instance()
        
        # Get all partitions for this user
        from just_dna_pipelines.annotation.assets import user_vcf_partitions
        all_partitions = instance.get_dynamic_partitions(user_vcf_partitions.name)
        user_partitions = [p for p in all_partitions if p.startswith(f"{self.safe_user_id}/")]
        
        for partition_key in user_partitions:
            # Fetch latest materialization for this partition
            result = instance.fetch_materializations(
                records_filter=AssetRecordsFilter(
                    asset_key=AssetKey("user_vcf_source"),
                    asset_partitions=[partition_key],
                ),
                limit=1,
            )
            
            if not result.records:
                continue
            
            record = result.records[0]
            mat = record.asset_materialization
            if not mat or not mat.metadata:
                continue
            
            # Extract metadata
            dagster_info = self._extract_metadata_from_materialization(mat.metadata)
            
            # Get filename from partition key or metadata
            filename = dagster_info.get("filename")
            if not filename:
                # Derive from partition key
                sample_name = partition_key.split("/", 1)[1] if "/" in partition_key else partition_key
                # Try to find matching file
                for f in self.files:
                    if f.startswith(sample_name):
                        filename = f
                        break
            
            if filename and filename in self.files:
                # Dagster metadata fully replaces existing metadata to avoid
                # stale fields from a previous upload leaking into a re-upload
                existing = self.file_metadata.get(filename, {})
                # Keep only filesystem-derived fields that Dagster doesn't track
                base = {
                    "filename": existing.get("filename", filename),
                    "sample_name": existing.get("sample_name", ""),
                    "size_mb": existing.get("size_mb", 0),
                    "upload_date": existing.get("upload_date", ""),
                    "path": existing.get("path", ""),
                    "custom_fields": {},
                }
                # Dagster metadata overwrites everything it provides
                base.update(dagster_info)
                self.file_metadata[filename] = base

    @rx.var
    def current_custom_fields(self) -> Dict[str, str]:
        """Get custom fields for the currently selected file."""
        if not self.selected_file:
            return {}
        return self.file_metadata.get(self.selected_file, {}).get("custom_fields", {})

    @rx.var
    def custom_fields_list(self) -> List[Dict[str, str]]:
        """Get custom fields as a list for rx.foreach."""
        fields = self.current_custom_fields
        return [{"name": k, "value": v} for k, v in fields.items()]

    @rx.var
    def has_custom_fields(self) -> bool:
        """Check if there are any custom fields."""
        return len(self.current_custom_fields) > 0

    @rx.var(cache=True)
    def backend_api_url(self) -> str:
        """Get the backend API URL prefix for downloads/reports.

        Custom API routes (via api_transformer) are served by the Reflex
        backend only.  The frontend dev server does NOT proxy arbitrary
        ``/api/...`` paths — it only forwards Reflex-internal routes
        (``/_event``, ``/_upload``, etc.).  Relative URLs therefore 404
        on the frontend.

        ``webui.run`` selects a free backend port and persists it in
        ``API_URL`` / ``REFLEX_BACKEND_PORT``.  We read those here so
        the browser constructs direct URLs to the backend
        (e.g. ``http://localhost:8002/api/report/...``).
        """
        return _backend_api_url()

    @rx.var
    def current_subject_id(self) -> str:
        """Get subject ID for the currently selected file."""
        if not self.selected_file:
            return ""
        return self.file_metadata.get(self.selected_file, {}).get("subject_id", "")

    @rx.var
    def current_study_name(self) -> str:
        """Get study name for the currently selected file."""
        if not self.selected_file:
            return ""
        return self.file_metadata.get(self.selected_file, {}).get("study_name", "")

    @rx.var
    def current_notes(self) -> str:
        """Get notes for the currently selected file."""
        if not self.selected_file:
            return ""
        return self.file_metadata.get(self.selected_file, {}).get("notes", "")

    @rx.var
    def current_species(self) -> str:
        """Get species for the currently selected file."""
        if not self.selected_file:
            return "Homo sapiens"
        return self.file_metadata.get(self.selected_file, {}).get("species", "Homo sapiens")

    @rx.var
    def current_reference_genome(self) -> str:
        """Get reference genome for the currently selected file."""
        if not self.selected_file:
            return "GRCh38"
        return self.file_metadata.get(self.selected_file, {}).get("reference_genome", "GRCh38")

    @rx.var
    def prs_comparable_samples(self) -> List[Dict[str, str]]:
        """Other left-panel samples that share species + genome and are PRS-ready."""
        if not self.selected_file or not self.safe_user_id:
            return []
        user_id = self.safe_user_id
        return comparable_prs_samples(
            list(self.files),
            self.selected_file,
            self.file_metadata,
            is_ready=lambda filename: _parquet_is_ready(
                _normalized_parquet_for_vcf(user_id, filename)
            ),
            display_names=self.sample_display_names,
        )

    @rx.var
    def prs_comparable_sample_filenames(self) -> List[str]:
        """Filenames for the PRS compare dropdown."""
        return [sample["filename"] for sample in self.prs_comparable_samples]

    @rx.var
    def has_prs_comparable_samples(self) -> bool:
        """True when at least one other prepared sample can join a PRS comparison."""
        return len(self.prs_comparable_samples) > 0

    @rx.var
    def current_sex(self) -> str:
        """Get sex for the currently selected file."""
        if not self.selected_file:
            return "N/A"
        return self.file_metadata.get(self.selected_file, {}).get("sex", "N/A")

    @rx.var
    def current_tissue(self) -> str:
        """Get tissue source for the currently selected file."""
        if not self.selected_file:
            return "Sample tissue"
        return self.file_metadata.get(self.selected_file, {}).get("tissue", "Sample tissue")

    @rx.var
    def current_source(self) -> str:
        """Get source type for the currently selected file (e.g. 'zenodo', 'upload')."""
        if not self.selected_file:
            return ""
        return self.file_metadata.get(self.selected_file, {}).get("source", "")

    @rx.var
    def current_zenodo_url(self) -> str:
        """Get Zenodo URL for the currently selected file, if imported from Zenodo."""
        if not self.selected_file:
            return ""
        return self.file_metadata.get(self.selected_file, {}).get("zenodo_url", "")

    @rx.var
    def current_zenodo_license(self) -> str:
        """Get Zenodo license for the currently selected file."""
        if not self.selected_file:
            return ""
        return self.file_metadata.get(self.selected_file, {}).get("zenodo_license", "")

    @rx.var
    def species_options(self) -> List[str]:
        """Get available species options."""
        return SPECIES_OPTIONS

    @rx.var
    def sex_options(self) -> List[str]:
        """Get available sex options."""
        return SEX_OPTIONS

    @rx.var
    def tissue_options(self) -> List[str]:
        """Get available tissue options."""
        return TISSUE_OPTIONS

    @rx.var
    def available_reference_genomes(self) -> List[str]:
        """Get available reference genomes for the current species."""
        species = self.current_species
        return REFERENCE_GENOMES.get(species, ["custom"])

    def select_file(self, filename: str):
        """Select a file — reset sibling grids first, then remount the workspace.

        Changing ``selected_file`` remounts the right panel.  If that happens
        before Output/PRS filters are cleared, the new MUI grids hydrate from
        the previous sample's filter model.  Stage the filename and clear
        those grids in events that run first.
        """
        self._pending_selected_file = filename
        return [
            OutputPreviewState.clear_output_preview,
            PRSState.reset_for_genome_switch(""),
            PRSTraitState.reset_for_genome_switch,
            UploadState.commit_selected_file,
        ]

    def commit_selected_file(self):
        """Apply the staged file selection and start loading that sample."""
        filename = self._pending_selected_file
        if not filename:
            return
        self.selected_file = filename
        self.last_run_success = False
        self.expanded_run_id = ""

        if filename not in self.file_metadata:
            self._load_file_metadata(filename)

        file_runs = [r for r in self.runs if r.get("filename") == filename]
        if file_runs:
            file_runs.sort(key=lambda x: x.get("started_at") or "", reverse=True)
            latest_run = file_runs[0]
            if latest_run.get("modules"):
                prev_modules = latest_run["modules"]
                available = set(self.available_modules)
                restored = [m for m in prev_modules if m in available]
                new_modules = sorted(available - set(prev_modules))
                self.selected_modules = restored + new_modules

        self.vcf_preview_expanded = True
        self.outputs_expanded = True
        self.run_history_expanded = True
        self.new_analysis_expanded = True
        self.right_panel_active_tab = "input"

        # Drop the previous genome's rows and output lists immediately.
        # Annotations and reports live under {user}/{sample}/; leaving the
        # old lists in place shows Oksana's files on Livia's remounted tabs.
        self._clear_vcf_preview()
        self._clear_sample_outputs()
        self.vcf_preview_loading = True

        return [
            *self._yield_prs_init_events(),
            UploadState.load_file_data_background,
        ]

    @rx.event(background=True)
    async def load_file_data_background(self) -> Optional[List[EventSpec]]:
        """Load VCF preview + output files in background (state lock released)."""
        async with self:
            selected_file = self.selected_file
            safe_user_id = self.safe_user_id
            if not selected_file or not safe_user_id:
                self._clear_vcf_preview()
                return
            expected_parquet = self._get_expected_normalized_parquet_path()
            prs_init_after_normalize = (
                expected_parquet is not None and not _parquet_is_ready(expected_parquet)
            )
            self.progress_status = "Normalizing VCF (quality filtering)..."

        sample_name = selected_file.replace(".vcf.gz", "").replace(".vcf", "")
        partition_key = f"{safe_user_id}/{sample_name}"

        loop = asyncio.get_event_loop()
        normalize_config = await loop.run_in_executor(
            None,
            lambda: _normalize_run_config_if_stale(safe_user_id, selected_file, partition_key),
        )
        if normalize_config is not None:
            # Normalization is a full Polars/polars-bio pass over the genome: run it in a
            # spawned child, not here.  Awaiting the handle does not block the loop.
            token = f"normalize:{partition_key}"
            handle = submit_job(
                token,
                "normalize_vcf_job",
                normalize_config,
                partition_key,
                user_vcf_partitions.name,
            )
            try:
                result = await await_job(handle)
            finally:
                forget_job(token)
            if not result.success:
                async with self:
                    if self.selected_file != selected_file:
                        return
                    self.progress_status = ""
                    self.vcf_preview_error = (
                        f"VCF normalization failed: {result.error or 'see Dagster UI'}"
                    )
                return

        async with self:
            if self.selected_file != selected_file:
                return
            self.progress_status = "Loading VCF preview..."
            self._load_norm_stats_from_dagster()
            self._load_vcf_into_grid()
            self._load_output_files_sync()
            self.progress_status = ""
            normalized_parquet = self._get_normalized_parquet_path()
            ref_genome = self.file_metadata.get(selected_file, {}).get("reference_genome", "GRCh38")

        if prs_init_after_normalize and normalized_parquet is not None:
            return [PRSState.initialize_prs_for_file(str(normalized_parquet), ref_genome)]
        return None

    def _load_vcf_into_grid(self) -> None:
        """Load the normalized (or raw fallback) parquet into the LazyFrame grid.

        Assumes norm stats are already loaded.  Must be called while holding
        the state lock (inside ``async with self:``).
        """
        if not self.selected_file or not self.safe_user_id:
            self._clear_vcf_preview()
            return

        normalized = self._get_normalized_parquet_path()
        if normalized is not None:
            try:
                lf = pl.scan_parquet(str(normalized))
                for _ in self.set_lazyframe(lf, {}, chunk_size=300):
                    pass
                # Tell SafeGridMixin how a compute worker can reopen this data, so
                # sorting and filtering happen out-of-process instead of on the loop.
                self.register_grid_source("scan_file", normalized)
                _inject_rsid_link_renderer(self)
                self.preview_source_label = f"{self.selected_file} (normalized)"
                self.vcf_preview_loading = False
                return
            except Exception:
                pass

        vcf_path = get_user_input_dir() / self.safe_user_id / self.selected_file
        if not vcf_path.exists():
            self._clear_vcf_preview()
            self.vcf_preview_error = f"VCF file not found: {vcf_path.name}"
            return

        try:
            lazy_vcf = prepare_vcf_for_module_annotation(vcf_path)
            descriptions = extract_vcf_descriptions(lazy_vcf)
            for _ in self.set_lazyframe(lazy_vcf, descriptions, chunk_size=300):
                pass
            self.register_grid_source("prepare_vcf", vcf_path)
            _inject_rsid_link_renderer(self)
            self.preview_source_label = f"{vcf_path.name} (raw VCF fallback)"
        except Exception as e:
            self._clear_vcf_preview()
            self.vcf_preview_error = str(e)
        finally:
            self.vcf_preview_loading = False

    def switch_tab(self, tab_name: str):
        """Switch to a different tab in the right panel."""
        self.active_tab = tab_name
        # Reload output files when switching to outputs tab
        if tab_name == "outputs":
            self._load_output_files_sync()

    def _load_output_files_sync(self):
        """Load output files for the selected sample (synchronous version).

        Enriches each file dict with Dagster materialization info:
        ``materialized_at`` (human-readable datetime or ""),
        ``needs_materialization`` (bool — True when upstream is newer or asset never materialized).
        """
        if not self.selected_file or not self.safe_user_id:
            self._clear_sample_outputs()
            return
        
        sample_name = self.selected_file.replace(".vcf.gz", "").replace(".vcf", "")
        partition_key = f"{self.safe_user_id}/{sample_name}"

        # Fetch Dagster materialization timestamps for relevant assets
        mat_info = self._fetch_output_materialization_info(partition_key)
        annotations_mat = mat_info.get("user_hf_module_annotations", {})
        report_mat = mat_info.get("user_longevity_report", {})
        
        # Load parquet data files from modules/ directory
        output_dir = get_user_output_dir() / self.safe_user_id / sample_name / "modules"
        
        files: list[dict] = []
        if output_dir.exists():
            for f in output_dir.glob("*.parquet"):
                if "_weights" in f.name:
                    file_type = "weights"
                elif "_annotations" in f.name:
                    file_type = "annotations"
                elif "_studies" in f.name:
                    file_type = "studies"
                else:
                    file_type = "data"
                
                module = f.stem.replace("_weights", "").replace("_annotations", "").replace("_studies", "")
                
                run_id = annotations_mat.get("run_id", "")
                files.append({
                    "name": f.name,
                    "path": str(f),
                    "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                    "module": module,
                    "type": file_type,
                    "sample_name": sample_name,
                    "materialized_at": annotations_mat.get("materialized_at", ""),
                    "needs_materialization": annotations_mat.get("needs_materialization", True),
                    "run_id": run_id,
                    "run_short": run_id[:8] if run_id else "",
                })
        
        # Also scan sample root for Ensembl annotation parquets (*_ensembl_annotated.parquet)
        ensembl_mat = mat_info.get("user_annotated_vcf_duckdb", {})
        sample_dir = get_user_output_dir() / self.safe_user_id / sample_name
        if sample_dir.exists():
            for f in sample_dir.glob("*_ensembl_annotated.parquet"):
                run_id = ensembl_mat.get("run_id", "")
                files.append({
                    "name": f.name,
                    "path": str(f),
                    "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                    "module": "ensembl",
                    "type": "annotations",
                    "sample_name": sample_name,
                    "materialized_at": ensembl_mat.get("materialized_at", ""),
                    "needs_materialization": ensembl_mat.get("needs_materialization", True),
                    "run_id": run_id,
                    "run_short": run_id[:8] if run_id else "",
                })

        # Scan vcf_exports/ directory for exported VCF files
        vcf_export_mat = mat_info.get("user_vcf_exports", {})
        vcf_dir = get_user_output_dir() / self.safe_user_id / sample_name / "vcf_exports"
        if vcf_dir.exists():
            for f in vcf_dir.iterdir():
                if not f.is_file():
                    continue
                if not (f.name.endswith(".vcf") or f.name.endswith(".vcf.gz") or f.name.endswith(".vcf.bgz")):
                    continue
                module = f.stem.replace("_annotated", "").replace(".vcf", "")
                run_id = vcf_export_mat.get("run_id", "")
                files.append({
                    "name": f.name,
                    "path": str(f),
                    "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                    "module": module,
                    "type": "vcf_export",
                    "sample_name": sample_name,
                    "materialized_at": vcf_export_mat.get("materialized_at", ""),
                    "needs_materialization": vcf_export_mat.get("needs_materialization", True),
                    "run_id": run_id,
                    "run_short": run_id[:8] if run_id else "",
                })

        files.sort(key=lambda x: (x["module"], x["type"]))
        self.output_files = files
        
        # Load HTML report files from reports/ directory
        reports_dir = get_user_output_dir() / self.safe_user_id / sample_name / "reports"
        report_run_id = report_mat.get("run_id", "")

        reports: list[dict] = []
        if reports_dir.exists():
            for f in reports_dir.glob("*.html"):
                mtime = f.stat().st_mtime
                mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                reports.append({
                    "name": f.name,
                    "path": str(f),
                    "size_kb": round(f.stat().st_size / 1024, 1),
                    "sample_name": sample_name,
                    "materialized_at": mtime_str,
                    "needs_materialization": False,
                    "run_id": report_run_id,
                    "run_short": report_run_id[:8] if report_run_id else "",
                })
        
        reports.sort(key=lambda x: x["materialized_at"], reverse=True)
        self.report_files = reports
        self.outputs_loaded_for_file = self.selected_file

    def _fetch_output_materialization_info(self, partition_key: str) -> Dict[str, Dict[str, Any]]:
        """Fetch materialization timestamps and staleness for output assets.

        Returns a dict keyed by asset name, each containing:
        ``materialized_at`` (str), ``needs_materialization`` (bool), ``timestamp`` (float).
        """
        instance = get_dagster_instance()
        asset_chain = [
            "user_vcf_normalized",
            "user_hf_module_annotations",
            "user_longevity_report",
            "user_annotated_vcf_duckdb",
            "user_vcf_exports",
        ]
        timestamps: Dict[str, float] = {}
        run_ids: Dict[str, str] = {}
        for asset_name in asset_chain:
            result = instance.fetch_materializations(
                records_filter=AssetRecordsFilter(
                    asset_key=AssetKey(asset_name),
                    asset_partitions=[partition_key],
                ),
                limit=1,
            )
            if result.records:
                timestamps[asset_name] = result.records[0].timestamp
                run_ids[asset_name] = result.records[0].run_id or ""
            else:
                timestamps[asset_name] = 0.0
                run_ids[asset_name] = ""

        info: Dict[str, Dict[str, Any]] = {}
        upstream_map = {
            "user_hf_module_annotations": "user_vcf_normalized",
            "user_longevity_report": "user_hf_module_annotations",
            "user_annotated_vcf_duckdb": "user_vcf_normalized",
            "user_vcf_exports": "user_hf_module_annotations",
        }
        for asset_name in ["user_hf_module_annotations", "user_longevity_report", "user_annotated_vcf_duckdb", "user_vcf_exports"]:
            ts = timestamps[asset_name]
            upstream_ts = timestamps.get(upstream_map[asset_name], 0.0)
            mat_at = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else ""
            needs = (ts == 0.0) or (upstream_ts > ts)
            info[asset_name] = {
                "materialized_at": mat_at,
                "needs_materialization": needs,
                "timestamp": ts,
                "run_id": run_ids[asset_name],
            }
        return info

    def _outputs_belong_to_selected_file(self) -> bool:
        return bool(self.selected_file) and self.outputs_loaded_for_file == self.selected_file

    @rx.var
    def has_output_files(self) -> bool:
        """True when the selected sample has annotation or report files loaded."""
        if not self._outputs_belong_to_selected_file():
            return False
        return len(self.output_files) > 0 or len(self.report_files) > 0

    @rx.var
    def output_file_count(self) -> int:
        """Number of annotation/data files for the selected sample only."""
        if not self._outputs_belong_to_selected_file():
            return 0
        return len(self.output_files)

    @rx.var
    def report_file_count(self) -> int:
        """Number of HTML reports for the selected sample only."""
        if not self._outputs_belong_to_selected_file():
            return 0
        return len(self.report_files)

    @rx.var
    def has_report_files(self) -> bool:
        """True when the selected sample has HTML reports loaded."""
        if not self._outputs_belong_to_selected_file():
            return False
        return len(self.report_files) > 0

    def _output_path_for_run(self, run_id: str) -> str:
        """Return the first annotation parquet produced by ``run_id``.

        A sample's output directory accumulates files across runs. Match both
        the materialization run id and the modules selected for the requested
        run so the Analysis action cannot land on an unrelated older parquet.
        """
        if not run_id or not self._outputs_belong_to_selected_file():
            return ""

        run = next((item for item in self.runs if item.get("run_id") == run_id), None)
        if run is None:
            return ""

        modules = set(run.get("modules") or [])
        if run.get("include_ensembl"):
            modules.add("ensembl")

        for file_info in self.output_files:
            if (
                file_info.get("run_id") == run_id
                and file_info.get("module") in modules
                and file_info.get("type") in {"annotations", "data", "weights"}
            ):
                return str(file_info.get("path") or "")
        return ""

    @rx.var
    def latest_run_output_path(self) -> str:
        """Annotation parquet to focus for the selected sample's latest run."""
        return self._output_path_for_run(self.latest_run_id)

    @rx.var
    def latest_report_url(self) -> str:
        """Browser URL for the report materialized by the latest run only."""
        if not self._outputs_belong_to_selected_file():
            return ""

        run_id = self.latest_run_id
        for file_info in self.report_files:
            if file_info.get("run_id") == run_id:
                return (
                    f"{self.backend_api_url}/api/report/{self.safe_user_id}/"
                    f"{file_info['sample_name']}/{file_info['name']}"
                )
        return ""

    @rx.var
    def has_latest_report(self) -> bool:
        """Whether the latest run generated a report that can be opened."""
        return bool(self.latest_report_url)

    async def delete_file(self, filename: str):
        """Delete an uploaded file from the filesystem and state."""
        if _is_immutable_mode():
            yield rx.toast.warning("File deletion is disabled in public demo mode.")
            return
        if not self.safe_user_id:
            auth_state = await self.get_state(AuthState)
            self.safe_user_id = self._get_safe_user_id(auth_state.user_email)
            
        root = Path(__file__).resolve().parents[3]
        file_path = get_user_input_dir() / self.safe_user_id / filename
        
        if file_path.exists():
            try:
                file_path.unlink()
                self.files = [f for f in self.files if f != filename]
                if self.selected_file == filename:
                    self.selected_file = ""
                    self._clear_vcf_preview()
                yield rx.toast.success(f"Deleted {filename}")
            except Exception as e:
                yield rx.toast.error(f"Failed to delete {filename}: {str(e)}")
        else:
            yield rx.toast.error(f"File {filename} not found on disk")

    @rx.var
    def filtered_runs(self) -> List[Dict[str, Any]]:
        """Filter runs for the currently selected file, excluding CANCELED runs."""
        if not self.selected_file:
            return []
        
        # Match by filename and exclude CANCELED runs (they're preserved in DB but hidden from UI)
        return [
            r for r in self.runs 
            if r.get("filename") == self.selected_file 
            and r.get("status") != "CANCELED"
        ]

    @rx.var
    def has_filtered_runs(self) -> bool:
        """Check if there are any runs for the selected file."""
        return len(self.filtered_runs) > 0

    @rx.var
    def last_run_for_file(self) -> Dict[str, Any]:
        """Get the most recent run for the selected file."""
        runs = self.filtered_runs
        if not runs:
            return {}
        # Already sorted by started_at descending in filtered_runs
        return runs[0]

    @rx.var
    def has_last_run(self) -> bool:
        """Check if there's a previous run for the selected file."""
        return bool(self.last_run_for_file)

    @rx.var
    def other_runs_for_file(self) -> List[Dict[str, Any]]:
        """Get all runs except the most recent one for timeline display."""
        runs = self.filtered_runs
        if len(runs) <= 1:
            return []
        return runs[1:]

    @rx.var
    def has_other_runs(self) -> bool:
        """Check if there are other runs besides the last one."""
        return len(self.other_runs_for_file) > 0

    @rx.var
    def latest_run_id(self) -> str:
        """Get the run_id of the most recent run for the selected file."""
        runs = self.filtered_runs
        if runs:
            return runs[0].get("run_id", "")
        return ""

    @rx.var
    def has_selected_file(self) -> bool:
        """Check if a file is selected."""
        return bool(self.selected_file)

    @rx.var
    def selected_file_info(self) -> Dict[str, Any]:
        """Get metadata for the currently selected file."""
        if not self.selected_file:
            return {}
        return self.file_metadata.get(self.selected_file, {})

    @rx.var
    def has_file_metadata(self) -> bool:
        """Check if we have metadata for the selected file."""
        return bool(self.selected_file_info)

    @rx.var
    def has_selected_modules(self) -> bool:
        """Check if any modules are selected."""
        return len(self.selected_modules) > 0

    @rx.var
    def can_run_annotation(self) -> bool:
        """Check if annotation can be run.
        
        Requires: file selected AND (HF modules selected OR Ensembl enabled).
        Also blocks if the selected file already has a running job.
        """
        if not self.selected_file:
            return False
        if not self.selected_modules and not self.include_ensembl:
            return False
        
        # Check if the SELECTED file has a running job
        for run in self.runs:
            if run.get("filename") == self.selected_file:
                status = run.get("status", "")
                if status in ("RUNNING", "QUEUED", "STARTING"):
                    return False
        
        return True

    @rx.var
    def selected_file_is_running(self) -> bool:
        """Check if the currently selected file has a running job."""
        if not self.selected_file:
            return False
        
        for run in self.runs:
            if run.get("filename") == self.selected_file:
                status = run.get("status", "")
                if status in ("RUNNING", "QUEUED", "STARTING"):
                    return True
        
        return False

    @rx.var
    def analysis_button_text(self) -> str:
        """Get the text for the analysis button based on state."""
        if self.selected_file_is_running:
            return "Analysis Running..."
        return "Start Analysis"

    @rx.var
    def analysis_button_color(self) -> str:
        """Get the color class for the start/running analysis button."""
        if self.selected_file_is_running:
            return "ui yellow right labeled icon large button fluid"
        return "ui primary right labeled icon large button fluid"

    @rx.var
    def module_metadata_list(self) -> List[Dict[str, Any]]:
        """Return module metadata for UI display."""
        custom_names = set(list_custom_modules())
        result = []
        for module_name in self.available_modules:
            meta = MODULE_METADATA.get(module_name, {
                "title": module_name.replace("_", " ").title(),
                "description": f"Annotation module: {module_name}",
                "icon": "database",
                "color": "neutral",
            })
            info = MODULE_INFOS.get(module_name)
            browsable_logo_url = ""
            if info and info.logo_url:
                if info.logo_url.startswith("hf://"):
                    hf_path = info.logo_url.replace("hf://", "")
                    browsable_logo_url = f"https://huggingface.co/{hf_path.replace(info.repo_id, info.repo_id + '/resolve/main', 1)}"
                elif info.logo_url.startswith("file://") or info.logo_url.startswith("/"):
                    browsable_logo_url = f"{self.backend_api_url}/api/module-logo/{module_name}"
            result.append({
                "name": module_name,
                "title": meta.get("title", module_name),
                "description": meta.get("description", ""),
                "icon": meta.get("icon", "database"),
                "color": meta.get("color", "neutral"),
                "logo_url": browsable_logo_url,
                "repo_id": info.repo_id if info else "",
                "selected": module_name in self.selected_modules,
                "is_custom": module_name in custom_names,
            })
        return result

    def _get_run_status_str(self, status: DagsterRunStatus) -> str:
        """Convert Dagster run status to string."""
        status_map = {
            DagsterRunStatus.QUEUED: "QUEUED",
            DagsterRunStatus.NOT_STARTED: "QUEUED",
            DagsterRunStatus.STARTING: "STARTING",
            DagsterRunStatus.STARTED: "RUNNING",
            DagsterRunStatus.SUCCESS: "SUCCESS",
            DagsterRunStatus.FAILURE: "FAILURE",
            DagsterRunStatus.CANCELED: "CANCELED",
            DagsterRunStatus.CANCELING: "CANCELING",
        }
        return status_map.get(status, "UNKNOWN")

    def _try_submit_to_daemon(self, instance: DagsterInstance, run_id: str) -> tuple[bool, str]:
        """
        Attempt to submit run to Dagster daemon.
        
        Returns:
            (success: bool, error_message: str)
        """
        try:
            instance.submit_run(run_id, workspace=None)
            return (True, "")
        except Exception as e:
            return (False, str(e))

    def _swap_run_id(self, old_id: str, new_id: str) -> None:
        """Replace a placeholder run_id with the real one everywhere."""
        updated_runs = []
        for r in self.runs:
            if r["run_id"] == old_id:
                r["run_id"] = new_id
                r["dagster_url"] = f"{get_dagster_web_url()}/runs/{new_id}"
            updated_runs.append(r)
        self.runs = updated_runs
        if self.vcf_export_run_id == old_id:
            self.vcf_export_run_id = new_id

    @rx.event(background=True)
    async def execute_job_with_run_discovery(
        self,
        job_name: str,
        run_config: dict,
        partition_key: str,
        original_run_id: str,
        sample_name: str,
    ) -> None:
        """Run a Dagster job in a compute child and reconcile the placeholder run id.

        Replaces the old thread-based ``_execute_inproc_with_state_update``, which had two
        defects this fixes: it ran the whole pipeline inside the ASGI process, and it
        wrote Reflex state from a bare thread with no state lock (its own docstring
        warned that concurrent events could see torn state).  Here every state write is
        inside ``async with self:``, and the pipeline is in another process entirely.

        Dagster assigns the real run id inside the child, so the placeholder created for
        the UI is swapped once the child reports back.  ``poll_run_status`` may discover
        the real run first via the partition-key hint; both paths converge.
        """
        handle = submit_job(
            original_run_id, job_name, run_config, partition_key, user_vcf_partitions.name
        )
        async with self:
            UploadState._active_inproc_runs[original_run_id] = partition_key
            self._add_log(f"Job running in compute child pid={handle.pid}")

        try:
            result = await await_job(handle)
        finally:
            forget_job(original_run_id)

        async with self:
            UploadState._active_inproc_runs.pop(original_run_id, None)
            self._inproc_discover_partition = ""
            self._inproc_discover_since = 0.0
            self._inproc_original_run_id = ""
            self.running = False
            self.vcf_exporting = False
            self.vcf_export_run_id = ""
            self.polling_active = False
            self.last_run_success = result.success

            if result.run_id:
                self._add_log(f"Job finished with Dagster run ID: {result.run_id}")
                self._swap_run_id(original_run_id, result.run_id)
            terminal_id = result.run_id or original_run_id

            updated_runs = []
            for r in self.runs:
                if r["run_id"] == terminal_id:
                    r["status"] = "SUCCESS" if result.success else "FAILURE"
                    r["ended_at"] = datetime.now().isoformat()
                    if result.success:
                        output_dir = (
                            get_user_output_dir() / self.safe_user_id / sample_name / "modules"
                        )
                        if output_dir.exists():
                            r["output_path"] = str(output_dir)
                    else:
                        r["error"] = result.error or "Job failed - check Dagster UI for details"
                updated_runs.append(r)
            self.runs = updated_runs

            if not result.success and result.error:
                self._add_log(f"Job execution failed: {result.error}")
            if result.success:
                self._load_output_files_sync()

    async def start_annotation_run(self):
        """Start annotation for the selected file with selected modules and/or Ensembl."""
        if not self.selected_file:
            yield rx.toast.error("Please select a file")
            return
        if not self.selected_modules and not self.include_ensembl:
            yield rx.toast.error("Please select at least one module or enable Ensembl annotations")
            return

        self.last_run_success = False
        self.running = True
        self.run_logs = []  # Clear previous logs
        self._add_log("Starting annotation job...")
        yield

        if not self.safe_user_id:
            auth_state = await self.get_state(AuthState)
            self.safe_user_id = self._get_safe_user_id(auth_state.user_email)

        sample_name = self.selected_file.replace(".vcf.gz", "").replace(".vcf", "")
        partition_key = f"{self.safe_user_id}/{sample_name}"

        root = Path(__file__).resolve().parents[3]
        vcf_path = get_user_input_dir() / self.safe_user_id / self.selected_file

        has_hf_modules = bool(self.selected_modules)
        has_ensembl = self.include_ensembl
        
        self._add_log(f"File: {self.selected_file}")
        if has_hf_modules:
            self._add_log(f"Modules: {', '.join(self.selected_modules)}")
        if has_ensembl:
            self._add_log("Ensembl annotation enabled (DuckDB)")
        self._add_log(f"User: {self.safe_user_id}")

        instance = get_dagster_instance()
        
        # Determine job based on what's selected
        if has_hf_modules and has_ensembl:
            job_name = "annotate_all_job"
        elif has_ensembl:
            job_name = "annotate_ensembl_only_job"
        else:
            job_name = "annotate_and_report_job"
        
        modules_to_use = self.selected_modules.copy() if has_hf_modules else []

        # Validate: drop any selected modules no longer in the registry (deleted/renamed)
        if modules_to_use:
            missing = [m for m in modules_to_use if m not in MODULE_INFOS]
            if missing:
                yield rx.toast.warning(
                    f"Skipping {len(missing)} module(s) not found in registry: {', '.join(missing)}"
                )
                modules_to_use = [m for m in modules_to_use if m in MODULE_INFOS]
            if not modules_to_use and not has_ensembl:
                yield rx.toast.error(
                    "No valid modules found — all selected modules are missing from the registry. "
                    "Re-select modules or check your module configuration."
                )
                self.running = False
                return
            has_hf_modules = bool(modules_to_use)

        file_info = self.file_metadata.get(self.selected_file, {})
        custom_metadata = file_info.get("custom_fields", {}) or {}

        normalize_config_async: dict = {
            "vcf_path": str(vcf_path.absolute()),
        }
        sex_value_async = file_info.get("sex") or None
        if sex_value_async:
            normalize_config_async["sex"] = sex_value_async

        run_config: dict = {
            "ops": {
                "user_vcf_normalized": {
                    "config": normalize_config_async,
                },
            }
        }

        if has_hf_modules:
            run_config["ops"]["user_hf_module_annotations"] = {
                "config": {
                    "vcf_path": str(vcf_path.absolute()),
                    "user_name": self.safe_user_id,
                    "sample_name": sample_name,
                    "modules": modules_to_use,
                    "species": file_info.get("species", "Homo sapiens"),
                    "reference_genome": file_info.get("reference_genome", "GRCh38"),
                    "subject_id": file_info.get("subject_id") or None,
                    "sex": sex_value_async,
                    "tissue": file_info.get("tissue") or None,
                    "study_name": file_info.get("study_name") or None,
                    "description": file_info.get("notes") or None,
                    "custom_metadata": custom_metadata if custom_metadata else None,
                }
            }
            run_config["ops"]["user_longevity_report"] = {
                "config": {
                    "user_name": self.safe_user_id,
                    "sample_name": sample_name,
                    "modules": modules_to_use,
                }
            }

        if has_ensembl:
            run_config["ops"]["user_annotated_vcf_duckdb"] = {
                "config": {
                    "vcf_path": str(vcf_path.absolute()),
                    "user_name": self.safe_user_id,
                    "sample_name": sample_name,
                }
            }

        # Create the run in Dagster immediately to get a REAL Run ID
        # Tag with source=webui so shutdown handler only cancels our runs
        try:
            job_def = defs.resolve_job_def(job_name)
            run = instance.create_run_for_job(
                job_def=job_def,
                run_config=run_config,
                tags={
                    "dagster/partition": partition_key,
                    "source": "webui",
                },
            )
            run_id = run.run_id
            self._add_log(f"Created Dagster run: {run_id}")
        except Exception as e:
            self._add_log(f"Failed to create run: {str(e)}")
            self.running = False
            self.last_run_success = False
            yield rx.toast.error(f"Failed to start job: {str(e)}")
            return

        # Add the real run to history immediately
        run_info = {
            "run_id": run_id,
            "filename": self.selected_file,
            "sample_name": sample_name,
            "modules": modules_to_use,
            "include_ensembl": has_ensembl,
            "status": "QUEUED",
            "started_at": datetime.now().isoformat(),
            "ended_at": None,
            "output_path": None,
            "error": None,
            "dagster_url": f"{get_dagster_web_url()}/runs/{run_id}",
        }
        self.runs = [run_info] + self.runs
        self.active_run_id = run_id
        self.polling_active = True
        self._add_log("Submitting run to Dagster daemon...")
        yield

        # Try daemon submission first
        daemon_success, daemon_error = self._try_submit_to_daemon(instance, run_id)
        
        if daemon_success:
            # Daemon accepted the run - poll status asynchronously via poll_run_status()
            self._add_log(f"Run {run_id} submitted successfully to daemon.")
            yield rx.toast.info(f"Annotation started for {sample_name}")
        else:
            # Daemon submission failed - fall back to in-process execution
            self._add_log(f"Daemon submission failed: {daemon_error}")
            self._add_log("Starting in-process execution (this will take a few minutes)...")
            yield rx.toast.info(f"Running in-process for {sample_name} - please wait...")
            
            # Delete the dummy run — the compute child will create a real one.
            instance.delete_run(run_id)
            
            # Tell the poller to discover the real run ID by partition key + timestamp.
            # poll_run_status (a safe Reflex event handler) will query Dagster for
            # recent runs matching this partition and swap in the real run_id.
            self._inproc_discover_partition = partition_key
            self._inproc_discover_since = time.time()
            self._inproc_original_run_id = run_id
            
            # Update status to RUNNING, keep polling active for discovery
            updated_runs = []
            for r in self.runs:
                if r["run_id"] == run_id:
                    r["status"] = "RUNNING"
                updated_runs.append(r)
            self.runs = updated_runs
            
            # Hand off to a spawned compute child.  The old code ran this in a thread of
            # the ASGI process, which put the whole pipeline on this worker and wrote
            # state without the lock.
            yield UploadState.execute_job_with_run_discovery(
                job_name, run_config, partition_key, run_id, sample_name
            )
    
    def _add_log(self, message: str):
        """Add a timestamped log entry."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.run_logs = self.run_logs + [f"[{timestamp}] {message}"]

    async def poll_run_status(self, _value: str = ""):
        """Poll Dagster for run status updates.
        
        Note: this handler is called by rx.moment's on_change which passes a
        timestamp string. We accept it as ``_value`` but don't use it.
        Must return (not yield) EventSpec so Reflex's frontend dispatcher
        can handle the result correctly.
        
        When ``_inproc_discover_partition`` is set, the active_run_id points to
        a deleted placeholder. We search all recent Dagster runs (any status)
        matching the partition key and created after ``_inproc_discover_since``
        to discover the real run created in the compute child.
        """
        if not self.polling_active:
            return

        instance = get_dagster_instance()

        # --- In-process run discovery mode ---
        if self._inproc_discover_partition:
            # The executor may have already finished and cleared discovery vars
            # or set a terminal status. Check the current run entry first.
            current_entry = next(
                (r for r in self.runs if r["run_id"] == self._inproc_original_run_id), None
            )
            if current_entry and current_entry.get("status") in ("SUCCESS", "FAILURE", "CANCELED"):
                self._inproc_discover_partition = ""
                self._inproc_discover_since = 0.0
                self._inproc_original_run_id = ""
                return

            records = instance.get_run_records(limit=20)
            for record in records:
                run = record.dagster_run
                if (
                    run.tags.get("dagster/partition") == self._inproc_discover_partition
                    and run.tags.get("source") == "webui"
                    and run.run_id != self._inproc_original_run_id
                    and record.create_timestamp.timestamp() >= self._inproc_discover_since - 5
                ):
                    self._add_log(f"Discovered in-process run: {run.run_id}")
                    self._swap_run_id(self._inproc_original_run_id, run.run_id)
                    self.active_run_id = run.run_id
                    self._inproc_discover_partition = ""
                    self._inproc_discover_since = 0.0
                    self._inproc_original_run_id = ""
                    break
            else:
                return

        if not self.active_run_id:
            return

        run = instance.get_run_by_id(self.active_run_id)

        if not run:
            self.polling_active = False
            return

        status_str = self._get_run_status_str(run.status)

        # Update run in history
        updated_runs = []
        for r in self.runs:
            if r["run_id"] == self.active_run_id:
                r["status"] = status_str
                if run.status in (DagsterRunStatus.SUCCESS, DagsterRunStatus.FAILURE, DagsterRunStatus.CANCELED):
                    r["ended_at"] = datetime.now().isoformat()
                    if run.status == DagsterRunStatus.SUCCESS:
                        sample_name = r.get("sample_name", "")
                        output_dir = get_user_output_dir() / self.safe_user_id / sample_name / "modules"
                        if output_dir.exists():
                            r["output_path"] = str(output_dir)
            updated_runs.append(r)
        self.runs = updated_runs

        # Fetch recent logs
        await self.fetch_run_logs(self.active_run_id)

        # Stop polling if run is complete
        if run.status in (DagsterRunStatus.SUCCESS, DagsterRunStatus.FAILURE, DagsterRunStatus.CANCELED):
            self.polling_active = False
            self.running = False
            self.last_run_success = (run.status == DagsterRunStatus.SUCCESS)

            if self.vcf_export_run_id and self.active_run_id == self.vcf_export_run_id:
                self.vcf_exporting = False
                self.vcf_export_run_id = ""

            self._load_output_files_sync()
            if run.status == DagsterRunStatus.SUCCESS:
                return rx.toast.success("Job completed successfully!")
            elif run.status == DagsterRunStatus.FAILURE:
                return rx.toast.error("Job failed. Check logs for details.")

    async def fetch_run_logs(self, run_id: str):
        """Fetch log events from Dagster for a run."""
        instance = get_dagster_instance()

        # Use all_logs(run_id) to get run events
        events = instance.all_logs(run_id)
        
        log_lines = []
        # Get last 50 events
        for event in events[-50:]:
            timestamp = datetime.fromtimestamp(event.timestamp).strftime("%H:%M:%S")
            msg = event.message or (event.dagster_event.event_type_value if event.dagster_event else "Event")
            log_lines.append(f"[{timestamp}] {msg}")

        self.run_logs = log_lines

    def view_run(self, run_id: str):
        """Set a run as the active run to view its logs."""
        self.active_run_id = run_id
        # Trigger log fetch
        return UploadState.fetch_run_logs(run_id)

    @rx.var
    def active_run_info(self) -> Dict[str, Any]:
        """Get the currently active run info."""
        for r in self.runs:
            if r.get("run_id") == self.active_run_id:
                return r
        return {}

    @rx.var
    def has_runs(self) -> bool:
        """Check if there are any runs."""
        return len(self.runs) > 0

    @rx.var
    def has_logs(self) -> bool:
        """Check if there are any log entries."""
        return len(self.run_logs) > 0

    @rx.var
    def log_count(self) -> int:
        """Get the number of log entries."""
        return len(self.run_logs)

    def do_nothing(self):
        """No-op event handler."""
        pass

    def toggle_outputs(self):
        """Toggle the outputs section expanded/collapsed."""
        self.outputs_expanded = not self.outputs_expanded

    def toggle_vcf_preview(self):
        """Toggle the VCF preview section expanded/collapsed."""
        self.vcf_preview_expanded = not self.vcf_preview_expanded

    def switch_right_panel_tab(self, tab_name: str):
        """Switch between top-level tabs in the right panel."""
        self.right_panel_active_tab = tab_name

    def switch_to_input_tab(self):
        """Switch the right panel to the input preview tab."""
        self.right_panel_active_tab = "input"

    def switch_to_prs_tab(self):
        """Switch the right panel to the PRS tab."""
        self.right_panel_active_tab = "prs"

    def switch_to_annotated_files_tab(self):
        """Switch the right panel to the annotated files tab."""
        self.right_panel_active_tab = "annotated_files"

    def switch_to_reports_tab(self):
        """Switch the right panel to the reports tab."""
        self.right_panel_active_tab = "reports"

    def switch_to_analysis_tab(self):
        """Switch the right panel to the new analysis tab."""
        self.right_panel_active_tab = "analysis"

    def drag_tab_start(self, tab_id: str):
        """Record which tab the user started dragging."""
        self._drag_tab_id = tab_id

    def drop_tab_onto(self, target_tab_id: str):
        """Reorder tabs: move the dragged tab before or after the target.

        When dragging left-to-right the user expects the source to land *after*
        the target; right-to-left it should land *before*.  We detect direction
        from the current order so either gesture feels natural.
        """
        src = self._drag_tab_id
        dst = target_tab_id
        if not src or src == dst or src not in self.tab_order or dst not in self.tab_order:
            self._drag_tab_id = ""
            return
        order = list(self.tab_order)
        src_idx = order.index(src)
        dst_idx = order.index(dst)
        order.remove(src)
        # Re-compute dst index after removal, then offset by drag direction.
        insert_at = order.index(dst)
        if src_idx < dst_idx:
            # Dragging right: land after the target.
            insert_at += 1
        order.insert(insert_at, src)
        self.tab_order = order
        self._drag_tab_id = ""

    def close_right_panel_tab_info(self, tab_name: str):
        """Hide the explanatory message for one right-panel tab."""
        if tab_name == "input":
            self.show_input_tab_info = False
        elif tab_name == "prs":
            self.show_prs_tab_info = False
        elif tab_name == "annotated_files":
            self.show_annotated_files_tab_info = False
        elif tab_name == "reports":
            self.show_reports_tab_info = False
        elif tab_name == "analysis":
            self.show_analysis_tab_info = False

    def close_input_tab_info(self):
        """Hide the input tab explanatory message."""
        self.show_input_tab_info = False

    def close_prs_tab_info(self):
        """Hide the PRS tab explanatory message."""
        self.show_prs_tab_info = False

    def close_annotated_files_tab_info(self):
        """Hide the annotated files tab explanatory message."""
        self.show_annotated_files_tab_info = False

    def close_reports_tab_info(self):
        """Hide the reports tab explanatory message."""
        self.show_reports_tab_info = False

    def close_analysis_tab_info(self):
        """Hide the analysis tab explanatory message."""
        self.show_analysis_tab_info = False

    def close_welcome_disclaimer(self):
        """Hide the welcome-page medical disclaimer for this session."""
        self.show_welcome_disclaimer = False

    def view_run_in_results(self, run_id: str = "") -> list[EventSpec] | None:
        """Switch to, focus, and preload the annotation parquet for ``run_id``."""
        self.right_panel_active_tab = "annotated_files"
        self.outputs_expanded = True
        self.focused_output_path = self._output_path_for_run(run_id)

        if self.focused_output_path:
            return [
                OutputPreviewState.view_output_file(self.focused_output_path),
                rx.call_script(
                    "window.setTimeout(() => "
                    "document.getElementById('focused-annotated-file')"
                    "?.scrollIntoView({behavior: 'smooth', block: 'center'}), 150)"
                ),
            ]
        return None

    def preview_output_file(self, file_path: str) -> list[EventSpec]:
        """Select ``file_path``, load its preview, then focus the preview heading."""
        self.focused_output_path = file_path
        return [
            OutputPreviewState.view_output_file(file_path),
            rx.call_script(_OUTPUT_PREVIEW_SCROLL_SCRIPT),
        ]

    def view_prs_in_outputs(self):
        """Switch the right panel to the PRS tab."""
        self.right_panel_active_tab = "prs"

    def toggle_run_history(self):
        """Toggle the run history section expanded/collapsed."""
        self.run_history_expanded = not self.run_history_expanded

    def toggle_new_analysis(self):
        """Toggle the new analysis section expanded/collapsed."""
        self.new_analysis_expanded = not self.new_analysis_expanded

    def expand_new_analysis(self):
        """Expand the new analysis section."""
        self.new_analysis_expanded = True

    def collapse_new_analysis(self):
        """Collapse the new analysis section."""
        self.new_analysis_expanded = False

    def toggle_run_expansion(self, run_id: str):
        """Toggle a run's expanded state in the timeline."""
        if self.expanded_run_id == run_id:
            self.expanded_run_id = ""
        else:
            self.expanded_run_id = run_id
            # Fetch logs for this run
            return UploadState.fetch_run_logs(run_id)

    def open_outputs_modal(self):
        """Open the outputs modal."""
        self.show_outputs_modal = True
        self._load_output_files_sync()

    def close_outputs_modal(self):
        """Close the outputs modal."""
        self.show_outputs_modal = False

    def set_show_outputs_modal(self, value: bool):
        """Set the outputs modal visibility (explicit setter for Reflex 0.8.9+)."""
        self.show_outputs_modal = value
        if value:
            self._load_output_files_sync()

    async def rerun_with_same_modules(self) -> AsyncGenerator[EventSpec | None, None]:
        """Re-run annotation with the same modules as the last run."""
        last_run = self.last_run_for_file
        if last_run:
            previous_modules = last_run.get("modules") or []
            available_modules = set(self.available_modules)
            self.selected_modules = [
                module for module in previous_modules if module in available_modules
            ]
            self.include_ensembl = bool(
                last_run.get("include_ensembl") or "ensembl" in previous_modules
            )
        # Start the annotation
        async for event in self.start_annotation_run():
            yield event

    def modify_and_run(self):
        """Pre-select modules from last run and switch the right panel to the Analysis tab."""
        last_run = self.last_run_for_file
        if last_run and last_run.get("modules"):
            self.selected_modules = last_run["modules"].copy()
        self.right_panel_active_tab = "analysis"
        self.new_analysis_expanded = True

    def _cleanup_orphaned_runs(self) -> int:
        """
        Clean up orphaned runs on startup by deleting them from Dagster's database.
        
        Removes only NOT_STARTED runs (daemon submission failures that never executed).
        CANCELED runs are preserved as part of run history.
        
        Returns the number of runs deleted.
        """
        instance = get_dagster_instance()
        
        # Get all NOT_STARTED runs (daemon submission failures)
        from dagster import RunsFilter
        orphaned_records = instance.get_run_records(
            filters=RunsFilter(statuses=[DagsterRunStatus.NOT_STARTED]),
            limit=100,
        )
        
        cleaned_count = 0
        for record in orphaned_records:
            run = record.dagster_run
            # Delete run from Dagster's database
            instance.delete_run(run.run_id)
            cleaned_count += 1
        
        return cleaned_count

    async def on_load(self):
        """Discover existing files and their statuses when the dashboard loads."""
        auth_state = await self.get_state(AuthState)
        if _is_immutable_mode():
            self.safe_user_id = "public"
        else:
            self.safe_user_id = self._get_safe_user_id(auth_state.user_email)

        # Clean up orphaned runs on startup (NOT_STARTED only)
        cleaned = self._cleanup_orphaned_runs()
        if cleaned > 0:
            self._add_log(f"Deleted {cleaned} orphaned NOT_STARTED run(s) from Dagster database")

        user_dir = get_user_input_dir() / self.safe_user_id

        # In immutable mode, ensure default samples are present
        default_sample_results: list[dict] = []
        if _is_immutable_mode():
            config = get_immutable_config()
            if config.default_samples:
                default_sample_results = resolve_default_samples(user_name=self.safe_user_id, log=logger)

        if not user_dir.exists():
            return

        # Find VCF files, sorted by modification time (newest first)
        vcf_files = list(user_dir.glob("*.vcf")) + list(user_dir.glob("*.vcf.gz"))
        vcf_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        self.files = [f.name for f in vcf_files]
        
        # Load basic metadata for all files (from filesystem)
        for filename in self.files:
            self._load_file_metadata(filename)

        # Overlay Zenodo source info for default samples resolved in immutable mode
        for sample_info in default_sample_results:
            fname = sample_info.get("filename", "")
            if fname in self.file_metadata:
                self.file_metadata[fname]["source"] = "zenodo"
                self.file_metadata[fname]["zenodo_url"] = sample_info.get("zenodo_url", "")
                self.file_metadata[fname]["zenodo_license"] = sample_info.get("license", "")
                if sample_info.get("subject_id"):
                    self.file_metadata[fname]["subject_id"] = sample_info["subject_id"]
                if sample_info.get("sex") and sample_info["sex"] != "N/A":
                    self.file_metadata[fname]["sex"] = sample_info["sex"]
                if sample_info.get("species"):
                    self.file_metadata[fname]["species"] = sample_info["species"]
                if sample_info.get("reference_genome"):
                    self.file_metadata[fname]["reference_genome"] = sample_info["reference_genome"]

        # Load persisted metadata from Dagster (overwrites filesystem metadata)
        self._load_metadata_from_dagster()
        
        # Re-sort files by upload_date (newest first) after Dagster metadata is loaded
        def sort_key(fname: str) -> str:
            return self.file_metadata.get(fname, {}).get("upload_date", "0000-00-00 00:00")
        self.files = sorted(self.files, key=sort_key, reverse=True)
        
        # Sync statuses with Dagster
        instance = get_dagster_instance()
        for f in self.files:
            sample_name = f.replace(".vcf.gz", "").replace(".vcf", "")
            pk = f"{self.safe_user_id}/{sample_name}"
            
            # Check if annotated asset exists using new fetch_materializations API
            asset_key = AssetKey("user_hf_module_annotations")
            result = instance.fetch_materializations(
                records_filter=AssetRecordsFilter(
                    asset_key=asset_key,
                    asset_partitions=[pk],
                ),
                limit=1,
            )
            records = result.records
            
            status = "uploaded"
            if records:
                status = "completed"
                
            if pk not in self.asset_statuses:
                self.asset_statuses[pk] = {}
            self.asset_statuses[pk]["hf_annotated"] = status
            # For backward compatibility with file_statuses computed var
            self.asset_statuses[pk]["annotated"] = status

        # Load recent runs from Dagster
        await self._load_recent_runs()

    async def _load_recent_runs(self):
        """Load recent annotation runs from Dagster."""
        instance = get_dagster_instance()
        
        # Get recent runs for all annotation jobs
        # Use get_run_records to get timestamps (start_time, end_time are on RunRecord, not DagsterRun)
        from dagster import RunsFilter
        annotation_job_names = [
            "annotate_and_report_job",
            "annotate_all_job",
            "annotate_ensembl_only_job",
            "annotate_with_hf_modules_job",
        ]
        all_run_records = []
        for jn in annotation_job_names:
            records = instance.get_run_records(
                filters=RunsFilter(job_name=jn),
                limit=20,
            )
            all_run_records.extend(records)
        # Merge and sort by start_time descending
        run_records = sorted(
            all_run_records,
            key=lambda r: r.start_time or 0,
            reverse=True,
        )[:20]
        
        run_list = []
        for record in run_records:
            run = record.dagster_run
            # Extract info from run config - use "ops" key (not "assets")
            config = run.run_config or {}
            ops = config.get("ops", {})
            hf_config = ops.get("user_hf_module_annotations", {}).get("config", {})
            duckdb_config = ops.get("user_annotated_vcf_duckdb", {}).get("config", {})
            norm_config = ops.get("user_vcf_normalized", {}).get("config", {})
            
            # Get VCF path from whichever config has it (HF, DuckDB, or normalize)
            vcf_path = hf_config.get("vcf_path") or duckdb_config.get("vcf_path") or norm_config.get("vcf_path", "")
            filename = Path(vcf_path).name if vcf_path else "unknown"
            sample_name = hf_config.get("sample_name") or duckdb_config.get("sample_name", "")
            modules = hf_config.get("modules", [])
            if duckdb_config and not modules:
                modules = ["ensembl"]
            
            # Timestamps are on RunRecord as Unix timestamps (floats) or create_timestamp as datetime
            started_at = None
            ended_at = None
            if record.start_time:
                started_at = datetime.fromtimestamp(record.start_time).isoformat()
            if record.end_time:
                ended_at = datetime.fromtimestamp(record.end_time).isoformat()
            
            run_info = {
                "run_id": run.run_id,
                "filename": filename,
                "sample_name": sample_name,
                "modules": modules or [],
                "include_ensembl": bool(duckdb_config),
                "status": self._get_run_status_str(run.status),
                "started_at": started_at,
                "ended_at": ended_at,
                "output_path": None,
            }
            
            # Check for output if successful
            if run.status == DagsterRunStatus.SUCCESS and sample_name:
                user_name = hf_config.get("user_name") or duckdb_config.get("user_name", self.safe_user_id)
                output_dir = get_user_output_dir() / user_name / sample_name / "modules"
                if output_dir.exists():
                    run_info["output_path"] = str(output_dir)
            
            run_list.append(run_info)
        
        self.runs = run_list


class OutputPreviewState(SafeGridMixin, LazyFrameGridMixin, rx.State):
    """Independent state for the output file preview grid.

    Inherits its own ``LazyFrameGridMixin`` so the output grid has a
    completely separate LazyFrame cache, column defs, rows, etc. from
    the VCF input grid managed by ``UploadState``.

    Output-card clicks go through ``UploadState.preview_output_file`` so the
    card selection and this independent preview grid update together.
    """

    output_preview_loading: bool = False
    output_preview_error: str = ""
    output_preview_label: str = ""
    output_preview_expanded: bool = False

    @rx.var
    def has_output_preview(self) -> bool:
        """True when the output grid has data loaded."""
        return bool(self.lf_grid_loaded)

    @rx.var
    def output_preview_row_count(self) -> int:
        """Total filtered row count in the output grid."""
        return int(self.lf_grid_row_count)

    @rx.var
    def has_output_preview_error(self) -> bool:
        """True when the last output preview load failed."""
        return bool(self.output_preview_error)

    def view_output_file(
        self, file_path: str
    ) -> Generator[None, None, None]:
        """Load an output data file into the output preview grid.

        Generator dispatched by ``UploadState.preview_output_file``. Reflex
        iterates it and pushes intermediate loading state to the frontend.
        """
        path = Path(file_path)
        if not path.exists():
            self.output_preview_error = f"File not found: {path.name}"
            return

        self.output_preview_loading = True
        self.output_preview_error = ""
        self.output_preview_expanded = True
        yield

        lf, descriptions = scan_file(path)
        yield from self.set_lazyframe(lf, descriptions, chunk_size=300)
        self.register_grid_source("scan_file", path)
        _inject_rsid_link_renderer(self)

        self.output_preview_label = path.name
        self.output_preview_loading = False

    def toggle_output_preview(self):
        """Toggle the output preview section open/closed."""
        self.output_preview_expanded = not self.output_preview_expanded

    def clear_output_preview(self):
        """Reset the output preview grid to empty state."""
        self.reset_grid_view_state()
        self.output_preview_label = ""
        self.output_preview_error = ""
        self.output_preview_expanded = False
        self.lf_grid_loaded = False
        self.lf_grid_rows = []
        self.lf_grid_columns = []
        self.lf_grid_row_count = 0
        self.clear_grid_source()


# ============================================================================
# PRS STATE — Polygenic Risk Score computation via prs-ui
# ============================================================================

from prs_ui import PRSComputeStateMixin
import prs_ui
import prs_ui.mixin as _prs_ui_mixin
from prs_ui.mixin import SUPERPOPULATION_LABELS as _SUPERPOPULATION_LABELS
from prs_ui.mixin import _enriched_to_row_dict as _prs_enriched_to_row_dict
from prs_ui.mixin import loaded_grid_selection_model as _loaded_grid_selection_model
from just_prs import resolve_cache_dir as _prs_resolve_cache_dir
from just_prs.prs import compute_prs as _compute_prs_fn
from just_prs.prs import ReferenceUniverse as _ReferenceUniverse
from just_prs.prs_catalog import PRSCatalog as _PRSCatalog
from just_prs.enrich import enrich_prs_result as _enrich_prs_result
from just_prs.reference import SUPERPOPULATIONS
from just_prs.viz import FINE_POPULATION_LABELS as _FINE_POPULATION_LABELS
from just_prs.viz import IGSR_POPULATION_URL as _IGSR_POPULATION_URL
from just_prs.viz import fine_population_label as _fine_population_label


def _scan_prs_genotypes(path: Path | str) -> pl.LazyFrame:
    """Scan a just-dna-lite parquet as just-prs genotypes.

    Annotation parquets keep polars-bio ``start``. Ancestry and scoring look
    up ``pos``. ``_get_genotypes_lf()`` already aliases; any extra
    ``scan_parquet`` into just-prs must go through this helper too.
    """
    return _prs_ui_mixin._normalize_genotypes_lf(pl.scan_parquet(str(path)))


_prs_catalog_instance: Optional[_PRSCatalog] = None
_PRS_REQUIRED_SCORE_COLUMNS = {
    "ftp_link_ebi",
    "scoring_parquet_filename",
    "scoring_parquet_path",
}
_PRS_CORRUPT_PARQUET_MARKERS = (
    "out of specification",
    "invalid thrift",
    "metadata size",
    "footer",
    "not a parquet",
)
_prs_cache_checked = False


def _is_prs_corrupt_parquet_error(exc: BaseException) -> bool:
    """Return whether an exception looks like a corrupt PRS parquet cache read."""
    message = f"{type(exc).__name__}: {exc}".casefold()
    return "parquet" in message and any(marker in message for marker in _PRS_CORRUPT_PARQUET_MARKERS)


def _remove_prs_score_parquet_cache(pgs_id: str, cache_dir: Path, genome_build: str) -> bool:
    """Remove the cached scoring parquet for one PGS ID so just-prs can re-fetch it."""
    parquet_path = cache_dir / f"{pgs_id}_hmPOS_{genome_build}.parquet"
    if not parquet_path.exists():
        return False
    parquet_path.unlink(missing_ok=True)
    logger.warning("Removed corrupt PRS scoring cache: %s", parquet_path)
    return True


def _remove_prs_metadata_cache(cache_dir: Path) -> None:
    """Remove PRS metadata parquets so PRSCatalog can rebuild or pull them again."""
    metadata_dir = cache_dir / "metadata"
    for name in ("scores.parquet", "performance.parquet", "best_performance.parquet", "publications.parquet"):
        (metadata_dir / name).unlink(missing_ok=True)


def _prs_scores_cache_is_stale(cache_dir: Path) -> bool:
    """Return whether cached PRS score metadata predates parquet-backed scoring."""
    scores_path = cache_dir / "metadata" / "scores.parquet"
    if not scores_path.exists():
        return False
    try:
        schema = pl.scan_parquet(scores_path).collect_schema()
    except Exception as exc:
        if _is_prs_corrupt_parquet_error(exc):
            logger.warning("PRS score metadata cache is corrupt; refreshing: %s", scores_path)
            _remove_prs_metadata_cache(cache_dir)
            return True
        raise
    return not _PRS_REQUIRED_SCORE_COLUMNS.issubset(set(schema.names()))


def _ensure_prs_catalog_cache_current(cache_dir: str) -> None:
    """Refresh stale PRS metadata left behind by older just-prs releases."""
    global _prs_cache_checked, _prs_catalog_instance
    if _prs_cache_checked:
        return

    cache_path = Path(cache_dir)
    if _prs_ui_mixin._catalog.cache_dir != cache_path:
        _prs_ui_mixin._catalog = _PRSCatalog(cache_dir=cache_path)

    if _prs_scores_cache_is_stale(cache_path):
        _prs_ui_mixin._catalog.reload()
        _prs_catalog_instance = None

    _prs_cache_checked = True


def _get_prs_catalog(cache_dir: str) -> _PRSCatalog:
    """Lazy singleton for the PRS catalog used in background computation."""
    global _prs_catalog_instance
    if _prs_catalog_instance is None:
        _prs_catalog_instance = _PRSCatalog(cache_dir=Path(cache_dir))
    return _prs_catalog_instance


def _prs_results_version() -> str:
    """Version tag for stored PRS results.  Changes when enrichment format changes."""
    return f"prs-ui={prs_ui.__version__}"


def _prs_ready_parquet_path(parquet_path: str) -> str:
    """Return ``parquet_path`` only when the file is readable and non-empty."""
    if parquet_path and _parquet_is_ready(Path(parquet_path)):
        return parquet_path
    return ""


def _prs_compute_belongs_to_current_genome(
    compute_token: int,
    compute_file: str,
    current_token: int,
    current_file: str,
) -> bool:
    """True only when an in-flight PRS compute still matches the selected genome.

    Background compute snapshots the file + a generation token. Switching
    genomes increments the token and clears the file, so a late write from
    the previous sample must not land on the newly selected one.
    """
    if not compute_file or not current_file:
        return False
    return compute_token == current_token and compute_file == current_file


def _prs_reusable_results_for_file(
    results: list[dict],
    source_file: str,
    current_file: str,
    force_recompute: bool,
    allowed_source_files: set[str] | None = None,
) -> dict[str, dict]:
    """Index cached PRS rows that belong to the current genome or comparison set.

    Rows from another genome, or any cache when force-recompute is on, are
    ignored so Compute cannot skip work by PGS ID after a file switch.
    Comparison rows are keyed by ``pgs_id::sample`` so two genomes never share
    a cache slot.
    """
    allowed = allowed_source_files if allowed_source_files is not None else (
        {current_file} if current_file else set()
    )
    if force_recompute or not allowed or not source_file:
        return {}
    if source_file not in allowed:
        return {}
    existing_by_id: dict[str, dict] = {}
    for row in results:
        pgs_id = str(row.get("pgs_id") or "")
        row_file = str(row.get("_source_file") or source_file)
        if pgs_id and row_file in allowed:
            existing_by_id[_prs_result_cache_key(row)] = row
    return existing_by_id


def _preferred_prs_chart_id(
    *,
    grouped: bool,
    trait_rows: list[dict],
    result_rows: list[dict],
    selected_pgs_ids: list[str],
) -> str:
    """Pick the trait or PGS id the results chart should open on.

    Prefers a cached/computed row that belongs to the current selection so
    Compute on an already-scored trait still opens that trait's chart.
    """
    selected = {str(pid) for pid in selected_pgs_ids if pid}
    if grouped:
        for row in trait_rows:
            trait = str(row.get("trait") or "")
            if not trait:
                continue
            pgs_ids = {
                part.strip()
                for part in str(row.get("pgs_ids") or "").split(",")
                if part.strip()
            }
            if selected and pgs_ids and not (pgs_ids & selected):
                continue
            if selected and not pgs_ids:
                continue
            return _prs_ui_mixin._concise_trait_label(trait) or trait
        if trait_rows:
            first = str(trait_rows[0].get("trait") or "")
            return _prs_ui_mixin._concise_trait_label(first) or first
        return ""
    for pid in selected_pgs_ids:
        for row in result_rows:
            if str(row.get("pgs_id") or "") == pid:
                return pid
    if result_rows:
        return str(result_rows[0].get("pgs_id") or "")
    return ""


def _compute_single_prs(
    pgs_id: str,
    vcf_path: str,
    genome_build: str,
    cache_dir: Path,
    genotypes_lf: Optional[pl.LazyFrame],
    catalog: _PRSCatalog,
    best_perf_df: pl.DataFrame,
    ancestry: str,
    compute_all_populations: bool = False,
    reference_restoration: bool = False,
    reference_universe_path: Optional[str] = None,
    reference_universe: Optional[_ReferenceUniverse] = None,
    sample_build: Optional[str] = None,
    genotype_input_mode: str = "auto",
) -> Dict[str, Any]:
    """Compute and enrich a single PRS — pure function, no Reflex state access.

    Uses enrich_prs_result + _enriched_to_row_dict so the result dict matches
    the format that _build_prs_results_grid expects.

    For WGS samples ``reference_restoration=True`` (with a resolved universe)
    fills absent variants as hom-ref, lifting genome-wide coverage from ~27% to
    ~99.9%.  The catalog-wide reference-allele universe is parsed **once** by the
    caller (``prepare_reference_universe``) and injected via ``reference_universe``
    so it is not re-parsed/re-joined per score; ``reference_universe`` takes
    precedence over ``reference_universe_path``.  Restoration only engages in
    just-prs' ``variant_only`` genotype mode, so WGS callers must pass
    ``genotype_input_mode="variant_only"`` — under ``auto`` a DeepVariant VCF's
    RefCall records resolve to ``all_sites`` and restoration silently no-ops.
    ``sample_build`` arms the build guard.
    """
    info = catalog.score_info_row(pgs_id)
    trait = info["trait_reported"] if info else None

    result = _compute_prs_fn(
        vcf_path=vcf_path,
        scoring_file=pgs_id,
        genome_build=genome_build,
        cache_dir=cache_dir,
        pgs_id=pgs_id,
        trait_reported=trait,
        genotypes_lf=genotypes_lf,
        genotype_input_mode=genotype_input_mode,
        reference_restoration=reference_restoration,
        reference_universe_path=reference_universe_path,
        reference_universe=reference_universe,
        sample_build=sample_build,
    )

    enriched = _enrich_prs_result(
        result,
        catalog,
        best_perf_df,
        genome_build=genome_build,
        selected_ancestry=ancestry,
        compute_all_populations=compute_all_populations,
    )

    row = _prs_enriched_to_row_dict(enriched)
    row["_low_match"] = result.match_rate < 0.1
    return row


def _compute_single_prs_with_cache_repair(
    pgs_id: str,
    vcf_path: str,
    genome_build: str,
    cache_dir: Path,
    genotypes_lf: Optional[pl.LazyFrame],
    catalog: _PRSCatalog,
    best_perf_df: pl.DataFrame,
    ancestry: str,
    compute_all_populations: bool = False,
    reference_restoration: bool = False,
    reference_universe_path: Optional[str] = None,
    reference_universe: Optional[_ReferenceUniverse] = None,
    sample_build: Optional[str] = None,
    genotype_input_mode: str = "auto",
) -> Dict[str, Any]:
    """Compute one PRS, repairing a corrupt local scoring parquet and retrying once."""
    kwargs = dict(
        pgs_id=pgs_id,
        vcf_path=vcf_path,
        genome_build=genome_build,
        cache_dir=cache_dir,
        genotypes_lf=genotypes_lf,
        catalog=catalog,
        best_perf_df=best_perf_df,
        ancestry=ancestry,
        compute_all_populations=compute_all_populations,
        reference_restoration=reference_restoration,
        reference_universe_path=reference_universe_path,
        reference_universe=reference_universe,
        sample_build=sample_build,
        genotype_input_mode=genotype_input_mode,
    )
    try:
        return _compute_single_prs(**kwargs)
    except Exception as exc:
        if not _is_prs_corrupt_parquet_error(exc):
            raise
        removed = _remove_prs_score_parquet_cache(pgs_id, cache_dir, genome_build)
        if not removed:
            raise
        logger.warning("Retrying PRS compute for %s after removing corrupt cache", pgs_id)
        return _compute_single_prs(**kwargs)


def _classify_sample_type(variant_count: int) -> tuple[str, float]:
    """Heuristically classify a normalized sample as WGS or array by variant density.

    Whole-genome callsets carry millions of variant records; consumer genotyping
    arrays carry ~0.3–1M typed markers; targeted panels far fewer.  Returns
    ``(sample_type, confidence)``; the user can override in the UI.  We only call
    WGS at high counts because mis-labelling an array as WGS would wrongly assume
    every untyped site is hom-ref.
    """
    n = variant_count
    if n >= 2_000_000:
        return "wgs", 0.97
    if n >= 1_000_000:
        return "wgs", 0.80
    if n >= 300_000:
        return "array", 0.75
    return "array", 0.85


def _restoration_settings_for_parquet(
    parquet_path: str,
    sample_type: str | None = None,
) -> tuple[bool, str]:
    """Return ``(reference_restoration, genotype_input_mode)`` for one genome.

    The selected left-panel sample uses the user-facing WGS/array toggle.
    Comparison peers are classified from variant density so an array is never
    restored as if it were whole-genome.
    """
    if sample_type == "wgs":
        return True, "variant_only"
    if sample_type == "array":
        return False, "auto"
    try:
        n = int(pl.scan_parquet(parquet_path).select(pl.len()).collect().item())
    except Exception:
        return False, "auto"
    kind, _confidence = _classify_sample_type(n)
    if kind == "wgs":
        return True, "variant_only"
    return False, "auto"


class PRSState(SafeGridMixin, PRSComputeStateMixin, LazyFrameGridMixin, rx.State):
    """PRS computation state — delegates entirely to PRSComputeStateMixin.

    The mixin handles score loading, selection, batch compute, quality
    assessment, percentile lookup, DataGrid rows/columns, and CSV export.
    This class only adds: Dagster checkpoint/restore and UI toggle state.
    """

    genome_build: str = "GRCh38"
    cache_dir: str = str(_prs_resolve_cache_dir())
    status_message: str = ""
    prs_initialized_for_file: str = ""
    prs_results_source_file: str = ""
    prs_compute_token: int = 0
    prs_selection_mode: str = "traits"
    compute_mode: str = "trait"
    prs_force_recompute: bool = False
    _ignore_empty_selection_replay: bool = False

    # --- Auto-detected sample ancestry (just-prs 0.5.1 ancestry epic) ---
    # Inferred on file load; sets selected_ancestry so percentiles default to
    # the matched panel. Shown on the sample row; the trait dashboard Population
    # dropdown is the override. No toolbar selector.
    detected_ancestry: str = ""           # super-pop code (AFR/AMR/EAS/EUR/SAS) or ""
    detected_ancestry_confidence: float = 0.0
    detected_fine_population: str = ""     # within-continent call, when available
    detected_fine_confidence: float = 0.0
    ancestry_detection_status: str = ""    # "" | detecting | done | unknown | failed

    # --- Sequencing type (WGS vs array) — drives reference-allele restoration ---
    # WGS: absent variants are hom-ref, so restoring REF alleles lifts coverage
    # ~27% -> ~99.9%.  Array/targeted: absent means untyped, so no hom-ref fill.
    # Auto-detected from variant density on load (preselected), user-overridable.
    sample_type: str = "wgs"               # effective choice: "wgs" | "array"
    detected_sample_type: str = ""         # heuristic suggestion
    sample_type_confidence: float = 0.0
    sample_type_source: str = ""           # "" | detected | metadata | user
    sample_variant_count: int = 0

    # Extra left-panel genomes scored alongside the selected sample. Filenames
    # only — paths are resolved from UploadState when the comparison is applied.
    compare_filenames: list[str] = []
    compare_choices: list[dict] = []

    def set_prs_force_recompute(self, value: bool) -> None:
        self.prs_force_recompute = bool(value)

    def _after_grid_page_published(self) -> None:
        """Re-project selected PGS IDs onto the current (filtered/sorted) rows."""
        self.lf_grid_row_selection_model = _loaded_grid_selection_model(
            self.lf_grid_rows, self.selected_pgs_ids, "pgs_id"
        )

    def _prs_compute_still_current(self, token: int, source_file: str) -> bool:
        """Return True if a background PRS task still belongs to this genome."""
        return _prs_compute_belongs_to_current_genome(
            token,
            source_file,
            self.prs_compute_token,
            self.prs_initialized_for_file or self.prs_genotypes_path,
        )

    def _clear_prs_sample_state(self) -> None:
        """Drop every sample-tied PRS value so another genome cannot inherit it.

        Trait/PGS selection is kept so the user can recompute the same scores
        on the newly selected genome without re-picking them.
        """
        self.prs_results = []
        self.prs_results_rows = []
        self.prs_results_columns = []
        self.prs_results_column_groups = []
        self.trait_summary_rows = []
        self.trait_summary_columns = []
        self.trait_summary_visible = False
        self.low_match_warning = False
        self.prs_results_source_file = ""
        self.prs_initialized_for_file = ""
        self.prs_genotypes_path = ""
        self._prs_genotypes_lf = None
        self.detected_ancestry = ""
        self.detected_ancestry_confidence = 0.0
        self.detected_fine_population = ""
        self.detected_fine_confidence = 0.0
        self.ancestry_detection_status = ""
        self.detected_sample_type = ""
        self.sample_type_confidence = 0.0
        self.sample_type_source = ""
        self.sample_variant_count = 0
        self.compare_filenames = []
        self.compare_choices = []
        self.prs_computing = False
        self.prs_progress = 0
        self.status_message = ""
        self._reset_selected_result()
        self._reset_grid_view_state(keep_selection=True)
        self._ignore_empty_selection_replay = True

    def reset_for_genome_switch(self, next_parquet_path: str = "") -> None:
        """Clear PRS results/charts when the selected genome changes.

        Always invoked from ``select_file``, including when the new parquet
        is not ready yet.  A no-op when the caller is re-selecting the same
        ready file.
        """
        ready = _prs_ready_parquet_path(next_parquet_path)
        if ready and ready == self.prs_initialized_for_file:
            return
        self.prs_compute_token += 1
        self._clear_prs_sample_state()

    @rx.var
    def prs_results_genome_label(self) -> str:
        """Sample folder name for the genome that owns the visible PRS results."""
        path = self.prs_results_source_file or self.prs_initialized_for_file
        if not path:
            return ""
        return Path(path).parent.name

    def _ensure_result_chart_selected(self) -> None:
        """Open the results chart for the selected trait/score, or the first cached one."""
        if not self.prs_results:
            self._reset_selected_result()
            return
        grouped = self.prs_view_mode == "grouped" or self.prs_selection_mode == "traits"
        if grouped and not self.trait_summary_rows:
            self.build_trait_summary()
        chart_id = _preferred_prs_chart_id(
            grouped=grouped,
            trait_rows=list(self.trait_summary_rows),
            result_rows=list(self.prs_results),
            selected_pgs_ids=list(self.selected_pgs_ids),
        )
        if not chart_id:
            self._reset_selected_result()
            return
        self.selected_result_id = chart_id
        self._refresh_selected_chart()

    def handle_lf_grid_row_selection(self, model: dict) -> None:
        """Keep PGS selection across a sample remount; ignore the empty replay."""
        if self.prs_selection_mode == "traits":
            return
        if is_stale_grid_view_replay(self._lf_grid_replay_selection, model):
            self._lf_grid_replay_selection = ""
            return
        self._lf_grid_replay_selection = ""
        if (
            self._ignore_empty_selection_replay
            and model.get("type", "include") == "include"
            and not model.get("ids", [])
            and self.selected_pgs_ids
        ):
            self._ignore_empty_selection_replay = False
            return
        self._ignore_empty_selection_replay = False
        PRSComputeStateMixin.handle_lf_grid_row_selection(self, model)

    def _refresh_selected_chart(self) -> None:
        """Rebuild the open chart from current results, or close it if stale."""
        selected_id = self.selected_result_id
        if not selected_id or not self.prs_results:
            self._reset_selected_result()
            return
        if self.prs_view_mode == "grouped" or self.prs_selection_mode == "traits":
            for trait_row in self.trait_summary_rows:
                row_trait = str(trait_row.get("trait") or "")
                if row_trait == selected_id or _prs_ui_mixin._concise_trait_label(row_trait) == selected_id:
                    self.selected_result_html = ""
                    self.selected_result_spec = self._generate_trait_chart_spec(selected_id)
                    return
        result = self._result_by_pgs_id(selected_id)
        if result is None:
            self._reset_selected_result()
            return
        self.selected_result_info = self._build_result_info(result)
        self.selected_result_html = ""
        self.selected_result_spec = self._generate_chart_spec(
            selected_id, result, mode=self.chart_mode,
        )

    def set_sample_type(self, value: str) -> None:
        """User override of the sequencing type used for restoration."""
        self.sample_type = "wgs" if value == "wgs" else "array"
        self.sample_type_source = "user"

    @rx.var
    def sample_type_label(self) -> str:
        """Confidence note for the detected sequencing type."""
        if self.detected_sample_type and self.sample_type_source == "detected":
            pct = round(self.sample_type_confidence * 100)
            return f"(autodetected {pct}% confidence)"
        if self.sample_type_source == "metadata":
            return "Set from sample metadata"
        return ""

    @rx.var
    def ancestry_chip_label(self) -> str:
        """Compact super-population label for the current-sample row."""
        if self.ancestry_detection_status != "done" or not self.detected_ancestry:
            return ""
        name = _SUPERPOPULATION_LABELS.get(self.detected_ancestry, self.detected_ancestry)
        return f"{name} ({self.detected_ancestry})"

    @rx.var
    def ancestry_chip_confidence(self) -> str:
        """Classifier confidence shown next to the ancestry chip."""
        if self.ancestry_detection_status != "done" or not self.detected_ancestry:
            return ""
        return f"{round(self.detected_ancestry_confidence * 100)}%"

    @rx.var
    def detected_fine_label(self) -> str:
        """Closest 1000G cohort label for the current-sample row."""
        if self.ancestry_detection_status != "done" or not self.detected_fine_population:
            return ""
        return _fine_population_label(self.detected_fine_population)

    @rx.var
    def detected_fine_url(self) -> str:
        """IGSR population page for a known 1000G fine-population code."""
        code = self.detected_fine_population
        if self.ancestry_detection_status != "done" or not code:
            return ""
        if code not in _FINE_POPULATION_LABELS:
            return ""
        return _IGSR_POPULATION_URL.format(code=code)

    @rx.var
    def detected_fine_title(self) -> str:
        """Tooltip describing the closest 1000G cohort."""
        code = self.detected_fine_population
        if self.ancestry_detection_status != "done" or not code:
            return ""
        entry = _FINE_POPULATION_LABELS.get(code)
        if entry is None:
            return (
                "Closest reference cohort in the ancestry model. This is a "
                "nearest reference point, not a nationality."
            )
        return (
            f"{entry[1]}. This is the nearest 1000 Genomes cohort, not a nationality."
        )

    @rx.var
    def detected_fine_confidence_label(self) -> str:
        """Fine-population classifier confidence, when available."""
        if (
            self.ancestry_detection_status != "done"
            or not self.detected_fine_population
            or self.detected_fine_confidence <= 0
        ):
            return ""
        return f"{round(self.detected_fine_confidence * 100)}%"

    @rx.var
    def sample_variant_label(self) -> str:
        """Variant count for the current-sample row."""
        if self.sample_variant_count <= 0:
            return ""
        return f"{self.sample_variant_count:,} variants"

    @rx.var
    def is_comparing(self) -> bool:
        """True when extra left-panel genomes are included in this PRS run."""
        return len(self.compare_filenames) > 0

    @rx.var
    def compare_heading(self) -> str:
        """Sample-section title: one genome, or a comparison of several."""
        n = 1 + len(self.compare_filenames)
        if n <= 1:
            return "Sample"
        return f"Comparing {n} samples"

    @rx.var
    def prs_compare_chips(self) -> list[dict]:
        """Peer rows for the Compare UI (selected file stays on the primary row)."""
        samples = list(self.prs_samples)
        chips: list[dict] = []
        for i, filename in enumerate(self.compare_filenames):
            sample = samples[i + 1] if i + 1 < len(samples) else {}
            chips.append(
                {
                    "filename": filename,
                    "label": str(sample.get("label") or _vcf_sample_stem(filename)),
                    "color": str(
                        sample.get("color") or _prs_ui_mixin.sample_color(i + 1)
                    ),
                    "ancestry": _prs_ui_mixin._ancestry_chip_text(sample),
                }
            )
        return chips

    async def _refresh_compare_choices(self) -> None:
        """Dropdown options: comparable peers that are not already selected."""
        upload = await self.get_state(UploadState)
        taken = set(self.compare_filenames)
        choices = [
            {
                "filename": peer["filename"],
                "display_name": peer.get("display_name") or peer.get("label") or "",
                "choice_label": peer.get("choice_label")
                or _sample_choice_label(
                    str(peer.get("display_name") or peer.get("label") or ""),
                    peer["filename"],
                ),
            }
            for peer in upload.prs_comparable_samples
            if peer["filename"] not in taken
        ]
        self.compare_choices = choices

    @rx.var
    def has_remaining_compare_choices(self) -> bool:
        """True when another left-panel sample can still be added."""
        return len(self.compare_choices) > 0

    @rx.var
    def has_one_compare_choice(self) -> bool:
        """One leftover peer: the add button can skip a picker."""
        return len(self.compare_choices) == 1

    @rx.var
    def compare_add_label(self) -> str:
        """Button text: name the leftover sample when there is only one."""
        if len(self.compare_choices) != 1:
            return "Add for comparison"
        name = str(self.compare_choices[0].get("display_name") or "sample")
        return f"Add {name} for comparison"

    @rx.var
    def compare_add_key(self) -> str:
        """Remount the add picker after a sample is added so it stays empty."""
        return ",".join(self.compare_filenames)

    async def _apply_compare_set(self) -> None:
        """Rebuild mixin ``prs_samples`` from the left-panel selection + peers."""
        upload = await self.get_state(UploadState)
        selected = upload.selected_file
        user_id = upload.safe_user_id
        if not selected or not user_id:
            return
        comparable = {peer["filename"]: peer for peer in upload.prs_comparable_samples}
        peers = [name for name in self.compare_filenames if name in comparable]
        if peers != list(self.compare_filenames):
            self.compare_filenames = peers
        primary_path = self.prs_initialized_for_file or str(
            _normalized_parquet_for_vcf(user_id, selected)
        )
        if not primary_path or not Path(primary_path).exists():
            return
        if not peers:
            self.load_genotypes(primary_path)
            samples = list(self.prs_samples)
            if samples:
                samples[0] = {
                    **samples[0],
                    "ancestry": self.detected_ancestry,
                    "ancestry_confidence": self.detected_ancestry_confidence,
                    "fine_population": self.detected_fine_population,
                    "fine_confidence": self.detected_fine_confidence,
                }
                self.prs_samples = samples
            return
        display_names = upload.sample_display_names
        payload: list[dict] = [
            {
                "label": str(
                    display_names.get(selected) or _vcf_sample_stem(selected)
                ),
                "path": primary_path,
                "ancestry": self.detected_ancestry,
                "ancestry_confidence": self.detected_ancestry_confidence,
                "fine_population": self.detected_fine_population,
                "fine_confidence": self.detected_fine_confidence,
            }
        ]
        for filename in peers:
            peer = comparable[filename]
            payload.append(
                {
                    "label": str(
                        peer.get("display_name")
                        or peer.get("label")
                        or display_names.get(filename)
                        or _vcf_sample_stem(filename)
                    ),
                    "path": str(_normalized_parquet_for_vcf(user_id, filename)),
                }
            )
        self.load_samples(payload)

    async def refresh_compare_choices(self) -> None:
        """Reload leftover comparable samples for the add-for-comparison control."""
        await self._refresh_compare_choices()

    async def add_compare_sample(self, filename: str | list[str]) -> Any:
        """Add one left-panel sample to the comparison in a single step."""
        if self.prs_computing:
            return
        chosen = filename[0] if isinstance(filename, list) else filename
        if not chosen or chosen in self.compare_filenames:
            return
        upload = await self.get_state(UploadState)
        if chosen not in upload.prs_comparable_sample_filenames:
            return
        self.compare_filenames = [*self.compare_filenames, chosen]
        await self._apply_compare_set()
        await self._refresh_compare_choices()
        if self.compare_filenames:
            return PRSState.detect_compare_ancestries

    async def add_only_compare_choice(self) -> Any:
        """Add the last remaining comparable sample without a picker."""
        if self.prs_computing or len(self.compare_choices) != 1:
            return
        filename = str(self.compare_choices[0].get("filename") or "")
        return await self.add_compare_sample(filename)

    async def remove_compare_sample(self, filename: str) -> Any:
        """Drop one comparison peer; the left-panel sample always stays."""
        if self.prs_computing:
            return
        self.compare_filenames = [name for name in self.compare_filenames if name != filename]
        await self._apply_compare_set()
        await self._refresh_compare_choices()
        if self.compare_filenames:
            return PRSState.detect_compare_ancestries

    async def clear_compare_samples(self) -> None:
        """Return to scoring only the left-panel sample."""
        if self.prs_computing:
            return
        self.compare_filenames = []
        await self._apply_compare_set()
        await self._refresh_compare_choices()

    @rx.event(background=True)
    async def detect_compare_ancestries(self) -> None:
        """Fill ancestry on comparison peers without resetting computed results.

        ``load_samples`` already copied the primary sample's call. Peers are
        inferred here and patched onto ``prs_samples`` in place — calling
        ``load_samples`` again would wipe results.
        """
        async with self:
            if not self.is_multi_sample:
                return
            snapshots = [dict(sample) for sample in self.prs_samples]
            token = self.prs_compute_token
            source_file = self.prs_initialized_for_file
            build = self.genome_build
            cache_dir_str = self.cache_dir

        catalog = _get_prs_catalog(cache_dir_str)
        loop = asyncio.get_event_loop()
        changed = False
        for index, sample in enumerate(snapshots):
            if index == 0 or str(sample.get("ancestry") or ""):
                continue
            path = str(sample.get("path") or "")
            if not path or not Path(path).exists():
                continue
            genotypes_lf = _scan_prs_genotypes(path)
            try:
                sample_ancestry = await loop.run_in_executor(
                    None,
                    lambda lf=genotypes_lf: catalog.infer_sample_ancestry(
                        genotypes_lf=lf, sample_build=build
                    ),
                )
            except Exception as exc:
                logger.warning("Compare-sample ancestry inference failed: %s", exc)
                continue
            superpop = getattr(sample_ancestry, "superpopulation", None)
            if not sample_ancestry or not superpop or superpop == "UNKNOWN":
                continue
            sample["ancestry"] = superpop
            sample["ancestry_confidence"] = float(sample_ancestry.confidence or 0.0)
            sample["fine_population"] = sample_ancestry.fine_population or ""
            sample["fine_confidence"] = float(sample_ancestry.fine_confidence or 0.0)
            changed = True

        if not changed:
            return
        async with self:
            if not self._prs_compute_still_current(token, source_file):
                return
            by_path = {str(sample.get("path") or ""): sample for sample in snapshots}
            merged: list[dict] = []
            for row in self.prs_samples:
                extra = by_path.get(str(row.get("path") or ""), {})
                merged.append(
                    {
                        **row,
                        "ancestry": extra.get("ancestry") or row.get("ancestry") or "",
                        "ancestry_confidence": extra.get("ancestry_confidence")
                        or row.get("ancestry_confidence")
                        or 0.0,
                        "fine_population": extra.get("fine_population")
                        or row.get("fine_population")
                        or "",
                        "fine_confidence": extra.get("fine_confidence")
                        or row.get("fine_confidence")
                        or 0.0,
                    }
                )
            self.prs_samples = merged

    @rx.event(background=True)
    async def detect_sample_ancestry(self) -> None:
        """Infer the sample's genetic ancestry and set the percentile fallback.

        Runs in the background (first call lazy-pulls ~250 MB of reference
        models from HuggingFace) so the UI stays responsive.  On success the
        detected super-population is shown on the sample row and becomes
        ``selected_ancestry``. The trait dashboard Population dropdown is the
        override for card numbers.
        """
        async with self:
            if self._get_genotypes_lf() is None:
                path = self.prs_genotypes_path
                if path and Path(path).exists():
                    self.set_prs_genotypes_lf(pl.scan_parquet(path))
            genotypes_lf = self._get_genotypes_lf()
            if genotypes_lf is None:
                return
            build = self.genome_build
            cache_dir_str = self.cache_dir
            token = self.prs_compute_token
            source_file = self.prs_initialized_for_file
            self.ancestry_detection_status = "detecting"
            self.detected_ancestry = ""
            self.detected_ancestry_confidence = 0.0
            self.detected_fine_population = ""
            self.detected_fine_confidence = 0.0

        try:
            catalog = _get_prs_catalog(cache_dir_str)
            loop = asyncio.get_event_loop()
            sample_ancestry = await loop.run_in_executor(
                None,
                lambda: catalog.infer_sample_ancestry(
                    genotypes_lf=genotypes_lf, sample_build=build
                ),
            )
            async with self:
                if not self._prs_compute_still_current(token, source_file):
                    return
                superpop = getattr(sample_ancestry, "superpopulation", None)
                if not sample_ancestry or not superpop or superpop == "UNKNOWN":
                    self.ancestry_detection_status = "unknown"
                    return
                self.detected_ancestry = superpop
                self.detected_ancestry_confidence = float(sample_ancestry.confidence or 0.0)
                self.detected_fine_population = sample_ancestry.fine_population or ""
                self.detected_fine_confidence = float(sample_ancestry.fine_confidence or 0.0)
                self.ancestry_detection_status = "done"
                if superpop in SUPERPOPULATIONS:
                    self.set_selected_ancestry(superpop)
        except Exception as exc:
            logger.warning("Sample ancestry inference failed: %s", exc)
            async with self:
                if self._prs_compute_still_current(token, source_file):
                    self.ancestry_detection_status = "failed"

    def set_compute_mode(self, value: str | list[str]) -> None:
        """Switch the By Trait / By PRS workbench tab."""
        mode = value if isinstance(value, str) else (value[0] if value else "trait")
        if mode not in ("trait", "prs"):
            mode = "trait"
        self.compute_mode = mode
        self.set_prs_selection_mode("traits" if mode == "trait" else "individual")

    def set_prs_selection_mode(self, mode: str) -> None:
        self.prs_selection_mode = mode
        self.compute_mode = "trait" if mode == "traits" else "prs"
        self.prs_view_mode = "grouped" if mode == "traits" else "individual"
        if mode == "individual" and self.selected_pgs_ids:
            self._sync_loaded_grid_selection(self.selected_pgs_ids)
        # Always rebuild on switch to traits so the grouped view reflects the
        # CURRENT prs_results — never a stale cached snapshot. Guarding on
        # "not self.trait_summary_rows" previously froze the view (e.g. at 13
        # models) once any summary existed, even after more scores computed.
        if mode == "traits" and self.prs_results:
            self.build_trait_summary()

    def sync_trait_pgs_ids(self, ids: list[str]) -> None:
        """Receive resolved PGS IDs from PRSTraitState."""
        if self.prs_selection_mode == "traits":
            self.selected_pgs_ids = ids

    def initialize_prs(self) -> Any:
        """Initialize PRS score metadata after validating the local cache."""
        _ensure_prs_catalog_cache_current(self.cache_dir)
        yield from PRSComputeStateMixin.initialize_prs(self)

    def load_compute_scores(self) -> Any:
        """Load PRS scores after refreshing stale metadata caches."""
        _ensure_prs_catalog_cache_current(self.cache_dir)
        yield from PRSComputeStateMixin.load_compute_scores(self)

    @rx.var
    def prs_dagster_url(self) -> str:
        parquet_path = self.prs_initialized_for_file
        if not parquet_path:
            return ""
        p = Path(parquet_path)
        partition_key = f"{p.parent.parent.name}/{p.parent.name}"
        return f"{get_dagster_web_url()}/assets/prs_results?partition={partition_key}"

    def initialize_prs_for_file(self, parquet_path: str, genome_build: str) -> Any:
        """Initialize PRS for a newly selected VCF file.

        Sets genotypes LazyFrame and loads PGS Catalog scores.  On file
        switch, clears stale results/charts and tries to restore this
        file's previous results from Dagster — never another genome's.
        """
        self.genome_build = "GRCh38"
        ready_parquet_path = _prs_ready_parquet_path(parquet_path)

        same_file = bool(ready_parquet_path) and ready_parquet_path == self.prs_initialized_for_file
        if not same_file:
            leftover = bool(
                self.prs_results
                or self.selected_result_id
                or self.prs_initialized_for_file
                or self.prs_results_source_file
            )
            if leftover:
                self.prs_compute_token += 1
                self._clear_prs_sample_state()
            self.prs_initialized_for_file = ready_parquet_path
            self.load_genotypes(ready_parquet_path)
        elif ready_parquet_path:
            self.prs_genotypes_path = ready_parquet_path
            self.set_prs_genotypes_lf(pl.scan_parquet(ready_parquet_path))
        else:
            self.prs_genotypes_path = ""
            self._prs_genotypes_lf = None

        yield from self.initialize_prs()

        if not self.prs_results and ready_parquet_path:
            p = Path(ready_parquet_path)
            partition_key = f"{p.parent.parent.name}/{p.parent.name}"
            self._load_prs_results_from_dagster(partition_key)

        yield PRSTraitState.initialize_traits(self.genome_build, ready_parquet_path, self.include_harmonized)

        yield PRSState.refresh_compare_choices

        # Auto-detect sequencing type + ancestry for a newly loaded sample.
        if not same_file and ready_parquet_path:
            self._detect_sample_type(ready_parquet_path)
            self.ancestry_detection_status = ""
            self.detected_ancestry = ""
            yield PRSState.detect_sample_ancestry

    def _detect_sample_type(self, parquet_path: str) -> None:
        """Classify WGS vs array from variant density and preselect it.

        Runs per newly loaded sample, overriding any prior in-session choice
        because the override belonged to the previous sample.  Parquet row count
        is read from file metadata, so this is fast even for large WGS callsets.
        """
        try:
            n = int(pl.scan_parquet(parquet_path).select(pl.len()).collect().item())
        except Exception as exc:
            logger.debug("Sample-type detection skipped: %s", exc)
            return
        kind, confidence = _classify_sample_type(n)
        self.sample_variant_count = n
        self.detected_sample_type = kind
        self.sample_type_confidence = confidence
        self.sample_type = kind
        self.sample_type_source = "detected"

    def set_prs_genome_build(self, value: str) -> Any:
        """Set genome build and reload both individual scores and trait grid."""
        yield from PRSComputeStateMixin.set_prs_genome_build(self, value)
        yield PRSTraitState.load_traits(self.genome_build, self.prs_genotypes_path, self.include_harmonized)

    def set_include_harmonized(self, value: bool) -> Any:
        """Reload both score and trait selectors when harmonized scores change."""
        yield from PRSComputeStateMixin.set_include_harmonized(self, value)
        yield PRSTraitState.load_traits(self.genome_build, self.prs_genotypes_path, self.include_harmonized)

    @rx.event(background=True)
    async def compute_selected_prs(self) -> None:
        """Compute PRS in background so the UI stays responsive.

        Uses @rx.event(background=True) to release the Reflex state lock
        during heavy compute_prs() calls.  Each score is computed in a
        thread-pool executor; state is updated via brief ``async with self:``
        blocks between iterations.
        """
        token = 0
        source_file = ""
        async with self:
            if self._get_genotypes_lf() is None:
                path = self.prs_genotypes_path
                if path and Path(path).exists():
                    self.set_prs_genotypes_lf(pl.scan_parquet(path))

            if self._get_genotypes_lf() is None:
                self.status_message = "Normalized VCF not found — run normalization first."
                return

            selected_ids = list(self.selected_pgs_ids)
            if not selected_ids:
                if self.prs_results:
                    self.build_trait_summary()
                    self._ensure_result_chart_selected()
                    self.status_message = (
                        "Showing cached PRS results. Select a trait above to compute more scores."
                    )
                    return
                self.status_message = "No PGS scores selected. Load and select scores above."
                return

            genome_build = self.genome_build
            cache_dir_str = self.cache_dir
            ancestry = self.selected_ancestry
            all_pops = self.compute_all_populations
            sample_type = self.sample_type
            refresh_reference_cache = self.refresh_reference_cache_before_compute
            self.prs_compute_token += 1
            token = self.prs_compute_token
            source_file = self.prs_initialized_for_file or self.prs_genotypes_path
            if not source_file:
                self.status_message = "Normalized VCF not found — run normalization first."
                return

            sample_jobs: list[tuple[str, str, pl.LazyFrame, bool, str]] = []
            for index, (label, path, lf) in enumerate(self._iter_sample_genotypes()):
                if not path:
                    continue
                if index == 0:
                    restore, mode = _restoration_settings_for_parquet(
                        path, sample_type=sample_type
                    )
                else:
                    restore, mode = _restoration_settings_for_parquet(path)
                sample_jobs.append((label, path, lf, restore, mode))
            if not sample_jobs:
                self.status_message = "Normalized VCF not found — run normalization first."
                return
            color_map = self._sample_color_map()
            comparing = self.is_multi_sample
            allowed_files = {path for _label, path, _lf, _restore, _mode in sample_jobs}
            allowed_files.add(source_file)
            existing_by_id = _prs_reusable_results_for_file(
                list(self.prs_results),
                self.prs_results_source_file,
                source_file,
                self.prs_force_recompute,
                allowed_source_files=allowed_files,
            )

            work_items: list[tuple[str, str, str, pl.LazyFrame, bool, str]] = []
            for label, path, lf, restore, mode in sample_jobs:
                for pid in selected_ids:
                    cache_key = _prs_result_cache_key({"pgs_id": pid, "sample": label})
                    if cache_key not in existing_by_id:
                        work_items.append((pid, label, path, lf, restore, mode))
            total = len(work_items)

            self.prs_computing = True
            self.prs_progress = 0
            self.low_match_warning = False
            if self.prs_force_recompute or self.prs_results_source_file != source_file:
                self.prs_results = []
                self.prs_results_rows = []
                self.prs_results_columns = []
                self.prs_results_column_groups = []
                self._reset_selected_result()

            if not work_items:
                self._build_prs_results_grid()
                self.prs_computing = False
                self.prs_progress = 100
                n_selected = len(selected_ids) * max(len(sample_jobs), 1)
                self.status_message = f"All {n_selected} selected score(s) already computed"
                if self.prs_results:
                    self.build_trait_summary()
                    self._ensure_result_chart_selected()
                return

            self.status_message = f"Computing PRS for {total} score(s)..." + (
                f" ({len(existing_by_id)} already computed)" if existing_by_id else ""
            )

        try:
            catalog = _get_prs_catalog(cache_dir_str)
            if refresh_reference_cache:
                catalog.refresh_reference_cache(panel="1000g")
            cache_path = Path(cache_dir_str) / "scores"
            best_perf_df = catalog.best_performance().collect()

            # WGS samples: restore reference alleles for absent variants (assumed
            # hom-ref) so genome-wide coverage isn't capped at the recorded set.
            # Restoration only engages in just-prs' variant_only mode, so WGS must
            # force it (auto would mis-detect DeepVariant RefCall VCFs as all_sites
            # and silently skip restoration).  Arrays keep auto: absent means
            # untyped, never hom-ref, so they must not impute.  Comparison peers
            # are classified independently so an array is never restored as WGS.
            any_restoration = any(restore for _label, _path, _lf, restore, _mode in sample_jobs)
            # Parse the catalog-wide (~34M-row) reference-allele universe ONCE and
            # reuse the in-memory handle across every selected score, instead of
            # re-parsing + re-joining it per score (the dominant cost — ~8.4 s/score
            # vs ~1.2 s/score with the prepared handle).
            reference_universe: Optional[_ReferenceUniverse] = None
            if any_restoration:
                try:
                    reference_universe = catalog.prepare_reference_universe(genome_build)
                except Exception as exc:
                    logger.warning(
                        "Reference-allele universe unavailable; scoring without restoration: %s",
                        exc,
                    )
                if reference_universe is None:
                    sample_jobs = [
                        (label, path, lf, False, "auto" if restore else mode)
                        for label, path, lf, restore, mode in sample_jobs
                    ]
                    work_items = [
                        (pid, label, path, lf, False, "auto" if restore else mode)
                        for pid, label, path, lf, restore, mode in work_items
                    ]
                    logger.info("WGS restoration requested but universe unavailable for %s", genome_build)
                else:
                    logger.info(
                        "Prepared reference-allele universe once for %s: %d positions",
                        genome_build,
                        reference_universe.n_positions,
                    )

            new_results: List[Dict[str, Any]] = []
            any_low_match = False
            failed_ids: List[str] = []

            for i, (pgs_id, sample_label, sample_path, sample_lf, restoration, genotype_mode) in enumerate(
                work_items, start=1
            ):
                async with self:
                    if not self._prs_compute_still_current(token, source_file):
                        logger.info("Aborting PRS compute; genome switched")
                        return
                    self.prs_progress = round(i / total * 100)
                    sample_note = f" ({sample_label})" if sample_label else ""
                    self.status_message = f"Computing {i}/{total}: {pgs_id}{sample_note}..."

                loop = asyncio.get_event_loop()
                try:
                    row = await loop.run_in_executor(
                        None,
                        lambda pid=pgs_id, path=sample_path, lf=sample_lf, restore=restoration, mode=genotype_mode: (
                            _compute_single_prs_with_cache_repair(
                                pgs_id=pid,
                                vcf_path=path,
                                genome_build=genome_build,
                                cache_dir=cache_path,
                                genotypes_lf=lf,
                                catalog=catalog,
                                best_perf_df=best_perf_df,
                                ancestry=ancestry,
                                compute_all_populations=all_pops,
                                reference_restoration=restore,
                                reference_universe=reference_universe if restore else None,
                                sample_build=genome_build,
                                genotype_input_mode=mode,
                            )
                        ),
                    )
                except Exception as score_exc:
                    logger.warning("PRS compute failed for %s: %s", pgs_id, score_exc)
                    failed_ids.append(pgs_id if not sample_label else f"{pgs_id} ({sample_label})")
                    gc.collect()
                    continue

                if row.pop("_low_match", False):
                    any_low_match = True
                row["_source_file"] = sample_path
                if sample_label:
                    row["sample"] = sample_label
                    row["sample_color"] = color_map.get(sample_label, "")
                new_results.append(row)
                cache_key = _prs_result_cache_key(row)

                # Persist per-score (by-readiness), not once at the end. By-trait
                # selects many scores in a single call, so an end-of-loop-only
                # checkpoint loses every computed score if the Nth one — or the
                # trait-summary build — crashes. Update + checkpoint after each
                # score so completed work always survives.
                async with self:
                    if not self._prs_compute_still_current(token, source_file):
                        logger.info(
                            "Discarding in-flight PRS write for %s; genome switched",
                            pgs_id,
                        )
                        return
                    existing_by_id[cache_key] = row
                    self.prs_results = list(existing_by_id.values())
                    self.prs_results_source_file = source_file
                    self._build_prs_results_grid()
                    self.low_match_warning = any_low_match
                    if not comparing:
                        self._checkpoint_prs_to_dagster()
                    # Invalidate + rebuild the trait summary on EACH added score so
                    # the grouped view tracks computed scores live instead of caching
                    # a stale snapshot (e.g. "13 models" while the rest stream in).
                    # Only meaningful in grouped mode; the mode switch rebuilds too.
                    if self.prs_selection_mode == "traits" or self.prs_view_mode == "grouped":
                        try:
                            self.build_trait_summary()
                        except Exception as summary_exc:
                            logger.warning("Incremental trait summary rebuild failed: %s", summary_exc)
                    self._ensure_result_chart_selected()
                gc.collect()

            async with self:
                if not self._prs_compute_still_current(token, source_file):
                    logger.info("Discarding finished PRS run; genome switched")
                    return
                merged = list(existing_by_id.values())
                self.prs_results = merged
                self.prs_results_source_file = source_file
                self._build_prs_results_grid()
                self.low_match_warning = any_low_match
                self.prs_computing = False
                self.prs_progress = 100
                n_reused = len(merged) - len(new_results)
                parts = [f"{len(new_results)} new + {n_reused} cached = {len(merged)} total PRS score(s)"]
                if failed_ids:
                    parts.append(f"{len(failed_ids)} failed: {', '.join(failed_ids[:5])}")
                self.status_message = "Computed " + "; ".join(parts)
                if not comparing:
                    self._checkpoint_prs_to_dagster()
                # Build the trait summary in isolation: the per-score results are
                # already persisted above, so a summary/UI failure must never
                # discard them — surface a notice instead of losing the run.
                if self.prs_results:
                    try:
                        self.build_trait_summary()
                    except Exception as summary_exc:
                        logger.error(
                            "Trait summary build failed (per-score results preserved): %s",
                            summary_exc,
                            exc_info=True,
                        )
                        self.status_message += " — trait summary unavailable (results saved)"
                    self._ensure_result_chart_selected()
        except Exception as exc:
            logger.error("PRS computation failed: %s", exc, exc_info=True)
            async with self:
                if self._prs_compute_still_current(token, source_file):
                    self.prs_computing = False
                    self.status_message = f"PRS computation failed: {exc}"

    def _checkpoint_prs_to_dagster(self) -> None:
        """Persist current PRS results to Dagster for cross-session restore."""
        import json
        if self.is_multi_sample:
            return
        parquet_path = self.prs_initialized_for_file
        if not parquet_path or not self.prs_results:
            return
        p = Path(parquet_path)
        partition_key = f"{p.parent.parent.name}/{p.parent.name}"
        pgs_ids = [r.get("pgs_id", "") for r in self.prs_results]
        try:
            instance = get_dagster_instance()
            instance.report_runless_asset_event(
                AssetMaterialization(
                    asset_key="prs_results",
                    partition=partition_key,
                    metadata={
                        "results": MetadataValue.json({"rows": self.prs_results}),
                        "pgs_ids": MetadataValue.text(json.dumps(pgs_ids)),
                        "genome_build": MetadataValue.text(self.genome_build),
                        "ancestry": MetadataValue.text(self.selected_ancestry or ""),
                        "sample_type": MetadataValue.text(self.sample_type),
                        "row_count": MetadataValue.int(len(self.prs_results)),
                        "format_version": MetadataValue.text(_prs_results_version()),
                    },
                )
            )
        except Exception:
            pass

    def _load_prs_results_from_dagster(self, partition_key: str) -> None:
        """Restore PRS results from the latest Dagster materialization."""
        if not partition_key or self.prs_force_recompute:
            return
        try:
            instance = get_dagster_instance()
            result = instance.fetch_materializations(
                records_filter=AssetRecordsFilter(
                    asset_key=AssetKey("prs_results"),
                    asset_partitions=[partition_key],
                ),
                limit=1,
            )
            if not result.records:
                return
            mat = result.records[0].asset_materialization
            if not mat or not mat.metadata:
                return
            version_meta = mat.metadata.get("format_version")
            stored_version = str(version_meta.value) if version_meta and hasattr(version_meta, "value") else ""
            if stored_version != _prs_results_version():
                self.status_message = "Stored PRS results are from an older version — please recompute."
                return
            results_meta = mat.metadata.get("results")
            if not results_meta or not hasattr(results_meta, "data"):
                return
            data = results_meta.data
            rows = data.get("rows", []) if isinstance(data, dict) else []
            rows = [row for row in rows if not str(row.get("sample") or "")]
            if rows:
                source_file = self.prs_initialized_for_file
                stamped = []
                for row in rows:
                    item = dict(row)
                    item["_source_file"] = source_file
                    stamped.append(item)
                self.prs_results = stamped
                self.prs_results_source_file = source_file
                self._build_prs_results_grid()
                stype_meta = mat.metadata.get("sample_type")
                stored_stype = str(stype_meta.value) if stype_meta and hasattr(stype_meta, "value") else ""
                if stored_stype in ("wgs", "array"):
                    self.sample_type = stored_stype
                    self.sample_type_source = "metadata"
                if self.prs_results:
                    self.build_trait_summary()
                    self._ensure_result_chart_selected()
                count_meta = mat.metadata.get("row_count")
                n = int(count_meta.value) if count_meta and hasattr(count_meta, "value") else len(rows)
                self.status_message = f"Restored {n} PRS result(s) from previous session"
        except Exception as exc:
            logger.warning("Failed to restore PRS results from Dagster: %s", exc)


# ============================================================================
# PRS TRAIT STATE — Grouped-by-trait PRS selection
# ============================================================================

def _build_trait_column_overrides() -> dict:
    return {
        "trait": {"minWidth": 200, "flex": 2},
        "trait_efo_id": {
            "width": 160,
            "cellRendererType": "url",
            "cellRendererConfig": {
                "baseUrl": "http://www.ebi.ac.uk/efo/",
                "color": "#1565c0",
            },
        },
        "n_models": {"width": 100},
        "avg_variants": {"width": 130},
        "min_variants": {"width": 120},
        "max_variants": {"width": 120},
        "pgs_ids": {"minWidth": 200, "flex": 1},
    }


class PRSTraitState(SafeGridMixin, LazyFrameGridMixin, rx.State):
    """Trait-grouped PRS selection grid.

    Groups PGS Catalog scores by EFO trait so the user can select traits
    instead of individual PGS IDs.  Selected traits are resolved to their
    constituent PGS IDs and synced to PRSState for computation.
    """

    selected_traits: list[str] = []
    selected_pgs_ids: list[str] = []
    trait_selected_pgs_ids: list[str] = []
    prs_genotypes_path: str = ""
    traits_loaded: bool = False
    _ignore_empty_selection_replay: bool = False

    _trait_to_pgs: dict[str, list[str]] = {}
    _traits_genome_build: str = ""
    _traits_include_harmonized: bool = True

    def _after_grid_page_published(self) -> None:
        """Re-project selected traits onto the current (filtered/sorted) rows."""
        self.lf_grid_row_selection_model = _loaded_grid_selection_model(
            self.lf_grid_rows, self.selected_traits, "trait"
        )

    def _build_trait_df(self, genome_build: str, include_harmonized: bool = True) -> pl.DataFrame:
        """Group PGS Catalog scores by trait and return a summary DataFrame."""
        _ensure_prs_catalog_cache_current(str(_prs_resolve_cache_dir()))
        lf = _prs_ui_mixin._catalog.scores(
            genome_build=genome_build,
            include_harmonized=include_harmonized,
        )
        df = lf.select(
            "pgs_id", "trait_reported", "trait_efo", "trait_efo_id", "n_variants",
        ).collect()

        df = df.with_columns(
            pl.when(pl.col("trait_efo").is_not_null() & (pl.col("trait_efo") != ""))
            .then(pl.col("trait_efo"))
            .otherwise(pl.col("trait_reported"))
            .alias("trait"),
        )

        grouped = df.group_by("trait").agg(
            pl.col("pgs_id").count().alias("n_models"),
            pl.col("pgs_id").alias("_pgs_list"),
            pl.col("trait_efo_id").first().alias("trait_efo_id"),
            pl.col("n_variants").mean().cast(pl.Int64).alias("avg_variants"),
            pl.col("n_variants").min().alias("min_variants"),
            pl.col("n_variants").max().alias("max_variants"),
        ).sort("n_models", descending=True)

        mapping: dict[str, list[str]] = {}
        for row in grouped.iter_rows(named=True):
            mapping[row["trait"]] = row["_pgs_list"]
        self._trait_to_pgs = mapping

        result = grouped.with_columns(
            pl.col("_pgs_list").list.join(", ").alias("pgs_ids"),
        ).drop("_pgs_list")
        return result

    def load_traits(
        self,
        genome_build: str,
        genotypes_path: str = "",
        include_harmonized: bool = True,
    ) -> Any:
        """Load trait-grouped data into the grid."""
        self._traits_genome_build = genome_build
        self._traits_include_harmonized = include_harmonized
        self.prs_genotypes_path = genotypes_path
        self.traits_loaded = False
        self.selected_traits = []
        self.selected_pgs_ids = []
        self.trait_selected_pgs_ids = []
        yield
        trait_df = self._build_trait_df(genome_build, include_harmonized)
        self.traits_loaded = True
        yield from self.set_lazyframe(
            trait_df.lazy(),
            chunk_size=500,
            eager_value_options_row_limit=0,
            column_overrides=_build_trait_column_overrides(),
        )

    def reset_for_genome_switch(self) -> None:
        """Clear trait-grid filters/sorts when the selected genome changes.

        Trait selection is kept so the user can recompute the same scores.
        """
        self._reset_grid_view_state(keep_selection=True)
        self._ignore_empty_selection_replay = True

    def initialize_traits(
        self,
        genome_build: str,
        genotypes_path: str = "",
        include_harmonized: bool = True,
    ) -> Any:
        """Load traits on first access or when genome build changes."""
        same_config = (
            self._traits_genome_build == genome_build
            and self._traits_include_harmonized == include_harmonized
        )
        self.prs_genotypes_path = genotypes_path
        if same_config and self.traits_loaded:
            return
        yield from self.load_traits(genome_build, genotypes_path, include_harmonized)

    def handle_lf_grid_row_selection(self, model: dict) -> None:
        """Track selected traits and resolve to PGS IDs."""
        if is_stale_grid_view_replay(self._lf_grid_replay_selection, model):
            self._lf_grid_replay_selection = ""
            return
        self._lf_grid_replay_selection = ""
        selection_type: str = model.get("type", "include")
        raw_ids: list = model.get("ids", [])
        if (
            self._ignore_empty_selection_replay
            and selection_type == "include"
            and not raw_ids
            and (self.selected_traits or self.selected_pgs_ids)
        ):
            self._ignore_empty_selection_replay = False
            return
        self._ignore_empty_selection_replay = False
        self.lf_grid_row_selection_model = model
        selected_row_ids: set[int] = {int(i) for i in raw_ids}

        if selection_type == "exclude" and not selected_row_ids:
            self.selected_traits = list(self._trait_to_pgs.keys())
            pgs_ids: list[str] = []
            for ids in self._trait_to_pgs.values():
                pgs_ids.extend(ids)
            self.selected_pgs_ids = pgs_ids
            self.trait_selected_pgs_ids = pgs_ids
            return PRSState.sync_trait_pgs_ids(pgs_ids)  # type: ignore[return-value]

        if selection_type == "include" and not selected_row_ids:
            self.selected_traits = []
            self.selected_pgs_ids = []
            self.trait_selected_pgs_ids = []
            return PRSState.sync_trait_pgs_ids([])  # type: ignore[return-value]

        traits: list[str] = []
        for row in self.lf_grid_rows:
            row_id = row.get("__row_id__")
            in_set = (int(row_id) in selected_row_ids) if row_id is not None else False
            if (selection_type == "include" and in_set) or (
                selection_type == "exclude" and not in_set
            ):
                trait = row.get("trait")
                if trait:
                    traits.append(str(trait))

        self.selected_traits = traits
        resolved = self._resolve_pgs_ids_from_traits()
        return PRSState.sync_trait_pgs_ids(resolved)  # type: ignore[return-value]

    def select_filtered_traits(self) -> Any:
        """Select traits matching the current grid filter."""
        traits: list[str] = []
        for row in self.lf_grid_rows:
            trait = row.get("trait")
            if trait:
                traits.append(str(trait))
        self.selected_traits = traits
        resolved = self._resolve_pgs_ids_from_traits()
        return PRSState.sync_trait_pgs_ids(resolved)  # type: ignore[return-value]

    def _clear_trait_selection(self) -> None:
        """Drop trait checkboxes and the durable PGS id list."""
        self._ignore_empty_selection_replay = False
        self._lf_grid_replay_selection = filter_model_fingerprint(
            self.lf_grid_row_selection_model
        )
        self.selected_traits = []
        self.selected_pgs_ids = []
        self.trait_selected_pgs_ids = []
        self.lf_grid_row_selection_model = {"type": "include", "ids": []}

    def deselect_all_traits(self) -> Any:
        """Clear all selected traits."""
        self._clear_trait_selection()
        return PRSState.sync_trait_pgs_ids([])  # type: ignore[return-value]

    @rx.event(background=True)
    async def clear_lf_grid_filters(self) -> Any:
        """Clear trait filters and the Intelligence (or any) checkbox selection."""
        async with self:
            self._clear_trait_selection()
            self._clear_grid_filter_fields()
        await self._publish_page(append=False, with_count=True)
        return [PRSState.sync_trait_pgs_ids([])]

    def _resolve_pgs_ids_from_traits(self) -> list[str]:
        """Resolve selected traits to PGS IDs."""
        pgs_ids: list[str] = []
        for trait in self.selected_traits:
            pgs_ids.extend(self._trait_to_pgs.get(trait, []))
        self.selected_pgs_ids = pgs_ids
        self.trait_selected_pgs_ids = pgs_ids
        return pgs_ids


# ============================================================================
# AGENT STATE — Module Creator AI agent
# ============================================================================

_AGENT_UPLOADS_DIR = Path("data/agent_uploads")
_MAX_AGENT_ATTACHMENTS = 5


class AgentState(rx.State):
    """State for the Module Creator agent chat and the editing slot.

    The editing slot is the central workspace for a module being created or
    refined.  It can be populated by the agent (after a chat turn) or by
    manual file upload.  The *Add* action registers the slot contents as a
    custom module; *Clear* empties the slot; *Download* fetches a zip.
    """

    # -- Chat state -----------------------------------------------------------
    agent_messages: List[Dict[str, str]] = []
    agent_processing: bool = False
    agent_use_team: bool = True
    agent_status: str = ""
    agent_events: List[Dict[str, str]] = []
    agent_input: str = ""
    # Key used by the modules page textarea to remount on reset.
    _agent_input_key: int = 0
    agent_uploaded_files: List[str] = []
    _agent_uploaded_paths: List[str] = []

    # -- Editing slot state ---------------------------------------------------
    _slot_spec_dir: str = ""
    slot_module_name: str = ""
    slot_module_title: str = ""
    slot_module_description: str = ""
    slot_module_icon: str = ""
    slot_module_color: str = ""
    slot_version: int = 0
    slot_adding: bool = False
    slot_replace_pending_name: str = ""   # module name queued for confirm-replace

    # -- API key settings UI --------------------------------------------------
    settings_expanded: bool = False  # hidden; opened via the header gear button

    def toggle_settings(self):
        self.settings_expanded = not self.settings_expanded

    # -- API key settings -----------------------------------------------------

    @rx.var
    def gemini_key_configured(self) -> bool:
        """True when a Gemini/Google API key is present in the environment."""
        return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))

    @rx.var
    def openai_key_configured(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    @rx.var
    def anthropic_key_configured(self) -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY"))

    @rx.var
    def settings_gemini_placeholder(self) -> str:
        return "Already configured — paste to update" if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") else "Paste Gemini API key…"

    @rx.var
    def settings_openai_placeholder(self) -> str:
        return "Already configured — paste to update" if os.getenv("OPENAI_API_KEY") else "Paste OpenAI API key… (optional)"

    @rx.var
    def settings_anthropic_placeholder(self) -> str:
        return "Already configured — paste to update" if os.getenv("ANTHROPIC_API_KEY") else "Paste Anthropic API key… (optional)"

    def save_api_keys(self, form_data: dict) -> None:
        """Write submitted API keys into os.environ and persist to .env."""
        key_map = {
            "gemini_key": "GEMINI_API_KEY",
            "openai_key": "OPENAI_API_KEY",
            "anthropic_key": "ANTHROPIC_API_KEY",
        }
        env_path = Path(__file__).resolve().parents[3] / ".env"
        lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
        changed = []
        for field, env_var in key_map.items():
            value = (form_data.get(field) or "").strip()
            if not value:
                continue
            os.environ[env_var] = value
            changed.append(env_var)
            updated = False
            for i, line in enumerate(lines):
                stripped = line.lstrip("# \t")
                if stripped.startswith(f"{env_var}="):
                    lines[i] = f"{env_var}={value}"
                    updated = True
                    break
            if not updated:
                lines.append(f"{env_var}={value}")
        if changed:
            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            # Collapse settings panel after a successful save
            self.settings_expanded = False
            yield rx.toast.success(f"Saved to .env: {', '.join(changed)}")
        else:
            yield rx.toast.info("No keys entered — nothing saved.")

    def set_agent_input(self, value: str) -> None:
        """Explicit setter for agent_input (avoids deprecation warning)."""
        self.agent_input = value

    def set_agent_use_team(self, value: bool) -> None:
        """Explicit setter for agent_use_team (avoids deprecation warning)."""
        self.agent_use_team = value

    def set_agent_mode(self, value: Union[str, List[str]]) -> None:
        """Set module creator mode from segmented control value."""
        mode = value[0] if isinstance(value, list) and value else value
        self.agent_use_team = mode == "team"

    def _reset_agent_input(self) -> None:
        """Clear chat input and remount uncontrolled textarea."""
        self.agent_input = ""
        self._agent_input_key = self._agent_input_key + 1

    # -- Slot computed vars ---------------------------------------------------

    @rx.var
    def slot_is_populated(self) -> bool:
        """True when the editing slot contains a valid module spec."""
        if not self._slot_spec_dir:
            return False
        return (Path(self._slot_spec_dir) / "module_spec.yaml").exists()

    @rx.var
    def slot_files(self) -> List[str]:
        """Filenames in the current editing slot."""
        if not self._slot_spec_dir:
            return []
        d = Path(self._slot_spec_dir)
        if not d.exists():
            return []
        return sorted(f.name for f in d.iterdir() if f.is_file())

    @rx.var
    def slot_zip_url(self) -> str:
        """URL to download the slot spec as a zip (version appended to filename)."""
        if not self._slot_spec_dir or not self.slot_module_name:
            return ""
        return f"{_backend_api_url()}/api/agent-spec-zip/{self.slot_module_name}?v={self.slot_version}"

    @rx.var
    def slot_display_name(self) -> str:
        """Human-readable slot title: 'name — title (v3)'."""
        if not self.slot_module_name:
            return ""
        parts = [self.slot_module_name]
        if self.slot_module_title and self.slot_module_title != self.slot_module_name:
            parts.append(f"— {self.slot_module_title}")
        if self.slot_version > 0:
            parts.append(f"(v{self.slot_version})")
        return " ".join(parts)

    @rx.var
    def slot_archive_logs(self) -> List[Dict[str, str]]:
        """List of versioned log files across all version dirs for this module."""
        if not self._slot_spec_dir or not self.slot_module_name:
            return []
        module_dir = GENERATED_MODULES_DIR / self.slot_module_name
        if not module_dir.exists():
            return []
        name = self.slot_module_name
        logs = []
        for vdir in sorted(module_dir.iterdir()):
            if not vdir.is_dir() or not vdir.name.startswith("v"):
                continue
            for f in sorted(vdir.iterdir()):
                if f.is_file() and f.suffix == ".log":
                    logs.append({
                        "name": f.name,
                        "url": f"{_backend_api_url()}/api/agent-log/{name}/{vdir.name}/{f.name}",
                    })
        return logs

    # -- Helpers --------------------------------------------------------------

    def _add_chat_message(self, role: str, content: str) -> None:
        """Append a message to the chat log."""
        self.agent_messages = [*self.agent_messages, {"role": role, "content": content}]

    def _populate_slot(self, spec_dir: Path) -> None:
        """Read module_spec.yaml from *spec_dir* and populate slot state."""
        from just_dna_pipelines.agents.module_creator import read_spec_meta

        meta = read_spec_meta(spec_dir)
        if not meta.get("name"):
            return

        self._slot_spec_dir = str(spec_dir)
        self.slot_module_name = meta["name"]
        self.slot_module_title = meta.get("title", "")
        self.slot_module_description = meta.get("description", "")
        self.slot_module_icon = meta.get("icon", "database")
        self.slot_module_color = meta.get("color", "#6435c9")
        self.slot_version = int(meta.get("version", 1))

    def _build_slot_context(self) -> str:
        """Build a context block from the current slot files for the agent prompt."""
        if not self._slot_spec_dir:
            return ""
        d = Path(self._slot_spec_dir)
        if not d.exists():
            return ""
        parts = ["\n\n--- EXISTING MODULE IN EDITING SLOT (Scenario B) ---"]

        all_files = sorted(f.name for f in d.iterdir() if f.is_file())
        parts.append(f"\nFiles in spec directory: {', '.join(all_files)}")

        for fname in ("module_spec.yaml", "variants.csv", "studies.csv", "MODULE.md"):
            fpath = d / fname
            if fpath.exists():
                parts.append(f"\n=== {fname} ===\n{fpath.read_text(encoding='utf-8')}")
        parts.append(
            "\nThe user wants to modify this module. Produce the COMPLETE "
            "updated module (all files), not just the diff. Keep the same "
            "module name unless instructed otherwise."
            "\nIf a MODULE.md was included above, update it with a new changelog "
            "entry via the write_module_md tool. If none was included, write a "
            "fresh one.\n--- END EXISTING MODULE ---"
        )
        return "\n".join(parts)

    # -- Slot actions ---------------------------------------------------------

    async def upload_to_slot(self, files: list[rx.UploadFile]) -> None:
        """Upload module spec files and populate the editing slot."""
        import zipfile as _zipfile

        if not files:
            return

        tmp_path = Path(tempfile.mkdtemp(prefix="dna_slot_"))
        for f in files:
            if not f.filename:
                continue
            content = await f.read()
            (tmp_path / f.filename).write_bytes(content)

        # Extract zips in place
        for zf_path in list(tmp_path.glob("*.zip")):
            try:
                with _zipfile.ZipFile(zf_path, "r") as zf:
                    zf.extractall(tmp_path)
            except _zipfile.BadZipFile:
                self._add_chat_message("agent", f"{zf_path.name} is not a valid zip file")
                shutil.rmtree(tmp_path, ignore_errors=True)
                return
            zf_path.unlink()

        # Promote files from a single subfolder if needed
        extracted_names = {p.name for p in tmp_path.iterdir() if p.is_file()}
        if "module_spec.yaml" not in extracted_names:
            for subdir in [d for d in tmp_path.iterdir() if d.is_dir()]:
                sub_names = {p.name for p in subdir.iterdir() if p.is_file()}
                if "module_spec.yaml" in sub_names:
                    for child in subdir.iterdir():
                        if child.is_file():
                            shutil.move(str(child), str(tmp_path / child.name))
                    subdir.rmdir()
                    extracted_names = {p.name for p in tmp_path.iterdir() if p.is_file()}
                    break

        if "module_spec.yaml" not in extracted_names:
            self._add_chat_message("agent", "Upload failed: module_spec.yaml not found")
            shutil.rmtree(tmp_path, ignore_errors=True)
            return
        if "variants.csv" not in extracted_names:
            self._add_chat_message("agent", "Upload failed: variants.csv not found")
            shutil.rmtree(tmp_path, ignore_errors=True)
            return

        from just_dna_pipelines.agents.module_creator import read_spec_meta
        meta = read_spec_meta(tmp_path)
        module_name = meta.get("name", "uploaded_module")
        version = int(meta.get("version", 1))
        persist_dir = GENERATED_MODULES_DIR / module_name / f"v{version}"
        persist_dir.mkdir(parents=True, exist_ok=True)
        for fp in tmp_path.iterdir():
            if fp.is_file():
                shutil.copy2(fp, persist_dir / fp.name)
        shutil.rmtree(tmp_path, ignore_errors=True)

        self._populate_slot(persist_dir)
        self._add_chat_message(
            "agent",
            f"Module **{self.slot_module_name}** loaded into editing slot (v{self.slot_version}).",
        )

    def load_custom_module_to_slot(self, module_name: str) -> None:
        """Load a registered custom module into the editing slot.

        If the slot already has a module, set ``slot_replace_pending_name`` so
        the UI can show a confirmation prompt instead of silently overwriting.
        """
        if self.slot_is_populated:
            self.slot_replace_pending_name = module_name
        else:
            self._do_load_custom_module(module_name)

    def confirm_replace_slot(self) -> None:
        """Confirmed — replace current slot contents with the pending module."""
        name = self.slot_replace_pending_name
        self.slot_replace_pending_name = ""
        if name:
            self._do_load_custom_module(name)

    def cancel_replace_slot(self) -> None:
        """Cancel a pending slot-replace operation."""
        self.slot_replace_pending_name = ""

    def _do_load_custom_module(self, module_name: str) -> None:
        """Copy spec files from the registered modules dir into a versioned
        generated dir and populate the editing slot from there."""
        src_dir = CUSTOM_MODULES_DIR / module_name
        if not (src_dir / "module_spec.yaml").exists():
            self._add_chat_message(
                "agent",
                f"Module **{module_name}** has no spec files — try re-registering it first.",
            )
            return
        from just_dna_pipelines.agents.module_creator import read_spec_meta
        meta = read_spec_meta(src_dir)
        version = int(meta.get("version", 1))
        dest_dir = GENERATED_MODULES_DIR / module_name / f"v{version}"
        dest_dir.mkdir(parents=True, exist_ok=True)
        _SPEC_SUFFIXES = {".yaml", ".csv", ".md", ".png", ".log"}
        for f in src_dir.iterdir():
            if f.is_file() and f.suffix.lower() in _SPEC_SUFFIXES:
                shutil.copy2(f, dest_dir / f.name)
        self._populate_slot(dest_dir)
        self._add_chat_message(
            "agent",
            f"Module **{module_name}** loaded into editing slot (v{self.slot_version}).",
        )

    @rx.event(background=True)
    async def add_slot_module(self) -> None:
        """Register the editing slot as a custom module.

        Runs as a background task so the long-running Ensembl resolution
        doesn't block the UI.  Uses get_state(UploadState) to refresh
        the module list directly instead of a cross-state yield which
        is unreliable after long blocking calls.
        """
        async with self:
            if not self._slot_spec_dir:
                return
            spec_dir = self._slot_spec_dir
            self.slot_adding = True

        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(None, register_custom_module, Path(spec_dir))
        except Exception as exc:
            logger.error("Module registration executor failed: %s", exc, exc_info=True)
            async with self:
                self.slot_adding = False
                self._add_chat_message("agent", f"Registration failed: {exc}")
            return

        try:
            async with self:
                self.slot_adding = False
                if result.success:
                    stats = result.stats or {}
                    name = stats.get("module_name", self.slot_module_name)
                    variant_count = stats.get("weights_rows", 0)
                    self._add_chat_message(
                        "agent",
                        f"Module **{name}** registered successfully! "
                        f"({variant_count} variants) — now available for annotation.",
                    )
                    upload_state = await self.get_state(UploadState)
                    upload_state._refresh_module_ui_state()
                else:
                    self._add_chat_message(
                        "agent",
                        f"Registration failed: {'; '.join(result.errors[:3])}",
                    )
        except Exception as exc:
            logger.error("Module UI refresh after registration failed: %s", exc, exc_info=True)
            async with self:
                self.slot_adding = False
                self._add_chat_message("agent", f"Module registered but UI refresh failed: {exc}")

    def clear_slot(self) -> None:
        """Empty the editing slot."""
        self._slot_spec_dir = ""
        self.slot_module_name = ""
        self.slot_module_title = ""
        self.slot_module_description = ""
        self.slot_module_icon = ""
        self.slot_module_color = ""
        self.slot_version = 0
        self._add_chat_message("agent", "Editing slot cleared.")

    # -- Agent file attachment ------------------------------------------------

    async def upload_agent_file(self, files: list[rx.UploadFile]) -> None:
        """Save uploaded context files for the agent (up to 5 total)."""
        if not files:
            return
        _AGENT_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        remaining_slots = _MAX_AGENT_ATTACHMENTS - len(self._agent_uploaded_paths)
        if remaining_slots <= 0:
            self._add_chat_message(
                "status",
                f"Attachment limit reached ({_MAX_AGENT_ATTACHMENTS}). Remove one before adding more.",
            )
            return

        added_count = 0
        for upload_file in files:
            if added_count >= remaining_slots:
                break
            filename = upload_file.filename or "upload"
            dest = _AGENT_UPLOADS_DIR / filename
            if dest.exists():
                stem = dest.stem
                suffix = dest.suffix
                idx = 2
                while True:
                    candidate = _AGENT_UPLOADS_DIR / f"{stem}_{idx}{suffix}"
                    if not candidate.exists():
                        dest = candidate
                        break
                    idx += 1
            data = await upload_file.read()
            dest.write_bytes(data)
            self.agent_uploaded_files = [*self.agent_uploaded_files, dest.name]
            self._agent_uploaded_paths = [*self._agent_uploaded_paths, str(dest)]
            added_count += 1

        skipped_count = len(files) - added_count
        if skipped_count > 0:
            self._add_chat_message(
                "status",
                f"Added {added_count} attachment(s). Skipped {skipped_count} due to the {_MAX_AGENT_ATTACHMENTS}-file limit.",
            )

    def clear_agent_file(self) -> None:
        """Remove all attached files without clearing the chat."""
        self.agent_uploaded_files = []
        self._agent_uploaded_paths = []

    def remove_agent_file(self, filename: str) -> None:
        """Remove one attached file by displayed filename."""
        if filename not in self.agent_uploaded_files:
            return
        idx = self.agent_uploaded_files.index(filename)
        names = list(self.agent_uploaded_files)
        paths = list(self._agent_uploaded_paths)
        names.pop(idx)
        paths.pop(idx)
        self.agent_uploaded_files = names
        self._agent_uploaded_paths = paths

    # -- Chat send ------------------------------------------------------------

    @rx.event(background=True)
    async def send_agent_message(self) -> None:
        """Send a message to the agent (runs in background, UI stays responsive).

        If the editing slot is populated, the existing module files are injected
        as context so the agent can refine rather than recreate.
        """
        async with self:
            question = self.agent_input.strip()
            if not question:
                return
            message = question
            file_paths = list(self._agent_uploaded_paths)
            slot_context = self._build_slot_context()
            self.agent_messages = [
                *self.agent_messages,
                {"role": "user", "content": message},
            ]
            self._reset_agent_input()
            self.agent_processing = True
            self.agent_events = []
            self.agent_status = ""

        spec_output = Path(tempfile.mkdtemp(prefix="module_spec_"))

        msg_to_send = message
        inline_blocks: List[str] = []
        attachment_paths: List[Path] = []
        for raw_path in file_paths:
            path_obj = Path(raw_path)
            if not path_obj.exists():
                continue
            suffix = path_obj.suffix.lower()
            if suffix in (".md", ".txt", ".csv"):
                file_content = path_obj.read_text(encoding="utf-8")
                inline_blocks.append(
                    f"Here is the input document ({path_obj.name}):\n\n{file_content}"
                )
            else:
                attachment_paths.append(path_obj)
        if inline_blocks:
            msg_to_send = "\n\n".join([*inline_blocks, message])

        if slot_context:
            msg_to_send += slot_context

        from just_dna_pipelines.agents.module_creator import run_agent_async, run_team_async, RunLog

        use_team = self.agent_use_team
        run_log = RunLog()
        run_log.log(f"User message: {message}")
        if file_paths:
            run_log.log(f"Attached files: {file_paths}")

        async def _on_status(msg: str) -> None:
            async with self:
                self.agent_status = msg

        async def _on_event(event_type: str, label: str, detail: str, call_id: str = "") -> None:
            async with self:
                self.agent_status = label
                if call_id and event_type.endswith("_done"):
                    # Merge into the matching start entry: rename label and
                    # replace detail with the result (so the collapsible shows
                    # the result rather than the original args).
                    self.agent_events = [
                        {**ev, "label": label, "detail": detail, "type": event_type}
                        if ev.get("call_id") == call_id
                        else ev
                        for ev in self.agent_events
                    ]
                else:
                    self.agent_events = [
                        *self.agent_events,
                        {"type": event_type, "label": label, "detail": detail, "call_id": call_id},
                    ]

        response = None
        error_msg = ""
        try:
            runner = run_team_async if use_team else run_agent_async
            response = await runner(
                message=msg_to_send,
                file_paths=attachment_paths,
                model_id=None,
                spec_output_dir=spec_output,
                on_status=_on_status,
                on_event=_on_event,
                run_log=run_log,
                current_version=self.slot_version,
            )
        except Exception as exc:
            error_msg = str(exc)
            run_log.log(f"ERROR: {error_msg}")

        found_spec_dir = ""
        try:
            if spec_output.exists():
                for d in spec_output.iterdir():
                    if d.is_dir() and (d / "module_spec.yaml").exists():
                        found_spec_dir = str(d)
                        break

            # Persist to data/output/generated_modules/{name}/v{X}/
            if found_spec_dir:
                from just_dna_pipelines.agents.module_creator import read_spec_meta
                meta = read_spec_meta(Path(found_spec_dir))
                module_name = meta.get("name") or Path(found_spec_dir).name
                version = int(meta.get("version", 1))
                persist_dir = GENERATED_MODULES_DIR / module_name / f"v{version}"
                persist_dir.mkdir(parents=True, exist_ok=True)
                for f in Path(found_spec_dir).iterdir():
                    if f.is_file():
                        shutil.copy2(f, persist_dir / f.name)
                found_spec_dir = str(persist_dir)
        except Exception as exc:
            logger.error("Failed to persist agent module spec: %s", exc, exc_info=True)
            if not error_msg:
                error_msg = f"Module spec generated but failed to persist: {exc}"

        async with self:
            agent_reply = (
                f"An error occurred: {error_msg}" if error_msg
                else (response or "Agent returned no response.")
            )
            run_log.log(f"Agent reply length: {len(agent_reply)} chars")
            self.agent_messages = [
                *self.agent_messages,
                {"role": "agent", "content": agent_reply},
            ]
            self.agent_processing = False
            self.agent_status = ""
            # agent_events intentionally kept — user can inspect postmortem.
            # They are cleared at the start of the next send_agent_message.
            if found_spec_dir:
                self._populate_slot(Path(found_spec_dir))

            # Write versioned run log to the module's spec directory
            self._write_run_log(run_log, found_spec_dir, error_msg)

    # -- Run log persistence ---------------------------------------------------

    def _write_run_log(self, run_log: Any, found_spec_dir: str, error_msg: str) -> None:
        """Write the run log into the module's versioned directory.

        Successful runs: ``<module_dir>/v<N>.log``
        Failed runs (no spec produced): ``data/output/generated_modules/_logs/<timestamp>.log``
        """
        if found_spec_dir:
            log_path = Path(found_spec_dir) / f"v{self.slot_version}.log"
        else:
            fallback_dir = GENERATED_MODULES_DIR / "_logs"
            fallback_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_path = fallback_dir / f"failed_{ts}.log"
            run_log.log(f"No module spec produced — writing log to fallback: {log_path}")

        log_path.write_text(run_log.text(), encoding="utf-8")
        logger.info("Run log written to %s", log_path)

    # -- Clear chat -----------------------------------------------------------

    def clear_agent_chat(self) -> None:
        """Reset the agent chat and editing slot to initial state."""
        self.agent_messages = []
        self.agent_processing = False
        self.agent_status = ""
        self.agent_events = []
        self._reset_agent_input()
        self.agent_uploaded_files = []
        self._agent_uploaded_paths = []
        self._slot_spec_dir = ""
        self.slot_module_name = ""
        self.slot_module_title = ""
        self.slot_module_description = ""
        self.slot_module_icon = ""
        self.slot_module_color = ""
        self.slot_version = 0


# ============================================================================
# REGISTRY STATE
# ============================================================================

def _resolve_store(key: str) -> RegistryStore:
    """The store this key names, falling back to the default one.

    Selection arrives from the client, so an unknown key is a possibility rather than a bug —
    it resolves to the default store instead of raising.
    """
    return get_registry_store(key) or default_registry_store()


# Compiled artifact files the digest is computed over. Taken from the compiler rather than
# restated, because a hand-copied list silently stops mirroring it: this was frozen at the
# original three while 0.5 grew the set to sixteen (the 0.4 table families plus the enrichment
# sidecars `frequencies`/`gene_metrics`/`literature`/`sources`), so the digest computed here
# ignored every one of them and could not equal the server's for any enriched module.
# `build_artifact` skips absent files, so passing the full set is safe for a minimal module.
#
# 0.6 made the constant public as `ARTIFACT_PARQUETS` (upstream S35 — the private name is exactly
# what let a hand-kept copy in the publisher drop thirteen of sixteen names), and added three fact
# tables to it. Import it; never re-list it here.
_ARTIFACT_FILES: tuple = tuple(ARTIFACT_PARQUETS)


#: Authored tables that can lead a module, in priority order. The leading table's row count is what
#: the server's enrichment limit counts.
#:
#: Imported rather than restated: the hand-kept copy named four of the ten families, so a module led
#: by any of the other six (`heteroplasmy`, `copynumbers`, `repeat_alleles`, `haplotypes`,
#: `allele_function`, `activity_phenotype`) counted **zero** authored rows and was therefore always
#: routed to the enrichment half of `/check` however large it really was.
_LEAD_TABLES: tuple = LEAD_TABLE_CSVS

#: The server's ceiling on the enrichment half of `/check` (`REGISTRY_ENRICH_MAX_VARIANTS`).
#: Past it the endpoint answers `422 too_many_variants`, so a bigger module goes to `/validate` —
#: which has no network tier and is the half that decides publishability anyway.
_ENRICH_MAX_VARIANTS: int = 500

#: Raw spec bytes past which the spec is packed into one archive rather than sent as loose parts.
#: The server bounds the wire at 25 MiB.
_PACK_ABOVE_BYTES: int = 20 * 1024 * 1024


def _trust_word(trusted: Optional[bool]) -> str:
    """Flatten `ResolutionInfo.trusted` to a branchable word, keeping all three states.

    `None` is not "untrusted": it means the server said nothing, which is what an older release
    predating the field looks like. Collapsing it into `False` would label such a version as
    positionally unjoinable when nothing established that.
    """
    if trusted is True:
        return "yes"
    if trusted is False:
        return "no"
    return "unknown"


def _authored_row_count(module_dir: Path) -> int:
    """Rows in whichever table leads the module — what the enrichment limit counts."""
    for table in _LEAD_TABLES:
        path = module_dir / table
        if path.exists():
            with path.open(encoding="utf-8") as handle:
                return max(sum(1 for _ in handle) - 1, 0)
    return 0


def _spec_bytes(module_dir: Path) -> int:
    """Raw size of the authored parts, which is what decides loose-parts vs packed archive."""
    return sum(
        f.stat().st_size
        for pattern in ("module_spec.yaml", "*.csv", "*.log")
        for f in module_dir.glob(pattern)
        if f.is_file()
    )


def _local_key(namespace: str, name: str) -> str:
    """Local registry key for a registry module: ``{namespace}__{name}``.

    Namespacing keeps a registry install from colliding with (and being shadowed by) a
    same-named HF module or a same-named module from a different namespace — they install and
    appear in annotation as distinct modules. Locally-authored modules (no namespace) keep their
    bare name. The namespace is sanitized to ``[a-z0-9_]`` (e.g. ``just-dna-seq`` → ``just_dna_seq``)
    so the key stays a valid module-name token.
    """
    if not namespace:
        return name
    safe_ns = "".join(ch if ch.isalnum() else "_" for ch in namespace.lower()).strip("_")
    return f"{safe_ns}__{name}"


def _without_local_module(modules: List[Dict[str, Any]], name: str) -> List[Dict[str, Any]]:
    """Drop one installed row from the left-pane list without rescanning disk."""
    return [m for m in modules if m.get("name") != name]


def _cards_with_installed(
    cards: List[Dict[str, Any]],
    local_names: List[str],
    busy_key: str = "",
) -> List[Dict[str, Any]]:
    """Stamp each catalog card with local key, installed, and per-card Get busy.

    The browse grid reads ``installed`` / ``local_key`` / ``busy`` per card.
    Updating those in place (a new list, so Reflex notices) is what flips
    Get ↔ Installed without a catalog round-trip.

    ``busy`` must live on the card. Comparing a global ``busy_key`` to
    ``card["local_key"]`` inside ``rx.foreach`` compiles as one shared Var, so
    every Get button looks clicked.
    """
    keys = set(local_names)
    out: List[Dict[str, Any]] = []
    for card in cards:
        updated = dict(card)
        local_key = updated.get("local_key") or _local_key(
            str(updated.get("namespace") or ""), str(updated.get("name") or ""),
        )
        updated["local_key"] = local_key
        updated["installed"] = local_key in keys
        updated["busy"] = bool(busy_key) and local_key == busy_key
        out.append(updated)
    return out


def _scan_local_modules() -> List[Dict[str, Any]]:
    """Scan the local custom-modules dir → one dict per registered module.

    Two content identities are recorded, because they answer different questions:

    ``signature`` is ``content_signature`` over the *authored* CSVs — name- and
    Ensembl-independent, and **the value the registry gates 409 duplicate_content on**. It is
    therefore the one that predicts whether a publish will be rejected. It is also stable across
    a recompile, which the artifact digest is not: rebuilding a module always mints a new digest,
    so a digest-only check reports "not published" for a module that merely got rebuilt and then
    offers a Publish button the server rejects.

    ``digest`` is the compiled-artifact digest, still computed from the files on disk (not read
    from ``manifest.json``), and still the only identity available for a **compiled-only import**
    that carries no spec CSVs — a metadata-stripped module shared peer-to-peer.

    ``manifest.json`` is used only for optional display metadata (version/namespace/title).
    ``has_spec`` marks whether spec files are present (needed for Edit-into-slot). Pure function
    — no client and no HTTP (``content_signature`` parses CSVs locally) — safe in an executor.
    """
    out: List[Dict[str, Any]] = []
    if not CUSTOM_MODULES_DIR.exists():
        return out
    for d in sorted(CUSTOM_MODULES_DIR.iterdir()):
        # Any lead table, not just weights — a `pharm_variants`-led install is a module, and
        # testing for weights here made one annotatable but unlistable, unpublishable and
        # uneditable from this pane.
        if not (d.is_dir() and has_lead_table(d)):
            continue
        name = d.name
        try:
            digest = build_artifact(d, list(_ARTIFACT_FILES)).digest
        except Exception:  # noqa: BLE001 - unreadable artifact → no digest, treat as unclassified
            digest = ""
        has_spec = (d / "module_spec.yaml").exists()
        signature = ""
        if has_spec:
            try:
                signature = content_signature(d)
            except Exception:  # noqa: BLE001 - unauthored/invalid spec → fall back to digest
                signature = ""
        entry: Dict[str, Any] = {
            "name": name, "version": "", "digest": digest, "signature": signature,
            "namespace": "",
            "catalog_name": name, "title": name, "icon": "database", "color": "#6435c9",
            "has_spec": has_spec, "in_catalog": False,
        }
        manifest_path = d / "manifest.json"
        if manifest_path.exists():
            try:
                mf = read_manifest(manifest_path)
                entry["version"] = mf.identity.version or ""
                entry["namespace"] = mf.identity.namespace or ""
                entry["catalog_name"] = mf.identity.name or name
                entry["title"] = mf.display.title or name
                entry["icon"] = mf.display.icon or "database"
                entry["color"] = mf.display.color or "#6435c9"
            except Exception:  # noqa: BLE001 - manifest is best-effort metadata
                pass
        # The compiler leaves manifest identity.version null (marketplace-assigned at publish
        # time); fall back to the authored spec version so the publish pane shows a version and
        # enables the Publish button.
        if not entry["version"]:
            entry["version"] = spec_version(d)
        out.append(entry)
    return out


class RegistryState(rx.State):
    """Module Registry: local registry cross-referenced against the remote catalog.

    Network calls run in ``@rx.event(background=True)`` handlers off the Reflex state lock.
    """

    # --- Right-pane tab ---
    registry_active_tab: str = "catalog"

    # --- Store (which registry server we are talking to) ---
    # Empty until `load_registry` resolves the default, so a page that never loaded cannot pin a
    # stale key. Selection is per session and deliberately not persisted: the store decides where
    # a publish lands, and a sticky "polygon" from last week is exactly the setting a user would
    # not think to check.
    store_key: str = ""

    # --- Catalog (Catalog tab) ---
    query: str = ""
    sort: str = "name"
    group_filter: str = ""                # 0.8.0 listing group ("" = default; test spaces hidden)
    namespace_filter: str = ""            # "" = all namespaces
    namespace_options: List[str] = []     # namespaces discovered from catalog results
    page: int = 1
    per_page: int = 24
    cards: List[Dict[str, Any]] = []
    total: int = 0
    catalog_loading: bool = False
    catalog_error: str = ""
    server_incompatible: bool = False   # server contract newer than this client (0.7.1 guard)

    # --- Local registry snapshot (name -> metadata + in_catalog flag) ---
    local_modules: List[Dict[str, Any]] = []
    _local_names: List[str] = []

    # --- Selection (left pane) ---
    selected_name: str = ""              # local registry key (namespaced for registry modules)
    selected_catalog_name: str = ""      # catalog module name (for API calls)
    selected_namespace: str = ""
    selected_title: str = ""
    selected_description: str = ""
    selected_author: str = ""
    selected_icon: str = "database"
    selected_color: str = "#6435c9"
    selected_variant_count: int = 0
    selected_gene_count: int = 0
    selected_logo_url: str = ""          # absolute logo URL (schema 0.3.0), "" → fall back to icon
    selected_clinvar_count: int = 0
    selected_pathogenic_count: int = 0
    selected_benign_count: int = 0
    selected_version: str = ""
    selected_versions: List[str] = []
    _remote_versions: List[str] = []
    _remote_digests: Dict[str, str] = {}
    # version -> "yes" | "no" | "unknown". `ResolutionInfo.trusted` is three-valued in registry
    # 0.11.3 and the third state is not a detail: `false` means the compiler reported a positional
    # table that joins by rsID only, and `null` means the server did not say. Carried as a string
    # because an Optional[bool] cannot be branched on with rx.cond without collapsing None to False.
    _remote_trust: Dict[str, str] = {}
    detail_loading: bool = False
    detail_error: str = ""

    # --- Action status + gating ---
    action_busy: bool = False
    # Local registry key of the card currently installing ("" if none / uninstall / import).
    # Backend-only: the catalog grid reads ``card["busy"]``, stamped by
    # ``_cards_with_installed``. Do not compare this to ``card["local_key"]`` in
    # ``rx.foreach`` — that compiles as one shared Var and lights every Get.
    _busy_key: str = ""
    action_message: str = ""
    pending_action: Dict[str, Any] = {}   # {} = none

    # --- Publication identity + profile ---
    install_id: str = ""
    token: str = ""
    account: str = ""              # immutable account handle, once registered
    namespaces: List[str] = []     # namespaces this account owns / belongs to
    display_name: str = ""         # mandatory-to-register, regex-guarded
    email: str = ""
    avatar_local: str = ""         # local-only avatar (data URI); never uploaded
    roles: List[Dict[str, str]] = []       # [{namespace, role}] from members()
    account_stats: Dict[str, Any] = {}     # summed catalog_stats over owned namespaces
    profile_message: str = ""

    # --- Publication flow ---
    publish_namespace: str = ""    # target namespace for publishing
    new_namespace: str = ""        # create-namespace input
    ns_available: str = ""         # "" | checking | yes | no | invalid
    publish_state: str = ""        # new | new_version | published_identical | yanked | conflict
    publish_version: str = ""
    published_digest: str = ""
    publish_busy: bool = False
    publish_message: str = ""

    # --- Pre-publish rehearsal (registry 0.11 `/check` and `/validate`) ---
    precheck_busy: bool = False
    precheck_endpoint: str = ""    # "" | check | validate — which half actually ran
    precheck_verdict: str = ""     # "" | pass | fail | blocked | rate_limited | error
    precheck_message: str = ""
    precheck_findings: List[str] = []

    # ------------------------------------------------------------------ helpers

    @rx.var
    def _selected_local(self) -> Dict[str, Any]:
        for m in self.local_modules:
            if m.get("name") == self.selected_name:
                return m
        return {}

    @rx.var
    def has_selection(self) -> bool:
        return self.selected_name != ""

    @rx.var
    def sel_status(self) -> str:
        """State machine for (selected_name, selected_version) vs local + catalog."""
        if not self.selected_name:
            return "none"
        li = self._selected_local
        installed_here = bool(li) and li.get("version", "") == self.selected_version
        remote_here = self.selected_version in self._remote_versions
        if installed_here:
            if li.get("in_catalog"):
                return "installed"
            return "mismatch" if remote_here else "local_only"
        return "not_installed" if remote_here else "not_available"

    @rx.var
    def sel_status_label(self) -> str:
        return {
            "installed": "Installed",
            "mismatch": "Version mismatch",
            "local_only": "Local only",
            "not_installed": "Not installed",
            "not_available": "Not available",
        }.get(self.sel_status, "")

    @rx.var
    def sel_status_color(self) -> str:
        return {
            "installed": "#21ba45",
            "mismatch": "#f2711c",
            "local_only": "#a333c8",
            "not_installed": "#2185d0",
            "not_available": "#767676",
        }.get(self.sel_status, "#767676")

    @rx.var
    def show_download(self) -> bool:
        # Only remote-present + local-absent, per name+version.
        return self.sel_status == "not_installed"

    @rx.var
    def show_local_actions(self) -> bool:
        # Edit/Export/Uninstall/Upload apply when the selected version is the installed one.
        li = self._selected_local
        return bool(li) and li.get("version", "") == self.selected_version

    @rx.var
    def edit_enabled(self) -> bool:
        li = self._selected_local
        return bool(li) and li.get("has_spec", False) and li.get("version", "") == self.selected_version

    @rx.var
    def export_url(self) -> str:
        if not self.selected_name:
            return ""
        return f"{_backend_api_url()}/api/module-zip/{self.selected_name}"

    @rx.var
    def has_pending(self) -> bool:
        return bool(self.pending_action)

    @rx.var
    def pending_warn(self) -> str:
        return self.pending_action.get("warn", "")

    @rx.var
    def can_prev(self) -> bool:
        return self.page > 1

    @rx.var
    def can_next(self) -> bool:
        return self.page * self.per_page < self.total

    # ------------------------------------------------------------------ store

    def _current_store(self) -> RegistryStore:
        """The selected registry server (backend-only; not a Var)."""
        return _resolve_store(self.store_key)

    @rx.var
    def store_label(self) -> str:
        return self._current_store().label

    @rx.var
    def store_url(self) -> str:
        return self._current_store().base_url

    @rx.var
    def store_description(self) -> str:
        return self._current_store().description

    @rx.var
    def store_is_test(self) -> bool:
        """Whether the selected server is a test ground — badged, never inferred by the reader.

        Mirrors ``mode`` from ``/api/v1/version``, taken from the configured store rather than
        fetched: a badge that depends on a network call is absent exactly when the server is slow.
        """
        return self._current_store().is_test

    def _client_args(self):
        return self._current_store().base_url, (self.token or None)

    def _begin_action(self, message: str, busy_key: str = "") -> None:
        """Mark an install/uninstall in progress. Call inside ``async with self``."""
        self.action_busy = True
        self._busy_key = busy_key
        self.action_message = message
        self.cards = _cards_with_installed(list(self.cards), list(self._local_names), busy_key)

    def _end_action(self, message: str) -> None:
        """Clear the in-progress mark. Call inside ``async with self``."""
        self.action_busy = False
        self._busy_key = ""
        self.action_message = message
        self.cards = _cards_with_installed(list(self.cards), list(self._local_names), "")

    def _publish_local_snapshot(self, modules: List[Dict[str, Any]]) -> None:
        """Push a local-registry snapshot to the left list and the browse cards.

        Call inside ``async with self``. Assigns new lists so Reflex sends a delta;
        mutating ``local_modules`` in place would leave the Installed list stale until
        the catalog search returned.
        """
        names = [m["name"] for m in modules]
        self.local_modules = modules
        self._local_names = names
        self.cards = _cards_with_installed(list(self.cards), names, self._busy_key)

    # ------------------------------------------------------------------ setters

    def set_query(self, value: str) -> None:
        self.query = value

    @rx.event(background=True)
    async def switch_registry_tab(self, tab: str):
        # The tab name arrives from the client, so a hidden tab is refused here
        # too — not only left unrendered.
        if tab == "publication" and not REGISTRY_PUBLICATION_ENABLED:
            return
        async with self:
            self.registry_active_tab = tab
        if tab == "publication":
            if self.token:
                await self._refresh_account()
            await self._load_publish_state()

    def set_selected_version(self, version: str) -> None:
        self.selected_version = version

    def cancel_pending(self) -> None:
        self.pending_action = {}

    # ------------------------------------------------------------------ loaders

    async def _refresh_upload_ui(self) -> None:
        """Refresh the annotate-page module list after an install/uninstall.

        Must acquire the state context: in a background task, ``get_state`` on another state is
        only valid inside ``async with self`` (StateProxy is immutable otherwise).
        """
        async with self:
            upload_state = await self.get_state(UploadState)
            upload_state._refresh_module_ui_state()

    async def _refresh_local(self) -> None:
        """Rescan local registry and classify each module against the catalog.

        Signature first, digest only as a fallback. The registry gates 409 duplicate_content on
        the authored-content signature, so that is what predicts a rejected publish; the artifact
        digest changes on every recompile and would report a merely-rebuilt module as unpublished.
        Modules with no spec CSVs (compiled-only imports) have no signature and keep the digest
        route. Both lookups are batched, so this stays at most two requests for the whole corpus.
        """
        async with self:
            url, token = self._client_args()
        loop = asyncio.get_event_loop()
        local = await loop.run_in_executor(None, _scan_local_modules)
        signatures = [m["signature"] for m in local if m.get("signature")]
        digests = [m["digest"] for m in local if m["digest"] and not m.get("signature")]
        sig_matches: Dict[str, list] = {}
        matches: Dict[str, list] = {}
        if signatures or digests:
            def _lookup():
                with RegistryClient(url, token) as c:
                    sigs = c.lookup_by_signatures(signatures) if signatures else {}
                    digs = c.lookup_by_digests(digests) if digests else {}
                    return sigs, digs
            try:
                sig_matches, matches = await loop.run_in_executor(None, _lookup)
            except Exception:  # noqa: BLE001 - offline classification degrades to local-only
                sig_matches, matches = {}, {}
        for m in local:
            # lookup_by_signatures returns VersionRef models; lookup_by_digests returns dicts.
            ms = list(sig_matches.get(m.get("signature", ""), []) or []) if m.get("signature") else []
            by_signature = bool(ms)
            if not ms:
                ms = matches.get(m["digest"]) or []
            m["in_catalog"] = bool(ms)
            if ms:
                # Content matched the catalog — backfill identity the local copy is missing
                # (covers metadata-stripped imports shared peer-to-peer).
                best = ms[0]
                get = (lambda k, d="": getattr(best, k, d)) if by_signature else (lambda k, d="": best.get(k, d))
                if not m["namespace"]:
                    m["namespace"] = get("namespace")
                if not m["version"]:
                    m["version"] = get("version")
                m["catalog_name"] = get("name", m["name"]) or m["name"]
        async with self:
            self._publish_local_snapshot(local)

    async def _do_search(self) -> None:
        async with self:
            self.catalog_loading = True
            self.catalog_error = ""
            q, sort, page, per_page = self.query, self.sort, self.page, self.per_page
            group = self.group_filter
            ns_filter = self.namespace_filter
            url, token = self._client_args()
            local_names = list(self._local_names)
        loop = asyncio.get_event_loop()

        def _list():
            # Reads are contract-tolerant, so we do NOT gate them on the version guard: a flaky
            # or unwired `/version` (502/404) must never block browsing. The compatibility guard
            # is applied only where it matters — installing an artifact (see `_do_install`).
            with RegistryClient(url, token) as c:
                return c.list_modules(
                    q=(q or None), sort=sort, group=(group or None),
                    namespace=(ns_filter or None), page=page, per_page=per_page,
                )

        try:
            body = await loop.run_in_executor(None, _list)
        except VersionMismatchError as e:
            async with self:
                self.catalog_loading = False
                self.server_incompatible = True
                self.catalog_error = f"{_REGISTRY_MISMATCH_HINT} ({e.detail})"
                self.cards = []
                self.total = 0
            return
        except Exception as e:  # noqa: BLE001 - surface a message, don't crash the page
            async with self:
                self.catalog_loading = False
                self.catalog_error = f"Could not reach the registry: {e}"
                self.cards = []
                self.total = 0
            return
        items = body.get("items", []) or []
        for card in items:
            stats = card.get("stats") or {}
            card["variant_count"] = int(stats.get("variant_count") or 0)
            card["gene_count"] = int(stats.get("gene_count") or 0)
            card["clinvar_count"] = int(stats.get("clinvar_count") or 0)
            card["pathogenic_count"] = int(stats.get("pathogenic_count") or 0)
            # Server-relative logo → absolute URL for the browser (schema 0.3.0 surfacing).
            logo = card.get("logo_url") or ""
            card["logo_full"] = (url + logo) if logo.startswith("/") else logo
        async with self:
            self.cards = _cards_with_installed(items, local_names, self._busy_key)
            self.total = int(body.get("total", 0) or 0)
            # Grow the namespace filter options from whatever we've seen (only when unfiltered,
            # so the option set stays complete rather than collapsing to the active filter).
            if not ns_filter:
                seen = set(self.namespace_options) | {c.get("namespace", "") for c in items}
                self.namespace_options = sorted(n for n in seen if n)
            self.server_incompatible = False
            self.catalog_loading = False

    async def _ensure_identity(self) -> None:
        """Load (or mint + persist) the publishing identity for the *selected* store.

        The profile is per server: an account, its token and its namespaces are minted by one
        registry and mean nothing to another, so switching stores loads a different slot rather
        than carrying the old account across. The install-id is machine-local and shared.
        """
        async with self:
            store = self._current_store()
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, load_store_identity, store.key)
        # The slot is the only source. `$REGISTRY_TOKEN` is deliberately *not* read as a
        # fallback: it is the CLI's publishing credential, so honouring it would sign the UI in
        # as that account with no user action — and `_refresh_account` persists whatever it finds,
        # which would leave a second copy of the token shadowing `.env` on every later read.
        token = data.get("token", "")
        account = data.get("account", "")
        namespaces = data.get("namespaces", []) or []
        display_name = data.get("display_name", "")
        email = data.get("email", "")
        avatar_local = data.get("avatar_local", "")
        install_id = await loop.run_in_executor(None, ensure_install_id)  # ~1s proof-of-work
        async with self:
            self.install_id = install_id
            self.token = token
            self.account = account
            self.namespaces = namespaces
            self.display_name = display_name
            self.email = email
            self.avatar_local = avatar_local
            if namespaces and not self.publish_namespace:
                self.publish_namespace = namespaces[0]

    def _persist_identity(self) -> None:
        """Write the profile back to the selected store's slot (call inside a sync context)."""
        save_store_identity(self._current_store().key, {
            "token": self.token, "account": self.account,
            "namespaces": list(self.namespaces), "display_name": self.display_name,
            "email": self.email, "avatar_local": self.avatar_local,
        })

    @rx.event(background=True)
    async def load_registry(self):
        async with self:
            if not self.store_key:
                self.store_key = default_registry_store().key
        await self._ensure_identity()
        await self._refresh_local()
        await self._do_search()
        if self.token:
            await self._refresh_account()

    @rx.event(background=True)
    async def set_store(self, key: str):
        """Point the whole page at another registry server.

        Everything on screen belongs to one server — the catalog, the selected module's versions,
        the account and its namespaces, and the publish rehearsal — so all of it is cleared before
        the same load sequence runs again. Reusing ``load_registry`` rather than writing a second
        loader is deliberate: a parallel path is how one of these panes ends up showing the
        previous server's answer.
        """
        store = _resolve_store(key)
        async with self:
            if store.key == self.store_key:
                return
            self.store_key = store.key
            self._reset_for_store_switch()
        yield RegistryState.load_registry

    def _reset_for_store_switch(self) -> None:
        """Drop every var that belongs to the previous server. Call inside ``async with self``."""
        # Catalog
        self.cards = []
        self.total = 0
        self.page = 1
        self.namespace_options = []
        self.namespace_filter = ""
        self.catalog_error = ""
        self.server_incompatible = False
        # Selection (a version list from one server does not describe another's module)
        self.selected_name = ""
        self.selected_catalog_name = ""
        self.selected_namespace = ""
        self.selected_versions = []
        self.selected_version = ""
        self._remote_versions = []
        self._remote_digests = {}
        self._remote_trust = {}
        self.detail_error = ""
        self.pending_action = {}
        self.action_message = ""
        # Account + publication
        self.token = ""
        self.account = ""
        self.namespaces = []
        self.roles = []
        self.account_stats = {}
        self.profile_message = ""
        self.publish_namespace = ""
        self.new_namespace = ""
        self.ns_available = ""
        self.publish_state = ""
        self.publish_version = ""
        self.published_digest = ""
        self.publish_message = ""
        self.precheck_endpoint = ""
        self.precheck_verdict = ""
        self.precheck_message = ""
        self.precheck_findings = []

    @rx.event(background=True)
    async def search(self):
        async with self:
            self.page = 1
        await self._do_search()

    @rx.event(background=True)
    async def set_sort(self, value: str):
        async with self:
            self.sort = value
            self.page = 1
        await self._do_search()

    @rx.event(background=True)
    async def set_group_filter(self, value: str):
        async with self:
            self.group_filter = value
            self.page = 1
        await self._do_search()

    @rx.event(background=True)
    async def set_namespace_filter(self, value: str):
        async with self:
            self.namespace_filter = value
            self.page = 1
        await self._do_search()

    @rx.event(background=True)
    async def next_page(self):
        async with self:
            if not (self.page * self.per_page < self.total):
                return
            self.page += 1
        await self._do_search()

    @rx.event(background=True)
    async def prev_page(self):
        async with self:
            if self.page <= 1:
                return
            self.page -= 1
        await self._do_search()

    # ------------------------------------------------------------------ selection

    async def _load_detail(self, namespace: str, name: str, registry_name: str = "") -> None:
        # `name` is the catalog name used for the API; `registry_name` (if given) is the local
        # registry key the selection should track (they differ for peer-shared imports).
        selection_key = registry_name or name
        async with self:
            self.detail_loading = True
            self.detail_error = ""
            url, token = self._client_args()
            li = next((m for m in self.local_modules if m.get("name") == selection_key), {})
            installed_version = li.get("version", "")
        loop = asyncio.get_event_loop()

        def _detail():
            with RegistryClient(url, token) as c:
                return c.get_module(namespace, name)

        try:
            detail = await loop.run_in_executor(None, _detail)
        except VersionMismatchError as e:
            async with self:
                self.detail_loading = False
                self.server_incompatible = True
                self.detail_error = f"{_REGISTRY_MISMATCH_HINT} ({e.detail})"
            return
        except Exception as e:  # noqa: BLE001
            async with self:
                self.detail_loading = False
                self.detail_error = f"Could not load details: {e}"
            return
        versions = detail.get("versions", []) or []
        # Only offer versions that match the current schema/compiler contract. The live catalog
        # holds a mix; the `revalidate` audit sets `needs_upgrade=True` on stale ones (which show
        # up as the un-bumped `x.y.0` releases), and re-published ones clear it. Filtering here
        # keeps the version dropdown to installable, current-schema releases.
        compatible = [v for v in versions if v.get("version") and not v.get("needs_upgrade", False)]
        remote_versions = [v.get("version") for v in compatible]
        remote_digests = {v.get("version"): (v.get("artifact_digest") or "") for v in compatible}
        # Trust is per *version*, not per module: it describes how that build's variants were
        # pinned to the genome, so a module can hold a trusted release and an untrusted one.
        remote_trust = {
            v.get("version"): _trust_word((v.get("resolution") or {}).get("trusted"))
            for v in compatible
        }
        stats = detail.get("stats") or {}
        union = list(remote_versions)
        if installed_version and installed_version not in union:
            union.append(installed_version)  # always keep what's actually installed selectable
        # Default to the newest compatible version (catalog `latest_version` may be a stale one).
        latest_compatible = remote_versions[0] if remote_versions else ""
        default_v = installed_version if installed_version in union else latest_compatible
        async with self:
            self.selected_name = selection_key
            self.selected_catalog_name = name
            self.selected_namespace = namespace
            self.selected_title = detail.get("title") or name
            self.selected_description = detail.get("description") or ""
            self.selected_author = detail.get("owner") or ""
            self.selected_icon = detail.get("icon") or "database"
            self.selected_color = detail.get("color") or "#6435c9"
            self.selected_variant_count = int(stats.get("variant_count") or 0)
            self.selected_gene_count = int(stats.get("gene_count") or 0)
            self.selected_clinvar_count = int(stats.get("clinvar_count") or 0)
            self.selected_pathogenic_count = int(stats.get("pathogenic_count") or 0)
            self.selected_benign_count = int(stats.get("benign_count") or 0)
            logo = detail.get("logo_url") or ""
            self.selected_logo_url = (url + logo) if logo.startswith("/") else logo
            self._remote_versions = remote_versions
            self._remote_digests = remote_digests
            self._remote_trust = remote_trust
            self.selected_versions = union
            self.selected_version = default_v
            self.detail_loading = False

    @rx.event(background=True)
    async def select_catalog(self, namespace: str, name: str):
        # Track selection under the namespaced local key so status/install line up whether or not
        # it's installed (an installed copy lives at CUSTOM_MODULES_DIR/{namespace}__{name}).
        await self._load_detail(namespace, name, registry_name=_local_key(namespace, name))

    @rx.event(background=True)
    async def select_local(self, name: str):
        async with self:
            li = next((m for m in self.local_modules if m.get("name") == name), {})
            namespace = li.get("namespace", "")
            catalog_name = li.get("catalog_name", name)
        if namespace:
            await self._load_detail(namespace, catalog_name, registry_name=name)
            return
        async with self:
            self.selected_name = name
            self.selected_catalog_name = li.get("catalog_name", name)
            self.selected_namespace = ""
            self.selected_title = li.get("title", name)
            self.selected_description = ""
            self.selected_author = ""
            self.selected_icon = li.get("icon", "database")
            self.selected_color = li.get("color", "#6435c9")
            self.selected_logo_url = ""
            self.selected_variant_count = 0
            self.selected_gene_count = 0
            self.selected_clinvar_count = 0
            self.selected_pathogenic_count = 0
            self.selected_benign_count = 0
            version = li.get("version", "")
            self.selected_version = version
            self.selected_versions = [version] if version else []
            self._remote_versions = []
            self._remote_digests = {}

    # ------------------------------------------------------------------ install

    async def _do_install(self, namespace: str, name: str, version: str) -> None:
        # `name` is the catalog module name; the local install lives under a namespaced key so it
        # never collides with a same-named HF module or another namespace's module.
        key = _local_key(namespace, name)
        async with self:
            if self.action_busy:
                return
            self._begin_action(f"Downloading {name} {version}…", busy_key=key)
            url, token = self._client_args()
        loop = asyncio.get_event_loop()

        def _install():
            dest = CUSTOM_MODULES_DIR / key
            with tempfile.TemporaryDirectory() as td:
                tarball = Path(td) / f"{key}.tar.gz"
                with RegistryClient(url, token) as c:
                    # get_tarball does not self-guard (unlike download/publish), so check first:
                    # a format/compiler mismatch would otherwise yield an unusable artifact.
                    # Only a genuine mismatch blocks; a flaky/unwired /version (5xx/404) must not —
                    # let the download itself surface any real transport error.
                    try:
                        c.assert_compatible()
                    except VersionMismatchError:
                        raise
                    except RegistryError:
                        pass
                    c.get_tarball(namespace, name, version, tarball)
                if dest.exists():
                    shutil.rmtree(dest)
                dest.mkdir(parents=True, exist_ok=True)
                with tarfile.open(tarball, "r:gz") as tf:
                    tf.extractall(dest, filter="data")
            register_downloaded_module(dest)

        try:
            await loop.run_in_executor(None, _install)
        except VersionMismatchError as e:
            async with self:
                self.server_incompatible = True
                self._end_action(f"{_REGISTRY_MISMATCH_HINT} ({e.detail})")
            return
        except Exception as e:  # noqa: BLE001
            async with self:
                self._end_action(f"Install failed: {e}")
            return
        await self._refresh_local()
        await self._refresh_upload_ui()
        async with self:
            self._end_action(f"Installed {name} {version}.")

    @rx.event(background=True)
    async def request_download(self):
        async with self:
            key = self.selected_name                       # local registry key
            catalog_name = self.selected_catalog_name      # name for the API
            ns = self.selected_namespace
            version = self.selected_version
            li = next((m for m in self.local_modules if m.get("name") == key), {})
            installed_v = li.get("version", "")
            unmirrored = bool(li) and not li.get("in_catalog", False)
        if li and installed_v and installed_v != version and unmirrored:
            async with self:
                self.pending_action = {
                    "kind": "download", "name": catalog_name, "namespace": ns, "version": version,
                    "warn": (f"Installing {catalog_name} {version} will replace your local copy of "
                             f"{installed_v}, which has no matching catalog copy to restore."),
                }
            return
        await self._do_install(ns, catalog_name, version)

    @rx.event(background=True)
    async def quick_install(self, namespace: str, name: str, version: str):
        async with self:
            already = _local_key(namespace, name) in {m.get("name") for m in self.local_modules}
        if already:
            return
        await self._do_install(namespace, name, version)
        # Land the freshly-installed module in the left details pane (under its namespaced key).
        await self._load_detail(namespace, name, registry_name=_local_key(namespace, name))

    # ------------------------------------------------------------------ uninstall

    async def _do_uninstall(self, name: str) -> None:
        async with self:
            if self.action_busy:
                return
            # Drop the row now — unregister + catalog classification can take seconds
            # (artifact hashing, HF rediscovery, signature lookup) and used to leave
            # the Installed list frozen until all of that finished.
            self._begin_action(f"Uninstalling {name}…")
            self._publish_local_snapshot(_without_local_module(list(self.local_modules), name))
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, unregister_custom_module, name)
        except Exception as e:  # noqa: BLE001
            await self._refresh_local()
            async with self:
                self._end_action(f"Uninstall failed: {e}")
            return
        await self._refresh_local()
        await self._refresh_upload_ui()
        async with self:
            self._end_action(f"Uninstalled {name}.")

    @rx.event(background=True)
    async def request_uninstall(self):
        async with self:
            name = self.selected_name
            gate = self.sel_status in ("local_only", "mismatch")
        if gate:
            async with self:
                self.pending_action = {
                    "kind": "uninstall", "name": name,
                    "warn": (f"Uninstalling {name} removes it permanently — it has no matching "
                             f"catalog copy to reinstall."),
                }
            return
        await self._do_uninstall(name)

    # ------------------------------------------------------------------ import / upload

    async def _do_register_temp(self, spec_dir: str) -> None:
        async with self:
            self._begin_action("Importing module…")
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(None, register_custom_module, Path(spec_dir))
        except Exception as e:  # noqa: BLE001
            async with self:
                self._end_action(f"Import failed: {e}")
            return
        ok = getattr(result, "success", False)
        errs = "; ".join(getattr(result, "errors", []) or [])
        await self._refresh_local()
        await self._refresh_upload_ui()
        async with self:
            self._end_action("Imported module." if ok else f"Import failed: {errs}")

    @rx.event
    async def upload_import(self, files: list[rx.UploadFile]):
        """Persist uploaded spec files, decide gating, then chain to the background importer.

        Upload handlers cannot be ``background=True``, so this only does the quick file save +
        gate decision; the heavy compile happens in ``start_import``.
        """
        tmp = Path(tempfile.mkdtemp(prefix="mp_import_"))
        for f in files:
            data = await f.read()
            (tmp / Path(f.filename).name).write_bytes(data)
        zips = list(tmp.glob("*.zip"))
        if len(zips) == 1 and len(list(tmp.iterdir())) == 1:
            with zipfile.ZipFile(zips[0]) as zf:
                zf.extractall(tmp)
            zips[0].unlink()
        spec_dir = tmp
        if not (spec_dir / "module_spec.yaml").exists():
            subs = [d for d in tmp.iterdir() if d.is_dir() and (d / "module_spec.yaml").exists()]
            if subs:
                spec_dir = subs[0]
        if not (spec_dir / "module_spec.yaml").exists():
            self.action_message = "Import needs module_spec.yaml (+ variants.csv), or a .zip containing them."
            return
        raw = yaml.safe_load((spec_dir / "module_spec.yaml").read_text(encoding="utf-8")) or {}
        name = ((raw.get("module") or {}).get("name")) or ""
        li = next((m for m in self.local_modules if m.get("name") == name), {})
        unmirrored = bool(li) and not li.get("in_catalog", False)
        if unmirrored:
            self.pending_action = {
                "kind": "upload", "name": name, "spec_dir": str(spec_dir),
                "warn": (f"Importing will overwrite your installed {name}, which has no "
                         f"matching catalog copy to restore."),
            }
            return
        return RegistryState.start_import(str(spec_dir))

    @rx.event(background=True)
    async def start_import(self, spec_dir: str):
        await self._do_register_temp(spec_dir)

    # ------------------------------------------------------------------ gating dispatch

    @rx.event(background=True)
    async def confirm_pending(self):
        async with self:
            pa = dict(self.pending_action)
            self.pending_action = {}
        kind = pa.get("kind")
        if kind == "uninstall":
            await self._do_uninstall(pa["name"])
        elif kind == "download":
            await self._do_install(pa["namespace"], pa["name"], pa["version"])
        elif kind == "upload":
            await self._do_register_temp(pa["spec_dir"])

    # ================================================================== publication
    # ---- computed ----
    @rx.var
    def is_registered(self) -> bool:
        return bool(self.token) and bool(self.account)

    @rx.var
    def display_name_valid(self) -> bool:
        return bool(_DISPLAY_NAME_RE.match(self.display_name or ""))

    @rx.var
    def namespaces_full(self) -> bool:
        return len(self.namespaces) >= 5

    @rx.var
    def can_create_namespace(self) -> bool:
        return (
            self.display_name_valid
            and is_valid_namespace((self.new_namespace or "").strip().lower())
            and len(self.namespaces) < 5
        )

    @rx.var
    def token_masked(self) -> str:
        t = self.token or ""
        return (t[:8] + "…" + t[-4:]) if len(t) > 16 else ("•" * len(t))

    @rx.var
    def publish_has_spec(self) -> bool:
        li = self._selected_local
        return bool(li) and li.get("has_spec", False)

    @rx.var
    def selected_in_catalog(self) -> bool:
        """Whether the selected module's content already exists in the catalog.

        Set by ``_refresh_local``, which matches on ``content_signature`` (the authored-data
        identity the registry actually gates 409 ``duplicate_content`` on) and falls back to the
        artifact digest only for compiled-only imports that carry no spec. This lets us pre-empt
        the rejection instead of offering a Publish button the server refuses.
        """
        return bool(self._selected_local.get("in_catalog", False))

    @rx.var
    def selected_catalog_ref(self) -> str:
        """``namespace/name@version`` of the catalog match for the selected module (else "")."""
        li = self._selected_local
        if not li.get("in_catalog", False):
            return ""
        ns, name, ver = li.get("namespace", ""), li.get("catalog_name", ""), li.get("version", "")
        return f"{ns}/{name}@{ver}" if ns and name else ""

    @rx.var
    def selected_trusted(self) -> str:
        """Trust of the *selected version*: ``yes`` | ``no`` | ``unknown``.

        ``unknown`` also covers a locally-installed version that the catalog does not list, which
        is why this reads the map rather than defaulting to a bool.
        """
        return self._remote_trust.get(self.selected_version, "unknown")

    @rx.var
    def selected_trust_hint(self) -> str:
        """Why the selected version carries that trust, in the terms the registry means it."""
        word = self.selected_trusted
        if word == "yes":
            return "Variants are pinned to genome coordinates, so this joins to a VCF by position."
        if word == "no":
            return (
                "This build's table has no coordinates — it joins on rsID and genotype only, so a "
                "VCF without rsIDs in its ID column will match nothing. Published as untrusted "
                "deliberately; it is not a defect."
            )
        return "The catalog did not report a trust level for this version."

    @rx.var
    def can_publish(self) -> bool:
        # Content already in the catalog can't be republished (the server rejects it as
        # duplicate_content); don't offer the button for it.
        return (
            self.publish_state in ("new", "new_version")
            and self.publish_has_spec
            and not self.selected_in_catalog
        )

    @rx.var
    def publish_is_published(self) -> bool:
        return self.publish_state in ("published_identical", "yanked", "conflict")

    @rx.var
    def show_yank(self) -> bool:
        return self.publish_state == "published_identical"

    @rx.var
    def show_unyank(self) -> bool:
        return self.publish_state == "yanked"

    @rx.var
    def can_update_meta(self) -> bool:
        return self.publish_state in ("published_identical", "yanked")

    token_revealed: bool = False

    # ---- setters ----
    def set_new_namespace(self, value: str) -> None:
        self.new_namespace = value
        # Live client-side check so the hint shows while typing; on_blur then checks availability.
        norm = (value or "").strip().lower()
        self.ns_available = "invalid" if norm and not is_valid_namespace(norm) else ""

    def toggle_token(self) -> None:
        self.token_revealed = not self.token_revealed

    @rx.var
    def token_display(self) -> str:
        return self.token if self.token_revealed else self.token_masked

    @rx.event
    async def set_avatar(self, files: list[rx.UploadFile]):
        """Store a local-only avatar as a data URI (never uploaded to the server)."""
        if not files:
            return
        f = files[0]
        data = await f.read()
        mime = "image/png" if str(f.filename).lower().endswith("png") else "image/jpeg"
        self.avatar_local = f"data:{mime};base64,{base64.b64encode(data).decode()}"
        self._persist_identity()

    # ---- profile ----
    @rx.event
    def save_profile(self, form_data: dict):
        name = (form_data.get("display_name") or "").strip()
        email = (form_data.get("email") or "").strip()
        if not _DISPLAY_NAME_RE.match(name):
            self.profile_message = "Display name must be 2–32 chars: letters, digits, or underscore only."
            return
        self.display_name = name
        self.email = email
        self._persist_identity()
        self.profile_message = "Saved."
        if self.token:
            return RegistryState.push_profile

    @rx.event(background=True)
    async def push_profile(self):
        async with self:
            url, token = self._client_args()
            display_name, email = self.display_name, self.email
        loop = asyncio.get_event_loop()

        def _do():
            with RegistryClient(url, token) as c:
                return c.update_profile(display_name=display_name, email=email)

        try:
            await loop.run_in_executor(None, _do)
        except Exception as e:  # noqa: BLE001
            async with self:
                self.profile_message = f"Saved locally; server profile update failed: {e}"
            return
        async with self:
            self.profile_message = "Profile updated."

    # ---- namespace availability + creation ----
    @rx.event(background=True)
    async def check_namespace(self):
        """Check availability of the current `new_namespace` (reads state; on_blur triggers it)."""
        async with self:
            value = (self.new_namespace or "").strip().lower()
            self.new_namespace = value
            if not value:
                self.ns_available = ""
                return
            self.ns_available = "checking"
            url, token = self._client_args()
        loop = asyncio.get_event_loop()

        def _do():
            with RegistryClient(url, token) as c:
                return c.namespace_available(value)

        try:
            res = await loop.run_in_executor(None, _do)
        except Exception:  # noqa: BLE001
            async with self:
                self.ns_available = ""
            return
        async with self:
            if not res.get("valid", False):
                self.ns_available = "invalid"
            else:
                self.ns_available = "yes" if res.get("available", False) else "no"

    @rx.event
    def create_namespace(self, form_data: dict):
        ns = (form_data.get("new_namespace") or "").strip().lower()
        if not self.display_name_valid:
            self.publish_message = "Set a valid display name in the account pane first."
            return
        if not ns:
            self.publish_message = "Enter a namespace name."
            return
        if len(self.namespaces) >= 5:
            self.publish_message = "Namespace limit reached (5 per account)."
            return
        return RegistryState.do_create_namespace(ns)

    @rx.event(background=True)
    async def do_create_namespace(self, ns: str):
        async with self:
            self.publish_busy = True
            self.publish_message = f"Creating namespace {ns}…"
            url, token = self._client_args()
            install_id, display_name = self.install_id, self.display_name
        loop = asyncio.get_event_loop()

        # 1. Register the account (mint token) if this is the first namespace.
        if not token:
            def _register():
                last = None
                with RegistryClient(url, None) as c:
                    for _ in range(6):
                        handle = derive_handle(display_name)
                        try:
                            return c.register(install_id, handle)
                        except RegistryError as e:
                            if e.status_code == 409:  # handle collision → new suffix
                                last = e
                                continue
                            raise
                raise last or RuntimeError("could not register account")
            try:
                reg = await loop.run_in_executor(None, _register)
            except Exception as e:  # noqa: BLE001
                async with self:
                    self.publish_busy = False
                    self.publish_message = f"Registration failed: {e}"
                return
            async with self:
                self.token = reg.get("token", "")
                self.account = reg.get("account", "")
                self.namespaces = reg.get("namespaces", []) or []
                token = self.token
                # Mirror the token under *this store's* variable, never a shared one. A test
                # server's token in `REGISTRY_TOKEN` has broken publishing here before, and it
                # does not surface as anything auth-shaped: the public server answers
                # `403 insufficient_capability`, which reads as a namespace-permissions bug.
                token_env = self._current_store().token_env
                self._persist_identity()
            if token and token_env:
                await loop.run_in_executor(None, set_env_var, token_env, token)

        # 2. Claim the namespace.
        def _claim():
            with RegistryClient(url, token) as c:
                avail = c.namespace_available(ns)
                if not avail.get("valid", False):
                    raise RuntimeError("invalid namespace name")
                if not avail.get("available", False):
                    raise RuntimeError("namespace already taken")
                return c.claim_namespace(ns)

        try:
            await loop.run_in_executor(None, _claim)
        except RegistryError as e:
            async with self:
                self.publish_busy = False
                self.publish_message = (
                    "Namespace limit reached (5 per account)."
                    if e.status_code == 403 else f"Could not claim namespace: {e.detail}"
                )
            return
        except Exception as e:  # noqa: BLE001
            async with self:
                self.publish_busy = False
                self.publish_message = f"Could not claim namespace: {e}"
            return
        async with self:
            if ns not in self.namespaces:
                self.namespaces = self.namespaces + [ns]
            self.publish_namespace = ns
            self.new_namespace = ""
            self.ns_available = ""
            self._persist_identity()
            self.publish_busy = False
            self.publish_message = f"Created namespace {ns}."
        await self._refresh_account()
        await self._load_publish_state()

    @rx.event(background=True)
    async def set_publish_namespace(self, value: str):
        async with self:
            self.publish_namespace = value
        await self._load_publish_state()

    # ---- publish state machine ----
    async def _load_publish_state(self) -> None:
        async with self:
            ns = self.publish_namespace
            li = self._selected_local
            catalog_name = li.get("catalog_name", "") if li else ""
            local_version = li.get("version", "") if li else ""
            local_digest = li.get("digest", "") if li else ""
            url, token = self._client_args()
        if not (ns and catalog_name and li):
            async with self:
                self.publish_state = ""
                self.published_digest = ""
                self.publish_version = local_version
            return
        loop = asyncio.get_event_loop()

        def _versions():
            with RegistryClient(url, token) as c:
                try:
                    return c.versions(ns, catalog_name).get("items", [])
                except RegistryError as e:
                    if e.status_code == 404:
                        return []
                    raise

        try:
            vers = await loop.run_in_executor(None, _versions)
        except Exception:  # noqa: BLE001 - unknown; leave state blank
            async with self:
                self.publish_state = ""
                self.publish_version = local_version
            return
        match = next((v for v in vers if v.get("version") == local_version), None)
        async with self:
            self.publish_version = local_version
            if match is None:
                self.publish_state = "new_version" if vers else "new"
                self.published_digest = ""
            else:
                self.published_digest = match.get("artifact_digest", "")
                if match.get("yanked", False):
                    self.publish_state = "yanked"
                elif self.published_digest == local_digest:
                    self.publish_state = "published_identical"
                else:
                    self.publish_state = "conflict"

    @rx.event(background=True)
    async def precheck_selected(self):
        """Rehearse the publish server-side before uploading anything.

        Which endpoint runs is decided here rather than left to the user, because the choice is
        mechanical: `/check` is the full dry run (validation plus the server's network tier) but its
        enrichment half is capped at `_ENRICH_MAX_VARIANTS`, and a module over that answers
        `422 too_many_variants`. `/validate` has no network tier and is the half that decides
        publishability, so it is both the fallback and the right answer for a large module. A spec
        too large to send as loose parts is packed — before client/server 0.11.1 there was no
        archive form at all, so a big module could be published but never rehearsed.
        """
        async with self:
            ns = self.publish_namespace
            li = self._selected_local
            key = li.get("name", "") if li else ""
            catalog_name = li.get("catalog_name", "") if li else ""
            has_spec = li.get("has_spec", False) if li else False
            url, token = self._client_args()
        if not (ns and catalog_name):
            return
        if not has_spec:
            async with self:
                self.precheck_verdict = "error"
                self.precheck_message = "This module has no spec files to check."
                self.precheck_findings = []
            return

        spec_dir = CUSTOM_MODULES_DIR / key
        async with self:
            self.precheck_busy = True
            self.precheck_verdict = ""
            self.precheck_findings = []
            self.precheck_endpoint = ""
            self.precheck_message = f"Checking {catalog_name} against {ns}…"

        loop = asyncio.get_event_loop()

        def _run() -> tuple[str, Any]:
            rows = _authored_row_count(spec_dir)
            pack = _spec_bytes(spec_dir) > _PACK_ABOVE_BYTES
            with RegistryClient(url, token) as c:
                if rows <= _ENRICH_MAX_VARIANTS:
                    try:
                        return "check", c.check(ns, catalog_name, spec_dir, pack=pack)
                    except RegistryError as exc:
                        # Only the size ceiling is worth downgrading for; anything else is a real
                        # answer and belongs to the caller.
                        if not (exc.status_code == 422 and "too_many_variants" in str(exc.detail)):
                            raise
                return "validate", c.validate(ns, catalog_name, spec_dir, pack=pack)

        try:
            endpoint, report = await loop.run_in_executor(None, _run)
        except VersionMismatchError as e:
            async with self:
                self.precheck_busy = False
                self.server_incompatible = True
                self.precheck_verdict = "error"
                self.precheck_message = f"{_REGISTRY_MISMATCH_HINT} ({e.detail})"
            return
        except RegistryError as e:
            async with self:
                self.precheck_busy = False
                self.precheck_findings = []
                if e.status_code == 429:
                    # The rate limiter says "not yet" — emphatically not "would not publish".
                    self.precheck_verdict = "rate_limited"
                    self.precheck_message = (
                        "The check endpoint is rate limited right now. This says nothing about "
                        "whether the module would publish — try again in a minute."
                    )
                elif e.status_code == 403:
                    self.precheck_verdict = "blocked"
                    self.precheck_message = (
                        f"Your token does not own the namespace {ns}, so the server refused the "
                        f"check. This reads like a spec problem and is not one. ({e.detail})"
                    )
                elif e.status_code == 413:
                    self.precheck_verdict = "blocked"
                    self.precheck_message = f"Spec is too large for the server to accept: {e.detail}"
                else:
                    self.precheck_verdict = "error"
                    self.precheck_message = f"Check failed: {e.detail}"
            return
        except Exception as e:  # noqa: BLE001
            async with self:
                self.precheck_busy = False
                self.precheck_verdict = "error"
                self.precheck_message = f"Check failed: {e}"
            return

        # A CheckReport wraps the ValidationReport; a ValidationReport is its own validation half.
        validation = getattr(report, "validation", report)
        passed = bool(report.would_publish) if endpoint == "check" else bool(validation.valid)
        findings: List[str] = []
        for level in ("errors", "warnings"):
            entries = list(getattr(validation, level, []) or [])
            for entry in entries[:5]:
                findings.append(f"{level[:-1]}: {str(entry)[:220]}")
            if len(entries) > 5:
                findings.append(f"… and {len(entries) - 5} more {level}")

        stats = getattr(validation, "stats", None)
        counts = ""
        if stats is not None:
            counts = (
                f" — {getattr(stats, 'variant_count', 0):,} variants, "
                f"{getattr(stats, 'study_count', 0):,} studies, "
                f"{getattr(stats, 'gene_count', 0):,} genes"
            )
        skipped = getattr(report, "skipped_reason", "") if endpoint == "check" else ""

        async with self:
            self.precheck_busy = False
            self.precheck_endpoint = endpoint
            self.precheck_verdict = "pass" if passed else "fail"
            verb = "would publish" if endpoint == "check" else "validates"
            if passed:
                self.precheck_message = f"{catalog_name} {verb}{counts}."
            else:
                self.precheck_message = f"{catalog_name} would be rejected{counts}."
            if endpoint == "validate":
                self.precheck_message += (
                    " Validation tier only — this module is over the server's enrichment limit, "
                    "so the network passes did not run."
                )
            if skipped:
                self.precheck_message += f" Enrichment skipped: {skipped}."
            self.precheck_findings = findings

    @rx.event(background=True)
    async def publish_selected(self):
        async with self:
            ns = self.publish_namespace
            li = self._selected_local
            key = li.get("name", "") if li else ""
            catalog_name = li.get("catalog_name", "") if li else ""
            version = li.get("version", "") if li else ""
            has_spec = li.get("has_spec", False) if li else False
            url, token = self._client_args()
        if not (ns and catalog_name and version):
            return
        if not has_spec:
            async with self:
                self.publish_message = "This module has no spec files to publish."
            return
        async with self:
            self.publish_busy = True
            self.publish_message = f"Publishing {catalog_name} {version} to {ns}…"
        loop = asyncio.get_event_loop()

        def _pub():
            with RegistryClient(url, token) as c:
                return c.publish(ns, catalog_name, version, CUSTOM_MODULES_DIR / key, changelog="")

        try:
            manifest = await loop.run_in_executor(None, _pub)
        except VersionMismatchError as e:
            async with self:
                self.publish_busy = False
                self.server_incompatible = True
                self.publish_message = f"{_REGISTRY_MISMATCH_HINT} ({e.detail})"
            return
        except RegistryError as e:
            async with self:
                self.publish_busy = False
                # The registry uses 409 for both "this version number is taken" and "this exact
                # data is already published (possibly under another name)". Surface the difference.
                if e.status_code == 409 and "duplicate_content" in str(e.detail):
                    self.publish_message = f"Not published: {e.detail}"
                elif e.status_code == 409:
                    self.publish_message = (
                        f"Version {version} already exists in {ns} — bump the version (Edit) to publish changes."
                    )
                else:
                    self.publish_message = f"Publish failed: {e.detail}"
            return
        except Exception as e:  # noqa: BLE001
            async with self:
                self.publish_busy = False
                self.publish_message = f"Publish failed: {e}"
            return
        # The server recompiles the uploaded spec with its pinned Ensembl reference, so the
        # published artifact digest can legitimately differ from our locally-compiled bytes (e.g.
        # when the local Ensembl cache was incomplete). We just published this spec, so trust the
        # server's returned manifest as authoritative rather than recomputing a local-vs-server
        # "conflict" (which would falsely tell the user their fresh publish differs).
        server_digest = manifest.artifact.digest if manifest and manifest.artifact else ""
        local_digest = li.get("digest", "") if li else ""
        recompiled = bool(server_digest) and bool(local_digest) and server_digest != local_digest
        await self._refresh_local()
        await self._refresh_account()
        async with self:
            self.publish_state = "published_identical"
            self.published_digest = server_digest
            self.publish_version = version
            self.publish_busy = False
            if recompiled:
                self.publish_message = (
                    f"Published {ns}/{catalog_name}@{version}. The registry recompiled from your "
                    "spec with its reference Ensembl build, so the published artifact differs from "
                    "your local copy — reinstall to sync it."
                )
            else:
                self.publish_message = f"Published {ns}/{catalog_name}@{version}."

    async def _set_yank(self, yanked: bool) -> None:
        async with self:
            ns = self.publish_namespace
            li = self._selected_local
            catalog_name = li.get("catalog_name", "") if li else ""
            version = li.get("version", "") if li else ""
            url, token = self._client_args()
        if not (ns and catalog_name and version):
            return
        async with self:
            self.publish_busy = True
            self.publish_message = ("Yanking " if yanked else "Restoring ") + version + "…"
        loop = asyncio.get_event_loop()

        def _do():
            with RegistryClient(url, token) as c:
                return c.yank(ns, catalog_name, version) if yanked else c.unyank(ns, catalog_name, version)

        try:
            await loop.run_in_executor(None, _do)
        except Exception as e:  # noqa: BLE001
            async with self:
                self.publish_busy = False
                self.publish_message = f"{'Yank' if yanked else 'Restore'} failed: {e}"
            return
        await self._load_publish_state()
        async with self:
            self.publish_busy = False
            self.publish_message = ("Yanked " if yanked else "Restored ") + version + "."

    @rx.event(background=True)
    async def yank_selected(self):
        await self._set_yank(True)

    @rx.event(background=True)
    async def unyank_selected(self):
        await self._set_yank(False)

    # ---- metadata (out-of-digest; no version bump) ----
    @rx.event
    def update_meta(self, form_data: dict):
        changelog = (form_data.get("changelog") or "").strip()
        if not changelog:
            self.publish_message = "Enter release notes to update."
            return
        return RegistryState.do_update_changelog(changelog)

    @rx.event(background=True)
    async def do_update_changelog(self, changelog: str):
        async with self:
            ns = self.publish_namespace
            li = self._selected_local
            catalog_name = li.get("catalog_name", "") if li else ""
            version = li.get("version", "") if li else ""
            url, token = self._client_args()
        if not (ns and catalog_name and version):
            return
        async with self:
            self.publish_busy = True
            self.publish_message = "Updating release notes…"
        loop = asyncio.get_event_loop()

        def _do():
            with RegistryClient(url, token) as c:
                return c.amend_changelog(ns, catalog_name, version, changelog)

        try:
            await loop.run_in_executor(None, _do)
        except Exception as e:  # noqa: BLE001
            async with self:
                self.publish_busy = False
                self.publish_message = f"Metadata update failed: {e}"
            return
        async with self:
            self.publish_busy = False
            self.publish_message = "Release notes updated — no version bump needed."

    @rx.event
    async def update_logo(self, files: list[rx.UploadFile]):
        if not files:
            return
        f = files[0]
        data = await f.read()
        tmp = Path(tempfile.mkdtemp(prefix="reg_logo_")) / Path(f.filename).name
        tmp.write_bytes(data)
        return RegistryState.do_update_logo(str(tmp))

    @rx.event(background=True)
    async def do_update_logo(self, logo_path: str):
        async with self:
            ns = self.publish_namespace
            li = self._selected_local
            catalog_name = li.get("catalog_name", "") if li else ""
            version = li.get("version", "") if li else ""
            url, token = self._client_args()
        if not (ns and catalog_name and version):
            return
        loop = asyncio.get_event_loop()

        def _do():
            with RegistryClient(url, token) as c:
                return c.amend_logo(ns, catalog_name, version, Path(logo_path))

        try:
            await loop.run_in_executor(None, _do)
        except Exception as e:  # noqa: BLE001
            async with self:
                self.publish_message = f"Logo update failed: {e}"
            return
        async with self:
            self.publish_message = "Logo updated — out-of-digest, no version bump."

    # ---- account refresh (roles + stats) ----
    async def _refresh_account(self) -> None:
        async with self:
            url, token = self._client_args()
            fallback_ns = list(self.namespaces)
            fallback_account = self.account
        if not token:
            return
        loop = asyncio.get_event_loop()

        def _fetch():
            roles: List[Dict[str, str]] = []
            stats = {"modules": 0, "downloads": 0, "stars": 0, "reviews": 0}
            with RegistryClient(url, token) as c:
                try:
                    who = c.whoami()
                except Exception:  # noqa: BLE001
                    who = {}
                acct = who.get("account") or fallback_account
                ns_list = who.get("namespaces", fallback_ns) or fallback_ns
                for ns in ns_list:
                    try:
                        members = c.members(ns)
                        role = next((m.get("role") for m in members if m.get("account") == acct), "member")
                    except Exception:  # noqa: BLE001
                        role = "owner"
                    roles.append({"namespace": ns, "role": role})
                    try:
                        st = c.catalog_stats(namespace=ns)
                        for k in ("modules", "downloads", "stars", "reviews"):
                            stats[k] += int(st.get(k, 0) or 0)
                    except Exception:  # noqa: BLE001
                        pass
                return who, ns_list, roles, stats

        try:
            who, ns_list, roles, stats = await loop.run_in_executor(None, _fetch)
        except Exception:  # noqa: BLE001
            return
        async with self:
            if who:
                self.account = who.get("account", self.account)
                if who.get("display_name"):
                    self.display_name = who.get("display_name")
                if who.get("email"):
                    self.email = who.get("email")
            self.namespaces = ns_list
            self.roles = roles
            self.account_stats = stats
            if ns_list and not self.publish_namespace:
                self.publish_namespace = ns_list[0]
            self._persist_identity()

    # ------------------------------------------------------------------ edit (cross-page)

    @rx.event
    async def edit_selected(self):
        # Load into the Module Manager editing slot, then switch to that page/tab.
        if not MODULE_CREATOR_ENABLED:
            return  # /modules is not registered; the redirect would 404.
        agent = await self.get_state(AgentState)
        agent._do_load_custom_module(self.selected_name)
        return rx.redirect("/modules")
