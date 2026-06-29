# just-prs change request: reference-allele restoration should resolve once per batch

## Context / who calls what
`just-dna-lite` (webui `PRSState.compute_selected_prs`) uses the **single-score call
path**: it loops over the selected PGS IDs and calls
`just_prs.prs.compute_prs(..., reference_restoration=True, reference_universe_path=…,
genotype_input_mode="variant_only", sample_build=…)` once per score. It does **not**
use `compute_prs_batch` (it needs per-score progress, incremental result caching,
corrupt-cache repair, and per-score enrichment).

WGS restoration was wired in and is correct, but PRS over many scores became very slow.

## Root cause
`compute_prs` calls `_apply_reference_resolution` (prs.py ~line 512) on **every** call,
which joins the **scoring file** against the **reference-allele universe** to fill the
scoring file's `reference_allele`:

```python
scoring_norm.join(universe, left_on=["chr_name_norm","chr_pos_norm"],
                  right_on=["_u_chrom","_u_pos"], how="left")
```

The universe is **catalog-wide and identical for every PGS ID** (~34M rows), but this
join runs per score, and as written it hashes the 34M-row universe each time.

`compute_prs_batch` does not help: it just forwards `reference_universe_path` to each
per-score `compute_prs`/`compute_prs_duckdb`, so the universe is re-resolved/re-joined
per score there too.

## Measurements (newton WGS, PGS000018; universe 33,937,853 rows; scoring 1,745,179 rows)
| formulation | time |
|---|---|
| (a) `scoring.join(universe, how="left")` — current, hashes 34M | **6.72 s / score** |
| (b) `universe.join(scoring, how="inner")` — hashes the small 1.7M side | **1.18 s** |
| (c) build all-sites sample once (`universe.join(sample_GT, how="left")`) | 5.64 s once |
| (c) per-score `scoring.join(all_sites, how="left")` | 4.49 s |
| (c2) `all_sites.join(scoring, how="semi")` — hashes small side | 0.78 s |
| universe parquet parse (already cheap) | 1.71 s |

Two independent wins, both needed:
1. **Resolve restoration once per batch**, not per score.
2. **Hash the small (scoring) side**, not the 34M universe side (≈6× even single-shot).

## Requested change
`_apply_reference_resolution` inside a single `compute_prs` call is correct and should
stay for the single-call path — but it must become **conditional / skippable**, so the
batch path resolves restoration **once at the start** and reuses it for every score.

### Option A (preferred) — expose "prepare once", usable by the single-call loop
This lets just-dna-lite keep its per-score loop (progress/caching/enrich) while paying
the universe cost once.

1. Add a public helper, e.g.
   `prepare_reference_universe(universe_path | build, *, cache_dir) -> ReferenceUniverse`
   that parses the universe **once** and returns an in-memory handle (LazyFrame backed by
   a collected frame, or a small wrapper).
2. Let `compute_prs` / `compute_prs_duckdb` accept that handle, e.g.
   `reference_universe: ReferenceUniverse | None = None`, taking precedence over
   `reference_universe_path`. When supplied, **skip re-parsing** and reuse it.
3. Inside `_apply_reference_resolution`, **flip the join** so the small scoring side is
   the hash/build side (e.g. `universe.join(scoring, how="inner")` then re-attach the
   unmatched scoring rows for LEFT semantics, or an equivalent that avoids hashing 34M).
   Per measurement (b)/(c2) this alone is ~6× faster.

Caller (just-dna-lite) then does, once before the loop:
`uni = prepare_reference_universe(build); compute_prs(..., reference_universe=uni)` per score.

### Option B — fix `compute_prs_batch` to restore once
If the single-call path won't expose a handle: in `compute_prs_batch`, when
`reference_restoration` is set, resolve the universe and build the restoration artifact
once before the loop, then pass it into each per-score compute with a flag that makes the
per-score `_apply_reference_resolution` a **no-op** (already resolved). Same join-flip as
above. just-dna-lite would then switch to `compute_prs_batch` and give up some per-score
control (progress/incremental caching), so Option A is preferred.

## Notes / constraints
- Restoration only engages in `genotype_input_mode="variant_only"` (correct). WGS callers
  must keep passing `variant_only`; arrays stay `auto`. Keep that behavior.
- Whatever is built once must still produce **identical results** to the current per-score
  path (correctness over speed): same `reference_allele` fill + `ref_resolved_source`.
- A subset-to-selected-positions approach was explicitly **not** wanted — the universe is
  small/catalog-wide; prepare the whole thing once and reuse for any set of scores.

## just-dna-lite side, after just-prs ships
- Bump just-prs; in `PRSState.compute_selected_prs`, call `prepare_reference_universe(...)`
  once before the per-score loop and thread the handle into `_compute_single_prs`.
- (Interim webui monkeypatch that cached only the universe *parse* has been reverted — it
  addressed parse, not the join, and would have clobbered this fix.)
