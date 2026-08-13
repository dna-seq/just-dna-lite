# Just-DNA-Seq Workshop — CRABS 2026

**Event:** CRABS 2026 (Computational Research Advances in Biomedical Sciences), Kyiv School of Economics, 16–23 August 2026
**Slots:** Friday 21 August, ICU Event Hall
**Instructors:** Livia Zaharia (IBIMA, Rostock University Medical Center) and Oksana Lobko (just-dna-seq open-source team)
**Format:** In-person, hands-on, two parts on the same day
**Repositories:** [just-dna-lite](https://github.com/dna-seq/just-dna-lite) · [just-dna-compiler](https://github.com/dna-seq/just-dna-compiler) · [dna-seq-claude-marketplace](https://github.com/dna-seq/dna-seq-claude-marketplace)

| | Title | Time | Length |
|---|---|---|---|
| Part 1 | Hack Your Own Genome — Just-DNA-Seq Workshop, Part 1 | 12:30–14:00 | 90 min |
| Part 2 | Hack Your Own Genomic Module with AI — Just-DNA-Seq Workshop, Part 2 | 14:30–16:45 | 135 min |

Total hands-on time is 225 minutes, roughly double the RoBioinfo 2026 session.

---

## Schedule conflict to resolve with the organizers

The published sheet lists **Part 1 at 12:30–14:00** and **lunch at 13:30–14:30**. Those overlap by thirty minutes. Part 2 begins at 14:30, which implies the intended lunch is 14:00–14:30.

This plan assumes **Part 1 runs the full 90 minutes and lunch is 14:00–14:30**. If the organizers instead hold lunch at 13:30 and cut Part 1 to sixty minutes, drop the PRS segment (Maryna Korshevniuk's "From GWAS to PRS and Beyond" lecture runs Thursday 11:15, so the theory is covered) and the export segment, keeping modules, report and variant interrogation.

Confirm this before the programme is printed.

---

## What changed since RoBioinfo 2026

Four things, and they reshape the session rather than extend it.

**The 14 GB Ensembl download is no longer a prerequisite.** The RoBioinfo plan required every participant to run `uv run pipelines ensembl-setup` at home, a 30–60 minute download that was its single largest failure mode. Two developments remove it. First, the module set on HuggingFace has grown from five to ten and now includes `cardio`, `cancer` and `pathogenic`, which are built from ClinVar snapshots. Clinical significance flagging arrives with the modules. Second, the `ensembl` MCP plugin queries live Ensembl over the network with no API key and no local cache, which covers the per-variant lookups a workshop actually performs. Participants now need `uv`, a clone, and `uv sync`. Nothing else.

**Part 2 is a different session, not a longer one.** RoBioinfo's AI Module Creator segment was a 25-minute demonstration of a button inside the web UI. Part 2 is now an authoring workflow in the participant's own AI coding agent, running `just-dna-compiler` and `just-dna-enricher` (both at 0.5.4), ending in a signed, published module. The web UI's Module Manager remains available as a fallback lane for participants who cannot get an agent working.

**The registry is real and nearly empty.** `module-registry.just-dna.life` responds and currently holds exactly one module, `eric-mods/lactose_tolerance`. Participants who publish on Friday will be among the first. This is worth saying out loud in the room; it converts an exercise into a contribution.

**Reports are HTML, not PDF.** The RoBioinfo plan and the current README both say PDF. Only an HTML template exists (`annotation/templates/longevity_report.html.j2`). Corrected throughout below.

---

## Part 1 — Hack Your Own Genome

### Description

Participants load a real whole-genome VCF and work through the full annotation path on their own laptop: normalisation and quality filtering, ten curated annotation modules, a generated report, tracing a flagged variant back to its underlying data, a polygenic score computed against an auto-detected ancestry reference panel, and export to Parquet and VCF for downstream analysis. Everything runs locally. No genome data leaves the machine.

The session is research-oriented. It does not cover clinical interpretation or diagnostic workflows, and it spends real time on what the numbers do not mean.

### Learning objectives

By the end, participants can:

- load and normalise a whole-genome VCF and explain what quality filtering removed and why
- run curated annotation modules and read the generated report
- trace a single reported finding back to the variant row and the source study behind it
- look up any variant against live Ensembl and ClinVar from inside their AI agent
- compute a polygenic score against an ancestry-matched reference panel and state its limitations
- export annotated data as Parquet or VCF and query it

### Timetable

| Minutes | Clock | Segment | What happens |
|---|---|---|---|
| 0–10 | 12:30 | Load a genome | Confirm `uv run start` works. Load a sample: participant's own VCF, or Livia's or Anton's public Zenodo genome. Watch the normalisation job run. While it runs, orient the room on the fields that matter: chromosome, position, reference versus alternate allele, genotype, depth, quality. |
| 10–15 | 12:40 | What filtering removed | Read the quality-filter banner. `PASS`/`.` filter values, depth ≥ 10, quality ≥ 20. Explain why gVCF reference blocks are dropped and why that is correct rather than data loss. |
| 15–35 | 12:45 | Modules and report | Select all ten modules, run, open the HTML report. Start with `longevitymap` to anchor the session in the host programme's ageing focus, then compare how a curated module (`superhuman`) and a ClinVar panel (`pathogenic`) present findings differently. |
| 35–50 | 13:05 | Interrogate one hit | Pick a single reported variant. Find its row in the annotated Parquet. Read its `state`, `weight`, `direction`, and the study behind it. Then look the same rsID up against live Ensembl and ClinVar through the `ensembl` plugin and compare. The gap between "a module flagged this" and "the literature says this" is the point of the segment. |
| 50–55 | 13:20 | Stretch | Short break in place. |
| 55–75 | 13:25 | Polygenic scores | Open the PRS tab. Ancestry is auto-detected and the matching 1000G reference panel preselected; show the confidence badge and discuss what happens when it is low. Pick one trait, compute, read the percentile. Reference back to Maryna Korshevniuk's Thursday lecture rather than re-teaching the theory. |
| 75–85 | 13:45 | Export and limits | Export annotated Parquet and a per-module VCF. Run a three-line Polars query in the terminal. Close on limitations: small effect sizes in longevity genetics, replication gaps, European-trained scores on non-European samples, penetrance versus flagging. |
| 85–90 | 13:55 | Bridge | "Every module you just ran was written by someone. After lunch you write one." |

### Notes for the instructors

The `pharmgkb` module carries no `weights.parquet` and joins on rsID plus genotype rather than position. On a VCF whose `ID` column is empty (DeepVariant output, among others) it will match nothing. This is expected behaviour, not a bug, and is worth thirty seconds of explanation if a participant asks why one module returned nothing.

Cold start is around 203 seconds; annotation of a 6.1 million variant whole genome runs in roughly 39 seconds at under 750 MB peak RAM. Start the app before the room fills.

For a room where upload chaos is a risk, `uv run start --immutable` serves the two public Zenodo genomes with uploads disabled. This guarantees everyone has data. It also blocks participants from using their own genomes, so use it only as a recovery move.

---

## Part 2 — Hack Your Own Genomic Module with AI

### Description

Participants author a genomic annotation module from scratch using an AI agent, compile it into a signed artifact, publish it to the module registry, and then load it back into just-dna-lite to annotate the genome from Part 1.

The intellectual spine of the session is the division of labour. The agent fetches literature and drafts rows. The human makes every judgement the data cannot make for itself. The compiler checks what is checkable and refuses what is not. Participants see all three, including the places where the agent is confidently wrong and nothing offline catches it.

### Learning objectives

By the end, participants can:

- install and use genomics plugins in their AI coding agent
- explain what an annotation module is: which table a given fact belongs in, and why
- draft module rows from a gene or a paper using an agent
- identify which cells a human must fill and why an agent must not fill them
- enrich, validate, compile and sign a module
- publish to the registry and consume their own module in just-dna-lite

### Timetable

| Minutes | Clock | Segment | What happens |
|---|---|---|---|
| 0–15 | 14:30 | Get your agent armed | Participants install the plugins for whichever agent they use. Four lanes, cheat-sheet on the handout (see below). Instructors circulate. Anyone stuck after ten minutes moves to the CLI lane, which always works. |
| 15–30 | 14:45 | What a module is | One CSV, one concern. Walk the table classification: a variant plus genotype goes in `variants.csv`, evidence goes in `studies.csv`, a quantity with a threshold goes in a binning table, a drug response goes in `pharm_variants.csv`. Open one reference example. `hfe_hemochromatosis` is the cleanest end-to-end case. |
| 30–60 | 15:00 | Scaffold and draft | `just-dna-compiler scaffold spec/ --kind variants.csv --kind studies.csv --name <yours>`, then draft from a gene: `just-dna-enricher draft-panel spec/ --gene HFE --use non-commercial`. Participants pick their own gene. The agent handles literature search and fills what it is allowed to fill. |
| 60–75 | 15:30 | Coffee break | Aligns with the venue's break rhythm on other days. |
| 75–105 | 15:45 | Curate, enrich, compile | The core of the session. Drafted rows carry `<<REPLACE>>` in the cells only a human can decide: genotype, state, weight, conclusion. These block every loader by design, including `enrich`. Curate first, then `just-dna-enricher enrich spec/`, then `just-dna-compiler validate spec/ --strict` and `compile spec/ out/ --strict`. |
| 105–120 | 16:15 | Sign and publish | `just-dna-compiler keygen`, `sign`, `verify`. Claim a namespace and publish to the test registry at `module-polygon.just-dna.life`. Participants who want their module public push to `module-registry.just-dna.life`. |
| 120–133 | 16:30 | Close the loop | Register the compiled module as a source in just-dna-lite and re-run annotation on the genome from Part 1. Your own module, your own genome, your own finding. |
| 133–135 | 16:43 | Wrap | Where the registry goes next, how to contribute, how to get help. |

### The lesson that has to land

There is one failure mode worth building the session's credibility on, because it is the clearest demonstration in the whole stack of what AI-assisted science gets wrong.

The `start` column is the 1-based VCF position. An author, or an agent, who subtracts one to convert to 0-based coordinates produces a module that passes `validate`, passes `compile --strict`, reports `fully_resolved: true`, and mints content-addressed GA4GH identifiers that verify cleanly. Every check passes. Every variant is at the wrong locus. This happened at scale, to a careful author, across 3,038 variants in four modules. Only online enrichment catches it, and only for about three rows in four.

A content-addressed identifier is an honest digest of whatever it was handed. It certifies the bytes, not the biology. For a room at a health intelligence conference, that distinction is worth more than any feature demonstration.

The related rules follow from the same principle and should be stated as rules, not preferences:

- Curate before you enrich. Forward resolution is allele-aware, so you cannot enrich first to discover the alleles.
- Never fill a redundancy-bearing cell from the same source that checks it. `rsid`, `chrom`, `start`, `ref`, `alts`, `clin_sig`, `doi` exist to be cross-checked; filling them from the checking source destroys the check.
- `--strict` means reproducible, not correct.
- A `risk` weight is negative.
- A genotype is `C/C`, never `CC`.

### The four agent lanes

| Lane | What works today | Command |
|---|---|---|
| **Claude Code** | Full plugin support. First-class lane. | `claude plugin marketplace add dna-seq/dna-seq-claude-marketplace`<br>`claude plugin install just-module-creator@dna-seq`<br>`claude plugin install ensembl@dna-seq` |
| **Codex** | `ensembl` installs cleanly. The module creator is not in the Codex catalog. | Clone `just-dna-compiler`, open as project. `AGENTS.md` is read automatically; drive the CLI directly. |
| **Cursor** | Does not consume Claude marketplace plugins. MCP configurable manually. | Clone the repo. `.cursor/rules/` present in `just-dna-agents`. MCP snippet in `ensembl-mcp/docs/client_setup.md`. |
| **Antigravity** | MCP configurable. `AGENTS.md` read automatically. | Agent panel → ⋯ → MCP Servers → View raw config (`~/.gemini/config/mcp_config.json`). |
| **CLI only** | Always works, no agent required. The guaranteed fallback. | `pip install just-dna-enricher` |

`just-module-creator` v0.9.0 boots with zero configuration and needs no API key for authoring. A key is required only to publish, and `registry_register` mints one in the room. It also has a hard `JMC_OFFLINE=true` switch if venue network fails.

---

## Instructor pre-work

### Blocker: `just-dna-agents` MCP server is unpublished

`uvx just-dna-agents-mcp@0.4.0` fails. The package returns HTTP 404 on PyPI, as do `just-dna-agents` and `just-module-creator`. For `just-module-creator` this is harmless, because its plugin builds from `${CLAUDE_PLUGIN_ROOT}` via `uv run --project` and never touches PyPI. For `just-dna-agents` it is fatal to the MCP server: skills, agents and commands still load, but every MCP tool breaks.

**Action:** either publish `just-dna-agents-mcp` to PyPI before August, or keep `just-dna-agents` out of the workshop entirely. This plan uses `just-module-creator` throughout and does not depend on `just-dna-agents`.

### Gap: three of the four agent lanes have no plugin path

Only Claude Code can install `just-module-creator` as a plugin. The Codex catalog (`.agents/plugins/marketplace.json`) lists only `ensembl` and `just-prs`, and `just-prs-mcp` has no `.codex-plugin/` manifest at all, so its Codex install is untested and may not work.

**Action, roughly a day of work:** add `.agents/plugins/` and `.codex-plugin/plugin.json` manifests to `just-module-creator`, and copy its skills to `.agents/skills/` the way `ensembl-mcp` does. This turns three second-class lanes into one. If it does not happen, say plainly in the room that Claude Code is the supported path and everything else uses the CLI.

### Checklist

- [ ] Confirm the Part 1 / lunch overlap with the organizers
- [ ] Publish `just-dna-agents-mcp`, or drop `just-dna-agents` from all materials
- [ ] Add Codex and Antigravity manifests to `just-module-creator` (optional but high value)
- [ ] Test `claude plugin install just-prs@dna-seq` under Codex Desktop, or remove the claim from the marketplace README
- [ ] Fix the two dead local paths in `modules.yaml` (`/data/sources/just-dna-lite/...` resolve nowhere on any participant machine)
- [ ] Correct "PDF report" to "HTML report" in the README and FAQ
- [ ] Update the README module count from five to ten
- [ ] Set the Module Manager default off Research team mode (currently `agent_use_team = True`, the 7–8 minute path)
- [ ] Bring both public genomes on USB, plus a local HTTP server, so nobody downloads 2–4 GB over venue Wi-Fi
- [ ] Pre-claim a workshop namespace on the test registry
- [ ] Print the four-lane cheat sheet

### Send to participants three days ahead

```bash
# 1. Install uv:  https://docs.astral.sh/uv/
uv python install 3.13

# 2. Clone and install
git clone https://github.com/dna-seq/just-dna-lite.git
cd just-dna-lite
uv sync

# 3. Confirm it starts
uv run start          # then open http://localhost:3000

# 4. For Part 2, install the authoring tools
pip install just-dna-enricher

# 5. If you use Claude Code, add the plugins
claude plugin marketplace add dna-seq/dna-seq-claude-marketplace
claude plugin install just-module-creator@dna-seq
claude plugin install ensembl@dna-seq
```

Optionally bring your own genome as a VCF. It must be GRCh38 and a full genome or exome. Otherwise use one of the two public genomes provided.

There is no large download this year. If you attended a previous just-dna-seq workshop and downloaded the 14 GB Ensembl cache, it still works but is not required.

---

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Venue Wi-Fi cannot serve 30 people hitting Ensembl and PyPI | Medium | USB sticks with genomes and a local wheel cache. `JMC_OFFLINE=true` for the module creator. Reference examples work fully offline. |
| Participants arrive with nothing installed | High | Sunday's software setup clinic (16.08, 12:00–13:00) is the natural place to catch this. Ask the organizers to add just-dna-lite to its tool list. |
| Agent lanes fragment the room | Medium | CLI lane is the declared fallback from minute one, not a rescue. Oksana takes the non-Claude lanes. |
| Part 2 runs long | Medium | Publishing (105–120) is the compressible segment. Compiling locally is the real deliverable; publishing is the flourish. |
| A participant's own VCF is GRCh37 or a microarray export | Medium | Public genomes ready to swap in. Do not attempt liftover in the room. |

---

## What participants will and will not get

**Will get:** a working local installation, their own genome annotated against ten curated modules, a report, a polygenic score with an ancestry-matched reference, exported data they can query, one annotation module they authored and compiled themselves, and, if they choose, that module published to a public registry.

**Will not get:** clinical interpretation, diagnostic conclusions, alignment or variant calling, support for microarray or GRCh37 data, or any claim that a flagged variant means something about their health. The scope is research and education.
