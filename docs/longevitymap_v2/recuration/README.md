# Longevity Map 2.0.0: the re-curation

The module in `data/modules/longevitymap_v2/` is the re-curation the v2 design in this folder's parent asked for. It
was built in [dna-seq/longevity-loci](https://github.com/dna-seq/longevity-loci), where every row, note, decision and
check lives; this folder carries what the paper and the release need from it.

| File | What it is |
|---|---|
| `loci.csv` | the 172 loci of the 2.0.0 build: tier, mechanism, age of action, verdict, second-signal link, lead rsIDs, and the row file in longevity-loci that holds the evidence (rows at longevity-loci 95db966, the commit the module was exported from) |
| `MANUSCRIPT_SECTION_DRAFT.md` | a draft section for the paper (the module as a key part of the system, and what the curation found), for the reviser to adapt or decline |
| `../../../data/modules/longevitymap_v2/quote_sources.csv` | every quote the module's studies rest on, with its source; checked verbatim against the cached text in longevity-loci |

How a row was made, the tier rules and every call with the alternative it rejected: longevity-loci's
`README.md`, `docs/FORMATS.md` and `docs/DECISIONS.md` (D1–D43). The release steps: `docs/LONGEVITYMAP_V2_RELEASE.md`.

**At a glance (2.0.0).** 172 loci, 171 rsIDs, 513 genotype rows (121 protective, 101 risk, 291 neutral reference),
697 study rows citing 54 papers. Tiers: A 15, B 75, C 44, D 38. No weights are authored (`weighting: scale: none`),
so no per-variant sum is formed. Content signature `sha256:997b3356…`, the same under this repository's compiler and longevity-loci's (longevity-loci
9d87300): the study notes worded for a reader (no citation ids or row numbers), and the literature sweep's rows in.

**The literature sweep is in.** A sweep of 2015 to October 2026 added eight loci (rows 170 to 177) and papers to
older rows; all were read adversarially and corrected (longevity-loci D43) before this build. No tier of the 164
earlier loci moved. `MANUSCRIPT_SECTION_DRAFT.md` was written at 169 loci and its counts predate this build.

Paths named inside the spec's own files (`module_spec.yaml`'s comment, `provenance.json`) are longevity-loci's, where
the module was authored.
