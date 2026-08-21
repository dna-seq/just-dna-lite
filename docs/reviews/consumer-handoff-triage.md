# Triage: the just-module-creator consumer hand-off

Our reply to [`docs/CONSUMER_HANDOFF_from_just-module-creator.md`](../CONSUMER_HANDOFF_from_just-module-creator.md)
(2026-08-20, addendum 2026-08-21). Written 2026-08-21 against `9ed37af`.

They asked for a reply "by whatever route suits you" and said "we are not doing that" is a fine
answer. This is that reply, one verdict per item. They also asked to be told which claims are wrong;
the short version is **none of the ones we checked**, and one of them corrects *our* documentation
rather than the other way round.

## What we verified, and what we took on trust

Their corpus measurements (the `hboc_palb2` star ratings, the 27-bundle census, the 0-of-10
`provenance_quote` count) are theirs to measure and we took them as reported. What we re-ran is
every claim they make about **our** code, because that is what decides a verdict. All six checked
out against today's tree:

| Claim | Site | Verdict |
|---|---|---|
| `alts` renders `'A/,/C'` on a pharm module | `report_logic.py:709` | **Confirmed, and latent-not-live on our corpus — see below.** Literal `"/".join(row.get("alts", []) or [])`, and `"/".join("A,C") == 'A/,/C'` measured. That `alts` is `String` on `pharm_variants` is their measurement, not ours. |
| 0.5 annotations dedup drops the second annotation | `report_logic.py:528-534` | **Confirmed**, with the loss argued in a code comment — stated to us, not to the reader. |
| `weighting` fetched and dropped on the remote path | `_attested_files`, `hf_modules.py:113-155` | **Confirmed.** The full `ModuleManifest` is validated and everything but `artifact.files` is discarded. |
| `./.` reads as called, and as no alleles | `io.py:169-195`, `restoration.py:236-241` | **Confirmed.** The regex extracts no digits, and `called_sites` never inspects GT. |
| The genotype match is not phase-aware | `io.py:192` vs `hf_logic._normalize_lead_genotype` | **Confirmed, and it needs a nuance we owe our own docs — see below.** |
| RM43 landed; the pharm downgrade comments are stale | `just_dna_compiler/compiler.py:499, 6273` | **Confirmed, and this one corrects CLAUDE.md.** |

### One we measured further than they did

The shipped `pharmgkb` in `data/interim/v1_port/` carries **no `alts` column at all** and
**0 of 1482 rows placed** (`chrom` null throughout). Both follow from it being a 0.5 artifact, and
both matter to the verdicts:

- The `alts` bug is **latent today and goes live on the next recompile** — `row.get("alts", [])`
  returns `[]` and renders empty. They said as much ("newly reachable: before format 0.6 the column
  did not exist"); we can confirm it from our own bytes.
- The pharm downgrade is **correct today** for this module. 0 of 1482 placed is exactly what
  `_lead_join_strategy`'s value probe is for. What is wrong is the *stated reason* — see below.

And one measurement that contradicts a shared assumption. Both this repo's CLAUDE.md and the
hand-off treat "no manifest on HuggingFace" as the current state — CLAUDE.md said "every module on
HuggingFace today" and the hand-off called `logo_url` "dead code in production" on the same premise.
**All ten modules in `just-dna-seq/annotators` publish a `manifest.json` as of 2026-08-21.**
Attestation is the normal discovery path now and probing is the exception, which is what makes item
2 below a change to every report rather than a latent one.

### The two that change what we have written down

**RM43 shipped and we did not notice.** CLAUDE.md still says the fix "waits on RM43 and a `0.4`-family
equivalent of `VariantRow.authored_ident`". The installed compiler 0.6.1 says otherwise at
`compiler.py:499` — since 0.6 it joins `resolution.csv` onto `pharm_variants` / `haplotypes` /
`heteroplasmy`, and publishes `positional_rows` / `positional_rows_placed` to say whether it worked.
So the two comments at `hf_logic.py:231` and `:298` assert a retired fact, CLAUDE.md's resolution
section repeats it, and a 0.6-compiled PGx module is being downgraded to an rsID join it no longer
needs. Their §`resolution.csv` is right and our docs are stale.

**The phase claim is true, and so is the CLAUDE.md rule that looks like it contradicts it.** CLAUDE.md
pins that neither `_normalize_lead_genotype` nor `_genotype_alleles` sorts, and gives the right
reason: sorting the module side folds `A|G` and `G|A` together and manufactures a match the module
never stated. The hand-off is talking about a *different* side of the join — `io.py:192` sorts the
**VCF** side unconditionally. Both are correct statements and together they make a phased authored
row unmatchable in either ordering, silently. Sorting the module side is not the fix (it is the bug
CLAUDE.md prevents). The honest fix is theirs: a sorted VCF genotype carries no phase, so **refuse a
phased authored row loudly** rather than joining it to nothing. CLAUDE.md's rule stands; what it is
missing is the sentence saying the VCF side sorts and what follows from that.

---

## Verdicts

Four dispositions: **Accept** (we will do it), **Accept — design first** (agreed, but the shape needs
deciding before code), **Defer** (agreed and blocked or not yet worth it, reason given), **Not ours**
(belongs in another repo; a note there is the whole job).

### Tranche 1 — live defects and one-liners — **DONE (2026-08-21)**

These are bugs or near-bugs, all verified above, none larger than a function. All nine are
implemented, with `just-dna-pipelines/tests/test_consumer_handoff.py` pinning each. Per the repo's
rule about bug-catching claims, the pre-fix behaviour was run rather than asserted: the old
`_lead_join_strategy` classifies a `haplotypes`-led table `position` and the join then raises
`ColumnNotFoundError: unable to find column "genotype"`; the old alt expression renders `'A/,/C'`;
the old `read_module_provenance` returns `(None, None, None)` for a module whose manifest states all
three.

**One of these changes broke discovery and the suite caught it**, which is worth recording rather
than presenting an unblemished result. Moving manifest reading into `_probe_module_at_path`
introduced a call to `_weighting_summary`, defined 500 lines further down — *after* the module-level
`MODULE_INFOS = discover_hf_modules()`. It raised no `ImportError`, because
`discover_modules_from_source` catches per-source failures: every source failed with `name
'_weighting_summary' is not defined` and discovery silently returned **nothing**, with the reason
only in the eliot log. Ten tests in `test_hf_modules` failed on it. Fixed by moving the definition
above its first caller, and pinned network-free by probing a real directory over `LocalFileSystem` —
every test that caught it needed the network, which is exactly the wrong dependency for this class
of bug.

**And the risk that finding created was checked rather than assumed.** With all ten modules now
attesting, the `_has()` gate on `annotations_url` / `studies_url` / `sources_url` consults the
manifest for all ten for the first time — so a file present at the path but absent from
`artifact.files` would now be *dropped* where it was previously probed and found, and a module's
credits section would vanish silently. Measured across all ten: the attested set equals the parquets
actually present, every weights-led module keeps all three URLs, and `pharmgkb` correctly has
`sources` but neither `annotations` nor `studies` (a pharm module legitimately has neither). No side
table was lost.

| # | Item | Site | Verdict |
|---|---|---|---|
| 1 | `alts` split on `,`, do not assume a list | `report_logic.py:709` | **Accept.** Wrong text reaches the report *and* the AI prompt today. Their upstream answer — retyping `alts` is a 1.0 break — makes the consumer-side split the answer for all of 0.x, not a stopgap. |
| 2 | Carry `weighting` / version / digest off the remote manifest | `hf_modules._attested_files` → `read_module_provenance` | **Accept, and it changes more reports than either of us thought.** The manifest is already parsed and validated three lines earlier. Measured after the fix against the live source: **all ten modules in `just-dna-seq/annotators` publish a `manifest.json` and none has a local directory**, so every one of them rendered *Not stated* before and every one now states its `artifact.digest`. `identity.version` and `weighting` are absent on all ten and correctly stay *Not stated*. |
| 3 | `_lead_join_strategy` must check the columns its join needs | `hf_logic.py:222-243` | **Accept.** `position` is returned on `{chrom,start}` alone, so a `haplotypes`-led module (which has `allele`, not `genotype`) raises `ColumnNotFoundError` at collect time instead of being recorded as skipped. Requiring `{chrom,start,genotype}` degrades it to the `unsupported` it should already get. |
| 4 | Fix the stated reason for the pharm downgrade; exercise the branch | `hf_logic.py:229-232, 296-299` + CLAUDE.md | **Accept, and it is smaller than they wrote.** `_lead_join_strategy` probes *values*, not family names, so a genuinely 0.6-compiled pharm module already gets the position join — no `positional_rows*` gate is needed in `hf_logic`, which is the alternative they themselves offer ("keep the schema probe and fix the stated reason"). The whole item is: correct the two comments and CLAUDE.md's RM43 sentence, recompile `pharmgkb` under 0.6, and pin the position branch with a test. It has never run on this family. |
| 5 | `README_CANDIDATES` in the publish allowlist | `v1_port/publish.py:39` | **Accept.** `_ALLOW_PATTERNS` is `[*ARTIFACT_PARQUETS, "manifest.json", "logo.png", "logo.jpg"]`, so `manifest.readme` attests a file the repo does not have and `verify_manifest(check_readme=True)` passes anyway. Import it as `just_dna_enricher.upload` does. |
| 6 | `pipelines module register-compiled <dir>` | `module_compiler/cli.py` | **Accept.** Their smallest complete ask and the one with a live cost: another team ships a `python -c` into `module_registry.register_downloaded_module` because we expose no front door. `register` recompiles and changes the digest, so it is not the same command. |
| 7 | Warn on a silent name collision in discovery | `hf_modules.py:397` | **Accept.** `if name not in all_modules` with the HF collection as source #1 shadows a locally registered module with no warning. One `log_message` at `warning`. |
| 8 | Refuse a phased authored row loudly | `hf_logic._normalize_lead_genotype` | **Accept.** The corollary of the phase finding above: the VCF side sorts, so a phased authored genotype can match in neither ordering and does so silently. We will not sort the module side (that is the bug CLAUDE.md exists to prevent) — we will detect a `\|`-split lead genotype and skip it with the reason recorded, the same way `UnsupportedLeadTable` is recorded. `v1_port/runner.py:246-286` has the mirror hole on the authoring side and gets the same treatment. |
| 9 | Doc corrections | `AI_MODULE_CREATION.md`, `MODULE_MARKETPLACE_SPEC.md` | **Accept.** `register` writes to `get_registered_modules_dir()`, not `data/output/modules/`; the marketplace spec's `register_custom_module` sentence is stale (`_do_install` uses `register_downloaded_module`, which is the better choice). Also worth writing down: a **partial** manifest makes a module invisible to discovery while `list-custom` still lists it, so it is strictly worse than no manifest. |

### Tranche 2 — the two shapes

They nominated these as where to start and we agree; each unblocks several sections at once.

| Item | Verdict |
|---|---|
| **Shape 1: a gated `ModuleInfo` URL field per fact sidecar** (`frequencies`, `gwas_effects`, `gene_metrics`, `gene_validity`, `clinical_assertions`, `literature`) | **Accept.** Their premise checks out: `get_module_table_url` falls through to a bare `f"{info.path}/{table_name}.parquet"` guess, which is the probe-instead-of-attest path `_attested_files` exists to end. The change is mechanical — extend `MODULE_TABLES` / `ModuleTable`, add one `_has()`-gated field each. Do this before any of the render asks, which are otherwise unimplementable. `clinical_assertions.parquet` is *already published* by `v1_port/publish.py` and simply cannot be seen. |
| **Shape 2: a fourth `measure` branch in `_lead_join_strategy`** for the binning family | **Accept — design first.** Agreed in principle: four families are authored, compiled, published, installed and then skipped. But this is not a join, it is an extraction plus a bin lookup, and it carries the two rules that make it safe — the three-valued outcome where an absent measurement selects the `unresolved` sentinel and **never** the lowest bin, and `source_field` / `source_element` as the extraction contract rather than a hardcoded field. Getting those wrong reports "asymptomatic carriage" for an unmeasured sample. It also lands on a namespace we already know is unsafe: CLAUDE.md records that `user_vcf_normalized` flattens INFO and FORMAT into **one** namespace where `AF`, `DP`, `MQ` and `AD` collide, which is exactly what `FORMAT/AF` vs `INFO/AF` for heteroplasmy needs to distinguish. **So shape 2 has a hard prerequisite we already knew about and they did not:** the qualified-pointer work from format RM53. Their heteroplasmy example — reading `INFO/AF` and reporting a carrier as asymptomatic on the strength of a reference panel's allele frequency — is precisely what our current parquet would do. Sequence: RM53 namespace split first, then `measure`. |

### Tranche 3 — accepted, ordinary work

Agreed, each is a join and a render once shape 1 lands. Listed in the order we would take them.

- **State the 0.5 dedup loss to the reader, not just to us.** Their ask was "fix it or state the loss"; we state it in a code comment and the reader sees a collapsed row with no indication. The fix is not to stop collapsing — the RM80 reply rejects `variant_key` dedup as the general answer and the fan-out double-counts the variant, which is the worse loss — it is to surface that a pre-0.6 artifact had further annotations at this locus, and to say so on the eliot log where `_annotations_keying` already reports which keying fired.
- **`clinical_assertions` renders** — star rating beside the interpretation, per-ALT selection joined at `chrom:start:ref` (**not** `variant_key`, which matched 4 of 24 in their measurement), and `conflicting` as its own state rather than one more tier. Their caution is right and we will pin it: **do not average the stars**, min and max are two counts because an average describes no record, and `null` is not `0`.
- **`literature` join on `pmid`** — DOI and PMC links, open-access badge, `exists is False` as a module defect rather than a coverage gap. Note their deliberate limit: no `title`/`journal`/`year` in the table, so ask it for identifiers, not prose.
- **`studies` sort key and provenance quote** — sort on `neg_log10_p` (our own `v1_port/adapters.py` computes and stores it and nothing reads it), badge ≥ 7.3, render `effect_size (effect_measure) relative to effect_allele` as one string and **withhold entirely when `effect_allele` is null**, because a magnitude with no referent inverts rather than breaks. Plus the null-key study row getting a module-level Evidence section, and the missing test on the studies read path.
- **`genome_build` dereferenced** — `cli_annotate.py:264-268` falls back to the literal `"GRCh38"`. A GRCh37 module joined against a GRCh38 VCF produces silently wrong rows and the module has been declaring its build all along. This is the highest-severity item in tranche 3.
- **Net weight gated on `weighting`** — we already render the weighting cell beside the number and CLAUDE.md already says "if you ever want to aggregate, that block is the gate". They found the place where we render two ungated numbers side by side. Gate or annotate.
- **`manifest.license`, `authorship`, `readme`, `verification.closure` / `checks[].skipped` / `checks[].release`** — all parsed already, all unread. `closure` is the one we rate highest: nothing today distinguishes a finished module from a draft.
- **The `licensing.csv` blanks** — `license_sha256` compare on refresh, an explicit "no licence terms recorded" row so that absent terms and no obligations stop looking identical, `notice` hoisted into the disclaimer, `redistribution` consulted before a report is shared.
- **`pharm_variants` small reads** — `annotation_id` linked to ClinPGx, `phenotype_category` used to group, `positional_rows*` read at install time to warn before a small join result is discovered.
- **`frequencies` / `gene_metrics` / `gene_validity` renders** with the reading rules they specify, which we accept verbatim and consider the valuable half of the ask: `status = not_covered` means *unknown* and never zero; `AN = 0` must not be `fill_null(0)`; ClinGen dosage codes are **non-ordinal**, so never sort on the code; key gene metrics on `(gene, dataset)` and refuse to rank genes across releases; and `disputed` / `refuted` / `no_known_disease_relationship` are a **caveat**, never a low rank on `ORDERED_GENE_VALIDITY`.
- **`pgs` routed to the PRS workbench** rather than skipped by the genotype annotator. They are right that this is misrouting rather than a missing read: the ids need to reach `selected_pgs_ids`. `match_rate_floor` → `min_match_rate`, `training_ancestry` + `training_cohort` → `assess_ancestry_coherence`, and `research_tier == "research_only"` suppressing the absolute-risk estimate. Their note that these three columns exist so a consumer can *refuse* is the point, and the refusal cannot happen today. We will not fabricate a coverage metric in `note`.
- **`resolution.csv`: `prune_unmatchable_rows` should stop hand-parsing** — `runner.py:251` uses `csv.DictReader` keyed on `rsid` alone, so it unions alleles across builds and cannot see a coordinate-keyed row. `load_csv_rows(path, ResolutionRow, ...)` filtered on build and `status != "not_found"` reuses the compiler's own predicate and `extra="forbid"` catches a typo'd column.
- **Trust `manifest.logo`** where a manifest is present. Their correction is right: the comment at `hf_modules.py:237-238` predates format 0.5 giving `manifest.logo` a `{name, sha256, size}`. Probing stays as the manifest-less fallback.
- **Star-allele family**: `allele_function` joined to `haplotypes` on `(gene, haplotype_name) → (gene, allele)` is the read that needs **no caller and no new schema**, and it is the one we would do first. `diplotypes` needs no VCF join either but does need `drug` + `clinical_context` selection (half the rows are drug rows, so a naive reader double-reports every diplotype) and the compiler's phase-ambiguity warning propagated with a withhold. The caller itself is out of scope for now.

### Tranche 4 — deferred, with reasons

- **The callability quartet** (`requires_callable`, `callable_from`, `quality_from`, `min_quality`). **Defer, and the reason is already written down.** CLAUDE.md's restoration section names three prerequisites, all upstream: the INFO/FORMAT namespace collision (RM53), QUAL inverting on a reference record which is exactly where a `requires_callable` row is evaluated (RM57), and gVCF `MIN_DP` needing interval containment rather than an equality join (RM57's second half). A bare column lookup against today's flattened parquet reads a well-formed number of the wrong kind without error. Their milder ask — mark the row *unknown* rather than asserting the reference conclusion — is reachable sooner and we will take that first.
- **No-calls as a third state.** **Accept in principle, defer on sizing.** Both halves are real and neither is a one-liner: `io.py` needs a no-call distinguishable from an empty genotype, and `restoration.build_restoration_context` needs `called_sites` to inspect GT so a `./.` stops suppressing restoration at a site nobody called. The second is the one that changes a rendered result.
- **`locus_index`** — read into the view model, never rendered or branched on. **Accept their framing: use it or drop it.** Leaning drop until something needs it.
- **`acmg_sf` / `actionability`** — **Defer.** Agreed these are the columns by which a module states a disclosure policy, but acting on them is a product decision about what we withhold from a reader, not a rendering change. Worth a separate conversation.
- **`rsid_status` / `rsid_alternates` / `authority`** — **Defer, and they framed it correctly as a decision rather than a patch.** `resolution.csv` is not published, so the question is whether any of the three earns a manifest field or a place in the publish allowlist. Our inclination: `rsid_status` yes (an rsID merged away in dbSNP is a fact a reader needs and it exists nowhere else), the other two no.
- **`aggregate_logs` / `RegistryClient.logs`** — **Defer.** Both exist and neither is called; offering the transcript beside the module card is small. Gated on the privacy item below, which must land first.

### Tranche 5 — not ours

Per the working agreement, a note in the receiving repo's docs is the entire job. No commits there.

- **`manifest.stats.genes` derived from `variants.csv` alone**, so a PGx or binning module publishes `gene_count: 0` and is unfindable by gene. Theirs to say and they said so; the fix is `variant_stats` upstream or registry-side indexing. → note in `just-dna-format/docs/ROADMAP.md`.
- **Registry-side**: `version_diseases` missing beside `version_genes` / `version_categories`; `ModuleDetail` projecting `gene_validity` down to one boolean; `has_gene_metrics` missing from `_V017_COLUMNS`; `gather_pmids` reading `studies.csv` only, so `revalidate --check-pmids` never verifies a module whose threshold citation lives on a bin row. → they have already filed these; we will not duplicate.
- **Enricher**: `pgx_draft` discarding the CPIC `activity_score` it already reads. → theirs.
- **just-module-creator's own**: `MODULE.md` vs `README.md`, `_autocrop_whitespace` destroying alpha, the logo agent prompt, `RunLog` naive local time, `provenance.json`. They list these as their own and we agree.
- **Format 1.0**: retyping `alts` to `List(Utf8)`. They raised it and got the right answer; item 1 above is our side of it.

---

## The one we are escalating rather than triaging

**A published log transcript is unreviewed and can carry anything** — the full team system prompt,
every model id, and the user's local upload paths, at up to 4 MB per version, shipped when a user
clicks Register. They flagged it as the one item they would put above its neighbours on urgency
grounds, and they are right; it is a privacy exposure, not a missing feature.

It is also **ours**, because the publish path runs through our webui. Two things follow:

1. The pre-publish log review step they ask for is a product decision — what we redact, what we
   show the user before it leaves the machine, whether we publish transcripts at all by default.
   That is the maintainer's call and we are not going to pick it silently.
2. **The exposure is live today**, via the flat `v<N>.log` aggregate that already ships on
   Register — their own words are "a user clicks Register and ships it" and "buried in a 1.7 MB
   aggregate nobody will open". The `iterdir()` + `is_file()` walks they want changed to `rglob`
   (in `module_registry.register_custom_module`, and the slot-listing and publish paths in
   `webui/state.py` — we take their line references rather than restating our own) are not
   containing the leak, they are *narrowing* it to one file. Fixing them to enable per-role logs
   ships **more** transcript, not less.

**Decision (2026-08-21, maintainer): redact and keep publishing.** Transcripts stay in the publish
set, because the provenance story they enable is worth having, but a redaction pass strips the team
system prompt, model ids and absolute local paths before anything is uploaded. That pass is the
prerequisite; `rglob` and per-role logs land after it, and `aggregate_logs` / `RegistryClient.logs`
become implementable once what they would serve is safe to serve. Tracked as the next tranche after
the one below.

Original recommendation, kept for the record: decide the review/redaction step first — including whether we publish transcripts
by default at all — and implement `rglob` after. It is not the independent one-liner it looks
like, and shipping it first makes the existing exposure worse.

---

## What we are telling them

That the aggregate argument lands. Their framing is that authoring effort currently has no return —
a curator who locates a quote in a fulltext produces something indistinguishable from one who left
the cell empty — and the `licensing.csv` counterexample is the right one, because that read is good
precisely because somebody asked for it. Most of this list is not a disagreement about design; it is
a list of tables nobody requested.

That said, two qualifications on the ordering they proposed:

- **Shape 2 is not next.** It is blocked on format RM53, for a reason their own heteroplasmy example
  demonstrates. Shape 1 is genuinely first and genuinely cheap.
- **`genome_build` deserves to be above most of shape 1.** A silently wrong row from a build mismatch
  is worse than an unrendered column, and they filed it in the middle of a list.

And one thing we would ask back: they say there is no `CONSUMER_SUGGESTIONS.md` intake here and that
setting one up is not theirs to do. Fair. This file is the reply for this round; if there is a second
round it should have somewhere to land, and that is ours to set up.
