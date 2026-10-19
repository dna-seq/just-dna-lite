"""`manuscript`: one CLI for the manuscript sources in `docs/manuscript/` (see its README.md)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

import typer

from just_dna_lite.manuscript import s5
from just_dna_lite.manuscript.build import (
    TECTONIC_ENV_VAR,
    build_paths,
    latex_to_pdf,
    markdown_to_docx,
    markdown_to_latex,
    stale_pdf_note,
    write_clean_twin,
)
from just_dna_lite.manuscript.ledger import LedgerError, ledger_app
from just_dna_lite.manuscript.s4 import (
    BIBLIOGRAPHY_JSON,
    CITATIONS_CSV,
    CURATION_YAML,
    MD_NAME,
    MODULES_CSV,
    check_against_snapshot,
    fetch_bibliography,
    load_bibliography,
    module_dirs,
    read_curation,
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
s5_app = typer.Typer(
    help="Supplementary Table S5 (PGS Catalog coverage of just-prs): scan every scoring file, then render.",
    no_args_is_help=True,
)
app.add_typer(s5_app, name="s5")
SNAPSHOT_JSON = "snapshot.json"


@app.command()
def build(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True, help="Markdown master")],
    out: Annotated[
        Optional[Path], typer.Option("--out", "-o", file_okay=False, help="Output directory (default: build/ beside PATH)")
    ] = None,
    no_pdf: Annotated[
        bool, typer.Option("--no-pdf", "--nopdf", help="Stop after the LaTeX and .docx; use on a host that cannot render")
    ] = False,
    template: Annotated[
        Optional[Path],
        typer.Option("--template", dir_okay=False, help="Pandoc LaTeX template, e.g. a venue's; default: pandoc's article"),
    ] = None,
) -> None:
    """Strip the ledger markers, convert with pandoc to LaTeX and .docx, and render the PDF with tectonic."""
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
    try:
        markdown_to_docx(paths.clean, paths.docx, resource_dir)
    except RuntimeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(f"wrote {paths.docx}")
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
    curation_path = out / CURATION_YAML
    curation = read_curation(curation_path, {m.name for m in modules}) if curation_path.is_file() else None
    (out / MD_NAME).write_text(render_markdown(modules, snapshot, stamp, bibliography, curation), encoding="utf-8")
    write_modules_csv(out / MODULES_CSV, modules, snapshot, stamp)
    write_citations_csv(out / CITATIONS_CSV, modules, bibliography)
    for name in (MD_NAME, MODULES_CSV, CITATIONS_CSV):
        typer.echo(f"wrote {out / name}")


@s5_app.command("scan")
def s5_scan(
    work_dir: Annotated[Path, typer.Argument(file_okay=False, help="Where s5_catalog.json and the per-file measures go")],
    cache_dir: Annotated[
        Path, typer.Option("--cache-dir", file_okay=False, help="Where the harmonized scoring files are downloaded (tens of GB)")
    ],
    build: Annotated[str, typer.Option("--build", help="Harmonized build to read")] = s5.DEFAULT_BUILD,
    downloads: Annotated[int, typer.Option("--downloads", min=1, help="Parallel downloads")] = 12,
    workers: Annotated[int, typer.Option("--workers", min=1, help="Parallel file readers (about 2 GB each at peak)")] = 6,
) -> None:
    """Read-only: record the Catalog release (UTC fetch time), download every scoring file, measure all its rows.

    Resumes: files already measured in WORK_DIR are skipped, and files already in the cache are not
    downloaded again. A resumed scan refuses if the Catalog has released since the first one.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = work_dir / s5.CATALOG_JSON
    if catalog_path.is_file():
        release = s5.read_catalog(catalog_path)
        current = s5.fetch_release_info()
        if current["date"] != release.release_date or release.build != build:
            typer.echo(
                f"Error: {catalog_path} is release {release.release_date} ({release.build}); the Catalog is now at "
                f"{current['date']}. Scan into a new work directory.",
                err=True,
            )
            raise typer.Exit(1)
    else:
        release = s5.fetch_catalog(build)
        s5.write_catalog(catalog_path, release)
    typer.echo(f"PGS Catalog release {release.release_date}, {len(release.scores)} scores, listed {release.fetched_at.isoformat()}")
    failed = s5.scan(release, work_dir, cache_dir, downloads, workers, typer.echo)
    if failed:
        typer.echo(f"Error: {len(failed)} files not measured, run scan again: {', '.join(failed)}", err=True)
        raise typer.Exit(1)
    typer.echo("every score measured")


@s5_app.command("render")
def s5_render(
    work_dir: Annotated[Path, typer.Argument(exists=True, file_okay=False, help="A work directory `s5 scan` completed")],
    out: Annotated[Path, typer.Option("--out", "-o", file_okay=False, help="Output directory")],
    threshold: Annotated[
        float, typer.Option("--threshold", min=0.0, max=1.0, help="Share of absolute weight that makes a file approximated")
    ] = s5.DEFAULT_THRESHOLD,
) -> None:
    """Write S5 (Markdown, per-file CSV, histogram as SVG and PNG) from a scan, offline."""
    release = s5.read_catalog(work_dir / s5.CATALOG_JSON)
    try:
        files = s5.classify_release(release, s5.read_measures(work_dir / s5.MEASURES_JSONL), threshold)
    except ValueError as exc:
        typer.echo(f"Error: {exc}; finish `manuscript s5 scan` first", err=True)
        raise typer.Exit(1) from exc
    measures = {f.measure.pgs_id: f.measure for f in files}
    out.mkdir(parents=True, exist_ok=True)
    (out / s5.MD_NAME).write_text(s5.render_markdown(release, files, s5.sensitivity(release, measures), threshold), encoding="utf-8")
    s5.write_csv(out / s5.CSV_NAME, s5.coverage_frame(release, files))
    figures = s5.write_histogram(out / s5.FIGURE_STEM, files, threshold)
    for path in (out / s5.MD_NAME, out / s5.CSV_NAME, *figures):
        typer.echo(f"wrote {path}")
    counts = {category: sum(1 for f in files if f.category == category) for category in s5.CATEGORIES}
    typer.echo(", ".join(f"{category}: {n:,}" for category, n in counts.items()))


if __name__ == "__main__":
    app()
