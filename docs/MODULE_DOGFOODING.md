# Dogfooding the module-creator plugin against the ten v1-port modules

**Run date 2026-08-21.** A revision/curation pass over every module in
`data/interim/v1_port/`, driven entirely through the installed plugin surface — its skills and its
MCP tools — rather than through this repo's own `pipelines v1-port` code. The question is not whether
the modules are good. It is **whether the tooling can tell you that**, and what it leaves you to
work out on your own.

## The surface under test

| Component | Version | Note |
|---|---|---|
| `just-module-creator` plugin | **0.18.0** (`@dna-seq`, user scope, installed 2026-08-21) | `JMC_MODE=essentials`; 20 skills + MCP server |
| `just-dna-format` | 0.6.6 | matches the plugin's own pin |
| `just-dna-compiler` | 0.6.6 | |
| `just-dna-enricher` | 0.6.6 | |
| `just-dna-registry` | 0.18.2 | |

A second, **stale** copy of the plugin is also installed — `just-module-creator@just-dna` **0.7.0**,
project scope, pointed at the `/data/sources/just-module-creator` checkout, carrying only two of the
twenty skills. Everything below was run against 0.18.0. See **D1**.

## How the pass was run

The ten modules were **copied** to `data/interim/_dogfood/` and every write-capable tool was pointed
at the copy. `data/interim/v1_port/` is deliberately held at its 0.5-era state (AGENTS.md: it is what
keeps the mixed-era read paths under live test), and half the plugin's verbs — `enrich_module`,
`compile_module`, `record_override`, any refresh — write into the spec directory they are given.

**No registry writes were made**, not even a rehearsal publish to the polygon. Reads
(`registry_check`, `registry_validate`, `compare_to_published`) only.

**This pass produces findings, not revisions.** Rebuilding and republishing the ten is the
maintainer's call and is already documented in [MODULE_RELEASE_0_5.md](MODULE_RELEASE_0_5.md).

Findings carry stable `D#` ids. Severity is about *the tooling*, never about the module.

---
## D1 — two plugin versions are installed and nothing in the plugin surface says which one you are using

**Severity: high (blocks every other finding from being filed correctly)**

`just-module-creator` is installed twice on this machine:

| Marketplace | Version | Scope | Skills shipped |
|---|---|---|---|
| `@dna-seq` (github `dna-seq/dna-seq-claude-marketplace`) | 0.18.0 | user | 20 |
| `@just-dna` (directory `/data/sources/just-module-creator`) | 0.7.0 | project | 2 |

The 0.7.0 entry is a dev checkout registered as a marketplace and pinned at a commit from
2026-08-11. Its `skills/` has only `create-module` and `find-evidence`; the eighteen `module-*`
skills do not exist in it.

Nothing the plugin exposes answers *which of these am I talking to*. The MCP server's instruction
block states the **library** versions it was built against ("just-dna-format 0.6.6 and
just-dna-compiler 0.6.6; older than yours means a stale process") — a genuinely good idea — but not
its own plugin version, which is the thing that differs between the two installs. Resolving it
required reading `~/.claude/plugins/installed_plugins.json` by hand.

**What the tooling should do:** report the plugin version in the MCP instruction block beside the
library versions, or expose it from any tool response. It is one string and it is the first thing a
bug report needs.

*(A related trap: the two installs disagree about the skill roster, so a session that resolves the
0.7.0 one will be told by `create-module` to load skills that are not installed.)*

---

## D2 — the VRS-unverifiable warning is emitted per allele, and the module with **better** data gets the flood

**Severity: high · Found on: superhuman, coronary vs cardio, cancer, longevitymap**

`validate_module` on `superhuman` returns **85 warnings**, of which **80** are one line per allele:

> `rs56185968 allele GTGTGTGTGTGTGTGTGTGTGTGTG: vrs_id ga4gh:VA.sfCbe… could not be verified —
> GTGTGTGTGTGTGTGTGTGTGTG>GTGTGTGTGTGTGTGTGTGTGTGTG is not a single-base substitution, so
> justifying it needs the reference sequence — minted upstream by the enricher, not recomputable
> here; carried unverified.`

`cardio` — 57,055 variants, **26,810 of them indels** — returns **seven** warnings total, and the
same underlying fact arrives as a single aggregated line: *"VRS allele identity covers N/M
allele(s) in resolution.csv (N%)"*.

The two paths are `_verify_vrs_ids` and `_vrs_coverage` (`just_dna_compiler/compiler.py:2648`,
`:2680`), and which one you land in is decided by **whether `resolution.csv` carries a `vrs_id` at
all**:

| module | resolution rows | with `vrs_id` | indel rows | indel rows **with** `vrs_id` | warnings |
|---|---|---|---|---|---|
| superhuman | 101 | 101 | 47 | **47** | 85 (80 per-allele) |
| cardio | 57,595 | 30,785 | 26,810 | **0** | 7 (1 aggregated) |
| longevitymap | 528 | 519 | 0 | 0 | 9 |

An id that is **absent** is "nothing to check" and gets counted into one tidy coverage line. An id
that is **present but not offline-justifiable** gets its own warning. So the module whose enricher
minted more identities is the one that becomes unreadable — the noise is inversely proportional to
how well-resolved the module is.

Both readings are the *same fact*: an indel identity cannot be justified without the reference
sequence. One of them is a sentence; the other is eighty.

**What the tooling should do:** aggregate `_verify_vrs_ids` the way `_vrs_coverage` already
aggregates — *"47 allele(s) carry an enricher-minted `vrs_id` this tier cannot justify offline
(indel/MNV); ids carried unverified"* — with the full list behind a flag or in a sidecar. The
grouping logic already exists in the same file.

---

## D3 — `warnings` is one flat list with no severity, no grouping and no cap

**Severity: high · Found on: every module**

`validate_module`, `compile_module` and `registry_check` all return `warnings: [str]`. There is no
`kind`, no code, no count, no "and 46 more". Consequences measured here:

- On `superhuman` the three warnings an author can actually act on — 8 heterozygous, 31 homozygous
  and 46 reference-homozygote genotypes with no row — are items **83, 84 and 85** of the list,
  after eighty they cannot act on at all.
- The response is large enough that reading it costs real context. `compile_module` on `superhuman`
  (a **190-row** module) returned ~14 kB of warnings. This is the smallest module family in the
  repo.
- There is no way to ask for the summary. `strict=false` changes what is an *error*, not how much
  is printed.

Every skill in the plugin insists that warnings on a green run are the real output
(`module-status`: *"a check that could not run is not a check that passed"*; `module-compile`:
*"Read `warnings`"*). That instruction is only followable if the list is readable.

**What the tooling should do:** return warnings as objects with a stable `code` and a `count`, and
collapse repeats by code. A `warnings_summary: {code: count}` beside the list would be enough and
breaks nothing.

---

## D4 — nothing distinguishes a warning an author can clear from one they cannot

**Severity: medium · Found on: superhuman, coronary, pharmgkb, cardio, cancer**

The VRS warnings say it themselves — *"minted upstream by the enricher, **not recomputable
here**"* — so no edit to the spec directory can clear them. They sit in the same list, at the same
level, as *"8 genotype(s) at 4 site(s) have no row"*, which is a curation gap the author is the only
person who can close.

The compiler's own source has the distinction and applies it to *severity*, not to
presentation — `compiler.py:2634`: **"a finding no authored edit could clear is not a `strict`
matter."** That reasoning stops one step short: such a finding is also not an *author-facing* matter,
and it is presented as one.

**What the tooling should do:** carry the existing `blame` discriminator out to the response —
`actionable: true|false`, or split `warnings` from `carried` / `notes`.

---

## D5 — a module can have no weights at all and nothing anywhere says so

**Severity: high · Found on: superhuman**

`superhuman` has **190 rows and an empty `weight` on every one of them**, and no `weighting:` block
in `module_spec.yaml`. It passes `validate_module(strict=true)` clean, compiles green, and the
compile reports `weights_rows: 190`. The artifact is called `weights.parquet` and contains no
weights.

Nothing in the surface remarks on this — not validate, not compile, not `registry_check`. The
`module-weights` skill is explicit that **no tool fills `weight`** and that this is deliberate. The
gap is that no tool *notices* it either, so "the author deliberately authors none" and "the author
forgot" are indistinguishable from outside — and `weighting:` exists precisely to tell them apart.

Downstream this is not cosmetic: this repo's report sums `weight` per module into `total_weight`,
so `superhuman` renders 0.0 for every category while displaying 190 findings.

**What the tooling should do:** warn when `weight` is empty on **every** row and `weighting:` is
absent — *"this module authors no weights and does not declare that it authors none"*. The same
check with the opposite sign (weights present, `weighting:` absent) is the one `module-weights`
already argues for.

---

## D6 — `category` is empty on five of six curated modules and nothing asks

**Severity: medium · Found on: coronary, lipidmetabolism, superhuman, thrombophilia, vo2max**

| module | rows | rows with `category` |
|---|---|---|
| longevitymap | 1039 | 1039 |
| coronary | 81 | 0 |
| lipidmetabolism | 45 | 0 |
| superhuman | 190 | 0 |
| thrombophilia | 24 | 0 |
| vo2max | 39 | 0 |

`validate_module` reports `categories: []` in `stats` for all five and treats it as unremarkable.
`category` is the column the consumer groups a report's sections by, so an empty one collapses a
module to a single unnamed block.

This is the general shape of the problem `module-curate` describes as *"cells only a pilot can
settle"* — but there is no inventory anywhere of **which optional columns this module left empty**,
which is the one thing a revision pass is for. `stats` reports fill for `genes`, `clinvar`,
`pathogenic` and `benign` and for nothing else.

**What the tooling should do:** put a per-column fill count in `stats` — it is one pass over rows
the validator has already loaded, and it turns "what is there to curate" from a question into a
table.

---

## D7 — for a `pharm_variants`-led module the headline stats are all zero

**Severity: medium · Found on: pharmgkb**

`validate_module` on `pharmgkb` (1,482 drug-response rows) returns:

```json
"variant_count": 0, "unique_rsids": 0, "study_count": 0,
"table_rows": {"pharm_variants.csv": 1482}
```

The real count is in `table_rows`; the four scalar counters are `variants.csv`-shaped and report
**0 rather than null** for a module that has no `variants.csv`. `unique_rsids: 0` is simply wrong —
`pharm_variants.csv` is keyed on `rsid` and has 1,482 of them.

This is the same tri-state rule the plugin enforces everywhere else, broken in its own output: the
MCP instruction block says *"`null` and `unknown` never mean pass"*, and `module-compile` says
*"**null never means zero**"*. Here zero is being used to mean "not applicable".

**What the tooling should do:** `null` for a counter whose table is absent, and lift the lead
table's row count into a `row_count` that is populated whatever the family.

---

## D8 — a 1,482-row pharmacogenomics module with zero citations passes strict validation silently

**Severity: medium · Found on: pharmgkb**

`pharmgkb` has no `studies.csv` and `study_count: 0`. Every one of its 1,482 rows makes a clinical
claim about a drug ("*may have an increased risk of myopathy when treated with atorvastatin*"), and
none of them carries a receipt.

`module-status` states the rule — *"**No `studies.csv` beside a `variants.csv` is a hole**, not a
choice"* — and then scopes it to `variants.csv`, so a PGx module falls outside it and nothing fires.
The `pharm_variants.csv` schema has **eight columns** (`rsid, genotype, gene, drug,
phenotype_category, annotation_id, evidence_level, conclusion`) and **no PMID column at all**, so
there is nowhere to put one even if an author wanted to.

`evidence_level: 1A` is carried, which points at ClinPGx's own grading — but that is a pointer to
somebody else's evidence, not a citation, and nothing in the format connects the two.

**Undecided case, not a bug:** it is genuinely unclear whether a drafted-from-ClinPGx module is
*supposed* to carry citations or whether `annotation_id` + `evidence_level` is the intended
provenance. Whichever it is, no skill says so. `module-draft` and `module-tables` both stay silent
on the question.

---

## D9 — `IFNL3;IFNL4` is counted as a gene

**Severity: low · Found on: pharmgkb**

`validate_module` reports `gene_count: 33` for `pharmgkb`, and the gene list contains all three of
`"IFNL3"`, `"IFNL4"` and `"IFNL3;IFNL4"` — the last of which is a two-gene cell from the upstream
ClinPGx export (33 rows carry it), counted as a distinct third gene.

Nothing validates gene symbols against any vocabulary, and nothing flags a delimiter inside a
single-valued cell. Low impact on its own; it matters because `genes` is one of the fields the
registry surfaces for search.

---

## D10 — the compiler sweeps files into the artifact that the registry's roster will drop

**Severity: medium · Found on: all ten**

Compiling `superhuman` produced an output directory containing `logo.png` and `v1_port.log`
alongside the five parquets. Neither name is in
`just_dna_registry.specfiles.RECOGNIZED_SPEC_FILES`, which is the roster `module-status` points at
as authoritative and which contains 24 names — no image of any kind, and no log.

`module-status` states the consequence itself: *"an unrecognised name is tolerated by the compiler
and dropped by the next server-side rebuild, so a file somebody invented beside the spec is a file
that will not survive a re-publish."* Two of the things that fall in that gap are not invented:

- **`logo.png` is consumed by this repo**, in the module card grid and in the report. Every one of
  the ten v1-port modules ships one.
- **`v1_port.log`** is a build log this repo writes. It contains nothing secret here, but the rule
  the skill states — *"logs are swept into every compile with no opt-out"* — combined with a roster
  that does not recognise them means a log is both unavoidably published and unreliably retained.

**What the tooling should do:** decide `logo.png` one way or the other and say which — either add it
to the roster or state that module artwork is a consumer-side concern that does not travel. Right
now it travels through a compile and does not travel through a rebuild, which is the worst of both.

---

## D11 — the documented top-level imports of `just_dna_compiler` do not exist

**Severity: low (documentation) · Found while working around D3**

`just_dna_compiler.__init__` exports **nothing** in 0.6.6 — `dir(just_dna_compiler)` is empty and
`from just_dna_compiler import validate_spec` raises `ImportError`. The working import is
`from just_dna_compiler.compiler import validate_spec`.

This repo's own `CLAUDE.md` documents the top-level form (*"`just-dna-compiler` … `validate_spec`,
`compile_module`, `reverse_module`"*), so the drift is on both sides. Corrected in this repo as part
of this pass.

---

## D12 — `version: null` and `authorship: []` pass strict validation without comment

**Severity: medium · Found on: coronary, lipidmetabolism, longevitymap, superhuman, thrombophilia, vo2max**

All six curated ports declare `version: null` and `authorship: []`. All six validate clean and
compile clean.

`module-status` lists `authorship:` among the things *"declared once at birth and never
re-asked … so an absence here is an absence for the module's whole life"*, and `module-close` owns
the methodology block. Neither the validator nor the compiler mentions either absence — the only
lifecycle warning that fires is the closure one.

The consumer side makes the cost concrete: this repo's report falls back from `identity.version` to
the authored spec version, so all six render **"Not stated"** in the *Modules in this report* table.
A reader cannot tie a saved report to the module version behind it, which is the exact question that
table exists to answer.

**What the tooling should do:** fold both into the existing closure warning, which is already the
"this module has not said whether it is finished" message. Three absences, one sentence.

---

## D13 — a 23-allele repeat locus authored as one variant row is not routed anywhere

**Severity: medium · Found on: superhuman**

`superhuman` authors `rs56185968` (NTRK1) as a single `variants.csv` row with **no coordinates**,
genotype `G/G`, and a conclusion about congenital insensitivity to pain. Enrichment resolved it to a
`GT`-repeat locus and expanded it to **23 alleles** — `G`, `GTGTG`, `GTGTGTG`, … up to a 45-base
allele — which is where 22 of superhuman's 80 VRS warnings come from.

`module-tables` states the routing rule clearly: *"A quantity with a threshold (repeat count, copy
number, heteroplasmy fraction, activity score) is a binning table, not a variant row"*, and
`repeat_alleles.csv` is in the roster for exactly this. Nothing detects that a row has landed in the
wrong family. The signal is unambiguous and already computed — a resolved locus whose ALT set is a
tandem ladder — and it arrives instead as 22 individually unactionable identity warnings.

Whether *this particular row* should be re-filed is a curation judgement and is left to the
maintainer. The finding is that the tooling has the evidence and does not raise the question.

---
## D14 — `lint_rows` finds nothing wrong with a conclusion that describes a different genotype

**Severity: high · Found on: thrombophilia (and the same shape in coronary, lipidmetabolism, vo2max)**

`lint_rows` was given twelve real `thrombophilia` rows and returned **`errors: 0, warnings: 0`**. Its
entire output was six `info` notes naming the redundancy-bearing columns, and six `alterations`
reporting that `-2.0` was normalised to `-2`.

Four of those twelve rows say something that contradicts the row they are on:

| rsid | `genotype` | `state` | `conclusion` (verbatim) |
|---|---|---|---|
| rs1799963 | `A/A` | risk | "**GA** carriers have 6.74x risk of thrombosis" — and the `A/G` row above it already says "GA carriers have 2.8x" |
| rs2519093 | `C/T` | risk | "**TT** genotype is associated with an increased venous thromboembolism risk" — identical to the `T/T` row's text |
| rs6025 | `T/T` | risk | "**CC** genotype is NOT associated with increased risk. AA carriers have 11.4x…" — a homozygous-alt row opening with the reference homozygote's sentence |
| rs1799889 | `G/G` | **risk** | "…The risk of blod clotting and coronary arthery disease **is not increased**." — the state and the prose disagree |

A fifth class is subtler and worth separating: `rs6025 C/T` reads *"CA carriers have 3.5-4.4x risk"*.
F5 Leiden is `1691G>A` in the legacy orientation and `C>T` in the dbSNP one, so this is not a
copy-paste slip — it is **the conclusion using a different allele naming than the `genotype` column
on the same row**. A reader sees `C/T` in one cell and prose about "CA carriers" in the next.

`conclusion` is the single most reader-facing cell in the format — it is literally the sentence a
person reads about themselves — and **nothing checks it against anything, including the other cells
on its own row**. `describe_table` confirms the design: `conclusion` is `required: true`,
`redundancy_bearing: null`, and absent from `attestation_bearing`.

Three of the four checks above need no external source and no judgement:

1. the conclusion names a genotype token (`GA`, `TT`, `CC`) that is not this row's genotype in either
   orientation;
2. two rows at the same rsID carry byte-identical conclusions under different genotypes;
3. `state` is `risk`/`protective` and the conclusion contains a negation of it.

**What the tooling should do:** add them to `lint_rows` at `warning` level. `module-curate` names
the conclusion as a pilot-only cell, which is right — but "only a human may write it" is not the same
as "nothing may check it", and the plugin currently treats them as the same.

*A note on `alterations`:* `lint_rows` also echoes the **entire input back** as `normalized_csv`.
On a 12-row slice that is fine; on longevitymap's 1039 rows it doubles a response that is already the
largest thing the tool returns. It should be opt-in.

---

## D15 — the plugin cannot see the channel these modules are actually published on

**Severity: high · Found on: all ten**

`compare_to_published`, `registry_is_published` and `registry_search` all answer about the **module
registry**. The production registry holds **8 modules across 5 namespaces**, and not one of them is
ours:

```
antonkulaga/{aggression_anger_snps, big_five_personality_snps, bodybuilding, cognitive_intelligence}
eric-mods/lactose_tolerance
ksuha-dna/{placebo_response_claude, placebo_response_research}
```

`registry_search(target="prod", query="coronary")` returns `total: 0`. `registry_is_published` on
`coronary` returns `free_to_publish: true`.

That verdict is true about the registry and **false about the world**: `coronary`,
`lipidmetabolism`, `longevitymap`, `superhuman`, `vo2max` and `thrombophilia` have all been published
for months — on **HuggingFace**, at `just-dna-seq/annotators`, which is where this repo's discovery
tier actually reads modules from and where all ten carry a `manifest.json` today.

So for every module in this repo the "am I ahead of what is published?" question — the one
`compare_to_published` exists to answer, and the one a revision pass opens with — **cannot be asked
at all**. The tool does not fail; it answers confidently about the wrong distribution channel.

The plugin is careful about exactly this class of mistake in another dimension: `target` is required
and has no default on every catalog read, because *"a search that guessed would answer confidently
about the wrong instance."* The same argument applies one level up, to which *kind* of publication is
being asked about, and there it is not applied.

**What the tooling should do:** at minimum, say what it did not look at — *"not found in the registry;
this does not cover HuggingFace or any other source"*. Better: let `compare_to_published` take a
source URL, since the comparison it performs needs only a readable `manifest.json` and every module
in `just-dna-seq/annotators` publishes one.

---

## D16 — `verification.json` counts findings and does not keep them

**Severity: high · Found on: cancer, pathogenic**

Two of the ten carry a `verification.json`. Both record a real, non-skipped check with a non-zero
result:

| module | check | subjects | findings | detail |
|---|---|---|---|---|
| cancer | `clinical_significance` (ClinVar `clinvar_2026-06-27`) | 141,616 | **20** | `null` |
| pathogenic | `clinical_significance` (same release) | 618,629 | **32** | `null` |

Fifty-two rows in the two largest modules assert a clinical significance that ClinVar disagrees with.
The record says **how many** and provides no way to find out **which**. `detail` is `null`, no
sidecar lists them, and `review_queue` / `review_logs` cover overrides and authoring logs, not check
findings.

The MCP instruction block is emphatic that this is the interesting direction — *"A mismatch means
CHECK BOTH SIDES: the row may be wrong, and so may the source"* — and an author cannot check either
side of a finding they cannot name.

Compounding it, **nothing rolls these up**. `validate_module` and `compile_module` read the spec
directory that contains this file and say nothing about it, so a revision pass driven by the
validator — which is what `module-status` prescribes as the fourth and deepest read — never learns
that 52 disagreements are on record.

**What the tooling should do:** write the findings, not just the count — a `verification_findings.csv`
sidecar keyed by `variant_key` with the authored value and the source's. And surface a one-line
summary in `validate_module`: *"verification.json records 20 unresolved findings from
clinical_significance."*

**Also worth deciding:** both records were produced by `just-dna-enricher 0.6.4` while the installed
enricher is **0.6.6**, and four of the five checks in each are `skipped: offline`. Nothing warns that
a check record is two patch versions stale or that it was taken with most of its passes switched off.
The tri-state itself is well designed and correctly reported — `skipped: "nothing_to_check"` with
*"this is not a comparison that found nothing"* is exactly right. The gap is that nobody is told to
look.

---

## D17 — eight of ten modules have never been cross-checked and nothing says so

**Severity: medium · Found on: cardio, coronary, lipidmetabolism, longevitymap, pharmgkb, superhuman, thrombophilia, vo2max**

Only `cancer` and `pathogenic` carry a `verification.json`. The other eight — including all six
expert-curated flagship modules and the 1,482-row pharmacogenomics module — have **no check record
of any kind**, and every one of them passes `validate_module(strict=true)`.

`module-status` gets the principle right: *"A check that could not run is not a check that passed."*
But its `verification.json` row is about reading a record that exists, and there is no warning for
the record that does not. The absence is silent in exactly the way the closure absence is not — the
closure warning fires on all ten.

**What the tooling should do:** the closure warning is the model. One more sentence in the same
place: *"this module records no cross-check either."*

---

## D18 — `registry_search` truncates the gene list without saying so

**Severity: low**

`registry_search(target="prod")` returns `"genes": ["ALCAM","ARL17B","ARPP21"]` for
`aggression_anger_snps`, whose own description says **22 genes**. Every result is cut to the first
three alphabetically, with no `gene_count` and no ellipsis. `bodybuilding` shows
`["ACTN3","ADRB2","CCND2"]` for a module whose description names ACTN3, PPARGC1A and ADRB2 as its
three candidate genes — so the list looks complete and is not.

Searching **by** gene works correctly; it is only the display that truncates. But a caller filtering
the returned records by `genes` in memory gets wrong answers silently, and the plugin's own rule for
this case is stated in `module-compile`: **null never means zero**. A truncated list that does not
say it is truncated is the same error in a different shape.

---
## D19 — "delete the `panel:` block; nothing else is lost" is not true for the modules that have one

**Severity: high · Found on: cardio, cancer, pathogenic**

The three ClinVar-drafted modules each declare a `panel:` block, and each gets this warning
(`just_dna_compiler/compiler.py:3425`):

> module_spec.yaml declares a `panel:` block. It is deprecated in 0.6 and removed at 1.0: the
> compiler never materialized rows from it, and the one thing that did read it — the enricher's
> ClinVar `clin_sig` cross-check … — now reads the `dataset` column of the module's licence row,
> which `just-dna-enricher draft-panel` writes itself. **Delete the block; the rows it describes are
> the authored `variants.csv` rows, and nothing else is lost.**

Measured against what the blocks actually carry:

| | `cancer` | `cardio` | `pathogenic` |
|---|---|---|---|
| `panel.genes` | **425** | present | `[]` (genome-wide) |
| `panel.reference` | `2026-06-27` | `2026-06-27` | `2026-06-27` |
| `panel.reference_sha256` | present | present | present |
| `panel.significance` | `[likely_pathogenic, pathogenic]` | present | `[likely_pathogenic, pathogenic]` |
| licence row `dataset` (the replacement) | `clinvar_2026-06-27` | **empty** | `clinvar_2026-06-27` |

Two things are lost, one of them completely:

**1. The selection criteria.** `panel.genes` + `panel.significance` is the machine-readable statement
of *what this module is* — 425 cancer-predisposition genes, pathogenic and likely-pathogenic only.
`dataset` carries a release name and nothing else. Nothing in the artifact reconstructs the criteria:
`validate_module` reports `gene_count: 298` for `cancer`, so 127 of the 425 panel genes yielded no
variant, and the difference between "gene not in the panel" and "gene in the panel with nothing to
report" is only derivable from the block being deleted.

**2. Which bytes.** `panel.reference_sha256` is a SHA-256 of the ClinVar snapshot. `dataset:
clinvar_2026-06-27` is a *release name*. A release name is not a hash, and ClinVar reissues.

**And for `cardio` the replacement field is empty.** `cardio` was drafted on 2026-08-10 with a
`sources.csv` that has a `dataset` column and leaves it blank; `cancer`, drafted 2026-08-19, fills
it. So the module that would follow this warning today loses its provenance entirely — the field the
warning redirects to has nothing in it, and `module-refresh` is explicit that a present sidecar is
authoritative and will not be re-derived by re-running the pass. There is no backfill path.

**What the tooling should do:** either keep `panel:` and carry it into `manifest.json` the way
`weighting` already is, or make the deprecation warning conditional — *"the licence row's `dataset`
is empty, so deleting this block loses the only record of which snapshot this module was drafted
from"* — and ship a backfill. Telling an author that nothing is lost, when the specific thing lost is
the reproducibility of a 70,000-row drafted module, is the one class of message that should never be
generic.

---
## D20 — `check_identifiers` merges correctly, and then misattributes the record it merged into

**Severity: low · Found on: cancer · Positive finding attached**

The behaviour worth recording first is that it is **right**. Running `check_identifiers` on `cancer`,
which already carried a `verification.json` with a real ClinVar `clinical_significance` record (20
findings, produced 2026-08-19), **preserved that record** and added three new ones. Nothing was
clobbered, `module_hash` was recomputed identically, and the per-record `checked_at` timestamps were
kept. A cheap check does not destroy an expensive one. That is the failure mode this pass went looking
for and it is not there.

The `nothing_to_check` handling is equally good: `thrombophilia` has no `trait_efo_id` anywhere, and
the record says so — `skipped: "nothing_to_check"`, *"no row carries a trait_efo_id, so there was no
term to ask OLS4 about"* — rather than recording a clean pass over an empty set. That is exactly the
vacuous-truth trap `module-compile` warns about for `fully_resolved`, avoided here by construction.

The defect is one field. `verification.json` has a **single top-level `producer`**, and the merge
rewrites it:

```
BEFORE  producer: just-dna-enricher 0.6.4   records: [clinical_significance(20), …]
AFTER   producer: just-dna-enricher 0.6.6   records: [clinical_significance(20), gene_locus_agreement, …]
```

After the merge the file claims enricher 0.6.6 produced the `clinical_significance` record, which was
produced by 0.6.4. The evidence survives in `checked_at`, so it is recoverable — but `producer` is now
a statement about a mixed record set, and it is wrong for every record it did not produce.

**What the tooling should do:** move `producer` onto the record, where `source`, `release` and
`checked_at` already are. It is the only field in the file that is scoped to the whole document while
describing individual work.

---

## D21 — `check_identifiers` prints the full roster when nothing is wrong

**Severity: medium · Found on: cancer**

`check_identifiers` on `cancer` returned a `genes` array with **298 entries**, each of the form
`{"identifier":"BRCA1","state":"approved","current":"BRCA1","label":"HGNC:1100"}` — roughly 30 kB
saying that nothing changed. `stale` was `[]` and `gene_locus_conflicts` was `[]`.

`pathogenic` has **4,793 genes**. The same call there returns roughly half a megabyte of confirmation.

The verdict fields (`stale`, `gene_locus_conflicts`, `gene_locus_check_skipped`) are well designed and
are all a caller needs; the roster is the raw material. Same shape as **D3** and it lands on the same
tool family.

**What the tooling should do:** return `checked: 298, approved: 298` and reserve the roster for
`stale`/conflicting entries, or put it behind a `detail=true`.

---

## D22 — `registry_check` reports `valid: false` when nothing ran

**Severity: high**

`registry_check` on `thrombophilia` with no token stored returned:

```json
"valid": false,          "errors": [],           "warnings": [],
"verdict": null,         "verdict_unavailable": "no_registry_token",
"name_matches_path": false,
"unchecked": ["nothing was checked: no registry token is available for this instance."],
"next_step": "Not a verdict — nothing ran. …"
```

`verdict`, `verdict_unavailable`, `unchecked` and `next_step` are **excellent** — four fields that
between them make it impossible to misread the network tier. And directly beside them, two plain
booleans that assert the opposite:

- **`valid: false`** with an empty `errors` array, on a module that passes `validate_module(strict=true)` clean.
- **`name_matches_path: false`** for spec dir `…/_dogfood/thrombophilia` and name `thrombophilia`, which match.

Both are unrun checks defaulting to `false`. This is the plugin's own cardinal rule, applied
meticulously in the three-valued fields of the same response and dropped in the two-valued ones:
*"a check that could not run is not a check that passed"* — and it is not a check that **failed**
either. `registry_url` is `""` for the same reason.

The cost is concrete: a caller that branches on `valid` — the obvious field, and the one named the
same as `validate_module`'s — concludes that a clean module is invalid because a credential was
missing.

**What the tooling should do:** make `valid` and `name_matches_path` `null` when the corresponding
check did not run. The response already carries the vocabulary for it.

---

## D23 — the plugin has its own credential store and never looks at the project's

**Severity: low · undecided rather than wrong**

`registry_check` reported `no_registry_token` in a checkout whose `.env` defines `REGISTRY_URL`,
`REGISTRY_TOKEN` and `REGISTRY_TOKEN_SANDBOX`, and which talks to the same production registry from
`scripts/registry_precheck.py` and `pipelines registry`. `authenticate` stores a token *"only against
your own session"*.

Session-scoped credentials are a defensible security position and may well be the right one. But
nothing says that is what is happening, so the reading from inside a wired-up project is *"my
credentials are not working"* rather than *"this tool has a different credential store on purpose"*.

**What the tooling should do:** say so in the `next_step` — one clause: *"the plugin keeps its own
per-session token and does not read `REGISTRY_TOKEN` from the environment."*

---

## D24 — `module-install-local` is accurate about this repo, and its route-C warning is a live bug here

**Severity: high (against just-dna-lite, not the plugin) · Positive finding attached**

The `module-install-local` skill makes a series of precise, falsifiable claims about *this*
repository. Every one checked out:

| claim | verified |
|---|---|
| `register_downloaded_module` exists in `just_dna_pipelines.module_registry` | yes, `module_registry.py:245` |
| there is no CLI for it; `pipelines module` offers only validate/register/unregister/list-custom/compile/reverse | yes |
| nothing verifies a manifest on the way in — `verify_manifest` is called nowhere | yes |
| route C copies spec-dir files over the compiled output and the suffix list includes `.json` | yes, `module_registry.py:160` |

That last one is not a hazard in the abstract. **Reproduced end to end**, on a copy of `coronary`
renamed to `dogfood_routec` and registered through `register_custom_module`:

```
spec-dir manifest.json (from the 2026-08-09 build)
    artifact.digest  sha256:65496ede939344eb46f2383326c083ca7f1cf1b42d7ecf7265164460cc43d38f
    compiled_at      2026-08-09T17:52:25Z

after `register_custom_module(spec, resolve_with_ensembl=False)` — a fresh compile on 2026-08-21 —
registered_modules/dogfood_routec/manifest.json
    artifact.digest  sha256:65496ede939344eb46f2383326c083ca7f1cf1b42d7ecf7265164460cc43d38f   ← stale
    compiled_at      2026-08-09T17:52:25Z                                                       ← stale
    module name      coronary                                                                   ← wrong module
```

`compile_module` writes `manifest.json` into `output_dir`, and then
`module_registry.py:161-163` copies every `.yaml/.csv/.md/.png/.jpg/.jpeg/.log/.json` from the spec
directory on top of it. So the registered module ships a manifest describing **different bytes, built
twelve days earlier, under a different name**.

This matters here specifically because `read_module_provenance` reads that file to populate the
report's *"Modules in this report"* table — the table whose whole purpose is to tie a saved report to
the module version behind it. It would state the wrong digest with full confidence.

**And every one of the ten v1-port modules has a `manifest.json` sitting in its spec directory**, so
this fires on all of them.

**Fixed in this pass** — the one finding on this list that is ours to close. The copy loop is now
`module_registry.copy_spec_files`, which skips the names in `COMPILER_OWNED_OUTPUTS`
(`manifest.json`, case-insensitively) and copies everything else exactly as before, `provenance.json`
included. Re-running the reproduction above now yields `sha256:8e995f2a…` / `2026-08-21T17:50:06Z` —
the compile that actually ran — with the stale manifest left untouched in the spec directory, which
is the author's file and not ours to delete.

Pinned by `just-dna-pipelines/tests/test_spec_file_copy.py` (5 tests, no compiler, no network, no
fixture module). Per the repo's own rule about bug-catching claims, the old loop was re-created
verbatim and run against the same assertion: it writes `sha256:stale` into the output and the test
fails, so the test does catch the bug rather than merely describing it.

*The test registrations were unregistered and their directories removed; `modules.yaml`'s working
copy was checked afterwards and holds exactly the two module entries that pre-dated this session.*

---
## D25 — nine of the twenty skills are shadowed by a command that never loads them

**Severity: critical (it silently disables the plugin's documented entry point)**

The plugin ships `skills/` (20 entries) and `commands/` (9 entries). The nine command files are
**routing shims**, and their entire body is an instruction to load the same-named skill.
`commands/module-revise.md` in full:

> Load the `module-revise` skill and follow it for: `$ARGUMENTS`
>
> The output is a **decision list**, not a diff and not a findings dump. …
>
> The skill is the procedure; this command only routes to it. **Do not restate `module-revise`'s
> content here or work from memory of it — load it.**

Invoking `module-revise` resolves to the **command**, which returns that text and nothing else. The
skill body is not delivered. Invoked twice to confirm; the second attempt was reported as a
re-invocation and returned the same routing text again.

The split is exact:

| shadowed — returns only the routing text | loads its own body |
|---|---|
| `create-module`, `find-evidence`, `module-101`, `module-check`, `module-compile`, `module-publish`, `module-revise`, `module-start`, `module-tables` | `module-close`, `module-consumer`, `module-curate`, `module-diff`, `module-draft`, `module-enrich`, `module-install-local`, `module-refresh`, `module-status`, `module-symptom`, `module-weights` |

**The nine that fail are the nine an author reaches for first**, including `create-module` — which
the MCP server's own instruction block names as the way in: *"Load `create-module` to route."* And
`module-revise`, which `module-status` names as the correct entry point for a second pass, *"which is
almost every real session."*

The failure is maximally quiet. The command's own text forbids the fallback that would mask it —
*"do not … work from memory of it"* — so a compliant agent that follows the instruction produces
nothing, while a non-compliant one improvises the procedure and looks like it worked. Both of this
pass's `module-status` and `module-install-local` loads delivered full, excellent skill bodies, so
the surface reads as working right up until it does not.

**Workaround used here:** read `skills/module-revise/SKILL.md` from the plugin directory. That works
and is not something a user should have to know.

**What the tooling should do:** the shims are redundant with the skill's own `description` and
`triggers` — the eleven unshadowed skills are reached fine without one. Deleting `commands/` is
probably the whole fix.

---

## D14 addendum — the two conclusion checks, measured across the corpus

**D14** proposed three lint rules from four hand-verified `thrombophilia` rows. Both machine-checkable
ones were then implemented and run over the six curated modules (**1,418 rows**), tightening the first
rule after an initial version produced obvious false positives — `"TG"` in *"raised plasma
triglyceride (TG) levels"* is not a genotype. The rule that survives requires the token to be built
**from alleles that appear at this rsID's own locus**, which excludes `TG` at a C/G site by
construction.

| module | rows | conclusion names another genotype **at this locus** | identical conclusion on genotypes with **different** `state`/`weight` |
|---|---|---|---|
| coronary | 81 | 5 | 4 |
| lipidmetabolism | 45 | 2 | 4 |
| longevitymap | 1039 | 8 | 480 |
| superhuman | 190 | 1 | 0 |
| thrombophilia | 24 | 4 | 2 |
| vo2max | 39 | 0 | 2 |
| **total** | **1,418** | **20** | **492** |

**Rule 1, precision inspected by hand on all 20.** Roughly twelve are real and six of those are
severe — `coronary` `rs17514846` has the `C/C` and `A/A` conclusions **swapped** (`C/C` reads *"AA
genotype is associated with an increased risk of CAD"*, `A/A` reads *"CC genotype is NOT associated"*)
while all three rows carry `state: neutral, weight: 0.0`; `coronary` `rs11591147 T/T` is scored
`protective, +1.2` under text reading *"GG genotype is protective"*. The remainder are legitimate
comparative or quoted prose — `longevitymap` conclusions are abstract excerpts containing
`HR (MnSOD(CC/CT)) = 0.91`. **Measured precision is roughly 60%**, which is why the recommendation is
`warning` and not `error`. Twenty items to eyeball across six modules is a morning's work; finding
them without a rule is not.

**Rule 2 is a question, not a defect.** 480 of the 492 are `longevitymap`, where a heterozygote and a
homozygote share one sentence while carrying different weights — arguably correct for a GWAS port,
where the association statement is the same and only the dose differs. The point is that **the
tooling never raises it and the author has no way to record having decided it**. A reader with `C/T`
and a reader with `T/T` see identical prose and different numbers, and nothing in the module says
whether that was intended.

---
## D26 — the six curated modules state no licence, and only the PGx path has a gate

**Severity: medium · Found on: coronary, lipidmetabolism, longevitymap, superhuman, thrombophilia, vo2max**

| | `version` | `license` | `authorship` | `panel:` |
|---|---|---|---|---|
| cardio | 1.0.0 | public-domain | 1 | yes |
| cancer | 2.0.0 | public-domain | 1 | yes |
| pathogenic | 2.0.0 | public-domain | 1 | yes |
| pharmgkb | 1.0.0 | CC-BY-SA-4.0 | 1 | — |
| **the six curated** | **null** | **null** | **[]** | — |

The split is exact: everything machine-drafted declares all three, everything hand-curated declares
none. And their `sources.csv` carries **one row, `ensembl / resolution`** — nothing at
`layer: annotation`, which is the layer that carries the derivative-work obligation and the only one
this repo's report footer reads. So six modules that are about to be published state no terms at all,
and the report renders *"Not stated"* — correctly, because nothing was stated.

`module-status` describes a compile gate for this — *"The licence is unstated and the rows came from a
PGx source. The compile gate reads `licensing.csv` and nothing else"* — and it is scoped to a PGx
source. For originally-curated content nothing fires, in either direction: no warning that terms are
absent, and no way to record *"this is our own curation, deliberately unlicensed for now"*.

It is defensible that a tool should not nag about a licence. It is not defensible that "unstated" and
"deliberately none" are the same bytes, when the format is otherwise fastidious about exactly that
distinction.

---

# The pass, module by module

Every module was read on `module-status`'s four passes (names on disk → spec declarations →
`verification.json` → one `validate_module(strict=true)`). All ten are **`valid: true` with zero
errors**.

| module | lead | rows | studies | warnings | the notable thing |
|---|---|---|---|---|---|
| coronary | weights | 81 (27 variants) | 118 | 2 | conclusions swapped between `C/C` and `A/A` at rs17514846, all three rows `neutral 0.0` |
| lipidmetabolism | weights | 45 (15) | 41 | 3 | 1 orphan citation (20686565) |
| longevitymap | weights | 1039 (528) | 671 | 9 | the only module that fills `category`; 480 shared-conclusion groups |
| superhuman | weights | 190 (101) | 103 | **85** | **no `weight` on any row**; 80 of the 85 warnings are one VRS line per allele |
| thrombophilia | weights | 24 (8) | 27 | 3 | 4 of 24 conclusions describe a different genotype |
| vo2max | weights | 39 (13) | 19 | 2 | cleanest of the six |
| pharmgkb | pharm_variants | 1482 | **0** | 5 | no citations, no PMID column to put one in; stats report `variant_count: 0` |
| cardio | weights | 57,055 | 121,467 | 7 | `panel:` deprecated and its replacement field is **empty**; no `verification.json` |
| cancer | weights | 70,658 | 140,934 | 6 | `verification.json`: **20** unresolved ClinVar disagreements, unlisted |
| pathogenic | weights | 308,990 | 626,088 | 6 | **32** unresolved disagreements; `validate_module` takes **93 s** with no progress output |

Two operational notes from running it:

- **`validate_module` on `pathogenic` takes 93 seconds and prints nothing until it returns.** Through
  the MCP surface that is a silent block of unknown length. `cardio` and `cancer` take ~17 s each.
- **The large modules had to be validated through the library**, not the tool, to keep the warning
  volume readable — see **D3**. `from just_dna_compiler.compiler import validate_spec`, not the
  documented top-level import (**D11**).

---

# What is good, and should not be traded away

A findings list is a biased sample. Four things in this surface are better than what they replace and
several of the findings above are *only* findings because the surrounding design sets a high bar:

- **Tri-state everywhere it counts.** `skipped: "nothing_to_check"` with *"this is not a comparison
  that found nothing"*; `verdict: null` with `verdict_unavailable` and `unchecked` beside it;
  `gene_locus_check_skipped`; `still_bound` being three-valued with `null ≠ false`. **D7** and **D22**
  are notable precisely because they are the two places this slips.
- **Schema answers generated from the live models.** `describe_table` cannot drift from what the
  compiler accepts, and it says which columns are `redundancy_bearing` and why filling one from its
  own checking source makes the check vacuous. That reasoning is not written down anywhere else.
- **Merging, not clobbering.** `check_identifiers` preserved a `clinical_significance` record it did
  not produce (**D20**), and sidecars merge by design.
- **Documentation that is checkable and checks out.** `module-install-local` makes four falsifiable
  claims about *this* repository and all four are true — including one that turned out to be a live
  bug here (**D24**). The skills describe just-dna-lite's behaviour more accurately than
  just-dna-lite's own docs did in one respect, which is a strange and good thing to be able to say.

---

# The decision list

`module-revise`'s output is a decision list, not a findings dump: what has to be chosen, what turns on
it, where the choice gets made. Everything evident and mechanical was left out. Nothing below was
applied — `data/interim/v1_port/` is deliberately held at its 0.5-era state.

**Applied silently in a real revision pass** (listed once here so they are not mistaken for
decisions): rename `sources.csv` → `licensing.csv` on the eight modules carrying the deprecated
spelling; nothing else qualified.

1. **`superhuman` authors no weights at all — 190 rows, `weight` empty on every one.** The report sums
   `weight` per module, so it renders 0.0 for every category while showing 190 findings. Either author
   them or declare `weighting:` as authoring none. → `module-weights`

2. **Twenty conclusions across the six curated modules describe a genotype other than their row's;
   about twelve are real.** Two are severe: `coronary` rs17514846 has the `C/C` and `A/A` conclusions
   swapped, and `coronary` rs11591147 scores `T/T` protective under text saying `GG` is protective.
   A reader is shown the wrong sentence about themselves. → `module-curate`

3. **`cancer` and `pathogenic` carry 52 unresolved ClinVar disagreements between them and the record
   does not say which rows.** Re-running the check with findings retained is the only way to recover
   them. Both sides may be right — ClinVar lags too. → `module-check`

4. **`cardio`'s `panel:` block is deprecated and the field it redirects to is empty.** Deleting it as
   the warning instructs destroys the only record of which ClinVar snapshot the module was drafted
   from. Backfill `dataset` in `sources.csv` first, or keep the block until 1.0 forces the question.
   → `module-refresh`

5. **`pharmgkb` makes 1,482 clinical claims with no citations, and `pharm_variants.csv` has no column
   to put one in.** Decide whether `evidence_level` + `annotation_id` is the intended provenance for a
   drafted PGx module — and if it is, say so somewhere. → open question for the format tier

6. **Six modules state no `version`, no `license` and no `authorship`.** Every report they appear in
   renders *"Not stated"* for all three, so a saved report cannot be tied to the module version behind
   it. → `module-start` / `module-close`

7. **Ten modules, zero closures; eight of ten have never been cross-checked.** Closing is a deliberate
   act and this is the maintainer's call, not a defect. → `module-close`

8. **`superhuman` rs56185968 is a 23-allele GT-repeat authored as one variant row with genotype
   `G/G`.** Whether it belongs in `repeat_alleles.csv` is a curation judgement; nothing in the
   tooling raises it. → `module-tables`

---

# For the plugin maintainers, in order

| | finding | why first |
|---|---|---|
| 1 | **D25** — nine skills shadowed by commands that never load them | it disables `create-module`, the documented entry point, silently |
| 2 | **D2 / D3** — per-allele warning flood, flat uncapped `warnings` | makes "read the warnings" unfollowable on the smallest module here |
| 3 | **D22** — `registry_check` returns `valid: false` when nothing ran | a caller branching on the obvious field gets the wrong answer |
| 4 | **D16** — check findings counted and discarded | 52 real disagreements that cannot be acted on |
| 5 | **D19** — "nothing else is lost" is false for a drafted panel | the message actively instructs an author into a data loss |
| 6 | **D15** — the published channel is invisible to the plugin | "am I ahead of what's published" cannot be asked about these modules |
| 7 | **D14** — nothing checks the most reader-facing cell in the format | two rules, no external source, ~12 real hits in 1,418 rows |
| 8 | **D5 / D6 / D12 / D17 / D26** — absences that pass in silence | one extra clause each on a warning that already fires |
| 9 | **D1 / D7 / D9 / D10 / D11 / D18 / D20 / D21 / D23** | small, cheap, mostly one-line |

**D24** is ours, not theirs, and is the one item on this page that this repo should close itself.
