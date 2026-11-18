**just-dna-lite, where it stands** (kept current by the lead)

The app is at release v0.3.26, on the 0.8 line of the format libraries and polars 2. The repository took on three standing agent seats on 2026-11-18 (a lead, a correspondence seat, a reviser), and its first written roadmap is `docs/ROADMAP.md`. The paper is in round v0.7.

Landed on 2026-11-18, on the lead's local branch and not yet pushed: the README and the FAQ now say that the upload takes VCF files only and that GRCh37 files are not converted; a regression test shows one-allele genotypes (chrX in men, the mitochondrion) are scored as one copy by both scoring engines.

Next, in order:

- RM3, the UI treating every sample as GRCh38 (lead; a decision needed, desk #59, default the small fix)
- RM4, longevity-loci's re-curated module in the app and the paper (lead and reviser; a decision needed, desk #60)
- RM6, the twelve open issues sorted (correspondence; waits on that seat being taken)
- RM5, richer Ensembl annotation (lead; waits on an upstream release, looked at again on 2026-12-02)
