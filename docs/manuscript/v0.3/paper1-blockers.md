# Paper 1 Blockers and Workarounds (v0.3)

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
