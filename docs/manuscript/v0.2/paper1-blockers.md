# Paper 1 Blockers and Workarounds

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

