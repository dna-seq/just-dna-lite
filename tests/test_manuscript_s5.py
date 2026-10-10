"""`manuscript s5`: Supplementary Table S5 measured and classified offline, on real scoring files.

The fixture directory holds real PGS Catalog harmonized GRCh38 files from the release of 2026-09-17,
whole where they are small (PGS000001, PGS000024, PGS000152, PGS000343, PGS002246, PGS004255) and as
the header plus the first rows where they are not (PGS005228, `excerpt` below), with the Catalog's own
metadata for those scores in `s5_catalog.json`. Ground truth is recomputed here with the standard
library's csv reader, independently of the Polars reader under test.
"""

from __future__ import annotations

import csv
import gzip
import re
from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner

from just_dna_lite.manuscript.cli import app
from just_dna_lite.manuscript.s5 import (
    APPROXIMATED,
    AS_SPECIFIED,
    CANNOT_SCORE,
    CATALOG_JSON,
    CATEGORIES,
    CSV_NAME,
    FIGURE_STEM,
    MD_NAME,
    MEASURES_JSONL,
    RULES,
    CatalogRelease,
    FileMeasure,
    classify,
    classify_release,
    measure_file,
    read_catalog,
    sensitivity,
)

FIXTURES = Path(__file__).resolve().parent / "data" / "manuscript" / "s5"
HLA_ONLY = "PGS000343"
EFFECT_IS_OTHER = "PGS005228"  # excerpt: header plus the first rows
ORDINARY = "PGS000001"
INTERACTION = "PGS000024"
MULTIPLICATIVE = "PGS000152"
BOTH_WEIGHTS = "PGS002246"
GENOBOOST = "PGS004255"
NUCLEOTIDES = re.compile(r"^[ACGT]+$")


@pytest.fixture(scope="module")
def release() -> CatalogRelease:
    return read_catalog(FIXTURES / CATALOG_JSON)


@pytest.fixture(scope="module")
def measures(release: CatalogRelease) -> dict[str, FileMeasure]:
    return {s.pgs_id: measure_file(FIXTURES / f"{s.pgs_id}_hmPOS_GRCh38.txt.gz", s.pgs_id) for s in release.scores}


def plain_rows(pgs_id: str) -> list[dict[str, str]]:
    """The data rows of a fixture file, read with the csv module."""
    with gzip.open(FIXTURES / f"{pgs_id}_hmPOS_GRCh38.txt.gz", "rt", encoding="utf-8") as handle:
        lines = [line for line in handle if not line.startswith("#")]
    return list(csv.DictReader(lines, delimiter="\t", quoting=csv.QUOTE_NONE))


def test_every_row_falls_in_exactly_one_class(release: CatalogRelease, measures: dict[str, FileMeasure]) -> None:
    for score in release.scores:
        m = measures[score.pgs_id]
        rows = plain_rows(score.pgs_id)
        assert m.rows == len(rows), score.pgs_id
        assert m.rows == m.rows_unplaced + m.rows_non_nucleotide + m.rows_effect_is_other + m.rows_scored, score.pgs_id
        parts = m.weight_unplaced + m.weight_non_nucleotide + m.weight_effect_is_other + m.weight_scored
        assert parts == pytest.approx(m.weight_total, rel=1e-12, abs=1e-12), score.pgs_id
        placed = [r for r in rows if r.get("hm_pos", "") not in ("", "NA", "None") and r.get("hm_chr", "") not in ("", "NA", "None")]
        assert m.rows_unplaced == len(rows) - len(placed), score.pgs_id
        nucleotide = [r for r in placed if NUCLEOTIDES.match(r["effect_allele"])]
        assert m.rows_non_nucleotide == len(placed) - len(nucleotide), score.pgs_id
        same = [r for r in nucleotide if r["effect_allele"] == r.get("other_allele")]
        assert m.rows_effect_is_other == len(same), score.pgs_id


def test_weight_is_the_absolute_effect_weight_or_the_largest_dosage_weight(measures: dict[str, FileMeasure]) -> None:
    rows = plain_rows(ORDINARY)
    assert measures[ORDINARY].weight_total == pytest.approx(sum(abs(float(r["effect_weight"])) for r in rows))
    assert measures[ORDINARY].weight_source == "effect_weight"
    rows = plain_rows(GENOBOOST)
    expected = sum(max(abs(float(r[f"dosage_{k}_weight"])) for k in range(3)) for r in rows)
    assert measures[GENOBOOST].weight_total == pytest.approx(expected)
    assert measures[GENOBOOST].weight_source.startswith("dosage")
    # a file with both kinds is weighed by effect_weight, the column just-prs scores
    rows = plain_rows(BOTH_WEIGHTS)
    assert measures[BOTH_WEIGHTS].weight_total == pytest.approx(sum(abs(float(r["effect_weight"])) for r in rows))


def test_the_fixture_files_land_in_their_categories(release: CatalogRelease, measures: dict[str, FileMeasure]) -> None:
    files = {f.score.pgs_id: f for f in classify_release(release, measures)}
    assert files[HLA_ONLY].category == CANNOT_SCORE
    assert files[HLA_ONLY].share_unplaceable == 1.0
    assert all(not NUCLEOTIDES.match(e) for e in measures[HLA_ONLY].unplaceable_examples)
    assert files[EFFECT_IS_OTHER].category == CANNOT_SCORE
    assert files[EFFECT_IS_OTHER].share_effect_is_other == 1.0
    assert files[ORDINARY].category == AS_SPECIFIED
    assert files[ORDINARY].reasons == ()
    assert files[GENOBOOST].category == AS_SPECIFIED
    assert files[INTERACTION].category == APPROXIMATED and "interaction" in files[INTERACTION].reasons
    assert files[MULTIPLICATIVE].category == APPROXIMATED and "multiplicative" in files[MULTIPLICATIVE].reasons
    assert files[BOTH_WEIGHTS].category == APPROXIMATED and "dosage_weights_ignored" in files[BOTH_WEIGHTS].reasons
    known = {rule.key for rule in RULES}
    assert all(set(f.reasons) <= known for f in files.values())


def test_shares_are_fractions_that_sum_to_one(release: CatalogRelease, measures: dict[str, FileMeasure]) -> None:
    for f in classify_release(release, measures):
        shares = (f.share_unplaced, f.share_non_nucleotide, f.share_effect_is_other, f.share_scored_flagged, f.share_scored_plain)
        assert all(0.0 <= s <= 1.0 for s in shares), f.score.pgs_id
        assert sum(shares) == pytest.approx(1.0), f.score.pgs_id
        assert f.share_unplaceable == pytest.approx(f.share_unplaced + f.share_non_nucleotide)


@pytest.mark.parametrize(("share", "category"), [(0.10, APPROXIMATED), (0.0999, AS_SPECIFIED), (0.0, AS_SPECIFIED)])
def test_the_threshold_is_inclusive(release: CatalogRelease, measures: dict[str, FileMeasure], share: float, category: str) -> None:
    base = measures[ORDINARY]
    moved = base.model_copy(update={"weight_unplaced": share * base.weight_total, "weight_scored": (1 - share) * base.weight_total})
    score = next(s for s in release.scores if s.pgs_id == ORDINARY)
    assert classify(score, moved, 0.10).category == category


def test_unmeasured_or_foreign_files_are_refused(release: CatalogRelease, measures: dict[str, FileMeasure]) -> None:
    partial = {k: v for k, v in measures.items() if k != ORDINARY}
    with pytest.raises(ValueError, match="missing"):
        classify_release(release, partial)
    foreign = {**measures, "PGS999999": measures[ORDINARY].model_copy(update={"pgs_id": "PGS999999"})}
    with pytest.raises(ValueError, match="not in the release"):
        classify_release(release, foreign)


def test_sensitivity_counts_are_consistent(release: CatalogRelease, measures: dict[str, FileMeasure]) -> None:
    table = sensitivity(release, measures)
    assert [s.label for s in table] == ["any (> 0)", "1%", "10%", "25%", "50%"]
    for s in table:
        assert s.approximated + s.as_specified + s.cannot == len(release.scores)
        assert s.over_threshold <= s.approximated
    assert len({s.cannot for s in table}) == 1
    approximated = [s.approximated for s in table]
    assert approximated == sorted(approximated, reverse=True)


def test_render_writes_one_row_per_score(release: CatalogRelease, measures: dict[str, FileMeasure], tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    (work / CATALOG_JSON).write_text(release.model_dump_json(), encoding="utf-8")
    (work / MEASURES_JSONL).write_text("".join(m.model_dump_json() + "\n" for m in measures.values()), encoding="utf-8")
    out = tmp_path / "out"
    result = CliRunner().invoke(app, ["s5", "render", str(work), "--out", str(out)])
    assert result.exit_code == 0, result.output
    table = pl.read_csv(out / CSV_NAME)
    assert sorted(table["pgs_id"].to_list()) == sorted(s.pgs_id for s in release.scores)
    assert table["pgs_id"].n_unique() == table.height
    assert set(table["category"].unique().to_list()) <= set(CATEGORIES)
    counts = table.group_by("category").len()
    assert counts["len"].sum() == len(release.scores)
    for column in [c for c in table.columns if c.startswith("share_")]:
        assert table[column].is_between(0.0, 1.0).all(), column
    assert (table["rows"] == table["rows_unplaced"] + table["rows_non_nucleotide"] + table["rows_effect_is_other"] + table["rows_scored"]).all()
    assert set(table["catalog_release"].unique().to_list()) == {release.release_date}
    markdown = (out / MD_NAME).read_text(encoding="utf-8")
    assert f"PGS Catalog release of {release.release_date}" in markdown
    for category, n in counts.iter_rows():
        assert f"| {category.capitalize()} | {n:,} |" in markdown
    svg = (out / f"{FIGURE_STEM}.svg").read_text(encoding="utf-8")
    assert svg.lstrip().startswith("<?xml") and "</svg>" in svg
    assert (out / f"{FIGURE_STEM}.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
