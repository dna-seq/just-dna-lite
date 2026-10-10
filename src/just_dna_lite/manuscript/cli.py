"""`manuscript`: one CLI for the manuscript sources in `docs/manuscript/` (see its README.md)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from just_dna_lite.manuscript.build import (
    TECTONIC_ENV_VAR,
    build_paths,
    latex_to_pdf,
    markdown_to_latex,
    stale_pdf_note,
    write_clean_twin,
)
from just_dna_lite.manuscript.ledger import LedgerError, ledger_app
from just_dna_pipelines.runtime import load_env

app = typer.Typer(
    name="manuscript",
    help="Manuscript tools: the revision ledger in the Markdown source, and the PDF build.",
    no_args_is_help=True,
)
app.add_typer(ledger_app, name="ledger")


@app.command()
def build(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True, help="Markdown master")],
    out: Annotated[
        Optional[Path], typer.Option("--out", "-o", file_okay=False, help="Output directory (default: build/ beside PATH)")
    ] = None,
    no_pdf: Annotated[
        bool, typer.Option("--no-pdf", "--nopdf", help="Stop after the LaTeX; use on a host that cannot render")
    ] = False,
    template: Annotated[
        Optional[Path],
        typer.Option("--template", dir_okay=False, help="Pandoc LaTeX template, e.g. a venue's; default: pandoc's article"),
    ] = None,
) -> None:
    """Strip the ledger markers, convert with pandoc to LaTeX, and render the PDF with tectonic."""
    load_env()  # MANUSCRIPT_TECTONIC, TECTONIC_CACHE_DIR from this checkout's .env; exported values win
    paths = build_paths(path, out)
    resource_dir = path.parent
    try:
        write_clean_twin(path, paths.clean)
    except LedgerError as exc:
        for issue in exc.issues:
            typer.echo(f"{path}:{issue.line}: {issue.severity} {issue.code}: {issue.message}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"wrote {paths.clean}")
    try:
        markdown_to_latex(paths.clean, paths.tex, resource_dir, template)
    except (FileNotFoundError, RuntimeError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"wrote {paths.tex}")
    if no_pdf:
        note = stale_pdf_note(paths)
        if note is not None:
            typer.echo(f"note: {note}", err=True)
        return
    try:
        result = latex_to_pdf(paths, resource_dir)
    except (FileNotFoundError, RuntimeError) as exc:
        typer.echo(f"Error: PDF not built ({TECTONIC_ENV_VAR} overrides the tectonic binary): {exc}", err=True)
        raise typer.Exit(1) from exc
    pages = f"{result.pages} pages" if result.pages is not None else "page count unknown"
    typer.echo(f"wrote {result.pdf} ({pages})")
    for character, count in result.missing_characters.items():
        typer.echo(f"warning: {character} is missing from the font and left blank ({count}x); see {paths.log}", err=True)


if __name__ == "__main__":
    app()
