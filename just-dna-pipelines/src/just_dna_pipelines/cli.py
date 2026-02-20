"""
CLI for just-dna-pipelines.

Provides command-line interface for running annotation pipelines.
"""

from pathlib import Path
from typing import Dict, Optional

import typer
from rich.console import Console
from rich.table import Table

from just_dna_pipelines.module_compiler.cli import app as module_app
from just_dna_pipelines.agents.cli import app as agent_app

app = typer.Typer(
    name="pipelines",
    help="Genomic annotation pipelines for VCF files.",
    no_args_is_help=True,
)
app.add_typer(module_app, name="module")
app.add_typer(agent_app, name="agent")

console = Console()


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
def annotate_modules(
    vcf_path: Optional[str] = typer.Option(
        None,
        "--vcf", "-v",
        help="Path to local VCF file to annotate.",
    ),
    hf_source: Optional[str] = typer.Option(
        None,
        "--hf-source", "-s",
        help="HuggingFace dataset source in format 'repo_id/path/to/file.vcf'.",
    ),
    zenodo_source: Optional[str] = typer.Option(
        None,
        "--zenodo", "-z",
        help="Zenodo record URL or direct file URL. Example: 'https://zenodo.org/records/18370498'",
    ),
    user_name: str = typer.Option(
        ...,
        "--user", "-u",
        help="User name for organizing outputs.",
    ),
    sample_name: Optional[str] = typer.Option(
        None,
        "--sample", "-n",
        help="Sample name. If not provided, uses VCF filename stem.",
    ),
    modules: Optional[str] = typer.Option(
        None,
        "--modules", "-m",
        help="Comma-separated list of modules to use. "
             "Run 'pipelines list-modules' to see available modules. "
             "If not specified, uses all discovered modules.",
    ),
    output_dir: Optional[str] = typer.Option(
        None,
        "--output", "-o",
        help="Output directory. Default: data/output/users/{user}/{sample}/modules/",
    ),
    compression: str = typer.Option(
        "zstd",
        "--compression", "-c",
        help="Parquet compression: zstd, snappy, lz4, gzip.",
    ),
) -> None:
    """
    Annotate a VCF file with HuggingFace annotation modules.

    You must provide either --vcf for a local file or --hf-source for a HuggingFace file.

    Examples:

        # Annotate a local VCF with all modules
        uv run pipelines annotate-modules --vcf /path/to/sample.vcf --user myuser

        # Annotate from Zenodo with specific modules (recommended for personal health data)
        uv run pipelines annotate-modules \\
            --zenodo https://zenodo.org/records/18370498 \\
            --user antonkulaga \\
            --modules longevitymap,coronary

        # Annotate from HuggingFace
        uv run pipelines annotate-modules \\
            --hf-source some-repo/data/sample.vcf \\
            --user someuser
    """
    from huggingface_hub import hf_hub_download

    from just_dna_pipelines.annotation.hf_modules import get_all_modules, DISCOVERED_MODULES
    from just_dna_pipelines.annotation.hf_logic import annotate_vcf_with_all_modules
    from just_dna_pipelines.annotation.configs import HfModuleAnnotationConfig

    # Validate input source
    sources = [vcf_path, hf_source, zenodo_source]
    num_sources = sum(1 for s in sources if s is not None)
    
    if num_sources == 0:
        console.print("[red]Error: You must provide either --vcf, --hf-source, or --zenodo[/red]")
        raise typer.Exit(1)
        
    if num_sources > 1:
        console.print("[red]Error: Provide only one of --vcf, --hf-source, or --zenodo, not multiple[/red]")
        raise typer.Exit(1)

    # Resolve VCF path
    if zenodo_source:
        console.print(f"[blue]Downloading VCF from Zenodo: {zenodo_source}[/blue]")
        import requests
        
        # If it's a record URL, we need to find the VCF file
        if "/records/" in zenodo_source and "/files/" not in zenodo_source:
            record_id = zenodo_source.split("/records/")[-1].split("?")[0]
            api_url = f"https://zenodo.org/api/records/{record_id}"
            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()
            
            # Find the first VCF file
            vcf_file = next((f for f in data["files"] if f["key"].endswith(".vcf") or f["key"].endswith(".vcf.gz")), None)
            if not vcf_file:
                console.print(f"[red]Error: No VCF file found in Zenodo record {record_id}[/red]")
                raise typer.Exit(1)
            
            download_url = vcf_file["links"]["self"]
            filename = vcf_file["key"]
        else:
            download_url = zenodo_source
            filename = zenodo_source.split("/")[-1].split("?")[0]
            if not (filename.endswith(".vcf") or filename.endswith(".vcf.gz")):
                filename = "genome.vcf"

        # Use ~/.cache/just-dna-pipelines/zenodo/ for caching
        cache_dir = Path.home() / ".cache" / "just-dna-pipelines" / "zenodo"
        cache_dir.mkdir(parents=True, exist_ok=True)
        resolved_vcf_path = cache_dir / filename
        
        if not resolved_vcf_path.exists():
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            with open(resolved_vcf_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        console.print(f"[green]Downloaded to: {resolved_vcf_path}[/green]")

    elif hf_source:
        console.print(f"[blue]Downloading VCF from HuggingFace: {hf_source}[/blue]")
        
        # Parse HuggingFace source: repo_id/path/to/file.vcf
        parts = hf_source.split("/", 1)
        if len(parts) < 2:
            console.print("[red]Error: HF source must be in format 'owner/repo/path/to/file.vcf'[/red]")
            raise typer.Exit(1)
        
        # Find where repo_id ends (first two parts) and filename begins
        all_parts = hf_source.split("/")
        if len(all_parts) < 3:
            console.print("[red]Error: HF source must include repo owner, repo name, and file path[/red]")
            raise typer.Exit(1)
        
        repo_id = f"{all_parts[0]}/{all_parts[1]}"
        filename = "/".join(all_parts[2:])
        
        # Import get_token for authentication
        from huggingface_hub import get_token
        token = get_token()
        
        resolved_vcf_path = Path(hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            repo_type="dataset",
            token=token,
        ))
        console.print(f"[green]Downloaded to: {resolved_vcf_path}[/green]")
    else:
        resolved_vcf_path = Path(vcf_path)
        if not resolved_vcf_path.exists():
            console.print(f"[red]Error: VCF file not found: {resolved_vcf_path}[/red]")
            raise typer.Exit(1)

    # Parse modules
    module_list: Optional[list[str]] = None
    if modules:
        module_list = [m.strip().lower() for m in modules.split(",")]
        # Validate modules
        valid_modules = set(DISCOVERED_MODULES)
        for m in module_list:
            if m not in valid_modules:
                console.print(f"[red]Error: Unknown module '{m}'. Valid: {sorted(valid_modules)}[/red]")
                raise typer.Exit(1)

    # Determine sample name
    resolved_sample_name = sample_name or resolved_vcf_path.stem

    # Create config
    config = HfModuleAnnotationConfig(
        vcf_path=str(resolved_vcf_path),
        user_name=user_name,
        sample_name=resolved_sample_name,
        modules=module_list,
        output_dir=output_dir,
        compression=compression,
    )

    # Show configuration
    console.print("\n[bold]Configuration:[/bold]")
    console.print(f"  VCF: {resolved_vcf_path}")
    console.print(f"  User: {user_name}")
    console.print(f"  Sample: {resolved_sample_name}")
    console.print(f"  Modules: {module_list or 'all'}")
    console.print(f"  Compression: {compression}")
    console.print()

    # Create a logger adapter for Rich console
    class RichLogger:
        def info(self, msg: str) -> None:
            console.print(f"[blue]INFO:[/blue] {msg}")

        def warning(self, msg: str) -> None:
            console.print(f"[yellow]WARN:[/yellow] {msg}")

        def debug(self, msg: str) -> None:
            pass

    # Run annotation
    console.print("[bold green]Starting annotation...[/bold green]\n")
    
    manifest, metadata = annotate_vcf_with_all_modules(
        logger=RichLogger(),
        vcf_path=resolved_vcf_path,
        config=config,
        user_name=user_name,
        sample_name=resolved_sample_name,
    )

    # Display results
    console.print("\n[bold green]Annotation Complete![/bold green]\n")

    # Create results table
    table = Table(title="Module Annotation Results")
    table.add_column("Module", style="cyan")
    table.add_column("Output File", style="green")

    for m in manifest.modules:
        table.add_row(m.module, m.weights_path or "N/A")

    console.print(table)
    console.print(f"\n[bold]Total variants annotated:[/bold] {manifest.total_variants_annotated}")
    console.print(f"[bold]Manifest:[/bold] {manifest.modules[0].weights_path.rsplit('/', 1)[0]}/manifest.json")


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
    ctx = typer.Context(download_ensembl)
    ctx.invoke(
        download_ensembl,
        repo_id=repo_id,
        cache_dir=cache_dir,
        force=force,
    )

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
    console.print("[dim]Use --modules with comma-separated values to select specific modules.[/dim]")


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
