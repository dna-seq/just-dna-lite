# Upstream ledger: polars-bio

Kept by the correspondence seat (`docs/seats/CORRESPONDENCE.md`).

- **Publishes:** PyPI
- **What we use:** VCF reading and writing
- **Read mark:** 0.38.0, read 2026-11-19.
- **Last checked:** 2026-11-19 (release watcher baseline)

## Entries

- **Waiting upstream:** a hardcoded 512 MB `max_companion_bytes` cap refuses the PGS Catalog `.pvar.zst` (polars-bio#453); just-prs stays on `pgenlib` meanwhile.

### 0.37.0 to 0.38.0 (read 2026-11-19)

Taken in da6311b's `uv sync --upgrade` on `main`; the floor stays >=0.37.0. 0.38.0 caps `polars<2.2`, so a polars 2.2 waits for polars-bio. polars-bio#453 (the PGEN companion cap) is still open. Verdict: **done, release notes not read**.
