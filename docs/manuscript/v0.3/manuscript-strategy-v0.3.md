# **Just-DNA-Lite Manuscript Strategy (v0.3 — Paper 2 replaced)**

**Supersedes:** `../v0.2/manuscript-strategy-v0.2.md` (the post-split strategy).
**What changed:** Paper 2 is a different paper. The `just-dna-agents` draft is retired and
the companion is now the **just-module-creator** manuscript, which lives in that repository
and targets a conference rather than a journal. Paper 1 is unchanged in substance; its
companion references have been retargeted to what Paper 2 actually contains.

## **What v0.3 is**

| File | What it is |
|---|---|
| `manuscript-strategy-v0.3.md` | This document. |
| `paper1-just-dna-lite.md` | Paper 1, carried from v0.2 with its nine companion references rewritten. |
| `paper1-blockers.md` | Paper 1's pre-submission blockers, updated. |
| `paper2-just-module-creator.md` | **A mirror.** The editable draft is `just-module-creator/docs/manuscript/manuscript.tex`. |
| `paper2-references.bib` | Mirror of Paper 2's bibliography, so citations dropped by the pandoc rendering are recoverable here. |

Paper 2 is mirrored, not owned. `just-module-creator/docs/manuscript/README.md` declares that
repo the workspace for the draft, and the mirror here exists so the two papers can be read as a
pair and checked against each other. Edits go upstream; refresh by re-copying. The mirrored
Markdown is a pandoc rendering of the `.tex` and **loses every `\cite` key** — citation markers
show up as stray commas in the prose. Read the upstream `.tex` when a citation matters.

## **The two papers as they now stand**

- **Paper 1 — Just-DNA-Lite (platform).** *Just-DNA-Lite: a Local-First, Open-Source Platform
  for Personal Genome Annotation and Polygenic Risk Scoring.* Journal submission, venue per the
  table below. Named authors. Owns the annotation pipeline, the web UI, the module format and
  registry **from the consuming side**, and **both `just-prs` and `just-prs-mcp`** — the PRS
  engine and the typed access layer that lets an assistant call it.
- **Paper 2 — the Just-DNA ecosystem (authoring).** *Creating and Sharing Genomic Annotation
  Modules with AI: The Just-DNA Ecosystem.* EASRP 2026 (European AI Summer Research Paper),
  **anonymous, 8-page A4 main text**. This is **the agentic paper** — every AI-authoring claim
  belongs to it. Covers `just-module-creator` as a plugin for Claude Code
  and Codex (60 typed MCP tools, 20 skills), the module artifact and its checks,
  `just-dna-format` / `just-dna-compiler` / `just-dna-enricher` / `just-dna-registry`, the
  local / test-registry / public-catalog publication routes, an authoring scoring protocol, and
  the first eight published modules across three namespaces.

## **Three things the replacement changes, and what to do about each**

### 1. `just-dna-agents` is deprecated; `just-prs-mcp` comes into Paper 1

The retired Paper 2 promised a unified agentic toolkit: PRS over MCP, annotation orchestration,
explanatory graphics, interpretation prompts, an Agno multi-agent team, a cross-model consensus
mechanism, with `just-prs-mcp` folding into it. **The new Paper 2 covers none of that, and says
so explicitly** — it does not require its own orchestration runtime and it declines to evaluate
any agent-team topology.

`just-dna-agents` is deprecated. It was an earlier module-authoring MCP server and compiler, and
`just-module-creator` replaces it; its `just_dna_agents_mcp` server exposed authoring and
compilation tools only — no PRS, chart, or interpretation tool was ever in it. The v0.2 open
item "Confirm Agno migration from just-dna-lite into dna-agents complete" closes as *not
happening*, and the repository is **dropped from Paper 1's Code Availability table** rather than
listed as available software.

Because that merge never happened, **`just-prs-mcp` still stands on its own — and it belongs to
Paper 1.** It is on PyPI, runs locally via `uvx` with no API key, is listed in the BioContextAI
Registry, and exposes typed tools for catalog search, build and ancestry detection, VCF and
array normalization, per-model and per-trait scoring, reference-population comparison,
absolute-risk context, and quality assessment, plus trait-panel graphics, prompts, and a bundled
interpretation skill. So Paper 1 §3.2.1 was true all along and merely named the wrong
repository. It has been **rewritten as a first-class Paper 1 contribution** rather than hedged
as an availability pointer, with the argument the section needed: an assistant asked to score a
genome otherwise writes its own scoring loop and reports a number with no record of which models
were used or how many variants matched, and a typed tool call replaces that with the benchmarked
engine plus travelling provenance. Two of Paper 1's own principles carry into it directly —
the server runs locally so privacy stays structural, and the tools return match rates, quality
tiers, reference population, and inter-model disagreement, so §6.3's transparency commitment
survives a conversational interface.

**The resulting boundary is consume-versus-author, and it is cleaner than v0.2's.** Both papers
involve AI assistants and MCP, which a reviewer reading the pair will notice, so each states the
direction explicitly: in Paper 1 the assistant *calls* validated operations and computes nothing
itself; in Paper 2 the assistant *produces* new annotation content that must pass checks before
it can be used. Paper 1 §3.2.1 and its scope paragraph now say so in as many words.

**All agentic material is Paper 2's, including the in-app creator's agent team.** Do not read the
retirement of the `just-dna-agents` draft as leaving the multi-agent work unpapered: Paper 2 is
the agentic paper, and Paper 1 §4 defers the agent architecture and the models behind both
modes to it.

**The in-app Agno team is legacy, and that decides how Paper 1 writes about it.** The Agno
`Team` lives in this repository, not in the deprecated `just-dna-agents` — the web UI's
single/team toggle drives
`just-dna-pipelines/src/just_dna_pipelines/agents/module_creator.py`, which builds one to three
researchers each on a different model (Gemini, OpenAI, Claude, by available API key) with
BioContext MCP tools, a Gemini reviewer with Google Search for fact-checking, and a Gemini Pro
principal investigator holding the write/validate/register tools. It is the legacy path.
Whether it is removed outright or rebuilt on `just-module-creator`'s tools **is undecided**.

A paper cannot describe an architecture whose future is undecided as one of its capabilities. So
**Paper 1 §4 is now implementation-agnostic** and no longer states the two-mode
single-agent / research-team structure, does not name the models, and drops the "in minutes"
timing claim from §3.4. What it keeps is what survives either outcome: the app has an in-app
drafting entry point; whatever drafts a module emits the same deterministic artifacts; those
artifacts pass the same validator and compiler as a hand-authored module; the `curator` field
keeps AI-drafted content distinct. §4 now says the artifact contract rather than the drafting
method is what the platform depends on — which is true today, true if Agno is cut, and true if
it is rebuilt.

This also **resolves the dangling deferral without any cross-repo work.** Paper 2 documents the
plugin path and states the plugin "does not require its own orchestration runtime" because the
host supplies the agent — true of the plugin, and it would have been false of the in-app Agno
team. Since Paper 1 no longer describes that team, Paper 2 needs no paragraph about it, and §4's
deferral points at the authoring workflow Paper 2 actually documents. **Do not add the in-app
Agno path to Paper 2**; it would document a legacy implementation into an anonymous conference
submission that then has to be corrected if the path is cut.

Revisit only if the rebuild happens: a §4 written on `just-module-creator`'s tools would put
Paper 1's in-app creator and Paper 2's plugin on one toolchain, which is a stronger story than
either paper tells now, and worth a sentence in each at that point.

**What neither paper may claim** is a comparison: that the team mode beats the single mode, that
one model beats another, or that cross-model consensus reduces hallucination. Paper 2's scored
runs use one model through one host and say so; there is no evidence for a comparative claim in
either place. This is a discipline rule about claims, not a statement that the multi-agent work
is out of scope.

What genuinely has no home is the *orchestration* story — one conversation combining annotation,
PRS, and other models. No paper claims it and Paper 1 no longer points at it. If it is built, it
is Paper 3.

### 2. The module contract is now claimed by both papers — resolve it by side, not by ownership

This is the live scope risk in v0.3. Paper 1's novelty defense in v0.2 rested on
`just-dna-format` plus the registry plus fsspec discovery. Paper 2's first and third
contributions are the module contract and how modules move between local, test, and public
stores. Read side by side, the two papers currently describe the same artifact.

**This is not salami-slicing and does not need to be, provided each paper keeps to its own
side of the artifact boundary:**

| | Paper 1 (consuming) | Paper 2 (authoring) |
|---|---|---|
| Module contract | what a compiled artifact must contain to be *joined* to a genome; discovery, lead-table classification, integrity claims at read time | what an author writes; which table holds which claim; the schema read live from the installed compiler |
| Registry | discovery, install, version pinning from the consumer's side | publish, rehearse on the test registry, version, own a namespace |
| Compiler | not described; the artifact is the input | validation, resolution, content signature, what compilation does and does not establish |
| Evidence fields | how `direction`, `clin_sig`, provenance reach a report | how a row earns them, and which checks could have failed |
| MCP / assistants | the assistant **calls** validated operations (`just-prs-mcp`) and computes nothing itself | the assistant **produces** annotation content that must pass checks before use |

Concretely, before either submission: Paper 1 §2.2 and §3.4 should be re-read against Paper 2
§3.1 and §3.5 and cut back to the consuming view, and each paper should cite the other for the
half it does not own. Neither paper should re-derive the other's tables.

The reciprocal citation already holds in one direction and must be kept: Paper 2 defers all
runtime benchmarks to Paper 1 and states whole-genome annotation "in under 40 seconds", which
matches Paper 1's abstract, §1, and §5.1. **If Paper 1's benchmark number ever changes,
Paper 2's Method section changes with it.**

### 3. The sequencing from v0.2 is inverted

v0.2 said: post Paper 2 first as a preprint, then submit Paper 1 citing it. That was written
when Paper 2 was a lean preprint carrying its own evaluation burden. It no longer applies:

- Paper 2 is an **anonymous conference submission**. It cannot be posted as a preprint under
  named authorship before review without risking the venue's anonymity policy — check EASRP
  2026's specific preprint policy before assuming either way.
- Paper 2 cites Paper 1 **six times and depends on it for every runtime claim**. Its own
  simulated review flags this as a weakness: "the companion paper does not exist yet … a
  reviewer may refuse to evaluate half the system on a promise."

**So Paper 1 goes public first.** The cheapest fix for Paper 2's biggest structural weakness is
a citable Paper 1 record. Post Paper 1 to arXiv (with a Zenodo/OSF archival record if a DOI is
needed), then Paper 2 cites a real artifact instead of "in preparation". Paper 1 cites Paper 2
as "in review" and depends on it for nothing empirical.

The bioRxiv/medRxiv caution from v0.1 and v0.2 stands unchanged: do not put the citation chain
on a venue that has already rejected this work twice for gene-disease inference. arXiv for
speed, Zenodo/OSF for a DOI.

## **Journal and venue targets**

### Paper 1 — unchanged from v0.2

| Journal | Recent JIF | Fit | Positioning |
|---|---|---|---|
| **Bioinformatics** | 5.4 | **Best realistic fit** | Lead with system-level novelty (no-code modules-as-data, formal module contract, registry, fsspec ecosystem, structural local privacy, benchmarked PRS/annotation) as one coherent local-first architecture. |
| GigaScience | 3.9 | Strong open-science fit | Verify editorial stability; prepare an exceptional FAIR/reproducibility package. |
| BMC Bioinformatics | 3.3 | Safest software-paper fit | Fallback if speed/fit matter more than prestige. |
| Genome Biology | 9.4 | Reach | Only with broader validation and a compact state-of-the-art comparison table. |
| PLOS Computational Biology | 3.6 | Strong open-source fit | Frame as open-source infrastructure; ship test data and exact reproducibility commands. |

If IF > 5 is mandatory: Bioinformatics first, Genome Biology as reach. If IF > 3 is acceptable:
GigaScience → PLOS Comp Biol → BMC Bioinformatics → Bioinformatics.

### Paper 2 — now a conference, not a journal

EASRP 2026 is the current target and the 8-page anonymous format is already what the draft is
written to. The v0.2 journal table for Paper 2 (BMC Bioinformatics / Bioinformatics) no longer
applies as a first target. If EASRP does not land, the journal route is a methods/software paper
on validated module authoring — but that version needs what its own simulated review asks for:
a comparison against PubMind on overlapping variants, and either a real creation evaluation or
an honest methods-only framing.

## **Claims discipline (carried forward, re-scoped)**

Paper 1 may state that authored modules are checked before they are registered. It may not
quantify creation accuracy, claim reduced hallucination, or claim a baseline comparison.
This survives the Paper 2 swap intact — and gets easier, because the new Paper 2 makes no
accuracy claim either. Its three scored runs are one prompt against one expert-curated
reference module, reported as such.

Paper 2's own maturity split, as the draft currently stands:

- **Claimed as results:** the plugin surface (60 tools, 20 skills); deterministic validation and
  compilation; the publication routes; the catalog inventory (8 modules, 19 versions, 3
  namespaces, 885 variants); the measured 3,668 rows whose `provenance_quote` was the article
  title.
- **Claimed narrowly and correctly:** three scored authoring runs on one prompt, plugin version
  fixed, one model through one host.
- **Explicitly not claimed:** recall/precision at scale, model or host sensitivity, free-text
  conclusion quality, usability or task timing.

## **Remaining pre-submission work**

**Paper 1:**
- Re-read §2.2 and §3.4 against Paper 2 §3.1/§3.5 and cut to the consuming view (item 2 above).
- **Rename `just-dna-marketplace` → `just-dna-registry` throughout.** The package has been
  renamed; the root `pyproject.toml` depends on `just-dna-registry>=0.18.2` and the sibling
  checkout's own `pyproject.toml` declares that name. Paper 2 already uses `just-dna-registry`,
  so the two companion papers currently disagree about what the service is called. Roughly ten
  sites in Paper 1, including the Code Availability URL. Not done here — it is a whole-paper
  editorial pass, not a reference retarget.
- State-of-the-art comparison table: still not added, still must not be written from memory.
  Note that Paper 2 now ships its own comparison table (annotation engines, OakVar, CIViC,
  PubMind-DB, raw LLM); Paper 1's must compare *consumers* — VEP, ANNOVAR, OpenCRAVAT/OakVar,
  Galaxy, PRSice, PGS Catalog tooling — and not duplicate it.
- Bibliography: 2022–2026 additions and citation hygiene.
- ROGEN funding text: visible TODO needs the confirmed mandatory wording.
- Figures 1, 3, 4 need final assets.

**Paper 2 (upstream, in just-module-creator):**
- Wait on a citable Paper 1 record before submission if the schedule allows; six citations
  currently resolve to "in preparation".
- Address the PubMind comparison its own simulated review asks for.
- Confirm EASRP 2026's preprint and anonymity policy before any public posting.

## **Open items**

- [ ] Post Paper 1 first (arXiv, plus Zenodo/OSF if a DOI is needed). Reversed from v0.2.
- [ ] Check EASRP 2026 preprint/anonymity policy.
- [ ] Resolve the module-contract overlap by side (item 2); cut Paper 1 §2.2/§3.4 accordingly.
- [ ] Rename `just-dna-marketplace` → `just-dna-registry` across Paper 1.
- [ ] Keep Paper 1's 40-second benchmark and Paper 2's Method statement of it in lockstep.
- [ ] Add Paper 1's consumer-side comparison table, without duplicating Paper 2's.
- [ ] Decide whether the *orchestration* layer (one conversation across annotation, PRS, and
      other models; multi-agent creation; cross-model consensus) is being built. Until it is, no
      paper points at it. If it is built, it is Paper 3. PRS over MCP is not part of this
      question — `just-prs-mcp` ships it today.
- [ ] Decide the in-app creator's fate — cut Agno, or rebuild it on `just-module-creator`'s
      tools. Paper 1 §4 is written to survive either, so this does not block submission; if the
      rebuild lands before submission, add a sentence to each paper tying the two paths to one
      toolchain.
- [ ] Resolve Paper 2 authorship and author order when the anonymous version is de-anonymized.
- [ ] Refresh the `paper2-just-module-creator.md` mirror before any joint read-through.

## **Retired with this version**

`../v0.2/paper2-dna-agents.md` — the `just-dna-agents` agentic-toolkit draft. Kept for
reference; superseded, not to be submitted. `just-module-creator`'s manuscript README makes the
same call from the other side: "That draft described `just-dna-agents`, which this plugin
replaced. Use it for inspiration only."
