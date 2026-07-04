"""CLI entry points for running the Reflex app."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import atexit
from pathlib import Path

_IS_WINDOWS = sys.platform == "win32"

from just_dna_pipelines.runtime import load_env

DEFAULT_DAGSTER_FILE = "just-dna-pipelines/src/just_dna_pipelines/annotation/definitions.py"
DEFAULT_DAGSTER_PORT = 3005


def _run_reflex(command: str, run_args: dict[str, object]) -> None:
    """Run Reflex and treat Ctrl+C as a normal shutdown."""

    from reflex.reflex import _run
    from reflex.utils import processes

    try:
        _run(**run_args)
    except KeyboardInterrupt:
        atexit.unregister(processes.atexit_handler)


def _consume_immutable_flag() -> None:
    """Set the env var if ``--immutable`` is present in sys.argv."""
    if "--immutable" in sys.argv:
        sys.argv = [a for a in sys.argv if a != "--immutable"]
        os.environ["JUST_DNA_IMMUTABLE_MODE"] = "true"


def _setup() -> None:
    """Load .env and ensure cwd is the project root (where rxconfig.py lives)."""
    load_env()
    root = Path(__file__).resolve().parents[2]
    os.chdir(root)


def _workspace_root() -> Path:
    """Return the uv workspace root that contains webui and pipeline packages."""
    return Path(__file__).resolve().parents[3]


def _resolve_dagster_port() -> int:
    """Resolve the Dagster UI port from DAGSTER_PORT."""
    port_text = os.getenv("DAGSTER_PORT", "").strip()
    if not port_text:
        return DEFAULT_DAGSTER_PORT
    try:
        return int(port_text)
    except ValueError as exc:
        raise ValueError("DAGSTER_PORT must be an integer") from exc


def _ensure_dagster_home(workspace_root: Path) -> Path:
    """Create DAGSTER_HOME and the minimal Dagster config if needed."""
    dagster_home = os.getenv("DAGSTER_HOME", "data/interim/dagster")
    dagster_home_path = Path(dagster_home)
    if not dagster_home_path.is_absolute():
        dagster_home_path = workspace_root / dagster_home_path

    dagster_home_path.mkdir(parents=True, exist_ok=True)
    (dagster_home_path / "logs").mkdir(parents=True, exist_ok=True)

    config_file = dagster_home_path / "dagster.yaml"
    if not config_file.exists():
        config_file.write_text("telemetry:\n  enabled: false\n", encoding="utf-8")

    os.environ["DAGSTER_HOME"] = str(dagster_home_path)
    return dagster_home_path


def _port_is_listening(host: str, port: int) -> bool:
    """Return True when a TCP listener is already reachable."""
    import socket

    probe_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((probe_host, port)) == 0


def _start_dagster_for_serve() -> subprocess.Popen[bytes] | None:
    """Start Dagster web UI alongside production Reflex serve."""
    workspace_root = _workspace_root()
    dagster_file = workspace_root / os.getenv("DAGSTER_FILE", DEFAULT_DAGSTER_FILE)
    dagster_host = os.getenv("DAGSTER_HOST", "127.0.0.1")
    dagster_port = _resolve_dagster_port()
    dagster_home = _ensure_dagster_home(workspace_root)

    if _port_is_listening(dagster_host, dagster_port):
        print(
            f"Dagster UI already appears to be listening at http://{dagster_host}:{dagster_port}.",
            flush=True,
        )
        return None

    dg_name = "dg.exe" if _IS_WINDOWS else "dg"
    dg_path = Path(sys.executable).parent / dg_name
    popen_kwargs: dict[str, object] = {}
    if _IS_WINDOWS:
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    process = subprocess.Popen(
        ["dg", "dev", "-f", str(dagster_file), "-p", str(dagster_port), "-h", dagster_host],
        cwd=workspace_root,
        executable=str(dg_path) if dg_path.exists() else None,
        **popen_kwargs,
    )
    print(f"Started Dagster UI at http://{dagster_host}:{dagster_port}", flush=True)
    print(f"Dagster home: {dagster_home}", flush=True)
    return process


def _stop_process(process: subprocess.Popen[bytes] | None) -> None:
    """Stop a background process group created by this launcher."""
    if process is None or process.poll() is not None:
        return

    try:
        if _IS_WINDOWS:
            process.terminate()
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    except (ProcessLookupError, OSError):
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if _IS_WINDOWS:
            process.kill()
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)


def main() -> None:
    """Start the Reflex development server.

    Supports ``--immutable`` flag to start in public demo mode.
    """
    _consume_immutable_flag()
    _setup()

    from reflex import constants
    from reflex_base.config import environment

    environment.REFLEX_COMPILE_CONTEXT.set(constants.CompileContext.RUN)
    _run_reflex("Reflex app", {"env": constants.Env.DEV})


def serve() -> None:
    """Start the single-port production server (Reflex 0.9+ unified mode).

    Self-sufficient: compiles frontend and serves everything from a single
    Python process — no separate Node.js server needed.

    Supports ``--immutable`` flag for public demo mode.
    """
    _consume_immutable_flag()
    _setup()

    web_dir = Path(".web")
    if web_dir.exists():
        shutil.rmtree(web_dir)
        print("Removed stale .web build directory before production serve.", flush=True)

    from webui.crawler_assets import generate_crawler_assets
    from webui.deployment_urls import resolve_configured_public_app_url

    app_url = resolve_configured_public_app_url()
    if app_url:
        os.environ["API_URL"] = app_url
        print(f"Using fullstack public app URL for Reflex API: {app_url}", flush=True)
    dagster_process = _start_dagster_for_serve()
    atexit.register(_stop_process, dagster_process)
    generate_crawler_assets()

    from reflex import constants
    from reflex.constants.base import RunningMode
    from reflex_base.config import environment

    port_str = os.getenv("APP_PORT", "").strip()
    port = int(port_str) if port_str else None

    environment.REFLEX_COMPILE_CONTEXT.set(constants.CompileContext.RUN)
    _run_reflex(
        "Reflex app",
        {
            "env": constants.Env.PROD,
            "running_mode": RunningMode.FULLSTACK,
            "frontend_port": port,
            "backend_port": port,
        },
    )


def _find_pids_on_port_unix(port: int) -> list[tuple[int, str]]:
    """Return (pid, command) pairs listening on *port* using lsof/ps."""
    try:
        out = subprocess.check_output(
            ["lsof", "-ti", f":{port}"], text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    results = []
    for raw_pid in out.split():
        pid = int(raw_pid)
        try:
            cmd = subprocess.check_output(
                ["ps", "-p", str(pid), "-o", "comm="], text=True, stderr=subprocess.DEVNULL,
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            cmd = "?"
        results.append((pid, cmd))
    return results


def _find_pids_on_port_windows(port: int) -> list[tuple[int, str]]:
    """Return (pid, command) pairs listening on *port* using netstat."""
    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "TCP"], text=True, stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    seen: set[int] = set()
    results = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 5 or "LISTENING" not in parts:
            continue
        local_addr = parts[1]
        if not local_addr.endswith(f":{port}"):
            continue
        try:
            pid = int(parts[-1])
        except ValueError:
            continue
        if pid == 0 or pid in seen:
            continue
        seen.add(pid)
        try:
            info = subprocess.check_output(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                text=True, stderr=subprocess.DEVNULL,
            ).strip()
            cmd = info.split(",")[0].strip('"') if info else "?"
        except (subprocess.CalledProcessError, FileNotFoundError):
            cmd = "?"
        results.append((pid, cmd))
    return results


def kill_ports() -> None:
    """Show and kill processes on ports 3000 and 8000-8010.

    Usage::

        uv run kill-ports            # show and kill default ports
        uv run kill-ports 3000       # only port 3000
        uv run kill-ports 3000 8000  # explicit list
    """
    ports = [int(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else [3000, *range(8000, 8011)]
    find_pids = _find_pids_on_port_windows if _IS_WINDOWS else _find_pids_on_port_unix
    killed_any = False
    for port in ports:
        for pid, cmd in find_pids(port):
            print(f"Port {port}: killing PID {pid} ({cmd})")
            try:
                if _IS_WINDOWS:
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(pid)],
                        check=True, capture_output=True,
                    )
                else:
                    os.kill(pid, signal.SIGKILL)
                killed_any = True
            except (OSError, subprocess.CalledProcessError) as exc:
                print(f"  failed: {exc}")
    if not killed_any:
        print("Nothing to kill — ports are free.")


if __name__ == "__main__":
    main()
