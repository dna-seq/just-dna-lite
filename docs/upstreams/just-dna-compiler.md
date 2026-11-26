# Upstream ledger: just-dna-compiler

Kept by the correspondence seat (`docs/seats/CORRESPONDENCE.md`).

- **Publishes:** PyPI; https://github.com/dna-seq/just-dna-compiler
- **What we use:** `validate_spec`, `compile_module`, `reverse_module`; the module build under `v1_port/`
- **Read mark:** 0.8.10, read 2026-11-26.
- **Last checked:** 2026-11-26 (release watcher, 0.8.10)

## Entries

### 0.8.10 (read 2026-11-26)

A patch to all three packages, floors between them at `>=0.8.10`. **RM453** (the known issue named at 0.8.9): an rsID row at a mirrored indel site that no second source placed gets both spellings again, as before 0.8.9, instead of no position. **RM456**: `compile_module` no longer raises on Python 3.13 over a `logs/` directory it may list but not search. **RM455**: a pull record that is not UTF-8 reads as unreadable; a `batch_size` below 1 raises `ValueError`; additive names `CacheLane.payload_filename`, `net.check_batch_size`. Format 0.8.10 changes only its release record. Upstream's after-upgrading steps: raise the floors (done on `bump/just-dna-format`, a207450, format contract tests 105 passed); recompile a module 0.8.9 compiled carrying RM449's "neither is filled and the position remains unset" sentence (our v1_port builds are still compiler 0.7.2, so this rides the rebuild already open); no re-derivation needed. Verdict: **bump handed to the lead; recompile stays with the rebuild**.

### 0.8.6 to 0.8.9 (read 2026-11-19)

Adopted in da6311b. What reaches us: **RM449** (an rsID row's indel genotype now goes on one event, not both). The release names two published modules that carry the wrong claim, `superhuman@2.4.1` (`rs766212849`) and `thrombophilia@2.0.1` (`rs1572088853`), and asks for a recompile of modules RM449 reaches. Our local v1_port builds are still compiler 0.7.2 (da6311b), so the recompile comes with the next rebuild. Republishing is the maintainer's call. **RM453** (known issue, fix due in 0.8.10): an offline re-derivation of `pathogenic_clinvar` leaves `rs80356821` unplaced. Re-derive mirrored indel sites online until then. RM451: `resolution_loci` is now `[]` where it was null. Verdict: **adopted; recompile open for the lead**.
