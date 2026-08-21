# What the authored surface offers that nothing reads yet

A hand-off from **just-module-creator** to the **just-dna-lite** consumer team, 2026-08-20.

## What this is, and what it is not

just-module-creator is the authoring half of the ecosystem: an MCP server plus skills that help
somebody write a module spec — `module_spec.yaml`, the CSVs, the sidecars — and get it compiled and
published. We own no schema and we annotate nothing. Which means we spend all our time on the far
side of a seam whose near side is yours, and we keep noticing the same thing: an author can fill a
column correctly, the compiler can validate it, the registry can serve it, and then no code ever
opens it.

While building our per-table dossiers we wrote that down systematically. Every dossier under
`just-module-creator/skills/module-tables/references/` ends with a `## Blanks for just-dna-lite`
section naming, with `path:line`, the read site that exists or the absence of one. This document is
that set collected in one place for the first time. It is a list of individually small asks, not a
review of your code.

**No numbered series behind it.** just-dna-lite has no `CONSUMER_SUGGESTIONS.md` intake, and setting
up a third repo's triage process is not ours to do — the split-inbox arrangement works for the format
tree and the registry because their maintainers run a loop, and nobody has agreed to run one here. So
there is no `S<n>` to reply to and nowhere structured for an answer to land. A reply by whatever route
suits you — an issue, a commit message, a conversation — is welcome, and a "we are not doing that" is
a perfectly good answer we will record on our side.

**How the set was gathered, so you can reproduce it rather than trust a number.** Grep the dossier
directory for the section heading:

```
grep -rl "Blanks for just-dna-lite" /data/sources/just-module-creator/skills/module-tables/references/
```

On 2026-08-20 that matched 25 files — 24 per-table and per-asset dossiers plus `LAYOUT.md`, which
covers the tree rather than any one table. Every section below comes from one of them. Re-run the
grep rather than quoting the number; dossiers get added.

**On the `path:line` citations.** They were read during our 2026-08-20 audit and they drift with your
next commit. Anchor on the symbol name, which we give alongside the line wherever one exists —
`_lead_join_strategy`, `load_module_credits`, `MODULE_TABLES` — and treat the line as a hint about
where to start looking. Bare `hf_logic.py`, `hf_modules.py`, `report_logic.py`, `io.py`,
`restoration.py` and the template mean
`just-dna-pipelines/src/just_dna_pipelines/annotation/`; `v1_port/` and `agents/` are the other
`just_dna_pipelines` subtrees. Anything in the format, compiler, enricher or registry is named as
such, because a few of these asks are not yours at all and we say so where that is the case.

---

## Start with `licensing.csv` / `sources.csv`, because it works

The licence sidecar is the most-read derived table in the ecosystem, and the read is a good one.
`load_module_credits` (`report_logic.py:1093`) scans `sources.parquet` through `ModuleTable.SOURCES`,
filters to `layer == "annotation"` — with a docstring citing the schema section that says why — and
projects `source`, `license`, `license_url`, `attribution`, `notice`, `dataset` and the three
tri-states without flattening them. `build_report_credits` (`:1136`, called at `:1315`) deduplicates
across every module in a report on `(source, license, attribution, notice)` and records which modules
pulled each one. The template renders the "Data sources and licences" footer at
`longevity_report.html.j2:942-976`, firing each Terms cell on `is sameas true|false` so a `None` never
renders as a permission. There are tests: `just-dna-pipelines/tests/test_report_logic.py:679, 706,
722`. Discovery sets `ModuleInfo.sources_url` from `manifest.artifact.files` at `hf_modules.py:241`,
probing only where there is no manifest. And your own publisher stopped dropping the file: since
`8f13142` (2026-08-18) `v1_port/publish.py:38` derives its allow-list from `ARTIFACT_PARQUETS` rather
than restating it.

**This is the point of leading with it.** That is a table read at the right layer, with the tri-states
preserved, gated on attestation rather than probed, and pinned by tests. It is what the rest of this
document is asking for, and it already exists — so the gap everywhere else is not "the consumer
ignores the format". It is that nobody asked for the other tables. Each ask below is roughly the size
of what `load_module_credits` already is: pick up a parquet the module already ships, join it on a key
it already carries, render it without collapsing a three-valued column. That is what turns this from a
list of complaints into a tractable set of small pieces of work.

Even here there are blanks, and they are the same shape as everywhere else:

- **`license_sha256` is unread.** It exists so that re-enriching turns an upstream terms change into a
  finding. Compare the incoming hash against the one recorded for the same `(source, layer)` on
  install or refresh and surface a diff. One string compare, and it is the only mechanism in the
  format that can detect a source silently rewriting its terms.
- **A module with no `sources.parquet` renders no credits section at all** — `{% if credits %}`,
  template line 942 — so "we could not establish the terms" and "no obligations" look identical.
  An explicit "no licence terms recorded" row, plus `manifest.sources.unknown_terms_sources` beside
  it, distinguishes them. The second case is the common one for the Gen-I ports.
- **`notice` is prose only.** Hoisting any module's `notice` into the report's own disclaimer block
  would let a restriction like PharmVar's *"not intended for direct diagnostic use"* survive into the
  artifact a reader keeps.
- **`redistribution` gates nothing at either end.** The registry-side half of this is theirs (RM27),
  and we have said so to them. The lite-side half: decline to include a module whose verdict is
  `false` in a report that will be shared, or say so at the top.

---

## Two shapes that recur, named once

Rather than repeat them in twenty sections:

**1. `ModuleInfo` has no field for any fact sidecar.** `MODULE_TABLES` (`hf_modules.py:36`) is
`["annotations", "studies", "weights", "sources"]`, `ModuleTable` is `:495-503`, and `ModuleInfo`'s URL
fields are `:225-241` — `lead_url`, `weights_url`, `annotations_url`, `studies_url`, `sources_url`.
`get_module_table_url` (`:513-547`) falls through to a bare `f"{info.path}/{table_name}.parquet"` guess
for anything else, which is the probe-instead-of-attest path `_attested_files` was written to end. So
`frequencies`, `gwas_effects`, `gene_metrics`, `gene_validity`, `clinical_assertions` and `literature`
cannot be fetched even by a caller that wants them. The ask is one gated field per table, on the same
`manifest.artifact.files` check `sources_url` already uses — and it unblocks six of the sections below
at once. It is the single highest-leverage item in this document.

**2. `manifest.stats.genes` is derived from `variants.csv` alone.** `compiler.py:3801` computes
`genes = sorted({v.gene for v in variants if v.gene})`, and the registry indexes `version_genes`
straight off it (`just-dna-registry .../db/repository.py:664`). So a module whose gene is stated only
in a PGx or binning table publishes `gene_count: 0, genes: []` and `registry_search(gene=…)` cannot
find it — measured on a CYP2D6 `activity_phenotype` module, on the corpus's own CYP2C19 example, and
on the shipped HTT manifest. **This one is not yours.** The fix is upstream in `variant_stats`, or
registry-side by indexing the PGx tables' `gene` column directly; we mention it because the symptom
shows up in your discovery path and it affects `copynumbers`, `repeat_alleles`, `allele_function`,
`haplotypes`, `diplotypes` and `pharm_variants` alike.

---

## The tables a report already almost handles

### `variants.csv`

The lead table, and the one path that is fully built. What is unread sits in its margins.

- **The callability quartet.** `requires_callable`, `callable_from`, `quality_from`, `min_quality` —
  grepped individually; the last two do not appear in consumer code at all, only in docs. The only
  quality gate is genome-wide and module-blind
  (`module_config.build_quality_filter_expr:91-121`, applied once at normalization), and
  `restoration.py:35-40` acknowledges the consequence: a `requires_callable` row's reference
  conclusion is asserted with no proof of callability. A reader could withhold that row's conclusion,
  or evaluate the pointer and the floor and mark the row *unknown* rather than dropping it.
- **No-calls are indistinguishable from silence.** `io.py:154-194` maps `GT="./."` to an empty list,
  so the row fails the list-equality join and vanishes; and `restoration.py:239-244` builds
  `called_sites` from `select("chrom","start")` without inspecting GT, so a `./.` record counts as
  *called* and suppresses restoration at that site. A third state and a count would cover both.
- **The genotype match is not phase-aware.** The VCF side is `.list.sort()`ed unconditionally and the
  module side is not, so an authored `A|G` matches nothing, silently. `phased` is read at exactly one
  place (`report_logic.py:453`) and the annotation engine deliberately does not read it
  (`hf_logic.py:127-131`). `v1_port/runner.py:246-286` has the same hole on the authoring side — it
  splits on `/` only, so a phased genotype becomes one token and the membership check passes
  vacuously. Either handle it or refuse a phased row loudly.
- **`locus_index` is read into the view model (`report_logic.py:751`) and never rendered or branched
  on.** `locus_count` is used correctly in restoration; the paths that count and classify rows do not
  gate on it. Use it or drop it.
- **`acmg_sf` and `actionability` are read nowhere.** They are the two columns by which a module
  offers a disclosure policy, and a reader has no way today to separate an incidental secondary
  finding from a requested one.
- **The 0.5 annotations dedup loses rows.** `report_logic.py:528-530` dedups on `variant_key` alone
  with `keep="first"`, while the docstring at `:488` names the 0.5 identity as
  `(variant_key, conclusion, negatives)` — so a poly-effect variant in a pre-0.6 artifact silently
  loses its second annotation's `gene`/`phenotype`/`category`. Fix it or state the loss.

### `studies.csv`

Carries the evidence behind a row: PMID, effect size and its measure and allele, p-value, and the
quoted passage.

- **`p_value_num` and `neg_log10_p` are written and never read — including by your own producer.**
  `v1_port/adapters.py:250-257` computes `_p_value_pair` and stores both; `report_logic.py:853-858`
  projects only the free-form `p_value` string. So the "Supporting studies" table lists in parquet
  order and a nominal `p=0.04` sits above a `5e-30`. Sorting on `neg_log10_p` and marking ≥ 7.3 as
  genome-wide significant is a sort key and a badge.
- **`provenance_quote` / `provenance_regex` reach no reader.** They are the only columns in the whole
  format that let a reader jump from a claim to the sentence behind it. Show the quote under the
  citation, with `literature.quotes_found` as a three-state badge — checked/found, checked/not found,
  could not be checked (null). A curator who does the most expensive authoring work in the format
  currently gets no surface for it, which is a large part of why 0 of 10 reference modules bother.
- **`effect_size` + `effect_measure` + `effect_allele` are unrendered.** The compiler warns when the
  allele is not at the locus (`compiler.py:2105`) and the report shows neither. Render
  `effect_size (effect_measure) relative to effect_allele` as one string, and withhold entirely when
  `effect_allele` is null — a magnitude with no referent inverts rather than breaks.
- **The subject-less study row has no home.** Rows carrying `variant_key = None` ground the *module*
  or a *bin boundary*; `load_studies_for_variants` filters `rsid.is_in(rsids)`, correctly, and drops
  them. A module-level "Evidence" section fed by null-key rows plus the bin `pmid`s would land them.
  `fmr1_cgg_repeat`'s ACMG threshold citation reaches no reader at all today.
- **No test covers the studies read path.** The coordinate branch recovered 34,697 rows and is pinned
  by nothing. One test against a real compiled module, asserting the coordinate branch and the
  null-key case.

### `literature.csv`

Per-PMID citation facts the enricher already resolved: `doi`, `pmcid`, `is_open_access`, `exists`,
`license`. No network needed at read time — it is in the artifact.

A join on `pmid` would turn the report's bare eight-digit number into a real reference list with DOI
and PMC links and an open-access badge. Note the deliberate limit: there is **no** `title`/`journal`/
`year` in this table by design, so a bibliographic citation string still needs a lookup — ask this
table for identifiers, not for prose. Beyond that: `exists is False` is a pinned fact meaning PubMed
has no record, which is a defect in the module rather than a coverage gap, and the compiler's warning
about it dies in a log — a per-module badge read off `manifest.literature.missing_count` (already in
`manifest_json`) plus a footnote on the offending row would surface it. `quotes_authored` /
`quotes_found` / `abstract_only_count` / `open_access_count` are all in `manifest.literature` and
unread; render the three-valued split rather than a percentage, because `quotes_found` null and `0`
are different claims. And if a consumer ever renders a `provenance_quote`, `commercial_use is False`
on the matching literature row is the flag saying that passage is publisher text under a no-sale
licence — today the report shows source-level rights from `sources.parquet` and would put a permissive
verdict beside a CC-BY-NC quotation.

### `module_spec.yaml` and the manifest blocks it produces

- **"Net weight" is not gated on `weighting`.** `report_logic.py:943-951` and `:1014` sum `weight` per
  module; `longevity_report.html.j2:813,859` render it as a stat box beside the weighting cell at
  `:929` — and the two are not wired to each other. Two modules' Net weight numbers appear side by
  side in one table with no scale caveat on either. The `weighting` block exists precisely to make
  that safe: gate the aggregate on it, or annotate the number.
- **`weighting` is dropped on the remote path.** `hf_modules.py:140` has the whole validated
  `ModuleManifest` in hand and takes only `artifact.files`; `read_module_provenance` then returns
  `(None, None, None)` for any HF-discovered module because `local_module_dir` is `None`. So every
  remotely-discovered module renders *Not stated* regardless of what its manifest says — the data was
  fetched and dropped three lines earlier. This is the cheapest fix in the document.
- **`genome_build` is dereferenced by nobody.** `cli_annotate.py:264-268` falls back to the literal
  `"GRCh38"` from the sample, and `agents/module_creator.py:277` hardcodes the same string into every
  scaffolded spec. A GRCh37 module joined against a GRCh38 VCF produces silently wrong rows, and the
  module has been declaring its build all along.
- **`authorship` is unread.** `Contribution.kind` exists so a consumer can route its scrutiny by it
  (`format .../manifest.py:1146-1168`). It is the one signal the format offers about how much a module
  was worked on and by whom, and a report cannot currently distinguish an AI-only module from one two
  medical geneticists reviewed.
- **The module-wide `license` is unread.** The report reconstructs licensing from `sources.parquet`
  (`report_logic.py:1093-1133`) and never reads `manifest.license`, so the author's own declaration —
  and any disagreement the compiler already warned about — reaches no reader.

### `README.md`

The module's prose: what it is, what it is not, how much to trust it.

No annotation-side reader renders it. A report can show a title, a gene list and a green
`compile_success`, and has nowhere to show *"these are candidates, most from a preprint"*. Surfacing
`manifest.readme` (or the downloaded `README.md`) wherever a module is presented to a person is the
ask. Two adjacent ones on the producing side: `v1_port/publish.py:39` omits `README_CANDIDATES` from
`_ALLOW_PATTERNS` while the manifest attests `manifest.readme`, so a fetched module gets a manifest
naming a file the repo does not have — and `verify_manifest(check_readme=True)` passes anyway, because
absent is not a failure. The one-line fix is written next door: import `README_CANDIDATES` as
`just_dna_enricher.upload` does. Separately, `agents/module_creator.py:576` still writes `MODULE.md`,
so every module that agent produces depends on the registry's rename to have a card at all and gets
`manifest.readme: null` if compiled locally. (The registry filed this against us; we have never had
that tool.) Finally, `manifest.readme.sha256` is per-version while the card is module-level
last-publish-wins, so a stale readme silently overwrites a current one — measured three times in the
corpus. Comparing the hash against version *n* at publish and saying "the prose did not change" out
loud costs one compare.

### `clinical_assertions.csv`

Per-ALT ClinVar assertions with their review status and star rating.

The parquet is already published to HF by `v1_port/publish.py:136`, but the table is not in
`MODULE_TABLES` (`hf_modules.py:36`) or `ModuleTable` (`:495-503`), so the annotator cannot see it —
a one-line list change plus an enum member, not a pipeline change. Then three renders:
`report_logic.py:625` prints `"ClinVar interpretation: Pathogenic"` with no indication whether that is
a 0★ single submitter or a 3★ expert panel, while `review_stars` and `review_status` sit in the
parquet keyed to the allele. `_effective_clin_sig` (`report_logic.py:300-321`) reads one flat authored
value; on `hboc_palb2` that value is `pathogenic` for `rs118203998` while the assertion table records
`G>A` as `uncertain_significance (0★)`. Join at position level — `chrom:start:ref`, as
`compiler.py:5776-5788` does, **not** on `variant_key`, which matched only 4 of 24 in measurement —
then select by the ALT the sample actually carries. And `_clin_sig_label` (`:324`) renders
`conflicting` as one more tier rather than as its own state; `hboc_palb2` carries one
(`rs878855123 C>T`, 1★) where the module's own row says `pathogenic`, so a disagreement inside ClinVar
is rendered as a settled call.

One caution for whatever consumes the manifest block: **do not average the stars.** Min and max are
published as two counts deliberately — *"published as the two counts rather than an average, which
would be a number describing no record"* (`format .../schema/manifest.py:441-443`) — and both are
`int | None` where `null` is not `0` (`compiler.py:4763-4767`).

### `pharm_variants.csv`

Drug-response rows drafted from ClinPGx. One live rendering bug and four small reads.

- **`alts` renders wrong today.** `report_logic.py:709` does `"/".join(row.get("alts", []) or [])`. On
  `weights.parquet` `alts` is `List(Utf8)` and that works; on `pharm_variants.parquet` it is `String` —
  measured value `'A,C'` — and `"/".join("A,C")` returns **`'A/,/C'`**, which is what reaches the
  report as *"Module alternate alleles"* and goes into the AI prompt. It is newly reachable: before
  format 0.6 the column did not exist, so `row.get("alts", [])` returned `[]` and rendered empty.
  Split on `,` yourself; do not assume a list. We have raised the type asymmetry upstream and the
  answer is that retyping `alts` to `List(Utf8)` is a breaking change reserved for 1.0, so the
  consumer-side split is the answer for the whole 0.x line rather than a stopgap.
- **The position join has never run on this family, and there is no longer a reason for that.**
  `_lead_join_strategy` picks `position` as soon as `chrom` is non-null, which a 0.6-compiled pharm
  module now is; that path joins on `(chrom, start, genotype)` and compares `ref`, and all types
  agree. But the comments still assert the family "reaches us with chrom/start null on every row"
  (`hf_logic.py:229-232`, `:296-299`). Recompiling the `pharmgkb` module against 0.6 and exercising
  the branch on an rsID-less VCF (DeepVariant output) would settle it; today a 1,482-row module
  annotates zero variants on such a VCF for no remaining reason.
- **`annotation_id` is a live ClinPGx accession on every drafted row and is read by nobody.** Linking
  it (`clinpgx.org/clinicalAnnotation/{id}`) gives a reader a route back to the curated record the
  module transcribed.
- **`phenotype_category` reaches the view model and organises nothing.** Efficacy, toxicity and
  metabolism rows for one drug are interleaved; sub-grouping or badging by category is what makes
  three rows about one variant+drug three different findings rather than repetition.
- **`positional_rows` / `positional_rows_placed` are unread on the consumer side.** The registry
  facets on them. Reading them from `manifest.json` at install time lets you warn that a module will
  annotate a fraction of its rows, instead of discovering it as a small join result. `None` means
  *not counted*, never `0`.

---

## The fact sidecars with no URL

Each of these needs shape 1 above — one gated `ModuleInfo` field — before anything else is possible.

### `frequencies.csv`

Population allele frequencies with `faf95`, `dataset`, and a three-valued `status`.

`faf95` is the statistic the ACMG BA1/BS1 rule uses. The compiler runs BA1 once at authoring time
against `clin_sig`, and warns correctly that the threshold is disease-specific — a consumer could
instead annotate each reported variant with its strongest available frequency and the group it came
from, so a report can say "this pathogenic call sits at faf95 0.06 in nfe". Key it at position level
exactly as `compiler._cross_check_frequencies` does (`chrom:start:ref`, not `variant_key`), and prefer
`faf95` over `max(allele_frequency)`. Two guards to build in at the same time, because both are
cheaper before the first read site than after: branch on `status`, where `not_covered` means *unknown*
and never absent-or-zero — a report saying "no gnomAD frequency" for a Y-PAR variant makes exactly the
false-absence claim that vocabulary member was added to prevent; and pin a test that `AN = 0` is not
read as zero, since `allele_frequency` is null in that case and a `fill_null(0)` anywhere in a polars
pipeline converts "no coverage" into "absent from the population". Also surface
`manifest.frequency.datasets` and `populations` on the module card before anything renders a count:
two modules in one report may carry different gnomAD releases and the report renders both as "the
frequency".

### `gwas_effects.csv`

GWAS Catalog associations with `beta`/`odds_ratio`, `units`, `effect_allele` and a three-valued
`status`.

The report already prints an instruction it cannot execute: `_weighting_summary` renders
`manifest.weighting.note` verbatim, and the one module that declares a weighting block sends the
reader to this table. Then: gate on `units` before any read site lands — branch on
`len(manifest.gwas_effects.units) > 1`, refuse to aggregate, render per `trait_efo_id` — because
otherwise the first read pools unpoolable betas. Render a null `effect_allele` as *direction unknown*,
never dropping the row and never assuming the ALT; the counts are published beside their complement
(42 of 195 rows on the reference module) specifically so that neither silent reading can happen.
Distinguish `not_found` (the Catalog was asked and holds nothing — a positive fact) from an absent
row. And surface `manifest.gwas_effects.datasets` wherever a magnitude is shown.

Worth knowing about the population that needs this table: across the 27 submitted bundles in the
registry's input directory, measured 2026-08-20, **0** carry `gwas_effects.csv` (the table did not
exist in their era), 27/27 carry rsIDs, and 27/27 fill every `weight` cell — 2439 of 2439, over 26
distinct values in `[-1.5, 1.5]`. The reference corpus authors `weight` zero times in 42 cells. So the
modules with hand-set weights are precisely the ones with no published effect to check them against.
Running the enricher's `gwas --no-study-facts` over those bundles at re-publish and surfacing the
resulting `units` set on the card would let a curator's 1.5 be read beside what was actually measured.
Budget it: 826 requests at `--no-study-facts`, unbounded with study facts on.

### `gene_metrics.csv`

gnomAD constraint (pLI, LOEUF, `oe_lof_lower`, `constraint_flags`) and ClinGen dosage ratings, per
gene.

Nothing fetches it (`hf_modules.py:206-243` builds four URLs and this is not one), so a report cannot
say "this truncating variant sits in a gene with LOEUF 0.64 and pLI ≈ 0" even when the module ships
exactly that. Join on `gene`, and render the LoF interval as an interval
(`oe_lof_lower ≤ oe_lof ≤ loeuf`) rather than one number. Two reading rules come with it. The ClinGen
`haploinsufficiency` / `triplosensitivity` codes are **non-ordinal** — `40` > `3` numerically, the
reverse in meaning — so display the terms and never sort on the code, with a blank rendered as *"not
evaluated"* rather than "no evidence". And read `dataset` per row before comparing two genes: one
table legitimately holds `gnomad_v4.1_constraint` and `gnomad_v2.1.1_constraint` rows for different
genes, whose pLI differ by orders of magnitude for the same gene (BRCA1: 1.55e-34 vs 5.52e-38). Key
any UI on `(gene, dataset)`, label the release, and refuse to rank genes across differing values. The
mixed-release trap is unexercised rather than solved, and the first consumer to join on `gene` alone
will hit it.

(Adjacent and not yours: the registry *computes* the ClinGen dosage ratings server-side under
`?pgx=true` — `services/enrich.py:1470`, `write=False` — and throws them away, so the one place they
are already derived is also where they are discarded. And `has_gene_metrics` is missing from
`_V017_COLUMNS` beside its four siblings.)

### `gene_validity.csv`

The curated gene–disease relationship: `classification`, `disease_id`, `moi`, `submitter`,
`classification_date`.

This is the sharpest gap of the fact tables, because the vocabulary is not a scale.
`ORDERED_GENE_VALIDITY` covers `limited → definitive`; `disputed`, `refuted` and
`no_known_disease_relationship` are the *opposite* claim. Today a module carrying a pathogenic PALB2
call whose gene–disease relationship a GCEP graded `definitive`, and one whose relationship somebody
refuted, render identically. Join on `gene`, surface the strongest assertion per `(gene, disease)`
with its submitter and date, sort with `vocab.ORDERED_GENE_VALIDITY`, and render the three negative
members as a **caveat**, never as a low rank. Two further reading rules: render
`classification_date` beside the verdict, and when two rows share `(gene, disease_id, moi, submitter)`
prefer the later date and say that you did; and never collapse `submitter` disagreement at read time —
a GenCC-sourced table legitimately holds `Definitive` from ClinGen and `Limited` from a laboratory for
one pair, which is the reason GenCC exists. Show the spread, or the strongest with a count of
dissenters.

(Registry-side, and we have said so there: `manifest.gene_validity.diseases` exists explicitly to be
indexed — *"so a catalog can index a module by condition without opening the parquet"*,
`format .../manifest.py:412-418` — and there is a `version_genes` table and a `version_categories`
table (`db/repository.py:1003-1016`) and no `version_diseases`. And `ModuleDetail` projects
`verification`, `weighting` and `gwas_effects` and not `gene_validity` (`services/catalog.py:354-362`),
so the richest fact block reduces to one boolean.)

### `pgs.csv`

A curated selection of published polygenic scores: `pgs_id`, `match_rate_floor`, `training_ancestry`,
`training_cohort`, `research_tier`, `group`, `trait_efo_id`.

This one is misrouted rather than unread. A pgs-led module is discovered as a module and then skipped
as `UnsupportedLeadTable`, because it is going through the genotype annotator when its content belongs
in the PRS workbench: feed its `pgs_id` column into `selected_pgs_ids` and the app can compute every
one of those scores. Today it will not, because the ids arrive in the wrong half of the process. Then:
pass `match_rate_floor` into `min_match_rate` and, where `weight_mass_coverage` is known, gate on C_wt
and say which metric you gated on — the module's only machine-readable "this result is invalid"
statement is currently discarded, and a score computed at 12% coverage is presented beside one at 98%.
Pass `training_ancestry` + `training_cohort` into `assess_ancestry_coherence` as the declared envelope,
and let `research_tier == "research_only"` suppress the absolute-risk estimate rather than caveat it —
those three columns exist so a consumer can *refuse*, and the refusal cannot happen today. Finally,
report a pgs-led module rather than dropping it: `generate_longevity_report` globs `*_weights.parquet`,
so a skipped module leaves no trace at all, not even a line saying it was skipped and why. A "scores
this module declares" section keyed on `group` / `trait_efo_id` needs no genotype join.

(A note on the C_wt half: the upstream ask is a coverage-metric column in the format. Please do not
fabricate one in `note` and treat it as structured.)

---

## The binning family: four tables, one code path

`activity_phenotype`, `copynumbers`, `heteroplasmy` and `repeat_alleles` share a single lookup rule,
so they share a single ask. `_lead_join_strategy` (`hf_logic.py:222-243`) has three strategies —
`position`, `rsid`, `unsupported` — and classifies the whole family `unsupported`; `hf_logic.py:302-304`
is the line that throws the module away, and `annotate_vcf_with_module_weights` raises
`UnsupportedLeadTable`. So these modules are authored, validated, compiled, published, installed, and
then skipped with a logged reason. They annotate nothing.

**The rule, fully specified in the compiler's `binning.py`:** group on the table's key fields plus
`trait_efo_id`; select the row with the greatest `measure_min ≤ x`; compare **in float32**, never with
an epsilon; read the group's *effective* tiling from `measure_tiling` (declared → else forced by a
fractional bound → else `binning.DEFAULT_MEASURE_TILING[kind]`) rather than from `measure_kind`. A
fourth strategy — call it `measure` — is the shape of the change.

**Three-valued, and the third state is the safety property.** A bin matched / no bin matched / the
measurement is absent. An absent measurement selects the `unresolved` sentinel row and **never** the
lowest bin. Nothing implements this today, so a consumer that later adds naive binning will report
"asymptomatic carriage" for a sample that was never measured, or Normal Metabolizer for a sample with
no diplotype — the precise failures the sentinel exists to prevent. There is a fourth state worth
having in the report-card shape from the start rather than retrofitted: a confidence interval that
*spans* bins. The house rule is withhold — do not pick among the bins, and do not fall back to
`unresolved`, which is a different claim. (Upstream has this deferred as RM56, so a reader that quietly
point-estimates makes their deferral invisible.)

**`source_field` / `source_element` are the extraction contract, and have zero occurrences in any
consumer repo.** They exist precisely so a reader does not have to guess which VCF field carries the
measurement. Two concrete consequences: for heteroplasmy the module says `FORMAT/AF` element
`annotated_alt`, and the guess that reads `INFO/AF` reports a carrier as asymptomatic on the strength
of a reference panel's allele frequency; for repeats the module says `FORMAT/REPCN` with `largest`,
and a hardcoded field takes the wrong element on a dominant locus, which is the exact wrong answer
RM54 was built to prevent. An author who correctly writes `source_element: largest_alt` has today
stated something no code will ever act on, which is indistinguishable from writing nothing.

The per-table specifics:

### `activity_phenotype.csv`

CPIC phenotype cut-points keyed `(gene, trait_efo_id)` — the bin edges that turn an activity score
into Poor/Intermediate/Normal/Ultrarapid. Beyond the shared rule, it has no home in the table
vocabulary at all: `get_module_table_url()` (`hf_modules.py:513-547`) cannot name it, so a consumer
that wanted to read it has no accessor to call, and a binning module gets a `lead_url` and no reader.

(One for us and the enricher rather than for you: the CPIC snapshot's `diplotypes.parquet` already
carries `(gene, diplotype, phenotype, activity_score)`
(`enricher/src/just_dna_enricher/cpic.py:628-641`) — which is what the reference example's author
grouped into four bins by hand — and `pgx_draft` reads that table and discards the score.)

### `copynumbers.csv`

CNV dosage bins. Two extras. **Coalesce the modifier dosage in the reader:**
`effective_modifier_copy_number` is a Python property, not a parquet column — the file carries
`modifier_cn` and `modifier_copy_number` side by side, one null (measured) — so a consumer reading
either column alone silently splits or drops a group. (`HeteroplasmyRow.variant_key` was promoted to a
stamped field for exactly this reason; this pair did not get that treatment.) And **decide `FORMAT/CN`
vs `INFO/CN`**: they differ by a factor of the ploidy, the module can already say which it means via
`source_field`, and today a correct annotation and a wrong-by-ploidy one are indistinguishable.

### `heteroplasmy.csv`

Mitochondrial heteroplasmy thresholds, grouped
`(gene, reference_sequence, tissue, variant_key, trait_efo_id)`. The extra axis is **`tissue`**, and it
is nearly free: the sample's tissue of origin is already in the annotate UI's own config and is simply
never joined to a bin row's `tissue`. `mt_heteroplasmy` puts the same variant's threshold at 0.3 in
blood and 0.4 in muscle, so ignoring it collapses two group keys into one wrong answer.

### `repeat_alleles.csv`

Repeat-expansion bins (HTT, FMR1). Beyond the shared rule and the `FORMAT/REPCN` extraction above, one
ask lands elsewhere and we flag it for completeness: the registry's `gather_pmids`
(`services/revalidate.py:130-141`) reads `studies.csv` only, while since 0.6 a threshold's citation may
live *only* on the bin row — so `revalidate --check-pmids` never verifies such a module's PMIDs. The
enricher's literature pass already reads both sites via `compiler.binning_citations` /
`load_binning_rows` (`enricher/literature.py:761-764`), so the two halves of the ecosystem disagree
about where citations live.

---

## The star-allele family: three tables, one caller

### `diplotypes.csv`

The conclusion table for star alleles: `(gene, hap_a, hap_b)` → phenotype, with `drug` and
`clinical_context`.

`_lead_join_strategy` classifies it `unsupported` and `hf_logic.py:602` skips it. **A reader needs no
VCF join at all** — it needs the caller's `(gene, hap_a, hap_b)` and a lexicographic sort, then one
lookup. Today a published CYP2C19 module annotates zero rows and appears in `skipped[module_name]`
with *"lead table has no populated coordinates and no rsid + genotype"*, which reads as a defective
module rather than as "this module answers a question we do not ask". `lnewco` (APOE ε) is the
concrete first customer and has been waiting since 0.5; `V1_PARITY.md` §5 records it as unbuilt with
"no schema decision outstanding".

Two reading rules to get right before the first reader ships rather than after, since nothing depends
on them yet. **Select on `drug` + `clinical_context`:** measured on the reference module, 1190 rows
over 595 pairs, half of them drug rows — so a naive reader double-reports every diplotype — and CPIC's
settings disagree (`strong` in `CVI ACS PCI`, `moderate` in `NVI`), so a reader that ignores
`clinical_context` picks a clinical setting on the patient's behalf. **And propagate the compiler's
phase-ambiguity warning, withholding on it.** It lands in `manifest.compilation.warnings` and no
consumer parses it. The compiler states the required behaviour: *"a consumer with unphased calls must
withhold rather than pick one; a phased consumer resolves it."* Without it, HFE `C282Y/H63D` versus
`C282Y-H63D`+`wt` — identical unphased genotype, opposite conclusions — will either manufacture an
at-risk finding or suppress one, silently. Note that the two warning classes are different asks: one
is resolved by phasing, one cannot be resolved at all.

### `haplotypes.csv`

The junction table: per-haplotype, the variants that define it. Positionally joinable, unlike
`diplotypes`.

`haplotypes.parquet` + `diplotypes.parquet` is a complete instruction set — the junction rows give the
per-variant genotype pattern, the diplotype table gives the conclusion — and the engine reads neither.
Three asks, in increasing size. **A robustness fix first:** make `_lead_join_strategy` check that the
columns its chosen join needs actually exist. Returning `position` on a table with no `genotype` column
produces a `ColumnNotFoundError` at collect time rather than a recorded skip — reproduced on a real
compiled `apoe_epsilon`. Requiring `{"chrom","start","genotype"}` for `position` degrades a
`haplotypes`-led module to the same recorded `unsupported` it already gets when its coordinates are
null. **Then a haplotype-aware join key:** the table states one `allele` per row, not a diploid
`genotype`, so the natural predicate is *"does the sample's call at this locus contain this allele"* —
which `compiler.resolution.hosting_verdict` already implements three-valued and which the enricher and
compiler both use for this table, so reusing it keeps `unknown` from collapsing into "no match".
**Then the caller itself.** Also worth reporting: which defined haplotypes no diplotype pairs — the
compiler checks "used but not defined" and not the reverse, and a consumer that emits `*40` from
`haplotypes.parquet` and finds no conclusion row has no way to say so. Measured: `*40`, `*41` in
`cyp2c19_star_alleles`.

### `allele_function.csv`

Per-star-allele function: `function_status` and `activity_value`.

There is a read here that needs **no caller and no new schema**: join `haplotypes.parquet` — which is
positionally joinable — to `allele_function.parquet` on `(gene, haplotype_name) → (gene, allele)` and
surface the function category alongside the variant. Today a user whose VCF plainly carries
`rs4244285` never sees "your `*2` allele has no function"; the fact sits in the parquet, unread. The
larger ask is the activity sum: accept a diplotype call — from PharmCAT, Aldy or Cyrius, or from a
`haplotypes.csv`-driven join — and use `activity_value` + `copy_number` to compute a per-sample
activity score, respecting the *cis* rule. A module can state everything a phenotype call needs and
the annotator still emits nothing for it.

---

## The tree, the provenance and the assets

### `resolution.csv`

The coordinate resolution table: `variant_key`, `genome_build`, `locus_index`, `status`,
`rsid_status`, `rsid_alternates`, `authority`.

- **Two comments assert a 0.5 fact that RM43 retired.** `hf_logic.py:231` and `:298` say the compiler
  applies `resolution.csv` to `weights.parquet` alone, which is why a `pharm_variants`-led module
  downgrades to an rsid join. Since format 0.6 the compiler fills `pharm_variants` / `haplotypes` /
  `heteroplasmy` from the same table, and the manifest publishes `positional_rows` /
  `positional_rows_placed` to say whether it worked. Gate the downgrade on those two counts (or keep
  the schema probe and fix the stated reason), so a 0.6-compiled PGx module gets the position join it
  now qualifies for — rsIDs are worthless on a DeepVariant VCF with an empty ID column, as that same
  function already notes.
- **`prune_unmatchable_rows` parses the table by hand.** `runner.py:251` uses `csv.DictReader` and keys
  on `rsid`, ignoring `variant_key`, `genome_build`, `locus_index` and `status` — so on a mixed-build
  or coordinate-authored spec it unions alleles across builds and cannot see a coordinate-keyed row at
  all. Switching to `load_csv_rows(path, ResolutionRow, ...)` and filtering on
  `genome_build == module build and status != "not_found"` reuses the compiler's own `_usable_loci`
  predicate, and `extra="forbid"` would catch a typo'd column the DictReader currently drops silently.
- **`rsid_status`, `rsid_alternates` and `authority` are unreadable downstream because the file is not
  published.** A report cannot say "this module's rsID has been merged away in dbSNP", "this label was
  a deterministic pick among equals", or "these coordinates came from ClinVar rather than Ensembl" —
  the first two exist nowhere else, the third only survives at module level via `sources.parquet`.
  This one is a decision rather than a patch: is any of the three worth a manifest field or a place in
  the publish allowlist? Today the answer is "silently unavailable", which reads to a user as "nothing
  to say".

### The `verification` manifest block

The record of which checks ran against the authored bytes, and whether the author declared them
final.

- **`closure` is unread — nothing distinguishes a finished module from a draft.** `hf_modules` decides
  what to load from `artifact.files` and never asks whether a human declared the bytes final. A
  half-authored module downloaded from HuggingFace annotates a genome exactly like a closed one. A
  line beside the annotation result, or a rank penalty in discovery, uses a field already parsed.
- **`checks[].skipped` is unread, so "not checked" and "checked, clean" are one state.** The `v1_port`
  `pathogenic` module carries `clinical_significance subjects=618629 findings=32` — 32 authored calls
  that disagree with ClinVar — and nothing between that manifest and a rendered report mentions it.
  A reader could decline to present a `clin_sig`-driven conclusion from a module whose record says
  `skipped: tautology` without also showing the reason.
- **`checks[].release` is unread, so no consumer can tell how stale a check is.** The record is the
  only place that answers currency. Warn when a module's `clinical_significance` was put against
  `clinvar_2026-06-27` while the pipeline's own snapshot is newer; today a module re-published
  unchanged for a year reads as freshly checked.

(And one that is ours, recorded here so the table is complete: a module authored through our plugin
attests 8 of 15 members, with `check_identifiers` and `check-acmg` the visible loss. Everything needed
is public and we know how to fix it.)

### `logs/`

The authoring transcript, published with the module and fetchable.

- **Nothing reads a published module's logs back.** `RegistryClient.logs(...)` — the endpoint, the
  client method and the fetch URL all exist and are exercised only by the registry's own tests.
  Offering the transcript beside the module card on the registry page is a call to a method that is
  already there. Today a module's provenance is fetchable and invisible.
- **Nobody calls `aggregate_logs`, so cross-version provenance is asserted and never assembled.**
  Union the logs across every version's manifest on the module-detail view. This matters more than it
  looks: `registry upgrade` deliberately does not carry logs forward (`upgrade.py:496-499`), so the
  union across manifests is the *only* thing that makes a v3 module's provenance include v1's.
  Without a caller, "v3 provenance = v1+v2+v3" is a claim no code makes true.
- **The Module Manager writes `v<N>.log` and never `logs/<role>.log`, though it runs a named team.**
  Fanning `RunLog` out per member — PI at `logs/pi.log`, each researcher at `logs/researcher-<n>.log`,
  the reviewer at `logs/reviewer.log` — is the shape `schema/tests/test_logs.py` was written against.
  **Blocked at two hops:** `state.py:5622` and `module_registry.py:158-161` both iterate `iterdir()`
  with `is_file()`, so a `logs/` subtree is silently dropped before publish. Both need `rglob`. Today
  the reviewer's verdict is buried in a 1.7 MB aggregate nobody will open.
- **A published transcript is unreviewed and can carry anything.** The real transcripts contain the
  full team system prompt, every model id, and the user's local upload paths, at up to 4 MB per
  version — and a user clicks Register and ships it. A pre-publish log review step is the ask. (This
  is the one item here we would put above its neighbours on urgency grounds; it is a privacy
  exposure rather than a missing feature.)
- **`RunLog` stamps naive local time** (`module_creator.py:96-101`). ISO-8601 UTC in the header makes
  two logs from two machines comparable and sorts against every other timestamp in the ecosystem.
- **The log's counts can contradict the module and nothing notices** — v1_port hit this and patched it
  with `_restate_log_counts`. Emitting the machine-checkable half of a run as `provenance.json`, which
  has a schema and a per-variant grain, and keeping the log for prose, converts an unverified
  assertion into a manifest block a consumer can read.

### `logo.png`

- **Trust `manifest.logo` and stop probing.** The comment at `hf_modules.py:237-238` says a manifest
  "says nothing about" the logo. That was true when only `ARTIFACT_PARQUETS` was attested;
  `manifest.logo` carries `{name, sha256, size}` and has since format 0.5. Probing can stay as the
  fallback for manifest-less sources, but where a manifest is present it names the file and the digest
  is one field away. Today a served logo is unverified while its hash sits unread.
- **`_autocrop_whitespace` destroys alpha.** `module_creator.py:474` does `.convert("RGB")`, so the
  generation path cannot emit a transparent logo while every published logo is RGBA. Convert to
  `RGBA`, take the bbox from the alpha channel where one exists, and fall back to the white-threshold
  path only for opaque images. It should also refuse — or say so — when the field is darker than its
  235 threshold, which is the `recent_longevity_2024` case where the crop is a measured no-op.
- **The logo agent is not asked for the house style.** Its prompt (`agents/prompts/pi.yaml:226-239`,
  `module_creator.yaml:196-208`) asks for none of the four invariants the published family shares —
  ring frame, corner medallion, in-ring title, transparency — and actively asks for a gradient the
  family never uses. Our dossier at `skills/module-tables/references/logo.md` carries a drop-in prompt
  block if that is useful.
- Worth noting the fallback chain is untested in practice: with the modules currently published and no
  logos among them, `logo_url` is dead code in production and the icon fallback is the only path
  anyone has exercised end to end since the mirror.

### The tree itself

From `LAYOUT.md`, and mostly reassurance rather than asks:

- **`derived/` needs no consumer support and no folder walk.** `layout.sidecar_candidates` accepts a
  sidecar at the root or under the folder, so a consumer reading the flat root reads everything.
  Noted here so nobody adds a walk that is not needed.
- **`manifest.derived[]` is the list to check** before assuming a downloaded module carries its
  sidecars. A consumer wanting frequencies from a module published before registry 0.17 will not find
  them attested.
- **`logs/` paths are verbatim in the manifest.** A consumer that rewrites or relativises them breaks
  the attestation.

---

## Why the aggregate is the argument

Individually, none of these is important. A sort key on a p-value. A `ModuleInfo` field. A `,` instead
of a list. A manifest block picked up three lines earlier in a function that already has it in scope.
Any one of them could sit in a backlog forever without anything visibly going wrong, and several are
latent rather than live — no consumer exists yet to get them wrong.

Together they are a different claim. The format has an authored surface — the columns an author fills
by hand, the pointers they state declaratively, the three-valued vocabularies that exist so a reader
can say *unknown* — and today most of that surface reaches no reader. The consequence is not that
reports are wrong. It is that authoring effort has no return: a curator who locates a quote in a
fulltext, states which VCF field carries the measurement, records that a gene–disease link was
*refuted*, or declares a match-rate floor, produces something indistinguishable from a curator who
left the cell empty. That is visible in the corpus. Zero of ten reference modules author a
`provenance_quote`. The pointer columns have zero occurrences in any consumer repo. Whole table
families are published, installed, and skipped with a logged reason.

`licensing.csv` is the counterexample, and it is why we think this is tractable rather than
structural. One table got asked for, and got a real read: filtered at the right layer, tri-states
preserved, gated on attestation instead of probed, pinned by tests, and fixed on the publish side when
the measurement showed files were being dropped. Nothing about that was hard. It just had a consumer.

The two shapes at the top of this document are where we would start, because each is one small change
that unblocks several sections at once — a gated `ModuleInfo` field per fact sidecar, and a fourth
`_lead_join_strategy` branch for the binning family. After those, the individual reads are mostly a
join and a render. And the ordering is genuinely yours to set: we are the authoring side and we do not
know your constraints. What we can offer is that every item above has the evidence attached, so
picking one does not start with a search.

Happy to talk through any of it, to re-measure anything that looks stale, or to be told which of these
are wrong. We would rather hear that than keep telling authors to fill a column.

---

# Addendum, 2026-08-21 — the one command that would let an author try a module before publishing it

A separate ask from everything above, and a much smaller one. This is not about a column nothing
reads; it is about a function nothing exposes.

## What we were doing

Adding a skill to just-module-creator that teaches an author to run a freshly compiled module against
their own VCF **without** publishing it to either registry instance. We think this matters for the
authoring loop: today the shortest honest path from "it compiled" to "it matched something real" runs
through a polygon publish, which means a namespace, a token and a name you have to live with. Most
authors should be able to see their module annotate a genome before they decide it is worth a catalog
entry at all.

## What we found, and it is good news

The mechanism already exists and works. `module_registry.register_downloaded_module(module_dir)` does
exactly the right three things — `_ensure_local_source`, display metadata out of `manifest.json`,
`refresh_module_registry()` — and deliberately does not recompile, which is what preserves the digest
the author actually tested. Its docstring explains why, and the reasoning is correct.

We verified the whole path end to end against `just-module-creator/assets/fto_bmi`, compiled by
`just-dna-compiler 0.6.1` through our own `compile_module` tool, using a scratch `JUST_DNA_MODULES_YAML`
and `--no-sync` so nothing in your tree was touched:

- discovery found it: `lead = weights`, `url = file:///…/fto_bmi/weights.parquet`
- `_lead_join_strategy` → `('position', 'lead table carries coordinates')`
- `scan_module_table` collected 3 rows
- `read_module_provenance` → `('1.0.0', 'sha256:c3d633f0…', None)`

So a module this plugin compiles is discoverable and annotatable **as-is**. Nothing needed adjusting.
One incidental correction to something we had assumed from your `spec_version` fallback: compiler 0.6.1
does fill `identity.version`, so the fallback did not fire here.

## The ask

**`register_downloaded_module` has no CLI wrapper.** Its only caller is
`webui/src/webui/state.py::RegistryState._do_install`. `pipelines module` offers `validate / register /
unregister / list-custom / compile / reverse`, and `register` takes a *spec* directory and recompiles —
which produces a different `artifact.digest` from the one the author compiled and tested.

So the documented route for "I have a compiled module directory, register it" is either the web UI or a
hand-written `python -c`. Our skill currently ships the `python -c`, which we would rather not do: it
reaches past your CLI into an internal function, and it will break silently if the signature moves.

Something like `pipelines module register-compiled <dir> [--name NAME]` would close it. Copy into
`get_registered_modules_dir()` if the directory is not already there, then call the existing function.
No new logic — we are asking for the front door to a room that is already furnished.

## Two things we would have wanted to be told

Both are notes for your docs rather than code changes, and both cost us a probe to find:

1. **When a readable `manifest.json` is present, `_find_lead_table` consults `artifact.files` and never
   the filesystem** — the `continue` in the `attested is not None` branch. That is the right design and
   `_attested_files`' docstring explains it well. The consequence worth writing down is that a manifest
   whose attested list omits the lead parquet makes the module **invisible**, while `list-custom`
   (which probes the filesystem via `has_lead_table`) still lists it. The two surfaces then disagree
   and neither says why. A partial manifest is strictly worse than no manifest, which falls back to
   probing.

2. **Name collisions resolve to the earliest source and are silent.** `discover_all_modules` does
   `if name not in all_modules`, the HuggingFace collection is source #1 in the shipped `modules.yaml`,
   and `_ensure_local_source` appends. A locally registered module named after a published one is
   shadowed with no warning — we measured ten published names present by default. A `log_message` at
   `warning` when a later source supplies a name already taken would make this self-diagnosing.

Neither is a defect. They are both "we had to read the source to know", which on our side we treat as a
documentation finding, so we are reporting them the same way here.

## Two doc/code disagreements, noted in passing

- `docs/AI_MODULE_CREATION.md` says `register` compiles into `data/output/modules/<name>/`; the code
  writes to `get_registered_modules_dir()`, i.e. `data/interim/registered_modules/<name>`.
- `docs/MODULE_MARKETPLACE_SPEC.md` says installs "reuse the existing `register_custom_module`
  write-and-refresh path"; `_do_install` uses `register_downloaded_module` instead — which is the
  better choice, so the code is right and the sentence is stale.

`MODULE_MARKETPLACE_SPEC.md`'s *"Client verify-then-install flow — specified, NOT implemented"* is, by
contrast, accurate and current, and we quote it in our skill rather than paraphrasing it: our authors
are told in as many words that installing locally verifies nothing and that a clean annotation run is
not evidence a module is correct.

As before: no numbered series, nowhere structured for a reply to land, and "we are not doing that" is a
fine answer we will record on our side.
