from __future__ import annotations

import os
import time
import re
import psutil
from contextlib import contextmanager
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Optional, Any
from just_dna_pipelines.models import ResourceReport

from eliot import start_action
from dotenv import find_dotenv, load_dotenv

from just_dna_pipelines.config import get_default_workers, get_parquet_workers


def load_env(override: bool = False) -> Optional[str]:
    """
    Search for .env file in the current directory and its parents.
    This is useful when running from subprojects (e.g. just-dna-pipelines/ or webui/)
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
def resource_tracker(name: str = "resource_usage", context: Optional[Any] = None):
    """
    Context manager to track execution time, CPU and peak memory usage.
    
    Args:
        name: Name of the resource being tracked
        context: Optional Dagster context. If provided, metadata will be logged to Dagster.
    """
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
    
    duration = end_time - start_time
    cpu_usage_percent = cpu_usage
    memory_delta = end_mem - start_mem
    peak_memory_mb = max(start_mem, end_mem) / (1024 * 1024)
    memory_delta_mb = (end_mem - start_mem) / (1024 * 1024)

    report = ResourceReport(
        name=name,
        duration=duration,
        cpu_usage_percent=cpu_usage_percent,
        peak_memory_mb=peak_memory_mb,
        memory_delta_mb=memory_delta_mb,
        start_time=start_time,
        end_time=end_time,
        start_mem=start_mem,
        end_mem=end_mem,
        memory_delta=memory_delta
    )
    
    # Store report in the data dict so calling code can access it
    data["report"] = report

    # Log to Eliot/standard logger
    try:
        from dagster import get_dagster_logger
        logger = get_dagster_logger()
        logger.info(
            f"📊 Resource Report [{name}]: Duration: {report.duration:.2f}s, "
            f"CPU: {report.cpu_usage_percent:.1f}%, Peak RAM: {report.peak_memory_mb:.2f}MB"
        )
    except Exception:
        pass

    # If running inside a Dagster context, log metadata
    if context is not None:
        try:
            from dagster import MetadataValue
            
            # Clean name for metadata key
            clean_key = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')
            if not clean_key:
                clean_key = "resource_usage"
            
            # Dagster 1.12.x compatible metadata logging
            # Note: context.log.info does not take metadata, use add_output_metadata or log separately
            # For assets, the standard way is to return Output with metadata, 
            # but inside the asset we can use context.add_output_metadata
            context.add_output_metadata({
                f"{clean_key}_duration_sec": MetadataValue.float(round(report.duration, 2)),
                f"{clean_key}_cpu_percent": MetadataValue.float(round(report.cpu_usage_percent, 1)),
                f"{clean_key}_peak_memory_mb": MetadataValue.float(round(report.peak_memory_mb, 2)),
                f"{clean_key}_memory_delta_mb": MetadataValue.float(round(report.memory_delta_mb, 2)),
            })
        except Exception:
            # Metadata logging failed
            pass


def resolve_worker_counts(
    download_workers: Optional[int] = None,
    workers: Optional[int] = None,
    parquet_workers: Optional[int] = None,
) -> tuple[int, int, int]:
    """Resolve worker counts from parameters or environment.

    - download_workers: from JUST_DNA_PIPELINES_DOWNLOAD_WORKERS or CPU count
    - workers: from JUST_DNA_PIPELINES_WORKERS via get_default_workers()
    - parquet_workers: from JUST_DNA_PIPELINES_PARQUET_WORKERS or default of 4
    """
    # Load .env if present (does not override existing env vars)
    env_path = load_env(override=False)
    if env_path:
        with start_action(action_type="load_env", env_path=env_path):
            pass

    env_dl = os.getenv("JUST_DNA_PIPELINES_DOWNLOAD_WORKERS")
    env_workers = os.getenv("JUST_DNA_PIPELINES_WORKERS")
    env_parquet = os.getenv("JUST_DNA_PIPELINES_PARQUET_WORKERS")

    resolved_download = (
        int(os.getenv("JUST_DNA_PIPELINES_DOWNLOAD_WORKERS", os.cpu_count() or 1))
        if download_workers is None
        else max(1, int(download_workers))
    )
    resolved_workers = get_default_workers() if workers is None else max(1, int(workers))
    resolved_parquet = get_parquet_workers() if parquet_workers is None else max(1, int(parquet_workers))

    with start_action(
        action_type="resolve_worker_counts",
        JUST_DNA_PIPELINES_DOWNLOAD_WORKERS=env_dl,
        JUST_DNA_PIPELINES_WORKERS=env_workers,
        JUST_DNA_PIPELINES_PARQUET_WORKERS=env_parquet,
        resolved_download=resolved_download,
        resolved_workers=resolved_workers,
        resolved_parquet=resolved_parquet,
    ):
        pass
    return resolved_download, resolved_workers, resolved_parquet





