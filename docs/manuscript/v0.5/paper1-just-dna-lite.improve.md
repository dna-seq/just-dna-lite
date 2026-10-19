# Review of the v0.5 revision

The main manuscript and separate supplement were read in full and revised in place. The abstract's original qualitative account is retained. The numerical paragraph added during this pass was removed after your correction; only its premature statement that supplementary data were already online at Bioinformatics was corrected. The existing journal shortlist remains a working choice, rather than a selected venue.

The comparison in `paper1-just-dna-lite.improve.diff` starts from the files as they stood when this task began, including your existing edits. Revision marks identify the new edits as Codex's. The benchmark result tables were not changed.

## Consequential changes

### Introduction: original argument restored

The original tool-comparison paragraph has been restored, including the criticism of commercial curation as opaque. The following paragraph's claim that no existing tool makes longevity-database annotation straightforward has also been restored. Those deletions changed the authors' argument without approval. They are no longer applied changes. The Broer and Tacutu citation years remain corrected to 2015 and 2018, respectively.

### Section 3.1: LongevityMap counts

Before:

> The Longevity Variants module illustrates how existing variant-trait association databases can be wrapped into the platform's no-code module format. It builds upon the LongevityMap database (Tacutu et al., 2017), which contains 3,144 variant-trait associations in 884 genes. We did not re-annotate or re-validate these variants; our contribution is (1) curation and expansion with post-2017 literature, adding 50 new entries and editing 876 existing records; (2) assignment of weighted scores based on study quality, replication across populations, and statistical significance; and (3) pathway-based categorization for structured browsing.

After:

> The Longevity Variants module illustrates how existing variant-trait association databases can be wrapped into the platform's no-code module format. It builds upon the LongevityMap database (Tacutu et al., 2018), which contains 3,144 variants in 884 genes (build 3, June 2017). We did not re-annotate or re-validate these variants; our contribution is (1) curation and expansion with post-2017 literature, adding 50 new entries and editing 876 existing records; (2) assignment of weighted scores based on study quality, replication across populations, and statistical significance; and (3) pathway-based categorization for structured browsing.

The source counts variants, not variant–trait associations. Its build 3 release date now identifies which count is meant. The stated curation changes were preserved.

### Section 3.2: scoring-file compatibility

Before:

> Polygenic risk scores (PRS) aggregate the effects of many common variants into a single weighted sum, providing a population-relative measure for a given trait (Lambert et al., 2021). We developed the just-prs library (github.com/dna-seq/just-prs) as the PRS computation engine for Just-DNA-Lite; it can also be used on its own (Section 3.2.1). just-prs scores the harmonized scoring files of the PGS Catalog (Lambert et al., 2021): of the 6,991 scores in its September 2026 release, 6,910 can be scored as specified, 76 only approximately and 5 not at all (Table S5).

After:

> Polygenic risk scores (PRS) aggregate the effects of many common variants into a single weighted sum, providing a population-relative measure for a given trait (Lambert et al., 2021). We developed the just-prs library (github.com/dna-seq/just-prs) as the PRS computation engine for Just-DNA-Lite; it can also be used on its own (Section 3.2.1). just-prs scores the harmonized scoring files of the PGS Catalog (Lambert et al., 2021): a file-level audit of just-prs 0.10.1 against the September 2026 release placed 6,910 of 6,991 files in Table S5's “as specified” category, 76 in “approximated” and 5 in “cannot be scored”. These categories assess scoring-file compatibility, using a 10% absolute-weight threshold for omitted or ambiguous rows. The first category can therefore include files with some omitted weight; it does not establish complete coverage in an individual genome or predictive validity.

Table S5 describes just-prs 0.10.1 and uses a tolerance threshold. Its “as specified” category can contain omitted weight; it does not establish exact implementation of every file or predictive validity.

The current published and installed just-prs version is 0.10.5, checked on 19 October 2026 against PyPI, the GitHub release tag and the installed package. The 0.10.1 label identifies the existing S5 audit, not the current release. The newer release flags models that its additive engine approximates and changes allele matching and haploid handling. Updating that audit requires checking the newer rules; the old counts have not been relabelled as 0.10.5 results. See the [0.10.5 package metadata](https://github.com/dna-seq/just-prs/blob/v0.10.5/just-prs/pyproject.toml) and [scoring implementation](https://github.com/dna-seq/just-prs/blob/v0.10.5/just-prs/src/just_prs/prs.py).

### Section 4.2: timing scope

Before:

> With the fixed input, the median share of a score's variants that were matched was 53% for just-prs (range 22 to 79%) and 51% for PLINK2 (range 22 to 78%); the counts are not the same measure (scoring rows with a called genotype at their position for just-prs, variants processed and matched by identifier for PLINK2). These values describe the benchmark configuration: reference-homozygote restoration, off here, and the LD-proxy estimation of the array workflow (Section 3.2) can raise coverage, and this comparison measures neither. The reported speedups are ratios of median runtimes over the same 100 scores; the medians of the per-score ratios agree with them to the precision shown (Table 3).

After:

> With the fixed input, the median share of a score's variants that were matched was 53% for just-prs (range 22 to 79%) and 51% for PLINK2 (range 22 to 78%); the counts are not the same measure (scoring rows with a called genotype at their position for just-prs, variants processed and matched by identifier for PLINK2). These values describe the benchmark configuration: reference-homozygote restoration, off here, and the LD-proxy estimation of the array workflow (Section 3.2) can raise coverage, and this comparison measures neither. The reported speedups are ratios of median runtimes over the same 100 scores; the medians of the per-score ratios agree with them to the precision shown (Table 3). Per-score timings exclude VCF normalization and genotype-file preparation for every engine. They measure scoring from prepared inputs; scoring-file parsing is included for just-prs, and the separately measured PLINK2 score-file preparation is shown in Table 3.

The added timing explanation comes from the recorded harness. It distinguishes scoring from one-time genotype preparation and states how score-file preparation was counted.

### Section 2.1: annotation engines

Before:

> Polars streaming joins keep peak memory low; for datasets too large to fit in memory, DuckDB handles out-of-core joins with configurable memory limits.

After:

> The module joins use Polars streaming execution. The optional Ensembl annotation uses DuckDB with configurable memory limits.

The implementation uses Polars for module joins and DuckDB for optional Ensembl annotation. The former sentence incorrectly described a general fallback between them.

### Section 2.1: inferred reference genotypes

Before: there was no description of annotation-side reference-genotype restoration.

Added:

> The current annotation engine also distinguishes called genotypes from inferred homozygous-reference genotypes. For variant-only callsets classified as whole-genome, it can restore a module's authored reference-genotype rows at sites the caller did not emit. Classification requires at least one million sites and at least 75% of the span between the first and last calls on each chromosome, summed across chromosomes, to lie within the configured flank of a call; a restored site must be within 10 kb of a called variant by default. Ambiguously placed module variants are excluded. Where the Genome in a Bottle low-mappability and segmental-duplication mask is available, sites inside it are excluded; otherwise, rows explicitly requiring callability evidence are withheld. Reports label restored rows as inferred and keep their counts separate from called matches. Nearby calls do not establish per-base callability. This annotation procedure is distinct from the optional PRS restoration described in Section 3.2.

This describes the current implementation and its inference limit. It separates annotation restoration from the optional polygenic-score procedure already described in Section 3.2.

### Supplementary S1: Generation I workflow

Before:

> **S1. Generation I: OakVar-Based Just-DNA-Seq Platform.** Architecture, pipeline, module types, and repository table for the OakVar-based Generation I system (see combined-manuscript supplement for full detail).

After:

> **S1. Generation I: OakVar-Based Just-DNA-Seq Platform.** Generation I implemented Just-DNA-Seq as annotation and report modules for OakVar (Kulaga et al., 2024). Its pipeline converted the VCF, mapped variants to genes, ran database annotators, aggregated their outputs, applied the project's trait modules as postaggregators, and rendered a report. The 2026 reconstruction used nine project postaggregators covering cancer, cardiac disease, coronary artery disease, drug response, longevity, lipid metabolism, thrombophilia, protective alleles and VO2 max; it had no counterpart of Generation II's Pathogenic module. Table S2 lists the installed versions, and Table S8 identifies the software repositories. The Generation I preprint describes the original platform in detail (https://arxiv.org/abs/2403.19087). These stages and annotation resources differ from Generation II's direct module-table joins, so the runtime comparison evaluates the configured workflows rather than equal annotation workloads.

The previous sentence pointed to material absent from this supplement. The replacement uses the recorded run stages, module inventory and Generation I preprint.

## Checks and their limits

All numerical rows of Tables 2, 3, 4, S2 and S10 were reproduced from the committed run records with the project's table-generating functions. The number checker found all 17 reported standard-error calculations consistent with their standard deviations and run counts. The S5 data contain 6,910, 76 and 5 files in the three categories, totaling 6,991. Module counts and versions were checked against the S4 snapshot.

The published just-prs 0.10.2 rerun was retrieved from its actual location, `just-prs/benchmarks/results/2026-10-11/`, and its metadata, per-score runtimes, agreement table and residual breakdown match the figures quoted in Section 4.2. The Data Availability link was repaired. The sex-chromosome benchmark's public results and metadata also resolve.

The main bibliography contains 31 entries. Twenty-six article, dataset or preprint identifiers resolve; five web or software sources were checked through their primary pages rather than assigned artificial DOIs. The 22 supplementary article DOIs resolve, as do the four software repository links. The supplement cites the main bibliography as well; its Table S7 reference list was checked separately from the later tables, which the scanner otherwise misreads as reference entries. No retraction or expression of concern was found for the 23 main and 22 supplementary article identifiers checked in the registries. Dataset records, web pages and the arXiv preprint do not have equivalent retraction checks. Shared entries occur in both lists.

Source support was examined for 6 of the 28 main-text sentences carrying author–year citations, prioritising borrowed counts and cost claims. Eight source-specific checks covered the cost comparison, lifespan heritability, LongevityMap and the 1000 Genomes panel; an independent reader checked these against primary sources, and all eight quoted passages were located mechanically. This is not an exhaustive check of every cited claim or of the thousands of papers catalogued in S4. The “full cost” wording was narrowed because the laboratory studies have defined exclusions and different currencies. “About 50%” was retained as a rounded, attributed estimate rather than treated as a universal heritability value.

The software and computational comparisons have no general clinical reporting checklist. The ancestry classifier's description was checked against the project's documented training panel and settings; the manuscript already states that it has no separate test set and has not measured accuracy in unrepresented populations. No new clinical validation or diagnostic claim was added.

Revision marks lint without errors or warnings in both sources. The original-to-final comparisons and style checks were run and reviewed. Three existing Table S7 notes were retained because their contrasts distinguish cohort-level plots from personal reports, and GWAS Catalog associations from PGS Catalog scoring files. These are technical distinctions, rather than ornamental contrasts.

The draft PDFs compile to 30 pages for the main text and 21 for the supplement in the current default layout. The abstract was visually checked and contains no newly added benchmark paragraph. Table S7 is unreadable in the supplement's default portrait PDF because its columns overlap; that PDF is a draft, and the table needs a wider layout before it is used for submission. The editable Markdown is the source of record.

## Fix now

The removed, uncited entry “Alteri, E., et al. (2024). The 23andMe data breach. European Journal of Human Genetics, 32(11), 1317–1320” could not be verified by Crossref or targeted author/title and journal searches. An unverifiable reference can cause a serious integrity query. It has been removed, and no retained claim depends on it; do not restore it without an authentic source. Five other uncited carryovers were removed. Seven retained references received identifier or title repairs, and the Broer and Tacutu citations now use their journal-issue years consistently. The manuscript's findings were not changed by these bibliographic repairs.

## Then the writing

Your preference for a qualitative abstract is applied. The abstract's “Results” text is restored to the pre-edit wording. The substantial additions and claim corrections above remain visible in the source diff; they are working revisions, not recorded human approvals.

## Once you have chosen the journal

Choose from the existing shortlist before changing the abstract format, section order or length. No new shortlist was made. BMC Bioinformatics, currently first in that working order, asks for an abstract with “Background”, “Results” and “Conclusions”; the current Motivation/Results format would need adaptation if that journal is selected ([software-article instructions](https://link.springer.com/journal/12859/submission-guidelines/software-article), read 19 October 2026). This does not itself require adding benchmark numbers.

## Before submission, once the code is final

Replace Figure 3's historical screenshot, whose caption already identifies its unsuitable absolute-risk and quality labels. Resolve the existing AI-use placeholders from the authors' actual account, confirm the author and affiliation details, archive the final software and benchmark files, and insert their final identifiers. Apply the chosen journal's declarations and layout, including the wide comparison table. Run the upload-file check on that final package; the draft check found no leaked secret or prompt directed at reviewers.
