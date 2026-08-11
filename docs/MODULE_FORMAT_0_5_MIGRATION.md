# Annotation modules on just-dna-format 0.5

State of the module compiler after moving to `just-dna-format` 0.5.0 / `just-dna-compiler` 0.5.1 /
`just-dna-enricher` 0.5.1, measured on 2026-08-09. **Nothing here is a compiler defect.** Every
published module still reverses, validates and recompiles cleanly; what changed is the *shape* of
what the compiler emits, and the published modules on HuggingFace predate that shape.

This file exists so the next person does not re-derive the numbers. The raw measurements are
reproducible with the script described in [Reproducing](#reproducing).

## Test status — resolved 2026-08-09

**The suite is green: 276 passed, 9 skipped, 0 failed.** It reported 29 failures when this file was
first written, then 23 after the environment fix; the rest were re-baselined rather than worked
around, because the assertions encoded the *old* shape rather than any invariant:

| group | count | resolution |
|---|---|---|
| `TestResolver` | 4 | configuration — an incomplete Ensembl cache, see below |
| `test_agent_smoke` | 1 | fixed in code (non-string `version`) |
| `test_module_roundtrip` — column equality | 12 | now asserts **no column is dropped** (superset), which is what the round-trip guarantees and what survives the next additive release |
| `test_module_roundtrip` — annotation row counts | 3 | now derived from the compiled weights: `annotations.height == weights.select("variant_key", "conclusion").unique().height` |
| `test_module_compiler` — `variant_key` | 1 | asserts the VRS shape plus the property that motivated it (two alts at one locus get distinct keys) |
| `test_module_compiler` — validation message | 1 | matches "no recognized table", the stable half of the 0.4 wording |
| `TestCompileWithResolution` | 5 | moved onto the enricher path (`enrich` → `resolution.csv` → inject-only compile), so they survive the 1.0 removal of `ensembl_cache=` |

A new file, `tests/test_modules_0_5.py` (36 tests), covers the surfaces this repo added on top: the
ClinVar panel route, the ClinPGx route, the `modules.yaml` merge, and the spec writer's handling of
list-typed and compiler-managed columns. Everything needing a reference snapshot skips cleanly
without one.

**The annotation identity, measured rather than assumed.** The first re-baseline asserted one
annotation row per `variant_key` and was wrong — vo2max has 13 distinct keys and 28 rows. The real
key is `(variant_key, conclusion)`: a variant whose genotypes carry different conclusions gets one
row each. Verified against all six rebuilt modules before the assertion was written.

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

1. **Rebuild and republish the modules** on `just-dna-seq/annotators` under 0.5 — ✅ rebuilt
   (`pipelines v1-port port --all`), **publishing left to the maintainer**. See
   [MODULE_RELEASE_0_5.md](MODULE_RELEASE_0_5.md). It moves every module's `artifact.digest`.
2. **Re-baseline the assertions** — ✅ done, see the table above.
3. **Move `TestCompileWithResolution` onto the `resolution.csv` path** — ✅ done, via a
   `_enrich_and_compile` helper, so they survive the 1.0 removal.
4. **Migrate off `ensembl_cache=`** — ✅ done for the port and the ClinVar/PGx routes; the compile is
   inject-only and the coordinates travel in `resolution.csv`. `module_compiler/resolver.py` and
   `register_custom_module` still inject a cache and are the remaining callers.

### One more trap, found migrating (2026-08-09)

`compile_module(resolve_with_ensembl=False)` reads as "do not use Ensembl", which is exactly what a
migration to `resolution.csv` wants it to mean. It is the **master switch for resolution**, so it
also disables the injected-table path: a module with a complete, correct `resolution.csv` compiles
*successfully* with `chrom=None` on every weight row. The correct 0.5 call is

```python
compile_module(spec_dir, out_dir, resolve_with_ensembl=True, ensembl_cache=None)
```

Reported upstream; `tests/test_module_compiler.py::test_no_resolve_flag_skips_resolution` now pins
the behaviour so nobody re-derives it.

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
