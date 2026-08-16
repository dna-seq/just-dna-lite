"""
Canonical Ensembl-variations cache downloader (single source of truth).

Both CLI entry points (`just_dna_lite.cli` and `just_dna_pipelines.cli`) delegate here so the
download logic exists once. Files are validated by **SHA256** taken from HuggingFace LFS metadata
(the authoritative content checksum), downloaded to a ``.part`` temp file, and renamed only after
they validate — so an interrupted download never leaves a truncated file under the real name.
"""

import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests
from huggingface_hub import get_token, hf_hub_url, list_repo_tree
from huggingface_hub.utils import HfHubHTTPError
from platformdirs import user_cache_dir
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

logger = logging.getLogger(__name__)

DEFAULT_ENSEMBL_REPO = "just-dna-seq/ensembl_variations"

# {filename: (size_bytes, sha256)}
EnsemblManifest = Dict[str, Tuple[int, str]]


class EnsemblDownloadError(RuntimeError):
    """Raised when the Ensembl cache could not be provisioned (empty repo or failed validation)."""


def resolve_ensembl_cache_root(cache_dir_override: Optional[str]) -> Path:
    """Resolve the *root* cache directory (parent of ``ensembl_variations/``)."""
    if cache_dir_override:
        return Path(cache_dir_override)
    env = os.getenv("JUST_DNA_PIPELINES_CACHE_DIR")
    return Path(env) if env else Path(user_cache_dir(appname="just-dna-pipelines"))


def fetch_ensembl_manifest(repo_id: str, token: Optional[str]) -> EnsemblManifest:
    """Return ``{filename: (size_bytes, sha256)}`` for every parquet in ``data/`` of the repo.

    HF's tree API returns transient 5xx (504 Gateway Timeout) under load, so retry with backoff.
    The listing is scoped to the ``data/`` subtree to keep the request small.
    """
    last_error: Optional[Exception] = None
    for attempt in range(5):
        try:
            return {
                Path(entry.path).name: (entry.lfs.size, entry.lfs.sha256)
                for entry in list_repo_tree(
                    repo_id, path_in_repo="data", repo_type="dataset",
                    token=token, recursive=True,
                )
                if (
                    hasattr(entry, "path")
                    and entry.path.endswith(".parquet")
                    and entry.lfs is not None
                )
            }
        except HfHubHTTPError as exc:
            # Only retry on server-side / transient failures; re-raise auth/not-found immediately.
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status is not None and status < 500 and status != 429:
                raise
            last_error = exc
            time.sleep(2 * (attempt + 1))
    raise EnsemblDownloadError(
        f"HuggingFace tree API kept failing for {repo_id} after 5 attempts: {last_error}"
    )


def sha256_file(path: Path) -> str:
    """Compute SHA256 of a file in 4 MB chunks."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def file_is_valid(path: Path, expected_size: int, expected_sha256: str) -> bool:
    """True only if file exists, has the right size, AND the right SHA256."""
    if not path.exists() or path.stat().st_size != expected_size:
        return False
    return sha256_file(path) == expected_sha256


def download_ensembl_cache(
    repo_id: str = DEFAULT_ENSEMBL_REPO,
    cache_dir: Optional[str] = None,
    force: bool = False,
    console: Optional[Console] = None,
) -> Path:
    """Download the Ensembl parquet cache from HuggingFace, validating each file by SHA256.

    Args:
        repo_id: HuggingFace dataset repo ID.
        cache_dir: Override for the root cache directory (default: env var / platform default).
        force: Re-download even files that already pass SHA256 validation.
        console: Optional rich Console for progress output (a default one is created if omitted).

    Returns:
        Path to the ``ensembl_variations/data`` directory holding the parquet files.

    Raises:
        EnsemblDownloadError: If the repo has no parquet files or any file fails validation.
    """
    rich = console or Console()
    target_dir = resolve_ensembl_cache_root(cache_dir) / "ensembl_variations" / "data"
    target_dir.mkdir(parents=True, exist_ok=True)

    rich.print("\n[bold]Ensembl Variations Downloader[/bold]")
    rich.print(f"  Repo   : [cyan]{repo_id}[/cyan]")
    rich.print(f"  Target : [cyan]{target_dir}[/cyan]\n")

    token = get_token()
    rich.print("[dim]Fetching remote manifest (size + SHA256)…[/dim]")
    manifest = fetch_ensembl_manifest(repo_id, token)
    if not manifest:
        raise EnsemblDownloadError(f"no parquet files found in repo {repo_id}")

    total_gb = sum(s for s, _ in manifest.values()) / (1024 ** 3)
    rich.print(f"Manifest: [bold]{len(manifest)}[/bold] files, [bold]{total_gb:.1f} GB[/bold] total\n")

    to_download: EnsemblManifest = {}
    skipped = 0
    for filename, (size, sha256) in manifest.items():
        dest = target_dir / filename
        if not force and file_is_valid(dest, size, sha256):
            skipped += 1
            continue
        to_download[filename] = (size, sha256)

    if skipped:
        rich.print(f"[green]✓ {skipped} file(s) passed SHA256 — skipping.[/green]")

    if not to_download:
        final = list(target_dir.glob("*.parquet"))
        total = sum(f.stat().st_size for f in final) / (1024 ** 3)
        rich.print(f"\n[bold green]✓ Cache complete![/bold green]  {len(final)} files, {total:.2f} GB\n")
        return target_dir

    rich.print(f"\nDownloading [bold]{len(to_download)}[/bold] file(s)…\n")

    errors: list[str] = []
    with Progress(
        TextColumn("[bold cyan]{task.fields[filename]}", justify="right"),
        BarColumn(bar_width=None),
        TaskProgressColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=rich,
    ) as progress:
        for filename, (expected_size, expected_sha256) in to_download.items():
            url = hf_hub_url(repo_id, filename=f"data/{filename}", repo_type="dataset")
            dest = target_dir / filename
            tmp = dest.with_suffix(".part")

            task = progress.add_task("", filename=filename, total=expected_size)
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            with requests.get(url, headers=headers, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                with open(tmp, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        fh.write(chunk)
                        progress.update(task, advance=len(chunk))

            if not file_is_valid(tmp, expected_size, expected_sha256):
                tmp.unlink(missing_ok=True)
                errors.append(f"{filename}: SHA256 mismatch after download")
            else:
                tmp.rename(dest)

    if errors:
        rich.print(f"\n[bold red]✗ {len(errors)} file(s) failed validation:[/bold red]")
        for e in errors:
            rich.print(f"  {e}")
        raise EnsemblDownloadError(f"{len(errors)} file(s) failed SHA256 validation")

    final_files = list(target_dir.glob("*.parquet"))
    total_gb = sum(f.stat().st_size for f in final_files) / (1024 ** 3)
    rich.print(f"\n[bold green]✓ Done![/bold green]  {len(final_files)} files, {total_gb:.2f} GB at {target_dir}\n")
    return target_dir
