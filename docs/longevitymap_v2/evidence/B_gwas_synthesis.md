# Track B — Common-variant genetics of longevity and lifespan (GWAS, 2014–2026)

Scope: 59 sources (55 PubMed-verified PMIDs, 4 Crossref-verified preprints), plus the GWAS Catalog v2 and the PGS Catalog. Alleles come from paper tables, abstracts or the GWAS Catalog; the `source_of_allele` column in the candidate file records which.

## 1. Phenotypes are not interchangeable
- **Extreme longevity**: ≥90th/≥99th-percentile survivors against controls ≤60th percentile (Deelen 2019: 11,262/3,484 cases, 25,483 controls), or centenarians against middle-aged controls. Samples are small and definitions vary.
- **Parental lifespan**: offspring genotype regressed on parents' survival (Joshi, Pilling, Timmers 2019 with 1,012,240 lives, Wright 2019). Power is high. Deaths happen mostly before 85, so smoking and CVD loci dominate.
- **Healthspan**: first of seven diseases or death (Zenin 2019). Because cancer counts as an event, pigmentation and skin-cancer loci (IRF4, TYR, DEF8) and TCF7L2 appear.
- **Multivariate composites**: Timmers 2020, Timmers 2022, Rosoff 2023. These add power but not independent replication, because their inputs overlap and UK Biobank is in nearly all of them.

## 2. Robust loci (tier 1: genome-wide in more than one analysis, with independent-sample support)
| Locus | Lead (pro-longevity allele) | Effect | Independent support | Main mediating disease |
|---|---|---|---|---|
| APOE | rs429358-T (non-ε4); rs7412-T (ε2) | +1.06 y/allele parental (Timmers 2019); ε4 OR 0.60 for ≥90th pct, 0.52 for ≥99th (Deelen 2019); ε2 OR 1.28/1.47 | every design and ancestry | AD + CVD; largest lifespan variance explained (0.23 y²). ε4 effect rises about 32% per decade of parental age |
| CHRNA3/5 (15q25) | rs8042849-T | +0.44 y | GERA viability (Mostafavi 2017); CHARGE >90 proxy P = 0.95 (not replicated) | smoking → lung cancer/COPD; mainly paternal |
| LPA | rs10455872-A / rs55730499-C | +0.76 y | CHARGE proxy P = 0.002; healthspan; MR (Timmers 2022) | Lp(a) → CAD |
| CDKN2B-AS1 (9p21) | rs1556516-G; rs7859727-C | +0.25 y | ≥99th pct OR 1.20 (rs7039467-A); Bae 2022; Torres 2021 (French replication) | CAD (cancer-protective alleles shorten life) |
| HLA-DQA1/DRB1 | rs34831921-A / rs34967069-T | +0.56–0.6 y | CHARGE proxy P = 0.003 | autoimmune |
| ATXN2/SH2B3/BRAP (12q24) | rs11065979-C; rs3184504-C | +0.28 y; CC vs TT OR 1.18 for parental extreme longevity | Fortney 2015 replication | BP/CVD (+ more cancer) |
| FOXO3 | rs1159806-T (multivariate GW); legacy rs2802292 | small (β_lifespan 0.015) | Broer 2015 meta (OR 1.17, P = 1.85×10⁻¹⁰); Deelen 2019 look-up | unclear; less metabolic syndrome |
| 5q33.3/EBF1 | rs2149954-T | OR 1.10 for ≥90 | prospective HR 0.95; Zeng 2016; Timmers 2019 | BP / CV mortality |
| LDLR, FURIN/FES, ZW10 | rs142158911-A, rs6224-G, rs61905747-A | +0.25–0.36 y | LifeGen validation (Timmers 2019); nominal in longevity data (Timmers 2020; Deelen 2019) | LDL/BP/CVD |

**Tier 2** (GW in UKB-dominated or prior-informed analyses, partial replication): CELSR2/PSRC1, HTT (supported in Finnish/Japanese survival), KCNK3, MAGI3, HP, PSORS1C3, 13q21.31, ABO, IGF2R, ZC3HC1, TMEM18, GBX2, POM121C, TCF7L2 and IRF4 (healthspan), TOX3, SLC22A3, and IL6 rs2069837 (Han Chinese; the trans-ethnic replication reuses CLHLS).
**Tier 3** (GW in one study; 73 rsIDs): GPR78 (failed in UKB), the Pilling 2017 sex-specific and rare hits, SLC4A7/LINC02513/FGD6, the Wright and Rosoff novel loci, ANKRD20A9P, BMPER, TMEM43, BET1L, CLEC3B rs13963, LRP1B, ZSCAN23, and Calabrian rs11186068.
**Tier 4** (suggestive or failed): KALRN, RP1, RDH5, KIF13B, CADM2, GRIK2, RAD50/IL13, FN3KRP, rs145265196, rs35715456, and the CLHLS sex-specific loci.

## 3. How much is disease-mediated
None of the papers reports a per-locus "% mediated". What they report:
- Timmers 2019 partitions lifespan variance explained (LVE). Across the top 20/45 disease SNPs, CVD accounts for 0.33/0.43 y², smoking and lung cancer for 0.13/0.15 y², and other cancers for 0.03/0.11 y². Together these loci explain 0.95 y², under 1% of lifespan variance. Table 1 labels each locus by disease category: CHRNA3/5 smoking; LPA, LDLR, CDKN2B-AS1 and FURIN cardiometabolic; HLA and MAGI3 autoimmune; HTT none.
- Antagonistic pleiotropy: at ATXN2/BRAP and CDKN2B-AS1 the cancer-protective allele shortens life. The SH2B3 longevity allele raises cancer risk. A higher lifespan PRS goes with more AD, Parkinson's and prostate and breast cancer.
- Age dependence: the non-APOE protective effects shrink by about 24% per decade of parental age, while APOE ε4 grows by about 32% (Timmers 2020).
- Joshi 2017 (MR): +1 BMI unit costs about 7 months; +1 year of education adds about 11 months, mostly through smoking.

## 4. Ancestry and recent work (2022–2026)
- No large multi-ancestry lifespan GWAS was found from FinnGen, MVP, All of Us or China Kadoorie, and no lifespan GWAS reported X-chromosome loci.
- East Asian evidence comes from CLHLS (Zeng 2016/2018/2024), Liu 2021, BBJ survival (Akiyama 2023, BET1L), Taiwan (Hsieh 2026, where a PRS raised AUC from 0.913 to 0.956 at ≥95 y) and Singapore (Chang 2022). Lead variants differ from the European ones; APOE is the only clear shared locus.
- 2025–2026 work turned to rare-variant burden (TET2, ATM, BRCA1/2: CHIP and cancer), small founder populations (Calabria) and PRS validation.

## 5. GWAS Catalog (v2 API, pulled 2026-11-03)
| EFO trait | associations | p < 5×10⁻⁸ | GCST studies | publications |
|---|---|---|---|---|
| parental longevity (EFO_0007796) | 442 | 125 | 18 | 7 |
| life span determination trait (OBA_VT0005372; covers "longevity") | 275 | 68 | 28 | 20 |
| healthspan (EFO_0009762) | 37 | 26 | 4 | 3 |
| age at death (EFO_0005056) | 2 | 0 | 1 | 1 |
| father's / mother's age at death | 0 | 0 | 0 | 0 |
| aging (EFO_0022597; mostly epigenetic clocks, out of scope) | 394 | 268 | 44 | 22 |

Across the in-scope traits plus per-PMID pulls there are 196 genome-wide-significant association rows, covering 150 unique rsIDs from 21 publications. **Only 7 of these rsIDs are in longevitymap v1**: rs429358, rs7412, rs769449, rs405509, rs2075650, rs4420638 and rs2149954. In the candidate CSV (156 rsIDs) the 7 in-v1 rsIDs are the same, except that rs1063192 (CDKN2B-AS1, Torres 2021) takes the place of rs4420638. The v1 gene list contains APOE, FOXO3, CDKN2B-AS1, IL6, TOMM40 and APOC1. It has none of LPA, CHRNA3/5, SH2B3/ATXN2, HLA-DQA1, LDLR, FURIN, ZW10, ABO or the 5q33.3 gene label. The v2 associations endpoint left most effect sizes blank (`beta` = "-"), so effect sizes were taken from the papers.

## 6. Lifespan polygenic scores
- PGS Catalog lifespan/mortality scores: **PGS000906** (Tesi 2021, 330 variants, HR 0.89/SD), **PGS002795** (4 SNPs, evaluated only for CAD), **PGS000318/319** (Meisner 2020 composite mortality, HR 1.10 F / 1.15 M), **PGS001393** (father's age at death, PGS-only R² ≈ 0.0008). The Timmers 2019 score has not been deposited.
- Performance: 0.85–0.98 years per SD in subjects and 3.0–6.4 years between the top and bottom deciles (Timmers 2019). Finnish twins: HR 0.838/SD, against HR 3.34 for heavy smoking. Hainan oldest-old: HR 0.87. Associations become negligible after age 80 (Lahtinen 2026).

## Implications for longevitymap v2 requirements
1. **Rebuild the core around GWAS tiers, not HAGR candidate studies.** Add the 11 tier-1 loci (45 rsIDs in the candidate CSV), keep their published per-allele effects in `gwas_effects`, and record a `tier` (T1–T4) on every row. v1's 528 rsIDs share only 7 rsIDs with the genome-wide-significant set.
2. **One lead variant per locus for scoring.** Enter LD proxies (e.g. rs10455872/rs55730499; rs8042849/rs1317286/rs10519203) as aliases so the same signal is not counted twice. Weight T1 > T2. Report T3/T4 rows as informational only (weight 0), or omit them.
3. **Store allele orientation explicitly.** Studies flip effect alleles (rs429358-T is pro-longevity in Timmers, but C is the effect allele in Joshi and Deelen). Keep `effect_allele` plus a harmonised `pro_longevity_allele` column, and check strand against GRCh38 positions; the candidate CSV includes GRCh38 positions from the Catalog.
4. **Use a `haplotypes`/`diplotypes` table for APOE** (ε2/ε3/ε4 from rs429358 + rs7412). The e2e2 effect differs from e2e3 (Kuo 2020), and ε4's effect is age-dependent.
5. **Write conclusions that name the mediator.** Examples: "this allele lowers Lp(a)/coronary risk", "smoking-related; effect depends on smoking". Do not present these loci as "longevity genes". Explain antagonistic pleiotropy where it applies (CDKN2B-AS1, SH2B3: more cancer risk).
6. **Make ancestry conditional.** European parental-lifespan effects should not drive the call for non-European genomes. Mark IL6 rs2069837, BET1L rs76612380, CLEC3B rs13963 and BMPER as East Asian-specific, low weight, and T3 or T2.
7. **Add a `pgs` pointer table** (PGS000906; PGS000318/319 by sex; PGS001393) with a caveat about the small effect (~1 year per SD, HR ≈ 0.84–0.89). Never present a percentile as a predicted age at death.
8. **Record phenotype class per study** (`extreme_longevity` / `parental_lifespan` / `healthspan` / `multivariate` / `survival`). Treat effects in different units (years, −lnHR, logOR) as non-comparable, and do not sum them across classes.
9. **Downgrade or exclude** the Pilling 2017 rare and sex-specific hits that were not replicated, GPR78, Tanaka rs35715456, FN3KRP, and v1 candidate-gene rows that lack genome-wide support. Keep FOXO3 at reduced weight, since its replication rests on lookups.
10. **Route rare variants** (LoF burden in BRCA1/2, ATM, TET2) to the rare-variant/cancer modules, not this common-variant table.
