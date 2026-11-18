# Roadmap

Open work only, in order. Each item is a section `## RMn — name` whose first line says its state and its
owner. A done item leaves this file in the commit that lands it. Written on 2026-11-18 from `CLAUDE.md`,
`docs/INVESTIGATE_*.md`, `plans/handoffs/`, the open issues and the code as it was that day; nothing
before that day is carried as backlog. The lead seat keeps it (`docs/seats/LEAD.md`).

## RM3 — The web UI treats every sample as GRCh38

**State:** blocked: desk #59, yes after a present (if nobody answers, the small fix is built: a clear refusal of a file whose header is not GRCh38) · **Owner:** lead

`docs/INVESTIGATE_GRCH37_UI.md` (2026-10-10, code reading only): the UI sets `genome_build = "GRCh38"` on
every file load, so a GRCh37 or T2T sample is scored, ancestry-called and position-joined as GRCh38
with no warning; results are silently wrong or empty. Two sizes of answer, the maintainer's to pick:
refuse or warn on a build the header says is not GRCh38 (small), or pass the real build to just-prs so
PRS uses the Catalog's harmonized files while annotation stays GRCh38-only with a banner (larger).
The paper's input-format claims depend on which.

## RM4 — longevity-loci's re-curated longevity module, in the app and in the paper

**State:** waits until 2026-11-21: longevity-loci's pull request, to review · **Owner:** lead

The repository `dna-seq/longevity-loci` re-curated the longevity module; its lead is building a deck
comparing it with the Generation I port this repository publishes as Longevity Map (asked by the
maintainer, 2026-11-18). Here, `docs/longevitymap_v2/` holds the earlier research and requirements,
and the paper's section 3.1 and Table S14 describe the module before the re-curation. Open, and the
maintainer's: whether the app's default module list and the registry take the new module, under which
name, and whether the paper's round v0.7 describes it (the reviser's work once decided).

Decided on 2026-11-18 (the maintainer, in `#agent-chat > general chat`, relayed to desk #60): the paper
takes the re-curated module in as "a key module of the whole system", with a section on its curation
and what the new longevity analysis taught, not only as an example. That is the reviser's to write
with him, from the item handed to it that day (counts, method and source commit from
longevity-loci's lead). Decided on 2026-11-19 (the maintainer, in longevity-loci's session, relayed by its lead): "the new
module shall supreseed v1 port ... Keep v1 port version frozen and pr the ready module, supplementaries
and publishing surface go into PR." longevity-loci's lead opens that pull request here (the 2.0.0 spec
under `data/modules/longevitymap_v2/`, a release runbook, the `modules.yaml` description, its
supplements under `docs/longevitymap_v2/`); the lead reviews it, the maintainer merges and publishes.

## RM5 — The Ensembl join adds rsIDs only

**State:** waits until 2026-12-02: look for the enricher release that pulls the snapshot's `groups/` sidecars (upstream S150, RM437, planned for 0.9) · **Owner:** lead

Since the enricher's split snapshot replaced our downloader, the Ensembl step carries `chrom, start,
ref, alt, id` and no consequence, ClinVar or frequency columns (`CLAUDE.md`, "Build traps"). The
handoff of 2026-11-03 in `plans/handoffs/` designed a richer split layout from the new Ensembl
variation VCF; upstream took that direction, so nothing is built here until its release. Then: pull
the groups, join them, and only then call the step's output annotation.

## RM6 — The open issues, sorted into plan or answered

**State:** waits until 2026-11-21: the correspondence seat's first reading of the issues · **Owner:** correspondence

Twelve issues are open, most of them feature suggestions from June 2026 (#7 to #20), with one outside
pull request (#28, the Windows installer, reviewed in `docs/reviews/`). Several are overtaken by what
has landed (#7 and #11, the MCP server and the module-creator plugin; #10, the AI prompt links in
reports). The correspondence seat reads them once and proposes, for each, a roadmap item, an answer
or a close; nothing is posted without the maintainer's word on that text.

## RM7 — A module's digest is shown, never verified

**State:** after RM3 · **Owner:** lead

The report prints each module's `artifact.digest` as the module's own claim; nothing calls
`verify_manifest` (`CLAUDE.md`, "Report"). Wiring it with `require_marketplace=True` rejects every
local compile, so the design question is what a local or sandbox module shows instead.
