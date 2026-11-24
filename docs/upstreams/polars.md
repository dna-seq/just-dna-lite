# Upstream ledger: polars

Kept by the correspondence seat (`docs/seats/CORRESPONDENCE.md`).

- **Publishes:** PyPI
- **What we use:** every table; the streaming engine's row order rules are in `CLAUDE.md`
- **Read mark:** 2.2.0, read 2026-11-25.
- **Last checked:** 2026-11-25 (release watcher)

## Entries

### 2.2.0 (read 2026-11-25)

Published 2026-11-24T18:15Z. Breaking: `str.find(_many)` returns character offsets, scalar function arguments are
required at plan time, SQL `DELETE` changes the registered table. None of `str.find`, `bin.find` or `SQLContext`
appears in our code. **Blocked:** polars-bio 0.38.0 (the latest) requires `polars<2.2`, so the lock cannot move;
retried when polars-bio lifts its cap. Waited for, never rerouted.
