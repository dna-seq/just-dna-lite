# Track F — Presenting longevity genetics to three audiences (longevitymap v2)

Evidence: `trackF_evidence_table.csv` (68 records; PMIDs title-verified in PubMed, DOIs title-matched in Crossref). Example variants: `trackF_candidate_variants.csv`.

## 1. Organising frameworks usable as report sections

- **Hallmarks of Aging (López-Otín 2023, PMID 36599349)** list 12 hallmarks: genomic instability, telomere attrition, epigenetic alterations, loss of proteostasis, disabled macroautophagy, deregulated nutrient-sensing, mitochondrial dysfunction, cellular senescence, stem-cell exhaustion, altered intercellular communication, chronic inflammation, dysbiosis.
- **Geroscience seven pillars (Kennedy 2014, PMID 25417146):** adaptation to stress, epigenetics, inflammation, macromolecular damage, metabolism, proteostasis, stem cells/regeneration. These are intertwined, not independent.
- **Gene-level annotation.** Open Genes (PMID 37665017) covers 2402 genes with hallmark-of-aging annotations and a confidence level per gene. HAGR 2024 (PMID 37933854) lists 307 human GenAge genes; the current LongevityMap holds 3144 variants in 884 genes, against 528 rsIDs / 272 genes in the v1 port. In Gene Ontology (QuickGO), **GO:0007568 "aging" is obsolete**: ageing is "not a normal, genetically encoded biological program". The live terms are GO:0008340 (determination of adult lifespan) and GO:0090398 (cellular senescence), so GO alone cannot carry a hallmark mapping.
- **Disease-mediated vs direct effects.** Most lifespan signal runs through disease. In Timmers 2019 (PMID 30642433), dementia, cardiovascular and lung-cancer variants explain the most variance. Most of the 10 multivariate loci in Timmers 2020 (PMID 32678081) are cardiovascular. In Deelen 2019 (PMID 31413261), only APOE ε4/ε2 held up in parental-age validation. Organ system/disease mediation is the more honest primary axis; hallmarks are research context.

## 2. Reporting standards and evidence grading

- **PRS-RS (Wand 2021, PMID 33692554):** 22 reporting items, including the ancestry of development/validation samples and the ancestry-inference method. The **PGS Catalog** (PMIDs 33692568, 38853961 [preprint]) distributes scores with alleles and weights; `pgsc_calc` estimates ancestry and normalises scores against reference data.
- **ClinGen risk-allele framework (Schmidt 2024, PMID 38054408):** **Established / Likely / Uncertain risk allele**, plus protective-allele equivalents. Reports state classification, zygosity, effect size and, when accurate, absolute risk.
- **ClinGen gene–disease validity (PMID 28552198):** Definitive through Conflicting. Suitable for gene-level labels, not SNPs.
- **Venice criteria (PMID 17898028):** amount of evidence, replication and protection from bias, three levels each, giving strong / moderate / weak credibility.
- **LongevityMap's binary flag in v1:** 571 study rows significant, 100 not. v1 has **no effect sizes, effect alleles or p-values**, and 975 of 1022 genotype rows are "protective". The Sebastiani 2012 281-SNP model (PMID 22279548) supplies **280 of 671 (41.7%) study rows**, all flagged "significant". That model reached 60% sensitivity / 58% specificity in an independent set, and 23andMe's research blog reported it appeared overfit. Its Science 2010 predecessor is retracted (PMID 20595579; not cited in v1).
- **Professional statements.** ESHG 2010 (PMID 20736974) makes clinical utility essential and requires counselling and transparent claims; ESHG 2022 (PMID 34916614) rejects embryo PRS. The ICDA Task Force (PMID 34782789) and a counselling practice resource (PMID 36617640) say PGS clinical utility is not yet demonstrated. **ACMG 2023 (PMID 36920474) and 2024 (PMID 38393332): titles verified only; content not accessible and not summarised.**
- **Ancestry.** PRS are several-fold more accurate in European ancestry (PMID 30926966). Accuracy also falls continuously with genetic distance from the training data: 14% lower in the furthest decile even within Europeans (PMID 37198491). eMERGE calibrates PRS by genetic ancestry (PMID 38374346).
- **Absolute vs relative risk.** Absolute frequencies, pictographs and plain language are preferred over relative risk (PMID 21931068). A 2025 review of 13 PGS-report studies supports absolute risk and non-stigmatising colours (PMID 40196936). In a CAD report, percentiles plus word labels were understood best and odds ratios were dropped (PMID 34598685). In 2025–2026 tests, pictographs beat bell curves, which were often misread (PMIDs 39885483, 42661205). eMERGE IV providers named interpreting relative risk as a concern (PMID 41353565).

## 3. How people interpret results; risks

- **Misreading:** the public rated sample DTC results easy to understand yet often misread them (PMID 21720148).
- **Determinism:** genetic attributions feel immutable even when the genetic explanation is weak (PMID 21142350). Sham "high-risk" vs "protected" feedback changed physiology regardless of genotype (PMID 30932047).
- **Behaviour:** 18 trials showed no behaviour change and no detected psychological harm from DNA-based risk feedback (PMID 26979548).
- **False reassurance:** in REVEAL, APOE ε4-negative participants had lower test-related distress than ε4-positive ones (PMID 19605829).
- **Rare-variant calls from raw data are unreliable:** 40% of DTC raw-data variants sent for confirmation were false positives (PMID 29565420); only 16% of chip calls below 0.001% frequency were confirmed (PMID 33589468). Among raw-data downloaders, 63% used Promethease (PMID 31204012).
- **Heritability:** estimates run from <10% (pedigrees, assortative mating corrected; PMID 30401766) to >50% (intrinsic mortality, 2026 twin analysis; PMID 41610249). A heritability sentence must name its estimand.
- **Population specificity:** a 2026 Calabrian GWAS found no APOE or FOXO3 association (PMID 42176242).

## 4. How existing products present longevity genetics (product and press pages)

- **23andMe:** no dedicated longevity report found. It offers an APOE ε4 late-onset Alzheimer's report and notes that ethnicity may affect relevance. Its 2010 research blog judged the Sebastiani longevity model not predictive in its cohort.
- **Genomelink:** a "Longevity" trait based on "common genetic markers found for elderly humans of over 80 years old", returned as a tendency label.
- **SelfDecode:** a Longevity report stated to analyse 7,283,077 variants with up to 114 recommendations. Marketing pages say "six genes" (APOE, FOXO3, SOD2, SIRT1, MTHFR, TNF) control ageing speed. **This is the determinism pattern to avoid.**
- **Nebula/DNA Complete:** advertises "38+ Longevity Reports". A third-party review describes a free report based on one FOXO3 SNP (rs2764264).
- **Promethease:** matches raw data against SNPedia. Each finding carries a subjective community "magnitude" (0–10) and a "repute" (good/bad/not set); there is no combined risk.

## Implications for longevitymap v2 requirements

1. **Section hierarchy.** Use this order:
   1. Summary card: what the module can and cannot say.
   2. Data quality and ancestry match.
   3. Established longevity loci: the APOE ε2/ε3/ε4 diplotype via the `haplotypes` table.
   4. Genome-wide lifespan/healthspan loci, grouped by mediating organ system or disease (cardiovascular, neurocognitive, metabolic, smoking/lung).
   5. Optional PGS Catalog score (`pgs` table) with ancestry-calibrated percentile.
   6. Candidate-gene associations grouped by hallmark (12-hallmark mapping via Open Genes/GenAge), collapsed by default.
   7. Methods, sources and limitations.
2. **Evidence tiers.** Map to ClinGen terms and Venice dimensions:
   - **T1 "Established":** p ≤ 5×10⁻⁸ in a longevity/lifespan GWAS and replicated in an independent cohort or parental-lifespan data (e.g. rs429358-C, OR 0.60; rs7412-T, OR 1.28; Deelen 2019).
   - **T2 "Likely":** genome-wide significant in one large or multivariate GWAS without independent replication, or a meta-analysed candidate with consistent direction.
   - **T3 "Uncertain / exploratory":** single candidate-gene or nominal association, which covers most of v1.
   - **T4 "Not supported":** non-significant, failed replication (e.g. rs7676745), or a retracted source. T4 is shown only to researchers, as negative evidence.
3. **Store the tier and its criteria as columns** (n, replication, p, design, ancestry). Avoid falsely precise numeric weights. Fill `effect_allele`, `effect_size`, `effect_measure` and `p_value` from source tables (empty in v1).
4. **Treat the Sebastiani 2012 model SNPs as one model,** not 280 independent "significant" claims. Default them to T3 at most, or drop them.
5. **Fields per audience.**
   - Citizen: gene, plain label, genotype, tier badge, association-phrased direction, mediating condition, ancestry flag, "what this does not mean".
   - Geneticist: + rsID, GRCh38 position, ref/alt, effect allele, zygosity, effect size with 95% CI, p, phenotype definition, cohort ancestry/n, callability, ClinGen-style class.
   - Researcher: + hallmark/pathway, LongevityMap/GWAS/PGS IDs, significant vs non-significant study counts, I², pleiotropy.
6. **APOE.** Make the APOE section opt-in or interstitial, because ε4 implies Alzheimer's risk. Present ε2/ε4 as disease-mediated.
7. **Ancestry disclosure.** Compute the user's genetic-ancestry distance from each study population. Show "Studied mainly in people of European ancestry; accuracy for you may be lower" whenever there is a mismatch, and suppress PGS percentiles when the user is out of the reference distribution.
8. **Recommended sentences:**
   - "Most of how long people live is not explained by known genetic variants; lifestyle, environment and chance matter more for any one person."
   - "This variant was more common among people who reached very old age; it does not predict your lifespan."
   - "Effects reported here are averages across large groups and are small for any individual."
   - "Estimates of lifespan heritability range from under 10% to over 50% depending on method."
   - "Not carrying a risk variant does not mean low risk."
   - "This is research information, not a medical test; confirm any medically important finding in a clinical laboratory."
9. **Do not show:**
   - a summed candidate-gene "longevity score" or weight total;
   - predicted age at death or genotype-based "biological age";
   - odds ratios to citizens without absolute context;
   - bell-curve-only visuals or red/green "good/bad" colouring;
   - "gene controls ageing" claims;
   - rare/pathogenic array calls without a confirmation warning;
   - T4 rows in the citizen view.
10. **Use pictographs and word labels** for absolute risk. Show a PGS percentile only with PRS-RS metadata (score ID, development ancestry, validation performance).
11. **Re-sync to current LongevityMap** (3144 variants / 884 genes) before tiering; record its release date.
