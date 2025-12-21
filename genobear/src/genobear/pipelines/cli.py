"""
GenoBear Pipelines CLI - Manage and serve Prefect pipelines.

This provides commands for:
- Listing available pipelines
- Serving pipelines via Prefect
- Managing pipeline registry
"""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from genobear.runtime import load_env
from genobear.pipelines.registry import store, PipelineCategory
from genobear.pipelines.serve import serve_pipelines

load_env()

app = typer.Typer(
    name="gb",
    help="GenoBear CLI - Manage and run genomic pipelines",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

console = Console()


@app.command()
def list(
    category: Optional[str] = typer.Option(
        None,
        "--category",
        "-c",
        help="Filter by category (annotation, preparation, analysis, upload, utility, custom)",
    ),
    source: Optional[str] = typer.Option(
        None,
        "--source",
        "-s",
        help="Filter by source (builtin, entrypoint, custom)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed information",
    ),
) -> None:
    """List all registered pipelines."""
    cat = PipelineCategory(category) if category else None
    pipelines = store.list_pipelines(category=cat, source=source)
    
    if not pipelines:
        console.print("[yellow]No pipelines found matching criteria.[/yellow]")
        return
    
    table = Table(title="Registered Pipelines", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Category", style="green")
    table.add_column("Description", style="white")
    
    if verbose:
        table.add_column("Source", style="yellow")
        table.add_column("Tags", style="blue")
    
    for info in pipelines:
        if verbose:
            table.add_row(
                info.name,
                info.category.value,
                info.description[:60] + "..." if len(info.description) > 60 else info.description,
                info.source,
                ", ".join(info.tags[:3]),
            )
        else:
            table.add_row(
                info.name,
                info.category.value,
                info.description[:80] + "..." if len(info.description) > 80 else info.description,
            )
    
    console.print(table)
    console.print(f"\n[bold]Total:[/bold] {len(pipelines)} pipeline(s)")


@app.command("run")
def start_pipelines(
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        "-h",
        help="Host for the Prefect server check",
    ),
    port: int = typer.Option(
        4200,
        "--port",
        "-p",
        help="Port for the Prefect server check",
    ),
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        "-l",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    ),
    limit: Optional[int] = typer.Option(
        None,
        "--limit",
        help="Limit on concurrent flow runs",
    ),
) -> None:
    """Start the Prefect server (if needed) and the GenoBear pipelines.
    
    This starts a long-running process that serves all registered
    GenoBear flows via Prefect. 
    
    To see the UI and manage deployments, open http://localhost:4200/flows 
    in your browser.
    """
    console.print("[bold cyan]GenoBear Pipelines[/bold cyan]")
    console.print(f"Log Level: {log_level}")
    
    pipelines = store.list_pipelines()
    console.print(f"\n[bold]Available pipelines:[/bold] {len(pipelines)}")
    
    for info in pipelines:
        console.print(f"  [green]•[/green] {info.name} ({info.category.value})")
    
    console.print("\n[bold yellow]Starting pipelines...[/bold yellow]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")
    
    serve_pipelines(
        host=host,
        port=port,
        log_level=log_level,
        limit=limit,
    )


@app.command()
def info(
    name: str = typer.Argument(
        ...,
        help="Pipeline name to get info for",
    ),
) -> None:
    """Show detailed information about a specific pipeline."""
    pipeline = store.get(name)
    
    if pipeline is None:
        console.print(f"[red]Pipeline not found: {name}[/red]")
        raise typer.Exit(code=1)
    
    console.print(f"\n[bold cyan]{pipeline.name}[/bold cyan]")
    console.print(f"[dim]{'─' * 40}[/dim]")
    console.print(f"[bold]Category:[/bold] {pipeline.category.value}")
    console.print(f"[bold]Version:[/bold] {pipeline.version}")
    console.print(f"[bold]Author:[/bold] {pipeline.author or 'Unknown'}")
    console.print(f"[bold]Source:[/bold] {pipeline.source}")
    console.print(f"[bold]Tags:[/bold] {', '.join(pipeline.tags) or 'None'}")
    console.print(f"\n[bold]Description:[/bold]")
    console.print(f"  {pipeline.description or 'No description available'}")


@app.command()
def version() -> None:
    """Show version information."""
    import importlib.metadata
    ver = importlib.metadata.version("genobear")
    console.print(f"genobear version: [bold green]{ver}[/bold green]")


if __name__ == "__main__":
    app()

