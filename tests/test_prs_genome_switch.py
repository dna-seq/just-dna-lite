"""PRS results must never follow a previous genome after a file switch."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from webui.grid import _artifact_key, filter_model_fingerprint, is_stale_grid_view_replay
from webui.state import (
    _preferred_prs_chart_id,
    _prs_compute_belongs_to_current_genome,
    _prs_reusable_results_for_file,
    _prs_result_cache_key,
    _sample_choice_label,
    _scan_prs_genotypes,
    comparable_prs_samples,
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


def test_comparable_prs_samples_requires_same_species_genome_and_ready_parquet() -> None:
    """Compare must not mix species, builds, unread tables, or the selected file."""
    files = ["a.vcf.gz", "b.vcf.gz", "c.vcf.gz", "d.vcf.gz", "e.vcf.gz"]
    meta = {
        "a.vcf.gz": {
            "species": "Homo sapiens",
            "reference_genome": "GRCh38",
            "sample_name": "Anton",
        },
        "b.vcf.gz": {
            "species": "Homo sapiens",
            "reference_genome": "GRCh38",
            "sample_name": "Livia",
        },
        "c.vcf.gz": {"species": "Mus musculus", "reference_genome": "GRCh38"},
        "d.vcf.gz": {"species": "Homo sapiens", "reference_genome": "GRCh37"},
        "e.vcf.gz": {
            "species": "Homo sapiens",
            "reference_genome": "GRCh38",
            "sample_name": "Unread",
        },
    }
    ready = {"a.vcf.gz", "b.vcf.gz", "c.vcf.gz", "d.vcf.gz"}
    peers = comparable_prs_samples(
        files, "a.vcf.gz", meta, is_ready=lambda filename: filename in ready
    )
    assert [peer["filename"] for peer in peers] == ["b.vcf.gz"]
    assert peers[0]["label"] == "Livia"
    assert peers[0]["display_name"] == "Livia"
    assert peers[0]["choice_label"] == "Livia (b.vcf.gz)"
    named = comparable_prs_samples(
        files,
        "a.vcf.gz",
        meta,
        is_ready=lambda filename: filename in ready,
        display_names={"b.vcf.gz": "Livia Zaharia"},
    )
    assert named[0]["label"] == "Livia Zaharia"
    assert named[0]["choice_label"] == "Livia Zaharia (b.vcf.gz)"
    assert comparable_prs_samples(
        files, "a.vcf.gz", meta, is_ready=lambda _filename: False
    ) == []


def test_sample_choice_label_shows_name_and_filename() -> None:
    """Dropdown text keeps the VCF name when the left-panel label is different."""
    assert (
        _sample_choice_label("Livia Zaharia", "SIMHIFQTILQ.hard-filtered.vcf.gz")
        == "Livia Zaharia (SIMHIFQTILQ.hard-filtered.vcf.gz)"
    )
    assert _sample_choice_label("antonkulaga", "antonkulaga.vcf") == "antonkulaga.vcf"
    assert _sample_choice_label("file.vcf", "file.vcf") == "file.vcf"


def test_prs_result_cache_key_separates_compared_samples() -> None:
    """A leftover PGS ID from genome A must not skip compute on genome B."""
    assert _prs_result_cache_key({"pgs_id": "PGS000001"}) == "PGS000001"
    assert (
        _prs_result_cache_key({"pgs_id": "PGS000001", "sample": "livia"})
        == "PGS000001::livia"
    )


def test_reusable_results_index_comparison_rows_by_sample() -> None:
    """Compute used to collapse two genomes into one cache slot per PGS ID."""
    anton = "/data/anton/user_vcf_normalized.parquet"
    livia = "/data/livia/user_vcf_normalized.parquet"
    rows = [
        {"pgs_id": "PGS000001", "sample": "anton", "score": 1.0, "_source_file": anton},
        {"pgs_id": "PGS000001", "sample": "livia", "score": 2.0, "_source_file": livia},
    ]
    reused = _prs_reusable_results_for_file(
        rows,
        anton,
        anton,
        force_recompute=False,
        allowed_source_files={anton, livia},
    )
    assert reused["PGS000001::anton"]["score"] == 1.0
    assert reused["PGS000001::livia"]["score"] == 2.0
    assert _prs_reusable_results_for_file(
        rows, anton, anton, force_recompute=False
    ) == {"PGS000001::anton": rows[0]}


def test_compare_ancestry_aliases_start_to_pos(tmp_path: Path) -> None:
    """Would have logged 'unable to find column pos' on every Compare add."""
    path = tmp_path / "norm.parquet"
    pl.DataFrame(
        {
            "chrom": ["1", "1"],
            "start": [100, 200],
            "end": [101, 201],
            "rsid": ["rs1", "rs2"],
            "ref": ["A", "C"],
            "alt": ["G", "T"],
            "genotype": [["A", "G"], ["C", "C"]],
        }
    ).write_parquet(path)

    raw = pl.scan_parquet(path)
    assert "pos" not in raw.collect_schema().names()
    with pytest.raises(pl.exceptions.ColumnNotFoundError):
        raw.select("pos").unique().collect()

    normalized = _scan_prs_genotypes(path)
    names = normalized.collect_schema().names()
    assert "pos" in names
    assert "start" not in names
    assert "end" not in names
    assert set(normalized.select("pos").collect()["pos"].to_list()) == {100, 200}
