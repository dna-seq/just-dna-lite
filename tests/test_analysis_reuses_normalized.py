"""An analysis skips normalization when the sample's normalized parquet is current.

The select-time normalization runs a real ``normalize_vcf_job`` here, on the small test VCF, so
"current" is decided by the same Dagster materialization metadata and parquet footer the web UI
reads, not by a stub.
"""

import shutil
from pathlib import Path

import pytest
from dagster import AssetMaterialization, DagsterInstance, MetadataValue

from just_dna_pipelines.annotation.annotation_runner import FULL_JOB, REUSE_NORMALIZED_JOB
from just_dna_pipelines.annotation.assets import NORMALIZATION_VERSION
from just_dna_pipelines.module_config import _load_config
from just_dna_pipelines.annotation.definitions import defs
from just_dna_pipelines.runtime import load_env
from webui import dagster_reads

SMALL_VCF = Path(__file__).resolve().parents[1] / "data" / "input" / "tests" / "antku_small.vcf"
USER = "reusetest"
SAMPLE = "antku_small"
PARTITION = f"{USER}/{SAMPLE}"


@pytest.fixture
def instance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DagsterInstance:
    load_env()
    monkeypatch.setenv("JUST_DNA_PIPELINES_OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("JUST_DNA_PIPELINES_INPUT_DIR", str(tmp_path / "input"))
    ephemeral = DagsterInstance.ephemeral()
    monkeypatch.setattr(dagster_reads, "get_dagster_instance", lambda: ephemeral)
    return ephemeral


def _normalize(instance: DagsterInstance, tmp_path: Path) -> Path:
    vcf = tmp_path / "input" / USER / SMALL_VCF.name
    vcf.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(SMALL_VCF, vcf)
    job = defs.resolve_job_def("normalize_vcf_job")
    instance.add_dynamic_partitions(job.partitions_def.name, [PARTITION])
    result = job.execute_in_process(
        run_config={
            "ops": {
                "user_vcf_normalized": {
                    "config": {"vcf_path": str(vcf), "user_name": USER, "sample_name": SAMPLE}
                }
            }
        },
        instance=instance,
        partition_key=PARTITION,
    )
    assert result.success
    return tmp_path / "output" / PARTITION / "user_vcf_normalized.parquet"


def test_a_sample_never_normalized_runs_the_full_job(instance: DagsterInstance) -> None:
    assert dagster_reads.analysis_job_name(PARTITION, True, False) == FULL_JOB


def test_a_current_parquet_is_reused(instance: DagsterInstance, tmp_path: Path) -> None:
    normalized = _normalize(instance, tmp_path)
    assert dagster_reads.normalize_run_config_if_stale(USER, SMALL_VCF.name, PARTITION) is None
    assert dagster_reads.analysis_job_name(PARTITION, True, False) == REUSE_NORMALIZED_JOB
    # The select-time check and the analysis agree, because they are the same test.
    assert normalized.exists()


@pytest.mark.parametrize("damage", [b"", b"PAR1 truncated, no footer"], ids=["empty", "truncated"])
def test_a_damaged_parquet_is_normalized_again(
    instance: DagsterInstance, tmp_path: Path, damage: bytes
) -> None:
    normalized = _normalize(instance, tmp_path)
    normalized.write_bytes(damage)
    assert dagster_reads.analysis_job_name(PARTITION, True, False) == FULL_JOB
    assert dagster_reads.normalize_run_config_if_stale(USER, SMALL_VCF.name, PARTITION) is not None


@pytest.mark.parametrize("recorded", [None, NORMALIZATION_VERSION - 1], ids=["unrecorded", "older"])
def test_a_parquet_from_older_normalization_code_is_normalized_again(
    instance: DagsterInstance, tmp_path: Path, recorded: int | None
) -> None:
    """Same filters, older code: a split-VCF parquet from before version 2 holds wrong genotypes."""
    _normalize(instance, tmp_path)
    assert dagster_reads.analysis_job_name(PARTITION, True, False) == REUSE_NORMALIZED_JOB
    metadata = {"quality_filters_hash": MetadataValue.text(_load_config().quality_filters.config_hash())}
    if recorded is not None:
        metadata["normalization_version"] = MetadataValue.int(recorded)
    instance.report_runless_asset_event(
        AssetMaterialization(asset_key="user_vcf_normalized", partition=PARTITION, metadata=metadata)
    )
    assert dagster_reads.analysis_job_name(PARTITION, True, False) == FULL_JOB
    assert dagster_reads.normalize_run_config_if_stale(USER, SMALL_VCF.name, PARTITION) is not None


def test_a_deleted_parquet_is_normalized_again(instance: DagsterInstance, tmp_path: Path) -> None:
    _normalize(instance, tmp_path).unlink()
    assert dagster_reads.analysis_job_name(PARTITION, True, False) == FULL_JOB


@pytest.mark.parametrize(
    ("has_hf_modules", "expected"),
    [(True, "annotate_all_job"), (False, "annotate_ensembl_only_job")],
)
def test_ensembl_runs_keep_their_own_jobs(
    instance: DagsterInstance, tmp_path: Path, has_hf_modules: bool, expected: str
) -> None:
    _normalize(instance, tmp_path)
    assert dagster_reads.analysis_job_name(PARTITION, has_hf_modules, True) == expected


def test_no_modules_never_picks_the_reuse_job(instance: DagsterInstance, tmp_path: Path) -> None:
    _normalize(instance, tmp_path)
    assert dagster_reads.analysis_job_name(PARTITION, False, False) == FULL_JOB


def test_the_reuse_job_selects_no_normalization() -> None:
    job = defs.resolve_job_def(REUSE_NORMALIZED_JOB)
    selected = {key.to_user_string() for key in job.asset_layer.executable_asset_keys}
    assert "user_vcf_normalized" not in selected
    assert {"user_hf_module_annotations", "user_longevity_report"} <= selected
