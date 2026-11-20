# Upstream ledger: dagster

Kept by the correspondence seat (`docs/seats/CORRESPONDENCE.md`).

- **Publishes:** PyPI
- **What we use:** the pipeline; the floor stays at 1.13.28 for the protobuf 7 resolution
- **Read mark:** 1.13.28, the version in `uv.lock` when this ledger was opened on 2026-11-19. Nothing before it is backlog.
- **Last checked:** 2026-11-19 (release watcher baseline)

## Entries

### 1.13.29 and 1.13.30 (read 2026-11-19)

Nothing in them reaches this repository: UI fixes, `dg --help` under typer 0.26+, Python 3.10 dropped
(we run 3.13), Dagster+ only items. **The bump does not resolve.** `dagster-dg-cli` 1.13.29 and 1.13.30
require `typer<0.26`, against our `typer>=0.27.1` (`just-dna-pipelines`, since bcf6ff8), and the dagster
family pins each other `==`, so the whole family stays at 1.13.28. The cap reads as a stopgap: the same
release says it fixed `dg --help` on typer 0.26. Per `CLAUDE.md` a pin that won't resolve is waited for:
the watcher says the next dagster release, and it is tried then. Lowering our typer floor is the lead's
call, not a bump. Verdict: **blocked: upstream typer cap in dagster-dg-cli**.

### 1.13.31 (2026-11-19)

`dagster-dg-cli` 1.13.31 (on PyPI 22:05Z, 23 minutes after `dagster`) still requires `typer<0.26`, so the
bump stays blocked; the family stays at 1.13.28. No release notes on GitHub yet. Tried again at the next
release. A report upstream (dagster-io/dagster: the cap contradicts 1.13.29's "fixed `dg --help` with
typer 0.26 or later") is the maintainer's to post, if wanted; not drafted unless asked. Verdict: **blocked**.
