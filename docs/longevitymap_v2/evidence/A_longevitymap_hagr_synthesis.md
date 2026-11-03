# Track A: LongevityMap, the HAGR ecosystem, and an audit of longevitymap v1.2.0

All PMIDs are title-verified against PubMed. Counts are computed from the v1 CSVs, the LongevityMap Build 3 download and GWAS Catalog v2. Companion files: evidence table (53 papers), candidate variants (47 rows, 40 rsIDs), audit_numbers.json.

## 1. The original LongevityMap

- **Paper.** Budovsky A et al., *Trends Genet* 2013;29:559–560, PMID 23998809, doi:10.1016/j.tig.2013.08.003. I could not get the full text: it is Elsevier hybrid, with no OA copy and no PMCID. The abstract describes it as "the first database of genes, loci, and variants studied in the context of human longevity and healthy ageing". **The counts at publication are unverified.**
- **Inclusion criteria.** These come from the HAGR help page and the HAGR NAR papers of 2018 and 2024. Entries were curated by hand from the literature, and studies in cohorts that were unhealthy at baseline were excluded. Large and small studies were both admitted, including cross-sectional and extreme-longevity designs. Negative results were included on purpose.
- **How significance was assigned.** Each entry is one observation from one study. It is flagged "significant" or "non-significant" according to whether that study reported statistical significance. None of the sources I could read documents a uniform threshold such as p<5e-8 or a multiple-testing rule. On controversial findings, the stated policy is to report the facts and let users decide.
- **Data model.** The downloadable `longevity.csv` from Build 3 has six fields: id, Association, Population, Variant(s), Gene(s), PubMed. It has **no allele, effect direction, effect size, p-value or sample size**. The website shows study design and sample size as free text.
- **Limitations stated.** The database is inclusive rather than filtered, and sample sizes and designs vary widely. The full Budovsky text was not accessible, so the paper's own limitations section was not read.

## 2. Maintenance status (HAGR)

- Tacutu et al., NAR 2013 (PMID 23193293), predates LongevityMap and does not mention it.
- Tacutu et al., NAR 2018 (PMID 29121237), reports **Build 3 (24/06/2017): 550 entries, 884 genes, 3,144 variants, 275 significant**.
- de Magalhães et al., NAR 2024 (PMID 37933854), repeats the **same figures**: 3,144 variants, 884 genes, 270 studies, 275 significant.
- The live site (checked 2026-11-03) still shows "Build 3 (24/06/2017)" with 550 entries. The download zip is internally dated 2017-06-24.
- **Conclusion: LongevityMap has not been updated since June 2017.** The Build 3 release notes say it added no new entries, only re-annotation.
- **Licence.** The HAGR legal page says HAGR is under CC BY 3.0 Unported and free for any use, including commercial, provided HAGR is cited.

## 3. Audit of v1.2.0 (528 rsIDs, 1,022 genotype rows, 671 study rows, 126 PMIDs)

**How v1 relates to the Build 3 download.** Build 3 contains 2,860 distinct rsIDs, and v1 includes 512 of them. Of the 2,348 Build 3 rsIDs missing from v1, 2,339 carry only non-significant entries, so v1 is effectively the significant subset of LongevityMap. In Build 3, 337 of the 550 entries have no rsID at all (APOE E2/E3/E4, I/D polymorphisms, HLA alleles, haplogroups).

**Top problems**

| # | Problem | Evidence (computed) |
|---|---|---|
| 1 | Evidence rests mostly on one paper | 280/671 study rows (42%) cite Sebastiani 2012 (PMID 22279548). For 277/528 rsIDs (52%), covering 548/1,022 genotype rows, it is the only support. All 280 rows are flagged "significant", yet the paper reports a 281-SNP classifier in which only rs2075650 reached genome-wide significance. |
| 2 | Little replication | Only 35 rsIDs (6.6%) have ≥2 independent significant PMIDs, and 12 have ≥3. 50 rsIDs have both significant and non-significant rows. |
| 3 | No quantitative fields | 0/671 study rows have a p-value, effect size or effect allele. 0/1,022 variant rows have chromosome or position. The genotype-level `state` cannot be traced back to LongevityMap, because its download has no allele column. |
| 4 | Weights are undocumented and hardly track evidence | Weight values cluster at 0.07 (259 rows) and 0.14 (253 rows). The homozygote weight is exactly twice the heterozygote weight for 478 of 482 rsIDs. Spearman correlation between \|weight\| and the number of significant studies is 0.16. rsIDs with no significant study have a higher mean \|weight\| (0.38) than rsIDs with one (0.20). |
| 5 | Stale | Cited PMIDs span 1993–2015 (median 2009), and only 10 PMIDs are later than 2013. The source has been frozen since 2017. |
| 6 | Modern loci missing | GWAS Catalog lists 121 rsIDs at p≤5e-8 for life-span determination, parental longevity, healthspan and age at death. Only 6 are in v1, all from the APOE/TOMM40/APOC1 cluster plus rs2149954. Of the 40 rsIDs in the candidate list, 36 are new. |
| 7 | Conclusion text is study-level and reused | There are 79 unique conclusions across 1,022 rows. One text is shared by 548 rows covering 277 rsIDs. 961 rows carry text that is shared across rsIDs. |
| 8 | Design mix is mostly candidate-gene | 336 rows are GWAS-derived, but 280 of those are from Sebastiani 2012. The rest are 220 candidate case-control rows, 101 longitudinal rows and 14 family rows. |
| 9 | Ancestry is not harmonised | 50 free-text population labels. "American (Caucasian)" accounts for 315/671 rows (47%). |
| 10 | Directional skew | 975 rows are "protective" and 47 are "risk". Only the reported longevity genotype is listed, so non-carriers are uninterpretable. |
| 11 | Other gaps | 254 rows (130 rsIDs) have no gene. 12 rsIDs have no studies row. Categories are dominated by "other" (483 rows). No cited PMID is flagged as retracted in PubMed. |

## 4. Resources that could complement or replace LongevityMap

- **GWAS Catalog v2.** Longevity is indexed as OBA_VT0005372 (EFO_0004300 returned 404). Six traits gave 708 associations, 180 at p≤5e-8. Key studies: Deelen 2019 (31413261; 11,262/3,484 cases ≥90th/99th percentile vs 25,483), Timmers 2019 (30642433; ~1M parental lifespans), Joshi 2017 (29030599), Pilling 2017 (29227965), Zenin 2019 healthspan (30729179), Timmers 2020 (32678081). Non-European: Zeng 2016 (26912274), Liu 2021 (33657282), Akiyama 2023 (36737517), Hsieh 2026 (41949656). The one study record checked (42176242) is CC0; others not checked.
- **PGS Catalog.** Only PGS000906 (Tesi 2021, 330 variants), PGS002795 (4 variants), PGS001393 (father's age at death) and PGS000318/319 (mortality). Thin coverage; licence is per score.
- **Sequencing studies.** Garagnani 2021 (33941312), Lin 2021 (37117627), Ying 2024 (39424787; RGP1, PCNX2, ANO9), Park 2025 (40021682; LoF in TET2, ATM, BRCA1/2, mostly cancer/CHIP), Gurinovich 2025 (39751714; SLC9A2 rs6543176).
- **Open Genes** (37665017; 2,402 genes, allelic associations, API) and **HALL** (37870433; 1,913 SNPs). Both articles are CC BY 4.0; **database licences unverified** (sites blocked).
- **"LongevityDB", "CentenarianDB"**: 0 Europe PMC hits; not published resources.

## 5. Implications for longevitymap v2 requirements

1. **Rebuild the scored core from genome-wide evidence** and use tiers:
   - **T1:** p≤5e-8 in a large GWAS with a published longevity, lifespan or healthspan phenotype, replicated independently or in a multivariate analysis. Examples: APOE rs429358/rs7412, LPA rs10455872, CDKN2B-AS1, HYKK/CHRNA3-5 rs8042849, FOXO3 rs1159806, HLA-DQA1/DRB1, LDLR.
   - **T2:** genome-wide significant in a single study, or ancestry-specific (e.g. IL6 rs2069837 and BMPER rs17169634 in Chinese cohorts).
   - **T3:** candidate-gene variants with ≥2 independent significant studies (35 rsIDs in v1).
   - **T4:** everything else, kept as informational with weight 0.
2. **Set weight to 0 or drop the 277 rsIDs supported only by Sebastiani 2012**, and any row whose only support is a single candidate-gene study.
3. **Make the quantitative fields mandatory for any row that carries weight:** effect_allele, other_allele, effect_measure (OR, HR, or beta in years per allele), effect_size, p_value, n, ancestry and phenotype_definition (90th or 99th percentile, parental lifespan, healthspan, multivariate). Rows without them cannot be scored.
4. **Put published estimates in `gwas_effects`**, recording the GWAS Catalog association_id or paper table as provenance. Weight should be a documented function of the estimate, for example log(OR) scaled and additive (hom = 2×het), rather than a hand-set value.
5. **Add a `haplotypes` table for APOE ε2/ε3/ε4** (rs429358 + rs7412). Collapse proxy SNPs (rs2075650, rs4420638, rs769449) into a single signal per locus to avoid double counting. Apply LD clumping across all loci.
6. **Add a `pgs` pointer table** for PGS000906, with the caveat that it was developed in Dutch centenarians. Do not present mortality PRS (PGS000318/319) as longevity scores.
7. **State pleiotropy in the conclusions.** Most longevity loci are disease loci: APOE for Alzheimer's and CVD; LPA, LDLR and CDKN2B-AS1 for CAD; CHRNA3/5 for smoking. Cross-reference the cardio and Alzheimer's modules so findings are not reported twice.
8. **Rare and LoF variants** (TET2, ATM, BRCA1/2) belong in cancer or CHIP modules. Mention them as cross-references only.
9. **Harmonise ancestry** to GWAS Catalog categories, mark non-European signals as ancestry-specific, and never transfer their effect sizes to other ancestries.
10. **Emit all genotypes per scored locus**, including reference homozygotes as neutral, and write conclusions at variant level rather than reusing study text.
11. **Fill GRCh38 coordinates and ref/alt** for every rsID. v1 has none.
12. **Keep LongevityMap only as a provenance and negative-evidence table**, with CC BY 3.0 attribution, and label it "frozen 2017". Do not re-port it wholesale.
13. **Before redistributing any Open Genes or HALL content, verify their data licences.** Re-check GWAS Catalog terms for each study.
