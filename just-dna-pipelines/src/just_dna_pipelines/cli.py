"""
CLI for just-dna-pipelines.

Provides command-line interface for running annotation pipelines.
"""

from pathlib import Path
from typing import Dict, Optional

import typer
from rich.console import Console
from rich.table import Table

from just_dna_pipelines.annotation.module_cache import (
    clear_hf_module_cache,
    get_app_version,
)
from just_dna_pipelines.module_compiler.cli import app as module_app
from just_dna_pipelines.agents.cli import app as agent_app
from just_dna_pipelines.v1_port.cli import app as v1_port_app
from just_dna_enricher.cli import app as enricher_app
from just_dna_registry.client_cli import app as registry_client_app

app = typer.Typer(
    name="pipelines",
    help="Genomic annotation pipelines for VCF files.",
    no_args_is_help=True,
)
app.add_typer(module_app, name="module")
app.add_typer(agent_app, name="agent")
app.add_typer(v1_port_app, name="v1-port")
# The enricher's own Typer app, mounted whole rather than re-declared: it is the
# authoring tier that produces `resolution.csv` and the 0.5 fact sidecars which
# `pipelines module compile` then consumes with no reference and no network.
# Mounting it means new enricher commands appear here without further wiring.
app.add_typer(enricher_app, name="enrich")
app.add_typer(registry_client_app, name="registry")

console = Console()


@app.command()
def clear_module_cache() -> None:
    """Delete the locally cached HuggingFace annotator-module data.

    Forces the next run to re-download the currently published module versions.
    Use after republishing a module in place (same version); version bumps are
    invalidated automatically on startup.
    """
    removed = clear_hf_module_cache()
    if removed:
        console.print(f"[green]Cleared HF module cache for:[/green] {', '.join(removed)}")
    else:
        console.print("[yellow]No cached HF module repos found — nothing to clear.[/yellow]")
    console.print(f"[dim]Current app version: {get_app_version()}[/dim]")


@app.command()
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
        help="Force re-download even if files are already complete.",
    ),
) -> None:
    """
    Download Ensembl variation annotations from HuggingFace to the local cache.

    Files are saved to:
      {cache_dir}/ensembl_variations/data/

    Already-complete files (correct byte size) are skipped.

    The destination is read from JUST_DNA_PIPELINES_CACHE_DIR (or ~/.cache/just-dna-pipelines
    if not set). Pass --cache-dir to override.

    Examples:

        # Download using settings from .env
        uv run pipelines download-ensembl

        # Force re-download of all files
        uv run pipelines download-ensembl --force

        # Custom cache directory
        uv run pipelines download-ensembl --cache-dir /data/my-cache
    """
    import os
    import requests as req
    from huggingface_hub import list_repo_tree, get_token, hf_hub_url
    from platformdirs import user_cache_dir
    from rich.progress import (
        Progress, BarColumn, DownloadColumn, TextColumn,
        TransferSpeedColumn, TimeRemainingColumn, TaskProgressColumn,
    )

    # ── Resolve cache directory ────────────────────────────────────────────────
    if cache_dir:
        resolved_cache = Path(cache_dir)
    else:
        env_cache = os.getenv("JUST_DNA_PIPELINES_CACHE_DIR")
        resolved_cache = Path(env_cache) if env_cache else Path(user_cache_dir(appname="just-dna-pipelines"))

    target_dir = resolved_cache / "ensembl_variations" / "data"
    target_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[bold]Ensembl Variations Downloader[/bold]")
    console.print(f"  Repo   : [cyan]{repo_id}[/cyan]")
    console.print(f"  Target : [cyan]{target_dir}[/cyan]")
    console.print()

    # ── Fetch remote file manifest with sizes ──────────────────────────────────
    token = get_token()
    console.print("[dim]Fetching remote file manifest…[/dim]")
    remote_files = {
        Path(entry.path).name: entry.lfs.size if entry.lfs else entry.size
        for entry in list_repo_tree(repo_id, repo_type="dataset", token=token, recursive=True)
        if hasattr(entry, "path") and entry.path.startswith("data/") and entry.path.endswith(".parquet")
    }
    if not remote_files:
        console.print(f"[red]Error: no parquet files found in repo {repo_id}[/red]")
        raise typer.Exit(1)

    console.print(f"Manifest: [bold]{len(remote_files)}[/bold] files, "
                  f"[bold]{sum(remote_files.values()) / (1024**3):.1f} GB[/bold] total\n")

    # ── Classify each file ─────────────────────────────────────────────────────
    to_download: Dict[str, int] = {}

    def _is_valid(path: Path, expected_size: int) -> bool:
        return path.exists() and path.stat().st_size == expected_size

    skipped = 0
    for filename, size in remote_files.items():
        dest = target_dir / filename
        if not force and _is_valid(dest, size):
            skipped += 1
            continue
        to_download[filename] = size

    if skipped:
        console.print(f"[green]✓ {skipped} file(s) already complete — skipping.[/green]")
    if not to_download:
        total_gb = sum(f.stat().st_size for f in target_dir.glob("*.parquet")) / (1024**3)
        console.print(f"\n[bold green]✓ All done![/bold green]  {len(remote_files)} files, {total_gb:.2f} GB at {target_dir}\n")
        return

    console.print(f"\nDownloading [bold]{len(to_download)}[/bold] missing file(s)…\n")

    # ── Per-file download with byte-level progress bar ─────────────────────────
    errors: list[str] = []
    with Progress(
        TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
        BarColumn(bar_width=None),
        TaskProgressColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        for filename, expected_size in to_download.items():
            url = hf_hub_url(repo_id, filename=f"data/{filename}", repo_type="dataset")
            dest = target_dir / filename
            tmp = dest.with_suffix(".part")

            task = progress.add_task("", filename=filename, total=expected_size)

            headers = {"Authorization": f"Bearer {token}"} if token else {}
            with req.get(url, headers=headers, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                with open(tmp, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        fh.write(chunk)
                        progress.update(task, advance=len(chunk))

            actual_size = tmp.stat().st_size
            if actual_size != expected_size:
                tmp.unlink(missing_ok=True)
                errors.append(f"{filename}: expected {expected_size} bytes, got {actual_size}")
                progress.update(task, description=f"[red]✗ {filename}")
            else:
                tmp.rename(dest)
                progress.update(task, description=f"[green]✓ {filename}")

    # ── Summary ────────────────────────────────────────────────────────────────
    if errors:
        console.print(f"\n[bold red]✗ {len(errors)} file(s) failed:[/bold red]")
        for e in errors:
            console.print(f"  {e}")
        raise typer.Exit(1)

    final_files = list(target_dir.glob("*.parquet"))
    total_gb = sum(f.stat().st_size for f in final_files) / (1024**3)
    console.print(f"\n[bold green]✓ Done![/bold green]  {len(final_files)} files, {total_gb:.2f} GB at {target_dir}\n")


@app.command()
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
    import os
    import logging
    from platformdirs import user_cache_dir
    from just_dna_pipelines.annotation.duckdb_assets import build_duckdb_from_parquet

    logger = logging.getLogger("just_dna_pipelines.cli")

    if cache_dir:
        resolved_cache = Path(cache_dir)
    else:
        env_cache = os.getenv("JUST_DNA_PIPELINES_CACHE_DIR")
        resolved_cache = Path(env_cache) if env_cache else Path(user_cache_dir(appname="just-dna-pipelines"))

    ensembl_dir = resolved_cache / "ensembl_variations"
    data_dir = ensembl_dir / "data"
    duckdb_path = ensembl_dir / "ensembl_variations.duckdb"

    if not data_dir.exists() or not any(data_dir.glob("*.parquet")):
        console.print(
            f"[red]Error: Ensembl parquet cache not found at {data_dir}[/red]\n"
            "[dim]Run [bold]uv run pipelines download-ensembl[/bold] first.[/dim]"
        )
        raise typer.Exit(1)

    if duckdb_path.exists() and not force:
        size_mb = duckdb_path.stat().st_size / (1024 * 1024)
        console.print(
            f"[green]DuckDB already exists:[/green] {duckdb_path} ({size_mb:.1f} MB)\n"
            "[dim]Use --force to rebuild.[/dim]"
        )
        return

    if duckdb_path.exists():
        console.print(f"[yellow]Removing existing DuckDB: {duckdb_path}[/yellow]")
        duckdb_path.unlink()

    console.print(f"\n[bold]Building Ensembl DuckDB[/bold]")
    console.print(f"  Source : [cyan]{ensembl_dir}[/cyan]")
    console.print(f"  Output : [cyan]{duckdb_path}[/cyan]\n")

    _, metadata = build_duckdb_from_parquet(ensembl_dir, duckdb_path, logger=logger)

    console.print(f"[bold green]Done![/bold green]")
    console.print(f"  Views created    : {metadata['num_views']} ({metadata['view_names']})")
    console.print(f"  Parquet files    : {metadata['total_parquet_files']}")
    console.print(f"  Database size    : {metadata['db_size_mb']} MB")
    if "build_duration_sec" in metadata:
        console.print(f"  Build time       : {metadata['build_duration_sec']:.1f}s")
        console.print(f"  Peak memory      : {metadata['peak_memory_mb']:.0f} MB")
    console.print()


@app.command()
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
    Full Ensembl setup pipeline: download parquet, verify, build DuckDB.

    This is the recommended one-stop command for setting up the Ensembl
    annotation cache from scratch. It runs three steps in sequence:

      1. download-ensembl  — fetch parquet files from HuggingFace
      2. verify (inline)   — confirm all files are present
      3. build-duckdb      — create the DuckDB catalog over the parquet

    Already-complete steps are skipped automatically (use --force to redo).

    Examples:

        uv run pipelines ensembl-setup
        uv run pipelines ensembl-setup --force
        uv run pipelines ensembl-setup --cache-dir /data/my-cache
    """
    import os
    import logging
    from platformdirs import user_cache_dir
    from just_dna_pipelines.annotation.duckdb_assets import build_duckdb_from_parquet

    logger = logging.getLogger("just_dna_pipelines.cli")

    # ── Step 1: Download ──────────────────────────────────────────────────────
    console.print("[bold]Step 1/3: Download Ensembl parquet files[/bold]\n")
    download_ensembl(repo_id=repo_id, cache_dir=cache_dir, force=force)

    # ── Step 2: Verify ────────────────────────────────────────────────────────
    console.print("\n[bold]Step 2/3: Verify cache integrity[/bold]\n")

    if cache_dir:
        resolved_cache = Path(cache_dir)
    else:
        env_cache = os.getenv("JUST_DNA_PIPELINES_CACHE_DIR")
        resolved_cache = Path(env_cache) if env_cache else Path(user_cache_dir(appname="just-dna-pipelines"))

    ensembl_dir = resolved_cache / "ensembl_variations"
    data_dir = ensembl_dir / "data"
    parquet_files = list(data_dir.glob("*.parquet"))

    if not parquet_files:
        console.print(f"[red]Error: No parquet files found at {data_dir}[/red]")
        raise typer.Exit(1)

    total_gb = sum(f.stat().st_size for f in parquet_files) / (1024 ** 3)
    console.print(f"[green]Cache present:[/green] {len(parquet_files)} files, {total_gb:.2f} GB at {data_dir}")

    # ── Step 3: Build DuckDB ──────────────────────────────────────────────────
    console.print(f"\n[bold]Step 3/3: Build DuckDB[/bold]\n")

    duckdb_path = ensembl_dir / "ensembl_variations.duckdb"

    if duckdb_path.exists() and not force:
        size_mb = duckdb_path.stat().st_size / (1024 * 1024)
        console.print(f"[green]DuckDB already exists:[/green] {duckdb_path} ({size_mb:.1f} MB) — skipping.")
    else:
        if duckdb_path.exists():
            duckdb_path.unlink()
        console.print(f"  Source : [cyan]{ensembl_dir}[/cyan]")
        console.print(f"  Output : [cyan]{duckdb_path}[/cyan]\n")

        _, metadata = build_duckdb_from_parquet(ensembl_dir, duckdb_path, logger=logger)

        console.print(f"  Views  : {metadata['num_views']} ({metadata['view_names']})")
        console.print(f"  Files  : {metadata['total_parquet_files']}")
        console.print(f"  Size   : {metadata['db_size_mb']} MB")
        if "build_duration_sec" in metadata:
            console.print(f"  Time   : {metadata['build_duration_sec']:.1f}s")

    console.print(f"\n[bold green]Ensembl setup complete![/bold green]\n")


@app.command()
def list_modules() -> None:
    """
    List all available annotation modules (auto-discovered from configured sources).
    """
    from just_dna_pipelines.annotation.hf_modules import DISCOVERED_MODULES, MODULE_INFOS
    from just_dna_pipelines.module_config import get_module_meta, MODULES_CONFIG

    table = Table(title="Available Annotation Modules")
    table.add_column("Module", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Source", style="dim")

    for module in DISCOVERED_MODULES:
        meta = get_module_meta(module)
        info = MODULE_INFOS.get(module)
        source = info.source_url if info else ""
        table.add_row(module, meta.description or "", source)

    console.print(table)
    console.print(f"\n[dim]Sources: {', '.join(s.url for s in MODULES_CONFIG.sources)}[/dim]")
    console.print("[dim]Select modules with: uv run annotate genome.vcf -m <name> [-m <name> ...][/dim]")


@app.command()
def show_manifest(
    manifest_path: str = typer.Argument(
        ...,
        help="Path to manifest.json file",
    ),
) -> None:
    """
    Display the contents of an annotation manifest file.
    """
    import json

    path = Path(manifest_path)
    if not path.exists():
        console.print(f"[red]Error: Manifest not found: {path}[/red]")
        raise typer.Exit(1)

    with open(path) as f:
        manifest = json.load(f)

    console.print(f"\n[bold]Annotation Manifest[/bold]")
    console.print(f"  User: {manifest['user_name']}")
    console.print(f"  Sample: {manifest['sample_name']}")
    console.print(f"  Source VCF: {manifest['source_vcf']}")
    console.print(f"  Total variants: {manifest['total_variants_annotated']}")

    table = Table(title="Output Files")
    table.add_column("Module", style="cyan")
    table.add_column("Weights File", style="green")

    for m in manifest["modules"]:
        table.add_row(m["module"], m.get("weights_path", "N/A"))

    console.print(table)


def main() -> None:
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
