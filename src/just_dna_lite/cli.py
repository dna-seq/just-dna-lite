from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Annotated

import typer


app = typer.Typer(
    name="pipelines",
    help="Pipelines - Genomic analysis stack",
    no_args_is_help=True,
    add_completion=False
)


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


def _kill_process_group(proc: Optional[subprocess.Popen]) -> None:
    """Kill a process and its entire process group."""
    if proc is None or proc.poll() is not None:
        return
    
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGTERM)
        proc.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    except Exception as e:
        typer.secho(f"Error killing process group: {e}", fg=typer.colors.RED, err=True)


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


@app.command("ui")
def start_ui(
    granian: Annotated[
        bool, typer.Option("--granian", help="Use Granian for the backend.")
    ] = True,
) -> None:
    """Start only the Reflex Web UI."""
    root = _find_workspace_root(Path.cwd())
    if root is None:
        raise typer.BadParameter("Could not find workspace root. Run this from the repo root.")

    if granian:
        os.environ["REFLEX_USE_GRANIAN"] = "true"
    
    webui_dir = root / "webui"
    if not webui_dir.exists():
        raise typer.BadParameter(f"webui folder not found: {webui_dir}")

    typer.secho("🚀 Starting Reflex Web UI...", fg=typer.colors.BRIGHT_CYAN, bold=True)
    
    typer.echo("\n" + "═" * 65)
    typer.secho("⏳ The UI is initializing. It will be available shortly at:", fg=typer.colors.YELLOW)
    typer.echo(f"  • Web UI:       http://localhost:3000 (Main Interface)")
    typer.echo(f"  • Backend API:  http://localhost:8000 (Reflex Internal)")
    typer.secho("\nNote: It may take 10-20 seconds to compile the frontend.", fg=typer.colors.DIM)
    typer.echo("═" * 65 + "\n")

    # Clean up UI ports
    for port in [3000, 3001, 8000]:
        _kill_port_owner(port)

    # Reflex already runs both frontend+backend in dev.
    proc = subprocess.Popen(
        ["uv", "run", "reflex", "run"], 
        cwd=str(webui_dir),
        preexec_fn=os.setpgrp if hasattr(os, "setpgrp") else None
    )
    try:
        proc.wait()
    except KeyboardInterrupt:
        typer.secho("\nStopping UI...", fg=typer.colors.YELLOW)
        _kill_process_group(proc)


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
        int,
        typer.Option(
            "--port",
            "-p",
            help="Port for the Dagster UI.",
        ),
    ] = 3005,
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

    # Set DAGSTER_HOME to data/interim/dagster
    dagster_home = os.getenv("DAGSTER_HOME", "data/interim/dagster")
    if not Path(dagster_home).is_absolute():
        dagster_home = str((root / dagster_home).resolve())
    
    dagster_home_path = Path(dagster_home)
    _ensure_dagster_config(dagster_home_path)
    os.environ["DAGSTER_HOME"] = dagster_home
    
    typer.secho(f"🚀 Starting Dagster Dev (UI + Daemon) for {file}...", fg=typer.colors.BRIGHT_CYAN, bold=True)
    typer.echo(f"📁 Dagster home: {dagster_home}")
    _kill_port_owner(port)
    
    typer.secho(f"\n💡 Dagster UI will be available at: http://localhost:{port}\n", fg=typer.colors.GREEN, bold=True)
    
    # Use os.execvp to replace the current process with dagster dev
    # This ensures all output is properly forwarded and the process behaves correctly
    os.execvp(
        sys.executable,
        [sys.executable, "-m", "dagster", "dev", "-f", str(dagster_file), "-p", str(port)]
    )


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
        int, typer.Option("--dagster-port", help="Port for the Dagster UI.")
    ] = 3005,
) -> None:
    """Start the full stack: Dagster (Pipelines) and Reflex UI."""
    root = _find_workspace_root(Path.cwd())
    if root is None:
        root = Path.cwd()

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
    
    # 0. Clean up orphan processes
    ports_to_clean = [3000, 3001, 8000, dagster_port]
    typer.echo(f"🧹 Cleaning up existing processes on ports {', '.join(map(str, ports_to_clean))}...")
    for port in ports_to_clean:
        _kill_port_owner(port)

    # 1. Start the UI in the background
    webui_dir = root / "webui"
    typer.secho("🚀 Starting Reflex Web UI...", fg=typer.colors.BRIGHT_CYAN)
    # Reflex will run in the background but share the same process group
    subprocess.Popen(
        [sys.executable, "-m", "reflex", "run"],
        cwd=str(webui_dir)
    )

    # Give it a moment to initialize
    time.sleep(2)

    # 2. Start Dagster by REPLACING this process (exec)
    # This ensures Dagster has full control of stdout/stderr and terminal signals,
    # making it behave exactly like the `uv run dagster-ui` command.
    typer.secho(f"🧬 Starting Dagster Pipelines for {dagster_file}...", fg=typer.colors.BRIGHT_BLUE)
    typer.echo(f"📁 Dagster home: {dagster_home}")
    dagster_file_path = root / dagster_file

    typer.echo("\n" + "═" * 65)
    typer.secho("🚀 Just DNA Pipelines Stack is starting!", fg=typer.colors.GREEN, bold=True)
    typer.secho("⏳ Note: Reflex UI takes ~20s to initialize.", fg=typer.colors.YELLOW)
    typer.echo(f"  • Web UI:       http://localhost:3000 (Main Interface)")
    typer.echo(f"  • Pipelines UI: http://localhost:{dagster_port} (Dagster Dashboard)")
    typer.echo(f"  • Backend API:  http://localhost:8000 (Reflex Internal)")
    typer.echo("═" * 65 + "\n")

    # This replaces the current process with dagster dev
    os.execvp(
        sys.executable,
        [sys.executable, "-m", "dagster", "dev", "-f", str(dagster_file_path), "-p", str(dagster_port)]
    )


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


if __name__ == "__main__":
    app()




