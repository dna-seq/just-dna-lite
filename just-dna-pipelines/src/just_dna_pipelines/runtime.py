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
from dotenv import load_dotenv

from just_dna_pipelines.config import get_default_workers, get_parquet_workers


def _is_workspace_root(path: Path) -> bool:
    pyproject = path / "pyproject.toml"
    return pyproject.is_file() and "[tool.uv.workspace]" in pyproject.read_text(encoding="utf-8")


def _first_workspace_root(start: Path) -> Optional[Path]:
    for candidate in (start, *start.parents):
        if _is_workspace_root(candidate):
            return candidate
    return None


def find_workspace_root() -> Optional[Path]:
    """The just-dna-lite checkout this process belongs to, or None outside one.

    ``$JUST_DNA_PIPELINES_ROOT`` wins, then the checkout this package is installed from (an editable
    install lives inside it), then the nearest uv workspace above the working directory.
    """
    override = os.environ.get("JUST_DNA_PIPELINES_ROOT")
    if override and Path(override).is_dir():
        return Path(override).resolve()
    return _first_workspace_root(Path(__file__).resolve().parent) or _first_workspace_root(Path.cwd().resolve())


def load_env(override: bool = False) -> Optional[str]:
    """Load this checkout's ``.env``, never one that lives above it.

    Searches from the working directory up to the workspace root and stops there, so running from
    ``just-dna-pipelines/`` or ``webui/`` still finds the root ``.env``. python-dotenv's own
    ``find_dotenv`` keeps climbing: a checkout with no ``.env`` then read ``~/sources/.env`` (another
    project's) and built every report link on its ``DEPLOY_URL``. With no ``.env``, the root's
    ``.env.template`` supplies the defaults.

    Returns:
        The path of the file loaded, or None when there is none.
    """
    root = find_workspace_root()
    if root is None:
        return None
    cwd = Path.cwd().resolve()
    search = [cwd, *cwd.parents] if cwd == root or root in cwd.parents else [root]
    for directory in search:
        env_path = directory / ".env"
        if env_path.is_file():
            load_dotenv(env_path, override=override)
            return str(env_path)
        if directory == root:
            break
    template = root / ".env.template"
    if template.is_file():
        load_dotenv(template, override=override)
        return str(template)
    return None


@contextmanager
def environ_guard():
    """Undo whatever the enclosed code adds to or changes in ``os.environ``.

    For importing a dependency that calls a bare ``load_dotenv()`` at import time (just-dna-registry
    does): that walks up from the dependency's own directory and can read a ``.env`` outside this
    checkout. Inside the block the import sees whatever it loaded; afterwards ``os.environ`` is
    exactly what it was, so only our own ``load_env`` decides the configuration. Call ``load_env``
    first, so values from this checkout's ``.env`` are already in place and are not reverted.
    """
    before = dict(os.environ)
    try:
        yield
    finally:
        for key in [k for k in os.environ if k not in before]:
            del os.environ[key]
        for key, value in before.items():
            if os.environ.get(key) != value:
                os.environ[key] = value


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
            
            # Dagster 1.13.x: context.log.info() has no metadata kwarg; use add_output_metadata
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





