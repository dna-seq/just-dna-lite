from __future__ import annotations

import os
import time
import psutil
from contextlib import contextmanager
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Optional, Any

from eliot import start_action
from dotenv import find_dotenv, load_dotenv

from genobear.config import get_default_workers, get_parquet_workers


def load_env(override: bool = False) -> Optional[str]:
    """
    Search for .env file in the current directory and its parents.
    This is useful when running from subprojects (e.g. genobear/ or webui/)
    to ensure the root .env is loaded.
    
    Returns:
        The path to the .env file found and loaded, or None if not found.
    """
    env_path = find_dotenv(usecwd=True)
    if env_path:
        load_dotenv(env_path, override=override)
        return env_path
    return None


@contextmanager
def resource_tracker(name: str = "resource_usage"):
    """Context manager to track execution time, CPU and peak memory usage."""
    process = psutil.Process(os.getpid())
    start_time = time.perf_counter()
    start_mem = process.memory_info().rss
    
    # Start CPU tracking
    process.cpu_percent(interval=None)
    
    data = {"name": name, "start_time": start_time, "start_mem": start_mem}
    yield data
    
    end_time = time.perf_counter()
    end_mem = process.memory_info().rss
    cpu_usage = process.cpu_percent(interval=None)
    
    data["end_time"] = end_time
    data["end_mem"] = end_mem
    data["duration"] = end_time - start_time
    data["cpu_usage_percent"] = cpu_usage
    data["memory_delta"] = end_mem - start_mem
    data["peak_memory_mb"] = max(start_mem, end_mem) / (1024 * 1024)
    data["memory_delta_mb"] = (end_mem - start_mem) / (1024 * 1024)

    # If running inside a Prefect flow/task, log and create artifact
    try:
        from prefect import get_run_logger
        from prefect.artifacts import create_markdown_artifact
        try:
            logger = get_run_logger()
            logger.info(
                f"Resource Report [{name}]: Duration: {data['duration']:.2f}s, "
                f"CPU: {data['cpu_usage_percent']:.1f}%, Peak RAM: {data['peak_memory_mb']:.2f}MB"
            )
            
            create_markdown_artifact(
                key=f"{name.replace(' ', '_').lower()}-resources",
                markdown=f"""# Resource Report: {name}
| Metric | Value |
| :--- | :--- |
| **Duration** | {data['duration']:.2f}s |
| **CPU Usage** | {data['cpu_usage_percent']:.1f}% |
| **Peak Memory** | {data['peak_memory_mb']:.2f} MB |
| **Memory Delta** | {data['memory_delta_mb']:+.2f} MB |
""",
                description=f"Resource usage metrics for {name}"
            )
        except Exception:
            # Not in a prefect context or logger not available
            pass
    except ImportError:
        pass


def resolve_worker_counts(
    download_workers: Optional[int] = None,
    workers: Optional[int] = None,
    parquet_workers: Optional[int] = None,
) -> tuple[int, int, int]:
    """Resolve worker counts from parameters or environment.

    - download_workers: from GENOBEAR_DOWNLOAD_WORKERS or CPU count
    - workers: from GENOBEAR_WORKERS via get_default_workers()
    - parquet_workers: from GENOBEAR_PARQUET_WORKERS or default of 4
    """
    # Load .env if present (does not override existing env vars)
    env_path = load_env(override=False)
    if env_path:
        with start_action(action_type="load_env", env_path=env_path):
            pass

    env_dl = os.getenv("GENOBEAR_DOWNLOAD_WORKERS")
    env_workers = os.getenv("GENOBEAR_WORKERS")
    env_parquet = os.getenv("GENOBEAR_PARQUET_WORKERS")

    resolved_download = (
        int(os.getenv("GENOBEAR_DOWNLOAD_WORKERS", os.cpu_count() or 1))
        if download_workers is None
        else max(1, int(download_workers))
    )
    resolved_workers = get_default_workers() if workers is None else max(1, int(workers))
    resolved_parquet = get_parquet_workers() if parquet_workers is None else max(1, int(parquet_workers))

    with start_action(
        action_type="resolve_worker_counts",
        GENOBEAR_DOWNLOAD_WORKERS=env_dl,
        GENOBEAR_WORKERS=env_workers,
        GENOBEAR_PARQUET_WORKERS=env_parquet,
        resolved_download=resolved_download,
        resolved_workers=resolved_workers,
        resolved_parquet=resolved_parquet,
    ):
        pass
    return resolved_download, resolved_workers, resolved_parquet


def setup_prefect_api() -> bool:
    """Setup Prefect API connection if environment variables are provided.
    
    Returns:
        bool: True if server-based Prefect is configured, False for ephemeral mode.
    """
    api_url = os.getenv("PREFECT_API_URL")
    if api_url:
        print(f"🚀 Prefect configured for server at: {api_url}")
        return True
    else:
        print("💡 Prefect running in ephemeral (standalone) mode.")
        return False


@contextmanager
def prefect_flow_run(name: str, profile: bool = True):
    """Context manager for running a Prefect flow with optional resource tracking.
    
    Args:
        name: Name of the flow/operation
        profile: If True, tracks resource usage
    """
    setup_prefect_api()
    if profile:
        with resource_tracker(name) as tracker:
            yield tracker
    else:
        yield {}





