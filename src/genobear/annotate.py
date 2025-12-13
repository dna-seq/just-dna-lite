"""
GenoBear Annotate CLI - Pipeline-based VCF annotation.

This module provides a CLI interface for annotating VCF files with genomic databases.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from eliot import start_action

from dotenv import load_dotenv

logs = Path("logs") if Path("logs").exists() else Path.cwd().parent / "logs"

load_dotenv()

# Set POLARS_VERBOSE from env if not already set (default: 0 for clean output)
if "POLARS_VERBOSE" not in os.environ:
    os.environ["POLARS_VERBOSE"] = "0"

from genobear.annotation.runners import annotate_vcf, download_ensembl_reference
from genobear.config import get_profile_enabled
from pycomfort.logging import to_nice_file, to_nice_stdout

# Create the main CLI app
app = typer.Typer(
    name="genobear-annotate",
    help="Genomic VCF Annotation Tool (using annotation pipelines)",
    rich_markup_mode="rich",
    no_args_is_help=True
)

console = Console()


@app.command()
def vcf(
    vcf_path: str = typer.Argument(
        ...,
        help="Path to the input VCF file to annotate"
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path for annotated parquet file. If not specified, saves to data/output/"
    ),
    cache_dir: Optional[str] = typer.Option(
        None,
        "--cache-dir",
        help="Cache directory for ensembl_variations data. Default: $GENOBEAR_CACHE_DIR or platform-specific cache"
    ),
    repo_id: str = typer.Option(
        "just-dna-seq/ensembl_variations",
        "--repo-id",
        help="HuggingFace repository ID for ensembl_variations dataset"
    ),
    variant_type: str = typer.Option(
        "SNV",
        "--variant-type",
        help="Variant type to use for annotation (SNV, INDEL, etc.)"
    ),
    token: Optional[str] = typer.Option(
        None,
        "--token",
        help="HuggingFace API token (if not set, uses HF_TOKEN env variable)"
    ),
    force_download: bool = typer.Option(
        False,
        "--force-download/--no-force-download",
        help="Force re-download of ensembl_variations data even if cache exists"
    ),
    workers: Optional[int] = typer.Option(
        None,
        "--workers",
        help="Number of workers for parallel processing (default: GENOBEAR_WORKERS or CPU count)"
    ),
    log: bool = typer.Option(
        True,
        "--log/--no-log",
        help="Enable detailed logging to files"
    ),
    run_folder: Optional[str] = typer.Option(
        None,
        "--run-folder",
        help="Optional run folder for pipeline execution and caching"
    ),
    vortex: bool = typer.Option(
        False,
        "--vortex/--no-vortex",
        help="Convert output to Vortex format for efficient storage and querying"
    ),
    profile: bool = typer.Option(
        get_profile_enabled(),
        "--profile/--no-profile",
        help="Track CPU, memory, and execution time for each pipeline step (default: $GENOBEAR_PROFILE or True)"
    ),
    cache: bool = typer.Option(
        True,
        "--cache/--no-cache",
        help="Enable pipeline caching for faster repeated runs (default: True)"
    ),
):
    """
    Annotate a VCF file with ensembl_variations data.
    
    This command:
    1. Checks if ensembl_variations cache exists (downloads if needed)
    2. Parses the input VCF to identify chromosomes
    3. Performs lazy joins with reference data for each chromosome
    4. Saves the annotated result to parquet
    5. Optionally converts to Vortex format for efficient storage
    
    Examples:
    
        # Basic annotation
        annotate vcf input.vcf.gz -o annotated.parquet
        
        # Annotate with custom cache directory
        annotate vcf input.vcf.gz -o output.parquet --cache-dir /path/to/cache
        
        # Force re-download of reference data
        annotate vcf input.vcf.gz --force-download
        
        # Annotate and convert to Vortex format
        annotate vcf input.vcf.gz -o annotated.parquet --vortex
    """
    console.print("[bold cyan]GenoBear VCF Annotation[/bold cyan]")
    console.print(f"Input VCF: {vcf_path}")
    
    # Convert paths
    vcf_input = Path(vcf_path)
    if not vcf_input.exists():
        console.print(f"[bold red]Error:[/bold red] VCF file not found: {vcf_path}")
        raise typer.Exit(code=1)
    
    # Determine output path
    if output is None:
        output_dir = Path("data") / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{vcf_input.stem}_annotated.parquet"
    else:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
    
    console.print(f"Output: {output_path}")
    
    cache_path = Path(cache_dir) if cache_dir else None
    
    # Execute annotation pipeline
    results = annotate_vcf(
        vcf_path=vcf_input,
        output_path=output_path,
        cache_dir=cache_path,
        repo_id=repo_id,
        variant_type=variant_type,
        token=token,
        force_download=force_download,
        workers=workers,
        log=log,
        run_folder=run_folder,
        save_vortex=vortex,
        profile=profile,
        cache=cache,
    )
    
    console.print("[bold green]✓[/bold green] Annotation completed successfully!")
    
    # Get the actual saved path from results
    saved_path = None
    vortex_saved_path = None
    if results and isinstance(results, dict):
        if "annotated_vcf_path" in results:
            saved_path = results["annotated_vcf_path"]
        elif output_path:
            # Fallback to the provided output_path
            saved_path = output_path
        if "vortex_path" in results:
            vortex_saved_path = results["vortex_path"]
    
    if saved_path:
        saved_path = Path(saved_path)
        if saved_path.exists():
            file_size_mb = saved_path.stat().st_size / (1024 * 1024)
            console.print(f"Annotated file saved to: {saved_path}")
            console.print(f"File size: {file_size_mb:.2f} MB")
        else:
            console.print(f"[bold yellow]Warning:[/bold yellow] Output path specified but file not found: {saved_path}")
    else:
        console.print(f"[bold yellow]Warning:[/bold yellow] No output path returned from pipeline")
        if output_path:
            console.print(f"Expected output at: {output_path}")
    
    if vortex_saved_path:
        vortex_saved_path = Path(vortex_saved_path)
        if vortex_saved_path.exists():
            vortex_size_mb = vortex_saved_path.stat().st_size / (1024 * 1024)
            console.print(f"Vortex file saved to: {vortex_saved_path}")
            console.print(f"Vortex file size: {vortex_size_mb:.2f} MB")
            if saved_path and saved_path.exists():
                compression_ratio = (1 - vortex_size_mb / file_size_mb) * 100
                console.print(f"Compression ratio: {compression_ratio:.1f}%")
        else:
            console.print(f"[bold yellow]Warning:[/bold yellow] Vortex path specified but file not found: {vortex_saved_path}")
    
    # Display profiling stats if enabled
    if profile and results and isinstance(results, dict) and "profiling_report" in results:
        console.print("\n[bold cyan]Resource Usage Report:[/bold cyan]")
        console.print(results["profiling_report"])
        
        # Warn if profiling shows zeros (caching)
        report = results["profiling_report"]
        if "| 0       " in report or any("| 0              " in line for line in report.split("\n")):
            console.print(
                "\n[bold yellow]Note:[/bold yellow] Profiling shows 0 calls because functions were skipped due to caching."
            )
            console.print(
                "Use [cyan]--no-cache[/cyan] to force re-execution and see actual resource usage, "
                "or use [cyan]htop[/cyan] / [cyan]/usr/bin/time -v[/cyan] for real-time monitoring."
            )


@app.command()
def download_reference(
    cache_dir: Optional[str] = typer.Option(
        None,
        "--cache-dir",
        help="Cache directory for ensembl_variations data. Default: $GENOBEAR_CACHE_DIR or platform-specific cache"
    ),
    repo_id: str = typer.Option(
        "just-dna-seq/ensembl_variations",
        "--repo-id",
        help="HuggingFace repository ID for ensembl_variations dataset"
    ),
    token: Optional[str] = typer.Option(
        None,
        "--token",
        help="HuggingFace API token (if not set, uses HF_TOKEN env variable)"
    ),
    force: bool = typer.Option(
        False,
        "--force/--no-force",
        help="Force re-download even if cache exists"
    ),
    log: bool = typer.Option(
        True,
        "--log/--no-log",
        help="Enable detailed logging to files"
    ),
):
    """
    Download ensembl_variations reference data from HuggingFace Hub.
    
    This command downloads the reference annotation data to the local cache.
    If the cache already exists, download is skipped unless --force is used.
    
    Examples:
    
        # Download to default cache location
        annotate download-reference
        
        # Download to custom location
        annotate download-reference --cache-dir /path/to/cache
        
        # Force re-download
        annotate download-reference --force
    """
    console.print("[bold cyan]GenoBear Reference Download[/bold cyan]")
    
    cache_path = Path(cache_dir) if cache_dir else None
    
    results = download_ensembl_reference(
        cache_dir=cache_path,
        repo_id=repo_id,
        token=token,
        force_download=force,
        log=log,
    )
    
    if "ensembl_cache_path" in results:
        downloaded_path = results["ensembl_cache_path"]
        console.print("[bold green]✓[/bold green] Download completed successfully!")
        console.print(f"Reference data available at: {downloaded_path}")
    else:
        console.print("[bold yellow]Warning:[/bold yellow] No cache path returned")


if __name__ == "__main__":
    app()

