# APOE type (ε2, ε3, ε4)

This module tells you which two versions of the APOE gene you carry, and what that pair is known to
mean. APOE makes a protein that carries cholesterol and other fats in the blood and the brain. It is
best known as the gene with the largest common effect on the risk of Alzheimer's disease that starts
late in life.

There are six possible results, one for each pair of versions: ε2/ε2, ε2/ε3, ε2/ε4, ε3/ε3, ε3/ε4 and
ε4/ε4. Each result explains how common the pair is, how it changes the risk of Alzheimer's disease
compared with the most common pair (ε3/ε3), how sure the research is, and anything practical worth
knowing. For two ε2 copies it also covers a blood-fat disorder that this pair can lead to.

A result here is a shift in likelihood, not a diagnosis or a prediction. Most people with one ε4 copy
never develop Alzheimer's disease, and many people without ε4 do.

## How this works

You inherit one copy of the APOE gene from each parent, and each copy is one of three common versions,
called ε2, ε3 and ε4. Two places in the gene tell them apart, and your result is the pair of versions
you carry, such as ε3 and ε4.

ε3 is the most common version and the usual point of comparison. ε4 is linked with a higher risk of
Alzheimer's disease that starts late in life, and ε2 with a lower one. The two do not simply cancel
out: a person with one ε2 and one ε4 still has a raised risk. These are shifts in likelihood, not
predictions: many people with ε4 never develop the disease, and many without it do.

One combination of letters, the one for ε2 with ε4, can very rarely come instead from an uncommon
version called ε1 paired with ε3. A DNA file that does not record which letters came from the same
parent cannot tell these apart, and this report reads it as ε2/ε4.

APOE testing is not a way to predict Alzheimer's disease in people without symptoms. A result here
can help you and your doctor understand your background risk, but it cannot say whether you will
develop the disease.

## For professionals

### Defining sites and alleles

Two SNPs in APOE exon 4 on GRCh38 define the three common haplotypes. Coordinates are 1-based VCF
positions.

| Haplotype | rs429358 (19:44908684, ref T) | rs7412 (19:44908822, ref C) | Protein (residues 112, 158) |
|---|---|---|---|
| ε2 | T | **T** | Cys112, Cys158 |
| ε3 | T | C | Cys112, Arg158 |
| ε4 | **C** | C | Arg112, Arg158 |

ε3 carries the reference allele at both sites, so it is written out in `haplotypes.csv` rather than
left implicit. `diplotypes.csv` lists all six unordered pairs, each with its label and conclusion.
The module authors no weights: a combined result is not a sum of per-variant scores.

Phase matters and the module cannot supply it. A sample heterozygous at both sites (rs429358 T/C,
rs7412 C/T) is either ε2/ε4 or the rare ε1/ε3; ε1 is not modelled here, so the caller reports ε2/ε4.
The module states what each pair means; which pair a sample carries is the caller's job.

### Sources

Every number in the conclusions comes from one of these papers. `studies.csv` carries the population,
design and a short summary of each, plus a verbatim passage where the licence allows one.

| PMID | Paper | Used for |
|---|---|---|
| 32818802 | Lumsden AL et al. Apolipoprotein E (APOE) genotype-associated disease risks: a phenome-wide, registry-based, case-control study utilising the UK Biobank. EBioMedicine 2020. | Genotype frequencies in 337,484 white British participants: ε3/ε3 58.2%, ε3/ε4 23.9%, ε2/ε3 12.3%, ε2/ε4 2.6%, ε4/ε4 2.4%, ε2/ε2 0.6%. |
| 21556001 | Genin E et al. APOE and Alzheimer disease: a major gene with semi-dominant inheritance. Mol Psychiatry 2011. | Modelled lifetime risk of AD by age 85 in Caucasians (case-control ORs applied to Rochester incidence and US life tables; conditional on surviving to 85), men / women: ε3/ε3 8% / 10%, ε2/ε4 20% / 27%, ε3/ε4 23% / 30%, ε4/ε4 51% (95% CI 41–70) / 60% (95% CI 47–84), ε2 without ε4 5% / 6%. With PAQUID (France) incidence, ε4/ε4 women reach 68%. ε4 probably the ancestral allele. |
| 37930705 | Belloy ME et al. APOE Genotype and Alzheimer Disease Risk Across Age, Sex, and Population Ancestry. JAMA Neurol 2023. | ORs against ε3/ε3 by ancestry. White: ε2/ε2 0.39, ε2/ε3 0.53, ε2/ε4 2.23, ε3/ε4 3.46, ε4/ε4 13.04. ε3/ε4 4.54 East Asian, 2.18 Black, 1.90 Hispanic; ε2 not associated in Hispanic or East Asian individuals. |
| 9343467 | Farrer LA et al. Effects of age, sex, and ethnicity on the association between apolipoprotein E genotype and Alzheimer disease. A meta-analysis. JAMA 1997. | The classic meta-analysis: Caucasian ORs 0.6 (ε2/ε2, not significant; ε2/ε3), 2.6 (ε2/ε4), 3.2 (ε3/ε4), 14.9 (ε4/ε4); weaker ε4 effect in African American and Hispanic, stronger in Japanese subjects. |
| 8346443 | Corder EH et al. Gene dose of apolipoprotein E type 4 allele and the risk of Alzheimer's disease in late onset families. Science 1993. | ε4 gene dose; mean age at onset falling from 84 to 68 years with the number of ε4 copies. |
| 7920638 | Corder EH et al. Protective effect of apolipoprotein E type 2 allele for late onset Alzheimer disease. Nat Genet 1994. | Original report of ε2 protection. |
| 32015339 | Reiman EM et al. Exceptionally low likelihood of Alzheimer's dementia in APOE2 homozygotes from a 5,000-person neuropathological study. Nat Commun 2020. | ε2/ε2 OR 0.13 against ε3/ε3 in autopsy-confirmed cases, 0.52 in clinically diagnosed ones. |
| 38710950 | Fortea J et al. APOE4 homozygozity represents a distinct genetic form of Alzheimer's disease. Nat Med 2024. | Near-full penetrance of AD biology in ε4/ε4 (almost all show AD pathology; by 65 nearly all have abnormal CSF amyloid and 75% positive amyloid PET); earlier symptom onset, mean age 65.1. |
| 35781703 | Heidemann BE et al. Establishing the relationship between familial dysbetalipoproteinemia and genetic variants in the APOE gene. Clin Genet 2022. | 10-15% of ε2/ε2 carriers develop dysbetalipoproteinaemia, usually with obesity, insulin resistance or diabetes; high cardiovascular risk; treatment. |
| 38625929 | Paquette M et al. Prevalence of Dysbetalipoproteinemia in the UK Biobank According to Different Diagnostic Criteria. J Clin Endocrinol Metab 2025. | 0.6% of UK Biobank participants were ε2/ε2, and 36% of them met a broad definition of dysbetalipoproteinaemia (prevalence 1 in 469). |
| 37357276 | Cummings J et al. Lecanemab: Appropriate Use Recommendations. J Prev Alzheimers Dis 2023. | ε4 carriers, especially homozygotes, have a higher risk of ARIA on anti-amyloid antibodies; APOE genotyping of treatment candidates is recommended. |

Where sources differ, the conclusions follow the larger and newer analysis and say how the effect
changes with ancestry. The frequencies are from a UK white British cohort and differ in other
populations. The lifetime risks are modelled Caucasian estimates, not counts of people followed to 85:
they combine case-control odds ratios with population incidence and life tables and are conditional on
living to 85, which is how the conclusions word them. Odds ratios are kept out of the conclusions and
appear only here and in `studies.csv`.

### What this module cannot tell you

- **Rarer APOE alleles.** Only ε2, ε3 and ε4 are modelled. ε1, APOE3-Leiden, APOE Christchurch and
  other rare variants, some of which cause dominant dysbetalipoproteinaemia, are not detected, and a
  sample carrying one is reported as the nearest common pair.
- **A diagnosis.** APOE is a risk modifier with incomplete, age-dependent penetrance. No result here
  says whether a person has or will develop Alzheimer's disease or dysbetalipoproteinaemia; a doctor
  settles that with clinical assessment and blood tests.
- **Prediction in people without symptoms.** APOE testing is not a way to predict Alzheimer's disease
  in people without symptoms. Even for ε4/ε4, whose carriers nearly all show the disease's biology in
  biomarker studies, the modelled lifetime risk by 85 is about 50–70%, and most ε3/ε4 carriers never
  develop the disease.
- **Positions the sequencing missed.** Both defining sites sit in a GC-rich stretch of exon 4 that
  short-read sequencing sometimes covers poorly. When a site is absent from the file and the result is
  read as reference there, that result is less certain than one read from two called positions; the
  report says so on the result itself.
- **Ancestries beyond those studied.** Effect sizes were measured mainly in people of European
  ancestry, with smaller samples of Black, Hispanic and East Asian people. For other ancestries the
  direction is likely the same and the size is not known.
- **Other APOE effects.** ε4 is also linked with higher cholesterol and heart disease, and ε2/ε2
  with some vascular conditions. The conclusions mention these only where they matter for the reader.

### How it was made

The haplotype and diplotype rows, labels and calling rules come from the just-dna-format reference
example (MIT). Version 1.1.0 rewrote every conclusion in the report voice described in
just-dna-lite's `docs/REPORT_VOICE.md` and grounded each claim in the papers above. Every PMID was
taken from a literature search in the curating session and its title checked against PubMed.

Verbatim passages in `studies.csv` were located by an AI agent (Claude, via just-module-creator) in
the text returned by `fetch_fulltext`, so the literature pass's `quotes_found` on those rows is a
citation-pairing check rather than independent evidence. For PMID 21556001 the passage was read in the PMC author manuscript; the literature pass can only reach that paper's abstract, so it reports the quote as unchecked rather than found. Five passages come from abstracts, because
those articles are not open access. Two articles (32818802 and 35781703) are CC BY-NC-ND, so their
facts are cited but no text from them is carried; see `licensing.csv`.

Review record, 2026-09-27: two independent AI reviewers (Claude agents), a lay reader and a
scientific reviewer, read the rendered report and every result text. Changed as a result: the
lifetime risks are worded as modelled estimates for people who live to 85; ε4/ε4 gives the range of
estimates (about half to two in three) and the near-universal Alzheimer's biology from Fortea 2024
instead of "4 in 10 had not developed it"; ε2/ε4 compares with ε3/ε4 correctly, drops the
contradictory "likely rather than certain", and ends with the ε1/ε3 caveat; ε3/ε3 says it is the
baseline most people share; each conclusion explains ε and the APOE2/3/4 names; the antibody
medicines are glossed; the ε2/ε2 blood-fat disorder is named plainly first; the risk results say
APOE is not used to predict the disease in people without symptoms; "How this works" no longer
claims the report lists two pairs; the limits cover prediction in people without symptoms and poorly covered positions.
This is an AI review, not a human one.

## About this copy

This directory is both a vendored test fixture in just-dna-lite and the spec of the published module
`antonkulaga/apoe_epsilon`. Version 1.1.0 (2026-09-27) keeps the rows and rules of the just-dna-format
reference example unchanged: the same haplotypes, the same six pairs and the same labels. Its
conclusions were rewritten and sourced, and it adds `studies.csv`, `licensing.csv`, authorship and a
declared MIT licence. Version 1.0.0 is the one published on 2026-09-27.
