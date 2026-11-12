"""The meta-table (format 0.8) in the report: combinations that replace their members, per-row facts.

The fixture is just-dna-compiler's ``reference_examples/pleiotropy_tradeoff`` spec (vendored at
``5fbf2653`` under ``fixtures/meta/``), compiled at test time with the installed compiler. Each test
adds its own ``meta.csv`` rows to a temporary copy, so the parquets are the compiler's real output and
the expected sets are read back from them, never typed in.

The "sample" is a set of rows taken from the compiled ``weights.parquet`` for the genotypes it
carries: the engine passes every lead-table column through, so these are the columns the report sees.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module

from just_dna_pipelines.annotation.report_logic import (
    _join_meta_resolved,
    apply_meta_combinations,
    report_environment,
)
from phenotype_fixtures import probe_local

FIXTURE = Path(__file__).parent / "fixtures" / "meta" / "pleiotropy_tradeoff"
COMBINATION = (
    "variants[variant_key=rs3184504, genotype=C/T] & variants[variant_key=rs10455872, genotype=A/G]"
)
COMBINED_CONCLUSION = "You carry one SH2B3 T allele and one Lp(a)-raising LPA allele together."


def _compile(tmp_path: Path, extra_meta: list[dict[str, str]]) -> Path:
    spec = tmp_path / "spec" / "pleiotropy_tradeoff"
    shutil.copytree(FIXTURE, spec)
    with (spec / "meta.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    rows.extend({field: extra.get(field, "") for field in fields} for extra in extra_meta)
    with (spec / "meta.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    out = tmp_path / "pleiotropy_tradeoff"
    result = compile_module(spec, out, resolve_with_ensembl=True, ensembl_cache=None)
    assert result.success, result.errors
    return out


def _sample(artifact: Path, genotypes: dict[str, str]) -> pl.DataFrame:
    """The weights rows a sample with these authored genotypes would match."""
    weights = pl.read_parquet(artifact / "weights.parquet")
    keep = pl.lit(False)
    for rsid, genotype in genotypes.items():
        keep = keep | (
            (pl.col("variant_key") == rsid) & (pl.col("genotype").list.sort().list.join("/") == genotype)
        )
    sample = weights.filter(keep)
    assert sample.height == len(genotypes), "each genotype names one authored row"
    return sample


def _keys(frame: pl.DataFrame) -> set[tuple[str, str]]:
    return {
        (row["variant_key"], "/".join(sorted(row["genotype"])))
        for row in frame.select("variant_key", "genotype").iter_rows(named=True)
    }


@pytest.fixture
def with_combination(tmp_path: Path) -> Path:
    return _compile(
        tmp_path,
        [{"members": COMBINATION, "direction": "risk", "conclusion": COMBINED_CONCLUSION, "pmid": "20560212"}],
    )


def test_a_combination_every_member_of_which_matches_replaces_those_rows(with_combination: Path) -> None:
    info = probe_local(with_combination)
    assert info.meta_url is not None and info.meta_resolved_url is not None
    sample = _sample(with_combination, {"rs3184504": "C/T", "rs10455872": "A/G", "rs5882": "A/A"})

    kept, findings = apply_meta_combinations(sample, "pleiotropy_tradeoff", info)

    assert [finding["conclusion"] for finding in findings] == [COMBINED_CONCLUSION]
    meta = pl.read_parquet(with_combination / "meta.parquet").filter(pl.col("replaces"))
    replaced = {(match["key"][0], match["key"][1]) for match in meta.row(0, named=True)["matches"]}
    assert _keys(kept) == _keys(sample) - replaced
    assert set(findings[0]["replaces"]) == {f"{vk} {gt}" for vk, gt in replaced}
    assert kept.height + len(replaced) == sample.height


def test_a_combination_with_one_member_missing_changes_nothing(with_combination: Path) -> None:
    info = probe_local(with_combination)
    sample = _sample(with_combination, {"rs3184504": "C/T", "rs10455872": "A/A"})

    kept, findings = apply_meta_combinations(sample, "pleiotropy_tradeoff", info)

    assert findings == []
    assert _keys(kept) == _keys(sample)


def test_a_member_that_matches_no_module_row_is_never_counted_as_met(tmp_path: Path) -> None:
    """`matches` lists only what matched; the member count comes from the authored cell."""
    artifact = _compile(
        tmp_path,
        [{
            "members": "variants[variant_key=rs3184504, genotype=C/T] & variants[variant_key=rs999999999]",
            "direction": "risk",
            "conclusion": COMBINED_CONCLUSION,
        }],
    )
    info = probe_local(artifact)
    sample = _sample(artifact, {"rs3184504": "C/T", "rs10455872": "A/G"})

    kept, findings = apply_meta_combinations(sample, "pleiotropy_tradeoff", info)

    assert findings == []
    assert _keys(kept) == _keys(sample)


def test_a_combination_scoped_to_a_sex_is_not_applied_to_an_unplaced_sample(tmp_path: Path) -> None:
    artifact = _compile(
        tmp_path,
        [{"members": COMBINATION, "direction": "risk", "conclusion": COMBINED_CONCLUSION, "sex": "female"}],
    )
    info = probe_local(artifact)
    sample = _sample(artifact, {"rs3184504": "C/T", "rs10455872": "A/G"})

    kept, findings = apply_meta_combinations(sample, "pleiotropy_tradeoff", info)

    assert findings == []
    assert _keys(kept) == _keys(sample)


def test_a_module_without_meta_is_left_alone(tmp_path: Path) -> None:
    spec = tmp_path / "spec" / "plain"
    shutil.copytree(FIXTURE, spec)
    (spec / "meta.csv").unlink()
    out = tmp_path / "plain"
    assert compile_module(spec, out, resolve_with_ensembl=True, ensembl_cache=None).success
    info = probe_local(out)
    assert info.meta_url is None and info.meta_resolved_url is None
    sample = _sample(out, {"rs3184504": "C/T", "rs10455872": "A/G"})

    kept, findings = apply_meta_combinations(sample, "plain", info)

    assert findings == [] and kept.equals(sample)


def test_meta_resolved_reaches_each_row_it_keys(with_combination: Path) -> None:
    """`tradeoff` is true or null (never false), and only the unscoped `variants` targets join."""
    weights = pl.scan_parquet(with_combination / "weights.parquet")
    resolved = pl.read_parquet(with_combination / "meta_resolved.parquet")

    joined = _join_meta_resolved(
        weights, pl.scan_parquet(with_combination / "meta_resolved.parquet"), "pleiotropy_tradeoff"
    ).collect()

    assert joined.height == weights.collect().height
    expected_tradeoff = {
        (row["key"][0], row["key"][1])
        for row in resolved.filter(
            (pl.col("table") == "variants") & pl.col("sex").is_null() & pl.col("drug").is_null()
            & pl.col("tradeoff").fill_null(False)
        ).iter_rows(named=True)
    }
    assert expected_tradeoff, "the fixture computes a trade-off for SH2B3"
    assert _keys(joined.filter(pl.col("meta_tradeoff").fill_null(False))) == expected_tradeoff
    assert joined["meta_tradeoff"].drop_nulls().all()


def test_the_template_renders_a_combined_result(with_combination: Path) -> None:
    info = probe_local(with_combination)
    sample = _sample(with_combination, {"rs3184504": "C/T", "rs10455872": "A/G"})
    _, findings = apply_meta_combinations(sample, "pleiotropy_tradeoff", info)

    rendered = report_environment().from_string(
        '{% import "longevity_report.html.j2" as report %}{{ report.meta_findings_block(findings) }}'
    ).render(findings=findings)

    assert COMBINED_CONCLUSION in rendered
    assert "Combined result" in rendered
    assert "https://pubmed.ncbi.nlm.nih.gov/20560212/" in rendered
    for replaced in findings[0]["replaces"]:
        assert replaced in rendered
