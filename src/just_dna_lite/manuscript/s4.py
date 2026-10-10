"""`manuscript s4 render`: Supplementary Table S4 ("Module sources") from the modules' own files.

Everything in the table is read from a compiled module directory, never typed: `manifest.json`
(identity, curator, method, authorship, publication time, digest), `sources.parquet` (the compiled
licence sidecar: which databases each layer came from, with their release), `studies.parquet` and the
lead table (the PMIDs each row cites), `literature.parquet` (PubMed's DOI for each PMID) and the build
log the port wrote beside it (`v1_port.log`, `clinvar_panel.log`, `pharmgkb.log`).

The registry is a live catalogue, so a table about it is only true at a moment. `snapshot.json`
(written by `manuscript s4 snapshot`) records that moment and the registry's own answers; without one
the render says it describes local builds. First author and year are not in any module file: they
come from PubMed, cached in a bibliography JSON beside the output, and are fetched only on request.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import polars as pl
import yaml
from just_dna_enricher.eutils import EutilsClient, EutilsSettings, is_missing
from just_dna_enricher.literature import bibliographic
from just_dna_format.manifest import ModuleManifest, read_manifest
from just_dna_format.spec import Defaults
from just_dna_pipelines.module_config import find_lead_table
from pydantic import BaseModel, ConfigDict

MANIFEST = "manifest.json"
STUDIES = "studies.parquet"
LITERATURE = "literature.parquet"
SOURCES = "sources.parquet"
# The build logs the v1-port routes write beside a module. Their top-level `key: value` lines are the
# port's own provenance record (source repository and file hash, or snapshot release and filters).
BUILD_LOGS = ("v1_port.log", "clinvar_panel.log", "pharmgkb.log")
MD_NAME = "S4_module_sources.md"
MODULES_CSV = "S4_module_sources.csv"
CITATIONS_CSV = "S4_module_citations.csv"
BIBLIOGRAPHY_JSON = "S4_bibliography.json"
# Hand-written, cited curation notes: the one part of S4 no module file records (how a Generation I
# literature module chose its variants). Kept beside the output and rendered as each module's Curation line.
CURATION_YAML = "S4_curation.yaml"
DATABASE_LAYER = "annotation"
_LOG_SCALAR_RE = re.compile(r"^(?P<key>[a-z][a-z0-9_]*): (?P<value>\S.*)$")
_PMID_RE = re.compile(r"^[0-9]+$")


class SourceRow(BaseModel):
    """One row of the compiled licence sidecar: a database, the layer it fed, and its release."""

    model_config = ConfigDict(frozen=True)

    source: str
    name: str
    layer: str
    license: Optional[str]
    dataset: Optional[str]


class Citation(BaseModel):
    model_config = ConfigDict(frozen=True)

    pmid: str
    doi: Optional[str]
    rows: int


class ModuleSources(BaseModel):
    """What one compiled module says about where its rows came from."""

    model_config = ConfigDict(frozen=True)

    name: str
    title: str
    description: Optional[str]
    version: str
    published_at: Optional[str]
    artifact_digest: str
    content_signature: Optional[str]
    curator: str
    method: str
    authorship_kinds: list[str]
    curator_type: str
    curator_type_basis: str
    lead_table: str
    lead_rows: int
    variant_count: Optional[int]
    gene_count: Optional[int]
    study_rows: int
    sources: list[SourceRow]
    build_record: dict[str, str]
    citations: list[Citation]

    @property
    def database_derived(self) -> bool:
        return any(row.layer == DATABASE_LAYER for row in self.sources)


class Bibliography(BaseModel):
    model_config = ConfigDict(frozen=True)

    first_author: Optional[str]
    year: Optional[str]
    title: Optional[str]
    journal: Optional[str]


class SnapshotModule(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    latest_version: str
    published_at: Optional[str]
    artifact_digest: str
    content_signature: Optional[str]
    versions: list[str]
    yanked_versions: list[str]
    mirror_version: Optional[str] = None
    mirror_digest: Optional[str] = None


class Snapshot(BaseModel):
    """The registry's answers at one moment, as `manuscript s4 snapshot` recorded them."""

    model_config = ConfigDict(frozen=True)

    as_of: datetime
    registry_key: str
    registry_url: str
    registry_version: Optional[str]
    format_version: Optional[str]
    namespace: str
    mirror_repo: Optional[str]
    modules: list[SnapshotModule]


def _attribution_name(attribution: Optional[str], source: str) -> str:
    """`"ClinVar, NCBI (https://…)"` → `"ClinVar"`: the sidecar's own display name, else its key."""
    if not attribution:
        return source
    return attribution.split(" (")[0].split(",")[0].strip() or source


def read_sources(module_dir: Path) -> list[SourceRow]:
    path = module_dir / SOURCES
    if not path.is_file():
        return []
    frame = pl.read_parquet(path)
    return [
        SourceRow(
            source=row["source"],
            name=_attribution_name(row.get("attribution"), row["source"]),
            layer=row["layer"],
            license=row.get("license"),
            dataset=row.get("dataset"),
        )
        for row in frame.iter_rows(named=True)
    ]


def read_build_record(module_dir: Path) -> dict[str, str]:
    """Top-level scalar `key: value` lines of the module's build log, minus local filesystem paths."""
    record: dict[str, str] = {}
    for log_name in BUILD_LOGS:
        path = module_dir / log_name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            match = _LOG_SCALAR_RE.match(line)
            if match is None:
                continue
            value = match["value"].strip()
            if Path(value).is_absolute():  # the builder's cache directory says nothing about the source
                continue
            record.setdefault(match["key"], value)
    return record


def _pmid_frame(path: Path) -> pl.DataFrame:
    """`pmid` → number of rows citing it, for one table; empty when the table has no PMID column."""
    lf = pl.scan_parquet(path)
    if "pmid" not in lf.collect_schema().names():
        return pl.DataFrame(schema={"pmid": pl.String, "rows": pl.UInt32})
    return (
        lf.select(pl.col("pmid").cast(pl.String).str.strip_chars())
        .filter(pl.col("pmid").is_not_null() & (pl.col("pmid") != ""))
        .group_by("pmid")
        .agg(pl.len().alias("rows"))
        .collect()
    )


def read_citations(module_dir: Path, lead_table: str) -> list[Citation]:
    """Every PMID the module's study rows (and its lead table, where it carries one) cite."""
    frames = [_pmid_frame(module_dir / name) for name in (STUDIES, f"{lead_table}.parquet") if (module_dir / name).is_file()]
    counts = pl.concat(frames).group_by("pmid").agg(pl.col("rows").sum()) if frames else pl.DataFrame()
    if counts.is_empty():
        return []
    doi_by_pmid: dict[str, str] = {}
    literature = module_dir / LITERATURE
    if literature.is_file():
        lit = pl.read_parquet(literature).select(pl.col("pmid").cast(pl.String), "doi").drop_nulls()
        doi_by_pmid = dict(lit.iter_rows())
    rows = sorted(counts.iter_rows(), key=lambda r: (not _PMID_RE.match(r[0]), int(r[0]) if _PMID_RE.match(r[0]) else 0, r[0]))
    return [Citation(pmid=pmid, doi=doi_by_pmid.get(pmid), rows=int(n)) for pmid, n in rows]


def classify_curator(manifest: ModuleManifest, sources: list[SourceRow]) -> tuple[str, str]:
    """A curator *type* and the evidence for it, from the module's own provenance; never guessed.

    A database feeding the annotation layer outranks the manifest's `curator`/`method`, because those
    two fall back to the format's defaults when a spec states none, and a default is not a statement.
    """
    defaults = Defaults()
    stated = f"manifest curator `{manifest.curator}`, method `{manifest.method}`"
    databases = sorted({row.name for row in sources if row.layer == DATABASE_LAYER})
    is_default = manifest.curator == defaults.curator and manifest.method == defaults.method
    if databases:
        note = " (the format's defaults, not a statement)" if is_default else ""
        return f"Database-derived ({', '.join(databases)})", f"licence sidecar: {', '.join(databases)} feeds the annotation layer; {stated}{note}"
    if manifest.method == "expert-curated":
        return "Expert", stated
    kinds = {kind for entry in manifest.authorship for kind in entry.kind}
    if not is_default and kinds == {"ai"}:
        return "AI-generated", f"{stated}; authorship kinds {sorted(kinds)}"
    return "Undetermined", f"{stated}; authorship kinds {sorted(kinds) or 'none'}"


def read_module_sources(module_dir: Path) -> ModuleSources:
    """Read one compiled module directory (local build or registry download) into a `ModuleSources`."""
    manifest = read_manifest(module_dir / MANIFEST)
    lead_table = find_lead_table(module_dir)
    if lead_table is None:
        raise ValueError(f"{module_dir} holds no lead table, so it is not a compiled module")
    sources = read_sources(module_dir)
    curator_type, basis = classify_curator(manifest, sources)
    studies = module_dir / STUDIES
    study_rows = pl.scan_parquet(studies).select(pl.len()).collect().item() if studies.is_file() else 0
    lead_rows = pl.scan_parquet(module_dir / f"{lead_table}.parquet").select(pl.len()).collect().item()
    stats = manifest.stats
    return ModuleSources(
        name=manifest.identity.name,
        title=manifest.display.title if manifest.display and manifest.display.title else manifest.identity.name,
        description=manifest.display.description if manifest.display else None,
        version=manifest.identity.version,
        published_at=manifest.published_at,
        artifact_digest=manifest.artifact.digest,
        content_signature=manifest.content_signature,
        curator=manifest.curator,
        method=manifest.method,
        authorship_kinds=sorted({kind for entry in manifest.authorship for kind in entry.kind}),
        curator_type=curator_type,
        curator_type_basis=basis,
        lead_table=lead_table,
        lead_rows=lead_rows,
        variant_count=stats.variant_count if stats else None,
        gene_count=stats.gene_count if stats else None,
        study_rows=study_rows,
        sources=sources,
        build_record=read_build_record(module_dir),
        citations=read_citations(module_dir, lead_table),
    )


def module_dirs(root: Path) -> list[Path]:
    """Every immediate subdirectory of `root` that holds a manifest and a lead table, by name."""
    return sorted(p for p in root.iterdir() if p.is_dir() and (p / MANIFEST).is_file() and find_lead_table(p) is not None)


def read_snapshot(path: Path) -> Snapshot:
    return Snapshot.model_validate_json(path.read_text(encoding="utf-8"))


def load_bibliography(path: Path) -> dict[str, Bibliography]:
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {pmid: Bibliography.model_validate(entry) for pmid, entry in raw.items()}


def fetch_bibliography(pmids: list[str], known: dict[str, Bibliography]) -> dict[str, Bibliography]:
    """Fill first author / year / title for `pmids` not yet in `known`, from PubMed esummary.

    The request identifies only the tool: `email` and `api_key` are set empty on purpose, so neither a
    contact address nor a personal NCBI key from the environment is sent.
    """
    wanted = [pmid for pmid in pmids if pmid not in known and _PMID_RE.match(pmid)]
    merged = dict(known)
    if not wanted:
        return merged
    with EutilsClient(settings=EutilsSettings(email="", api_key="")) as client:
        records = client.esummary("pubmed", wanted)
    for pmid, record in records.items():
        if is_missing(record):
            merged[pmid] = Bibliography(first_author=None, year=None, title=None, journal=None)
            continue
        merged[pmid] = Bibliography.model_validate(bibliographic(record))
    return merged


def write_bibliography(path: Path, bibliography: dict[str, Bibliography]) -> None:
    ordered = {pmid: bibliography[pmid].model_dump() for pmid in sorted(bibliography, key=lambda p: (len(p), p))}
    path.write_text(json.dumps(ordered, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def _fmt_time(value: Optional[str]) -> str:
    if not value:
        return "time not stated"
    return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")


def _databases(module: ModuleSources) -> str:
    parts = []
    for row in module.sources:
        release = f", release `{row.dataset}`" if row.dataset else ""
        parts.append(f"{row.name} ({row.layer} layer, {row.license or 'licence not stated'}{release})")
    return "; ".join(parts) or "none recorded"


def _built_from(module: ModuleSources) -> str:
    record = module.build_record
    if "source_repo" in record:
        return f"Generation-I module `{record['source_repo']}`, file `{record.get('source_file', '?')}` ({record.get('source_sha256', 'hash not recorded')})"
    if "route" in record:
        release = next((record[k] for k in record if k.endswith("_release")), None)
        sha = next((record[k] for k in record if k.endswith("_source_sha256")), None)
        detail = ", ".join(x for x in (f"release `{release}`" if release else "", sha or "") if x)
        return f"{record['route']}" + (f" ({detail})" if detail else "")
    return "no build log in the artifact"


def _build_filters(module: ModuleSources) -> list[str]:
    """The selection rules a database route recorded (review floor, significance, evidence level)."""
    keys = ("clin_sig", "min_review_stars", "max_citations", "min_evidence_level", "supersedes",
            "genes_requested", "genes_matched", "clinvar_records", "clinical_annotations", "drugs", "genes")
    return [f"{key} = {module.build_record[key]}" for key in keys if key in module.build_record]


def _cite_cell(citation: Citation, bib: dict[str, Bibliography]) -> tuple[str, str]:
    entry = bib.get(citation.pmid)
    author = entry.first_author if entry and entry.first_author else ""
    year = entry.year if entry and entry.year else ""
    return author, year


class CurationNote(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    selection: str
    references: tuple[str, ...] = ()


class Curation(BaseModel):
    """`S4_curation.yaml`: per-module selection notes, each citing keys of `references`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    modules: dict[str, CurationNote]
    references: dict[str, str]


def read_curation(path: Path, module_names: set[str]) -> Curation:
    curation = Curation.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    unknown_modules = sorted(set(curation.modules) - module_names)
    if unknown_modules:
        raise ValueError(f"{path.name}: no such module in this render: {', '.join(unknown_modules)}")
    cited = {key for note in curation.modules.values() for key in note.references}
    missing = sorted(cited - set(curation.references))
    if missing:
        raise ValueError(f"{path.name}: cited but not defined under references: {', '.join(missing)}")
    return curation


def render_markdown(
    modules: list[ModuleSources],
    snapshot: Optional[Snapshot],
    as_of: Optional[datetime],
    bib: dict[str, Bibliography],
    curation: Optional[Curation] = None,
) -> str:
    by_name = {m.name: m for m in snapshot.modules} if snapshot else {}
    lines = ["# Supplementary Table S4. Module sources", ""]
    if snapshot:
        lines += [
            f"Registry state at {snapshot.as_of.strftime('%Y-%m-%d %H:%M UTC')}, {snapshot.registry_url}, namespace "
            f"`{snapshot.namespace}` (registry {snapshot.registry_version or 'version not reported'}, module format "
            f"{snapshot.format_version or 'not reported'}). The registry is a live catalogue: modules published or "
            "versioned after this time are not described here, and later versions of these modules may differ. Each "
            "published version is immutable, so the version and artifact digest below identify exactly the artifact "
            "this table was read from.",
            "",
        ]
    else:
        stamp = as_of.strftime("%Y-%m-%d %H:%M UTC") if as_of else "an unrecorded time"
        lines += [f"Local module builds as of {stamp}; not a registry snapshot.", ""]
    lines += [
        "Every value is read from the module's own published files: `manifest.json` (identity, curator, method, "
        "publication time, digest), `sources.parquet` (the source databases, with their release where the build "
        "recorded one), `studies.parquet` and the lead table (the PubMed IDs each row cites), `literature.parquet` "
        "(the DOI PubMed gives for each PMID) and the build log shipped with the module. First author and year come "
        "from PubMed (esummary) and are given for the literature-curated modules. For the database-derived modules "
        "the curated source is the database release; the papers that database links to are counted here and "
        f"listed in `{CITATIONS_CSV}`.",
        "",
        "Curator types: **Expert**, the manifest states method `expert-curated` (literature modules curated by hand "
        "in Generation I and ported to the current format); **Database-derived**, the licence sidecar names a "
        "database feeding the annotation layer, and the rows were drafted mechanically from that release. "
        "Ensembl and ClinVar entries on the *resolution* layer only place an rsID on GRCh38; they are not evidence.",
        "",
    ]
    if snapshot and any(m.mirror_version is not None and (m.mirror_version != m.latest_version or m.mirror_digest != m.artifact_digest) for m in snapshot.modules):
        lines += [
            f"The legacy HuggingFace mirror (`{snapshot.mirror_repo}`) differs from the registry for: "
            + "; ".join(
                f"`{m.name}` (mirror {m.mirror_version}, {m.mirror_digest})"
                for m in snapshot.modules
                if m.mirror_version is not None and (m.mirror_version != m.latest_version or m.mirror_digest != m.artifact_digest)
            )
            + ". The registry is the reference.",
            "",
        ]
    lines += [
        "## Summary",
        "",
        "| Module | Version | Published | Curator type | Source database (release) | Lead rows | Study rows | Cited papers |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for m in modules:
        dbs = "; ".join(f"{r.name} `{r.dataset}`" for r in m.sources if r.layer == DATABASE_LAYER) or "none (literature curation)"
        lines.append(
            f"| {m.title} (`{m.name}`) | {m.version} | {_fmt_time(m.published_at)[:10]} | {m.curator_type} | {dbs} | "
            f"{m.lead_rows:,} | {m.study_rows:,} | {len(m.citations):,} |"
        )
    lines.append("")
    for m in modules:
        snap = by_name.get(m.name)
        with_doi = sum(1 for c in m.citations if c.doi)
        lines += [f"## {m.title} (`{m.name}`)", ""]
        if m.description:
            lines += [m.description if m.description.endswith(".") else f"{m.description}.", ""]
        lines += [
            f"- **Version** {m.version}, published {_fmt_time(m.published_at)}; artifact `{m.artifact_digest}`.",
            f"- **Curator type** {m.curator_type} ({m.curator_type_basis}).",
            f"- **Built from** {_built_from(m)}.",
            f"- **Databases by layer** {_databases(m)}.",
        ]
        note = curation.modules.get(m.name) if curation else None
        if note is not None:
            cites = "; ".join(note.references)
            lines.append(f"- **Curation** {note.selection.rstrip('.')}" + (f" ({cites})." if cites else "."))
        filters = _build_filters(m)
        if filters:
            lines.append(f"- **Selection recorded by the build** {'; '.join(filters)}.")
        lines.append(
            f"- **Counts** {m.lead_rows:,} `{m.lead_table}` rows"
            + (f", {m.variant_count:,} variants" if m.variant_count else "")
            + (f", {m.gene_count:,} genes" if m.gene_count else "")
            + f"; {m.study_rows:,} study rows citing {len(m.citations):,} distinct PubMed IDs ({with_doi:,} with a DOI)."
        )
        if snap and snap.yanked_versions:
            lines.append(f"- **Yanked versions** {', '.join(snap.yanked_versions)}.")
        lines.append("")
        if not m.citations:
            lines += ["No row of this artifact cites a PubMed ID; its evidence is the database release above.", ""]
            continue
        if m.database_derived:
            lines += [
                f"The {len(m.citations):,} PubMed IDs are the source database's own literature links, transcribed as "
                f"the release gives them and not checked here; see `{CITATIONS_CSV}`.",
                "",
            ]
            continue
        lines += ["| First author | Year | PMID | DOI | Rows citing |", "|---|---|---|---|---|"]
        ordered = sorted(m.citations, key=lambda c: (_cite_cell(c, bib)[1] or "9999", _cite_cell(c, bib)[0], c.pmid))
        for c in ordered:
            author, year = _cite_cell(c, bib)
            lines.append(f"| {author} | {year} | {c.pmid} | {c.doi or ''} | {c.rows} |")
        lines.append("")
    if curation:
        used = sorted({key for name, note in curation.modules.items() for key in note.references})
        if used:
            lines += ["## References", "", *(f"- **{key}** {curation.references[key]}" for key in used), ""]
    return "\n".join(lines)


def _common_columns(snapshot: Optional[Snapshot], as_of: Optional[datetime]) -> dict[str, str]:
    stamp = snapshot.as_of if snapshot else as_of
    return {
        "as_of_utc": stamp.isoformat() if stamp else "",
        "registry_url": snapshot.registry_url if snapshot else "",
        "namespace": snapshot.namespace if snapshot else "",
    }


def write_modules_csv(path: Path, modules: list[ModuleSources], snapshot: Optional[Snapshot], as_of: Optional[datetime]) -> None:
    common = _common_columns(snapshot, as_of)
    fields = [*common, "module", "title", "version", "published_at", "artifact_digest", "content_signature", "curator",
              "method", "authorship_kinds", "curator_type", "curator_type_basis", "built_from", "source_databases",
              "lead_table", "lead_rows", "variant_count", "gene_count", "study_rows", "cited_papers", "cited_papers_with_doi"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for m in modules:
            writer.writerow({
                **common, "module": m.name, "title": m.title, "version": m.version, "published_at": m.published_at or "",
                "artifact_digest": m.artifact_digest, "content_signature": m.content_signature or "", "curator": m.curator,
                "method": m.method, "authorship_kinds": ";".join(m.authorship_kinds), "curator_type": m.curator_type,
                "curator_type_basis": m.curator_type_basis, "built_from": _built_from(m), "source_databases": _databases(m),
                "lead_table": m.lead_table, "lead_rows": m.lead_rows, "variant_count": m.variant_count or "",
                "gene_count": m.gene_count or "", "study_rows": m.study_rows, "cited_papers": len(m.citations),
                "cited_papers_with_doi": sum(1 for c in m.citations if c.doi),
            })


def write_citations_csv(path: Path, modules: list[ModuleSources], bib: dict[str, Bibliography]) -> None:
    fields = ["module", "version", "pmid", "doi", "first_author", "year", "title", "journal", "rows_citing"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for m in modules:
            for c in m.citations:
                entry = bib.get(c.pmid) if not m.database_derived else None
                writer.writerow({
                    "module": m.name, "version": m.version, "pmid": c.pmid, "doi": c.doi or "",
                    "first_author": entry.first_author or "" if entry else "", "year": entry.year or "" if entry else "",
                    "title": entry.title or "" if entry else "", "journal": entry.journal or "" if entry else "",
                    "rows_citing": c.rows,
                })


def check_against_snapshot(modules: list[ModuleSources], snapshot: Snapshot) -> list[str]:
    """Disagreements between the module directories read and the registry answers recorded."""
    problems = []
    read = {m.name: m for m in modules}
    for snap in snapshot.modules:
        module = read.get(snap.name)
        if module is None:
            problems.append(f"{snap.name}: in the snapshot but no module directory was read")
        elif module.version != snap.latest_version or module.artifact_digest != snap.artifact_digest:
            problems.append(
                f"{snap.name}: directory holds {module.version} {module.artifact_digest}, "
                f"registry latest is {snap.latest_version} {snap.artifact_digest}"
            )
    problems += [f"{name}: read but not in the snapshot" for name in read.keys() - {s.name for s in snapshot.modules}]
    return problems
