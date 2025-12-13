from pathlib import Path
from typing import Optional, Literal

import pyarrow as pa
import pyarrow.parquet as pq
import vortex as vx  # pip install vortex-data
import typer
from eliot import start_action, to_file


def parquet_to_vortex(
    parquet_path: Path,
    output_dir: Path | None = None,
    batch_size: int = 1_000_000,
    compression: Literal["default", "compact"] = "compact",
) -> Path:
    """
    Convert a Parquet file to Vortex in a streaming / batch-wise fashion.

    Parameters
    ----------
    parquet_path : Path
        Path to the input .parquet file.
    output_dir : Path | None
        Directory for the output .vortex file. If None, use parquet_path.parent.
    batch_size : int
        Target number of rows per batch when reading from Parquet.
    compression : Literal["default", "compact"]
        Compression mode: "default" balances size and performance, "compact" prioritizes smaller file sizes.

    Returns
    -------
    Path
        Path to the written .vortex file.
    """
    parquet_path = Path(parquet_path)
    if output_dir is None:
        output_dir = parquet_path.parent
    else:
        output_dir = Path(output_dir)

    vortex_path = output_dir / (parquet_path.stem + ".vortex")

    parquet_file = pq.ParquetFile(str(parquet_path))
    schema = parquet_file.schema_arrow

    def batch_iter():
        for batch in parquet_file.iter_batches(batch_size=batch_size):
            yield batch

    reader = pa.RecordBatchReader.from_batches(schema, batch_iter())
    
    # Choose compression options
    if compression == "compact":
        write_options = vx.io.VortexWriteOptions.compact()
    else:
        write_options = vx.io.VortexWriteOptions.default()
    
    # Write with the specified compression options
    write_options.write_path(reader, str(vortex_path))

    return vortex_path


def convert_folder_to_vortex(
    input_folder: Path,
    output_dir: Path | None = None,
    batch_size: int = 1_000_000,
    overwrite: bool = False,
    recursive: bool = True,
    compression: Literal["default", "compact"] = "compact",
) -> list[Path]:
    """
    Iteratively convert all Parquet files in a folder to Vortex format.

    Parameters
    ----------
    input_folder : Path
        Path to the folder containing .parquet files.
    output_dir : Path | None
        Directory for the output .vortex files. If None, use the same folder as each parquet file.
    batch_size : int
        Target number of rows per batch when reading from Parquet.
    overwrite : bool
        Whether to overwrite existing .vortex files. If False, skips files that already have vortex versions.
    recursive : bool
        Whether to search for parquet files recursively in subdirectories. Default is True.
    compression : Literal["default", "compact"]
        Compression mode: "default" balances size and performance, "compact" prioritizes smaller file sizes.

    Returns
    -------
    list[Path]
        List of paths to the written .vortex files.
    """
    with start_action(
        action_type="convert_folder_to_vortex",
        input_folder=str(input_folder),
        output_dir=str(output_dir) if output_dir else None,
        batch_size=batch_size,
        overwrite=overwrite,
        recursive=recursive,
        compression=compression,
    ) as action:
        input_folder = Path(input_folder)
        
        if not input_folder.exists():
            action.log(
                message_type="error",
                step="folder_not_found",
                folder=str(input_folder)
            )
            raise FileNotFoundError(f"Input folder not found: {input_folder}")
        
        if not input_folder.is_dir():
            action.log(
                message_type="error",
                step="path_is_not_directory",
                path=str(input_folder)
            )
            raise NotADirectoryError(f"Path is not a directory: {input_folder}")
        
        # Find all parquet files in the folder
        if recursive:
            parquet_files = list(input_folder.glob("**/*.parquet"))
        else:
            parquet_files = list(input_folder.glob("*.parquet"))
        
        action.log(
            message_type="info",
            step="found_parquet_files",
            num_files=len(parquet_files),
            files=[str(f) for f in parquet_files]
        )
        
        if not parquet_files:
            action.log(
                message_type="warning",
                step="no_parquet_files_found",
                folder=str(input_folder)
            )
            return []
        
        # Prepare output directory if specified
        if output_dir is not None:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        
        converted_files = []
        
        # Convert each parquet file
        for idx, parquet_file in enumerate(parquet_files, 1):
            with start_action(
                action_type="convert_single_file",
                file_index=idx,
                total_files=len(parquet_files),
                parquet_file=str(parquet_file)
            ) as file_action:
                # Determine output path
                if output_dir is None:
                    vortex_path = parquet_file.with_suffix('.vortex')
                else:
                    vortex_path = output_dir / f"{parquet_file.stem}.vortex"
                
                # Skip if file exists and overwrite is False
                if vortex_path.exists() and not overwrite:
                    file_action.log(
                        message_type="info",
                        step="vortex_exists_skipping",
                        vortex_path=str(vortex_path)
                    )
                    converted_files.append(vortex_path)
                    continue
                
                # Convert the file
                result_path = parquet_to_vortex(
                    parquet_path=parquet_file,
                    output_dir=output_dir if output_dir else parquet_file.parent,
                    batch_size=batch_size,
                    compression=compression,
                )
                
                file_action.log(
                    message_type="info",
                    step="conversion_complete",
                    output_path=str(result_path),
                    parquet_size_mb=round(parquet_file.stat().st_size / (1024 * 1024), 2),
                    vortex_size_mb=round(result_path.stat().st_size / (1024 * 1024), 2)
                )
                
                converted_files.append(result_path)
        
        action.log(
            message_type="info",
            step="all_conversions_complete",
            total_files=len(parquet_files),
            converted_files=len(converted_files)
        )
        
        return converted_files


# CLI Application
app = typer.Typer(help="Convert Parquet files to Vortex format")


@app.command()
def convert_folder(
    input_folder: Path = typer.Argument(..., help="Path to the folder containing .parquet files"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Output directory for .vortex files (default: same as input)"),
    batch_size: int = typer.Option(1_000_000, "--batch-size", "-b", help="Number of rows per batch when reading Parquet"),
    overwrite: bool = typer.Option(False, "--overwrite", "-f", help="Overwrite existing .vortex files"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r", help="Search for parquet files recursively in subdirectories"),
    compression: str = typer.Option("compact", "--compression", "-c", help="Compression mode: 'compact' (smaller files, default) or 'default' (balanced)"),
    log_file: Optional[Path] = typer.Option(None, "--log-file", "-l", help="Path to save Eliot log file"),
) -> None:
    """
    Convert all Parquet files in a folder to Vortex format.
    """
    # Validate compression option
    if compression not in ["default", "compact"]:
        typer.echo(f"Error: compression must be 'default' or 'compact', got '{compression}'", err=True)
        raise typer.Exit(1)
    
    # Setup logging if log file specified
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        to_file(open(str(log_file), "w"))
    
    # Convert files
    converted_files = convert_folder_to_vortex(
        input_folder=input_folder,
        output_dir=output_dir,
        batch_size=batch_size,
        overwrite=overwrite,
        recursive=recursive,
        compression=compression,  # type: ignore
    )
    
    # Print summary
    typer.echo(f"\n✓ Converted {len(converted_files)} files:")
    for vortex_file in converted_files:
        typer.echo(f"  - {vortex_file}")


@app.command()
def convert_single(
    parquet_file: Path = typer.Argument(..., help="Path to the .parquet file to convert"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Output directory for .vortex file (default: same as input)"),
    batch_size: int = typer.Option(1_000_000, "--batch-size", "-b", help="Number of rows per batch when reading Parquet"),
    compression: str = typer.Option("compact", "--compression", "-c", help="Compression mode: 'compact' (smaller files, default) or 'default' (balanced)"),
) -> None:
    """
    Convert a single Parquet file to Vortex format.
    """
    # Validate compression option
    if compression not in ["default", "compact"]:
        typer.echo(f"Error: compression must be 'default' or 'compact', got '{compression}'", err=True)
        raise typer.Exit(1)
    
    vortex_path = parquet_to_vortex(
        parquet_path=parquet_file,
        output_dir=output_dir,
        batch_size=batch_size,
        compression=compression,  # type: ignore
    )
    
    typer.echo(f"✓ Converted: {vortex_path}")


if __name__ == "__main__":
    app()
