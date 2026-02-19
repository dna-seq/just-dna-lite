from __future__ import annotations

import os
import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Any, List, Dict, Optional

import reflex as rx
from reflex.event import EventSpec
from pydantic import BaseModel
from dagster import DagsterInstance, AssetKey, AssetMaterialization, AssetRecordsFilter, DagsterRunStatus, RunsFilter, MetadataValue
from just_dna_pipelines.annotation.definitions import defs
from just_dna_pipelines.annotation.hf_modules import DISCOVERED_MODULES, MODULE_INFOS, HF_DEFAULT_REPOS
from just_dna_pipelines.module_config import build_module_metadata_dict
from just_dna_pipelines.annotation.assets import user_vcf_partitions
from just_dna_pipelines.annotation.hf_logic import prepare_vcf_for_module_annotation
from reflex_mui_datagrid import LazyFrameGridMixin, extract_vcf_descriptions, scan_file


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
    "N/A",      # Not specified/applicable
    "Male",
    "Female",
    "Other",
]

# Tissue source options (common sample sources)
TISSUE_OPTIONS: List[str] = [
    "Not specified",
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


def _ensure_dagster_config(dagster_home: Path) -> None:
    """
    Ensure dagster.yaml exists with proper configuration.
    
    Creates the config file if missing, enabling auto-materialization
    and other important features.
    """
    config_file = dagster_home / "dagster.yaml"
    
    if config_file.exists():
        return
    
    dagster_home.mkdir(parents=True, exist_ok=True)
    
    config_content = """# Dagster instance configuration
# Storage defaults to DAGSTER_HOME

# Enable auto-materialization for assets with AutoMaterializePolicy
auto_materialize:
  enabled: true
  minimum_interval_seconds: 60
"""
    
    config_file.write_text(config_content, encoding="utf-8")


def get_dagster_instance() -> DagsterInstance:
    """Get the Dagster instance, ensuring DAGSTER_HOME is set."""
    # Find workspace root
    root = Path(__file__).resolve().parents[3]
    dagster_home = os.getenv("DAGSTER_HOME", "data/interim/dagster")
    if not Path(dagster_home).is_absolute():
        dagster_home = str((root / dagster_home).resolve())
    
    dagster_home_path = Path(dagster_home)
    _ensure_dagster_config(dagster_home_path)
    os.environ["DAGSTER_HOME"] = dagster_home
    return DagsterInstance.get()


def get_dagster_web_url() -> str:
    """Get the URL for the Dagster web UI from environment or default."""
    return os.getenv("DAGSTER_WEB_URL", "http://localhost:3005").rstrip("/")


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


class UploadState(LazyFrameGridMixin, rx.State):
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
    
    # Class variable to track active in-process runs (for SIGTERM cleanup)
    # Maps run_id -> partition_key for runs executing via execute_in_process
    _active_inproc_runs: Dict[str, str] = {}

    # ============================================================
    # NEW SAMPLE FORM STATE - for adding samples with metadata
    # ============================================================
    new_sample_subject_id: str = ""
    new_sample_sex: str = "N/A"
    new_sample_tissue: str = "Not specified"
    new_sample_species: str = "Homo sapiens"
    new_sample_reference_genome: str = "GRCh38"
    new_sample_study_name: str = ""
    new_sample_notes: str = ""

    @rx.var
    def dagster_web_url(self) -> str:
        """Get the Dagster web UI URL."""
        return get_dagster_web_url()

    @rx.var
    def module_details(self) -> Dict[str, Dict[str, Any]]:
        """Return details (logo, repo, etc.) for each available module."""
        return {name: info.model_dump() for name, info in MODULE_INFOS.items()}

    @rx.var
    def repo_info_list(self) -> List[Dict[str, Any]]:
        """
        Return info about each HF repository used as a module source.
        
        Groups modules by their repo_id and provides browsable HF URLs.
        """
        repos: Dict[str, Dict[str, Any]] = {}
        for name, info in MODULE_INFOS.items():
            repo_id = info.repo_id
            if repo_id not in repos:
                repos[repo_id] = {
                    "repo_id": repo_id,
                    "url": f"https://huggingface.co/datasets/{repo_id}",
                    "modules": [],
                    "module_count": 0,
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

    def _reset_new_sample_form(self):
        """Reset new sample form to defaults."""
        self.new_sample_subject_id = ""
        self.new_sample_sex = "N/A"
        self.new_sample_tissue = "Not specified"
        self.new_sample_species = "Homo sapiens"
        self.new_sample_reference_genome = "GRCh38"
        self.new_sample_study_name = ""
        self.new_sample_notes = ""

    def _get_safe_user_id(self, auth_email: str) -> str:
        """Sanitize user_id for path and partition key."""
        user_id = auth_email or "anonymous"
        return "".join([c if c.isalnum() else "_" for c in user_id])

    async def handle_upload(self, files: list[rx.UploadFile]):
        """Handle the upload of VCF files and register them in Dagster."""
        self.uploading = True
        
        auth_state = await self.get_state(AuthState)
        self.safe_user_id = self._get_safe_user_id(auth_state.user_email)
        
        root = Path(__file__).resolve().parents[3]
        # Align with Dagster's expected input directory
        upload_dir = root / "data" / "input" / "users" / self.safe_user_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        new_files = []
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
            
            # 2. Materialize user_vcf_source (the source asset)
            instance.report_runless_asset_event(
                AssetMaterialization(
                    asset_key="user_vcf_source",
                    partition=partition_key,
                    metadata={
                        "path": str(file_path.absolute()),
                        "size_bytes": len(content),
                        "uploaded_via": "webui",
                        "upload_date": upload_date,
                    }
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
        
        # Normalize each uploaded VCF to parquet (lightweight, synchronous)
        for file in files:
            if not file.filename:
                continue
            sample_name = file.filename.replace(".vcf.gz", "").replace(".vcf", "")
            pk = f"{self.safe_user_id}/{sample_name}"
            fp = upload_dir / file.filename
            if fp.exists():
                self._normalize_vcf_sync(instance, fp, pk)

        self.uploading = False
        if new_files:
            self.selected_file = new_files[-1]
            self.vcf_preview_expanded = True
            self._load_vcf_preview_sync()
            self._load_output_files_sync()
            yield rx.toast.success(f"Uploaded and registered {len(new_files)} files.")
        else:
            yield rx.toast.warning("No files were uploaded")

    async def handle_upload_with_metadata(self, files: list[rx.UploadFile]):
        """
        Handle upload of VCF files with metadata from the new sample form.
        
        This combines file upload and metadata registration in a single operation.
        The metadata from the form (subject_id, sex, tissue, species, etc.) is 
        stored in the Dagster asset materialization.
        """
        if not files:
            yield rx.toast.warning("No files selected for upload")
            return
            
        self.uploading = True
        
        auth_state = await self.get_state(AuthState)
        self.safe_user_id = self._get_safe_user_id(auth_state.user_email)
        
        root = Path(__file__).resolve().parents[3]
        upload_dir = root / "data" / "input" / "users" / self.safe_user_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        new_files = []
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
            
            # Build complete metadata dict with form values
            metadata: Dict[str, Any] = {
                "path": MetadataValue.path(str(file_path.absolute())),
                "size_bytes": MetadataValue.int(len(content)),
                "uploaded_via": MetadataValue.text("webui"),
                "upload_date": MetadataValue.text(upload_date),
                "species": MetadataValue.text(self.new_sample_species),
                "reference_genome": MetadataValue.text(self.new_sample_reference_genome),
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
                "reference_genome": self.new_sample_reference_genome,
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
        
        # Normalize each uploaded VCF to parquet (lightweight, synchronous)
        for file in files:
            if not file.filename:
                continue
            sn = file.filename.replace(".vcf.gz", "").replace(".vcf", "")
            pk = f"{self.safe_user_id}/{sn}"
            fp = upload_dir / file.filename
            if fp.exists():
                self._normalize_vcf_sync(instance, fp, pk)

        self.uploading = False
        
        if new_files:
            self._reset_new_sample_form()
            self.selected_file = new_files[-1]
            self.vcf_preview_expanded = True
            self._load_vcf_preview_sync()
            self._load_output_files_sync()
            yield rx.toast.success(f"Added {len(new_files)} sample(s) with metadata")
        else:
            yield rx.toast.warning("No files were uploaded")

    def _normalize_vcf_sync(self, instance: DagsterInstance, file_path: Path, partition_key: str) -> bool:
        """Run normalize_vcf_job in-process so the preview shows normalized data.

        Returns True on success, False on failure (logged but non-fatal).
        """
        run_config = {
            "ops": {
                "user_vcf_normalized": {
                    "config": {
                        "vcf_path": str(file_path.absolute()),
                    }
                }
            }
        }
        result = self._execute_job_in_process(instance, "normalize_vcf_job", run_config, partition_key)
        return result.success

    def _execute_job_in_process(self, instance: DagsterInstance, job_name: str, run_config: dict, partition_key: str):
        """
        Execute a Dagster job in-process (like prepare-annotations does).
        
        This avoids all the daemon/workspace mismatch issues that submit_run has.
        The job runs synchronously in the current process.
        
        Note: We cannot track the run_id before execution because execute_in_process
        creates the run internally. For orphaned STARTED runs from crashes,
        use the CLI cleanup command: `uv run pipelines cleanup-runs --status STARTED`
        """
        job_def = defs.resolve_job_def(job_name)
        
        # Ensure the partition exists before running
        existing_partitions = instance.get_dynamic_partitions(user_vcf_partitions.name)
        if partition_key not in existing_partitions:
            instance.add_dynamic_partitions(user_vcf_partitions.name, [partition_key])
        
        # Execute in-process - this creates and runs the job atomically
        # Tag with source=webui so shutdown handler only cancels our runs
        result = job_def.execute_in_process(
            run_config=run_config,
            instance=instance,
            tags={
                "dagster/partition": partition_key,
                "source": "webui",
            },
        )
        return result

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
        
        root = Path(__file__).resolve().parents[3]
        vcf_path = root / "data" / "input" / "users" / self.safe_user_id / filename
        
        instance = get_dagster_instance()
        
        # Update status to running immediately
        if partition_key not in self.asset_statuses:
            self.asset_statuses[partition_key] = {}
        self.asset_statuses[partition_key]["annotated"] = "running"
        yield
        
        job_name = "annotate_vcf_duckdb_job"
        
        # Use Dagster API to submit run instead of execute_in_process
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

        # Execute job in-process (like prepare-annotations does)
        # This avoids daemon/workspace mismatch issues
        result = self._execute_job_in_process(instance, job_name, run_config, partition_key)
        
        if result.success:
            self.asset_statuses[partition_key]["annotated"] = "completed"
            yield rx.toast.success(f"Annotation completed for {sample_name}")
        else:
            self.asset_statuses[partition_key]["annotated"] = "failed"
            yield rx.toast.error(f"Annotation failed for {sample_name}")

    def toggle_module(self, module: str):
        """Toggle a module on/off in the selection."""
        self.last_run_success = False
        if module in self.selected_modules:
            self.selected_modules = [m for m in self.selected_modules if m != module]
        else:
            self.selected_modules = self.selected_modules + [module]

    def select_all_modules(self):
        """Select all available modules."""
        self.last_run_success = False
        self.selected_modules = self.available_modules.copy()

    def deselect_all_modules(self):
        """Deselect all modules."""
        self.last_run_success = False
        self.selected_modules = []

    def toggle_ensembl(self):
        """Toggle Ensembl variation annotation on/off."""
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
        vcf_path = root / "data" / "input" / "users" / self.safe_user_id / filename
        
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
        result = self._execute_job_in_process(instance, job_name, run_config, partition_key)
        
        if result.success:
            self.asset_statuses[partition_key]["hf_annotated"] = "completed"
            yield rx.toast.success(f"HF annotation completed for {sample_name} with {modules_info}")
        else:
            self.asset_statuses[partition_key]["hf_annotated"] = "failed"
            yield rx.toast.error(f"HF annotation failed for {sample_name}")

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
    
    # File metadata cache: filename -> {size_mb, upload_date, reference_genome, sample_name}
    file_metadata: Dict[str, Dict[str, Any]] = {}
    
    # Run history tracking
    runs: List[Dict[str, Any]] = []
    active_run_id: str = ""
    run_logs: List[str] = []
    polling_active: bool = False
    
    # Tracking for the UI button state
    last_run_success: bool = False
    
    # Tab management for two-panel layout (legacy, kept for backwards compatibility)
    active_tab: str = "params"  # "params", "history", "outputs"
    
    # Output files for the selected sample
    output_files: List[Dict[str, Any]] = []
    report_files: List[Dict[str, Any]] = []  # HTML report files
    outputs_active_tab: str = "data"  # "data" or "reports" sub-tab in outputs section

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
        Shows Subject ID if available, otherwise filename.
        """
        result = {}
        for filename in self.files:
            meta = self.file_metadata.get(filename, {})
            subject_id = meta.get("subject_id", "")
            if subject_id and subject_id.strip():
                result[filename] = subject_id.strip()
            else:
                # Use sample name (filename without extension)
                result[filename] = filename.replace(".vcf.gz", "").replace(".vcf", "")
        return result

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
        file_path = root / "data" / "input" / "users" / self.safe_user_id / filename
        
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
            "tissue": "Not specified",  # Required - sample tissue source
            # Optional fields
            "study_name": "",
            "notes": "",
            # Custom key-value fields (user can add their own)
            "custom_fields": {},  # Dict[str, str] for user-defined fields
        }

    def _clear_vcf_preview(self):
        """Clear data preview and reset server-side grid state."""
        self.lf_grid_rows = []
        self.lf_grid_columns = []
        self.lf_grid_row_count = 0
        self.lf_grid_loading = False
        self.lf_grid_loaded = False
        self.lf_grid_stats = ""
        self.lf_grid_selected_info = "Click a row to see details."
        self._lf_grid_filter = {}
        self._lf_grid_sort = []
        self.vcf_preview_error = ""
        self.vcf_preview_loading = False
        self.preview_source_label = ""
        self._clear_norm_stats()

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

    def _ensure_normalized_fresh(self) -> bool:
        """Re-normalize if the parquet is stale (quality filters changed).

        Compares the hash stored on the materialization against the current
        config.  Returns True if re-normalization happened, False otherwise.
        """
        from just_dna_pipelines.module_config import _load_config

        current_hash = _load_config().quality_filters.config_hash()

        # If no stats loaded or hashes match, nothing to do
        if not self.norm_stats_loaded:
            # No previous materialization — need to normalize
            pass
        elif self.norm_filters_hash == current_hash:
            return False

        # Stale or missing — re-normalize
        if not self.selected_file or not self.safe_user_id:
            return False

        root = Path(__file__).resolve().parents[3]
        vcf_path = root / "data" / "input" / "users" / self.safe_user_id / self.selected_file
        if not vcf_path.exists():
            return False

        sample_name = self.selected_file.replace(".vcf.gz", "").replace(".vcf", "")
        partition_key = f"{self.safe_user_id}/{sample_name}"
        instance = get_dagster_instance()

        self._normalize_vcf_sync(instance, vcf_path, partition_key)
        # Reload stats from the fresh materialization
        self._load_norm_stats_from_dagster()
        return True

    def _get_normalized_parquet_path(self) -> Path | None:
        """Return the normalized parquet path if it exists, else None."""
        if not self.selected_file or not self.safe_user_id:
            return None
        sample_name = self.selected_file.replace(".vcf.gz", "").replace(".vcf", "")
        root = Path(__file__).resolve().parents[3]
        parquet_path = root / "data" / "output" / "users" / self.safe_user_id / sample_name / "user_vcf_normalized.parquet"
        if parquet_path.exists():
            return parquet_path
        return None

    def _load_vcf_preview_sync(self):
        """Load normalized parquet for preview; fall back to raw VCF.

        Also ensures the parquet is fresh (quality filters match current config)
        and loads filter statistics from Dagster for UI display.
        """
        if not self.selected_file or not self.safe_user_id:
            self._clear_vcf_preview()
            return

        self.vcf_preview_loading = True
        self.vcf_preview_error = ""

        # Load normalization stats and re-normalize if quality filters changed
        self._load_norm_stats_from_dagster()
        self._ensure_normalized_fresh()

        import polars as pl

        normalized = self._get_normalized_parquet_path()
        if normalized is not None:
            try:
                lf = pl.scan_parquet(str(normalized))
                for _ in self.set_lazyframe(lf, {}, chunk_size=300):
                    pass
                self.preview_source_label = f"{self.selected_file} (normalized)"
                self.vcf_preview_loading = False
                return
            except Exception:
                pass  # fall through to raw VCF

        root = Path(__file__).resolve().parents[3]
        vcf_path = root / "data" / "input" / "users" / self.safe_user_id / self.selected_file
        if not vcf_path.exists():
            self._clear_vcf_preview()
            self.vcf_preview_error = f"VCF file not found: {vcf_path.name}"
            return

        try:
            lazy_vcf = prepare_vcf_for_module_annotation(vcf_path)
            descriptions = extract_vcf_descriptions(lazy_vcf)
            for _ in self.set_lazyframe(lazy_vcf, descriptions, chunk_size=300):
                pass
            self.preview_source_label = f"{vcf_path.name} (normalized)"
        except Exception as e:
            self._clear_vcf_preview()
            self.vcf_preview_error = str(e)
        finally:
            self.vcf_preview_loading = False

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

    @rx.var
    def backend_api_url(self) -> str:
        """Get the backend API URL for downloads."""
        return os.getenv("API_URL", "http://localhost:8000")

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
    def current_sex(self) -> str:
        """Get sex for the currently selected file."""
        if not self.selected_file:
            return "N/A"
        return self.file_metadata.get(self.selected_file, {}).get("sex", "N/A")

    @rx.var
    def current_tissue(self) -> str:
        """Get tissue source for the currently selected file."""
        if not self.selected_file:
            return "Not specified"
        return self.file_metadata.get(self.selected_file, {}).get("tissue", "Not specified")

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
        """Select a file and pre-select modules from its latest run if available."""
        self.selected_file = filename
        # Reset success state on selection change
        self.last_run_success = False
        # Reset expanded run
        self.expanded_run_id = ""
        
        # Load file metadata if not already loaded
        if filename not in self.file_metadata:
            self._load_file_metadata(filename)
        
        # Find the latest run for this file to pre-select modules
        file_runs = [r for r in self.runs if r.get("filename") == filename]
        if file_runs:
            # Sort by started_at (ISO format strings) descending, handle None values
            file_runs.sort(key=lambda x: x.get("started_at") or "", reverse=True)
            latest_run = file_runs[0]
            if latest_run.get("modules"):
                self.selected_modules = latest_run["modules"].copy()
        
        # Expand all sections by default when selecting a file
        self.vcf_preview_expanded = True
        self.outputs_expanded = True
        self.run_history_expanded = True
        self.new_analysis_expanded = True
        
        # Load VCF preview for the selected sample
        self._load_vcf_preview_sync()

        # Load output files for the selected sample
        self._load_output_files_sync()

        # Clear the output preview grid (belongs to OutputPreviewState)
        return OutputPreviewState.clear_output_preview

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
            self.output_files = []
            self.report_files = []
            return
        
        sample_name = self.selected_file.replace(".vcf.gz", "").replace(".vcf", "")
        root = Path(__file__).resolve().parents[3]
        partition_key = f"{self.safe_user_id}/{sample_name}"

        # Fetch Dagster materialization timestamps for relevant assets
        mat_info = self._fetch_output_materialization_info(partition_key)
        annotations_mat = mat_info.get("user_hf_module_annotations", {})
        report_mat = mat_info.get("user_longevity_report", {})
        
        # Load parquet data files from modules/ directory
        output_dir = root / "data" / "output" / "users" / self.safe_user_id / sample_name / "modules"
        
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
                
                files.append({
                    "name": f.name,
                    "path": str(f),
                    "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                    "module": module,
                    "type": file_type,
                    "sample_name": sample_name,
                    "materialized_at": annotations_mat.get("materialized_at", ""),
                    "needs_materialization": annotations_mat.get("needs_materialization", True),
                })
        
        # Also scan sample root for Ensembl annotation parquets (*_annotated_duckdb.parquet)
        ensembl_mat = mat_info.get("user_annotated_vcf_duckdb", {})
        sample_dir = root / "data" / "output" / "users" / self.safe_user_id / sample_name
        if sample_dir.exists():
            for f in sample_dir.glob("*_annotated_duckdb.parquet"):
                files.append({
                    "name": f.name,
                    "path": str(f),
                    "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                    "module": "ensembl",
                    "type": "annotations",
                    "sample_name": sample_name,
                    "materialized_at": ensembl_mat.get("materialized_at", ""),
                    "needs_materialization": ensembl_mat.get("needs_materialization", True),
                })

        files.sort(key=lambda x: (x["module"], x["type"]))
        self.output_files = files
        
        # Load HTML report files from reports/ directory
        reports_dir = root / "data" / "output" / "users" / self.safe_user_id / sample_name / "reports"
        
        reports: list[dict] = []
        if reports_dir.exists():
            for f in reports_dir.glob("*.html"):
                reports.append({
                    "name": f.name,
                    "path": str(f),
                    "size_kb": round(f.stat().st_size / 1024, 1),
                    "sample_name": sample_name,
                    "materialized_at": report_mat.get("materialized_at", ""),
                    "needs_materialization": report_mat.get("needs_materialization", True),
                })
        
        reports.sort(key=lambda x: x["name"])
        self.report_files = reports

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
        ]
        timestamps: Dict[str, float] = {}
        for asset_name in asset_chain:
            result = instance.fetch_materializations(
                records_filter=AssetRecordsFilter(
                    asset_key=AssetKey(asset_name),
                    asset_partitions=[partition_key],
                ),
                limit=1,
            )
            timestamps[asset_name] = result.records[0].timestamp if result.records else 0.0

        info: Dict[str, Dict[str, Any]] = {}
        upstream_map = {
            "user_hf_module_annotations": "user_vcf_normalized",
            "user_longevity_report": "user_hf_module_annotations",
            "user_annotated_vcf_duckdb": "user_vcf_normalized",
        }
        for asset_name in ["user_hf_module_annotations", "user_longevity_report", "user_annotated_vcf_duckdb"]:
            ts = timestamps[asset_name]
            upstream_ts = timestamps.get(upstream_map[asset_name], 0.0)
            mat_at = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else ""
            needs = (ts == 0.0) or (upstream_ts > ts)
            info[asset_name] = {
                "materialized_at": mat_at,
                "needs_materialization": needs,
                "timestamp": ts,
            }
        return info

    @rx.var
    def has_output_files(self) -> bool:
        """Check if there are any output files (data or reports) for the selected sample."""
        return len(self.output_files) > 0 or len(self.report_files) > 0

    @rx.var
    def output_file_count(self) -> int:
        """Get the number of data output files."""
        return len(self.output_files)

    @rx.var
    def report_file_count(self) -> int:
        """Get the number of report files."""
        return len(self.report_files)

    @rx.var
    def has_report_files(self) -> bool:
        """Check if there are any report files."""
        return len(self.report_files) > 0

    @rx.var
    def total_output_count(self) -> int:
        """Total count of all output files (data + reports)."""
        return len(self.output_files) + len(self.report_files)

    async def delete_file(self, filename: str):
        """Delete an uploaded file from the filesystem and state."""
        if not self.safe_user_id:
            auth_state = await self.get_state(AuthState)
            self.safe_user_id = self._get_safe_user_id(auth_state.user_email)
            
        root = Path(__file__).resolve().parents[3]
        file_path = root / "data" / "input" / "users" / self.safe_user_id / filename
        
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
        if self.last_run_success:
            return "Analysis Complete"
        return "Start Analysis"

    @rx.var
    def analysis_button_icon(self) -> str:
        """Get the icon for the analysis button based on state."""
        if self.selected_file_is_running:
            return "loader-circle"
        if self.last_run_success:
            return "circle-check"
        return "play"

    @rx.var
    def analysis_button_color(self) -> str:
        """Get the color class for the analysis button (DNA palette: yellow=running, green=success, blue=default)."""
        if self.selected_file_is_running:
            return "ui yellow right labeled icon large button fluid"
        if self.last_run_success:
            return "ui green right labeled icon large button fluid"
        return "ui primary right labeled icon large button fluid"

    @rx.var
    def module_metadata_list(self) -> List[Dict[str, Any]]:
        """Return module metadata for UI display."""
        result = []
        for module_name in self.available_modules:
            meta = MODULE_METADATA.get(module_name, {
                "title": module_name.replace("_", " ").title(),
                "description": f"Annotation module: {module_name}",
                "icon": "database",
                "color": "neutral",
            })
            info = MODULE_INFOS.get(module_name)
            # Convert hf:// logo URL to browsable HTTPS URL for display
            browsable_logo_url = ""
            if info and info.logo_url:
                # hf://datasets/just-dna-seq/annotators/data/module/logo.png
                # -> https://huggingface.co/datasets/just-dna-seq/annotators/resolve/main/data/module/logo.png
                hf_path = info.logo_url.replace("hf://", "")
                browsable_logo_url = f"https://huggingface.co/{hf_path.replace(info.repo_id, info.repo_id + '/resolve/main', 1)}"
            result.append({
                "name": module_name,
                "title": meta.get("title", module_name),
                "description": meta.get("description", ""),
                "icon": meta.get("icon", "database"),
                "color": meta.get("color", "neutral"),
                "logo_url": browsable_logo_url,
                "repo_id": info.repo_id if info else "",
                "selected": module_name in self.selected_modules,
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

    def _execute_inproc_with_state_update(
        self, 
        instance: DagsterInstance, 
        job_name: str, 
        run_config: dict, 
        partition_key: str,
        original_run_id: str,
        sample_name: str
    ) -> None:
        """
        Execute job in-process and update UI state with result.
        
        This method runs synchronously but is called from a background thread/executor
        to avoid blocking the UI. DO NOT use asyncio.to_thread() here - causes
        Python/Rust interop panics with Dagster objects.
        """
        actual_run_id = None
        try:
            # Execute synchronously (caller handles threading)
            result = self._execute_job_in_process(
                instance, job_name, run_config, partition_key
            )
            
            # Get actual run ID from execute_in_process result
            actual_run_id = result.run_id
            
            # Track this as an active in-process run (for SIGTERM cleanup)
            UploadState._active_inproc_runs[actual_run_id] = partition_key
            
            self._add_log(f"Job completed via in-process execution with run ID: {actual_run_id}")
            
            # Update the run info with actual run ID and final status
            updated_runs = []
            for r in self.runs:
                if r["run_id"] == original_run_id:
                    r["run_id"] = actual_run_id
                    r["status"] = "SUCCESS" if result.success else "FAILURE"
                    r["ended_at"] = datetime.now().isoformat()
                    r["dagster_url"] = f"{get_dagster_web_url()}/runs/{actual_run_id}"
                    if not result.success:
                        r["error"] = "Job failed - check Dagster UI for details"
                    # Find output path if successful
                    if result.success:
                        root = Path(__file__).resolve().parents[3]
                        output_dir = root / "data" / "output" / "users" / self.safe_user_id / sample_name / "modules"
                        if output_dir.exists():
                            r["output_path"] = str(output_dir)
                updated_runs.append(r)
            self.runs = updated_runs
            
            # Reset state - this will trigger UI reactivity
            self.running = False
            self.polling_active = False
            self.last_run_success = result.success
            
            # Refresh output files so UI shows them immediately
            self._load_output_files_sync()
            
        except Exception as e:
            error_message = str(e)
            self._add_log(f"In-process execution failed: {error_message}")
            
            # Reset state and mark as failure
            self.running = False
            self.polling_active = False
            self.last_run_success = False
            
            # Update run status in history to FAILURE
            updated_runs = []
            for r in self.runs:
                if r["run_id"] == original_run_id:
                    r["status"] = "FAILURE"
                    r["ended_at"] = datetime.now().isoformat()
                    r["error"] = f"Execution failed: {error_message}"
                updated_runs.append(r)
            self.runs = updated_runs
        finally:
            # Clean up tracker
            if actual_run_id and actual_run_id in UploadState._active_inproc_runs:
                del UploadState._active_inproc_runs[actual_run_id]

    async def start_annotation_run(self):
        """Start annotation for the selected file with selected modules and/or Ensembl."""
        if not self.selected_file:
            yield rx.toast.error("Please select a file")
            return
        if not self.selected_modules and not self.include_ensembl:
            yield rx.toast.error("Please select at least one module or enable Ensembl annotations")
            return

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
        vcf_path = root / "data" / "input" / "users" / self.safe_user_id / self.selected_file

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
            # Launch as background task to keep UI responsive
            self._add_log(f"Daemon submission failed: {daemon_error}")
            self._add_log("Starting in-process execution (this will take a few minutes)...")
            yield rx.toast.info(f"Running in-process for {sample_name} - please wait...")
            
            # Delete the dummy run since execute_in_process will create a new one
            # This prevents the poller from checking a stale NOT_STARTED run
            instance.delete_run(run_id)
            self._add_log(f"Deleted dummy run {run_id}, execute_in_process will create a new run")
            
            # Disable polling - execute_in_process creates a new run ID that we'll track manually
            self.polling_active = False
            
            # Update status to RUNNING
            updated_runs = []
            for r in self.runs:
                if r["run_id"] == run_id:
                    r["status"] = "RUNNING"
                updated_runs.append(r)
            self.runs = updated_runs
            
            # Execute in thread pool to avoid blocking UI and Python GIL issues
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None,  # Use default executor
                self._execute_inproc_with_state_update,
                instance, job_name, run_config, partition_key, run_id, sample_name
            )
            # Don't await - let it run in background and update state when done
    
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
        """
        if not self.active_run_id or not self.polling_active:
            return

        # Don't poll for temporary IDs
        if str(self.active_run_id).startswith("running-"):
            return

        instance = get_dagster_instance()
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
                    # Find output path
                    if run.status == DagsterRunStatus.SUCCESS:
                        sample_name = r.get("sample_name", "")
                        root = Path(__file__).resolve().parents[3]
                        output_dir = root / "data" / "output" / "users" / self.safe_user_id / sample_name / "modules"
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
            # Reload output files so the UI shows them immediately
            self._load_output_files_sync()
            if run.status == DagsterRunStatus.SUCCESS:
                return rx.toast.success("Annotation completed successfully!")
            elif run.status == DagsterRunStatus.FAILURE:
                return rx.toast.error("Annotation failed. Check logs for details.")

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

    def switch_outputs_tab(self, tab_name: str):
        """Switch between 'data' and 'reports' sub-tabs in outputs section."""
        self.outputs_active_tab = tab_name

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

    async def rerun_with_same_modules(self):
        """Re-run annotation with the same modules as the last run."""
        last_run = self.last_run_for_file
        if last_run and last_run.get("modules"):
            self.selected_modules = last_run["modules"].copy()
        # Start the annotation
        async for event in self.start_annotation_run():
            yield event

    def modify_and_run(self):
        """Pre-select modules from last run and expand the analysis section."""
        last_run = self.last_run_for_file
        if last_run and last_run.get("modules"):
            self.selected_modules = last_run["modules"].copy()
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
        self.safe_user_id = self._get_safe_user_id(auth_state.user_email)
        
        # Clean up orphaned runs on startup (NOT_STARTED only)
        cleaned = self._cleanup_orphaned_runs()
        if cleaned > 0:
            self._add_log(f"🧹 Deleted {cleaned} orphaned NOT_STARTED run(s) from Dagster database")
        
        root = Path(__file__).resolve().parents[3]
        user_dir = root / "data" / "input" / "users" / self.safe_user_id
        
        if not user_dir.exists():
            return

        # Find VCF files, sorted by modification time (newest first)
        vcf_files = list(user_dir.glob("*.vcf")) + list(user_dir.glob("*.vcf.gz"))
        vcf_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        self.files = [f.name for f in vcf_files]
        
        # Load basic metadata for all files (from filesystem)
        for filename in self.files:
            self._load_file_metadata(filename)
        
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
                "status": self._get_run_status_str(run.status),
                "started_at": started_at,
                "ended_at": ended_at,
                "output_path": None,
            }
            
            # Check for output if successful
            if run.status == DagsterRunStatus.SUCCESS and sample_name:
                root = Path(__file__).resolve().parents[3]
                user_name = hf_config.get("user_name") or duckdb_config.get("user_name", self.safe_user_id)
                output_dir = root / "data" / "output" / "users" / user_name / sample_name / "modules"
                if output_dir.exists():
                    run_info["output_path"] = str(output_dir)
            
            run_list.append(run_info)
        
        self.runs = run_list


class OutputPreviewState(LazyFrameGridMixin, rx.State):
    """Independent state for the output file preview grid.

    Inherits its own ``LazyFrameGridMixin`` so the output grid has a
    completely separate LazyFrame cache, column defs, rows, etc. from
    the VCF input grid managed by ``UploadState``.

    The ``on_click`` handler in the output file card calls
    ``OutputPreviewState.view_output_file`` **directly** — no bridge
    through ``UploadState`` is needed.
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

    def view_output_file(self, file_path: str):
        """Load an output data file into the output preview grid.

        Generator — use ``yield from`` or call directly from ``on_click``.
        Reflex will iterate the generator and push intermediate state
        updates to the frontend.
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

        self.output_preview_label = path.name
        self.output_preview_loading = False

    def toggle_output_preview(self):
        """Toggle the output preview section open/closed."""
        self.output_preview_expanded = not self.output_preview_expanded

    def clear_output_preview(self):
        """Reset the output preview grid to empty state."""
        self.output_preview_label = ""
        self.output_preview_error = ""
        self.output_preview_expanded = False
        self.lf_grid_loaded = False
        self.lf_grid_rows = []
        self.lf_grid_columns = []
        self.lf_grid_row_count = 0
