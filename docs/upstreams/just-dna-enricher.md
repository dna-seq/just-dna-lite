# Upstream ledger: just-dna-enricher

Kept by the correspondence seat (`docs/seats/CORRESPONDENCE.md`).

- **Publishes:** PyPI; https://github.com/dna-seq/just-dna-compiler
- **What we use:** enrichment, the DuckDB Ensembl resolver and the snapshot lanes that own the caches
- **Read mark:** 0.8.5, the version in `uv.lock` when this ledger was opened on 2026-11-19. Nothing before it is backlog.
- **Last checked:** 2026-11-19

## Entries

- **Waiting upstream:** the Ensembl snapshot's `groups/` sidecars (consequence, ClinVar, frequencies) are not pulled, so our Ensembl join adds rsIDs only. Reported as S150, taken as RM437, planned for 0.9. Roadmap RM5 waits on it.
