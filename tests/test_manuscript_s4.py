"""`manuscript s4`: Supplementary Table S4 read from real module builds, offline.

Runs on the local v1-port builds in `data/interim/v1_port/` (gitignored; skipped with a reason when
absent). Ground truth is recomputed from each module's own parquets here, independently of the reader.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner

from just_dna_format.manifest import Contribution, read_manifest
from just_dna_format.spec import Defaults
from just_dna_lite.manuscript.cli import app
from just_dna_lite.manuscript.s4 import (
    CITATIONS_CSV,
    CURATION_YAML,
    MD_NAME,
    MODULES_CSV,
    ModuleSources,
    Snapshot,
    SnapshotModule,
    check_against_snapshot,
    classify_curator,
    module_dirs,
    read_curation,
    read_module_sources,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[1]
V1_PORT = ROOT / "data/interim/v1_port"
AS_OF = "2026-10-10T12:00:00"

pytestmark = pytest.mark.skipif(
    not V1_PORT.is_dir() or not any((p / "manifest.json").is_file() for p in V1_PORT.iterdir()),
    reason="no local module builds in data/interim/v1_port (run `uv run pipelines v1-port port --all`)",
)


@pytest.fixture(scope="module")
def modules() -> list[ModuleSources]:
    return [read_module_sources(path) for path in module_dirs(V1_PORT)]


def cited_pmids(module_dir: Path, lead_table: str) -> pl.DataFrame:
    """Non-empty PMID cells across `studies.parquet` and the lead table, one row per citing row."""
    frames = []
    for name in ("studies.parquet", f"{lead_table}.parquet"):
        path = module_dir / name
        if path.is_file() and "pmid" in pl.read_parquet_schema(path):
            frames.append(pl.read_parquet(path, columns=["pmid"]).with_columns(pl.col("pmid").cast(pl.String).str.strip_chars()))
    if not frames:
        return pl.DataFrame(schema={"pmid": pl.String})
    return pl.concat(frames).filter(pl.col("pmid").is_not_null() & (pl.col("pmid") != ""))


def test_every_manifest_directory_is_read(modules: list[ModuleSources]) -> None:
    on_disk = {p.name for p in V1_PORT.iterdir() if p.is_dir() and (p / "manifest.json").is_file()}
    assert {m.name for m in modules} == on_disk
    assert len(modules) == len(on_disk)


def test_citations_are_exactly_the_cited_pmids(modules: list[ModuleSources]) -> None:
    for module in modules:
        truth = cited_pmids(V1_PORT / module.name, module.lead_table)
        pmids = [c.pmid for c in module.citations]
        assert len(pmids) == len(set(pmids)), f"{module.name}: duplicate PMID in output"
        assert set(pmids) == set(truth["pmid"].to_list()), module.name
        assert sum(c.rows for c in module.citations) == truth.height, module.name


def test_citation_count_matches_the_manifest_literature_block(modules: list[ModuleSources]) -> None:
    checked = 0
    for module in modules:
        literature = read_manifest(V1_PORT / module.name / "manifest.json").literature
        if literature is None or literature.row_count is None:
            continue
        assert len(module.citations) == literature.row_count, module.name
        checked += 1
    if checked == 0:
        pytest.skip("no local module carries a literature block")


def test_dois_come_from_the_literature_table(modules: list[ModuleSources]) -> None:
    for module in modules:
        path = V1_PORT / module.name / "literature.parquet"
        lit = dict(pl.read_parquet(path).select(pl.col("pmid").cast(pl.String), "doi").iter_rows()) if path.is_file() else {}
        for citation in module.citations:
            assert citation.doi == lit.get(citation.pmid), (module.name, citation.pmid)


def test_build_record_never_carries_a_local_path(modules: list[ModuleSources]) -> None:
    for module in modules:
        assert not any(Path(value).is_absolute() for value in module.build_record.values()), module.name


def test_curator_type_reads_provenance_and_refuses_defaults(modules: list[ModuleSources]) -> None:
    expert = next((m for m in modules if m.curator_type == "Expert"), None)
    if expert is None:
        pytest.skip("no expert-curated local module")
    manifest = read_manifest(V1_PORT / expert.name / "manifest.json")
    defaults = Defaults()
    unstated = manifest.model_copy(update={"curator": defaults.curator, "method": defaults.method, "authorship": []})
    assert classify_curator(unstated, [])[0] == "Undetermined"
    ai_only = manifest.model_copy(
        update={"method": "ai-draft", "authorship": [Contribution(who="some-model", role="created", kind=["ai"])]}
    )
    assert classify_curator(ai_only, [])[0] == "AI-generated"
    for module in modules:
        if module.database_derived:
            assert module.curator_type.startswith("Database-derived ("), module.name


def test_snapshot_disagreement_is_reported(modules: list[ModuleSources]) -> None:
    first = modules[0]
    snapshot = Snapshot(
        as_of=datetime(2026, 10, 10, tzinfo=timezone.utc), registry_key="prod", registry_url="https://example.invalid",
        registry_version=None, format_version=None, namespace="ns", mirror_repo=None,
        modules=[SnapshotModule(name=first.name, latest_version=first.version, published_at=None,
                                artifact_digest="sha256:" + "0" * 64, content_signature=None, versions=[first.version],
                                yanked_versions=[])],
    )
    problems = check_against_snapshot(modules, snapshot)
    assert any(p.startswith(f"{first.name}: directory holds") for p in problems)
    assert len(problems) == len(modules)  # the one mismatch, plus every other module not in the snapshot


def test_render_writes_consistent_tables(modules: list[ModuleSources], tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["s4", "render", str(V1_PORT), "--out", str(tmp_path), "--as-of", AS_OF])
    assert result.exit_code == 0, result.output
    with (tmp_path / MODULES_CSV).open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [r["module"] for r in rows] == [m.name for m in modules]
    assert {r["as_of_utc"] for r in rows} == {"2026-10-10T12:00:00+00:00"}
    with (tmp_path / CITATIONS_CSV).open(encoding="utf-8") as handle:
        citations = list(csv.DictReader(handle))
    pairs = [(c["module"], c["pmid"]) for c in citations]
    assert len(pairs) == len(set(pairs))
    by_module = {m.name: m for m in modules}
    for row in rows:
        module = by_module[row["module"]]
        assert int(row["cited_papers"]) == sum(1 for c in citations if c["module"] == module.name)
    truth = {m.name: set(cited_pmids(V1_PORT / m.name, m.lead_table)["pmid"].to_list()) for m in modules}
    assert all(c["pmid"] in truth[c["module"]] for c in citations)
    markdown = (tmp_path / MD_NAME).read_text(encoding="utf-8")
    assert "Local module builds as of 2026-10-10 12:00 UTC" in markdown
    for module in modules:
        assert f"## {module.title} (`{module.name}`)" in markdown


def test_render_refuses_as_of_beside_a_snapshot(tmp_path: Path) -> None:
    (tmp_path / "snapshot.json").write_text(
        Snapshot(as_of=datetime(2026, 10, 10, tzinfo=timezone.utc), registry_key="prod", registry_url="https://example.invalid",
                 registry_version=None, format_version=None, namespace="ns", mirror_repo=None, modules=[]).model_dump_json(),
        encoding="utf-8",
    )
    result = CliRunner().invoke(app, ["s4", "render", str(tmp_path), "--out", str(tmp_path / "out"), "--as-of", AS_OF])
    assert result.exit_code == 1
    assert "records its own cutoff" in result.output


COMMITTED_CURATION = ROOT / "docs/manuscript/v0.3/supplementary" / CURATION_YAML


def test_the_committed_curation_renders_one_line_per_noted_module(modules: list[ModuleSources]) -> None:
    names = {m.name for m in modules}
    curation = read_curation(COMMITTED_CURATION, names)
    page = render_markdown(modules, None, datetime(2026, 10, 10, tzinfo=timezone.utc), {}, curation)
    assert page.count("- **Curation** ") == len(curation.modules)
    references = page.split("## References", 1)[1]
    cited = {key for note in curation.modules.values() for key in note.references}
    listed = {line.split("**")[1] for line in references.splitlines() if line.startswith("- **")}
    assert listed == cited
    assert "## References" not in render_markdown(modules, None, None, {}, None)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("modules:\n  no_such_module: {selection: x}\nreferences: {}\n", "no such module"),
        ("modules:\n  coronary: {selection: x, references: [Missing2026]}\nreferences: {}\n", "not defined"),
    ],
)
def test_curation_refuses_unknown_modules_and_undefined_references(
    tmp_path: Path, modules: list[ModuleSources], body: str, message: str
) -> None:
    path = tmp_path / CURATION_YAML
    path.write_text(body, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        read_curation(path, {m.name for m in modules})
