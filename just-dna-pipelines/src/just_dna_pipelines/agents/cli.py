"""
CLI commands for the module creator agent.

Mounted into the main pipelines CLI as ``uv run pipelines agent ...``.
"""
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

app = typer.Typer(
    name="agent",
    help="AI agent for creating annotation modules from papers and variant data.",
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
    input_file: Optional[Path] = typer.Option(
        None,
        "--file", "-f",
        help="Path to a PDF, CSV, or Markdown file with variant data.",
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Directory for spec output. Default: data/module_specs/agent_output/",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model", "-m",
        help="Gemini model ID. Default: GEMINI_MODEL env var or gemini-2.5-flash.",
    ),
    register: bool = typer.Option(
        False,
        "--register/--no-register",
        help="If set, automatically register the module after creation.",
    ),
) -> None:
    """
    Run the AI agent to create an annotation module from freeform input.

    Provide either --text with instructions, --file with a document, or both.
    The agent will parse the input, generate a module spec, validate it,
    and optionally register it.

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
    if not input_text and not input_file:
        console.print("[red]Error: provide --text and/or --file[/red]")
        raise typer.Exit(1)

    if input_file and not input_file.exists():
        console.print(f"[red]Error: file not found: {input_file}[/red]")
        raise typer.Exit(1)

    resolved_output = output_dir or Path("data/module_specs/agent_output")
    resolved_output.mkdir(parents=True, exist_ok=True)

    message_parts = []
    if input_file:
        suffix = input_file.suffix.lower()
        if suffix in (".md", ".txt", ".csv"):
            file_content = input_file.read_text(encoding="utf-8")
            message_parts.append(
                f"Here is the input document ({input_file.name}):\n\n{file_content}"
            )
            input_file = None  # text files go inline, not as Gemini file attachment
        else:
            message_parts.append(
                f"I've attached a file: {input_file.name}. "
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

    console.print("[bold]Module Creator Agent[/bold]")
    console.print(f"  Model  : [cyan]{model or 'default'}[/cyan]")
    console.print(f"  Output : [cyan]{resolved_output}[/cyan]")
    if input_file:
        console.print(f"  File   : [cyan]{input_file}[/cyan]")
    console.print()

    from just_dna_pipelines.agents.module_creator import create_module_agent

    agent = create_module_agent(
        model_id=model,
        spec_output_dir=resolved_output,
    )

    console.print("[bold green]Running agent...[/bold green]\n")

    kwargs: dict = {"show_tool_calls": True}
    if input_file:
        from agno.media import File
        kwargs["files"] = [File(filepath=input_file)]

    agent.print_response(full_message, **kwargs)

    if register:
        spec_dirs = [d for d in resolved_output.iterdir() if d.is_dir() and (d / "module_spec.yaml").exists()]
        if spec_dirs:
            from just_dna_pipelines.module_registry import register_custom_module
            for spec_dir in spec_dirs:
                console.print(f"\n[bold]Registering: {spec_dir.name}[/bold]")
                result = register_custom_module(spec_dir)
                if result.success:
                    console.print(f"[green]Registered '{spec_dir.name}' successfully![/green]")
                else:
                    console.print(f"[red]Registration failed: {result.errors}[/red]")
        else:
            console.print("[yellow]No spec directories found to register.[/yellow]")
