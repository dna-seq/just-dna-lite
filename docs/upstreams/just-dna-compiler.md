# Upstream ledger: just-dna-compiler

Kept by the correspondence seat (`docs/seats/CORRESPONDENCE.md`).

- **Publishes:** PyPI; https://github.com/dna-seq/just-dna-compiler
- **What we use:** `validate_spec`, `compile_module`, `reverse_module`; the module build under `v1_port/`
- **Read mark:** 0.8.9, read 2026-11-19.
- **Last checked:** 2026-11-19 (release watcher baseline)

## Entries

### 0.8.6 to 0.8.9 (read 2026-11-19)

Adopted in da6311b. What reaches us: **RM449** (an rsID row's indel genotype now goes on one event, not both). The release names two published modules that carry the wrong claim, `superhuman@2.4.1` (`rs766212849`) and `thrombophilia@2.0.1` (`rs1572088853`), and asks for a recompile of modules RM449 reaches. Our local v1_port builds are still compiler 0.7.2 (da6311b), so the recompile comes with the next rebuild. Republishing is the maintainer's call. **RM453** (known issue, fix due in 0.8.10): an offline re-derivation of `pathogenic_clinvar` leaves `rs80356821` unplaced. Re-derive mirrored indel sites online until then. RM451: `resolution_loci` is now `[]` where it was null. Verdict: **adopted; recompile open for the lead**.
