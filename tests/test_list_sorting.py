"""Sort orders of a sample's file lists and the PRS "Computed" column (issues #19, #20)."""

import os
import random
from pathlib import Path

import pytest

from webui.list_sorting import (
    COMPUTED_AT_FIELD,
    OUTPUT_FILE_SORTS,
    REPORT_FILE_SORTS,
    computed_at_now,
    created_fields,
    sort_files,
    with_computed_at_column,
)


def _files(tmp_path: Path, seed: int = 7) -> list[dict]:
    """Real files with distinct mtimes, listed the way the panel builds its dicts."""
    rng = random.Random(seed)
    specs = [
        ("longevitymap", "weights"),
        ("longevitymap", "annotations"),
        ("coronary", "weights"),
        ("ensembl", "annotations"),
        ("Älteres", "vcf_export"),  # unicode and a capital letter
        ("abo", "phenotypes"),
    ]
    stamps = rng.sample(range(1_700_000_000, 1_800_000_000), len(specs))
    files = []
    for (module, kind), stamp in zip(specs, stamps):
        path = tmp_path / f"{module}_{kind}.parquet"
        path.write_bytes(b"x")
        os.utime(path, (stamp, stamp))
        files.append({"name": path.name, "module": module, "type": kind, **created_fields(path.stat().st_mtime)})
    rng.shuffle(files)
    return files


def test_the_default_orders_are_the_ones_the_panel_always_used(tmp_path: Path) -> None:
    files = _files(tmp_path)
    assert OUTPUT_FILE_SORTS[0][0] == "module"
    assert [f["name"] for f in sort_files(files, "module")] == [
        f["name"] for f in sorted(files, key=lambda f: (f["module"], f["type"]))
    ]
    assert REPORT_FILE_SORTS[0][0] == "newest"


@pytest.mark.parametrize("order", sorted({v for v, _ in OUTPUT_FILE_SORTS + REPORT_FILE_SORTS}))
def test_every_order_keeps_every_file_once_and_is_stable_across_input_order(tmp_path: Path, order: str) -> None:
    files = _files(tmp_path)
    first = sort_files(files, order)
    assert sorted(f["name"] for f in first) == sorted(f["name"] for f in files)
    reshuffled = list(reversed(files))
    assert [f["name"] for f in sort_files(reshuffled, order)] == [f["name"] for f in first]


def test_newest_and_oldest_follow_the_file_dates_and_mirror_each_other(tmp_path: Path) -> None:
    files = _files(tmp_path)
    newest = sort_files(files, "newest")
    stamps = [f["created_ts"] for f in newest]
    assert stamps == sorted(stamps, reverse=True)
    assert [f["name"] for f in sort_files(files, "oldest")] == [f["name"] for f in reversed(newest)]
    # The displayed text sorts the same way as the number.
    assert [f["created_at"] for f in newest] == sorted((f["created_at"] for f in newest), reverse=True)


def test_name_ignores_case_and_type_groups_kinds(tmp_path: Path) -> None:
    files = _files(tmp_path)
    names = [f["name"] for f in sort_files(files, "name")]
    assert names == sorted(names, key=str.casefold)
    kinds = [f["type"] for f in sort_files(files, "type")]
    assert kinds == sorted(kinds)


def test_ties_on_the_key_fall_back_to_the_name() -> None:
    same = created_fields(1_750_000_000)
    files = [{"name": n, "module": "m", "type": "t", **same} for n in ("c.parquet", "A.parquet", "b.parquet")]
    expected = ["A.parquet", "b.parquet", "c.parquet"]
    for order in ("module", "type", "newest", "oldest"):
        assert [f["name"] for f in sort_files(files, order)] == expected


def test_an_empty_list_and_an_unknown_order() -> None:
    assert sort_files([], "newest") == []
    with pytest.raises(ValueError, match="Unknown sort order"):
        sort_files([], "size")


def test_the_prs_grid_gains_one_computed_column_keyed_by_row_id() -> None:
    results = [
        {"pgs_id": "PGS000001", COMPUTED_AT_FIELD: "2026-11-20 10:00:00"},
        {"pgs_id": "PGS000002"},  # restored from a checkpoint written before the stamp
        {"pgs_id": "PGS000003", COMPUTED_AT_FIELD: computed_at_now()},
    ]
    # prs-ui gives row i the id i; the grid may hand rows back in another order.
    rows = [{"id": i, "pgs_id": r["pgs_id"]} for i, r in enumerate(results)][::-1]
    columns = [{"field": "pgs_id", "headerName": "PGS ID"}]

    new_rows, new_columns = with_computed_at_column(results, rows, columns)

    assert {r["pgs_id"]: r[COMPUTED_AT_FIELD] for r in new_rows} == {
        r["pgs_id"]: r.get(COMPUTED_AT_FIELD, "") for r in results
    }
    assert [c["field"] for c in new_columns] == ["pgs_id", COMPUTED_AT_FIELD]
    assert len(new_rows) == len(rows)
    # Rebuilding the grid twice never adds the column twice.
    _, again = with_computed_at_column(results, new_rows, new_columns)
    assert [c["field"] for c in again] == ["pgs_id", COMPUTED_AT_FIELD]
