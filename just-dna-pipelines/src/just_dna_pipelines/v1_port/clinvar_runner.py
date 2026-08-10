"""
Orchestration for the ClinVar modules: gene list → draft → fill → resolve → compile.

The three steps after drafting are deliberately separate library calls rather than one
``compile_module(resolve_with_ensembl=True)``: 0.5 makes resolution the enricher's job and the
compiler inject-only, so this runner produces ``resolution.csv`` from the **same ClinVar snapshot**
the variants were drafted from and then compiles offline. Ensembl is not involved at all — ClinVar
carries the coordinates — which is why these modules build while an Ensembl cache is still syncing.
"""

import csv
import io
import shutil
from pathlib import Path
from typing import Optional

from just_dna_compiler.compiler import compile_module, validate_spec
from just_dna_enricher.enrich import enrich
from just_dna_enricher.locations import resolve_clinvar_reference
from pydantic import BaseModel, Field
from rich.console import Console

from just_dna_pipelines.v1_port.clinvar_panel import (
    MIN_REVIEW_STARS,
    PanelBuild,
    build_clinvar_module,
    panel_genes,
)
from just_dna_pipelines.v1_port.sources import REGISTRY, fetch_data_file, fetch_logo
from just_dna_pipelines.v1_port.symbols import load_symbol_resolver, resolve_panel_genes

DEFAULT_OUT_ROOT = Path("data/interim/v1_port")
DEFAULT_DOWNLOAD_CACHE = Path("data/interim/v1_port/_sources")

#: Ensembl is deliberately unreachable for these builds. ClinVar supplies every coordinate, and
#: pointing the resolver at a cache would let a coordinate arrive from a second source — which would
#: make the compiled bytes depend on which cache happened to be present.
_NO_ENSEMBL = Path("/nonexistent")

#: Authored rows per `enrich` call. **Not a tuning knob — a workaround for quadratic scaling.**
#:
#: `clinvar.lookup_clin_sig` and `_lookup_rsid_candidates` build one OR'd four-column predicate per
#: allele, which DuckDB evaluates per row per predicate rather than as a hash join. Measured on this
#: snapshot: 5,000 alleles as an OR-list takes **127 s**; the identical 5,000 as a temp table joined
#: against `clinvar` takes **0.13 s**. That thousandfold gap is why `cardio` unbatched had not
#: finished after two hours. Since the cost grows with the square of the alleles per call, capping
#: the call size makes the whole panel linear again. Reported upstream — see
#: `just-dna-format/docs/ROADMAP.md`; the fix there is the join, and then this cap can go.
ENRICH_BATCH_ROWS = 10_000

#: Panels skip the ClinVar `clin_sig` cross-check, and only panels may.
#:
#: The check re-reads every resolved allele's clinical significance and compares it to the authored
#: one — the dominant cost in a panel resolve (27.1 s → 2.6 s on a 7,818-row panel with it off, for
#: byte-identical output). For a *hand-authored* module that is money well spent: a human typed the
#: `clin_sig` and may have typed it wrong. For a panel it is tautological — `draft_gene_panel` copied
#: the value out of this same snapshot, so it cannot disagree with itself, and 0 conflicts is the
#: only answer the check can return. Paying ninety percent of the runtime to be told that is not
#: rigour, it is a round trip. Anything authored by hand keeps `verify_clinsig` on.
PANEL_VERIFY_CLIN_SIG = False


class ClinVarModuleResult(BaseModel):
    """Outcome of building one ClinVar module end to end."""

    build: PanelBuild
    valid: bool = False
    resolved_rows: int = 0
    unresolved_rows: int = 0
    compiled: bool = False
    digest: Optional[str] = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def module_gene_list(name: str, download_cache: Path) -> tuple[list[str], dict[str, str], list[str]]:
    """The panel's gene symbols, reconciled to the current NCBI symbols ClinVar publishes.

    ``pathogenic`` has no authored gene list — Gen-I's ``just_pathogenic`` shipped no data at all —
    so its list is derived from the snapshot selection itself (see :func:`panel_genes`).
    """
    if name == "pathogenic":
        reference = resolve_clinvar_reference()
        if reference is None:
            raise FileNotFoundError(
                "no ClinVar snapshot found; provision it with "
                "`just-dna-enricher cache pull --only clinvar`."
            )
        return panel_genes(reference), {}, []

    module = REGISTRY[name]
    gene_file = fetch_data_file(module, download_cache)
    raw = {line.strip() for line in gene_file.read_text().splitlines() if line.strip()}
    wanted, alias_map, unresolved = resolve_panel_genes(raw, load_symbol_resolver())
    return sorted(wanted), alias_map, unresolved


def build_clinvar_modules(
    names: list[str],
    *,
    out_root: Path = DEFAULT_OUT_ROOT,
    download_cache: Path = DEFAULT_DOWNLOAD_CACHE,
    snapshot: Optional[Path] = None,
    min_review_stars: Optional[int] = None,
    do_enrich: bool = True,
    do_compile: bool = True,
    console: Optional[Console] = None,
) -> list[ClinVarModuleResult]:
    """Build each named ClinVar module into ``out_root/<name>/``."""
    stars = MIN_REVIEW_STARS if min_review_stars is None else min_review_stars
    reference = Path(snapshot) if snapshot is not None else resolve_clinvar_reference()
    results: list[ClinVarModuleResult] = []
    for name in names:
        if console:
            console.print(f"[cyan]{name}[/cyan]: resolving gene list…")
        genes, alias_map, unresolved = module_gene_list(name, download_cache)

        if console:
            console.print(f"[cyan]{name}[/cyan]: drafting from ClinVar ({len(genes):,} gene(s))…")
        build = build_clinvar_module(
            name,
            genes,
            out_root / name,
            reference=reference,
            min_review_stars=stars,
            alias_remaps=alias_map,
            unresolved_symbols=unresolved,
        )
        # The Gen-I repo's logo, carried into the module the way the variant-backed ports do.
        if name in REGISTRY:
            fetch_logo(REGISTRY[name], build.output_dir)
        results.append(_finish(build, reference, do_enrich=do_enrich, do_compile=do_compile,
                               console=console))
    return results


def _rows_of(source: "Path | io.StringIO") -> list[list[str]]:
    """A CSV's parsed rows, so two spellings of the same table compare equal."""
    if isinstance(source, Path):
        with source.open(newline="", encoding="utf-8") as handle:
            return list(csv.reader(handle))
    return list(csv.reader(source))


def enrich_in_batches(
    spec_dir: Path,
    reference: Optional[Path],
    *,
    batch_rows: int = ENRICH_BATCH_ROWS,
    resume: bool = True,
    console: Optional[Console] = None,
) -> tuple[int, int]:
    """Resolve a large panel by enriching slices of ``variants.csv`` and concatenating the results.

    Returns ``(resolved_rows, unresolved_rows)``. Each slice is a spec directory holding the module's
    own yaml, its share of the authored rows, and a header-only ``studies.csv`` — the resolver reads
    the variant table and nothing else, so that is a complete input for it. The slices'
    ``resolution.csv`` files are concatenated into the real spec directory, deduplicated on the whole
    row, and the compile then consumes that one table as usual.

    Batching is safe because every decision the resolver makes is **per locus**: the allele-aware
    genotype fit, the one-to-many rsID expansion, the pseudoautosomal representative. Slicing on row
    boundaries can only separate loci from each other, never a locus from its own alleles — and the
    authored order that decides the compiled bytes is preserved, because slices are written and read
    back in order.

    ``resume`` (the default) reuses any batch that already carries a ``resolution.csv`` whose slice
    of ``variants.csv`` is byte-identical to the one this run would write. `pathogenic` is 62 batches
    and about an hour; losing all of it to a crash on batch 11 — which is exactly what happened once
    — is not a cost worth paying twice. The identity check is what makes it safe: a re-run after an
    edit to the authored table rewrites the slice, so the stale result is discarded rather than
    silently reused.
    """
    variants_csv = spec_dir / "variants.csv"
    with variants_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if len(rows) <= batch_rows:
        result = enrich(
            spec_dir, offline=True, ensembl_cache=_NO_ENSEMBL, clinvar_cache=reference,
            use_clinvar=True, use_gnomad=False, download=False,
            verify_clinsig=PANEL_VERIFY_CLIN_SIG,
        )
        return len(result.rows), len(result.unresolved)

    work_dir = spec_dir / "_enrich_batches"
    if not resume:
        shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    header: Optional[str] = None
    body: list[str] = []
    resolved = unresolved = 0
    reused = 0
    batches = range(0, len(rows), batch_rows)
    for index, start in enumerate(batches, start=1):
        batch_dir = work_dir / f"batch{index:03d}"
        batch_dir.mkdir(exist_ok=True)
        shutil.copyfile(spec_dir / "module_spec.yaml", batch_dir / "module_spec.yaml")

        slice_csv = io.StringIO()
        writer = csv.DictWriter(slice_csv, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows[start:start + batch_rows])
        wanted = slice_csv.getvalue()

        batch_variants, produced = batch_dir / "variants.csv", batch_dir / "resolution.csv"
        # Compared as parsed rows, not bytes: a slice written by an earlier version of this function
        # may differ only in line terminator, and re-resolving an hour of work over `\r\n` would be
        # a silly way to lose it.
        already_done = (
            produced.exists()
            and batch_variants.exists()
            and _rows_of(batch_variants) == _rows_of(io.StringIO(wanted))
        )
        if already_done:
            reused += 1
        else:
            batch_variants.write_text(wanted, encoding="utf-8")
            (batch_dir / "studies.csv").write_text("rsid,chrom,start,ref,pmid\n", encoding="utf-8")
            produced.unlink(missing_ok=True)
            if console:
                console.print(
                    f"  resolving batch {index}/{len(batches)} "
                    f"({min(batch_rows, len(rows) - start):,} rows)…"
                )
            result = enrich(
                batch_dir, offline=True, ensembl_cache=_NO_ENSEMBL, clinvar_cache=reference,
                use_clinvar=True, use_gnomad=False, download=False,
                verify_clinsig=PANEL_VERIFY_CLIN_SIG,
            )
            unresolved += len(result.unresolved)

        if produced.exists():
            lines = produced.read_text(encoding="utf-8").splitlines()
            if lines:
                header = header or lines[0]
                body.extend(lines[1:])
                resolved += len(lines) - 1

    if console and reused:
        console.print(f"  reused {reused}/{len(batches)} batch(es) resolved by an earlier run")
    if header is not None:
        seen: set[str] = set()
        unique = [line for line in body if not (line in seen or seen.add(line))]
        (spec_dir / "resolution.csv").write_text(
            "\n".join([header, *unique]) + "\n", encoding="utf-8"
        )
    # Only now: the slices are the resume point, so they outlive every batch but not the run.
    shutil.rmtree(work_dir, ignore_errors=True)
    return resolved, unresolved


def _finish(
    build: PanelBuild,
    reference: Optional[Path],
    *,
    do_enrich: bool,
    do_compile: bool,
    console: Optional[Console],
) -> ClinVarModuleResult:
    result = ClinVarModuleResult(build=build, warnings=list(build.warnings))
    if build.unfilled_placeholders:
        result.errors.append(
            f"{build.unfilled_placeholders} row(s) still carry a genotype placeholder"
        )

    validation = validate_spec(build.output_dir)
    result.valid = validation.valid
    result.errors.extend(validation.errors[:20])
    result.warnings.extend(validation.warnings[:20])
    if not validation.valid:
        return result

    if do_enrich:
        if console:
            console.print(f"[cyan]{build.name}[/cyan]: resolving from the ClinVar snapshot…")
        resolved, unresolved = enrich_in_batches(
            build.output_dir, reference, console=console
        )
        result.resolved_rows = resolved
        result.unresolved_rows = unresolved
        if unresolved:
            result.warnings.append(
                f"{unresolved} variant(s) unresolved against the ClinVar snapshot"
            )

    if do_compile:
        if console:
            console.print(f"[cyan]{build.name}[/cyan]: compiling…")
        # Master switch for resolution, not a choice of reference: with `ensembl_cache=None` and a
        # `resolution.csv` present it takes the injected-table path (no reference, no network).
        compiled = compile_module(
            build.output_dir,
            build.output_dir,
            resolve_with_ensembl=True,
            ensembl_cache=None,
            log_files=[build.output_dir / "clinvar_panel.log"],
        )
        result.compiled = compiled.success
        if compiled.manifest is not None:
            result.digest = compiled.manifest.artifact.digest
        result.errors.extend(compiled.errors[:20])
        result.warnings.extend(compiled.warnings[:20])
    return result
