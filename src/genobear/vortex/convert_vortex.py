"""CLI for converting parquet files to Vortex format."""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from eliot import to_file
from pycomfort.logging import to_nice_file, to_nice_stdout

from genobear.vortex.parquet_to_vortex import (
    parquet_to_vortex,
    convert_ensembl_directory_to_vortex,
)

app = typer.Typer(
    name="convert-vortex",
    help="Convert parquet files to Vortex format for efficient storage and querying",
    add_completion=False,
)
console = Console()


@app.command()
def file(
    parquet_path: Path = typer.Argument(
        ...,
        help="Path to the input parquet file",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    vortex_path: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Path where to save the Vortex file. If not provided, saves next to parquet with .vortex extension",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "-f",
        help="Whether to overwrite existing Vortex file",
    ),
    batch_size: int = typer.Option(
        100_000,
        "--batch-size",
        "-b",
        help="Number of rows per batch for streaming (larger = more memory, faster)",
    ),
    log_dir: Path = typer.Option(
        Path("logs"),
        "--log-dir",
        "-l",
        help="Directory for log files",
    ),
) -> None:
    """
    Convert a single parquet file to Vortex format.
    
    Uses streaming to handle large multi-gigabyte files efficiently without
    loading the entire file into memory.
    
    Example:
        convert-vortex file data/variants.parquet
        convert-vortex file data/large_file.parquet --batch-size 50000
        convert-vortex file data/variants.parquet --output data/variants.vortex
        convert-vortex file data/variants.parquet --overwrite
    """
    # Setup logging
    log_dir.mkdir(parents=True, exist_ok=True)
    json_path = log_dir / "parquet_to_vortex.json"
    log_path = log_dir / "parquet_to_vortex.log"
    
    to_nice_file(output_file=json_path, rendered_file=log_path)
    to_nice_stdout(output_file=json_path)
    
    console.print(f"[bold blue]Converting parquet to Vortex format (streaming)[/bold blue]")
    console.print(f"Input: {parquet_path}")
    console.print(f"Batch size: {batch_size:,} rows")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Converting...", total=None)
        
        try:
            result_path = parquet_to_vortex(
                parquet_path=parquet_path,
                vortex_path=vortex_path,
                overwrite=overwrite,
                batch_size=batch_size,
            )
            
            progress.update(task, completed=True)
            console.print(f"[bold green]✓[/bold green] Conversion complete!")
            console.print(f"Output: {result_path}")
            
            # Show file sizes for comparison
            parquet_size_mb = parquet_path.stat().st_size / (1024 * 1024)
            vortex_size_mb = result_path.stat().st_size / (1024 * 1024)
            compression_ratio = (1 - vortex_size_mb / parquet_size_mb) * 100 if parquet_size_mb > 0 else 0
            
            console.print(f"\n[bold]File sizes:[/bold]")
            console.print(f"  Parquet: {parquet_size_mb:.2f} MB")
            console.print(f"  Vortex:  {vortex_size_mb:.2f} MB")
            if compression_ratio > 0:
                console.print(f"  Compression: {compression_ratio:.1f}% smaller")
            elif compression_ratio < 0:
                console.print(f"  Size increase: {abs(compression_ratio):.1f}% larger")
            
        except Exception as e:
            progress.update(task, completed=True)
            console.print(f"[bold red]✗[/bold red] Conversion failed: {e}")
            raise typer.Exit(code=1)


@app.command()
def ensembl(
    ensembl_cache_path: Path = typer.Argument(
        ...,
        help="Path to Ensembl cache directory (containing variant type subdirectories)",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
    ),
    variant_type: str = typer.Option(
        "SNV",
        "--variant-type",
        "-t",
        help="Variant type directory to convert (e.g., SNV, INDEL)",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Optional output directory for Vortex files. If not provided, saves next to parquet files",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "-f",
        help="Whether to overwrite existing Vortex files",
    ),
    batch_size: int = typer.Option(
        100_000,
        "--batch-size",
        "-b",
        help="Number of rows per batch for streaming (larger = more memory, faster)",
    ),
    log_dir: Path = typer.Option(
        Path("logs"),
        "--log-dir",
        "-l",
        help="Directory for log files",
    ),
) -> None:
    """
    Convert all Ensembl parquet files in a directory to Vortex format.
    
    This command scans a directory containing Ensembl annotation parquet files
    and converts them all to Vortex format for improved query performance.
    Uses streaming to handle large multi-gigabyte files efficiently.
    
    Example:
        convert-vortex ensembl ~/.cache/genobear/ensembl_variations/splitted_variants
        convert-vortex ensembl ./data/ensembl --variant-type SNV --batch-size 50000
        convert-vortex ensembl ./data/ensembl --output-dir ./data/vortex
        convert-vortex ensembl ./data/ensembl --overwrite
    """
    # Setup logging
    log_dir.mkdir(parents=True, exist_ok=True)
    json_path = log_dir / "convert_ensembl_to_vortex.json"
    log_path = log_dir / "convert_ensembl_to_vortex.log"
    
    to_nice_file(output_file=json_path, rendered_file=log_path)
    to_nice_stdout(output_file=json_path)
    
    console.print(f"[bold blue]Converting Ensembl parquet files to Vortex format (streaming)[/bold blue]")
    console.print(f"Input directory: {ensembl_cache_path}")
    console.print(f"Variant type: {variant_type}")
    console.print(f"Batch size: {batch_size:,} rows")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Converting...", total=None)
        
        try:
            result_dir = convert_ensembl_directory_to_vortex(
                ensembl_cache_path=ensembl_cache_path,
                variant_type=variant_type,
                output_dir=output_dir,
                overwrite=overwrite,
                batch_size=batch_size,
            )
            
            progress.update(task, completed=True)
            console.print(f"[bold green]✓[/bold green] Conversion complete!")
            console.print(f"Output directory: {result_dir}")
            
            # Count converted files
            vortex_files = list(result_dir.glob("*.vortex"))
            console.print(f"Converted {len(vortex_files)} file(s)")
            
        except Exception as e:
            progress.update(task, completed=True)
            console.print(f"[bold red]✗[/bold red] Conversion failed: {e}")
            raise typer.Exit(code=1)


if __name__ == "__main__":
    app()



