"""One annotation run of one sample: choose the job, build its config, execute it, read what it did.

Shared by ``uv run annotate`` and the MCP worker (``just_dna_pipelines.lite_mcp.worker``). Both run
the same Dagster jobs as the web UI with the same ``ops``-keyed run config, so a run started from any
of them shows up in the Dagster UI when ``DAGSTER_HOME`` matches.

Nothing here prints. The CLI renders an :class:`AnnotationOutcome`; the worker serialises it.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import polars as pl
from dagster import AssetKey, AssetRecordsFilter, DagsterInstance, Definitions
from pydantic import BaseModel, Field

from just_dna_pipelines.annotation.assets import user_vcf_partitions
from just_dna_pipelines.annotation.hf_modules import AnnotationManifest
from just_dna_pipelines.annotation.resources import get_user_output_dir, get_workspace_root
from just_dna_pipelines.module_config import _load_config

DEFAULT_DAGSTER_HOME = "data/interim/dagster"

FULL_JOB = "annotate_and_report_job"
REUSE_NORMALIZED_JOB = "annotate_modules_and_report_job"
ENSEMBL_JOB = "annotate_all_job"


def ensure_dagster_home() -> Path:
    """Resolve and export ``DAGSTER_HOME`` the same way the launchers do."""
    root = get_workspace_root()
    configured = os.getenv("DAGSTER_HOME", DEFAULT_DAGSTER_HOME)
    dagster_home = Path(configured)
    if not dagster_home.is_absolute():
        dagster_home = (root / dagster_home).resolve()
    dagster_home.mkdir(parents=True, exist_ok=True)
    (dagster_home / "logs").mkdir(parents=True, exist_ok=True)
    os.environ["DAGSTER_HOME"] = str(dagster_home)
    return dagster_home


def sample_name_from_vcf(vcf_path: Path) -> str:
    """Match partition discovery: strip ``.vcf`` / ``.vcf.gz`` from the filename."""
    name = vcf_path.name
    if name.endswith(".vcf.gz"):
        return name[: -len(".vcf.gz")]
    if name.endswith(".vcf"):
        return name[: -len(".vcf")]
    return vcf_path.stem


def parquet_is_empty(path: Path) -> bool:
    """True when the parquet is missing, unreadable, or has zero rows (footer read only)."""
    if not path.exists():
        return True
    try:
        return pl.scan_parquet(path).select(pl.len()).collect().item() == 0
    except Exception:
        return True


def normalized_parquet_is_current(
    instance: DagsterInstance, partition_key: str, normalized_path: Path
) -> bool:
    """Whether ``user_vcf_normalized.parquet`` can be reused for this partition as it is.

    Current means: the latest materialization recorded the quality-filter hash now in force, the
    file is on disk, and it is not empty. An empty normalized genome is never legitimate — it is
    the signature of an earlier broken run whose config hash did not change, so it is treated as
    stale and the run self-heals.
    """
    current_hash = _load_config().quality_filters.config_hash()
    result = instance.fetch_materializations(
        records_filter=AssetRecordsFilter(
            asset_key=AssetKey("user_vcf_normalized"),
            asset_partitions=[partition_key],
        ),
        limit=1,
    )
    if not result.records:
        return False
    materialization = result.records[0].asset_materialization
    if materialization is None or not materialization.metadata:
        return False
    stored = materialization.metadata.get("quality_filters_hash")
    stored_hash = str(stored.value) if stored is not None and hasattr(stored, "value") else ""
    if stored_hash != current_hash or not normalized_path.exists():
        return False
    return not parquet_is_empty(normalized_path)


class AnnotationRequest(BaseModel):
    """Everything one run needs. ``vcf_path`` must already sit in the user's input directory."""

    vcf_path: Path
    user_name: str
    modules: list[str]
    ensembl: bool = False
    sex: Optional[str] = None
    reference_genome: str = "GRCh38"
    species: str = "Homo sapiens"
    subject_id: Optional[str] = None
    # Reuse a current normalized parquet instead of re-reading the VCF. The web UI always
    # re-normalizes; for an author re-running one module over several genomes that is most of
    # the wall-clock, and the staleness test above is the same one the UI uses to decide.
    reuse_normalized: bool = True
    source_tag: str = "cli"

    @property
    def sample_name(self) -> str:
        return sample_name_from_vcf(self.vcf_path)

    @property
    def partition_key(self) -> str:
        return f"{self.user_name}/{self.sample_name}"


class AnnotationOutcome(BaseModel):
    """What one run did, read back from disk after it finished."""

    run_id: str
    success: bool
    job_name: str
    partition_key: str
    normalized_reused: bool
    sample_output_dir: str
    modules_dir: str
    manifest_path: Optional[str] = None
    report_path: Optional[str] = None
    skipped_modules: dict[str, str] = Field(default_factory=dict)
    failed_modules: dict[str, str] = Field(default_factory=dict)
    total_variants_annotated: Optional[int] = None
    total_variants_restored: Optional[int] = None
    error: Optional[str] = None
    started_at: str
    finished_at: str


def select_job(request: AnnotationRequest, instance: DagsterInstance) -> tuple[str, bool]:
    """Return ``(job_name, normalized_reused)`` for this request."""
    if request.ensembl:
        return ENSEMBL_JOB, False
    if request.reuse_normalized:
        normalized = get_user_output_dir() / request.partition_key / "user_vcf_normalized.parquet"
        if normalized_parquet_is_current(instance, request.partition_key, normalized):
            return REUSE_NORMALIZED_JOB, True
    return FULL_JOB, False


def build_run_config(request: AnnotationRequest, job_name: str) -> dict[str, Any]:
    """The ``ops``-keyed run config for *job_name* (asset jobs take ``ops``, never ``assets``)."""
    vcf = str(request.vcf_path)
    hf_config: dict[str, Any] = {
        "vcf_path": vcf,
        "user_name": request.user_name,
        "sample_name": request.sample_name,
        "modules": request.modules,
        "species": request.species,
        "reference_genome": request.reference_genome,
        "sex": request.sex,
    }
    if request.subject_id:
        hf_config["subject_id"] = request.subject_id

    ops: dict[str, Any] = {
        "user_hf_module_annotations": {"config": hf_config},
        "user_longevity_report": {
            "config": {
                "user_name": request.user_name,
                "sample_name": request.sample_name,
                "modules": request.modules,
            }
        },
    }
    if job_name != REUSE_NORMALIZED_JOB:
        normalize_config: dict[str, Any] = {"vcf_path": vcf}
        if request.sex:
            normalize_config["sex"] = request.sex
        ops["user_vcf_normalized"] = {"config": normalize_config}
    if job_name == ENSEMBL_JOB:
        ops["user_annotated_vcf_duckdb"] = {
            "config": {
                "vcf_path": vcf,
                "user_name": request.user_name,
                "sample_name": request.sample_name,
            }
        }
    return {"ops": ops}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def latest_report(reports_dir: Path, not_before: Optional[float] = None) -> Optional[Path]:
    """Newest ``*.html`` report, optionally only one written at or after *not_before* (epoch)."""
    if not reports_dir.exists():
        return None
    reports = [p for p in reports_dir.glob("*.html") if not_before is None or p.stat().st_mtime >= not_before]
    if not reports:
        return None
    return max(reports, key=lambda p: p.stat().st_mtime)


def run_annotation(
    request: AnnotationRequest,
    instance: DagsterInstance,
    defs: Definitions,
    run_id: Optional[str] = None,
) -> AnnotationOutcome:
    """Execute one sample's annotation in this process and report what it produced.

    *defs* is passed in rather than imported here because building it runs module discovery (which
    can hit the network), and importing this module must stay cheap for ``annotate --help``.

    Must run in a process that owns its own Polars pool (a CLI or the MCP worker), never inside
    the ASGI server or the MCP server itself.
    """
    started = datetime.now(timezone.utc)
    existing = instance.get_dynamic_partitions(user_vcf_partitions.name)
    if request.partition_key not in existing:
        instance.add_dynamic_partitions(user_vcf_partitions.name, [request.partition_key])

    job_name, reused = select_job(request, instance)
    job_def = defs.resolve_job_def(job_name)
    error: Optional[str] = None
    result = None
    try:
        result = job_def.execute_in_process(
            run_config=build_run_config(request, job_name),
            instance=instance,
            run_id=run_id,
            raise_on_error=False,
            tags={"dagster/partition": request.partition_key, "source": request.source_tag},
        )
    except Exception as exc:  # config errors raise before a run exists; report, do not crash
        error = f"{type(exc).__name__}: {exc}"

    success = bool(result is not None and result.success)
    if result is not None and not success:
        failures = [
            f"{event.step_key}: {event.event_specific_data.error.message.strip()}"
            for event in result.all_events
            if event.is_step_failure and event.event_specific_data is not None
        ]
        error = "; ".join(failures) or "run failed without a step failure event"

    sample_out = get_user_output_dir() / request.partition_key
    modules_dir = sample_out / "modules"
    manifest_path = modules_dir / "manifest.json"
    report = latest_report(sample_out / "reports", not_before=started.timestamp() - 1)

    outcome = AnnotationOutcome(
        run_id=result.run_id if result is not None else (run_id or ""),
        success=success,
        job_name=job_name,
        partition_key=request.partition_key,
        normalized_reused=reused,
        sample_output_dir=str(sample_out),
        modules_dir=str(modules_dir),
        report_path=str(report) if report else None,
        error=error,
        started_at=started.isoformat(),
        finished_at=_utc_now(),
    )
    # A manifest older than this run belongs to a previous one; reading it would report stale work.
    if manifest_path.exists() and manifest_path.stat().st_mtime >= started.timestamp() - 1:
        manifest = AnnotationManifest.model_validate_json(manifest_path.read_text())
        outcome.manifest_path = str(manifest_path)
        outcome.skipped_modules = dict(manifest.skipped_modules)
        outcome.failed_modules = dict(manifest.failed_modules)
        outcome.total_variants_annotated = manifest.total_variants_annotated
        outcome.total_variants_restored = manifest.total_variants_restored
    return outcome
