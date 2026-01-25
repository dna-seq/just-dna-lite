"""
CLI for just-dna-pipelines.

Provides command-line interface for running annotation pipelines.
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="pipelines",
    help="Genomic annotation pipelines for VCF files.",
    no_args_is_help=True,
)

console = Console()


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
        help="HuggingFace dataset source in format 'repo_id/path/to/file.vcf'. "
             "Example: 'antonkulaga/personal-health/genetics/antonkulaga.vcf'",
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
             "Options: longevitymap,lipidmetabolism,vo2max,superhuman,coronary. "
             "If not specified, uses all modules.",
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

        # Annotate from HuggingFace with specific modules
        uv run pipelines annotate-modules \\
            --hf-source antonkulaga/personal-health/genetics/antonkulaga.vcf \\
            --user antonkulaga \\
            --modules longevitymap,coronary
    """
    from huggingface_hub import hf_hub_download

    from just_dna_pipelines.annotation.hf_modules import AnnotatorModule
    from just_dna_pipelines.annotation.hf_logic import annotate_vcf_with_all_modules
    from just_dna_pipelines.annotation.configs import HfModuleAnnotationConfig

    # Validate input source
    if vcf_path is None and hf_source is None:
        console.print("[red]Error: You must provide either --vcf or --hf-source[/red]")
        raise typer.Exit(1)

    if vcf_path is not None and hf_source is not None:
        console.print("[red]Error: Provide only one of --vcf or --hf-source, not both[/red]")
        raise typer.Exit(1)

    # Resolve VCF path
    if hf_source:
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
        
        resolved_vcf_path = Path(hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            repo_type="dataset",
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
        valid_modules = {m.value for m in AnnotatorModule.all_modules()}
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
def list_modules() -> None:
    """
    List all available annotation modules.
    """
    from just_dna_pipelines.annotation.hf_modules import AnnotatorModule

    table = Table(title="Available Annotation Modules")
    table.add_column("Module", style="cyan")
    table.add_column("Description", style="green")

    descriptions = {
        "longevitymap": "Longevity-associated variants from LongevityMap database",
        "lipidmetabolism": "Lipid metabolism and cardiovascular risk variants",
        "vo2max": "Athletic performance and VO2max-associated variants",
        "superhuman": "Elite performance and rare beneficial variants",
        "coronary": "Coronary artery disease associations",
    }

    for module in AnnotatorModule.all_modules():
        table.add_row(module.value, descriptions.get(module.value, ""))

    console.print(table)
    console.print("\n[dim]Use --modules with comma-separated values to select specific modules.[/dim]")


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
