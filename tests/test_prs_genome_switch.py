"""PRS results must never follow a previous genome after a file switch."""

from __future__ import annotations

from webui.grid import _artifact_key, filter_model_fingerprint, is_stale_grid_view_replay
from webui.state import (
    _preferred_prs_chart_id,
    _prs_compute_belongs_to_current_genome,
    _prs_reusable_results_for_file,
)


def test_in_flight_compute_is_stale_after_genome_switch() -> None:
    """Would have written Oksana's intelligence score onto Livia's tab."""
    assert _prs_compute_belongs_to_current_genome(
        1, "/data/oksana/user_vcf_normalized.parquet",
        1, "/data/oksana/user_vcf_normalized.parquet",
    )
    assert not _prs_compute_belongs_to_current_genome(
        1, "/data/oksana/user_vcf_normalized.parquet",
        2, "/data/livia/user_vcf_normalized.parquet",
    )
    assert not _prs_compute_belongs_to_current_genome(
        1, "/data/oksana/user_vcf_normalized.parquet",
        2, "",
    )
    assert not _prs_compute_belongs_to_current_genome(1, "", 1, "")


def test_cached_prs_rows_from_another_genome_are_not_reused() -> None:
    """Compute used to skip work because the PGS ID was already in state."""
    oksana = "/data/oksana/user_vcf_normalized.parquet"
    livia = "/data/livia/user_vcf_normalized.parquet"
    rows = [
        {"pgs_id": "PGS000001", "score": 1.23, "_source_file": oksana},
        {"pgs_id": "PGS000002", "score": 0.5, "_source_file": oksana},
    ]

    reused = _prs_reusable_results_for_file(rows, oksana, oksana, force_recompute=False)
    assert set(reused) == {"PGS000001", "PGS000002"}

    assert _prs_reusable_results_for_file(rows, oksana, livia, force_recompute=False) == {}
    assert _prs_reusable_results_for_file(rows, "", livia, force_recompute=False) == {}
    assert _prs_reusable_results_for_file(rows, oksana, oksana, force_recompute=True) == {}


def test_row_source_file_wins_over_state_source_file() -> None:
    """A leaked foreign row must not count as already-computed for this genome."""
    livia = "/data/livia/user_vcf_normalized.parquet"
    oksana = "/data/oksana/user_vcf_normalized.parquet"
    rows = [
        {"pgs_id": "PGS000001", "score": 1.23, "_source_file": oksana},
        {"pgs_id": "PGS000003", "score": 0.1, "_source_file": livia},
    ]
    reused = _prs_reusable_results_for_file(rows, livia, livia, force_recompute=False)
    assert set(reused) == {"PGS000003"}


def test_sorted_grid_artifact_is_per_file_not_per_state_class() -> None:
    """Would have served Oksana's sorted view after switching to Livia."""
    sort = [{"field": "pos", "sort": "asc"}]
    oksana = _artifact_key("UploadState", "/data/oksana.parquet", {}, sort)
    livia = _artifact_key("UploadState", "/data/livia.parquet", {}, sort)
    assert oksana != livia
    assert _artifact_key("UploadState", "/data/oksana.parquet", {}, sort) == oksana


def test_remount_filter_replay_is_dropped_once() -> None:
    """Unmounting a filtered grid can fire the old model after we cleared it."""
    previous = {"items": [{"field": "chrom", "operator": "equals", "value": "1"}]}
    fingerprint = filter_model_fingerprint(previous)

    assert is_stale_grid_view_replay(fingerprint, previous)
    assert not is_stale_grid_view_replay("", previous)
    assert not is_stale_grid_view_replay(fingerprint, {"items": []})
    assert not is_stale_grid_view_replay(
        fingerprint,
        {"items": [{"field": "chrom", "operator": "equals", "value": "2"}]},
    )


def test_cached_compute_opens_the_selected_trait_chart() -> None:
    """Compute used to no-op on a cached trait and leave the chart closed."""
    trait_rows = [
        {"trait": "body height", "pgs_ids": "PGS000010, PGS000011"},
        {"trait": "intelligence", "pgs_ids": "PGS000001, PGS000002"},
    ]
    result_rows = [
        {"pgs_id": "PGS000001", "trait": "intelligence"},
        {"pgs_id": "PGS000010", "trait": "body height"},
    ]
    assert _preferred_prs_chart_id(
        grouped=True,
        trait_rows=trait_rows,
        result_rows=result_rows,
        selected_pgs_ids=["PGS000001", "PGS000002"],
    ) == "intelligence"
    assert _preferred_prs_chart_id(
        grouped=True,
        trait_rows=trait_rows,
        result_rows=result_rows,
        selected_pgs_ids=[],
    ) == "body height"
    assert _preferred_prs_chart_id(
        grouped=False,
        trait_rows=trait_rows,
        result_rows=result_rows,
        selected_pgs_ids=["PGS000010"],
    ) == "PGS000010"


def test_clear_all_filter_replay_matches_the_old_intelligence_filter() -> None:
    """Clear All used to get the previous trait filter written back by MUI."""
    intelligence = {
        "items": [{"field": "trait", "operator": "contains", "value": "intelligence"}],
    }
    fingerprint = filter_model_fingerprint(intelligence)
    assert is_stale_grid_view_replay(fingerprint, intelligence)
    assert not is_stale_grid_view_replay(fingerprint, {"items": []})


def test_empty_filter_and_sort_share_the_same_fingerprint() -> None:
    """Cleared sort is stored as [] but fingerprints like an empty model."""
    assert filter_model_fingerprint([]) == filter_model_fingerprint({})
    assert filter_model_fingerprint(None) == filter_model_fingerprint({})
