"""The just-dna-lite MCP server: validation against a ground truth built from a real VCF, the job
store's crash handling, the run configs the runner hands Dagster, and the tool surface itself.

The validation fixture is a module authored *from* the tracked ``antku_small.vcf``: some loci carry
the sample's own genotype (must read ``called_matched``), some a genotype it does not have
(``called_unmatched``), one the right genotype under the wrong ``ref`` (``called_ref_mismatch``) and
some a position the VCF never calls (``not_observed``). The annotated parquet is produced by the
real engine join, so these tests fail if validation and the engine ever disagree about a match.
"""

from __future__ import annotations

import asyncio
import json
import random
import subprocess
import sys
from pathlib import Path

import polars as pl
import pytest
from dagster import validate_run_config
from fastmcp import Client
from fastmcp.exceptions import ToolError

from just_dna_pipelines.annotation.annotation_runner import (
    ENSEMBL_JOB,
    FULL_JOB,
    REUSE_NORMALIZED_JOB,
    AnnotationRequest,
    build_run_config,
)
from just_dna_pipelines.annotation.definitions import defs
from just_dna_pipelines.annotation.hf_logic import (
    annotate_vcf_with_module_weights,
    prepare_vcf_for_module_annotation,
)
from just_dna_pipelines.annotation.hf_modules import ModuleInfo
from just_dna_pipelines.lite_mcp import jobs
from just_dna_pipelines.lite_mcp.server import mcp
from just_dna_pipelines.lite_mcp.validation import SampleInput, validate_module_run

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKED_VCF = REPO_ROOT / "data" / "input" / "tests" / "antku_small.vcf"
MODULE = "lite_mcp_fixture"
SEED = 20260926
BASES = ("A", "C", "G", "T")


@pytest.fixture(scope="module")
def normalized(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("sample") / "user_vcf_normalized.parquet"
    prepare_vcf_for_module_annotation(TRACKED_VCF).sink_parquet(out)
    return out


class Truth:
    """The fixture module and which status each of its loci must get."""

    def __init__(self, lead: pl.DataFrame, by_status: dict[str, set[str]], matched_weights: dict[str, float]):
        self.lead = lead
        self.by_status = by_status
        self.matched_weights = matched_weights


def _snv_calls(normalized: Path) -> pl.DataFrame:
    return (
        pl.read_parquet(normalized)
        .filter(
            pl.col("ref").str.len_chars() == 1,
            pl.col("alt").str.len_chars() == 1,
            pl.col("genotype").list.len() == 2,
            ~pl.col("chrom").str.contains("_"),
        )
        .unique(subset=["chrom", "start"], keep="first", maintain_order=True)
    )


def build_truth(normalized: Path, outlier_weight: float | None = None) -> Truth:
    calls = _snv_calls(normalized)
    rng = random.Random(SEED)
    picked = [calls.row(i, named=True) for i in rng.sample(range(calls.height), 7)]
    matched, unmatched, mismatched = picked[:3], picked[3:5], picked[5:6]
    called_positions = set(zip(calls["chrom"], calls["start"]))
    absent = []
    for row in picked[6:] + picked[:1]:
        start = row["start"] + 1
        while (row["chrom"], start) in called_positions:
            start += 1
        absent.append({**row, "start": start})

    rows: list[dict] = []
    weights = [0.5, -0.3, 1.2]
    if outlier_weight is not None:
        weights[0] = outlier_weight
    by_status: dict[str, set[str]] = {k: set() for k in ("called_matched", "called_unmatched", "called_ref_mismatch", "not_observed")}
    matched_weights: dict[str, float] = {}

    def key(row: dict) -> str:
        return f"{row['chrom']}:{row['start']}:fixture"

    for row, w in zip(matched, weights):
        rows.append({**row, "genotype": row["genotype"], "weight": w})
        by_status["called_matched"].add(key(row))
        matched_weights[key(row)] = w
    for row in unmatched:
        # Author the one genotype the sample certainly does not carry at a site it was called at.
        other = next(b for b in BASES if b not in (row["ref"], *row["genotype"]))
        rows.append({**row, "genotype": [other, other], "weight": 0.7})
        by_status["called_unmatched"].add(key(row))
    for row in mismatched:
        wrong_ref = next(b for b in BASES if b not in (row["ref"], *row["genotype"]))
        rows.append({**row, "ref": wrong_ref, "genotype": row["genotype"], "weight": 0.4})
        by_status["called_ref_mismatch"].add(key(row))
    for row in absent:
        rows.append({**row, "genotype": [row["ref"], row["ref"]], "weight": 0.9})
        by_status["not_observed"].add(key(row))

    lead = pl.DataFrame(
        {
            "chrom": [r["chrom"] for r in rows],
            "start": pl.Series([r["start"] for r in rows], dtype=pl.UInt32),
            "ref": [r["ref"] for r in rows],
            "genotype": pl.Series([sorted(r["genotype"]) for r in rows], dtype=pl.List(pl.String)),
            "variant_key": [key(r) for r in rows],
            "rsid": [None] * len(rows),
            "module": [MODULE] * len(rows),
            "weight": [r["weight"] for r in rows],
            "state": ["risk"] * len(rows),
        },
        schema_overrides={"rsid": pl.String},
    )
    return Truth(lead, by_status, matched_weights)


def _annotate(truth: Truth, normalized: Path, tmp: Path) -> tuple[ModuleInfo, Path]:
    module_dir = tmp / MODULE
    module_dir.mkdir(parents=True, exist_ok=True)
    weights = module_dir / "weights.parquet"
    truth.lead.write_parquet(weights)
    info = ModuleInfo(name=MODULE, repo_id="test", path=str(module_dir), lead_url=str(weights), weights_url=str(weights))
    out = tmp / "annotated" / f"{MODULE}_weights.parquet"
    annotate_vcf_with_module_weights(pl.scan_parquet(normalized), MODULE, out, module_info=info)
    return info, out


def _samples(n: int, normalized: Path, annotated: Path) -> list[SampleInput]:
    return [SampleInput(sample_id=f"test/s{i}", normalized_path=normalized, annotated_path=annotated) for i in range(n)]


def test_every_locus_gets_the_status_its_construction_implies(normalized: Path, tmp_path: Path) -> None:
    truth = build_truth(normalized)
    info, annotated = _annotate(truth, normalized, tmp_path)
    coverage_out = tmp_path / "coverage.parquet"
    report = validate_module_run(info, _samples(1, normalized, annotated), coverage_out=coverage_out)

    coverage = pl.read_parquet(coverage_out)
    for status, expected in truth.by_status.items():
        got = set(coverage.filter(pl.col("status") == status)["locus"])
        assert got == expected, status
    assert report.coverage_totals["restored_hom_ref"] == 0
    assert report.loci == truth.lead.height
    assert report.join_strategy == "position"


def test_score_is_the_sum_of_the_matched_authored_weights(normalized: Path, tmp_path: Path) -> None:
    truth = build_truth(normalized)
    info, annotated = _annotate(truth, normalized, tmp_path)
    (score,) = validate_module_run(info, _samples(1, normalized, annotated)).scores
    expected = truth.matched_weights
    assert score.matched_loci == len(expected)
    assert score.total_weight == pytest.approx(sum(expected.values()))
    assert score.positive_weight == pytest.approx(sum(w for w in expected.values() if w > 0))
    assert score.negative_weight == pytest.approx(sum(w for w in expected.values() if w < 0))
    top = max(expected, key=lambda k: abs(expected[k]))
    assert score.top_variant == top
    assert score.top_share == pytest.approx(abs(expected[top]) / sum(abs(w) for w in expected.values()), abs=1e-4)


def test_coverage_findings_name_exactly_the_loci_that_earned_them(normalized: Path, tmp_path: Path) -> None:
    truth = build_truth(normalized)
    info, annotated = _annotate(truth, normalized, tmp_path)
    findings = {f.code: f for f in validate_module_run(info, _samples(3, normalized, annotated)).findings}
    assert set(findings["loci_never_observed"].loci) == truth.by_status["not_observed"]
    assert set(findings["called_but_never_matched"].loci) == truth.by_status["called_unmatched"]
    assert set(findings["reference_allele_mismatch"].loci) == truth.by_status["called_ref_mismatch"]


def test_identical_genomes_read_as_a_constant_score_shifted_by_shared_rows(normalized: Path, tmp_path: Path) -> None:
    truth = build_truth(normalized)
    info, annotated = _annotate(truth, normalized, tmp_path)
    findings = {f.code: f for f in validate_module_run(info, _samples(3, normalized, annotated)).findings}
    assert "constant_score" in findings
    assert set(findings["weight_shared_by_all_genomes"].loci) == set(truth.matched_weights)


def test_shape_checks_say_not_assessed_below_the_sample_floor(normalized: Path, tmp_path: Path) -> None:
    truth = build_truth(normalized)
    info, annotated = _annotate(truth, normalized, tmp_path)
    codes = {f.code: f.severity for f in validate_module_run(info, _samples(1, normalized, annotated)).findings}
    assert codes.get("distribution_not_assessed") == "not_assessed"
    assert "constant_score" not in codes and "weight_shared_by_all_genomes" not in codes


def test_an_outlier_weight_is_flagged_and_an_ordinary_one_is_not(normalized: Path, tmp_path: Path) -> None:
    truth = build_truth(normalized, outlier_weight=100.0)
    info, annotated = _annotate(truth, normalized, tmp_path / "outlier")
    outliers = {f.code: f for f in validate_module_run(info, _samples(1, normalized, annotated)).findings}["weight_outliers"]
    heavy = {k for k, w in truth.matched_weights.items() if w == 100.0}
    assert set(outliers.loci) == heavy

    plain = build_truth(normalized)
    info, annotated = _annotate(plain, normalized, tmp_path / "plain")
    assert "weight_outliers" not in {f.code for f in validate_module_run(info, _samples(1, normalized, annotated)).findings}


def test_skipped_and_failed_genomes_are_reported_and_not_scored(normalized: Path, tmp_path: Path) -> None:
    truth = build_truth(normalized)
    info, annotated = _annotate(truth, normalized, tmp_path)
    samples = [
        SampleInput(sample_id="test/ok", normalized_path=normalized, annotated_path=annotated),
        SampleInput(sample_id="test/skip", normalized_path=normalized, skipped_reason="vcf carries no rsIDs"),
        SampleInput(sample_id="test/fail", normalized_path=normalized, failed_reason="boom"),
    ]
    report = validate_module_run(info, samples)
    assert {s.sample_id: s.status for s in report.scores} == {"test/ok": "annotated", "test/skip": "skipped", "test/fail": "failed"}
    assert report.samples_annotated == 1
    codes = {f.code for f in report.findings}
    assert {"module_skipped", "module_failed"} <= codes


@pytest.mark.parametrize("job_name", [FULL_JOB, REUSE_NORMALIZED_JOB, ENSEMBL_JOB])
def test_the_runner_config_validates_against_the_job_it_is_for(job_name: str, tmp_path: Path) -> None:
    """Config for an asset outside a job's selection is a Dagster validation error, so the
    reuse job must not carry `user_vcf_normalized` config and the full job must."""
    request = AnnotationRequest(vcf_path=tmp_path / "s.vcf", user_name="test", modules=["coronary"], ensembl=job_name == ENSEMBL_JOB)
    config = build_run_config(request, job_name)
    validate_run_config(defs.resolve_job_def(job_name), config)
    assert ("user_vcf_normalized" in config["ops"]) == (job_name != REUSE_NORMALIZED_JOB)


def _write_job(tmp: Path, monkeypatch: pytest.MonkeyPatch, pid: int | None, status: str = "running") -> jobs.JobRecord:
    monkeypatch.setenv("JUST_DNA_PIPELINES_INTERIM_DIR", str(tmp))
    record = jobs.JobRecord(
        job_id="20260926T000000Z-deadbeef",
        status=status,
        request=jobs.JobRequest(samples=["test/s"], modules=["coronary"]),
        samples=[jobs.SampleRun(requested="test/s", status="running")],
        created_at=jobs.utc_now(),
        pid=pid,
        log_path=str(tmp / "lite_mcp" / "jobs" / "20260926T000000Z-deadbeef" / "worker.log"),
    )
    jobs.save_job(record)
    return record


def _dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def test_a_job_whose_worker_died_is_failed_not_running_forever(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    record = _write_job(tmp_path, monkeypatch, pid=_dead_pid())
    reconciled = jobs.reconcile(jobs.read_job(record.job_id))
    assert reconciled.status == "failed"
    assert reconciled.samples[0].status == "failed"
    assert jobs.read_job(record.job_id).status == "failed"


def test_a_finished_job_is_left_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    record = _write_job(tmp_path, monkeypatch, pid=_dead_pid(), status="succeeded")
    assert jobs.reconcile(jobs.read_job(record.job_id)).status == "succeeded"
    assert jobs.cancel_job(record.job_id).status == "succeeded"


@pytest.mark.parametrize("bad", ["", "../escape", "a/b", ".hidden"])
def test_job_ids_cannot_address_outside_the_store(bad: str) -> None:
    with pytest.raises(ValueError):
        jobs.job_dir(bad)


EXPECTED_TOOLS = {
    "status", "list_samples", "list_modules", "install_module", "uninstall_module", "start_annotation",
    "get_job", "list_jobs", "wait_for_job", "cancel_job", "get_results", "validate_module", "get_variant_rows",
}


def _call(name: str, args: dict) -> object:
    async def go() -> object:
        async with Client(mcp) as client:
            if name == "__list__":
                return {t.name for t in await client.list_tools()}
            return (await client.call_tool(name, args)).structured_content
    return asyncio.run(go())


def test_the_tool_surface_is_exactly_the_documented_one() -> None:
    assert _call("__list__", {}) == EXPECTED_TOOLS


def test_status_names_the_checkout_and_its_dagster_home() -> None:
    status = _call("status", {})
    assert Path(status["workspace_root"]) == REPO_ROOT
    assert status["modules_discovered"] > 0


def test_an_unknown_module_is_refused_before_any_job_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUST_DNA_PIPELINES_INTERIM_DIR", str(tmp_path))
    with pytest.raises(ToolError, match="Unknown module"):
        _call("start_annotation", {"samples": ["test/s"], "modules": ["no_such_module_anywhere"]})
    assert not (tmp_path / "lite_mcp" / "jobs").exists()


def test_install_refuses_a_directory_that_is_not_a_compiled_module(tmp_path: Path) -> None:
    (tmp_path / "variants.csv").write_text("rsid,genotype\n")
    with pytest.raises(ToolError, match="no lead parquet"):
        _call("install_module", {"compiled_dir": str(tmp_path)})


def test_job_records_round_trip_through_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    record = _write_job(tmp_path, monkeypatch, pid=None, status="queued")
    raw = json.loads(jobs.job_file(jobs.job_dir(record.job_id)).read_text())
    assert jobs.JobRecord.model_validate(raw) == record
