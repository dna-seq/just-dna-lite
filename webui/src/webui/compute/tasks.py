"""Callables executed inside compute-pool workers.

Keep this module slim.  Spawned children import the module that owns the callable, so
every top-level import here is paid by every worker at startup.  The heavy imports
(polars, the grid helpers, polars-bio) therefore live *inside* the functions, which is
the one place the "no inline imports" rule has to yield: the alternative is a
multi-second import on every worker whether or not it ever runs a query.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class GridSource:
    """How a worker should reopen a grid's data.

    A descriptor rather than a serialized plan on purpose: ``LazyFrame.serialize()``
    round-trips ``scan_parquet`` fine but fails for ``polars_bio.scan_vcf`` with
    ``ComputeError: python: ModuleNotFoundError: No module named 'cloudpickle'``,
    because polars-bio registers a Python-side IO source.
    """

    reader: Literal["scan_file", "prepare_vcf"]
    path: str


@dataclass(frozen=True)
class GridPage:
    """One materialized page plus the filtered row count when it was requested."""

    rows: list[dict[str, Any]]
    row_count: int | None


def _open(source: GridSource):
    """Reopen *source* as a LazyFrame inside the worker."""
    if source.reader == "prepare_vcf":
        from pathlib import Path

        from just_dna_pipelines.annotation.hf_logic import prepare_vcf_for_module_annotation

        return prepare_vcf_for_module_annotation(Path(source.path))

    from reflex_mui_datagrid import scan_file

    lf, _descriptions = scan_file(source.path)
    return lf


def _filtered(source: GridSource, filter_model: dict[str, Any], string_filter_mode: str):
    from reflex_mui_datagrid.polars_utils import apply_filter_model

    lf = _open(source)
    if filter_model and filter_model.get("items"):
        lf = apply_filter_model(
            lf,
            filter_model,
            None,
            string_filter_mode=string_filter_mode,  # type: ignore[arg-type]
        )
    return lf


def materialize_sorted(
    source: GridSource,
    filter_model: dict[str, Any],
    sort_model: list[dict[str, str]],
    out_path: str,
    string_filter_mode: str = "case_insensitive",
) -> int:
    """Stream the filtered+sorted frame to ``out_path`` and return its row count.

    Sorting once into a page-servable artifact is what makes pagination O(page).
    ``lf.sort(...).slice(offset, n)`` re-sorts the whole frame on every request:
    Polars only pushes a dynamic predicate down for single-key sorts, and multi-key
    sorts materialize in full.  ``sink_parquet`` streams and spills to disk, so peak
    memory here is bounded regardless of input size.
    """
    import polars as pl
    from reflex_mui_datagrid.polars_utils import apply_sort_model

    lf = _filtered(source, filter_model, string_filter_mode)
    apply_sort_model(lf, sort_model, None).sink_parquet(out_path)
    return int(pl.scan_parquet(out_path).select(pl.len()).collect().item())


def read_page(
    source: GridSource,
    filter_model: dict[str, Any],
    offset: int,
    limit: int,
    with_count: bool,
    string_filter_mode: str = "case_insensitive",
) -> GridPage:
    """Collect rows ``[offset, offset+limit)`` and optionally the filtered row count.

    No sort is applied here.  Sorted grids point *source* at the artifact written by
    :func:`materialize_sorted`, which is already in order, so this stays a cheap slice.
    """
    import polars as pl
    from reflex_mui_datagrid.polars_utils import _dataframe_to_dicts

    lf = _filtered(source, filter_model, string_filter_mode)

    row_count: int | None = None
    if with_count:
        row_count = int(lf.select(pl.len()).collect().item())

    page_df = lf.slice(offset, limit).collect().with_row_index("__row_id__", offset=offset)
    return GridPage(rows=_dataframe_to_dicts(page_df), row_count=row_count)


def value_options(
    source: GridSource,
    filter_model: dict[str, Any],
    field: str,
    max_unique: int,
    string_filter_mode: str = "case_insensitive",
) -> list[str]:
    """Return sorted distinct values for *field*, or ``[]`` if too high-cardinality.

    Uses Python's ``sorted`` rather than ``Series.sort()`` only because the values are
    already a small Python list by then — not for safety reasons; a spawned worker can
    use Polars' sort freely.
    """
    import polars as pl

    lf = _filtered(source, filter_model, string_filter_mode)
    values = (
        lf.select(pl.col(field).cast(pl.String))
        .unique()
        .drop_nulls()
        .head(max_unique + 1)
        .collect()
        .to_series()
        .to_list()
    )
    if len(values) > max_unique:
        return []
    return sorted(values)
