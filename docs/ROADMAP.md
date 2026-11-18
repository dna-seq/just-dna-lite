# Roadmap

Open work only, in order. Each item is a section `## RMn — name` whose first line says its state and its
owner. A done item leaves this file in the commit that lands it. Written on 2026-11-18 from `CLAUDE.md`,
`docs/INVESTIGATE_*.md`, `plans/handoffs/`, the open issues and the code as it was that day; nothing
before that day is carried as backlog. The lead seat keeps it (`docs/seats/LEAD.md`).

## RM1 — The README and the FAQ promise what the code does not do

**State:** unattended · **Owner:** lead

`README.md` (line 122) says the app takes 23andMe, AncestryDNA and MyHeritage files, and `docs/FAQ.md`
(line 33) says GRCh37 is handled through liftover. `CLAUDE.md`, "Writing preferences", says both are
planned and not done, and that no VCF liftover exists. Decided by that rule: reword both to what the
code does today, checked against the upload path, and say the limits where a reader meets them.

## RM2 — Reproduce the haploid-genotype crash in single-score PRS

**State:** unattended · **Owner:** lead

`docs/INVESTIGATE_HAPLOID_PRS.md` (2026-10-13) found by code reading that the Polars scoring engine
raises on a haploid GT such as `"1"` (male chrX, chrM), on just-prs 0.10.1. The lock has moved to
just-prs 0.11 since. Read-only: run its "To check" list on a VCF with haploid calls against the
version locked now, and write what happens. A crash that is the library's goes to the correspondence
seat as an upstream report; one that is ours becomes its own item.

## RM3 — The web UI treats every sample as GRCh38

**State:** waits until 2026-11-21: the maintainer's ordering of this first roadmap, asked in the lead's session on 2026-11-18 · **Owner:** lead

`docs/INVESTIGATE_GRCH37_UI.md` (2026-10-10, code reading only): the UI sets `genome_build = "GRCh38"` on
every file load, so a GRCh37 or T2T sample is scored, ancestry-called and position-joined as GRCh38
with no warning; results are silently wrong or empty. Two sizes of answer, the maintainer's to pick:
refuse or warn on a build the header says is not GRCh38 (small), or pass the real build to just-prs so
PRS uses the Catalog's harmonized files while annotation stays GRCh38-only with a banner (larger).
The paper's input-format claims depend on which.

## RM4 — longevity-loci's re-curated longevity module, in the app and in the paper

**State:** waits until 2026-11-21: the maintainer's ordering of this first roadmap, asked in the lead's session on 2026-11-18 · **Owner:** lead

The repository `dna-seq/longevity-loci` re-curated the longevity module; its lead is building a deck
comparing it with the Generation I port this repository publishes as Longevity Map (asked by the
maintainer, 2026-11-18). Here, `docs/longevitymap_v2/` holds the earlier research and requirements,
and the paper's section 3.1 and Table S14 describe the module before the re-curation. Open, and the
maintainer's: whether the app's default module list and the registry take the new module, under which
name, and whether the paper's round v0.7 describes it (the reviser's work once decided).

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

**State:** waits until 2026-11-21: the maintainer's ordering of this first roadmap, asked in the lead's session on 2026-11-18 · **Owner:** lead

The report prints each module's `artifact.digest` as the module's own claim; nothing calls
`verify_manifest` (`CLAUDE.md`, "Report"). Wiring it with `require_marketplace=True` rejects every
local compile, so the design question is what a local or sandbox module shows instead.
