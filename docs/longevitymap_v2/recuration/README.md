# Longevity Map 2.0.0: the re-curation

The module in `data/modules/longevitymap_v2/` is the re-curation the v2 design in this folder's parent asked for. It
was built in [dna-seq/longevity-loci](https://github.com/dna-seq/longevity-loci), where every row, note, decision and
check lives; this folder carries what the paper and the release need from it.

| File | What it is |
|---|---|
| `loci.csv` | the 164 loci of the 2.0.0 build: tier, mechanism, age of action, verdict, second-signal link, lead rsIDs, and the row file in longevity-loci that holds the evidence (rows at longevity-loci 12c673f, the commit the module was exported from) |
| `MANUSCRIPT_SECTION_DRAFT.md` | a draft section for the paper (the module as a key part of the system, and what the curation found), for the reviser to adapt or decline |
| `../../../data/modules/longevitymap_v2/quote_sources.csv` | every quote the module's studies rest on, with its source; checked verbatim against the cached text in longevity-loci |

How a row was made, the tier rules and every call with the alternative it rejected: longevity-loci's
`README.md`, `docs/FORMATS.md` and `docs/DECISIONS.md` (D1–D42). The release steps: `docs/LONGEVITYMAP_V2_RELEASE.md`.

**At a glance (2.0.0).** 164 loci, 163 rsIDs, 489 genotype rows (113 protective, 99 risk, 277 neutral reference),
679 study rows citing 51 papers. Tiers: A 15, B 73, C 41, D 35. No weights are authored (`weighting: scale: none`),
so no per-variant sum is formed. Content signature `sha256:aebf5e38…`, the same under just-dna-compiler 0.8.5
(this repository's lock) and 0.8.6 (where it was rehearsed on the polygon).

**Not in 2.0.0.** A literature sweep of 2015 to October 2026 has since added five loci in longevity-loci (rows 170
to 174, not yet through their adversarial review); they come as a later version.

Paths named inside the spec's own files (`module_spec.yaml`'s comment, `provenance.json`) are longevity-loci's, where
the module was authored.
