# Upstream ledger: just-dna-enricher

Kept by the correspondence seat (`docs/seats/CORRESPONDENCE.md`).

- **Publishes:** PyPI; https://github.com/dna-seq/just-dna-compiler
- **What we use:** enrichment, the DuckDB Ensembl resolver and the snapshot lanes that own the caches
- **Read mark:** 0.8.10, read 2026-11-26.
- **Last checked:** 2026-11-26 (release watcher, 0.8.10)

## Entries

### 0.8.10 (read 2026-11-26)

Released with the compiler; see `just-dna-compiler.md`, 0.8.10. Bump on `bump/just-dna-format` (a207450).

- **Waiting upstream:** the Ensembl snapshot's `groups/` sidecars (consequence, ClinVar, frequencies) are not pulled, so our Ensembl join adds rsIDs only. Reported as S150, taken as RM437, planned for 0.9. Roadmap RM5 waits on it.

### 0.8.6 to 0.8.9 (read 2026-11-19)

Adopted in da6311b, which also fixed `clinvar_panel` for the drafter's coordinate-row identity. RM440 adds a warning on `--rederive`; RM442 changes the AlphaGenome licence text; RM444 and RM447 reword messages. **RM445 (0.8.8):** check the pull records before a cache pull. da6311b found only `ensembl_variations` without `release_sha256`, and that lane publishes no `release.json`, so nothing was mislabelled. Still waiting: the `groups/` sidecars (S150, RM437, due 0.9). Verdict: **done**.
