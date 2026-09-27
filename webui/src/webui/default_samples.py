"""Fetch the immutable-mode public genomes once, off the event loop, from server start.

``UploadState.on_load`` used to call ``resolve_default_samples`` inline. That is ``requests`` and
``shutil`` work on multi-gigabyte VCFs (a Zenodo download when the cache is empty, a copy into
``data/input/users/public/`` when only the cache has them), and running it on the event loop froze
every client of the process: socket.io pings timed out, the page stayed drawn, and each click
reported the server as unreachable until the transfer finished, with nothing in the CLI.

The work is plain blocking I/O (no Dagster, Polars or DuckDB objects), so a thread is allowed
under the process model. ``serve`` runs one backend worker without Redis, so this runs once.
"""

import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Optional

from just_dna_pipelines.annotation.resources import resolve_default_samples
from just_dna_pipelines.module_config import get_immutable_config, is_immutable_mode

logger = logging.getLogger(__name__)

PUBLIC_USER = "public"

_executor: Optional[ThreadPoolExecutor] = None
_future: Optional["Future[list[dict[str, Any]]]"] = None


def _resolve_with_progress() -> list[dict[str, Any]]:
    labels = [sample.label for sample in get_immutable_config().default_samples]
    print(
        f"[immutable] preparing {len(labels)} public genome(s): {', '.join(labels)} "
        "(the first start downloads them from Zenodo)",
        flush=True,
    )
    started = time.monotonic()
    results = resolve_default_samples(user_name=PUBLIC_USER, log=logger)
    ready = ", ".join(r["filename"] for r in results) or "none"
    print(
        f"[immutable] public genomes ready in {time.monotonic() - started:.0f}s: {ready}",
        flush=True,
    )
    return results


def default_samples_future() -> Optional["Future[list[dict[str, Any]]]"]:
    """The one resolution of the public genomes, started on first call; ``None`` outside
    immutable mode or when no default samples are configured."""
    global _executor, _future
    if _future is not None:
        return _future
    if not is_immutable_mode() or not get_immutable_config().default_samples:
        return None
    _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="default-samples")
    _future = _executor.submit(_resolve_with_progress)
    return _future
