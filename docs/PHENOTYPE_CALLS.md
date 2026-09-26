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
| `candidates` | the consistent diplotypes: `{haplotype_a, haplotype_b, phenotype, conclusion, direction, clin_sig, not_assessable}` |
| `sites` | per defining site: `{rsid, chrom, start, ref, observed, evidence, matched_by, restored_flank_bp}` |
| `phase_would_decide` | true when the ambiguity is pure cis/trans — knowing the phase would settle it |
| `alleles_considered` | the haplotypes the module defines (a coverage statement) |
| `alleles_not_assessable` | alleles needing a structural/copy-number call an SNV VCF cannot make |
| `unpaired_haplotypes` | defined haplotypes no diplotype row pairs |
| `drug_rows` | pharmacogenomic rows, one per `(drug, clinical_context)`; the caller never picks a setting |
| `compiler_warnings` | the module's `manifest.compilation.warnings_summary`, verbatim |

### How a status is reached

1. **Resolve each defining site** against the callset (`gather_site_evidence`): by `(chrom, start)`
   first, then by rsID where the site names one and the VCF carries IDs, then — for a site the callset
   never emitted — `restoration.restorable_sites`, which restores it to hom-ref only where the callset's
   coverage supports it (the same gates the weights engine uses). Everything else is `no_call`. Each site
   records its `evidence` (`called` / `restored_hom_ref` / `no_call`) and `matched_by`.
2. **Keep the consistent diplotypes** (`call_gene`): a candidate is consistent when its expected
   unordered genotype equals the observed one at every `called` or `restored` site. A `no_call` site is a
   wildcard. A haplotype carries `ref` at any defining site it does not list (the PharmVar/CPIC
   unlisted-site convention).
3. **Set the status**: `called` when all consistent candidates agree on one phenotype; `ambiguous` when
   they disagree; `no_match` when none is consistent; `not_assessable` when nothing was observed at all
   (never a reference default), or when the only consistent candidates need an allele an SNV VCF cannot
   confirm.
4. **`phase_would_decide`** is true for an `ambiguous` call when the consistent candidates agree on the
   expected genotype at every `no_call` site — so the only remaining unknown is which homolog carries
   which observed allele. It is false when a `no_call` site (a missing *call*, not phase) is what splits
   them.

## v1 scope (what this version does not do)

- **Enumerative only.** Only the `diplotypes` combiner is implemented. The score-and-bin combiner
  (`allele_function` + `activity_phenotype`, e.g. a CYP2C19 activity score → metaboliser bin) is not — no
  reference example exercises it yet, and untested paths are not built.
- **Unphased.** The normalized parquet keeps `GT` but not `PS`, so every call is unphased. An unphased
  double-het two diplotypes both explain is `ambiguous` with `phase_would_decide` set (the HFE
  compound-het-vs-cis case), never resolved by a guess. Carrying `PS` through normalization to unlock the
  phased HFE rows is a separate, later change.
- **Diploid.** A site's genotype is compared as a two-allele set and a restored site is `[ref, ref]`, so a
  haploid contig (chrY/chrM, or a male's hemizygous X for G6PD) reads as `no_match` rather than a haploid
  call.
- **`*1` is not synthesised.** A diplotype naming a haplotype the module does not define (an implicit
  `*1`) is skipped rather than assumed all-reference. The reference examples we support (APOE, HFE) define
  every allele explicitly, so this does not arise; a module relying on an implicit `*1` needs that rule
  added.
- **Structural alleles** are detected from the `allele` spelling (there is no `sv_type` column on
  `haplotypes`; a structural allele is a non-nucleotide spelling) and reported `not_assessable`.

## Authoring rules (for a phenotype module)

- Define every allele at every defining site explicitly, including the reference-matching one (ABO's `O`,
  HFE's `wt`, APOE's `e3`). `*1` is the only implicit allele the format allows, and this consumer does not
  yet synthesise it.
- Enumerate the diplotypes in `diplotypes.csv` (allele pair → phenotype), or supply
  `allele_function` + `activity_phenotype` for score-and-bin (not yet consumed here).
- A structural or copy-number allele carries its symbolic spelling; the caller reports it not assessable
  from an SNV VCF rather than guessing.

## Tests

- `tests/test_phenotype_caller.py` — the four statuses, phase ambiguity, restoration, the parquet
  contract, and a **derived** test that reads each fixture's own diplotype table, feeds the exact genotype
  it implies, and requires the module's own phenotype back (runtime ground truth, not magic numbers).
- `tests/test_native_module_regression.py` — `module_kind` routing is unchanged for every native module,
  and native annotation is deterministic across runs.
- Fixtures are vendored spec directories (`tests/fixtures/phenotypes/`, copies of just-dna-format's
  `apoe_epsilon` / `hfe_compound_het`) compiled at test time with the published compiler, so there is no
  path dependency on a sibling checkout.
