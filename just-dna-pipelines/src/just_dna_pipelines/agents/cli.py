"""
CLI commands for the module creator agent team.

Mounted into the main pipelines CLI as ``uv run pipelines agent ...``.
"""
from pathlib import Path
from typing import List, Optional

import typer
from agno.media import File as AgnoFile
from rich.console import Console

from just_dna_pipelines.agents.module_creator import create_module_team, _describe_team
from just_dna_pipelines.module_registry import register_custom_module

MAX_ATTACHMENTS = 5

app = typer.Typer(
    name="agent",
    help="AI agent team for creating annotation modules from papers and variant data.",
    no_args_is_help=True,
)

console = Console()


@app.command("create-module")
def create_module(
    input_text: Optional[str] = typer.Option(
        None,
        "--text", "-t",
        help="Freeform text instructions for the agent.",
    ),
    input_file: Optional[List[Path]] = typer.Option(
        None,
        "--file", "-f",
        help="Path to an input file (repeat up to 5 times): PDF/CSV/Markdown/TXT.",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Directory for spec output. Default: data/module_specs/agent_output/",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model", "-m",
        help="Gemini model ID for PI. Default: GEMINI_MODEL env var or gemini-3-pro-preview.",
    ),
    register: bool = typer.Option(
        False,
        "--register/--no-register",
        help="If set, automatically register the module after creation.",
    ),
) -> None:
    """
    Run the AI agent team to create an annotation module from freeform input.

    The team consists of researcher agents (using all available LLM API keys),
    a reviewer with Google Search fact-checking, and a PI that synthesizes
    findings into the final module.

    Provide either --text with instructions, --file with a document, or both.

    Examples:

        # From a markdown file with variant descriptions
        uv run pipelines agent create-module --file data/module_specs/evals/mthfr_nad/freeform_input.md

        # From inline text
        uv run pipelines agent create-module --text "Create a module for BRCA1 and BRCA2 breast cancer variants"

        # With a research paper PDF
        uv run pipelines agent create-module --file paper.pdf --text "Focus on Table 2 variants"

        # Auto-register after creation
        uv run pipelines agent create-module --file input.md --register
    """
    input_files: List[Path] = list(input_file or [])

    if not input_text and not input_files:
        console.print("[red]Error: provide --text and/or --file[/red]")
        raise typer.Exit(1)

    if len(input_files) > MAX_ATTACHMENTS:
        console.print(f"[red]Error: at most {MAX_ATTACHMENTS} files are supported[/red]")
        raise typer.Exit(1)

    for path in input_files:
        if not path.exists():
            console.print(f"[red]Error: file not found: {path}[/red]")
            raise typer.Exit(1)

    resolved_output = output_dir or Path("data/module_specs/agent_output")
    resolved_output.mkdir(parents=True, exist_ok=True)

    message_parts = []
    attached_files: List[Path] = []
    for path in input_files:
        suffix = path.suffix.lower()
        if suffix in (".md", ".txt", ".csv"):
            file_content = path.read_text(encoding="utf-8")
            message_parts.append(
                f"Here is the input document ({path.name}):\n\n{file_content}"
            )
        else:
            attached_files.append(path)
            message_parts.append(
                f"I've attached a file: {path.name}. "
                "Please analyze it and create an annotation module."
            )

    if input_text:
        message_parts.append(input_text)

    message_parts.append(
        f"\nWrite the spec files to: {resolved_output}/<module_name>/ "
        f"using the write_spec_files tool. "
        f"Then call validate_spec on the resulting directory."
    )

    full_message = "\n\n".join(message_parts)

    team = create_module_team(
        model_id=model,
        spec_output_dir=resolved_output,
    )

    console.print("[bold]Module Creator Team[/bold]")
    console.print(f"  PI Model : [cyan]{model or 'default'}[/cyan]")
    console.print(f"  Output   : [cyan]{resolved_output}[/cyan]")
    console.print(f"  Team     : [cyan]{_describe_team(team)}[/cyan]")
    if input_files:
        console.print(f"  Files    : [cyan]{', '.join(str(path) for path in input_files)}[/cyan]")
    console.print()

    console.print("[bold green]Running team...[/bold green]\n")

    kwargs: dict = {"show_tool_calls": True, "stream": True}
    if attached_files:
        kwargs["files"] = [AgnoFile(filepath=path) for path in attached_files]

    team.print_response(full_message, **kwargs)

    if register:
        spec_dirs = [d for d in resolved_output.iterdir() if d.is_dir() and (d / "module_spec.yaml").exists()]
        if spec_dirs:
            for spec_dir in spec_dirs:
                console.print(f"\n[bold]Registering: {spec_dir.name}[/bold]")
                result = register_custom_module(spec_dir)
                if result.success:
                    console.print(f"[green]Registered '{spec_dir.name}' successfully![/green]")
                else:
                    console.print(f"[red]Registration failed: {result.errors}[/red]")
        else:
            console.print("[yellow]No spec directories found to register.[/yellow]")
