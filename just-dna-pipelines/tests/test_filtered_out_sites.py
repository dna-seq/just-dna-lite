"""A call the quality filter rejected is never restored as the reference genotype (GitHub issue 39).

`user_vcf_normalized` drops records that fail the quality filter. Restoration reads the normalized
parquet, so a site the caller emitted as `0/1` and the filter rejected used to look like a site the
caller never emitted, and on a whole-genome callset with a call nearby it was restored as hom-ref:
the opposite of what the caller said. Normalization now keeps the dropped positions beside the parquet
(`FILTERED_OUT_SITES_NAME`) and restoration treats them as emitted.

The normalization here is a real `normalize_vcf_job` run on a VCF written at test time, under the
repository's own `quality_filters`, so which record is rejected is the filter's verdict.
"""

from __future__ import annotations

import logging
from pathlib import Path

import polars as pl
import pytest
from dagster import DagsterInstance

from just_dna_pipelines.runtime import load_env

load_env()

from just_dna_pipelines.annotation import hf_logic, hf_modules, restoration
from just_dna_pipelines.annotation.configs import HfModuleAnnotationConfig
from just_dna_pipelines.annotation.definitions import defs
from just_dna_pipelines.annotation.hf_modules import ModuleInfo
from just_dna_pipelines.annotation.restoration import (
    EVIDENCE_COLUMN,
    EVIDENCE_RESTORED,
    FILTERED_OUT_SITES_NAME,
    CallsetScope,
    build_restoration_context,
    restorable_sites,
    restored_rows,
)

USER = "issue39"
SAMPLE = "rejected_call"
PARTITION = f"{USER}/{SAMPLE}"
MODULE = "issue39_mod"

PASSING = [1000, 2000]
REJECTED = 1500  # FILTER=LowQual: emitted by the caller as 0/1, dropped by `pass_filters`
ABSENT = 1700  # no record at all, 200 bp from a passing call: restorable

VCF_TEXT = "\n".join([
    "##fileformat=VCFv4.2",
    '##FILTER=<ID=PASS,Description="All filters passed">',
    '##FILTER=<ID=LowQual,Description="Low quality">',
    "##contig=<ID=chr1,length=248956422>",
    '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
    '##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Read depth">',
    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE",
    f"chr1\t{PASSING[0]}\t.\tG\tA\t50\tPASS\t.\tGT:DP\t0/1:30",
    f"chr1\t{REJECTED}\t.\tC\tT\t50\tLowQual\t.\tGT:DP\t0/1:30",
    f"chr1\t{PASSING[1]}\t.\tA\tG\t50\tPASS\t.\tGT:DP\t1/1:30",
    "",
])


@pytest.fixture
def normalized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("JUST_DNA_PIPELINES_OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("JUST_DNA_PIPELINES_INPUT_DIR", str(tmp_path / "input"))
    vcf = tmp_path / "input" / USER / f"{SAMPLE}.vcf"
    vcf.parent.mkdir(parents=True, exist_ok=True)
    vcf.write_text(VCF_TEXT, encoding="utf-8")
    instance = DagsterInstance.ephemeral()
    job = defs.resolve_job_def("normalize_vcf_job")
    instance.add_dynamic_partitions(job.partitions_def.name, [PARTITION])
    result = job.execute_in_process(
        run_config={"ops": {"user_vcf_normalized": {
            "config": {"vcf_path": str(vcf), "user_name": USER, "sample_name": SAMPLE}
        }}},
        instance=instance,
        partition_key=PARTITION,
    )
    assert result.success
    return tmp_path / "output" / PARTITION / "user_vcf_normalized.parquet"


def test_normalization_keeps_what_the_filter_dropped_beside_the_parquet(normalized: Path) -> None:
    kept = set(pl.read_parquet(normalized).select("start").to_series().to_list())
    dropped = pl.read_parquet(normalized.with_name(FILTERED_OUT_SITES_NAME))
    assert kept == set(PASSING)
    assert dropped.columns == ["chrom", "start"]
    assert dropped["start"].to_list() == [REJECTED]
    # Kept and dropped partition the VCF's records: nothing is lost and nothing is in both.
    assert kept | set(dropped["start"].to_list()) == {*PASSING, REJECTED}
    assert not kept & set(dropped["start"].to_list())


def _annotate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, normalized: Path) -> pl.DataFrame:
    """Run the engine on the normalized parquet with a module authoring hom-ref at both sites.

    The toy callset is three calls, which scope detection rightly calls targeted; the verdict is
    forced to whole-genome so the per-site rule is what this test reaches (as `test_restoration`'s
    `_wgs_context` does), and the hard-region mask is left out (no network).
    """
    lead = tmp_path / "weights.parquet"
    pl.DataFrame({
        "module": [MODULE, MODULE], "rsid": ["rs_rejected", "rs_absent"], "chrom": ["1", "1"],
        "start": [REJECTED, ABSENT], "ref": ["C", "A"], "alts": [["T"], ["G"]],
        "genotype": [["C", "C"], ["A", "A"]], "weight": [0.0, 0.0], "state": ["neutral", "neutral"],
    }, schema_overrides={"start": pl.UInt32}).write_parquet(lead)
    monkeypatch.setattr(hf_modules, "DISCOVERED_MODULES", [MODULE])
    monkeypatch.setattr(hf_logic, "MODULE_INFOS", {
        MODULE: ModuleInfo(name=MODULE, repo_id="org/repo", path=str(tmp_path), weights_url=str(lead)),
    })
    monkeypatch.setattr(restoration, "detect_callset_scope", lambda sites, flank: (CallsetScope.WGS, "forced"))
    monkeypatch.setattr(restoration, "load_hard_regions", lambda: (None, "not loaded in this test"))
    out_dir = tmp_path / "modules"
    hf_logic.annotate_vcf_with_all_modules(
        logging.getLogger(__name__),
        vcf_path=normalized,
        config=HfModuleAnnotationConfig(modules=[MODULE], output_dir=str(out_dir), user_name=USER),
        user_name=USER,
        sample_name=SAMPLE,
        normalized_parquet_path=normalized,
    )
    return pl.read_parquet(out_dir / f"{MODULE}_weights.parquet")


def _restored_starts(rows: pl.DataFrame) -> set[int]:
    return set(rows.filter(pl.col(EVIDENCE_COLUMN) == EVIDENCE_RESTORED)["start"].to_list())


def test_a_rejected_call_is_not_restored_and_an_absent_site_still_is(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, normalized: Path
) -> None:
    assert _restored_starts(_annotate(tmp_path, monkeypatch, normalized)) == {ABSENT}


def test_without_the_record_of_dropped_sites_nothing_is_restored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, normalized: Path
) -> None:
    """A parquet normalized before the record was kept cannot tell rejected from absent: off."""
    normalized.with_name(FILTERED_OUT_SITES_NAME).unlink()
    assert _restored_starts(_annotate(tmp_path, monkeypatch, normalized)) == set()


def _vcf() -> pl.LazyFrame:
    return pl.DataFrame(
        {"chrom": ["1", "1"], "start": PASSING, "ref": ["G", "A"], "alt": ["A", "G"],
         "filter": ["PASS", "PASS"], "genotype": [["A", "G"], ["G", "G"]]},
        schema_overrides={"start": pl.UInt32},
    ).lazy()


def _wgs(filtered_out: pl.LazyFrame | None, unknown: str = ""):
    base = build_restoration_context(_vcf(), 10_000, filtered_out, unknown)
    return restoration.RestorationContext(
        called_sites=base.called_sites, mode=base.mode, scope=CallsetScope.WGS,
        scope_reason="forced", max_flank_bp=10_000,
        filtered_out_sites=base.filtered_out_sites, filtered_out_unknown=base.filtered_out_unknown,
    )


@pytest.mark.parametrize("start_dtype", [pl.UInt32, pl.Int64], ids=["uint32", "int64"])
def test_restorable_sites_skips_a_filtered_out_site(start_dtype: pl.DataType) -> None:
    """The phenotype caller's path; the record's dtype need not match the parquet's."""
    dropped = pl.DataFrame({"chrom": ["1"], "start": [REJECTED]}, schema_overrides={"start": start_dtype}).lazy()
    sites = pl.DataFrame({"chrom": ["1", "1"], "start": [REJECTED, ABSENT]}).lazy()
    ctx = _wgs(dropped)
    assert set(restorable_sites(sites, ctx.called_sites, ctx).collect()["start"].to_list()) == {ABSENT}
    no_record = _wgs(None)
    assert set(restorable_sites(sites, no_record.called_sites, no_record).collect()["start"].to_list()) == {
        REJECTED, ABSENT,
    }


def test_an_unknown_record_turns_restoration_off_and_says_why() -> None:
    ctx = _wgs(None, "no record beside the parquet")
    assert not ctx.enabled
    lead = pl.DataFrame({
        "rsid": ["rs_absent"], "chrom": ["1"], "start": [ABSENT], "ref": ["A"],
        "genotype": [["A", "A"]], "module": ["m"], "weight": [0.0], "state": ["neutral"],
    }, schema_overrides={"start": pl.UInt32}).lazy()
    rows, stats = restored_rows(_vcf(), lead, "m", ctx)
    assert rows is None and stats["restored"] == 0


def test_a_filtered_out_site_does_not_count_as_coverage() -> None:
    """A rejected call is not evidence the stretch was read well: the flank is measured from passing
    calls only, so a site near only a rejected record stays unrestored."""
    far = 900_000
    dropped = pl.DataFrame({"chrom": ["1"], "start": [far - 10]}, schema_overrides={"start": pl.UInt32}).lazy()
    sites = pl.DataFrame({"chrom": ["1"], "start": [far]}).lazy()
    ctx = _wgs(dropped)
    assert restorable_sites(sites, ctx.called_sites, ctx).collect().height == 0
