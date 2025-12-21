"""
GenoBear Annotate Prefect CLI - Prefect-based VCF annotation.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer
import polars as pl
from rich.console import Console
from genobear.runtime import load_env

from genobear.annotation.runners import annotate_vcf

load_env()

# Set Polars env vars
os.environ.setdefault("POLARS_VERBOSE", "0")
os.environ.setdefault("POLARS_ENGINE_AFFINITY", "streaming")
os.environ.setdefault("POLARS_LOW_MEMORY", "1")

app = typer.Typer(
    name="genobear-annotate-prefect",
    help="Genomic VCF Annotation Tool (using Prefect flows)",
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
        help="Output path for annotated parquet file"
    ),
    cache_dir: Optional[str] = typer.Option(
        None,
        "--cache-dir",
        help="Cache directory for ensembl_variations data"
    ),
    repo_id: str = typer.Option(
        "just-dna-seq/ensembl_variations",
        "--repo-id",
        help="HuggingFace repository ID"
    ),
    variant_type: str = typer.Option(
        "SNV",
        "--variant-type",
        help="Variant type (SNV, INDEL, etc.)"
    ),
    token: Optional[str] = typer.Option(
        None,
        "--token",
        help="HuggingFace API token"
    ),
    force_download: bool = typer.Option(
        False,
        "--force-download/--no-force-download",
        help="Force re-download of reference data"
    ),
    profile: bool = typer.Option(
        True,
        "--profile/--no-profile",
        help="Track and display resource usage (time and memory)"
    ),
):
    """
    Annotate a VCF file using Prefect flows.
    """
    console.print("[bold cyan]GenoBear VCF Annotation (Prefect)[/bold cyan]")
    
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
    
    console.print(f"Input VCF: {vcf_path}")
    console.print(f"Output: {output_path}")

    # Use the high-level annotate_vcf function which handles everything
    # including Prefect flows and resource tracking
    results = annotate_vcf(
        vcf_path=vcf_input,
        output_path=output_path,
        cache_dir=Path(cache_dir) if cache_dir else None,
        repo_id=repo_id,
        variant_type=variant_type,
        token=token,
        force_download=force_download,
        profile=profile,
        log=True
    )

    console.print("[bold green]✓[/bold green] Prefect annotation completed!")

    if output_path.exists():
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        console.print(f"Annotated file saved to: {output_path} ({file_size_mb:.2f} MB)")


@app.command()
def version():
    """Show version information."""
    try:
        import importlib.metadata
        version = importlib.metadata.version("genobear")
        console.print(f"genobear version: [bold green]{version}[/bold green]")
    except importlib.metadata.PackageNotFoundError:
        console.print("genobear version: [yellow]development[/yellow]")


if __name__ == "__main__":
    app()

