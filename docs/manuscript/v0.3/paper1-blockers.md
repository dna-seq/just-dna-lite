# Paper 1 Blockers and Workarounds (v0.3)

## Editorial pass, 9 September 2026

### Author review corrections

- Restored the competitor paragraph in the Introduction, including DNA Complete/Nebula, Dante Labs, PLINK, ANNOVAR, and VEP. Those details were removed, not relocated, in the first editorial pass.
- Made the complete removal of OakVar explicit and named Dagster, polars-bio, Polars, and DuckDB as components of the replacement engine.
- Corrected PLINK2's role throughout the methods: it is an external benchmark comparator, not a provided just-prs engine.
- Verified the Parquet runtime path in `annotation/hf_modules.py` (`_probe_module_at_path`, `_remote_manifest`) and the separate YAML/CSV compilation route in `module_registry.py` (`register_custom_module`). Existing published modules need neither authoring files nor a manifest to be discovered.
- Verified restoration and array features against just-prs's `docs/reference-restoration.md`, `docs/grch37-universe-build.md`, and `just-prs/src/just_prs/array_scoring.py`. Added reference-homozygote restoration and precomputed LD proxies without claiming that the historical engine benchmark measured their coverage gains.
- **Figure 3, author action:** an image exists at `images/just_prs_trait_consensus.jpg`, but it is not embedded in the manuscript. Visual inspection found an absolute-risk percentage for intelligence and inconsistent quality labels. Replace it with a current screenshot showing trait, reference population, model IDs, coverage, and settings; embed the replacement and revise the caption to match. An inline HTML TODO now marks its location.
- **Full-platform MCP, release check:** at the author's request, the manuscript describes the intended completed Just-DNA-Lite MCP interface in the present tense, separately from the existing standalone `just-prs-mcp`. The author identifies the full-platform interface as work in progress. Confirm implementation and document its tool inventory before submission; this pass did not implement or test it.
- Restored the original opening of Section 6.3 on the right to read one's genome. The first pass removed useful motivation along with legal detail; that deletion was not requested.

This status supersedes conflicting historical entries below. The manuscript received a prose-only pass; no application code, experiments, or benchmark calculations were run. Existing measurements remain unchanged. References and implementation claims have not yet been independently verified.

**Completed:** shortened the abstract; clarified the platform contribution; renamed the registry; separated the format contract from the compiler; reduced MCP and companion-paper repetition; qualified warm-run speed claims; removed claims that cross-score correlation establishes individual risk rankings; distinguished local computation from external AI data sharing; removed the categorical GDPR-compliance claim; and shortened the ethical argument. The Introduction's original competitor comparison and exclusivity claim were restored at the author's request.

**Evidence and reporting issues still requiring attention:**

- Annotation counts: 4,729,824 SNPs and 1,414,226 indels do not reconcile with 6,138,868 total records. Check the original counting definitions and records before changing any number.
- Annotation timing: define warm and cold cache states, timed pipeline boundaries, selected modules, whether normalization and report generation are included, and comparability with the historical Generation I runs. Identify the separate GVCF input and justify any cross-input speedup comparison.
- Historical benchmark statistics: verify Table 2 and Supplementary S2 against the individual run records, including mean, SD, and SEM. The editorial pass preserved all supplied numbers.
- PRS selection: the original text called PGS000006 through PGS000106 "100 consecutive" IDs, although that inclusive range contains 101 IDs. The prose now says 100 scores without asserting the range. Supply the exact evaluated ID list and exclusions.
- PRS runtime: ratios of medians currently compare 100 successful just-prs scores with 96 PLINK2 scores. Report a paired comparison on the shared set if claiming a like-for-like speed advantage, and specify which preparation or loading costs are timed.
- PRS agreement: one person's scores across different models cannot establish agreement in rankings across people. Verify the proposed matching explanation with per-variant discrepancies; report model-specific absolute/relative errors and comparable missing-genotype handling. Predictive validity requires separate evidence.
- Memory: distinguish Python heap allocations, native allocations, total process memory, and baseline versus incremental use. The supplied heap and PLINK2 memory numbers are not yet an established comparable metric.
- Reference comparison: document missing-variant handling and whether sample and reference scores use comparable variant sets. A 50 to 54% match rate alone does not justify a percentile's reliability.
- Feature consistency: Section 3.2.1 lists ancestry detection, while Section 6.4 says automatic inference is not implemented. Confirm released behavior before resolving the discrepancy. Also confirm input builds, liftover status, the in-app creator, catalogue size/date, and exactly which validation checks the installed schema performs.
- Module provenance: Table 1 includes an AI-generated module within a set introduced as expert-curated. Confirm whether it is a shipped default or an optional example, and distinguish it explicitly. Format and compiler ownership also needs consistent wording in the repository table.
- Scientific citations and comparison: verify bibliographic records, especially the lifespan-heritability citation, and add a source-checked comparison with related platforms. No external literature verification was performed in this pass.
- Submission assets and metadata: final figure files, full supplements, pinned software/data versions, a usable benchmark invocation, funding acknowledgment, equal-contribution markers, unused affiliations, and a public companion citation remain to be confirmed. Removing a placeholder caption alone does not resolve a missing figure.

Paper 1 can report its own results independently of Paper 2; the earlier instruction to publish Paper 2 first is superseded by the v0.3 strategy.

This note lists practical blockers for the Paper 1 preprint/journal submission and separates what can be fixed by manuscript editing from what needs assets, citation checking, user input, or repository work.

## Summary

Paper 1 is close enough that the main near-term work is editorial: tighten scope, keep AI/MCP content from taking over the platform paper, and make the platform-ecosystem novelty clearer. The items that genuinely need non-editing work are limited: final figures/screenshots, citation cleanup, confirmed funding wording, and Paper 2 being posted as a preprint before Paper 1 cites it.

## Blockers

| Blocker | Why it matters | Suggested workaround | Type |
|---|---|---|---|
| Too much AI/MCP text | Paper 1 can look dependent on Paper 2's unready AI evaluation. Reviewers may ask for hallucination or creation-accuracy benchmarks inside the platform paper. | Keep one short pointer to Paper 2. Keep AI module creation as a platform feature only, with no performance or accuracy claims. | Editing only |
| Platform novelty not sharp enough | If agentic content moves out, Paper 1 must show what is novel beyond a fast pipeline using Polars, DuckDB, and Dagster. | Reframe novelty around the ecosystem: local-first app, annotation/PRS engines, `just-dna-format`, `just-dna-marketplace`, and fsspec discovery. | Editing only |
| State-of-the-art comparison missing | A comparison table could help defend novelty, but it should not be invented from memory. | Keep as a TODO unless verified. If added, check current features and cite sources for tools such as VEP, ANNOVAR, OpenCRAVAT/OakVar, Galaxy, PRSice, and PGS Catalog tooling. | Needs research/checking |
| Clinical framing risk | Previous preprints were rejected for gene-disease inference concerns. Diagnostic or individual-prediction wording increases risk. | Use "joins user variants against published databases," "research and education," "not clinical interpretation," and "population-level associations." Avoid implying diagnosis or new gene-disease inference. | Editing only |
| Figures/screenshots pending | Placeholder figures make the draft look unfinished. | Add final screenshots/captions, or remove/soften placeholder figure calls for the preprint. | Needs assets; cleanup is editing only |
| Bibliography not finalized | The bibliography is still carried over from the combined manuscript, and strong claims need citation hygiene. | Accept for an internal draft, but before journal submission verify citations for privacy breach, PRS validation, longevity heritability, DTC genetics, and right-to-read/GDPR framing. | Needs citation work |
| ROGEN funding text TODO | Visible TODOs in funding sections weaken submission readiness. | Replace with confirmed mandatory wording, or use a conservative provisional acknowledgment without a visible TODO. | Needs user/input, then editing |
| Paper 2 citation dependency | Paper 1 references the companion agentic layer. If Paper 2 is not public, the citation is weak. | Post Paper 2 first as a lean preprint/archive record. Paper 1 should cite it only for agentic-layer details, not for Paper 1's core empirical claims. | Needs submission step |
| Marketplace/format narrative still fresh | `just-dna-format` and `just-dna-marketplace` strengthen Paper 1, but they have only just been added to the story. | Keep integrating them into architecture, contribution, ecosystem-growth, and code-availability sections so they feel central rather than appended. | Editing only |
| AI-generated module trust boundary | AI-generated modules can trigger reviewer concern if they appear equivalent to expert-curated modules. | Label AI-generated modules as research-use drafts requiring review. Keep provenance explicit through expert-curated vs AI-generated wording. | Editing only |

## Suggested Editing Order

1. Trim AI/MCP repetition so Paper 1 remains a platform/software paper.
2. Strengthen the platform-ecosystem contribution around `just-dna-format` and `just-dna-marketplace`.
3. Clean clinical-risk language throughout the abstract, scope paragraph, discussion, and limitations.
4. Remove visible placeholder language for figures and funding.
5. Do a separate verified comparison-table pass only if there is time to check sources.

## Status (v0.3 update)

Paper 2 changed identity: the `just-dna-agents` agentic-toolkit draft is retired and the
companion is now the just-module-creator manuscript (*Creating and Sharing Genomic Annotation
Modules with AI: The Just-DNA Ecosystem*, EASRP 2026). See `manuscript-strategy-v0.3.md` for
the reasoning. What that changed in this blocker list:

**Resolved in v0.3:**
- **Companion references** — all nine pointers to the retired paper are retargeted to what the
  new Paper 2 actually contains. Nothing in Paper 1 now defers to material Paper 2 does not
  cover.
- **`just-prs-mcp` is in scope** — it stays with Paper 1 rather than folding into a companion
  toolkit that was never built. §3.2.1 is rewritten as a Paper 1 contribution, and the abstract,
  scope paragraph, design principles, and conclusion name it.
- **`just-dna-agents` dropped** — deprecated and superseded by `just-module-creator`; removed
  from the Code Availability table rather than listed as available software.
- **Paper 2 citation dependency inverted** — Paper 1 no longer waits on Paper 2. Paper 2 cites
  Paper 1 six times and depends on it for every runtime claim, so **Paper 1 goes public first**.
  This retires the v0.2 blocker row "Paper 2 citation dependency" below.

**New in v0.3:**

| Blocker | Why it matters | Suggested workaround | Type |
|---|---|---|---|
| `just-dna-marketplace` → `just-dna-registry` rename | The package was renamed; the root `pyproject.toml` depends on `just-dna-registry>=0.18.2` and the sibling checkout declares that name. Paper 2 already says `just-dna-registry`, so the two companion papers currently disagree about what the service is called. | Whole-paper rename pass, roughly ten sites including the Code Availability URL. Deliberately not done as part of the v0.3 reference retarget. | Editing only |
| Module-contract overlap with Paper 2 | Paper 1 §2.2/§3.4 and Paper 2 §3.1/§3.5 describe the same artifact. Read side by side this invites a salami-slicing objection. | Cut Paper 1 to the consuming view per the boundary table in the strategy doc; cite the companion for the authoring half; do not re-derive its tables. | Editing only |
| Benchmark number is now load-bearing for two papers | Paper 2's Method states whole-genome annotation "in under 40 seconds" on Paper 1's authority. If Paper 1's number moves, Paper 2 is wrong. | Keep the two in lockstep; re-check Paper 2 §3.2 whenever §5.1 is re-run. | Cross-repo check |
| Paper 1's comparison table must not duplicate Paper 2's | Paper 2 ships its own comparison (annotation engines, OakVar, CIViC, PubMind-DB, raw LLM). | Paper 1's table compares *consumers* — VEP, ANNOVAR, OpenCRAVAT/OakVar, Galaxy, PRSice, PGS Catalog tooling. Still must not be written from memory. | Needs research/checking |

## Status (v0.2 update)

**Resolved / implemented:**
- **Benchmark reproducibility** — §5.1 annotation-speed benchmark now states the input is the co-author genome released publicly on Zenodo (record 18370498, CC0), the same genome as the §5.2 PRS benchmark, so the pipeline is reproducible end-to-end. The "not publicly available" wording is removed and the setup table cites the Zenodo record.
- **PRS match-rate explanation** — the 50–54% match rate is explained in §5.2 (expected: absent/uncalled variants, indels, multiallelic sites, strand/build differences; comparable across engines; does not affect concordance).
- **Figure placeholder** — the "[screenshot pending]" marker on Figure 2 is removed; caption is now a normal descriptive caption. (Other figures still need final image assets.)
- **AI/MCP scope** — agentic content trimmed to a one-line companion pointer + one feature-level in-app-creator section; no AI performance/accuracy claims in Paper 1.
- **Marketplace/format narrative** — `just-dna-format` and `just-dna-marketplace` are integrated across abstract, introduction, §2.2 (module contract), §3.4 (ecosystem growth), and the code-availability table.
- **AI-module trust boundary** — AI-generated modules labelled research-use first drafts via the `curator` field, kept distinct from expert-curated modules.

**Still open (need assets / research / user input / a submission step):**
- **State-of-the-art comparison table** — NOT added. Per this doc's own caution, it must not be invented from memory; needs a verified pass with current feature checks and cited sources for VEP, ANNOVAR, OpenCRAVAT/OakVar, Galaxy, PRSice, PGS Catalog tooling.
- **Bibliography** — still carried from the combined manuscript; needs 2022–2026 additions and citation hygiene before journal submission.
- **ROGEN funding text** — visible TODO; needs the confirmed mandatory wording.
- **Remaining figures** — need final screenshots/captions (Figures 1, 3, 4).
- **Paper 2 preprint** — must be posted (arXiv/Zenodo) before Paper 1's companion citation is live.


## Correction (v0.3, agentic ownership)

An earlier v0.3 pass removed "multi-agent architecture, the models used, the cross-model
consensus mechanism" from Paper 1 §4's deferral list. That was wrong and is reverted. **Paper 2
is the agentic paper; all AI-authoring claims are its subject**, and Paper 1 §4 defers the agent
architecture and the models behind both the single and team modes to it.

Only the *comparative* claim stays off the table in both papers — team-beats-single,
model-beats-model, consensus-reduces-hallucination — because Paper 2's scored runs use one model
through one host and report it that way. That is a claims-discipline rule, not a scope exclusion.

**Resolved: §4 is implementation-agnostic.** The in-app Agno team is the legacy path, and
whether it is cut or rebuilt on `just-module-creator`'s tools is undecided — so Paper 1 §4 no
longer describes the two-mode single-agent / research-team structure, does not name the models,
and no longer claims a module is produced "in minutes" (§3.4). It keeps only what survives
either outcome: an in-app drafting entry point, the same deterministic artifacts whatever drafts
them, the same validator and compiler as a hand-authored module, and the `curator` field.

This closes the dangling deferral with no cross-repo work. **Do not add the in-app Agno path to
Paper 2** — that would document a legacy implementation into an anonymous conference submission
which then needs correcting if the path is cut.

| Blocker | Why it matters | Suggested workaround | Type |
|---|---|---|---|
| In-app creator's fate undecided | Not a submission blocker, since §4 now reads correctly under either outcome. But if Agno is cut *after* submission, §4's "in-app drafting entry point" becomes false. | Decide before the camera-ready. If it is rebuilt on `just-module-creator`'s tools, both papers gain a sentence tying the in-app path and the plugin path to one toolchain — a stronger story than either tells now. | Needs decision |
