# Compound phenotypes (blood groups, APOE, HFE, CYP2C19): calling them from a VCF

## Context

Our modules report per-position matches. A phenotype like ABO blood group, APOE ε-status, HFE
compound heterozygosity or a CYP2C19 metaboliser class is a function of **several sites read
together**, and today nothing in just-dna-lite evaluates such a function. The user asked which
well-known small-SNP-set phenotypes (not PRS) exist beside blood groups, what the module and report
formats need to describe them robustly without overcomplication, a plan to implement support, and a
validation plan proving the existing simple (weights-led) modules do not break.

### The finding that reshapes the task

**The module format can already describe most of this; what is missing is ours.**
`just-dna-format` 0.7 has `haplotypes.csv` (defining variants per named allele), `diplotypes.csv`
(allele pair → phenotype, enumerated), `allele_function.csv` (+`activity_value`) with
`activity_phenotype.csv` (score → bin), and `copynumbers.csv` (dosage → phenotype). Upstream ships
reference examples for exactly our cases: `apoe_epsilon`, `hfe_compound_het`, `cyp2c19_star_alleles`
(`../just-dna-compiler/reference_examples/`). Upstream's ROADMAP lists **star-allele / diplotype
callers as "Not format scope"**: turning a VCF into a diplotype is measurement, which makes it
**just-dna-lite's job**.

And we do not do that job. `module_config.LEAD_TABLES` ranks `diplotypes` ahead of `haplotypes`,
`hf_logic._lead_join_strategy` returns `unsupported` for it, and the engine raises
`UnsupportedLeadTable`. So a compiled `apoe_epsilon` today lands under "Modules not read in this run".
**The work is a caller plus a report section, and only a few small format notes go upstream.**

## Case analysis (4 cases + blood groups, measured on our own samples where possible)

| Case | Sites | Combiner the format already has | What makes it hard | Measured here |
|---|---|---|---|---|
| **ABO blood group** | c.261delG (O1, rs8176719), c.796C>A / c.803G>C (B, rs8176746/rs8176747), c.802G>A (O2), c.1061delC (A2) | enumerative `diplotypes` (codominant A+B=AB cannot be a sum) | **The GRCh38 reference haplotype is O**, not a "wild type", so the `*1 = reference, no rows` shortcut is wrong here. An O/O person has **no record** at 261 in a variant-only VCF, which makes restoration mandatory. The indel is spelled differently by different sources | All 4 samples carry the non-O insertion as `9:133257521 T>TC`. **The Ensembl cache places rs8176719 at `133257520 G>GC`**, where gnomAD shows AF 6e-7. A position-exact match against Ensembl-resolved coordinates misses it in every sample. Anton and dad: 261 het plus B-markers het, unphased → B/O (or rare O-on-B/A). Livia: 261 hom-insertion plus B 0\|1 → AB |
| ↳ Secretor (FUT2) | rs601338 (EUR/AFR), rs1047781 (EAS) | `allele_function`+`activity_phenotype` (0 functional → non-secretor) | the LoF allele is population-specific: rs601338 A at AF 0.50 in NFE vs 0.002 in EAS | Anton and dad het → secretor. No record for Livia → needs a restored hom-ref |
| ↳ Lewis (FUT3 × FUT2) | two genes | **none**: a phenotype over two genes' phenotypes | cross-gene combination (upstream RM28, parked) | out of v1 |
| ↳ RhD | whole-gene RHD deletion | `copynumbers` | not callable from an SNV VCF | must render as *not assessable*, never "RhD+" |
| **APOE ε2/ε3/ε4** | rs429358 + rs7412, 138 bp apart | enumerative `diplotypes` (upstream example) | **unphased double-het** = ε2/ε4 or ε1/ε3, and those phenotypes differ | **Anton is exactly this case** (0/1 at both, unphased, empty `rsid`) |
| **HFE C282Y/H63D** | rs1800562 + rs1799945 | enumerative, with `wt` and `C282Y-H63D` (cis) haplotypes (upstream example) | **phase decides the finding**: compound het in trans vs both in cis | dad H63D/wt, Borysova C282Y/wt. No double-het among our samples, so test with fixtures |
| **CYP2C19 metaboliser** | ~35 star alleles over ~60 sites | `diplotypes` (CPIC enumerates ~600 rows) **or** `allele_function`→`activity_phenotype` | many alleles, `*1` defined by absence, uncertain-function alleles → "Indeterminate" | combinatorics fine (630 pairs × 60 sites) |
| *stress: G6PD* | X-linked | — | hemizygous males: `DiplotypeRow.haplotype_b` is required, no hemizygous spelling | out of v1; upstream note |
| *stress: HIrisPlex eye colour* | 6 SNPs, multinomial logistic | weighted-sum (RM16, parked) | a fitted model, not a rule | **explicitly out of scope**: this is where "not PRS" ends |

Also fit the v1 design with no new format: AAT PI*S/Z (enumerative), HbS/HbC (compound het like
HFE), lactase persistence multi-SNP (any-of = several rows, already expressible).

### What the cases say the design must do (and must not)

1. **Two combiners, both existing**: enumerate (`diplotypes`) or score-and-bin
   (`allele_function.activity_value` → `activity_phenotype`). No boolean DSL, no evaluator in the
   module.
2. **Output a set of consistent diplotypes, not a single guess.** The phenotype is *called* only when
   every consistent diplotype maps to the same phenotype. Otherwise it is *ambiguous*, and the report
   says whether phase would settle it. No population priors in v1.
3. **Three-valued evidence per site** (`called` | `restored_hom_ref` | `no_call`), reusing the
   restoration gates. ABO O/O and FUT2 hom-ref depend on this.
4. **Match alleles by normalized event, with rsID as a second key.** The ABO indel proves it.
5. **State coverage**: list the alleles the module considered ("e1 not considered"; "ABO: A1, A2,
   B, O1, O2 tested; >250 ISBT alleles not"). A non-match is `no_match` (the sample carries a
   combination the module does not define), never a silent default.
6. **Structural or copy-number alleles** (`sv_type`, `copy_number`, RhD) → `not_assessable` from an
   SNV VCF.
7. **Never infer an undeclared default allele** except the format's own `*1` rule. ABO must define O
   explicitly, as HFE defines `wt` and APOE defines `e3`.

## Format changes: what we ask for and what we don't

**Module format: no mandatory change.** Phenotype modules are authored with the existing
`haplotypes` + `diplotypes` tables (enumerative) or `haplotypes` + `allele_function` +
`activity_phenotype` (score and bin). Authoring rules we adopt (docs only):
- define every allele at every defining site explicitly, including the reference-matching allele (ABO's O, HFE's `wt`, APOE's `e3`);
- `*1` is the only allowed implicit allele;
- structural alleles carry `sv_type`/`copy_number`, and the caller then reports them as not assessable.

Upstream notes, written as `CONSUMER_SUGGESTIONS.md` entries in `../just-dna-compiler/docs` (text
only, never commits there; take the S id from `.claude/triage-state.py --next`):
1. **Enricher places the rs8176719 insertion at `9:133257520 G>GC`; dbSNP, gnomAD and DRAGEN use
   `133257521 T>TC`.** This looks like an off-by-one on Ensembl insertions. Measure how many insertion
   rsIDs in the cache disagree with gnomAD before filing.
2. **No hemizygous diplotype spelling** (`DiplotypeRow.haplotype_b` is required): blocks G6PD and
   other X-linked phenotypes in males.
3. **Cross-gene phenotypes** (Lewis = FUT3 × FUT2; warfarin CYP2C9 × VKORC1) as corpus evidence for
   RM28. Suggest the enumerative answer: a table keyed on the per-gene *phenotypes*. We do not
   implement it.
4. **The unlisted-site convention is unstated.** The caller assumes a haplotype carries `ref` at any
   defining site it does not list (the PharmVar/CPIC reading). TABLES.md never says so. Ask upstream
   to state it, or to have `validate` warn when haplotypes of one gene list different site sets.

**Step 0b (de-risk before writing the caller):** compile `apoe_epsilon`, `hfe_compound_het` and
`cyp2c19_star_alleles` with the installed compiler 0.7.1. Confirm all four tables and their
`manifest.artifact.files` attestation come through, and record any warning. No consumer has ever read
these tables. The one earlier attempt (`apoe_epsilon` through our engine) found a defect on first
contact, so expect more and file them as notes.

**Report format: ours, new.** One `PhenotypeCall` per (module, gene):

| field | meaning |
|---|---|
| `status` | `called` \| `ambiguous` \| `not_assessable` \| `no_match` (three-valued rule: never silence, never a default) |
| `phenotype` | set only when every consistent diplotype maps to one phenotype |
| `candidates` | list of {`haplotype_a`, `haplotype_b`, `phenotype`, `conclusion`, `direction`, `clin_sig`} |
| `sites` | list of {`rsid`, `chrom`, `start`, `ref`, `observed` (alleles or null), `evidence` `called`\|`restored_hom_ref`\|`no_call`, `matched_by` `position`\|`rsid`\|`indel_window`, `restored_flank_bp`} |
| `phase_would_decide` | true when candidates differ only by cis/trans assignment |
| `alleles_considered` / `alleles_not_assessable` | coverage statement; SV/CN alleles land in the second list |
| `unpaired_haplotypes` | defined haplotypes no diplotype row pairs (measured upstream: CYP2C19 `*40`, `*41`) |
| `drug_rows` | drug rows grouped by (`drug`, `clinical_context`). Rendered side by side; the caller never picks a clinical setting |
| `compiler_warnings` | the module's phase-ambiguity warnings from `manifest.compilation` (`warnings_summary`), passed through verbatim |

Written as `{module}_phenotypes.parquet` beside the weights outputs (one row per gene, nested list
columns) and rendered in a new report section.

## Implementation steps

Package root: `just-dna-pipelines/src/just_dna_pipelines/`. Run the regression gate after
Steps 1, 2, 4, 5 and 7.

**Step 0: Baseline.** Add `scripts/regression_snapshot.py` (Typer: `snapshot` / `compare`) and take
the baseline on the current tree for {Anton, Livia} × {longevitymap, thrombophilia, coronary,
pharmgkb}, with output under `data/interim/regression_baseline/` (gitignored). Nothing else starts
before this exists.

**Step 1: Discovery exposes the phenotype tables** (`annotation/hf_modules.py`).
- Add `haplotypes_url`, `diplotypes_url`, `allele_function_url`, `activity_phenotype_url` to
  `ModuleInfo` (:39) and matching `ModuleTable` members (:616).
- Set them in `_probe_module_at_path` (:269) through the existing `_has()` attestation, the same way
  `concordance_url` is set.
- Add `module_kind(info) -> Literal["variant", "phenotype", "unsupported"]`. It returns
  `"phenotype"` iff `info.lead_table ∈ {diplotypes, haplotypes, allele_function, activity_phenotype}`
  **and** `haplotypes_url` is present **and** (`diplotypes_url` or both activity tables are present).
  It routes on the lead table, so weights- or pharm-led modules (including a mixed module) stay
  `"variant"`.
- `get_module_table_url` (:635) resolves the new members. Keep its protocol-less fallback unchanged.

**Step 2: Site-level restoration made public** (`annotation/restoration.py`).
- Promote `_absent_sites` + `_with_flanking_distance` into `restorable_sites(sites_lf, called_sites,
  context) -> LazyFrame`. It returns absent sites within the flank when `context.enabled`, and honours
  `requires_callable`.
- Re-express `restored_rows` through it. Behaviour must stay byte-identical (the gate plus
  `test_restoration.py` prove it).

**Step 3: The caller**: new `annotation/phenotype_caller.py` (Pydantic 2 models, polars, eliot).
- `load_phenotype_definition(module_name, info)`: reads the four tables via `scan_module_table` and
  passes through `manifest.compilation` warnings (`_remote_manifest`, `hf_modules.py:150`).
- `gather_site_evidence(vcf_lf, sites, context)`: matches each defining site in this order:
  1. by `(chrom, start)`, with contigs already normalized by `_normalize_vcf_contigs`;
  2. by rsID via `_vcf_rsid_join_keys` when the VCF carries IDs;
  3. for indels only, a ±10 bp window where `just_dna_format.alleles.parsimony_reduce` of both
     spellings is equal and the match is unique in the window (`matched_by="indel_window"`).

  If nothing matches, it falls back to `restorable_sites`, and otherwise records `no_call`.
  Allele hosting uses `just_dna_compiler.resolution.hosting_verdict`, which is three-valued, so its
  `None` stays unknown.
- `call_gene(definition, evidence) -> PhenotypeCall`:
  1. Enumerate every canonical pair of defined haplotypes (+`*1` per the format rule). A haplotype
     carries `ref` at any site it does not list.
  2. Keep the pairs whose expected unordered genotype equals the observed one at every called or
     restored site. A `no_call` site is a wildcard and is recorded.
  3. Map the kept pairs to phenotypes via the `diplotypes` rows, or via Σ`activity_value` →
     `activity_phenotype` bin (bounds inclusive, a shared endpoint goes to the higher bin, per
     TABLES.md).
  4. Set `status`. `phase_would_decide` = the candidates share the per-site allele multiset.
  5. Mark candidates needing an SV/CN allele as not assessable.
- `call_phenotype_module(vcf_lf, module_name, info, context, output_path) -> (Path, n_called)`.
  v1 treats every call as **unphased** (the normalized parquet keeps `GT` but not `PS`).

**Step 4: Engine integration** (`annotation/hf_logic.py`, `hf_modules.py`).
- In the loop of `annotate_vcf_with_all_modules` (:701-724), branch on `module_kind(info)` *before*
  the existing call. `"phenotype"` goes to `call_phenotype_module` with the already-built restoration
  context (:685), writing `{module}_phenotypes.parquet`. Everything else keeps the current call,
  untouched.
- `ModuleOutputMapping` (:861) gains `kind: Literal["variant","phenotype"] = "variant"` and
  `phenotypes_path: Optional[str] = None`. `AnnotationManifest` (:883) gains
  `phenotype_calls: dict[str, dict[str, int]]` (status counts) and `total_phenotypes_called`. The
  defaults keep old manifests valid, and variant totals are never touched.
- The Dagster metadata at :829 adds `modules_phenotype`.

**Step 5: Report** (`annotation/report_logic.py`, `templates/longevity_report.html.j2`).
- `generate_longevity_report` (:1420) partitions the manifest's modules by `kind` first, so the
  existing weights loop (:1455-1508) only ever sees `"variant"` modules and its code is unchanged.
- New `build_phenotype_report_data(manifest, modules_dir)` feeds a new `phenotype_modules` context
  key.
- Template: a new section "Phenotypes from combined variants" placed above the per-module variant
  sections, with a TOC entry and a `phenotype_card` macro. The card shows a status badge, the
  phenotype or candidate list, a "phase would decide" note, the per-site evidence table (reusing the
  `inferred` badge wording for restored sites), the coverage line, and drug rows grouped by clinical
  context.
- Provenance ("Modules in this report") lists phenotype modules as well. Exclusions are unchanged.
  `not_assessable` is a *result* rendered in the card, not an exclusion.

**Step 6: Pilot modules** (authored with the just-module-creator tools, registered locally, **not
published**).
- `abo_phenotype`: haplotypes A1, A2, B, O1, O2 over rs8176719 (authored at `133257521 T>TC`),
  rs8176746, rs8176747, rs41302905, rs56392308, rs1053878, plus 15 diplotype rows → A/B/AB/O (A2
  noted). Genomic alleles must be verified on the minus strand against dbSNP/ISBT, and the
  description states that RhD and rare ISBT alleles are not assessed.
- `fut2_secretor`: rs601338 + rs1047781 via `allele_function` + `activity_phenotype`.
- APOE: copy upstream `apoe_epsilon`.
- The existing weights-led `abo_blood_group` stays as the per-site cross-check. Retiring it is your
  call after the parity test passes.

**Step 7: MCP and webui touch-ups.**
- `lite_mcp/server.py` `_module_result` (:379) and `_sample_module_path` (:375) handle
  `kind="phenotype"`.
- `lite_mcp/worker.py:85` snapshots `_phenotypes.parquet`.
- `lite_mcp/validation.py` `validate_module_run` returns `not_assessed` with a reason for phenotype
  modules, never `no_output`.
- `webui/src/webui/state.py:2378` classifies the `_phenotypes` suffix.

**Step 8 (follow-up): Phase sets.** Carry `PS` through normalization (`user_vcf_normalized`). The
caller then treats two sites as phased only when both GTs use `|` with an equal `PS`. That unlocks the
HFE cis/trans rows. This is a separate change because it alters the normalized parquet schema.

**Step 9: Docs.**
- New `docs/PHENOTYPE_CALLS.md`: the design, authoring rules and the report contract.
- Update the CLAUDE.md/AGENTS.md engine and report sections and `docs/DAGSTER_GUIDE.md`.
- Update `docs/CONSUMER_HANDOFF_from_just-module-creator.md` §star-allele to "built".
- File the three upstream notes.

## Cross-repo scope: how changes spread and get checked

- **Code changes are in just-dna-lite only.** The caller uses only symbols already on PyPI:
  - format 0.7.0: the four tables, `split_genotype`, `parsimony_reduce`, `DiplotypeRow`;
  - compiler 0.7.1: `hosting_verdict`, `compile_module`.

  No pin moves, so `contract_compatible` against the registry is untouched.
- **just-dna-compiler gets text notes only**: three `CONSUMER_SUGGESTIONS.md` entries, each with
  our measurement and a reproducer. No code, commits or PRs there, per the working agreement.
- **The report contract (`PhenotypeCall`) lives here.** Upstream ROADMAP assigns RM7 (the
  evaluation-output schema) to just-dna-lite, so `docs/PHENOTYPE_CALLS.md` is its spec.
- **Test fixtures are vendored copies** of `apoe_epsilon` / `hfe_compound_het` under
  `tests/fixtures/phenotypes/`. That means no path dependency on a sibling checkout (the repo rule),
  and CI builds them with the published compiler.
- **If upstream acts on a note later**, it arrives as a PyPI release. For the enricher insertion fix,
  re-resolving the pilot moves `artifact.digest` but not what the caller matches, because the pilot
  authors `133257521` and the indel-window matching tolerates either spelling. The check is the same
  gate: bump floors (the registry together with the format minor), `uv sync`, rerun the regression
  snapshot and the caller tests.
- **Pilot modules** are compiled `strict` with the published compiler and registered locally. A
  registry publish is out of this plan and would rehearse on polygon first.

## Critical files

- `just-dna-pipelines/src/just_dna_pipelines/annotation/phenotype_caller.py` (new)
- `annotation/hf_modules.py` (ModuleInfo, ModuleTable, `_probe_module_at_path`, `module_kind`, manifest models)
- `annotation/hf_logic.py` (loop dispatch only)
- `annotation/restoration.py` (public site helper)
- `annotation/report_logic.py` + `annotation/templates/longevity_report.html.j2`
- `lite_mcp/server.py`, `lite_mcp/worker.py`, `lite_mcp/validation.py`, `webui/src/webui/state.py`
- `scripts/regression_snapshot.py` (new); tests under `just-dna-pipelines/tests/` (`test_phenotype_caller.py`, `test_native_module_regression.py`, updated `test_consumer_handoff.py`)

Reused rather than rewritten: `_normalize_vcf_contigs`, `_vcf_rsid_join_keys`,
`build_restoration_context`, `scan_module_table`, `_remote_manifest`, `split_genotype`,
`parsimony_reduce`, `hosting_verdict`, `DiplotypeRow` canonicalisation.

## Validation plan: the old native modules must not change

### Modules under the regression gate (old, weights- or pharm-led; not ABO)

| Module (HF `just-dna-seq/annotators`) | Why it is on the gate | Baseline on Anton (existing run) |
|---|---|---|
| **longevitymap** | largest native module; report routed **by name** (`report_logic.py:1497-1506`); restoration-heavy | 366 rows, 292 with conclusion; 289 called / 77 restored |
| **thrombophilia** | clinically sharp per-genotype rows (F5 Leiden rs6025, F2 rs1799963, MTHFR); the native module closest to "compound" meaning, so the most tempting one to reroute by mistake | 8 rows; 3 called / 5 restored |
| **coronary** | exercises the 0.6 `(variant_key, genotype)` annotations join and poly-effect keying in the report | 27 rows; 12 called / 15 restored |
| **pharmgkb** | `pharm_variants` lead with rsid fallback: the nearest **routing** neighbour of the new PGx dispatch, so it must stay on its own path | 0 rows on Anton (no rsIDs in his VCF); **validate on Livia**, who has rsIDs |

`abo_blood_group` (local, registered) is **not** on the gate. It is the experiment and gets rebuilt
as the first phenotype module (Step 6).

### Structural argument, made testable

The new caller is reached **only** from the branch that today raises `UnsupportedLeadTable`, and only
when the module carries `haplotypes` plus (`diplotypes` or `allele_function`+`activity_phenotype`).
A `weights`- or `pharm_variants`-led module never gets there. Pin this:

- `test_routing_is_unchanged_for_native_modules`: parametrized over the four modules above, plus
  every module `discover_hf_modules()` returns whose lead is not a haplotype family. Asserts
  `_lead_join_strategy` and the new `module_kind()` return what they return on `main`, i.e.
  `position`/`rsid` and `variant`.
- `LEAD_TABLES` order and contents unchanged (the existing `tests/test_format_0_6.py` set-equality
  tests already fence this).

### Golden comparison on real samples (before vs after)

1. **Baseline, on `main` before any change:** a script `scripts/regression_snapshot.py` (Typer).
   For each of {Anton, Livia} × {longevitymap, thrombophilia, coronary, pharmgkb} it runs
   `annotation_runner.run_annotation` into a scratch output dir and writes one JSON per
   (sample, module):
   - the manifest entry: `lead_table`, `num_matched`, restored count, `skipped`/`failed` reason;
   - the weights parquet, sorted by `(chrom, start, variant_key, genotype)` and hashed column by
     column (sha256 of each column's IPC bytes), plus height and schema (names and dtypes);
   - the report's rendered rows for that module: parse the HTML, extract `data-preview-row` rows
     plus detail rows as text, and strip timestamps and paths.
2. **After** each implementation step, rerun and diff. **Pass = identical schema, identical column
   hashes, identical manifest counts, identical extracted report rows** for all four modules on both
   samples. The only allowed report difference is a new, separate "Phenotypes" section, and only
   when a phenotype module was selected.
3. Run it both ways: native modules **alone**, and native modules **together with** the ABO/APOE
   phenotype modules in the same run. The mixed run proves a phenotype module cannot perturb its
   neighbours (shared restoration context, manifest totals, report ordering).
4. Manifest totals: `total_variants_annotated` and `total_variants_restored` must equal the native-only
   baseline when phenotype modules are added. Phenotype calls are counted in a **separate**
   `total_phenotypes_called`, never folded into variant counts (same reasoning as the existing
   restored-vs-annotated split).

### Existing suites that must stay green

- CI set: `uv run --package just-dna-pipelines pytest just-dna-pipelines/tests/ -m "not integration and not slow and not download and not large_download" -vvv`.
  This includes `test_report_logic.py` (47), `test_consumer_handoff.py` (its
  "haplotypes lead is unsupported" assertion **changes deliberately**: rewrite it to "haplotype lead
  routes to the phenotype caller", and keep a companion asserting a haplotypes table *without*
  diplotypes/activity tables is still a recorded skip), `test_format_0_6.py`, `test_hf_modules.py`
  unit parts, and `test_restoration.py` synthetic parts.
- Local real-data tests: `test_restoration.py::test_the_real_lactose_module_restores_both_of_its_sites`,
  `test_report_logic.py` L895 (pharmgkb end-to-end, needs the M8UBMVNLH sample),
  `test_hf_modules.py::TestAnnotationWithRealData`, `test_module_roundtrip.py` (integration),
  `tests/test_lite_mcp.py`.
- `.ci/verify_annotation.py` after `uv run annotate data/input/tests/antku_small.vcf --user ci_test -m longevitymap`.

### Tests for the new path (runtime ground truth, not magic numbers)

- **Fixtures** compiled at test time from spec dirs under `just-dna-pipelines/tests/fixtures/phenotypes/`
  with `just_dna_compiler.compiler.compile_module` (copies of upstream `apoe_epsilon` and
  `hfe_compound_het`, a trimmed `cyp2c19` with *1/*2/*3/*17, plus our ABO and FUT2 pilots).
- **Synthetic sample frames** in the normalized-parquet schema (`chrom,start,rsid,ref,alt,GT,genotype`)
  covering every diplotype of each fixture. The expected phenotype is **derived** by enumerating the
  module's own diplotype table, not hardcoded, and the caller must return exactly that set.
- Boundary and negative cases:
  - APOE double-het unphased → `ambiguous` only if e1 is defined; otherwise `called e2/e4` with
    "alleles considered: e2, e3, e4".
  - HFE double-het unphased → `ambiguous` {compound het, cis} with "phase would decide". Phased
    `0|1`/`1|0` → trans row and `0|1`/`0|1` → cis row come only with Step 8 (phase sets).
  - Exome-scope callset (restoration disabled) with no records → `not_assessable`, never `e3/e3` or
    `O/O`.
  - A genotype no pair explains → `no_match`.
  - The ABO indel written as Ensembl's `133257520 G>GC` and as dbSNP/DRAGEN's `133257521 T>TC`
    must match the same haplotype.
  - A CYP2C19 SV allele → `not_assessable` for the candidates that need it.
- **Real samples** (skip if absent): APOE on Anton must equal what the caller derives from his two
  `GT` cells, i.e. `{e2/e4}` under the 3-allele module. ABO on Anton, dad, Livia and Borysova must
  agree with the per-site conclusions the existing weights-led `abo_blood_group` already renders for
  the same sample. That makes the old module the cross-check for the new one.
- Report render test: the new section appears with status badges, per-site evidence and coverage,
  and **native sections' HTML is byte-identical** with and without a phenotype module (after
  timestamp stripping).
