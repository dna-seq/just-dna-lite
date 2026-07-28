"""Out-of-process compute tier for the web UI.

Nothing that uses Polars, DuckDB, polars-bio or Dagster runs in the ASGI process.
The event loop marshals arguments out and results back; everything else happens in a
**spawned** child.  Two reasons, both load-bearing:

1. **Fork safety.**  A child spawned from a fresh interpreter builds its own Rayon and
   Tokio pools.  A *forked* child inherits pools with no worker threads and parks
   forever on the first parallel call — no traceback, SIGTERM ignored.  See
   ``webui.forksafety`` and ``docs/GRANIAN_POLARS_FORK_DEADLOCK.md``.
2. **Liveness.**  Production runs a single ASGI worker (``_get_backend_workers()``
   returns 1 without Redis), so any multi-second call on the event loop stops every
   request, WebSocket event and health probe in the process.

Modules:

* ``pool`` — short queries (grid pages, previews) on a spawn-context
  ``ProcessPoolExecutor``: ``run_in_compute``, ``start_pool``, ``stop_pool``,
  ``ComputeTimeout``.
* ``jobs`` — Dagster runs, one spawned child each so they stay individually killable:
  ``submit_job``, ``await_job``, ``forget_job``, ``cancel_job``, ``active_jobs``,
  ``kill_all_jobs``.
* ``tasks`` — the picklable callables children execute: ``GridSource``,
  ``materialize_sorted``, ``read_page``, ``value_options``.

Import from those modules directly rather than from this package, so it stays obvious
where each name lives.
"""
