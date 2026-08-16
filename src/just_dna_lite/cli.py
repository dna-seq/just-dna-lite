from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Annotated, Dict, Optional

import typer
from dotenv import load_dotenv

load_dotenv()  # Load .env from cwd or parent dirs before any command runs

from just_dna_lite.process import (
    detached_popen_kwargs,
    install_launcher_signal_handlers,
    reap_dagster_instance,
    reap_webui_leftovers,
    shutdown_managed_processes,
)
from just_dna_pipelines.annotation.cli_annotate import annotate as annotate_cmd
from just_dna_pipelines.annotation.cli_annotate import annotate_main
from just_dna_pipelines.annotation.ensembl_download import (
    EnsemblDownloadError,
    download_ensembl_cache,
    fetch_ensembl_manifest,
    file_is_valid,
    resolve_ensembl_cache_root,
    sha256_file,
)
from just_dna_pipelines.annotation.module_cache import (
    clear_hf_module_cache,
    get_app_version,
)
from just_dna_pipelines.agents.cli import app as agent_app
from just_dna_pipelines.module_compiler.cli import app as module_compiler_app
from just_dna_pipelines.v1_port.cli import app as v1_port_app
from just_dna_enricher.cli import app as enricher_app
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


def _run_managed_foreground(command: list[str], dagster_home: Path) -> int:
    """Run a foreground child and tear down its whole tree on Ctrl+C."""

    proc = subprocess.Popen(command, **detached_popen_kwargs())
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
    """Kill the process listening on the specified port."""
    import socket
    
    # Check if port is actually in use by trying to connect to it
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect(("127.0.0.1", port))
            # If we reach here, the port is in use
        except ConnectionRefusedError:
            # Port is free
            return
        except Exception:
            # Some other error, better to check with tools
            pass

    try:
        typer.secho(f"🔍 Port {port} is in use, searching for owner...", fg=typer.colors.CYAN)
        
        # Try lsof with more specific flags
        result = subprocess.run(
            ["lsof", "-t", "-n", "-P", f"-iTCP:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            check=False
        )
        pids = result.stdout.strip().split()
        
        if not pids:
            # Try fuser as backup
            result = subprocess.run(
                ["fuser", f"{port}/tcp"],
                capture_output=True,
                text=True,
                check=False
            )
            # fuser output: 3000/tcp:  1234 5678
            if result.returncode == 0:
                output = result.stdout.split(":")[-1].strip()
                pids = output.split()

        if not pids:
            typer.secho(f"⚠️  Port {port} is busy (maybe in TIME_WAIT?) but owner PID could not be found.", fg=typer.colors.YELLOW)
            return

        for pid_str in pids:
            if pid_str:
                try:
                    pid = int(pid_str)
                    if pid == os.getpid():
                        continue
                    typer.secho(f"Stopping process {pid} on port {port}...", fg=typer.colors.YELLOW)
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(0.5)
                    try:
                        os.kill(pid, 0)
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                except (ValueError, ProcessLookupError):
                    pass
    except Exception as e:
        typer.secho(f"Error during port cleanup for {port}: {e}", fg=typer.colors.RED, err=True)


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
    
    dg_path = Path(sys.executable).parent / "dg"
    exit_code = _run_managed_foreground(
        [str(dg_path), "dev", "-f", str(dagster_file), "-p", str(dagster_port), "-h", dagster_host],
        dagster_home=dagster_home_path,
    )
    if exit_code != 0:
        raise typer.Exit(exit_code)


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
            ["uv", "run", "--package", "webui", "run"],
            cwd=root,
            **detached_popen_kwargs(),
        )
        child_processes.append(ui_proc)

        # Give it a moment to initialize
        time.sleep(2)

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

        dg_path = Path(sys.executable).parent / "dg"
        dagster_proc = subprocess.Popen(
            [str(dg_path), "dev", "-f", str(dagster_file_path), "-p", str(resolved_dagster_port), "-h", resolved_dagster_host],
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

    if exit_code != 0:
        raise typer.Exit(exit_code)


# Ensembl download logic is centralized in just_dna_pipelines.annotation.ensembl_download
# (single source of truth, shared with the just_dna_pipelines CLI). These are thin aliases so the
# other ensembl commands in this file (verify-ensembl, ensembl-setup) keep their call sites.
_resolve_ensembl_cache = resolve_ensembl_cache_root
_fetch_ensembl_manifest = fetch_ensembl_manifest
_sha256_file = sha256_file
_file_is_valid = file_is_valid


@app.command("download-ensembl")
def download_ensembl(
    repo_id: str = typer.Option(
        "just-dna-seq/ensembl_variations",
        "--repo", "-r",
        help="HuggingFace dataset repo ID.",
    ),
    cache_dir: Optional[str] = typer.Option(
        None,
        "--cache-dir", "-c",
        help="Override cache directory. Defaults to JUST_DNA_PIPELINES_CACHE_DIR env var "
             "or ~/.cache/just-dna-pipelines.",
    ),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="Force re-download even if files pass SHA256 validation.",
    ),
) -> None:
    """
    Download Ensembl variation annotations from HuggingFace to the local cache.

    Files are saved to:
      {cache_dir}/ensembl_variations/data/

    Each file is validated by SHA256 (from HF LFS metadata). Already-valid files
    are skipped.

    The destination is read from JUST_DNA_PIPELINES_CACHE_DIR (or
    ~/.cache/just-dna-pipelines if not set). Pass --cache-dir to override.

    Examples:

        uv run pipelines download-ensembl
        uv run pipelines download-ensembl --force
        uv run pipelines download-ensembl --cache-dir /data/my-cache
    """
    try:
        download_ensembl_cache(repo_id=repo_id, cache_dir=cache_dir, force=force)
    except EnsemblDownloadError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


@app.command("verify-ensembl")
def verify_ensembl(
    repo_id: str = typer.Option(
        "just-dna-seq/ensembl_variations",
        "--repo", "-r",
        help="HuggingFace dataset repo ID to check against.",
    ),
    cache_dir: Optional[str] = typer.Option(
        None,
        "--cache-dir", "-c",
        help="Override cache directory.",
    ),
) -> None:
    """
    Verify the local Ensembl cache against the remote SHA256 checksums.

    Reports missing, incomplete, and corrupted files without downloading anything.
    Exit code 1 if any file fails; 0 if the cache is fully intact.

    Example:

        uv run pipelines verify-ensembl
    """
    from huggingface_hub import get_token
    from rich.console import Console as RichConsole
    from rich.progress import Progress, SpinnerColumn, TextColumn, MofNCompleteColumn

    rich = RichConsole()
    resolved_cache = _resolve_ensembl_cache(cache_dir)
    target_dir = resolved_cache / "ensembl_variations" / "data"

    rich.print(f"\n[bold]Ensembl Cache Verifier[/bold]")
    rich.print(f"  Path : [cyan]{target_dir}[/cyan]\n")

    token = get_token()
    rich.print("[dim]Fetching remote manifest…[/dim]")
    manifest = _fetch_ensembl_manifest(repo_id, token)
    if not manifest:
        rich.print(f"[red]Error: no parquet files found in repo {repo_id}[/red]")
        raise typer.Exit(1)

    missing: list[str] = []
    wrong_size: list[str] = []
    bad_sha256: list[str] = []
    ok: list[str] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        MofNCompleteColumn(),
        console=rich,
    ) as progress:
        task = progress.add_task("Verifying files…", total=len(manifest))
        for filename, (expected_size, expected_sha256) in manifest.items():
            path = target_dir / filename
            progress.update(task, description=f"[dim]{filename}[/dim]", advance=1)
            if not path.exists():
                missing.append(filename)
            elif path.stat().st_size != expected_size:
                wrong_size.append(f"{filename}  (local {path.stat().st_size} B ≠ remote {expected_size} B)")
            elif _sha256_file(path) != expected_sha256:
                bad_sha256.append(filename)
            else:
                ok.append(filename)

    rich.print(f"\n[green]✓ OK        : {len(ok)}/{len(manifest)}[/green]")
    if missing:
        rich.print(f"[yellow]  Missing   : {len(missing)}[/yellow]")
        for f in missing:
            rich.print(f"    • {f}")
    if wrong_size:
        rich.print(f"[red]  Wrong size: {len(wrong_size)}[/red]")
        for f in wrong_size:
            rich.print(f"    • {f}")
    if bad_sha256:
        rich.print(f"[red]  Bad SHA256: {len(bad_sha256)}[/red]")
        for f in bad_sha256:
            rich.print(f"    • {f}")

    if missing or wrong_size or bad_sha256:
        rich.print("\n[dim]Run [bold]uv run pipelines download-ensembl[/bold] to repair.[/dim]\n")
        raise typer.Exit(1)

    rich.print("\n[bold green]Cache is fully intact.[/bold green]\n")


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

    Requires the Ensembl parquet cache to already be downloaded
    (run ``uv run pipelines download-ensembl`` first).

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

    resolved_cache = _resolve_ensembl_cache(cache_dir)
    ensembl_dir = resolved_cache / "ensembl_variations"
    data_dir = ensembl_dir / "data"
    duckdb_path = ensembl_dir / "ensembl_variations.duckdb"

    if not data_dir.exists() or not any(data_dir.glob("*.parquet")):
        rich.print(
            f"[red]Error: Ensembl parquet cache not found at {data_dir}[/red]\n"
            "[dim]Run [bold]uv run pipelines download-ensembl[/bold] first.[/dim]"
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
    repo_id: str = typer.Option(
        "just-dna-seq/ensembl_variations",
        "--repo", "-r",
        help="HuggingFace dataset repo ID.",
    ),
    cache_dir: Optional[str] = typer.Option(
        None,
        "--cache-dir", "-c",
        help="Override cache directory. Defaults to JUST_DNA_PIPELINES_CACHE_DIR env var "
             "or ~/.cache/just-dna-pipelines.",
    ),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="Force re-download and rebuild.",
    ),
) -> None:
    """
    Full Ensembl setup: download parquet, verify integrity, build DuckDB.

    One-stop command for bootstrapping the Ensembl annotation cache from
    scratch. Runs three steps in sequence:

      1. download-ensembl  — fetch parquet files from HuggingFace
      2. verify-ensembl    — confirm all files match remote SHA256
      3. build-duckdb      — create the DuckDB catalog over the parquet

    Already-complete steps are skipped automatically (use --force to redo).

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

    # ── Step 1: Download ──────────────────────────────────────────────────────
    rich.print("[bold]Step 1/3: Download Ensembl parquet files[/bold]\n")
    download_ensembl(
        repo_id=repo_id,
        cache_dir=cache_dir,
        force=force,
    )

    # ── Step 2: Verify ────────────────────────────────────────────────────────
    rich.print("\n[bold]Step 2/3: Verify cache integrity[/bold]\n")
    verify_ensembl(
        repo_id=repo_id,
        cache_dir=cache_dir,
    )

    # ── Step 3: Build DuckDB ──────────────────────────────────────────────────
    rich.print(f"\n[bold]Step 3/3: Build DuckDB[/bold]\n")

    resolved_cache = _resolve_ensembl_cache(cache_dir)
    ensembl_dir = resolved_cache / "ensembl_variations"
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


