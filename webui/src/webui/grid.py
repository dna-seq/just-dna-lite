"""Fork-safe, O(page) server-side grid handlers.

``LazyFrameGridMixin`` from ``reflex-mui-datagrid`` builds its pages as
``filter -> sort -> slice -> collect()`` inside **sync generator** event handlers.
That has two problems in production:

1. A Reflex generator handler holds the state lock for its whole execution — ``yield``
   pushes deltas but does not release the lock — so every queued event waits for the
   sort.  With a single ASGI worker that means the whole app stops.
2. ``lf.sort(...).slice(offset, n)`` is O(rows) on **every** click.  Polars only pushes
   a dynamic predicate down for single-key sorts; multi-key sorts materialize a full
   sort.  Scroll-append re-sorts per chunk.

``SafeGridMixin`` overrides those handlers with ``@rx.event(background=True)``
equivalents that hold the state lock only to read inputs and publish results, and that
do their Polars work in a spawned compute worker (``webui.compute``).  Sorted and
filtered views are materialized **once** to a parquet artifact; every page after that
is a cheap slice off the artifact.

Grids whose data is already a small in-memory frame (the PRS grids) register no source
and fall through to the library's in-process path, which is correct and fast for them.

Mix in *before* ``LazyFrameGridMixin`` so these overrides win:

    class MyState(SafeGridMixin, LazyFrameGridMixin, rx.State): ...
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

import reflex as rx
from just_dna_pipelines.annotation.resources import get_cache_dir
from reflex_mui_datagrid.lazyframe_grid import _DEFAULT_CHUNK_SIZE, _get_cache

from webui.compute.pool import ComputeTimeout, run_in_compute
from webui.compute.tasks import GridSource, materialize_sorted, read_page, value_options

# Bounded LRU of materialized views: {key: (path, row_count)}.
_MAX_ARTIFACTS = 8
_artifacts: OrderedDict[str, tuple[Path, int]] = OrderedDict()


def artifact_root() -> Path:
    """Directory holding materialized sorted views.

    Resolved per call, not at import: ``get_cache_dir()`` reads
    ``JUST_DNA_PIPELINES_CACHE_DIR`` from ``.env``, and caching the value at import time
    would bind whatever was set before ``load_env()`` ran.  That matters here —
    deployments put the cache on a large volume, while a whole-genome sorted artifact is
    easily a gigabyte and the root filesystem may not have room for it.
    """
    return get_cache_dir() / "grid_sort_artifacts"


def _artifact_key(cache_id: str, filter_model: dict[str, Any], sort_model: list[dict[str, Any]]) -> str:
    """Stable key for one (grid, filter, sort) view."""
    return json.dumps(
        {"cache": cache_id, "filter": filter_model or {}, "sort": sort_model or []},
        sort_keys=True,
        default=str,
    )


def _artifact_dir(cache_id: str, key: str) -> Path:
    """Deterministic directory for one view (readable, and stable across restarts)."""
    digest = hashlib.sha1(key.encode()).hexdigest()[:12]  # noqa: S324 - cache key, not security
    safe_cache_id = re.sub(r"[^A-Za-z0-9_.-]", "_", cache_id)[:40]
    return artifact_root() / f"{safe_cache_id}-{digest}"


def _evict_artifacts_over_limit() -> None:
    while len(_artifacts) > _MAX_ARTIFACTS:
        _key, (path, _rows) = _artifacts.popitem(last=False)
        shutil.rmtree(path.parent, ignore_errors=True)


def clear_grid_artifacts() -> None:
    """Remove every materialized view and forget the LRU.

    Called from the app lifespan on both ends: on startup because a SIGKILLed previous
    run (which is exactly what the watchdog does) leaves artifacts with no owner, and on
    shutdown to avoid leaving gigabytes of sorted parquet behind.
    """
    _artifacts.clear()
    shutil.rmtree(artifact_root(), ignore_errors=True)


async def resolve_view_source(
    source: GridSource,
    cache_id: str,
    filter_model: dict[str, Any],
    sort_model: list[dict[str, Any]],
) -> tuple[GridSource, dict[str, Any], int | None]:
    """Resolve where pages for this view should be read from.

    Unsorted grids read the original file with the filter applied.  Sorted grids read a
    materialized artifact instead, so paging never re-sorts: the sort is paid once, then
    every page is a slice.  Artifacts are reused across scroll chunks and kept in a
    bounded LRU.

    Module-level rather than a method so it is testable without a live Reflex state.

    Returns:
        ``(source_to_read, filter_to_apply, known_row_count)``.  For an artifact the
        filter is already baked in, so the returned filter is empty and the row count is
        known without a second query.
    """
    if not sort_model:
        return source, filter_model, None

    key = _artifact_key(cache_id, filter_model, sort_model)
    cached = _artifacts.get(key)
    if cached is not None:
        _artifacts.move_to_end(key)
        path, rows = cached
        if path.exists():
            return GridSource(reader="scan_file", path=str(path)), {}, rows
        del _artifacts[key]

    out_dir = _artifact_dir(cache_id, key)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "sorted.parquet"

    t0 = time.perf_counter()
    rows = await run_in_compute(materialize_sorted, source, filter_model, sort_model, str(out_path))
    print(
        f"[SafeGrid] materialized sorted view: {rows:,} rows "
        f"({(time.perf_counter() - t0) * 1000:.0f}ms) -> {out_path.name}",
        flush=True,
    )

    _artifacts[key] = (out_path, rows)
    _artifacts.move_to_end(key)
    _evict_artifacts_over_limit()
    return GridSource(reader="scan_file", path=str(out_path)), {}, rows


class SafeGridMixin(rx.State, mixin=True):
    """Background-event grid handlers backed by the out-of-process compute tier."""

    # Source descriptor for the grid's data.  Empty reader => no out-of-process path
    # available; fall back to the library's in-process handlers.
    _grid_reader: str = ""
    _grid_path: str = ""

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_grid_source(self, reader: str, path: str | Path) -> None:
        """Declare how a compute worker can reopen this grid's data.

        Call right after ``set_lazyframe``.  A descriptor is passed rather than the
        LazyFrame itself because ``LazyFrame.serialize()`` fails for
        ``polars_bio.scan_vcf`` plans (they embed a Python IO source and need
        cloudpickle), and because a path survives worker recycling.

        Args:
            reader: ``"scan_file"`` for parquet/CSV/VCF handled by
                ``reflex_mui_datagrid.scan_file``, or ``"prepare_vcf"`` for the
                pipelines' normalized-VCF reader.
            path: The file the worker should open.
        """
        self._grid_reader = reader
        self._grid_path = str(path)

    def clear_grid_source(self) -> None:
        """Forget the source, sending this grid back to the in-process path."""
        self._grid_reader = ""
        self._grid_path = ""

    @property
    def _grid_source(self) -> GridSource | None:
        if not self._grid_reader or not self._grid_path:
            return None
        return GridSource(reader=self._grid_reader, path=self._grid_path)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Page production
    # ------------------------------------------------------------------

    async def _publish_page(self, *, append: bool, with_count: bool) -> None:
        """Compute one page out-of-process and publish it to the frontend.

        Holds the state lock only to read inputs and to write results.
        """
        async with self:
            source = self._grid_source
            cache_id = self._lf_grid_cache_id
            filter_model = dict(self._lf_grid_filter or {})
            sort_model = list(self._lf_grid_sort or [])
            pagination = dict(self.lf_grid_pagination_model)
            existing_rows = list(self.lf_grid_rows) if append else []

        if source is None or not cache_id:
            # In-memory grid: the library's synchronous path is correct and cheap.
            async with self:
                self._refresh_lf_grid_page(append=append, refresh_row_count=with_count)
                self._update_filter_debug()
                self.lf_grid_loading = False
            return

        page_size = int(pagination.get("pageSize", _DEFAULT_CHUNK_SIZE))
        offset = int(pagination.get("page", 0)) * page_size

        t0 = time.perf_counter()
        try:
            view, view_filter, known_rows = await resolve_view_source(
                source, cache_id, filter_model, sort_model
            )
            page = await run_in_compute(
                read_page, view, view_filter, offset, page_size, with_count and known_rows is None
            )
        except ComputeTimeout as exc:
            async with self:
                self.lf_grid_loading = False
                self.lf_grid_stats = f"Query exceeded its time budget: {exc}"
            return
        except Exception as exc:
            async with self:
                self.lf_grid_loading = False
                self.lf_grid_stats = f"Query failed: {type(exc).__name__}: {exc}"
            return

        elapsed_ms = (time.perf_counter() - t0) * 1000
        row_count = known_rows if known_rows is not None else page.row_count

        async with self:
            self.lf_grid_rows = existing_rows + page.rows if append else page.rows
            if row_count is not None:
                self.lf_grid_row_count = row_count
                _get_cache(cache_id).total_rows = row_count
            loaded = len(self.lf_grid_rows)
            self.lf_grid_stats = (
                f"offset={offset:,}  +{len(page.rows)} rows  "
                f"loaded={loaded:,} / {self.lf_grid_row_count:,}  "
                f"{elapsed_ms:.0f}ms  ({'append' if append else 'replace'})"
            )
            self._update_filter_debug()
            self.lf_grid_loading = False

        print(
            f"[SafeGrid] page: offset={offset}, +{len(page.rows)} rows, "
            f"{elapsed_ms:.0f}ms, {'append' if append else 'replace'}",
            flush=True,
        )

    # ------------------------------------------------------------------
    # Overridden event handlers
    # ------------------------------------------------------------------

    @rx.event(background=True)
    async def handle_lf_grid_sort(self, sort_model: list[dict[str, Any]]) -> None:
        """Apply a new sort model, resetting the scroll stream to the top."""
        async with self:
            self.lf_grid_loading = True
            self.lf_grid_stats = "Sorting..."
            self._lf_grid_sort = sort_model
            page_size = self.lf_grid_pagination_model.get("pageSize", _DEFAULT_CHUNK_SIZE)
            self.lf_grid_pagination_model = {"page": 0, "pageSize": page_size}

        await self._publish_page(append=False, with_count=True)

    @rx.event(background=True)
    async def handle_lf_grid_filter(self, filter_model: dict[str, Any]) -> None:
        """Merge an incoming filter item and reload from the top.

        Filter-model merging, filterable-column screening and value-option upgrades stay
        on the library's helpers — they are cheap bookkeeping over the cached schema.
        Only the query itself moves off-process.
        """
        from reflex_mui_datagrid.lazyframe_grid import _filter_model_for_filterable_columns

        async with self:
            self.lf_grid_loading = True
            self.lf_grid_stats = "Filtering..."

            raw_items = filter_model.get("items", [])
            had_incoming_items = isinstance(raw_items, list) and bool(raw_items)

            cache_id = self._lf_grid_cache_id
            if cache_id:
                filter_model = _filter_model_for_filterable_columns(
                    filter_model, _get_cache(cache_id)
                )

            self.lf_grid_filter_model = filter_model
            if had_incoming_items and not filter_model.get("items"):
                self.lf_grid_loading = False
                return

            self._lf_grid_filter = self._merge_filter_model(filter_model)
            page_size = self.lf_grid_pagination_model.get("pageSize", _DEFAULT_CHUNK_SIZE)
            self.lf_grid_pagination_model = {"page": 0, "pageSize": page_size}

        # Outside the lock: a unique() over a whole-genome column is a real query.
        await self._ensure_value_options(filter_model)
        await self._publish_page(append=False, with_count=True)

    @rx.event(background=True)
    async def handle_lf_grid_scroll_end(self, _params: dict[str, Any]) -> None:
        """Load the next chunk when the virtual scroller nears the bottom."""
        async with self:
            if self.lf_grid_loading:
                return
            page = self.lf_grid_pagination_model.get("page", 0)
            page_size = self.lf_grid_pagination_model.get("pageSize", _DEFAULT_CHUNK_SIZE)
            next_offset = (page + 1) * page_size
            if next_offset >= self.lf_grid_row_count:
                return
            self.lf_grid_loading = True
            self.lf_grid_stats = f"Loading rows {next_offset:,}..."
            self.lf_grid_pagination_model = {"page": page + 1, "pageSize": page_size}

        await self._publish_page(append=True, with_count=False)

    @rx.event(background=True)
    async def clear_lf_grid_filters(self) -> None:
        """Clear accumulated server-side filters and the MUI filter UI."""
        async with self:
            self.lf_grid_loading = True
            self.lf_grid_stats = "Clearing filters..."
            self._lf_grid_filter = {}
            self.lf_grid_filter_model = {"items": []}
            page_size = self.lf_grid_pagination_model.get("pageSize", _DEFAULT_CHUNK_SIZE)
            self.lf_grid_pagination_model = {"page": 0, "pageSize": page_size}

        await self._publish_page(append=False, with_count=True)

    @rx.event(background=True)
    async def handle_lf_grid_request_value_options(self, field: str) -> None:
        """Compute one column's filter dropdown values out-of-process."""
        await self._ensure_value_options({"items": [{"field": field}]})

    # ------------------------------------------------------------------
    # Value options
    # ------------------------------------------------------------------

    async def _ensure_value_options(self, filter_model: dict[str, Any]) -> None:
        """Upgrade referenced columns to ``singleSelect`` dropdowns.

        Call **without** the state lock held: a ``unique()`` over a whole-genome column
        is a real query, and the whole point is not to hold the lock across it.  Uses a
        compute worker when a source is registered, and the library's in-process helper
        otherwise (in-memory grids, where it is trivial).
        """
        from reflex_mui_datagrid.lazyframe_grid import (
            _filter_model_for_filterable_columns,
            _resolve_field_name,
        )

        async with self:
            source = self._grid_source
            cache_id = self._lf_grid_cache_id
            accumulated_filter = dict(self._lf_grid_filter or {})
            if source is None or not cache_id:
                self._ensure_value_options_for_filter(filter_model)
                return

        cache = _get_cache(cache_id)
        if cache.schema is None:
            return

        screened = _filter_model_for_filterable_columns(filter_model, cache)
        columns_updated = False
        for item in screened.get("items", []):
            raw_field = item.get("field")
            if not raw_field:
                continue
            field = _resolve_field_name(str(raw_field), cache.schema)
            if not field or field in cache._value_options_cache:
                continue
            try:
                options = await run_in_compute(
                    value_options,
                    source,
                    accumulated_filter,
                    field,
                    cache.value_options_max_unique,
                )
            except Exception as exc:
                # Cache the miss so a failing column is not retried on every click.
                print(f"[SafeGrid] value options for {field!r} failed: {exc}", flush=True)
                cache._value_options_cache[field] = []
                continue

            cache._value_options_cache[field] = options
            if not options:
                continue
            for i, col_def in enumerate(cache.col_defs):
                if col_def.get("field") == field:
                    cache.col_defs[i] = {
                        **col_def,
                        "type": "singleSelect",
                        "valueOptions": options,
                    }
                    columns_updated = True
                    break

        if columns_updated:
            async with self:
                self.lf_grid_columns = cache.col_defs
