"""`manuscript`: one CLI for the manuscript sources in `docs/manuscript/` (see its README.md)."""

from __future__ import annotations

from datetime import datetime, timezone
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
from just_dna_lite.manuscript.s4 import (
    BIBLIOGRAPHY_JSON,
    CITATIONS_CSV,
    MD_NAME,
    MODULES_CSV,
    check_against_snapshot,
    fetch_bibliography,
    load_bibliography,
    module_dirs,
    read_module_sources,
    read_snapshot,
    render_markdown,
    write_bibliography,
    write_citations_csv,
    write_modules_csv,
)
from just_dna_lite.manuscript.s4_snapshot import take_snapshot
from just_dna_pipelines.module_config import default_registry_store, get_registry_store
from just_dna_pipelines.runtime import load_env

app = typer.Typer(
    name="manuscript",
    help="Manuscript tools: the revision ledger in the Markdown source, and the PDF build.",
    no_args_is_help=True,
)
app.add_typer(ledger_app, name="ledger")
s4_app = typer.Typer(
    help="Supplementary Table S4 (module sources): snapshot the registry, then render from the module files.",
    no_args_is_help=True,
)
app.add_typer(s4_app, name="s4")
SNAPSHOT_JSON = "snapshot.json"


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


@s4_app.command("snapshot")
def s4_snapshot(
    work_dir: Annotated[Path, typer.Argument(file_okay=False, help="Where the module downloads and snapshot.json go")],
    namespace: Annotated[str, typer.Option("--namespace", help="Registry namespace to describe")] = "just-dna-seq",
    store_key: Annotated[
        Optional[str], typer.Option("--store", help="Registry store key from modules.yaml (default: the default store)")
    ] = None,
    no_mirror: Annotated[bool, typer.Option("--no-mirror", help="Skip the HuggingFace mirror comparison")] = False,
) -> None:
    """Read-only: list NAMESPACE, download each latest non-yanked version, record the query time (UTC)."""
    store = get_registry_store(store_key) if store_key else default_registry_store()
    if store is None:
        typer.echo(f"Error: no registry store {store_key!r} in modules.yaml", err=True)
        raise typer.Exit(1)
    work_dir.mkdir(parents=True, exist_ok=True)
    snapshot = take_snapshot(store, namespace, work_dir, mirror=not no_mirror)
    (work_dir / SNAPSHOT_JSON).write_text(snapshot.model_dump_json(indent=1) + "\n", encoding="utf-8")
    typer.echo(f"registry {snapshot.registry_url} namespace {namespace} as of {snapshot.as_of.isoformat()}")
    for module in snapshot.modules:
        typer.echo(f"  {module.name} {module.latest_version} {module.artifact_digest}")
    typer.echo(f"wrote {work_dir / SNAPSHOT_JSON}")


@s4_app.command("render")
def s4_render(
    modules_root: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, help="Directory of compiled module directories")
    ],
    out: Annotated[Path, typer.Option("--out", "-o", file_okay=False, help="Output directory")],
    as_of: Annotated[
        Optional[datetime],
        typer.Option("--as-of", help="Cutoff for a render of local builds; a snapshot.json in MODULES_ROOT sets it otherwise"),
    ] = None,
    fetch: Annotated[
        bool, typer.Option("--fetch-bibliography", help="Ask PubMed for first author and year of uncached PMIDs")
    ] = False,
) -> None:
    """Write S4 (Markdown + two CSVs) from MODULES_ROOT, reading every value from the module files."""
    snapshot_path = modules_root / SNAPSHOT_JSON
    snapshot = read_snapshot(snapshot_path) if snapshot_path.is_file() else None
    if snapshot is not None and as_of is not None:
        typer.echo(f"Error: {snapshot_path} records its own cutoff; --as-of applies to local builds only", err=True)
        raise typer.Exit(1)
    modules = [read_module_sources(path) for path in module_dirs(modules_root)]
    if snapshot is not None:
        problems = check_against_snapshot(modules, snapshot)
        for problem in problems:
            typer.echo(f"Error: {problem}", err=True)
        if problems:
            raise typer.Exit(1)
    out.mkdir(parents=True, exist_ok=True)
    bib_path = out / BIBLIOGRAPHY_JSON
    bibliography = load_bibliography(bib_path)
    if fetch:
        wanted = [c.pmid for m in modules if not m.database_derived for c in m.citations]
        bibliography = fetch_bibliography(wanted, bibliography)
        write_bibliography(bib_path, bibliography)
        typer.echo(f"wrote {bib_path} ({len(bibliography)} PMIDs)")
    stamp = as_of.replace(tzinfo=timezone.utc) if as_of is not None and as_of.tzinfo is None else as_of
    (out / MD_NAME).write_text(render_markdown(modules, snapshot, stamp, bibliography), encoding="utf-8")
    write_modules_csv(out / MODULES_CSV, modules, snapshot, stamp)
    write_citations_csv(out / CITATIONS_CSV, modules, bibliography)
    for name in (MD_NAME, MODULES_CSV, CITATIONS_CSV):
        typer.echo(f"wrote {out / name}")


if __name__ == "__main__":
    app()
