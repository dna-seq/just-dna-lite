from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Annotated, Dict, Optional

import typer
from rich.console import Console
from rich.table import Table

from just_dna_pipelines.runtime import environ_guard, load_env

load_env()  # this checkout's .env (or .env.template), never one above it
# just-dna-registry calls a bare load_dotenv() at import, which climbs above this checkout; import it
# once under environ_guard so only our own load_env() decides the configuration.
with environ_guard():
    import just_dna_registry.client_cli  # noqa: F401

from just_dna_lite.dagster_sqlite import DagsterDatabaseKeepalive
from just_dna_lite.dagster_maintenance import human_bytes, prune_history, resolve_dagster_home
from just_dna_lite.frontend_runtime import node_too_old_for_dev_server
from just_dna_lite.inotify import CHECKED_ENV as INOTIFY_CHECKED_ENV, inotify_budget, inotify_preflight
from just_dna_lite.process import (
    detached_popen_kwargs,
    dg_dev_argv,
    find_dagster_instance_pids,
    find_port_listeners,
    install_launcher_signal_handlers,
    lite_mcp_http_argv,
    process_name,
    reap_dagster_instance,
    reap_webui_leftovers,
    shutdown_managed_processes,
    terminate_pids,
    webui_dev_argv,
)
from just_dna_pipelines.annotation.cli_annotate import annotate as annotate_cmd
from just_dna_pipelines.annotation.cli_annotate import annotate_main
from just_dna_pipelines.annotation.hard_regions import HARD_REGIONS_DESCRIPTION, ensure_hard_regions
from just_dna_pipelines.annotation.module_cache import (
    clear_hf_module_cache,
    get_app_version,
)
from just_dna_pipelines.agents.cli import app as agent_app
from just_dna_pipelines.module_compiler.cli import app as module_compiler_app
from just_dna_pipelines.v1_port.cli import app as v1_port_app
from just_dna_pipelines.predictions.cli import app as predict_app
from just_dna_enricher.cli import app as enricher_app
from just_dna_pipelines.lite_mcp.server import DEFAULT_HTTP_PORT as DEFAULT_MCP_PORT
from just_dna_pipelines.lite_mcp.server import serve as mcp_serve
from just_dna_enricher.caches import CACHE_LANES, prepare_caches
from just_dna_enricher.download import ensure_snapshot
from just_dna_enricher.locations import ensembl_release_label
from just_dna_enricher.resolver import EnsemblReferenceError
from just_dna_pipelines.annotation.resources import get_default_ensembl_cache_dir
from just_dna_registry.client_cli import app as registry_client_app
from just_dna_lite.registry_org_cli import app as registry_org_app

# Organization management (0.9.1) as a nested group: `pipelines registry org …`.
registry_client_app.add_typer(registry_org_app, name="org")

app = typer.Typer(
    name="pipelines",
    help="Pipelines - Genomic analysis stack",
    no_args_is_help=True,
    add_completion=False
)
app.add_typer(module_compiler_app, name="module")
app.add_typer(v1_port_app, name="v1-port")
# Genome prediction models: `pipelines predict run --user U --sample S` (variant effects, own report).
app.add_typer(predict_app, name="predict")
app.add_typer(agent_app, name="agent")
# The enricher's own Typer app, mounted whole rather than re-declared. It is the authoring
# tier that fills `resolution.csv` and the 0.5 fact sidecars, which `module compile` then
# consumes with no reference and no network — the replacement for injecting an Ensembl
# DuckDB, which just-dna-compiler deprecates for removal at 1.0. Mounting the app whole
# means new enricher commands surface here without further wiring.
app.add_typer(enricher_app, name="enrich")
# Registry reference client (list/download/publish/import-module/find-by-hash/
# update-module-version). Reads REGISTRY_URL / REGISTRY_TOKEN from flags, env, or .env.
app.add_typer(registry_client_app, name="registry")

# Same callback as ``uv run annotate``; discovery stays inside the command body.
app.command("annotate")(annotate_cmd)
# The MCP server (samples, modules, annotation jobs, validation). stdio by default, which is what an
# MCP client launches: `claude mcp add just-dna-lite -- uv run --project <checkout> pipelines mcp`.
app.command("mcp")(mcp_serve)


@app.command("list-modules")
def list_modules() -> None:
    """List the annotation modules discovered from the configured sources.

    This is the check that matters after publishing: it answers whether the app can *see* a module,
    not merely whether its files landed. A module that uploaded but does not appear here is not
    discoverable, which for the app's purposes means not published.

    `just_dna_pipelines.cli` defines the same command, but that entry point is shadowed by this one
    (both packages install a `pipelines` script and the root package wins), so it was unreachable.
    """
    # Imported inside the command on purpose: `annotation.hf_modules` runs discovery — and therefore
    # network I/O — at import time, and no other subcommand should pay for that.
    from just_dna_pipelines.cli import list_modules as _list_modules

    _list_modules()


@app.command("clear-module-cache")
def clear_module_cache() -> None:
    """Delete the locally cached HuggingFace annotator-module data.

    Forces the next run to re-download the currently published module versions.
    Use after republishing a module in place (same version); version bumps are
    invalidated automatically on startup.
    """
    removed = clear_hf_module_cache()
    if removed:
        typer.secho(f"Cleared HF module cache for: {', '.join(removed)}", fg=typer.colors.GREEN)
    else:
        typer.secho("No cached HF module repos found — nothing to clear.", fg=typer.colors.YELLOW)
    typer.echo(f"Current app version: {get_app_version()}")

DEFAULT_DAGSTER_PORT = 3005


def _resolve_dagster_port(port: Optional[int]) -> int:
    """Resolve the Dagster UI port from CLI override, env var, or default."""
    if port is not None:
        return port

    port_text = os.getenv("DAGSTER_PORT", "").strip()
    if not port_text:
        return DEFAULT_DAGSTER_PORT

    try:
        return int(port_text)
    except ValueError as exc:
        raise typer.BadParameter("DAGSTER_PORT must be an integer") from exc


def _ensure_dagster_config(dagster_home: Path) -> None:
    """
    Ensure dagster.yaml exists with proper configuration.
    
    Creates the config file and required subdirectories if missing,
    enabling auto-materialization and other important features.
    Always ensures required subdirectories exist even if config already present.
    """
    dagster_home.mkdir(parents=True, exist_ok=True)
    # Always ensure logs directory exists — Dagster telemetry writes here
    # and will crash if it's missing, even if dagster.yaml already exists
    (dagster_home / "logs").mkdir(parents=True, exist_ok=True)
    
    config_file = dagster_home / "dagster.yaml"
    
    if config_file.exists():
        # Ensure telemetry is disabled in existing config to avoid
        # RotatingFileHandler errors when logs/event.log path issues occur
        config_text = config_file.read_text(encoding="utf-8")
        if "telemetry:" not in config_text:
            config_text = config_text.rstrip() + "\n\ntelemetry:\n  enabled: false\n"
            config_file.write_text(config_text, encoding="utf-8")
        return
    
    config_content = """# Dagster instance configuration
# Storage defaults to DAGSTER_HOME

# Enable auto-materialization for assets with AutoMaterializePolicy
auto_materialize:
  enabled: true
  minimum_interval_seconds: 60

# Disable telemetry to avoid RotatingFileHandler errors
telemetry:
  enabled: false
"""
    
    config_file.write_text(config_content, encoding="utf-8")
    typer.secho(f"✅ Created Dagster config at {config_file}", fg=typer.colors.GREEN)


def _find_workspace_root(start: Path) -> Optional[Path]:
    """Find the workspace root by searching for a pyproject.toml with uv workspace config."""
    for candidate in [start, *start.parents]:
        pyproject = candidate / "pyproject.toml"
        if not pyproject.exists():
            continue
        text = pyproject.read_text(encoding="utf-8")
        if "[tool.uv.workspace]" in text:
            return candidate
    return None


def _run_managed_foreground(command: list[str], dagster_home: Path, cwd: Path) -> int:
    """Run a foreground child and tear down its whole tree on Ctrl+C."""

    proc = subprocess.Popen(command, cwd=cwd, **detached_popen_kwargs())
    processes = [proc]

    def _force(_signum: int, _frame: object) -> None:
        shutdown_managed_processes(processes, dagster_home=dagster_home, force=True)
        raise SystemExit(1)

    def _first(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    install_launcher_signal_handlers(_first, _force)
    try:
        return proc.wait()
    except KeyboardInterrupt:
        typer.secho("\nShutting down Dagster...", fg=typer.colors.YELLOW)
        shutdown_managed_processes(processes, dagster_home=dagster_home)
        return 0
    finally:
        shutdown_managed_processes(processes, dagster_home=dagster_home, force=True)


def _kill_port_owner(port: int) -> None:
    """Stop whatever is listening on *port*."""
    pids = find_port_listeners(port)
    if not pids:
        return
    typer.secho(
        f"Stopping {', '.join(f'{pid} ({process_name(pid)})' for pid in pids)} on port {port}...",
        fg=typer.colors.YELLOW,
    )
    terminate_pids(pids)


def _env_flag_enabled(name: str) -> bool:
    """Return true when an env flag is explicitly enabled."""

    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


@app.command("dagster")
def start_dagster(
    file: Annotated[
        str,
        typer.Option(
            "--file",
            "-f",
            help="The Dagster file to run.",
        ),
    ] = "just-dna-pipelines/src/just_dna_pipelines/annotation/definitions.py",
    port: Annotated[
        Optional[int],
        typer.Option(
            "--port",
            "-p",
            help="Port for the Dagster UI. Defaults to DAGSTER_PORT or 3005.",
        ),
    ] = None,
    host: Annotated[
        str,
        typer.Option(
            "--host",
            help="Host for the Dagster webserver. Use 0.0.0.0 in containers.",
        ),
    ] = "",
) -> None:
    """Start Dagster Dev (UI + Daemon) for the specified file."""
    root = _find_workspace_root(Path.cwd())
    if root is None:
        root = Path.cwd()
    
    dagster_file = root / file
    if not dagster_file.exists():
        # Try relative to current dir if not found from root
        dagster_file = Path.cwd() / file
        if not dagster_file.exists():
            raise typer.BadParameter(f"Dagster file not found: {file}")

    dagster_host = host or os.getenv("DAGSTER_HOST", "127.0.0.1")
    dagster_port = _resolve_dagster_port(port)

    # Set DAGSTER_HOME to data/interim/dagster
    dagster_home = os.getenv("DAGSTER_HOME", "data/interim/dagster")
    if not Path(dagster_home).is_absolute():
        dagster_home = str((root / dagster_home).resolve())
    
    dagster_home_path = Path(dagster_home)
    _ensure_dagster_config(dagster_home_path)
    os.environ["DAGSTER_HOME"] = dagster_home
    
    typer.secho(f"🚀 Starting Dagster Dev (UI + Daemon) for {file}...", fg=typer.colors.BRIGHT_CYAN, bold=True)
    typer.echo(f"📁 Dagster home: {dagster_home}")
    _kill_port_owner(dagster_port)
    
    typer.secho(f"\n💡 Dagster UI will be available at: http://{dagster_host}:{dagster_port}\n", fg=typer.colors.GREEN, bold=True)

    leftover = reap_dagster_instance(dagster_home_path)
    if leftover:
        typer.secho(
            f"🧹 Killed {len(leftover)} leftover Dagster process(es) from a previous session.",
            fg=typer.colors.YELLOW,
        )
    
    # cwd=root, as in start_all: definitions.py resolves some paths against the working directory.
    with DagsterDatabaseKeepalive(dagster_home_path):
        exit_code = _run_managed_foreground(
            dg_dev_argv(dagster_file, dagster_port, dagster_host),
            dagster_home=dagster_home_path,
            cwd=root,
        )
    if exit_code != 0:
        raise typer.Exit(exit_code)


def _start_lite_mcp_http(child_processes: list[subprocess.Popen], root: Path) -> Optional[str]:
    """Serve the MCP server over HTTP beside the UI; returns its URL, or None when not started.

    Off with ``JUST_DNA_MCP_HTTP=false``. A port that is already listening is left alone rather than
    killed: it is most likely this stack's MCP server from another terminal, and the stdio transport
    works without it anyway.
    """
    if os.getenv("JUST_DNA_MCP_HTTP", "true").strip().lower() in ("0", "false", "no", "off"):
        return None
    host = os.getenv("JUST_DNA_MCP_HOST", "127.0.0.1")
    port = int(os.getenv("JUST_DNA_MCP_PORT", str(DEFAULT_MCP_PORT)))
    if find_port_listeners(port):
        typer.secho(
            f"MCP port {port} is already in use; not starting the MCP HTTP server "
            "(set JUST_DNA_MCP_PORT to use another).",
            fg=typer.colors.YELLOW,
        )
        return None
    typer.secho("🔌 Starting just-dna-lite MCP server (HTTP)...", fg=typer.colors.BRIGHT_CYAN)
    child_processes.append(
        subprocess.Popen(lite_mcp_http_argv(host, port), cwd=root, **detached_popen_kwargs())
    )
    return f"http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{port}/mcp"


@app.command("start")
def start_all(
    granian: Annotated[
        bool, typer.Option("--granian", help="Use Granian for the backend.")
    ] = True,
    dagster_file: Annotated[
        str,
        typer.Option(
            "--dagster-file",
            "-f",
            help="The Dagster file to run.",
        ),
    ] = "just-dna-pipelines/src/just_dna_pipelines/annotation/definitions.py",
    dagster_port: Annotated[
        Optional[int], typer.Option("--dagster-port", help="Port for the Dagster UI. Defaults to DAGSTER_PORT or 3005.")
    ] = None,
    dagster_host: Annotated[
        str,
        typer.Option("--dagster-host", help="Host for the Dagster webserver. Use 0.0.0.0 in containers."),
    ] = "",
    immutable: Annotated[
        bool,
        typer.Option("--immutable", help="Start in immutable (public demo) mode. Disables file uploads and serves only pre-configured public genomes."),
    ] = False,
) -> None:
    """Start the full stack: Dagster (Pipelines) and Reflex UI.

    Use --immutable for public demos, workshops, or conferences.
    Equivalent to setting JUST_DNA_IMMUTABLE_MODE=true in .env.
    """
    if immutable:
        os.environ["JUST_DNA_IMMUTABLE_MODE"] = "true"

    root = _find_workspace_root(Path.cwd())
    if root is None:
        root = Path.cwd()

    resolved_dagster_host = dagster_host or os.getenv("DAGSTER_HOST", "127.0.0.1")
    resolved_dagster_port = _resolve_dagster_port(dagster_port)

    if granian:
        os.environ["REFLEX_USE_GRANIAN"] = "true"

    # Set DAGSTER_HOME
    dagster_home = os.getenv("DAGSTER_HOME", "data/interim/dagster")
    if not Path(dagster_home).is_absolute():
        dagster_home = str((root / dagster_home).resolve())
    
    dagster_home_path = Path(dagster_home)
    _ensure_dagster_config(dagster_home_path)
    os.environ["DAGSTER_HOME"] = dagster_home

    node_problem = node_too_old_for_dev_server()
    if node_problem:
        typer.secho(node_problem, fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    inotify_refusal, inotify_warning = inotify_preflight(inotify_budget())
    if inotify_refusal:
        typer.secho(inotify_refusal, fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    if inotify_warning:
        typer.secho(inotify_warning, fg=typer.colors.YELLOW, err=True)
    os.environ[INOTIFY_CHECKED_ENV] = "1"

    typer.secho("🏗️  Starting full Just DNA Pipelines stack...", fg=typer.colors.BRIGHT_MAGENTA, bold=True)

    leftover = reap_dagster_instance(dagster_home_path)
    if leftover:
        typer.secho(
            f"🧹 Killed {len(leftover)} leftover Dagster process(es) from a previous session.",
            fg=typer.colors.YELLOW,
        )

    leftover_ui = reap_webui_leftovers(root)
    if leftover_ui:
        typer.secho(
            f"🧹 Killed {len(leftover_ui)} leftover Web UI process(es) from a previous session.",
            fg=typer.colors.YELLOW,
        )

    # 0. Optionally clean up orphan processes
    ports_to_clean = [3000, 3001, 8000, resolved_dagster_port]
    if _env_flag_enabled("JUST_DNA_START_KILL_PORTS"):
        typer.echo(f"🧹 Cleaning up existing processes on ports {', '.join(map(str, ports_to_clean))}...")
        for port in ports_to_clean:
            _kill_port_owner(port)
        web_dir = root / "webui" / ".web"
        if web_dir.exists():
            shutil.rmtree(web_dir)
            typer.echo(f"🧹 Removed stale Reflex build directory: {web_dir}")
    else:
        typer.echo(
            "Port cleanup is disabled. Set JUST_DNA_START_KILL_PORTS=true to "
            f"stop existing listeners on ports {', '.join(map(str, ports_to_clean))} before startup."
        )

    # 1. Start the UI in the background via the workspace script
    typer.secho("🚀 Starting Reflex Web UI...", fg=typer.colors.BRIGHT_CYAN)
    child_processes: list[subprocess.Popen] = []
    exit_code = 0
    # Holds Dagster's shared SQLite files open so their WAL files are not deleted and rebuilt
    # between queries, which made every process on them fail with "database is locked".
    keepalive = DagsterDatabaseKeepalive(dagster_home_path)

    def _force(_signum: int, _frame: object) -> None:
        shutdown_managed_processes(
            child_processes,
            dagster_home=dagster_home_path,
            workspace_root=root,
            force=True,
        )
        raise SystemExit(1)

    def _first(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    install_launcher_signal_handlers(_first, _force)
    try:
        ui_proc = subprocess.Popen(
            webui_dev_argv(),
            cwd=root,
            **detached_popen_kwargs(),
        )
        child_processes.append(ui_proc)

        # Give it a moment to initialize
        time.sleep(2)

        mcp_url = _start_lite_mcp_http(child_processes, root)

        # 2. Start Dagster as the foreground child. The root launcher owns shutdown
        # ordering so child processes can flush and exit before the root exits.
        typer.secho(f"🧬 Starting Dagster Pipelines for {dagster_file}...", fg=typer.colors.BRIGHT_BLUE)
        typer.echo(f"📁 Dagster home: {dagster_home}")
        dagster_file_path = root / dagster_file

        typer.echo("\n" + "═" * 65)
        typer.secho("🚀 Just DNA Pipelines Stack is starting!", fg=typer.colors.GREEN, bold=True)
        if os.getenv("JUST_DNA_IMMUTABLE_MODE", "").lower() in ("true", "1", "yes"):
            typer.secho("🔒 IMMUTABLE MODE — file uploads disabled, public genomes only", fg=typer.colors.YELLOW, bold=True)
        typer.secho("⏳ Note: Reflex UI takes ~20s to initialize.", fg=typer.colors.YELLOW)
        typer.echo("  • Web UI:       http://localhost:3000 (use the URL Reflex prints if 3000 is taken)")
        typer.echo(f"  • Pipelines UI: http://localhost:{resolved_dagster_port} (Dagster Dashboard)")
        typer.echo("  • Backend API:  http://localhost:8000+ (Reflex Internal, auto-selected)")
        if mcp_url:
            typer.echo(f"  • MCP server:   {mcp_url} (claude mcp add --transport http just-dna-lite {mcp_url})")
        typer.echo("═" * 65 + "\n")

        # Clean up orphaned STARTED runs from previous session
        try:
            from dagster import DagsterInstance, DagsterRunStatus, RunsFilter
            instance = DagsterInstance.get()
            started_records = instance.get_run_records(
                filters=RunsFilter(statuses=[DagsterRunStatus.STARTED]),
                limit=100,
            )
            webui_started = [r for r in started_records if r.dagster_run.tags.get("source") == "webui"]
            if webui_started:
                typer.echo(f"🧹 Cleaning up {len(webui_started)} orphaned webui run(s) from previous session...")
                for record in webui_started:
                    run = record.dagster_run
                    instance.report_run_canceled(run, message="Orphaned run from previous session")
                    typer.echo(f"  ✓ Canceled {run.run_id[:8]}...")
        except Exception:
            pass

        dagster_proc = subprocess.Popen(
            dg_dev_argv(dagster_file_path, resolved_dagster_port, resolved_dagster_host),
            cwd=root,
            **detached_popen_kwargs(),
        )
        child_processes.append(dagster_proc)
        exit_code = dagster_proc.wait()
    except KeyboardInterrupt:
        typer.secho("\nShutting down...", fg=typer.colors.YELLOW)
        shutdown_managed_processes(
            child_processes,
            dagster_home=dagster_home_path,
            workspace_root=root,
        )
        return
    finally:
        shutdown_managed_processes(
            child_processes,
            dagster_home=dagster_home_path,
            workspace_root=root,
            force=True,
        )
        keepalive.close()

    if exit_code != 0:
        raise typer.Exit(exit_code)


def _ensembl_lane_dir(cache_dir: Optional[str]) -> Path:
    """The Ensembl snapshot directory: ``<cache_dir>/ensembl_variations`` when given, else the lane's."""
    if cache_dir:
        return Path(cache_dir) / "ensembl_variations"
    return get_default_ensembl_cache_dir()


@app.command("prepare-caches")
def prepare_caches_cmd(
    use: str = typer.Option(
        "unstated",
        "--use",
        help="Declared use for the licence-gated lanes: unstated | non-commercial | commercial.",
    ),
    lane: Optional[list[str]] = typer.Option(
        None,
        "--lane", "-l",
        help="Only these lanes (repeatable). Default: every lane the enricher registers.",
    ),
) -> None:
    """
    Provision every enricher reference cache this machine can have, plus our GIAB mask.

    `just-dna-enricher cache prepare` (`caches.prepare_caches`) with two things it lacks: `.env`
    is loaded through our bounded `load_env()` before any lane resolves its directory, and the
    GIAB hard-regions mask restoration reads is provisioned beside the lanes. It pulls the
    published snapshots, follows a newer published release of a pulled lane (RM420), and builds
    the lanes that are unpublished for recorded reasons, so it is safe on every deploy. The
    Ensembl snapshot is the `ensembl` lane (`--lane ensembl`); `pipelines enrich cache status`
    says which release each lane holds.

    Exit 1 if any lane failed. A lane that cannot run unattended (an operator-held workbook, a
    personal key) is reported as such and is not a failure.

    Examples:

        uv run pipelines prepare-caches --use non-commercial
        uv run pipelines prepare-caches --lane clinvar --lane clinpgx --use non-commercial
    """
    # The enricher's resolvers evaluate their default cache directory before they call
    # `load_env()` themselves, so `.env` has to be loaded first or the first lane lands in the
    # platformdirs default (the `cache pull` trap in CLAUDE.md).
    load_env()
    by_name = {cache_lane.name: cache_lane for cache_lane in CACHE_LANES}
    if lane:
        unknown = sorted(set(lane) - set(by_name))
        if unknown:
            typer.secho(
                f"Unknown lane(s): {', '.join(unknown)}. Known: {', '.join(by_name)}",
                fg=typer.colors.RED, err=True,
            )
            raise typer.Exit(2)
        selected = [by_name[name] for name in lane]
    else:
        selected = None

    outcomes = prepare_caches(selected, declared_use=use)

    table = Table(title="Enricher caches")
    for column in ("lane", "ready", "route", "path", "detail"):
        table.add_column(column)
    failed = 0
    for outcome in outcomes:
        if outcome.ready is True:
            ready = "[green]yes[/green]"
        elif outcome.ready is False:
            ready, failed = "[red]no[/red]", failed + 1
        else:
            ready = "[yellow]not unattended[/yellow]"
        table.add_row(
            outcome.lane, ready, outcome.route,
            str(outcome.path) if outcome.path else "",
            outcome.detail or "",
        )
    # Ours, not an enricher lane: the regions where a missing call on a genome is not read as
    # reference (restoration and the phenotype caller). Fetched on first use otherwise; provisioning
    # it here keeps an offline deployment from annotating without it.
    if not lane:
        try:
            mask_path = ensure_hard_regions()
            table.add_row("hard_regions", "[green]yes[/green]", "giab", str(mask_path), HARD_REGIONS_DESCRIPTION)
        except Exception as exc:  # network or disk; reported like any failed lane
            failed += 1
            table.add_row("hard_regions", "[red]no[/red]", "giab", "", f"{type(exc).__name__}: {exc}")
    Console().print(table)
    if failed:
        raise typer.Exit(1)


@app.command("build-duckdb")
def build_duckdb(
    cache_dir: Optional[str] = typer.Option(
        None,
        "--cache-dir", "-c",
        help="Override cache directory. Defaults to JUST_DNA_PIPELINES_CACHE_DIR env var "
             "or ~/.cache/just-dna-pipelines.",
    ),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="Rebuild even if a DuckDB already exists.",
    ),
) -> None:
    """
    Build (or rebuild) the Ensembl DuckDB from the local parquet cache.

    Creates lightweight VIEWs over the parquet files — no data is copied,
    so the database is tiny and queries stream directly from parquet.

    Requires the Ensembl snapshot to be present
    (``uv run pipelines prepare-caches --lane ensembl``, or ``ensembl-setup``).

    Examples:

        uv run pipelines build-duckdb
        uv run pipelines build-duckdb --force
        uv run pipelines build-duckdb --cache-dir /data/my-cache
    """
    import logging

    from rich.console import Console as RichConsole

    from just_dna_pipelines.annotation.duckdb_assets import build_duckdb_from_parquet

    rich = RichConsole()
    logger = logging.getLogger("just_dna_pipelines.cli")

    ensembl_dir = _ensembl_lane_dir(cache_dir)
    data_dir = ensembl_dir / "data"
    duckdb_path = ensembl_dir / "ensembl_variations.duckdb"

    if not data_dir.exists() or not any(data_dir.glob("*.parquet")):
        rich.print(
            f"[red]Error: Ensembl parquet cache not found at {data_dir}[/red]\n"
            "[dim]Run [bold]uv run pipelines prepare-caches --lane ensembl[/bold] first.[/dim]"
        )
        raise typer.Exit(1)

    if duckdb_path.exists() and not force:
        size_mb = duckdb_path.stat().st_size / (1024 * 1024)
        rich.print(
            f"[green]DuckDB already exists:[/green] {duckdb_path} ({size_mb:.1f} MB)\n"
            "[dim]Use --force to rebuild.[/dim]"
        )
        return

    if duckdb_path.exists():
        rich.print(f"[yellow]Removing existing DuckDB: {duckdb_path}[/yellow]")
        duckdb_path.unlink()

    rich.print(f"\n[bold]Building Ensembl DuckDB[/bold]")
    rich.print(f"  Source : [cyan]{ensembl_dir}[/cyan]")
    rich.print(f"  Output : [cyan]{duckdb_path}[/cyan]\n")

    _, metadata = build_duckdb_from_parquet(ensembl_dir, duckdb_path, logger=logger)

    rich.print(f"[bold green]Done![/bold green]")
    rich.print(f"  Views created    : {metadata['num_views']} ({metadata['view_names']})")
    rich.print(f"  Parquet files    : {metadata['total_parquet_files']}")
    rich.print(f"  Database size    : {metadata['db_size_mb']} MB")
    if "build_duration_sec" in metadata:
        rich.print(f"  Build time       : {metadata['build_duration_sec']:.1f}s")
        rich.print(f"  Peak memory      : {metadata['peak_memory_mb']:.0f} MB")
    rich.print()


@app.command("ensembl-setup")
def ensembl_setup(
    cache_dir: Optional[str] = typer.Option(
        None,
        "--cache-dir", "-c",
        help="Override cache directory. Defaults to JUST_DNA_PIPELINES_CACHE_DIR env var "
             "or ~/.cache/just-dna-pipelines.",
    ),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="Rebuild the DuckDB even if one exists.",
    ),
) -> None:
    """
    Full Ensembl setup: provision the snapshot, then build the DuckDB over it.

      1. the enricher's `ensembl` lane (`download.ensure_snapshot`) pulls
         just-dna-seq/ensembl_variations_split, keeping a file only where the
         snapshot's manifest.json attests it, and refetching a truncated one
      2. build-duckdb creates the DuckDB catalog over the parquet

    The snapshot is the enricher's: `uv run pipelines enrich cache status` says which
    release it holds, and `uv run pipelines enrich cache pull --only ensembl` follows
    a newer one. --force rebuilds the DuckDB.

    Examples:

        uv run pipelines ensembl-setup
        uv run pipelines ensembl-setup --force
        uv run pipelines ensembl-setup --cache-dir /data/my-cache
    """
    import logging

    from rich.console import Console as RichConsole

    from just_dna_pipelines.annotation.duckdb_assets import build_duckdb_from_parquet

    rich = RichConsole()
    logger = logging.getLogger("just_dna_pipelines.cli")
    ensembl_dir = _ensembl_lane_dir(cache_dir)

    rich.print("[bold]Step 1/2: Provision the Ensembl snapshot[/bold]\n")
    try:
        ensure_snapshot(ensembl_dir)
    except EnsemblReferenceError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    rich.print(f"  {ensembl_dir}: {ensembl_release_label(ensembl_dir) or 'release not stated'}")

    rich.print(f"\n[bold]Step 2/2: Build DuckDB[/bold]\n")
    duckdb_path = ensembl_dir / "ensembl_variations.duckdb"

    if duckdb_path.exists() and not force:
        size_mb = duckdb_path.stat().st_size / (1024 * 1024)
        rich.print(f"[green]DuckDB already exists:[/green] {duckdb_path} ({size_mb:.1f} MB) — skipping.")
    else:
        if duckdb_path.exists():
            duckdb_path.unlink()
        rich.print(f"  Source : [cyan]{ensembl_dir}[/cyan]")
        rich.print(f"  Output : [cyan]{duckdb_path}[/cyan]\n")

        _, metadata = build_duckdb_from_parquet(ensembl_dir, duckdb_path, logger=logger)

        rich.print(f"  Views  : {metadata['num_views']} ({metadata['view_names']})")
        rich.print(f"  Files  : {metadata['total_parquet_files']}")
        rich.print(f"  Size   : {metadata['db_size_mb']} MB")
        if "build_duration_sec" in metadata:
            rich.print(f"  Time   : {metadata['build_duration_sec']:.1f}s")

    rich.print(f"\n[bold green]Ensembl setup complete![/bold green]\n")


@app.command("sync-vcf-partitions")
def sync_vcf_partitions_cmd() -> None:
    """
    Scan data/input/users/ for VCF files and create Dagster partitions.
    
    This is useful when you add new VCF files and want to make them
    available for annotation without waiting for the sensor.
    """
    from just_dna_pipelines.annotation.utils import sync_vcf_partitions
    
    # Set DAGSTER_HOME
    root = _find_workspace_root(Path.cwd())
    if root is None:
        root = Path.cwd()
    
    dagster_home = os.getenv("DAGSTER_HOME", "data/interim/dagster")
    if not Path(dagster_home).is_absolute():
        dagster_home = str((root / dagster_home).resolve())
    
    Path(dagster_home).mkdir(parents=True, exist_ok=True)
    os.environ["DAGSTER_HOME"] = dagster_home
    
    typer.secho("🔍 Scanning for VCF files in data/input/users/...\n", fg=typer.colors.CYAN)
    
    new, existing = sync_vcf_partitions(verbose=True)
    
    typer.echo("\n" + "="*60)
    typer.secho("📊 Summary:", fg=typer.colors.BRIGHT_WHITE, bold=True)
    typer.echo(f"   New partitions added: {len(new)}")
    typer.echo(f"   Existing partitions: {len(existing)}")
    typer.echo(f"   Total partitions: {len(new) + len(existing)}")
    typer.echo("="*60)
    
    if new:
        typer.secho("\n✅ Partitions are now available in Dagster UI!", fg=typer.colors.GREEN)
        typer.echo("   Go to Assets → user_vcf_source or user_annotated_vcf")
        typer.echo("   to materialize these partitions.")


@app.command("list-vcf-partitions")
def list_vcf_partitions_cmd() -> None:
    """List all VCF partitions currently registered in Dagster."""
    from just_dna_pipelines.annotation.utils import list_vcf_partitions
    
    # Set DAGSTER_HOME
    root = _find_workspace_root(Path.cwd())
    if root is None:
        root = Path.cwd()
    
    dagster_home = os.getenv("DAGSTER_HOME", "data/interim/dagster")
    if not Path(dagster_home).is_absolute():
        dagster_home = str((root / dagster_home).resolve())
    
    Path(dagster_home).mkdir(parents=True, exist_ok=True)
    os.environ["DAGSTER_HOME"] = dagster_home
    
    partitions = list_vcf_partitions()
    
    if not partitions:
        typer.secho("📭 No VCF partitions found.", fg=typer.colors.YELLOW)
        typer.echo("\nRun 'uv run pipelines sync-vcf-partitions' to discover and add VCF files.")
    else:
        typer.secho(f"📋 Found {len(partitions)} VCF partition(s):\n", fg=typer.colors.CYAN, bold=True)
        for p in sorted(partitions):
            typer.echo(f"   • {p}")


@app.command("cleanup-runs")
def cleanup_orphaned_runs(
    status: Annotated[
        str,
        typer.Option("--status", help="Run status to clean up (NOT_STARTED, STARTED, STARTING, QUEUED)")
    ] = "NOT_STARTED",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be cleaned up without actually doing it")
    ] = False,
) -> None:
    """
    Clean up orphaned Dagster runs.
    
    By default, cleans up NOT_STARTED runs (daemon submission failures).
    Use --status STARTED to clean up abandoned in-process runs from web server restarts.
    """
    from dagster import DagsterInstance, DagsterRunStatus, RunsFilter
    
    root = _find_workspace_root(Path.cwd())
    if root is None:
        raise typer.BadParameter("Could not find workspace root. Run this from the repo root.")
    
    dagster_home = root / "data" / "interim" / "dagster"
    if not dagster_home.exists():
        typer.secho("No Dagster instance found. Nothing to clean up.", fg=typer.colors.YELLOW)
        return
    
    # Set DAGSTER_HOME for DagsterInstance.get()
    os.environ["DAGSTER_HOME"] = str(dagster_home.resolve())
    
    # Map string status to DagsterRunStatus enum
    status_map = {
        "NOT_STARTED": DagsterRunStatus.NOT_STARTED,
        "STARTED": DagsterRunStatus.STARTED,
        "STARTING": DagsterRunStatus.STARTING,
        "QUEUED": DagsterRunStatus.QUEUED,
    }
    
    if status not in status_map:
        typer.secho(
            f"Invalid status: {status}. Must be one of: {', '.join(status_map.keys())}",
            fg=typer.colors.RED,
            err=True
        )
        raise typer.Exit(1)
    
    status_enum = status_map[status]
    
    instance = DagsterInstance.get()
    run_records = instance.get_run_records(
        filters=RunsFilter(statuses=[status_enum]),
        limit=100,
    )
    
    if not run_records:
        typer.secho(f"✓ No {status} runs found. Nothing to clean up.", fg=typer.colors.GREEN)
        return
    
    typer.echo(f"Found {len(run_records)} {status} run(s):")
    typer.echo()
    
    for record in run_records:
        run = record.dagster_run
        partition = run.tags.get("dagster/partition", "N/A")
        typer.echo(f"  • Run {run.run_id[:8]}... (Job: {run.job_name}, Partition: {partition})")
    
    typer.echo()
    
    if dry_run:
        typer.secho("🔍 DRY RUN: No changes made.", fg=typer.colors.YELLOW)
        return
    
    # Confirm with user
    if not typer.confirm(f"Mark these {len(run_records)} run(s) as CANCELED?"):
        typer.secho("Aborted.", fg=typer.colors.YELLOW)
        return
    
    # Clean up runs
    for record in run_records:
        run = record.dagster_run
        instance.report_run_canceled(
            run,
            message=f"Orphaned {status} run cleaned up by CLI"
        )
        typer.echo(f"  ✓ Canceled run {run.run_id[:8]}...")
    
    typer.secho(f"\n✅ Cleaned up {len(run_records)} orphaned run(s).", fg=typer.colors.GREEN)


@app.command("prune-dagster-history")
def prune_dagster_history_cmd(
    max_age_days: Annotated[
        Optional[int],
        typer.Option(
            "--max-age-days",
            help="Also delete runs older than this many days. Off by default: a deleted run takes its "
            "materializations along, and a sample whose last run is gone shows as only uploaded "
            "and is normalized again.",
        ),
    ] = None,
    keep_runless: Annotated[
        bool,
        typer.Option("--keep-runless/--prune-runless", help="Keep every runless asset event instead of only the newest per partition")
    ] = False,
    no_vacuum: Annotated[
        bool,
        typer.Option("--no-vacuum", help="Skip the SQLite VACUUM that returns the freed pages to the filesystem")
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Report what would be removed without removing it")
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Also remove files and vacuum while Dagster is running")
    ] = False,
) -> None:
    """Bound the size of the Dagster event log.

    Deletes orphaned per-run databases and superseded runless asset events, then
    vacuums the index so the pages return to the filesystem. The newest runless
    materialization per asset and partition is always kept, which is the one the
    web UI reads back. Runs are deleted only with --max-age-days.
    """
    root = _find_workspace_root(Path.cwd())
    if root is None:
        raise typer.BadParameter("Could not find workspace root. Run this from the repo root.")

    dagster_home = resolve_dagster_home(root)
    if not dagster_home.exists():
        typer.secho("No Dagster instance found. Nothing to prune.", fg=typer.colors.YELLOW)
        return

    # A daemon holds the databases open without listening on the UI port, so ask for
    # this instance's Dagster processes as well as the port.
    dagster_port = _resolve_dagster_port(None)
    holders = sorted(set(find_port_listeners(dagster_port)) | set(find_dagster_instance_pids(dagster_home)))
    dagster_running = bool(holders) and not force
    if holders:
        typer.secho(
            f"Dagster is running for this instance (pids: {', '.join(str(p) for p in holders)}).",
            fg=typer.colors.YELLOW,
        )
        typer.echo(
            "Pruning rows anyway; file removals and the vacuum wait for a pass with the stack stopped."
            if dagster_running
            else "Pruning everything anyway because --force was given."
        )

    report = prune_history(
        dagster_home,
        max_age_days=max_age_days,
        prune_runless=not keep_runless,
        run_vacuum=not no_vacuum,
        dry_run=dry_run,
        dagster_running=dagster_running,
    )

    typer.echo(f"Dagster home: {report.dagster_home}")
    typer.echo(f"Event log before: {human_bytes(report.before.total)} ({report.before.per_run_count} per-run databases)")
    if max_age_days is not None:
        typer.echo(f"  runs older than {max_age_days} days: {len(report.deleted_runs)}")
    typer.echo(f"  orphaned per-run databases: {len(report.orphan_run_dbs)}")
    typer.echo(
        f"  superseded runless asset events: {report.runless_rows_deleted}"
        f" ({human_bytes(report.runless_bytes_deleted)} of payload)"
    )
    if report.stray_index_removed:
        verb = "would remove" if dry_run else "removed"
        typer.secho(f"  {verb} a stray '.db' index written for an empty run id", fg=typer.colors.YELLOW)
    for reason in report.skipped:
        typer.secho(f"  skipped: {reason}", fg=typer.colors.YELLOW)

    if dry_run:
        typer.secho("\nDRY RUN: nothing was removed.", fg=typer.colors.YELLOW)
        return

    typer.echo(f"Event log after: {human_bytes(report.after.total)}")
    typer.secho(f"\nFreed {human_bytes(report.bytes_freed)}.", fg=typer.colors.GREEN)


def _start_all_cli() -> None:
    """Entry point for ``uv run start``.

    ``[project.scripts]`` calls this directly, so we need a thin
    standalone typer app to parse CLI flags like ``--immutable``.
    """
    _start_app = typer.Typer(add_completion=False, invoke_without_command=True)
    _start_app.command()(start_all)
    _start_app()


def _start_dagster_cli() -> None:
    """Entry point for ``uv run dagster-ui``."""
    _dg_app = typer.Typer(add_completion=False, invoke_without_command=True)
    _dg_app.command()(start_dagster)
    _dg_app()


if __name__ == "__main__":
    app()


