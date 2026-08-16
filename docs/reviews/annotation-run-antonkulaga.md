# Annotation pipeline against Anton Kulaga's genome — run report and defects

**Date:** 2026-08-16 · **Branch:** `ui-store` (working tree, 0.5-contract changes uncommitted)
**Sample:** `antonkulaga.vcf` (Zenodo 18370498, CC-Zero) — DeepVariant 1.1.0, GRCh38, Ensembl contig
naming (`1`…`22`, `X`, `Y`, `MT`), **variant-only** (no gVCF reference blocks), **no rsIDs in `ID`**.
**Job:** `annotate_and_report_job`, all 12 discovered modules, partition `anonymous/antonkulaga`.
**Result:** success in 2m13s (normalize 25.6s, annotate 59.0s, report 48.1s; peak 500 MB, 147% CPU).

Outputs: `/data/just-dna-lite/output/users/anonymous/antonkulaga/`
(`user_vcf_normalized.parquet`, `modules/*_weights.parquet`, `reports/longevity_report_20260816_024256.html`).

---

## What the run produced

| module | lead | parquet rows | **real matches** | report section |
|---|---|---:|---:|---|
| longevitymap | weights | 289 | **215** | 215 variants, 201 positive / 14 negative |
| pathogenic | weights | 181 | **1** | 1 variant (rs55960271, CLCN1) |
| cancer | weights | 29 | **0** | "No annotated variants found" |
| superhuman | weights | 20 | **14** | 14 variants, all positive |
| cardio | weights | 18 | **0** | "No annotated variants found" |
| coronary | weights | 12 | **12** | 12 variants |
| lipidmetabolism | weights | 9 | **9** | 9 variants |
| vo2max | weights | 6 | **5** | 5 variants |
| thrombophilia | weights | 3 | **3** | 3 variants |
| pharmgkb | pharm_variants | 0 | **0** | "No annotated variants found" |
| eric_mods__lactose_tolerance | weights | 0 | **0** | "No annotated variants found" |
| test_namespace2__longevity_2025 | weights | 0 | **0** | "No annotated variants found" |

VCF normalization: 6,079,744 → 4,257,537 rows (30.0% removed by `PASS`/DP≥10/QUAL≥20). 139 contigs
survive, `MT` among them (29 rows). 4,257,537 / 4,257,537 genotypes are 2-allele lists. Zero rsIDs.

---

## Verified correct

These were checked against independently reconstructed ground truth, not against the engine's own
output.

**1. The position join is exact.** For each of the nine coordinate-led modules, the authored
`(chrom, start, ref, sorted-genotype)` tuples were joined to the normalized parquet outside the
engine and compared with the module parquets: **0 missed and 0 spurious matches**, all nine modules.
`probe_truth.py`.

**2. The `ref` agreement guard is doing real work and is not over-firing.** It discarded 12 rows
across the corpus (cancer 1, cardio 2, pathogenic 9). Every one is a genuine contradiction, e.g.
sample `T>C` SNV against a module `TT>C` deletion, or `TC>T` against `TCCTCGTCATCTCTCA>T`. In the
`pathogenic` module alone it is the difference between **1 reported pathogenic finding and 10** —
nine of which would each have been a different variant whose ALT string happened to coincide.

**3. The `variant_key` dedup in `_join_annotations` is lossless here.** Every `variant_key` with more
than one annotation row carries an identical `gene`/`category`/`phenotype` in all seven modules that
have annotation tables. And coronary's ratio is 77 annotation rows / 27 variant keys = **2.85**,
matching the documented ×2.85 inflation exactly — so the fix is both necessary and free of loss on
this corpus.

**4. Multi-allelic records are handled correctly.** polars-bio emits `|`-separated ALT
(63,566 rows), and GT indices ≥2 (`1/2` on 57,721 rows, up to `3/4`) resolve to the right alleles —
`1 15274 A G|T 1/2 → ["G","T"]`.

**5. Contig folding.** `MT` stays `MT`; no `M` or `chrM` leaks into the normalized parquet.

**6. The report renders exactly the real matches:** 259 `<tr class="clickable">` rows against
12+9+215+1+14+3+5 = 259, with 259 matching `colspan="8"` detail cells. Every per-module stat box
agrees with its parquet.

---

## Defects

### D1 — Reported variant counts include unmatched rows (2.2× inflation)

`annotate_vcf_with_module_weights` returns `num_rows`, the row count of the sunk parquet
(`hf_logic.py:389`). That parquet deliberately keeps the unmatched left-join rows so the report can
filter them later — so the number is a *positions probed* count, not an *annotated* count.

Consequences, all user-visible:

- `manifest.json` → `total_variants_annotated: 567`. Real total: **259**.
- Dagster asset metadata `total_variants_annotated` — same number.
- `pipelines` CLI (`cli.py:347`, `cli.py:573`) prints it as "Total variants annotated".
- The per-module log line reads `cancer: 29 variants with weights` for a module that annotated
  **zero**; `cardio: 18` → 0; `pathogenic: 181` → 1.

The fix is a second count on the same frame (`module` non-null), which the report already computes
in `_annotated_rows`. Both numbers are worth keeping — "181 positions probed, 1 annotated" is more
informative than either alone.

### D2 — Every eliot diagnostic in the annotation path is discarded

`hf_logic` and `report_logic` log `vcf_has_no_rsids`, `ref_mismatch_discarded`,
`join_strategy_downgraded`, `annotations_join_keying` and `missing_module_table_for_report` through
eliot. **No eliot destination is registered anywhere in the Dagster or webui path** — `to_file` /
`log_files` appear only in `v1_port/*_runner.py` and `module_compiler/cli.py`. Eliot buffers and
discards when no destination exists.

Verified: a full run's log contains **0** occurrences of any of those `step=` values and 0
occurrences of `action_type`, and a standalone `start_action(...).log(...)` prints nothing.

This is the reason D3 below is invisible, and it means the `ref_mismatch_discarded` guard — which
suppressed 9 of 10 pathogenic findings on this sample — did so with no record anywhere that a user
or a maintainer could read. The observability added for exactly these silent conditions is
unreachable in production.

### D3 — "No annotated variants found" where the true reason is "this VCF cannot match"

`pharmgkb` is `pharm_variants`-led with null coordinates, so the engine correctly downgrades to an
rsid join. Anton's DeepVariant VCF carries **0 rsIDs across 4,257,537 records**, so no variant *can*
match. The engine detects this (`step="vcf_has_no_rsids"`) but:

- the diagnostic goes nowhere (D2);
- `manifest.json` records `skipped_modules: {}` / `failed_modules: {}` and lists pharmgkb as an
  ordinary success with 0 rows;
- the report renders "No annotated variants found for this module."

A reader concludes they have no actionable drug-response variants. The truthful statement is that
this genome could not be tested against that module at all. The reason needs to travel on the
manifest (a third bucket alongside skipped/failed, or a per-module `note`) and be rendered.

### D4 — The "Alt allele" column shows the module's candidate alleles, not the sample's

`_build_variant` sets `"ref"` from the VCF row but `"alt"` from `row["alts"]`, the module's authored
allele list, joined with `/`. **155 of 259 report rows (60%)** therefore print two or more alleles in
a cell headed "Alt allele", immediately beside a "Your genotype" cell formatted identically.

The single `pathogenic` finding renders as `Ref allele: C · Alt allele: A/T · Your genotype: C/T`.
The person carries `T`; `A` is an allele ClinVar knows at that site and he does not have. Adjacent
columns with the same shape and different provenance are not readable. The sample's own `alt` is in
the parquet and unused.

### D5 — Weight-less modules render fabricated zeros

`superhuman` states no weights. `_build_variant` coerces `weight` to `0.0`, so the report shows a
Weight column of `0.0` on all 14 rows, a "Net weight 0.0" stat box, and the prose "14 variants were
found, 14 with positive weight and 0 with negative weight" — when the direction comes from `state`,
not from any weight. Same for the 4 of 5 vo2max rows and the single pathogenic row. The template
already renders conditionally elsewhere; the weight column and its prose should do the same.

### D6 — 40% of longevitymap's sites cannot report a homozygote (module data)

Authored genotype coverage per site, by module:

| module | rows | hom-ref rows | het | hom-alt | sites | **sites with no hom-alt** |
|---|---:|---:|---:|---:|---:|---:|
| longevitymap | 1039 | 193 | 501 | 324 | 520 | **208 (40%)** |
| superhuman | 190 | 3 | 86 | 101 | 101 | 22 (22%) |
| pathogenic | 617001 | 2727 | 308419 | 305696 | 285780 | 2837 (1%) |
| cancer | 139254 | 1296 | 69627 | 68331 | 62471 | 1267 (2%) |
| cardio | 115060 | 539 | 57465 | 56926 | 51988 | 656 (1%) |
| coronary / lipidmetabolism / vo2max / thrombophilia | — | balanced | | | | 0 |

Anton is homozygous for the alternate allele at **74 longevitymap sites the module covers**, and
every one is silently unreported. Concrete cases: `rs9899404` (17:48976466, he is C/C — module
authors T/T and C/T only), `rs15606`, `rs1205035`, `rs10190125`. The four hand-curated modules
(coronary, lipidmetabolism, vo2max, thrombophilia) are perfectly balanced, so this is a property of
the Gen-I port, not of the format.

Related and structural: **193 of longevitymap's 1039 rows (19%) author a hom-ref genotype**, which
can never match anything. A variant-only VCF emits no record at a hom-ref site, and in a gVCF the
`RefCall` block is dropped by `pass_filters` (documented as intentional). `eric_mods__lactose_tolerance`
is the pure case — it authors a `G/G` "lactase non-persistence" row for rs4988235, Anton has **no
record at all** at 2:135851076, and the module reports nothing rather than "you are G/G, non-persistent".
That is the most common lactose-intolerance result and the module cannot deliver it.

This one is not fixable in the engine alone. Worth a note in the format repo's ROADMAP: a compiler
warning for a site that authors hom-ref or omits hom-alt would have caught both.

### D7 — Credits over-claim licence restrictions

`build_report_credits(available_modules, …)` keys on every module with a parquet file, not on the
modules actually rendered. The report therefore carries ClinPGx's "Share-alike required" and
"Non-commercial use only" under the heading "This report redistributes curated content from the
databases below" — while containing **zero** rows of ClinPGx content. Restricting further than
required is the safe direction, but the statement is still false. Filter to modules with ≥1 rendered
variant.

### D8 — Pipe-delimited fields render verbatim

The one pathogenic finding's Conclusion reads
`ClinVar: pathogenic (2★) — Skeletal muscle channelopathy|CLCN1-related disorder|EMG: myopathic abnormalities|M…`.
The `|` list separator reaches the HTML unsplit.

### D9 — an rsID that resolves to two loci is fanned across both, and the authored genotype goes with it

Found while implementing D6. **Not a curation defect** — the panel is faithful and ClinVar is right;
the fan-out happens in the compiler's resolution join. This section originally blamed
`v1_port/clinvar_panel.py`; that was wrong and the trace below is what corrected it.

**ClinVar holds two real records** at 5:112767222 under one rsID (dbSNP merges them):

| variation_id | ref → alt | variant_type | clin_sig |
|---|---|---|---|
| 428095 | `T → TA` | Duplication | pathogenic |
| 2583495 | `TA → T` | Deletion | pathogenic |

**The panel authors that correctly.** `cancer/variants.csv` holds exactly two rsid-only rows, no
coordinates, both describing the duplication:

```
rs1114167546,,,,,T/TA, …risk… genotype: heterozygous
rs1114167546,,,,,TA/TA,…risk… genotype: homozygous (two copies)
```

**Resolution records both loci, and the join ignores the distinction.** `cancer/resolution.csv`
carries two rows under one `variant_key`, separated by `locus_index`:

```
rs1114167546,rs1114167546,5,112767222,T,TA,GRCh38,0,…
rs1114167546,rs1114167546,5,112767222,TA,T,GRCh38,1,…
```

2 authored genotypes × 2 resolved loci = **4 compiled rows**, each genotype paired with both ref
spellings. Two of them are nonsense: `TA/TA` against `ref=TA` reads as hom-**ref**, not the hom-alt
duplication the author wrote.

Scale — `variant_key`s that resolve to more than one locus, and they account for the spurious
hom-ref rows exactly:

| module | variant_keys | multi-locus | spurious hom-ref rows measured |
|---|---:|---:|---:|
| `cancer` | 68,331 | **1,296 (1.9%)** | 1,296 |
| `pathogenic` | 305,850 | **2,730 (0.9%)** | 2,727 |
| `cardio` | 57,055 | **540 (0.9%)** | 539 |
| `longevitymap` / `coronary` | 528 / 27 | **0** | 0 |

One for one, which is what identifies the mechanism rather than merely correlating with it.

It is latent for the position join — a VCF record matches one spelling and not the other — which is
why the first run did not show it. It is **not** latent for restoration: read literally, the
wrong-locus rows say "the reference genotype here is pathogenic", and the first implementation duly
restored **2,579** of them into this genome's `pathogenic` section and **1,183** into `cancer`,
every one telling the reader they carry a pathogenic variant they do not have. Caught before the
report was rendered; the guard is described below.

`locus_index` already names the ambiguity the join then discards, so the fix belongs upstream in
`just-dna-compiler` / `just-dna-enricher`, not here. Worth filing as a consumer suggestion beside
S31/S32.

### Also noted

`test_namespace2__longevity_2025` — a test-namespace module — renders as a titled section
("Familial Longevity (2025)") in a user-facing report, because everything in
`output/users/registered_modules` is auto-discovered. Config, not code, but it will ship in a demo.

---

## What was fixed, and the rerun

D1, D4, D6 and D9 are fixed; the rerun is `longevity_report_20260816_033533.html` (same partition,
2m21s). New file: `annotation/restoration.py`; tests: `tests/test_restoration.py` (14, all passing,
including the real lactose case as ground truth). Contract documented in CLAUDE.md.

**D1 — counts.** `annotate_vcf_with_module_weights` now returns matched rows, not the parquet's
height, and logs both (`num_matched` / `num_written`). `total_variants_annotated` went **567 → 372**,
which is the real figure; the log now reads `cancer: 0 variants annotated` where it read
`cancer: 29 variants with weights`.

**D6 — restoration.** Reference genotypes are restored where the callset is **variant-only and
whole-genome**, the site carries no record at all, and a called variant lies within 10 kb.
**113 rows restored**, provenance on `genotype_evidence` (`called` | `restored_hom_ref`) with the
flank distance beside it:

| module | annotated | of which inferred |
|---|---:|---:|
| longevitymap | 292 | 77 |
| coronary | 27 | 15 |
| lipidmetabolism / vo2max / thrombophilia | 15 / 12 / 8 | 6 / 7 / 5 |
| superhuman | 15 | 1 |
| **lactose_tolerance** | **2** | **2** |

The lactose case now reports what it should:

> rs4988235 · MCM6 · **G/G** `inferred` · "Homozygous ancestral genotype … adult-type hypolactasia"
> **Genotype source:** No variant was called at this position … it can also mean the position was not
> covered well enough to call, and this file cannot tell the two apart. The nearest called variant is
> **180 bp** away. Treat this as weaker than a directly sequenced result.

Verified after the rerun: manifest totals equal the parquets, and **0** restored rows sit on a site
the caller emitted. Every summary card carries an *Inferred* count beside *Total variants*, so an
inferred row is never pooled into a headline number.

**D9 — the guard.** `hom_ref_rows` withholds any locus the artifact spells with more than one `ref`.
That drops the ClinVar panels' apparent hom-ref rows from 1,296 / 540 / 2,728 to **0, 0, 0** — every
one came from an rsID resolved to two loci — while leaving the curated modules untouched. It is a
containment, not a fix: the mis-paired rows are still in the artifacts and still reachable by any
other reader.

**D4 — the Alt column** is now headed "Module alt alleles", which is what it holds.

**No config flag gates any of this.** The first cut had `restore_reference_genotypes: bool = True`
and it was wrong twice over: it is a guess at something measurable, and having it there disguised the
fact that detection only asked *variant-only vs all-sites* and never *whole-genome vs exome*. On a
WES callset every module site outside the capture kit is absent and the 10 kb flank test passes on
exon clustering, so restoration would have fabricated rows wholesale. `detect_callset_scope` closes
that:

| callset | sites (primary) | breadth within 10 kb | verdict |
|---|---:|---:|---|
| the four real WGS samples here | 4.25–4.61M | **0.942–0.950** | WGS |
| synthetic clustered (20 calls / 50 bp, every 100 kb) | 1.06M | **0.210** | targeted |
| exome / panel | ~50–100k | — | targeted (site count) |

Breadth is the share of the callset's span lying within one flank of a call — the same question the
per-site test asks, applied genome-wide. A gap percentile was tried first and rejected: the clustered
case puts 95% of its gaps at 50 bp, so p90 calls it dense while 79% of the span is nowhere near a
call.

Still open: **D2** (no eliot destination — the `hom_ref_restored` diagnostics this change adds go
nowhere too), **D3** (pharmgkb's "cannot be tested" reason not on the manifest or report), **D5**
(weight-less modules render 0.0), **D7** (credits over-claim), **D8** (pipe-delimited conclusions).

## Reproducing

The VCF was hard-linked into the input dir as
`/data/just-dna-lite/input/users/anonymous/antonkulaga.vcf` (source:
`/data/just-dna-lite/just-prs/genomes/antonkulaga.vcf`), the partition `anonymous/antonkulaga`
registered, and `annotate_and_report_job` executed with `execute_in_process` under the repo's
`DAGSTER_HOME` (`data/interim/dagster`) — the same run config `webui.state.run_hf_annotation`
builds, so this is the app's code path minus the compute-child marshalling.

Driver and probe scripts are in the session scratchpad
(`run_anton.py`, `probe_truth.py`, `probe_genotype_coverage.py`, `probe_missed.py`,
`probe_unmatched.py`, `probe_outputs.py`); none of them are needed to reproduce the run itself,
only to re-derive the ground truth in the tables above.
