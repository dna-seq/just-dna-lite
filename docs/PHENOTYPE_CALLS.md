# Compound phenotype calls

Most annotation modules report one match per position. A phenotype like **ABO blood group**, **APOE
ε-status**, an **HFE compound-heterozygous** finding or a **CYP2C19 metaboliser class** is instead a
function of several sites read *together*, as a pair of named alleles (a diplotype). The module format
(`just-dna-format` 0.7) can already *describe* these — with a `haplotypes` table (the variants of each
named allele) plus a combiner — but turning a VCF into a diplotype is **measurement**, and upstream
scopes that to the consumer. This document is that consumer's contract: what a phenotype module is, how
the caller reads one, and what the report says.

The code lives in `just_dna_pipelines.annotation.phenotype_caller`; the report section is built in
`report_logic.build_phenotype_report_data` and rendered by the `phenotype_card` macro in
`longevity_report.html.j2`.

## What makes a module a phenotype module

`hf_modules.module_kind(info)` classifies a module as `variant`, `phenotype`, or `unsupported`. It is
`phenotype` when, and only when:

- its **lead table** is one of `diplotypes`, `haplotypes`, `allele_function`, `activity_phenotype`, **and**
- it carries a `haplotypes` table, **and**
- it carries either `diplotypes` (the **enumerative** combiner) or both `allele_function` and
  `activity_phenotype` (the **score-and-bin** combiner).

Routing is on the lead table, so a weights- or `pharm_variants`-led module — even a mixed one that also
ships a `haplotypes` table — stays a `variant` module and is annotated exactly as before. A phenotype
lead with no usable combiner is `unsupported`: neither the caller's job nor the weights engine's, and it
stays a recorded skip.

The engine (`hf_logic.annotate_vcf_with_all_modules`) dispatches on `module_kind` **before** the weights
call. The caller is reached only from that branch, which is why a phenotype module cannot perturb the
native modules in the same run (verified: a native module's output parquet is byte-identical whether it
runs alone or beside a phenotype module, and the variant totals are unchanged).

## The call: one `PhenotypeCall` per (module, gene)

Written to `{module}_phenotypes.parquet` (one row per gene, nested list/struct columns). Fields:

| field | meaning |
|---|---|
| `status` | `called` \| `ambiguous` \| `not_assessable` \| `no_match`. Never silence, never a default. |
| `phenotype` | set only when every consistent diplotype maps to one phenotype |
| `candidates` | the consistent diplotypes: `{haplotype_a, haplotype_b, phenotype, conclusion, direction, clin_sig, not_assessable, activity_score}` (`activity_score` only on a score-and-bin module) |
| `sites` | per defining site: `{rsid, chrom, start, ref, observed, evidence, matched_by, restored_flank_bp, phased_alleles, phase_set}`. `observed` is sorted; `phased_alleles` keeps homolog order and is set only for a phased call |
| `phase_would_decide` | true when the ambiguity is pure cis/trans — knowing the phase would settle it |
| `alleles_considered` | the haplotypes the module defines (a coverage statement) |
| `alleles_not_assessable` | alleles needing a structural/copy-number call an SNV VCF cannot make |
| `unpaired_haplotypes` | defined haplotypes no diplotype row pairs |
| `drug_rows` | pharmacogenomic rows, one per `(drug, clinical_context)`; the caller never picks a setting |
| `compiler_warnings` | the module's `manifest.compilation.warnings_summary`, verbatim |

### How a status is reached

1. **Resolve each defining site** against the callset (`gather_site_evidence`), in this order:
   - by `(chrom, start)`, where the record's `ref` equals the site's (a record at that position with
     another `ref` is a different event, such as an indel anchored on the same base). When several
     records share the position, the one whose ALTs include an allele the site defines wins;
   - by rsID, where the site names one and the VCF carries IDs (a `;`-joined ID matches on each part);
   - for an **indel** site only, the same event at another anchor within ±10 bp
     (`INDEL_WINDOW_BP`): `just_dna_format.alleles.parsimony_reduce` of the record must equal the
     site's for one of its non-reference alleles, and **exactly one** record in the window may qualify.
     The record's alleles are rewritten into the site's spelling before any comparison
     (`matched_by = "indel_window"`). Two qualifying records is a refusal, logged as
     `step="indel_window_not_unique"`, and that site is `no_call` — it is **never** restored, because
     the callset demonstrably carries an event of that shape there;
   - otherwise `restoration.restorable_sites`, which restores the site to hom-ref only where the
     callset's coverage supports it (the same gates the weights engine uses). Everything else is
     `no_call`.

   Each site records its `evidence` (`called` / `restored_hom_ref` / `no_call`) and `matched_by`.
2. **Read phase where the callset states it.** A called site is *phased* when its `GT` uses `|` **and**
   it carries a non-null `PS`; its alleles are then kept in homolog order on `phased_alleles` with the
   `phase_set`. The alleles come from the `GT` indices, not from the `genotype` column, which the reader
   sorts and which has therefore lost homolog order. `PS` already reaches the normalized parquet when the
   VCF carries it (polars-bio reads every FORMAT field the header declares), so no normalization change
   was needed. A `|` genotype with no `PS` is read unphased.
3. **List the candidate diplotypes** (`_candidate_rows`). Enumerative module: the `diplotypes` rows as
   authored. Score-and-bin module: every unordered pair of alleles that both `haplotypes` and
   `allele_function` define, with the pair's summed `activity_value` binned by `activity_phenotype`
   (inclusive bounds, `None` open, a shared endpoint owned by the bin with the greater `measure_min`,
   compared in float32 — TABLES.md). The `unresolved` sentinel row never takes part in the bin scan. An
   allele missing from either table cannot be scored and is listed under `unpaired_haplotypes`.
4. **Keep the consistent diplotypes** (`call_gene`). Unphased and restored sites compare as unordered
   pairs. Phased sites are grouped by phase set, and inside one set the diplotype must fit under a
   **single orientation** (haplotype A on the first homolog at every site of the set, or on the second at
   every site). That is what separates the HFE compound heterozygote (trans) from both variants in cis. A
   `no_call` site is a wildcard. A haplotype carries `ref` at any defining site it does not list (the
   PharmVar/CPIC unlisted-site convention).
5. **Set the status**: `called` when all consistent candidates agree on one phenotype; `ambiguous` when
   they disagree; `no_match` when none is consistent; `not_assessable` when nothing was observed at all
   (never a reference default), when the only consistent candidates need an allele an SNV VCF cannot
   confirm, or when they agree on *no* phenotype (a score in no bin, an unstated activity value).
6. **`phase_would_decide`** is true for an `ambiguous` call when the consistent candidates agree on the
   expected genotype at every `no_call` site, so the only remaining unknown is which homolog carries
   which observed allele. It is false when a `no_call` site (a missing *call*, not phase) is what splits
   them. Two `|` genotypes in *different* phase sets say nothing about each other, so such a pair stays
   ambiguous with this flag set.

## Scope (what this version does not do)

- **Diploid.** A site's genotype is compared as a two-allele set and a restored site is `[ref, ref]`, so a
  haploid contig (chrY/chrM, or a male's hemizygous X for G6PD) reads as `no_match` rather than a haploid
  call. The format has no hemizygous diplotype spelling either (`DiplotypeRow.haplotype_b` is required).
- **`*1` is not synthesised.** A diplotype naming a haplotype the module does not define (an implicit
  `*1`) is skipped rather than assumed all-reference. Every module we hold defines every allele
  explicitly, so this does not arise; a module relying on an implicit `*1` needs that rule added.
- **Structural alleles** are detected from the `allele` spelling (there is no `sv_type` column on
  `haplotypes`; a structural allele is a non-nucleotide spelling) and reported `not_assessable`.
- **One gene at a time.** A phenotype over two genes' phenotypes (Lewis = FUT3 × FUT2, warfarin
  CYP2C9 × VKORC1) is not expressible in the format and not attempted here.
- **The indel window is a tolerance, and it says so.** Two spellings that reduce to the same event but
  sit at different anchors are not always the same variant: rs8176719's Ensembl placement
  (`133257520 G>GC`) is a genuinely different event from dbSNP's `133257521 T>TC`, because the flanking
  bases are G and T. The window treats them as one because a reference cache that places an rsID one base
  off is the case it exists for, and because a unique match within 10 bp is a strong signal. Every such
  match is labelled `indel_window` in the report so a reader can see it was not an exact hit.

## Pilot modules

Four phenotype modules are vendored under `just-dna-pipelines/tests/fixtures/phenotypes/`, compiled
strict with the published compiler at test time, and registered locally on the development machine with
`pipelines module register-compiled` (**not published**):

| module | combiner | what it exercises |
|---|---|---|
| `apoe_epsilon` | enumerative | copy of the just-dna-format reference example; the unphased double-het |
| `hfe_compound_het` | enumerative | copy of the reference example; cis vs trans, decided by phase sets |
| `abo_phenotype` | enumerative | five ABO alleles over six sites; the reference genome is O, two indel sites whose spelling varies by source |
| `fut2_secretor` | score-and-bin | three FUT2 alleles; the activity scale is chosen so secretion stays dominant |

Measured on this machine: Anton B/O1 → **B** and secretor; Livia A1/B → **AB** (her two B markers are
`0|1` in one phase set) with ε3/ε3 and wt/wt read from restored sites; the two other WGS samples O1/O1
→ **O**, one of them H63D/wt.

## Authoring rules (for a phenotype module)

- Define every allele at every defining site explicitly, including the reference-matching one (ABO's `O`,
  HFE's `wt`, APOE's `e3`). `*1` is the only implicit allele the format allows, and this consumer does not
  yet synthesise it.
- Enumerate the diplotypes in `diplotypes.csv` (allele pair → phenotype), or supply
  `allele_function` + `activity_phenotype` for score-and-bin. With score-and-bin, choose the
  `activity_value`s so the bins honour the biology (FUT2: one functional copy must reach the secretor
  bin, since secretion is dominant) and pin that in a test, because an additive scale does not do it by
  itself.
- Author an indel at the left-normalized position a VCF caller writes, checked against the reference
  sequence, and put the phenotype's group in `phenotype` with any subgroup in `conclusion` (ABO: `AB`,
  with A2 named in the text), so an unphased callset that cannot resolve the subgroup still calls the
  group.
- A structural or copy-number allele carries its symbolic spelling; the caller reports it not assessable
  from an SNV VCF rather than guessing.

## Tests

- `tests/test_phenotype_caller.py` — the four statuses, phase ambiguity and phase sets, restoration,
  both combiners, the indel window (both spellings of both ABO indels, and the refusal), the parquet
  contract, and a **derived** test that reads each fixture's own candidate list, feeds the exact genotype
  it implies, and requires the module's own phenotype back (runtime ground truth, not magic numbers). The
  score-and-bin test re-bins every pair straight from the authored CSV rather than trusting the caller's
  binning.
- `tests/test_native_module_regression.py` — `module_kind` routing is unchanged for every native module,
  and native annotation is deterministic across runs.
- Fixtures are vendored spec directories (`tests/fixtures/phenotypes/`) compiled at test time with the
  published compiler, so there is no path dependency on a sibling checkout.
