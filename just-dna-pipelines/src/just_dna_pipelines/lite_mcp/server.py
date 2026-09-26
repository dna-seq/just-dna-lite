"""The just-dna-lite MCP server.

Run it with ``uv run pipelines mcp`` (stdio, what Claude Code / Cursor / Codex launch) or
``uv run pipelines mcp --transport http`` (what ``uv run start`` serves beside the UI). Both
transports share the job store and ``DAGSTER_HOME``, so a job started through one is visible
through the other and in the Dagster UI.

Long work never runs inside a tool call. ``start_annotation`` records a job, spawns a worker
process and returns its id at once; ``get_job`` / ``wait_for_job`` report on it; ``get_results``,
``validate_module`` and ``get_variant_rows`` read what it left. A client that backgrounds long
calls (Claude Code moves any call past two minutes to a background task) can simply call
``wait_for_job`` and be told when it settles; one that does not can poll ``get_job``.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated, Any, Literal, Optional

import polars as pl
import typer
from dagster import DagsterEventType, DagsterInstance, DagsterRunStatus
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.lifespan import lifespan
from pydantic import BaseModel, Field

from just_dna_pipelines.annotation.annotation_runner import ensure_dagster_home
from just_dna_pipelines.annotation.resources import get_user_output_dir, get_workspace_root
from just_dna_pipelines.lite_mcp import catalog, jobs
from just_dna_pipelines.lite_mcp.catalog import InstallError, InstallResult, ModuleSummary, SampleListing
from just_dna_pipelines.lite_mcp.jobs import JobRecord, JobRequest, results_dir
from just_dna_pipelines.lite_mcp.validation import SampleInput, ValidationReport, validate_module_run
from just_dna_pipelines.urls import resolve_dagster_web_public_url

DEFAULT_HTTP_PORT = 3006
READ_ONLY = {"readOnlyHint": True, "openWorldHint": False}

INSTRUCTIONS = """\
just-dna-lite on this machine: the genomes it holds, the annotation modules it can run, and
background annotation jobs over them. Results include per-sample genotypes of real people; they
are the user's data, so quote them only as far as the task needs.

Typical loop for trying a module you just compiled:
  status -> list_samples -> install_module(compiled_dir) -> start_annotation(samples, [module])
  -> wait_for_job (or poll get_job) -> validate_module(job_id, module) -> get_variant_rows / get_results

A job runs in its own process and survives this session. Runs write into each sample's normal
output directory exactly as a web-UI run does (the latest run is what the UI shows) and appear in
the Dagster UI. validate_module findings are heuristics: each names the threshold that fired, and
"not_assessed" means the check could not run, never that it passed.
"""


def _version(dist: str) -> Optional[str]:
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return None


@lifespan
async def _dagster_home(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Export DAGSTER_HOME before the first tool runs; every job and status read needs the instance.

    `.env` is already loaded by then: `annotation.resources` calls `load_env()` at import, ahead of
    the module discovery that reads it.
    """
    ensure_dagster_home()
    yield {}


mcp = FastMCP(
    name="just-dna-lite",
    instructions=INSTRUCTIONS,
    version=_version("just-dna-pipelines"),
    lifespan=_dagster_home,
)


def _fail(message: str) -> ToolError:
    return ToolError(message)


class ServerStatus(BaseModel):
    server: str = "just-dna-lite"
    just_dna_lite_version: Optional[str]
    just_dna_pipelines_version: Optional[str]
    workspace_root: str
    dagster_home: str
    dagster_ui: str
    input_dir: str
    output_dir: str
    modules_discovered: int
    samples: int
    active_jobs: list[str]


@mcp.tool(annotations=READ_ONLY)
def status() -> ServerStatus:
    """Is just-dna-lite reachable, which checkout is it, and what does it hold. Call this first."""
    listing = catalog.list_samples()
    return ServerStatus(
        just_dna_lite_version=_version("just-dna-lite"),
        just_dna_pipelines_version=_version("just-dna-pipelines"),
        workspace_root=str(get_workspace_root()),
        dagster_home=os.environ["DAGSTER_HOME"],
        dagster_ui=resolve_dagster_web_public_url(),
        input_dir=listing.input_dir,
        output_dir=listing.output_dir,
        modules_discovered=len(catalog.module_names()),
        samples=len(listing.samples),
        active_jobs=[j.job_id for j in jobs.active_jobs()],
    )


@mcp.tool(annotations=READ_ONLY)
def list_samples(
    user: Annotated[Optional[str], Field(description="Only this user directory (e.g. 'local', 'anonymous')")] = None,
) -> SampleListing:
    """Genomes available for annotation, and configured public genomes not downloaded yet.

    Pass a sample's `sample_id` (user/sample) to start_annotation. A public genome's `alias` also
    works; the worker downloads it on first use (hundreds of MB).
    """
    return catalog.list_samples(user)


@mcp.tool(annotations=READ_ONLY)
def list_modules(
    contains: Annotated[Optional[str], Field(description="Case-insensitive substring filter on the name")] = None,
    refresh: Annotated[bool, Field(description="Re-run discovery first (a source that was unreachable at startup is skipped until then)")] = False,
) -> list[ModuleSummary]:
    """Annotation modules this installation discovers, with source, lead table and stated version/digest.

    Discovery runs once at server start and skips any source it cannot reach, so a network blip then
    leaves only the local modules listed. Pass refresh=true if a module you expect is missing.
    """
    if refresh:
        catalog.refresh()
    modules = catalog.list_modules()
    if contains:
        modules = [m for m in modules if contains.lower() in m.name.lower()]
    return modules


@mcp.tool(annotations={"destructiveHint": True, "idempotentHint": True, "openWorldHint": False})
def install_module(
    compiled_dir: Annotated[str, Field(description="A compile OUTPUT directory (holds weights.parquet or another lead parquet, and manifest.json)")],
    name: Annotated[Optional[str], Field(description="Directory name to install as; defaults to the directory's own name")] = None,
    replace: Annotated[bool, Field(description="Overwrite an earlier install of the same name made through this server")] = True,
) -> InstallResult:
    """Copy a compiled module into just-dna-lite so it can be annotated, without publishing it.

    The bytes are copied, not recompiled, so the digest you compiled is the digest that runs.
    Refuses a name another source already supplies (it would be silently shadowed) and refuses to
    overwrite a registry install. Re-installing the same name replaces the previous iteration.
    """
    try:
        return catalog.install_module(Path(compiled_dir), name=name, replace=replace)
    except InstallError as exc:
        raise _fail(str(exc)) from exc


@mcp.tool(annotations={"destructiveHint": True, "openWorldHint": False})
def uninstall_module(name: str) -> dict[str, Any]:
    """Remove a module installed through install_module. Registry installs are refused."""
    try:
        removed = catalog.uninstall_module(name)
    except InstallError as exc:
        raise _fail(str(exc)) from exc
    return {"name": name, "removed": removed}


class JobView(BaseModel):
    job_id: str
    status: str
    created_at: str
    started_at: Optional[str]
    finished_at: Optional[str]
    modules: list[str]
    samples: list[dict[str, Any]]
    error: Optional[str]
    log_path: str
    log_tail: list[str] = Field(default_factory=list)
    dagster_ui: str


def _dagster_steps(instance: DagsterInstance, run_id: str) -> dict[str, Any]:
    """Which steps of a Dagster run have started, finished or failed — the live progress signal."""
    run = instance.get_run_by_id(run_id)
    if run is None:
        return {"dagster_status": None, "steps_done": [], "step_running": None}
    done: list[str] = []
    started: list[str] = []
    failed: list[str] = []
    for entry in instance.all_logs(run_id):
        event = entry.dagster_event
        if event is None or event.step_key is None:
            continue
        if event.event_type == DagsterEventType.STEP_START:
            started.append(event.step_key)
        elif event.event_type == DagsterEventType.STEP_SUCCESS:
            done.append(event.step_key)
        elif event.event_type == DagsterEventType.STEP_FAILURE:
            failed.append(event.step_key)
    running = [s for s in started if s not in done and s not in failed]
    return {
        "dagster_status": run.status.value,
        "steps_done": done,
        "steps_failed": failed,
        "step_running": running[-1] if running else None,
    }


def _tail(path: Path, lines: int) -> list[str]:
    if lines <= 0 or not path.exists():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]


def _view(record: JobRecord, log_lines: int = 0) -> JobView:
    instance = DagsterInstance.get()
    samples: list[dict[str, Any]] = []
    for s in record.samples:
        row: dict[str, Any] = {
            "requested": s.requested,
            "sample_id": s.sample_id,
            "status": s.status,
            "run_id": s.run_id,
            "error": s.error,
        }
        if s.status == "running" and s.run_id:
            row.update(_dagster_steps(instance, s.run_id))
        if s.outcome is not None:
            row.update({
                "job_name": s.outcome.job_name,
                "normalized_reused": s.outcome.normalized_reused,
                "report_path": s.outcome.report_path,
                "skipped_modules": s.outcome.skipped_modules,
                "failed_modules": s.outcome.failed_modules,
                "variants_annotated": s.outcome.total_variants_annotated,
                "variants_restored": s.outcome.total_variants_restored,
            })
        samples.append(row)
    return JobView(
        job_id=record.job_id,
        status=record.status,
        created_at=record.created_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
        modules=record.request.modules,
        samples=samples,
        error=record.error,
        log_path=record.log_path,
        log_tail=_tail(Path(record.log_path), log_lines),
        dagster_ui=resolve_dagster_web_public_url(),
    )


def _job(job_id: str) -> JobRecord:
    try:
        return jobs.reconcile(jobs.read_job(job_id))
    except (KeyError, ValueError) as exc:
        raise _fail(str(exc)) from exc


@mcp.tool(annotations={"openWorldHint": False})
def start_annotation(
    samples: Annotated[list[str], Field(description="sample_id values from list_samples (user/sample), public-genome aliases, or VCF paths", min_length=1)],
    modules: Annotated[list[str], Field(description="Module names from list_modules", min_length=1)],
    user: Annotated[str, Field(description="User directory a VCF path or a public alias is placed under")] = "local",
    ensembl: Annotated[bool, Field(description="Also run the Ensembl DuckDB annotation (slow; needs the Ensembl cache)")] = False,
    reuse_normalized: Annotated[bool, Field(description="Skip re-normalizing a genome whose normalized parquet is current")] = True,
) -> JobView:
    """Start annotating the given genomes with the given modules. Returns a job id at once.

    The job runs in its own process, one genome after another, and survives this session. Follow
    it with wait_for_job or get_job, then read it with get_results / validate_module.
    """
    resolved, unknown = catalog.resolve_module_names(modules)
    if unknown:
        # Discovery may have missed a source at startup, or the module was installed by another process.
        catalog.refresh()
        resolved, unknown = catalog.resolve_module_names(modules)
    if unknown:
        raise _fail(f"Unknown module(s): {', '.join(unknown)}. Call list_modules (or install_module first).")
    record = jobs.create_job(
        JobRequest(samples=samples, modules=resolved, user=user, ensembl=ensembl, reuse_normalized=reuse_normalized)
    )
    return _view(record)


@mcp.tool(annotations=READ_ONLY)
def get_job(
    job_id: str,
    log_lines: Annotated[int, Field(description="How many trailing worker-log lines to include", ge=0, le=500)] = 20,
) -> JobView:
    """A job's status, each genome's progress (live Dagster steps while running), and errors."""
    return _view(_job(job_id), log_lines)


@mcp.tool(annotations=READ_ONLY)
def list_jobs(limit: Annotated[int, Field(ge=1, le=100)] = 10) -> list[JobView]:
    """Recent jobs, newest first."""
    return [_view(r) for r in jobs.list_jobs(limit)]


@mcp.tool(annotations=READ_ONLY)
async def wait_for_job(
    job_id: str,
    ctx: Context,
    timeout_seconds: Annotated[int, Field(ge=5, le=7200)] = 1800,
    poll_seconds: Annotated[int, Field(ge=1, le=60)] = 5,
) -> JobView:
    """Block until the job finishes (or the timeout passes), sending progress notifications.

    Progress keeps the call alive under clients that abort idle tool calls. On timeout the job keeps
    running; call again or poll get_job.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    record = _job(job_id)
    total = len(record.samples)
    while record.status in jobs.ACTIVE and loop.time() < deadline:
        finished = sum(1 for s in record.samples if s.status not in ("queued", "preparing", "running"))
        current = next((s for s in record.samples if s.status in ("preparing", "running")), None)
        message = (
            f"{record.status}: {finished}/{total} genomes done"
            + (f", now {current.sample_id or current.requested} ({current.status})" if current else "")
        )
        await ctx.report_progress(progress=finished, total=total, message=message)
        await asyncio.sleep(poll_seconds)
        record = _job(job_id)
    return _view(record, log_lines=20 if record.status in ("failed", "partial") else 0)


@mcp.tool(annotations={"destructiveHint": True, "openWorldHint": False})
def cancel_job(job_id: str) -> JobView:
    """Stop a queued or running job. Genomes already finished keep their results."""
    running = [s.run_id for s in _job(job_id).samples if s.status == "running" and s.run_id]
    record = jobs.cancel_job(job_id)
    instance = DagsterInstance.get()
    for run_id in running:
        run = instance.get_run_by_id(run_id)
        if run is not None and run.status in (DagsterRunStatus.STARTED, DagsterRunStatus.STARTING):
            instance.report_run_canceled(run, message="Canceled through the just-dna-lite MCP server")
    return _view(record)


class ModuleResult(BaseModel):
    module: str
    status: Literal["annotated", "skipped", "failed", "no_output"]
    reason: Optional[str] = None
    rows_written: Optional[int] = None
    rows_matched: Optional[int] = None
    rows_restored: Optional[int] = None
    parquet: Optional[str] = None


class SampleResult(BaseModel):
    sample_id: Optional[str]
    requested: str
    status: str
    error: Optional[str]
    report_path: Optional[str]
    normalized_reused: Optional[bool]
    modules: list[ModuleResult]


def _sample_module_path(record: JobRecord, sample_id: str, module: str) -> Path:
    return results_dir(Path(record.log_path).parent, sample_id) / f"{module}_weights.parquet"


def _module_result(record: JobRecord, run: jobs.SampleRun, module: str) -> ModuleResult:
    outcome = run.outcome
    if outcome is not None and module in outcome.failed_modules:
        return ModuleResult(module=module, status="failed", reason=outcome.failed_modules[module])
    if outcome is not None and module in outcome.skipped_modules:
        return ModuleResult(module=module, status="skipped", reason=outcome.skipped_modules[module])
    path = _sample_module_path(record, run.sample_id or "", module)
    if run.sample_id is None or not path.exists():
        return ModuleResult(module=module, status="no_output")
    lf = pl.scan_parquet(path)
    names = lf.collect_schema().names()
    counts = lf.select(
        pl.len().alias("written"),
        (pl.col("module").is_not_null().sum() if "module" in names else pl.len()).alias("matched"),
        ((pl.col("genotype_evidence") == "restored_hom_ref").sum() if "genotype_evidence" in names else pl.lit(0)).alias("restored"),
    ).collect().row(0, named=True)
    return ModuleResult(
        module=module,
        status="annotated",
        rows_written=counts["written"],
        rows_matched=counts["matched"],
        rows_restored=counts["restored"],
        parquet=str(path),
    )


@mcp.tool(annotations=READ_ONLY)
def get_results(job_id: str) -> list[SampleResult]:
    """Per genome: the report path, and per module whether it annotated, was skipped or failed, and how many rows matched.

    `rows_matched` counts rows that joined a module entry (restored hom-ref rows included, and also
    counted in `rows_restored`); `rows_written` also counts the sample's other calls at the module's
    positions, kept so "probed and did not match" differs from "never looked".
    """
    record = _job(job_id)
    return [
        SampleResult(
            sample_id=run.sample_id,
            requested=run.requested,
            status=run.status,
            error=run.error,
            report_path=run.outcome.report_path if run.outcome else None,
            normalized_reused=run.outcome.normalized_reused if run.outcome else None,
            modules=[_module_result(record, run, m) for m in record.request.modules],
        )
        for run in record.samples
    ]


def _module_info(module: str):
    info = catalog.module_infos().get(module)
    if info is None:
        catalog.refresh()
        info = catalog.module_infos().get(module)
    if info is None:
        raise _fail(f"Module {module!r} is not discovered any more; it may have been uninstalled or renamed.")
    return info


def _coverage_path(record: JobRecord, module: str) -> Path:
    return Path(record.log_path).parent / "validation" / f"{module}_coverage.parquet"


@mcp.tool(annotations=READ_ONLY)
def validate_module(job_id: str, module: str) -> ValidationReport:
    """Check one module's results across every genome in a finished job.

    Coverage: per authored locus, how many genomes matched, were restored hom-ref, were called with a
    genotype the module never authored, were called with a different ref, or had no call. Scores:
    each genome's summed weight and the distribution's shape (constant, one-sided, dominated by one
    variant, carried by inferred rows, shifted by a genotype everyone shares, outlier weights). Join
    health: join strategy, rows without coordinates, ambiguous or unmatchable phased rows, skips/failures.
    """
    record = _job(job_id)
    if module not in record.request.modules:
        raise _fail(f"Job {job_id} did not run {module!r}; it ran {', '.join(record.request.modules)}.")
    if record.status in jobs.ACTIVE:
        raise _fail(f"Job {job_id} is still {record.status}; wait_for_job first.")
    inputs: list[SampleInput] = []
    for run in record.samples:
        if run.sample_id is None:
            continue
        outcome = run.outcome
        inputs.append(
            SampleInput(
                sample_id=run.sample_id,
                normalized_path=get_user_output_dir() / run.sample_id / "user_vcf_normalized.parquet",
                annotated_path=_sample_module_path(record, run.sample_id, module),
                skipped_reason=outcome.skipped_modules.get(module) if outcome else None,
                failed_reason=(outcome.failed_modules.get(module) if outcome else None)
                or (run.error if run.status == "failed" else None),
            )
        )
    if not inputs:
        raise _fail(f"No genome in job {job_id} produced anything to validate.")
    return validate_module_run(_module_info(module), inputs, coverage_out=_coverage_path(record, module))


_ROW_COLUMNS = (
    "chrom", "start", "rsid", "ref", "alt", "genotype", "variant_key", "weight", "state", "direction",
    "clin_sig", "conclusion", "genotype_evidence", "restored_flank_bp", "GQ", "DP",
)


@mcp.tool(annotations=READ_ONLY)
def get_variant_rows(
    job_id: str,
    module: str,
    sample_id: Annotated[Optional[str], Field(description="Only this genome; default is every genome in the job")] = None,
    matched_only: Annotated[bool, Field(description="Only rows that matched a module entry")] = True,
    locus: Annotated[Optional[str], Field(description="Only this variant_key / rsid")] = None,
    coverage_status: Annotated[
        Optional[Literal["called_matched", "restored_hom_ref", "called_unmatched", "called_ref_mismatch", "not_observed"]],
        Field(description="Return the coverage matrix rows with this status instead (run validate_module first)"),
    ] = None,
    limit: Annotated[int, Field(ge=1, le=2000)] = 200,
    offset: Annotated[int, Field(ge=0)] = 0,
) -> dict[str, Any]:
    """Per-genome rows for one module: each sample's genotype at each module variant and the weight it got.

    These are real people's genotypes; ask for what the question needs. With `coverage_status`, reads
    the (sample, locus) matrix validate_module wrote, e.g. every locus called but never matched.
    """
    record = _job(job_id)
    if coverage_status is not None:
        path = _coverage_path(record, module)
        if not path.exists():
            raise _fail(f"No coverage matrix for {module} in job {job_id}; call validate_module first.")
        lf = pl.scan_parquet(path).filter(pl.col("status") == coverage_status)
        if sample_id:
            lf = lf.filter(pl.col("sample_id") == sample_id)
        if locus:
            lf = lf.filter(pl.col("locus") == locus)
        total = lf.select(pl.len()).collect().item()
        return {"total": total, "offset": offset, "rows": lf.slice(offset, limit).collect().to_dicts()}

    frames: list[pl.LazyFrame] = []
    for run in record.samples:
        if run.sample_id is None or (sample_id and run.sample_id != sample_id):
            continue
        path = _sample_module_path(record, run.sample_id, module)
        if not path.exists():
            continue
        lf = pl.scan_parquet(path)
        names = lf.collect_schema().names()
        if matched_only and "module" in names:
            lf = lf.filter(pl.col("module").is_not_null())
        if locus:
            keys = [c for c in ("variant_key", f"rsid_{module}", "rsid") if c in names]
            lf = lf.filter(pl.any_horizontal([pl.col(c) == locus for c in keys]))
        cols = [c for c in _ROW_COLUMNS if c in names]
        frames.append(
            lf.select(
                pl.lit(run.sample_id).alias("sample_id"),
                *[pl.col(c).list.join("/").alias(c) if c == "genotype" else pl.col(c) for c in cols],
            )
        )
    if not frames:
        raise _fail(f"No output for {module} in job {job_id}" + (f" for {sample_id}" if sample_id else ""))
    combined = pl.concat(frames, how="diagonal_relaxed")
    total = combined.select(pl.len()).collect().item()
    return {"total": total, "offset": offset, "rows": combined.slice(offset, limit).collect().to_dicts()}


cli = typer.Typer(add_completion=False, help="Serve the just-dna-lite MCP server.")


@cli.command()
def serve(
    transport: Annotated[str, typer.Option(help="stdio (for an MCP client to launch) or http")] = "stdio",
    host: Annotated[str, typer.Option(help="HTTP bind address")] = "127.0.0.1",
    port: Annotated[Optional[int], typer.Option(help=f"HTTP port (default $JUST_DNA_MCP_PORT or {DEFAULT_HTTP_PORT})")] = None,
) -> None:
    """Serve over stdio (default) or streamable HTTP at http://HOST:PORT/mcp."""
    if transport == "stdio":
        mcp.run(transport="stdio", show_banner=False)
        return
    if transport != "http":
        raise typer.BadParameter("transport must be 'stdio' or 'http'")
    resolved_port = port or int(os.getenv("JUST_DNA_MCP_PORT", str(DEFAULT_HTTP_PORT)))
    mcp.run(transport="http", host=host, port=resolved_port, show_banner=False)


def main() -> None:
    cli()
