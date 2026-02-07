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
def list_modules() -> None:
    """
    List all available annotation modules.
    """
    from just_dna_pipelines.annotation.hf_modules import DISCOVERED_MODULES

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

    for module in DISCOVERED_MODULES:
        table.add_row(module, descriptions.get(module, ""))

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
