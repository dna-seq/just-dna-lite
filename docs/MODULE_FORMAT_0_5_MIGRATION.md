# Annotation modules on just-dna-format 0.5

State of the module compiler after moving to `just-dna-format` 0.5.0 / `just-dna-compiler` 0.5.1 /
`just-dna-enricher` 0.5.1, measured on 2026-08-09. **Nothing here is a compiler defect.** Every
published module still reverses, validates and recompiles cleanly; what changed is the *shape* of
what the compiler emits, and the published modules on HuggingFace predate that shape.

This file exists so the next person does not re-derive the numbers. The raw measurements are
reproducible with the script described in [Reproducing](#reproducing).

## Test status

The suite reports **29 failures** on a stock checkout (222 passed, 1 skipped). They fall into three
groups, and only the first two are actionable:

| group | count | cause | status |
|---|---|---|---|
| `TestResolver` | 4 | incomplete local Ensembl cache — not code | fixed by configuration, see below |
| `test_agent_smoke` | 1 | module creator wrote a non-string `version` | fixed in code |
| `test_module_roundtrip` | 15 | 0.5 emits more columns than the published modules carry | **documented here, not fixed** |
| `test_module_compiler` (rest) | 9 | contract changes listed below | **documented here, not fixed** |

The last two groups are a *republishing* task, not a bug hunt: they cannot pass until the modules on
HuggingFace are rebuilt under 0.5 and the assertions are re-baselined against the new shape.

## The environment trap (fixed)

`get_default_ensembl_cache_dir()` read `JUST_DNA_PIPELINES_CACHE_DIR` without loading `.env` first.
Under `uv run start` that worked, because the app calls `load_env()` early. Under pytest — or any
direct library use — nothing loaded `.env`, so the helper silently fell back to the platform user
cache, created it, and re-downloaded Ensembl parquet to a different disk than the configured one.
`resources.py` now calls `load_env()` at import.

That fallback is why `TestResolver` failed: it left a partial cache with only 6 chromosomes, and the
two rsIDs that failed (`rs3892097` on chr22, `rs35599367` on chr7) were exactly the ones whose
chromosome was missing, while `rs4244285` on chr10 resolved fine. With a complete cache all
**13 `TestResolver` tests pass**.

Check before blaming the resolver — a complete GRCh38 cache is 25 parquet files (chr1–22, X, Y, MT):

```bash
ls "$JUST_DNA_PIPELINES_CACHE_DIR/ensembl_variations/data"/*.parquet | wc -l   # want 25
```

A partial cache does not announce itself: resolution just returns rows with `chrom=None` for the
chromosomes it lacks, so a module compiles "successfully" with unresolved coordinates.

## What 0.5 changes about a compiled module

Measured by round-tripping every published module: download the HF artifact → `reverse_module` →
`validate_spec` → `compile_module` → diff against the original.

**Every module round-trips without error.** `validate_spec` returns valid, `compile_module` returns
success, and **no column is ever dropped** — the change is purely additive.

### Columns

| table | published | 0.5 | added |
|---|---|---|---|
| `weights` | 19–20 | **37** | +17 (+18 where `negatives` is used) |
| `annotations` | 5 | **8** | +3 |
| `studies` | 7 | **19** | +12 |

- **weights** gains `variant_key`, `authored_ident`, `acmg_sf`, `actionability`, `clin_sig`,
  `direction`, `effect_allele`, `effect_measure`, `effect_size`, `stat_significance`,
  `trait_efo_id`, `flags`, `phased`, `requires_callable`, `callable_from`, `min_quality`,
  `quality_from` (and `negatives` where the module uses it).
- **annotations** gains `variant_key`, `conclusion`, `negatives`.
- **studies** gains `chrom`, `start`, `ref`, `doi`, `effect_measure`, `effect_size`,
  `stat_significance`, `trait_efo_id`, `p_value_num`, `neg_log10_p`, `provenance_quote`,
  `provenance_regex`.

### Rows

`weights` and `studies` row counts are **unchanged for every module**. Only `annotations` grows, and
only where a variant carries multiple genotypes — annotations are now keyed by `variant_key` rather
than collapsed per rsID:

| module | annotations rows | Δ |
|---|---|---|
| lipidmetabolism | 15 → 41 | +26 |
| vo2max | 13 → 28 | +15 |
| coronary | 27 → 77 | +50 |
| superhuman | 101 → 101 | 0 |
| longevitymap | 528 → 528 | 0 |

This is what `TestCompilation::test_mthfr_annotations_content` and
`test_cyp_annotations_deduplication` see when they assert `row_count == n_unique(rsid)` (24 vs 8,
21 vs 7). The assertion encodes the old per-rsID collapse.

### `variant_key` is a GA4GH VRS identifier

`VariantRow.variant_key` used to be the positional string `chrom:start:ref`. It is now a VRS
identifier, and it is frozen at load so the resolver can no longer re-key a row:

```
10:94781859:G   →   ga4gh:VA.r5fVsRyrz858RkwE0fe7t60-1rc-9gMo
```

`TestVariantRow::test_position_only_valid` asserts the old spelling.

### Validation message

Since 0.4 a module may lead with a table other than `variants.csv`, so the missing-table error is no
longer about that one file:

```
old: variants.csv not found
new: module has no recognized table: add variants.csv or a 0.4 table
     (e.g. pharm_variants.csv, diplotypes.csv, pgs.csv).
```

`TestValidation::test_missing_variants` matches on the old text.

### Resolution is inject-only

`compile_module(spec_dir, out_dir)` does **not** provision an Ensembl reference. Called bare it
compiles successfully with `chrom=None`; given a cache it resolves:

```
bare (no cache injected)      success=True  chrom=None
with ensembl_cache injected   success=True  chrom='10'
```

That is the documented design (`register_custom_module` and the pipelines `resolve_variants` wrapper
auto-provision and inject; the bare re-export and `pipelines module compile` stay inject-only). The
five `TestCompileWithResolution` failures all call the bare form and then assert coordinates were
filled in.

### Deprecation to plan for

Injecting a DuckDB cache is itself on the way out:

> `compile_module(ensembl_cache=...)` / in-compiler DuckDB resolution is deprecated and will be
> removed at 1.0. Produce a `resolution.csv` (e.g. `just-dna-enricher enrich`) and the compiler
> consumes it with no reference and no network.

`module_compiler/resolver.py` and `register_custom_module` currently inject `ensembl_cache`, so both
sit on that path. The replacement is the enricher producing a `resolution.csv` that the compiler
consumes — no reference, no network at compile time.

## What migration requires

1. **Rebuild and republish the modules** on `just-dna-seq/annotators` under 0.5. All five round-trip
   cleanly today, so this is a rebuild rather than a data-repair job. Note it moves every module's
   `artifact.digest`.
2. **Re-baseline the assertions** in `test_module_roundtrip.py` (column sets, annotation row counts)
   and `test_module_compiler.py` (`variant_key` spelling, the dedup counts, the validation message).
3. **Inject a cache in `TestCompileWithResolution`**, or move those tests onto the `resolution.csv`
   path so they survive the 1.0 removal.
4. **Migrate off `ensembl_cache=`** before 1.0.

Order matters: (1) before (2), or the new baselines get written against artifacts nobody ships.

## CLI surface (done)

The 0.5 tiers are reachable from `uv run pipelines`; nothing here changes the WebUI yet.

```bash
uv run pipelines enrich  --help        # just-dna-enricher, mounted whole
uv run pipelines module  --help        # validate / compile / reverse / register
uv run pipelines marketplace --help    # catalog client
```

**The offline path, end to end.** `enrich` writes `resolution.csv` beside the spec; `compile` then
consumes it with no reference and no network:

```bash
uv run pipelines enrich enrich data/module_specs/evals/mthfr_nad/ --offline
uv run pipelines module compile data/module_specs/evals/mthfr_nad/ -o data/output/modules/mthfr_nad
# Resolve:   resolution.csv (injected, no network)
```

`pipelines enrich enrich-and-compile <spec> <out>` does both in one step. All three routes —
straight compile with a cache, reverse → recompile, and enrich-and-compile — were verified to
produce the **same `artifact.digest`** on `mthfr_nad`, which is the digest-parity guarantee the
compiler's `resolution` module claims.

New flags, all passed straight through to the library: `module validate --strict --authority-key`;
`module compile --strict --authority-key --compiled-by --ensembl-reference --provenance --logo
--log-file --ba1-threshold`. `--ensembl-cache` is kept and marked deprecated in its own help text.

`module reverse` is new — `reverse_module` had no CLI before. It defaults to `--write-resolution`,
so a reversed spec recompiles offline and byte-identically.

**The partial-cache trap now announces itself.** `compile` reads back `weights.parquet` and reports
rows with no `chrom`:

```
⚠ 24/24 weight rows have no chrom
  They will never match a VCF. Resolve them before publishing:
    uv run pipelines enrich enrich <spec_dir>
```

That is the one failure mode described above that compilation itself reports as success.

## Reproducing

`scripts/audit_module_format.py` walks every module through
download → `reverse_module` → `validate_spec` → `compile_module` → diff, and writes per-module,
per-table row/column deltas plus the full added-column lists:

```bash
uv run python scripts/audit_module_format.py     # -> data/interim/module_audit.json
```

Override the destination with `MODULE_AUDIT_OUT`. Point `JUST_DNA_PIPELINES_CACHE_DIR` at a
**complete** Ensembl cache first, or the resolution numbers will be wrong in the quiet way described
above.
