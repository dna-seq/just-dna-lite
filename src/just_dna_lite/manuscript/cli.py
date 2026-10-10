"""`manuscript`: one CLI for the manuscript sources in `docs/manuscript/` (see its README.md)."""

from __future__ import annotations

import typer

from just_dna_lite.manuscript.ledger import ledger_app

app = typer.Typer(
    name="manuscript",
    help="Manuscript tools: the revision ledger kept in the Markdown source.",
    no_args_is_help=True,
)
app.add_typer(ledger_app, name="ledger")


if __name__ == "__main__":
    app()
