"""The PRS checkpoint keeps its rows beside the sample, not in the Dagster event log (#35)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from dagster import (
    AssetKey,
    AssetMaterialization,
    AssetRecordsFilter,
    DagsterInstance,
    MetadataValue,
)
from dagster._serdes import serialize_value
from webui.state import (
    PRS_CHECKPOINT_FILENAME,
    PRS_RESULTS_ASSET_KEY,
    _prs_partition_key,
    checkpoint_prs_results,
    restore_prs_checkpoint,
)

from webui import state


def _rows(padding: int = 0) -> list[dict[str, Any]]:
    """Rows shaped like prs-ui's: a dict keyed by data, a list of dicts, nulls, unicode."""
    return [
        {
            "pgs_id": "PGS000001",
            "score": 1.25,
            "variants_matched": 120,
            "reference_panel": None,
            "risk_estimate_methods": ["AUROC model", "h² EUR (pan_ukbb)"],
            "risk_estimates_by_method": {"AUROC model": "0.7%", "h² EUR (pan_ukbb)": "0.9% (h²=0.080)"},
            "heritability_metrics": [{"population": "European", "h2": "0.080"}],
            "summary": "x" * padding,
        },
        {
            "pgs_id": "PGS000002",
            "score": -0.5,
            "variants_matched": 7,
            "reference_panel": "1000G",
            "risk_estimate_methods": ["OR per SD"],
            "risk_estimates_by_method": {"OR per SD": "1.2x"},
            "heritability_metrics": [],
            "summary": "y" * padding,
        },
    ]


@pytest.fixture
def instance() -> Iterator[DagsterInstance]:
    with DagsterInstance.ephemeral() as inst:
        yield inst


@pytest.fixture
def parquet_path(tmp_path: Path) -> str:
    sample_dir = tmp_path / "users" / "public" / "sampleA"
    sample_dir.mkdir(parents=True)
    return str(sample_dir / "user_vcf_normalized.parquet")


def _checkpoint(instance: DagsterInstance, parquet_path: str, rows: list[dict[str, Any]]) -> Path:
    return checkpoint_prs_results(
        instance, parquet_path, rows, genome_build="GRCh38", ancestry="EUR", sample_type="wgs"
    )


def _latest_event_bytes(instance: DagsterInstance, partition_key: str) -> int:
    records = instance.fetch_materializations(
        records_filter=AssetRecordsFilter(
            asset_key=AssetKey(PRS_RESULTS_ASSET_KEY), asset_partitions=[partition_key]
        ),
        limit=1,
    ).records
    return len(serialize_value(records[0].asset_materialization))


def test_round_trip_returns_the_same_rows(instance: DagsterInstance, parquet_path: str) -> None:
    rows = _rows()
    comparison_row = {**rows[0], "sample": "peer (peer.vcf)"}
    written = _checkpoint(instance, parquet_path, [*rows, comparison_row])

    assert written == Path(parquet_path).parent / PRS_CHECKPOINT_FILENAME
    restored = restore_prs_checkpoint(instance, _prs_partition_key(parquet_path))

    assert restored.status == "restored"
    assert restored.rows == rows
    assert restored.sample_type == "wgs"
    assert restored.row_count == 3


def test_the_event_does_not_grow_with_the_rows(instance: DagsterInstance, parquet_path: str) -> None:
    partition_key = _prs_partition_key(parquet_path)
    _checkpoint(instance, parquet_path, _rows(padding=10))
    small = _latest_event_bytes(instance, partition_key)
    _checkpoint(instance, parquet_path, _rows(padding=200_000))
    large = _latest_event_bytes(instance, partition_key)

    assert large == small
    assert small < 4_000

    # Control: the pre-#35 shape, rows in the metadata, does grow, so the measure can see it.
    instance.report_runless_asset_event(
        AssetMaterialization(
            asset_key=PRS_RESULTS_ASSET_KEY,
            partition=partition_key,
            metadata={"results": MetadataValue.json({"rows": _rows(padding=200_000)})},
        )
    )
    assert _latest_event_bytes(instance, partition_key) > 400_000


def test_rewrite_replaces_the_file_and_leaves_no_temp(instance: DagsterInstance, parquet_path: str) -> None:
    _checkpoint(instance, parquet_path, _rows())
    path = _checkpoint(instance, parquet_path, _rows()[:1])

    assert json.loads(path.read_text(encoding="utf-8")) == _rows()[:1]
    assert sorted(p.name for p in path.parent.iterdir()) == [PRS_CHECKPOINT_FILENAME]


@pytest.mark.parametrize(
    "damage",
    [
        pytest.param(lambda p: p.unlink(), id="missing"),
        pytest.param(lambda p: p.write_text(p.read_text()[:40], encoding="utf-8"), id="truncated"),
        pytest.param(lambda p: p.write_text("", encoding="utf-8"), id="empty"),
        pytest.param(lambda p: p.write_text('{"rows": []}', encoding="utf-8"), id="not-a-list"),
    ],
)
def test_a_damaged_file_means_recompute(instance: DagsterInstance, parquet_path: str, damage: Any) -> None:
    damage(_checkpoint(instance, parquet_path, _rows()))

    restored = restore_prs_checkpoint(instance, _prs_partition_key(parquet_path))

    assert restored.status == "absent"
    assert restored.rows == []


def test_an_event_from_before_the_fix_is_not_read(instance: DagsterInstance, parquet_path: str) -> None:
    """Rows in a `results` blob are never restored: that branch would keep the bug reachable."""
    instance.report_runless_asset_event(
        AssetMaterialization(
            asset_key=PRS_RESULTS_ASSET_KEY,
            partition=_prs_partition_key(parquet_path),
            metadata={
                "results": MetadataValue.json({"rows": _rows()}),
                "format_version": MetadataValue.text(state._prs_results_version()),
            },
        )
    )

    assert restore_prs_checkpoint(instance, _prs_partition_key(parquet_path)).status == "absent"


def test_no_event_means_absent(instance: DagsterInstance) -> None:
    assert restore_prs_checkpoint(instance, "public/nobody").status == "absent"


def test_a_format_version_bump_invalidates_the_checkpoint(
    instance: DagsterInstance, parquet_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _checkpoint(instance, parquet_path, _rows())
    monkeypatch.setattr(state, "_prs_results_version", lambda: "prs-ui=99.0.0")

    restored = restore_prs_checkpoint(instance, _prs_partition_key(parquet_path))

    assert restored.status == "stale"
    assert restored.rows == []


def test_partition_key_is_user_and_sample() -> None:
    assert _prs_partition_key("/data/output/users/public/sampleA/user_vcf_normalized.parquet") == "public/sampleA"
