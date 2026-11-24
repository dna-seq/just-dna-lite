# Roadmap

Open work only, in order. Each item is a section `## RMn — name` whose first line says its state and its
owner. A done item leaves this file in the commit that lands it. Written on 2026-11-18 from `CLAUDE.md`,
`docs/INVESTIGATE_*.md`, `plans/handoffs/`, the open issues and the code as it was that day; nothing
before that day is carried as backlog. The lead seat keeps it (`docs/seats/LEAD.md`).

## RM4 — longevity-loci's re-curated longevity module, in the app and in the paper

**State:** waits until 2026-11-30: the maintainer's merge of pull request 37, reviewed by the lead on 2026-11-19 at bcd2f7b, and again on 2026-11-22 at ffcfdfe (the literature sweep's 8 loci: 172 loci, 513 rows, 697 studies; spec valid, routing tests 9 pass, recompiled to content signature 997b3356 as claimed); on 2026-11-25 still at ffcfdfe, checks green, mergeable, not merged · **Owner:** lead

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

**State:** unattended: the rest of the open issues; #7, #10 and #11 answered and closed and #17 answered on 2026-11-20 (desk #68), #19 and #20 planned as RM10 · **Owner:** correspondence

Twelve issues are open, most of them feature suggestions from June 2026 (#7 to #20), with one outside
pull request (#28, the Windows installer, reviewed in `docs/reviews/`). Several are overtaken by what
has landed (#7 and #11, the MCP server and the module-creator plugin; #10, the AI prompt links in
reports). The correspondence seat reads them once and proposes, for each, a roadmap item, an answer
or a close; nothing is posted without the maintainer's word on that text.

## RM7 — A module's digest is shown, never verified

**State:** waits until 2026-11-26: put the design question (what a local or sandbox module shows) to the maintainer · **Owner:** lead

The report prints each module's `artifact.digest` as the module's own claim; nothing calls
`verify_manifest` (`CLAUDE.md`, "Report"). Wiring it with `require_marketplace=True` rejects every
local compile, so the design question is what a local or sandbox module shows instead.

## RM8 — A weights-led module's haplotype pairs are never called

**State:** waits until 2026-11-30: pull request 37 merged, so the spec is on the trunk (not merged on 2026-11-25) · **Owner:** lead

Longevity Map 2.0.0 is led by `variants` and also carries `haplotypes` and `diplotypes`, so that APOE
is read once, as its ε pair. The engine sends a module to the phenotype caller only when it is
phenotype-led, so on the public demo genome the 2.0.0 report shows no APOE result (found by
longevity-loci's lead while checking pull request 37, 2026-11-19; not reproduced here yet). Reproduce
it on the compiled spec in `data/modules/longevitymap_v2/` once the pull request is merged, then make
the engine call the pairs of a module that has both, with the result in the report's combined
section. It blocks publishing 2.0.0 (`docs/LONGEVITYMAP_V2_RELEASE.md`), not the merge.

## RM9 — Republish superhuman with the 0.8.9 compiler's indel fix

**State:** blocked: desk #65 (if nobody answers, nothing is republished) · **Owner:** lead

Upstream RM449: the published `superhuman@2.4.1` was compiled before an rsID row's indel genotype went
on one event. Rebuilt locally on 2026-11-19 with compiler 0.8.9 (gitignored, `data/interim/v1_port/`):
spec version 2.5.0, all 118 positions resolved, `rs766212849` on one event (2:166278198, a 5-base
deletion). Republishing is the maintainer's. Not ours: the published `thrombophilia@2.0.1` that
RM449 also names; this repository builds thrombophilia as the 1.1.0 port of 9 positions, which lacks
the named row. The local Ensembl cache was an unfinished pull (chromosomes 9, MT, X, Y missing) and
completed during the rebuild (14 GB, moved off the home quota on 2026-11-20).
