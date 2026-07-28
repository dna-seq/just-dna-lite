# The Polars sort deadlock is a `fork()` bug, not a Granian bug

Status: root cause confirmed by isolated and end-to-end reproduction.
Supersedes the diagnosis in `granian-polars-sort-deadlock.md`.

## Symptom

Under production fullstack, sorting a DataGrid column silently wedges the server:

- process alive, port still accepting TCP, console still says `App running at…`
- no HTTP responses at all — pages, WebSocket events, health probes
- **no Python traceback**, and **SIGTERM does nothing**; only SIGKILL clears it
- the same sort is fine under the dev server

## Root cause

Polars' Rayon thread pool is a `Lazy` — it is created on the **first Polars
operation**, not at import. After `fork()`, the child inherits the pool's latches
and mutexes but **none of its worker threads**. The first parallel operation in the
child parks forever waiting on a worker that does not exist.

It parks with the GIL released, so Python-level signal handlers never get to run.
That is why there is no traceback and why SIGTERM is ignored — we confirmed even
`SIGALRM` with a handler installed cannot interrupt it.

You can see the pool appear. Thread names in `/proc/self/task/*/comm`:

```
after `import polars`:  jemalloc_bg_thd, polars-ooc-clea, python
after the first sort:   polars-0 … polars-15, tokio-rt-worker ×16, …
```

`polars-<n>` are the Rayon workers. They are invisible to Python's `threading`
module — Rust creates them and never registers them with the interpreter — which is
exactly why this hazard is so easy to ship.

### Isolated reproduction

One interpreter, repeated forks:

| Sequence | Child `sort()` |
|---|---|
| `import polars` → `fork()` | ok |
| `import polars` → **one Polars op in the parent** → `fork()` | **hangs; needs SIGKILL** |
| `POLARS_MAX_THREADS=1` → Polars op in parent → `fork()` | **hangs** |
| `POLARS_MAX_THREADS=4` / `=16` → Polars op in parent → `fork()` | **hangs** |
| `spawn` child instead of fork, warm parent pool | ok |

Note the third row: **capping Polars threads does not help, not even at 1.** That single
Rayon worker is still lost to the fork, so the child still parks. This is the intuitive
mitigation and it is ineffective — see the corrections section.

```python
import os, time
import polars as pl

pl.DataFrame({"a": [3, 1, 2]}).lazy().sort("a").collect()   # warm Rayon; comment out -> no hang

pid = os.fork()
if pid == 0:
    pl.DataFrame({"a": list(range(300_000))[::-1]}).lazy().sort("a").slice(0, 3).collect()
    os._exit(0)                                              # never reached
deadline = time.time() + 6
while time.time() < deadline:
    if os.waitpid(pid, os.WNOHANG)[0]:
        print("child finished"); break
    time.sleep(0.1)
else:
    os.kill(pid, 9); print("child HUNG — SIGKILL required")
```

### End-to-end reproduction, in Granian

Trivial ASGI app whose handler sorts 200k rows, `workers=1`, Rayon warmed in the
parent before `Server.serve()`:

| `multiprocessing` start method | Result |
|---|---|
| `fork` | worker starts, logs `Started worker-1`, **HTTP never responds** |
| `spawn` | `sorted-ok` |

The wedge is entirely explained by the start method. Granian is not implicated
beyond being the thing that forks.

## Why it only showed up in production

Both production server paths fork *after* the app has been imported:

- **`gunicorn --preload`** — Reflex's `should_use_granian()` is a `find_spec`
  heuristic: when both `uvicorn` and `gunicorn` are importable it silently prefers
  `gunicorn --preload --worker-class uvicorn.workers.UvicornH11Worker`. `--preload`
  imports the app in the master, then forks. Both packages arrive transitively, so
  which server you get flips with unrelated dependency changes.
- **Granian** — `granian/server/__init__.py` selects `MPServer` on GIL builds, which
  forks via `multiprocessing` (start method `fork` on Linux). Worse, Reflex's
  `_run_prod` runs `_compile_app()` in that *same* process first, so the entire app
  plus compile pass is warm pre-fork.

Dev mode does not fork a warm interpreter, so it never trips.

There is no upside being paid for here: `_get_backend_workers()` returns **1**
whenever Redis is absent, so the fork produces exactly one worker. The whole
deadlock class was bought for zero concurrency.

## Why nobody saw a warning

CPython *does* warn — `DeprecationWarning: This process is multi-threaded, use of
fork() may lead to deadlocks in the child`. The default filters are:

```
('default', None, DeprecationWarning, '__main__', 0)
('ignore',  None, DeprecationWarning, None, 0)
```

The fork happens inside `multiprocessing/popen_fork.py` or `gunicorn/arbiter.py` —
neither is `__main__` — so the only filter that would display it never matches and
the blanket `ignore` swallows it. Nothing was suppressed deliberately; the stdlib
default hides it.

## Corrections to the earlier write-up

Four claims in `granian-polars-sort-deadlock.md` do not hold up, and two of the three
shipped mitigations are inert:

1. **"Polars' sort deadlocks on the Granian ASGI worker thread."** The thread is not
   the problem; the `fork` is. The same sort on the same thread of a *spawned* worker
   is fine.
2. **The one-worker `ThreadPoolExecutor` prevents nothing.** Rayon's pool is
   process-global. Calling into it from a different thread of the same poisoned
   process changes nothing.
3. **`POLARS_MAX_THREADS=1` prevents nothing either.** Measured at 1, 4 and 16 threads:
   the child hangs every time. Even a single-worker pool loses that worker to the fork.
   This one is worth flagging loudly, because it reads like a mitigation and is not one.
4. **"Dev vs prod differ in event-loop/process layout."** They differ in whether a
   warm interpreter gets forked. That is the whole difference.

So of the three fixes shipped in the sibling project, **only the Python `list.sort`
actually does anything** — it never touches Rayon. The other two are inert. Anyone
relying on the thread cap for protection does not have it.

That also means the working fix carries the whole load, and it has a real cost: it
replaced an O(page) query with an O(rows) materialization plus a Python-level sort of
every row, on the request thread. It trades a deadlock for a scalability cliff.

## The fix

### 1. Never fork a warm native runtime

`webui/src/webui/forksafety.py`, applied at the top of `serve()` before reflex is
imported:

- `pin_asgi_server()` — pin `REFLEX_USE_GRANIAN=true` so the server choice cannot
  flip with transitive dependencies.
- `enforce_spawn_start_method()` — `multiprocessing.set_start_method("spawn", force=True)`.
  Granian honours `multiprocessing.get_start_method()` and already enables connection
  pickling for the socket handoff, so spawn is supported.
- `unmute_fork_warning()` — restore visibility of the warning described above.
- `install_fork_tripwire()` — `os.register_at_fork` hooks that snapshot live native
  pools in the parent and, in the child, write a loud banner naming them. A future
  fork-after-Polars becomes a log line rather than a silent wedge.

**Spawn requires a `__main__`-guarded entry point.** Spawned children re-import
`__main__`; without a guard, multiprocessing raises the `freeze_support()`
RuntimeError and the worker dies at startup. uv's generated console scripts
(`.venv/bin/serve`) have the guard, so `uv run serve` is fine — but anything invoked
as a bare top-level script is not.

Spawned children are fresh interpreters that build their own Rayon and Tokio pools, so
full Polars parallelism is available in them with no thread capping anywhere.

### 2. Keep heavy work out of the ASGI process

Fork-safety stops the deadlock; it does not stop one grid click from monopolising the
single ASGI worker. All Polars / DuckDB / polars-bio / Dagster work is submitted to a
spawn-context compute tier (`webui/src/webui/compute/`), so the event loop only ever
marshals arguments and results. A `spawn` context is load-bearing: a fork-context
`ProcessPoolExecutor` would inherit the very poison we are avoiding.

### 3. Bounded grid pages: materialize once, paginate cheap

`lf.sort(...).slice(offset, n).collect()` is O(rows) on **every** click. Polars does
not turn it into a bounded top-k in general — `explain()` shows a dynamic-predicate
pushdown for single-key sorts only; multi-key sorts materialize a full sort.

So on a sort/filter change the compute child streams the sorted frame to a temp
parquet once, and every page after that is a cheap slice off that artifact. Measured
on 2M rows:

```
scan_parquet(src).sort(k).sink_parquet(tmp)        0.1 s   (streaming, spills to disk)
scan_parquet(tmp).slice(1_500_000, 100).collect()  3 ms
```

That is both fork-safe and strictly faster than the current behaviour.

### 4. Liveness backstop

A wedged worker provably ignores SIGTERM, so `/_health` on the same ASGI app plus an
external watchdog that SIGKILLs the process group after repeated timeouts stays — as
a backstop for unknown future wedges, not as the fix.

## Verifying

```bash
uv run serve
# expect on startup:
#   Process model: server=granian (pinned), mp_start_method=spawn, native_pools_live=...
curl -s http://127.0.0.1:3000/_health     # {"status":"ok"}
```

Then sort a column on a whole-genome grid and scroll a few pages. Expect `/_health`
to keep answering *during* the sort, the first sort to log a materialize timing,
later pages to log single-digit milliseconds, and the ASGI process's RSS to stay flat
while a child does the work.

## Applying this to the sibling project

1. Set the start method to `spawn` before the server starts, and check the entry
   point is `__main__`-guarded. That alone removes the deadlock.
2. Drop `POLARS_MAX_THREADS=1`. It is not protecting anything (row 3 of the table),
   and it costs all Polars parallelism process-wide.
3. Consider reverting the Python `list.sort` to a Polars query, ideally
   materialize-once/paginate-cheap; see
   `docs/reviews/reflex-mui-datagrid-fork-safety-proposal.md`.
4. Keep the `/_health` watchdog.
