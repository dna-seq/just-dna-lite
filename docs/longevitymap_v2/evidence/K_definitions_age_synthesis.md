# Track K — What counts as a pro-longevity variant, and at what age it acts

Companion files: evidence table (70 verified PMIDs), definitions comparison (11 classes), age-of-action table (40 loci), and Timmers 2019 age-band profiles (24 loci, derived from the paper's Figure 5 source data).

## 1. Eleven ways the literature defines a pro-longevity variant

The definitions differ in two ways: **what endpoint they measure** and **which ages they can see**.

- **Extreme-survival case-control (EXTREME_SURVIVAL_CC).** Survivors past the 90th/99th percentile, or centenarians, are compared with younger controls. The effect integrates all mortality up to the threshold. Deelen 2019 (31413261) reports stronger effects at the 99th than the 90th percentile for most variants (APOE e4 OR 0.60→0.52; e2 OR 1.28→1.47). Sample sizes are small, controls are often still alive, and the design cannot say *when* an allele acted. Results are ancestry-bound: APOE and FOXO3 were weak or absent at ≥85/90/95 y in Taiwan (Hsieh 2026, 41949656).
- **Parental lifespan / kin-cohort (PARENTAL_LIFESPAN).** About 1 M parents give most of the known loci (30642433, 29227965, 29030599). The signal is diluted by 50% kinship, parents dying before 40 are excluded, and living parents are censored. Parents born in the early 20th century inflate smoking and CVD loci.
- **Own-survival Cox (OWN_SURVIVAL).** This design allows direct age-interaction and competing-cause analyses (Wolters 2019, 31356640: e4 HR 1.17, falling to 1.07 after censoring for dementia). Deaths in biobanks recruited at 40–70 y are few and cancer-dominated (Park 2025, 40021682). Disease-specific mortality loci overlap little with susceptibility loci (Yang 2025, 41028524).
- **Healthspan and multivariate ageing factors (HEALTHSPAN / MULTIVARIATE_AGEING).** These include Zenin 2019 healthspan (30729179), Timmers 2020 MANOVA (32678081), aging-GIP1 (37118362) and mvAge genomic SEM (37550455). They have the most power and find non-disease loci (FOXO3, FGD6, ZW10, HTT, MAML3). However, healthspan counts non-fatal first diagnoses, such as skin cancer (IRF4, TYR, DEF8), and a factor locus need not change lifespan.
- **Viability / allele-frequency change with age (VIABILITY_AF).** Mostafavi 2017 (28873088) found only two genome-wide signals: APOE e4, whose frequency declines after age 70, and CHRNA3, which declines across almost all paternal ages. The design gives an age profile directly but needs an ancestry and birth-cohort null model.
- **Familial longevity scores (FAMILIAL_LONGEVITY).** FEL, LRC and mLRC are case-selection devices rather than variant tests (11253150, 30617297, 32352215, 33407157). Longevity is heritable only when ≥20% of relatives are long-lived.
- **Disease-allele depletion (DISEASE_DEPLETION).** Evidence conflicts. Beekman 2010 (20921414) and Gutman 2020 (32860726) found no depletion. In contrast, CAD PGS falls with the number of long-lived ancestors (Sant'Anna 2026, 42065824), and a non-APOE AD protective score rises with age at death in centenarians (Bae 2026, 40615639).
- **Rare variants / burden (RARE_BURDEN).** Large exome studies mostly find life-**shortening** genes (BRCA1/2, ATM, TET2, ASXL1; 37117740, 40021682). Pro-longevity rare variants come from small centenarian exomes (IGF1R, mTOR, IIS/AMPK, Wnt; 18316725, 40232348, 37117627) and are unreplicated.
- **Evolutionary (EVOLUTIONARY).** Antagonistic pleiotropy, purifying selection on early-onset disease variants and mammalian constraint (28812720, 38064565, 28640878, 32043462, 28683096) explain why risk alleles persist. They do not test human lifespan per variant.
- **Mendelian randomization (MR_MEDIATOR).** Here a pro-longevity allele means "lower exposure" (LDL, Lp(a), blood pressure, BMI, smoking, VCAM1). This defines actionability but assumes a lifelong, age-invariant effect.
- **Biomarker clocks (BIOMARKER_CLOCK).** Slower epigenetic or proteomic ageing is not the same as longer life. TERT alleles that lengthen telomeres *raise* intrinsic epigenetic age acceleration (Lu 2018, 29374233).

## 2. Absence of risk vs presence of protection vs buffering

- **ABSENCE_OF_RISK.** The "pro-longevity" allele is the common allele at a disease-risk locus: APOE non-e4 (rs429358 T), the CHRNA3/5 major allele, and the 9p21 non-risk haplotype. The long-lived simply lack a harmful allele. Most GWAS lifespan loci are of this kind (Timmers 2019: dementia, CVD and lung-cancer variants explain the most variance).
- **PRESENCE_OF_PROTECTION.** A minority allele confers benefit beyond the population baseline: APOE e2, PCSK9 R46L (CHD HR 0.50; 16554528), LPA loss-of-function alleles (28007139), and candidate IGF1R/mTOR rare variants.
- **BUFFERING.** An allele or score that reduces the penalty of another risk factor: the Tesi 2021 longevity PRS partly compensates for e4 (33216869), and Wnt rare variants are pro-longevity in APOE4 carriers (37117627). This needs interaction evidence, and none is genome-wide significant yet.

A simple operational rule: label ABSENCE_OF_RISK when the pro-longevity allele has frequency >0.5 in the study ancestry and the locus is a known disease-risk locus; label PRESENCE_OF_PROTECTION when it is the minor allele with a protective biomarker or disease effect; assign BUFFERING only from a published interaction.

## 3. Recommendation for scoring vs annotation

**Score from:**
- EXTREME_SURVIVAL_CC (the most specific for "longevity"; 99th-percentile evidence ranks highest);
- PARENTAL_LIFESPAN (the most powerful);
- OWN_SURVIVAL;
- VIABILITY_AF (confirmatory only);
- HEALTHSPAN/MULTIVARIATE_AGEING, only when the locus also has at least a suggestive lifespan-type signal.

**Annotate only:** FAMILIAL_LONGEVITY (as a design attribute that up-weights specificity), DISEASE_DEPLETION, RARE_BURDEN (pro-longevity claims stay tier C–D until replicated), EVOLUTIONARY, MR_MEDIATOR and BIOMARKER_CLOCK.

Every studies.csv row should carry one `study_phenotype_class` from this list of 11 values. It should also record the threshold or age band (e.g., ">=99th pct vs <=60th", "parents 40–75 y") and PROXY:PARENTAL where applicable.

## 4. Age-of-action axis: criteria

The reference scale is the per-allele log hazard ratio. Absolute effects can still differ: e4 costs 0.2 life-years before 75 but 1.1 after (Joshi 2016, 27029810).

- **LIFELONG.** No significant age moderator (P≥0.05), all age-band estimates have the same sign, and the 80+/40–60 ratio lies between 0.5 and 2. This is provisional because power is limited.
- **MIDLIFE.** A significant negative age moderator (FDR q<0.05 = DIRECT; nominal = DIRECT_WEAK); or ratio <0.5 plus a supporting collective trend (Timmers 2020: −24%/decade for nine loci); or inference from a mediating disease whose genetic relative risk declines with age (Jiang 2021, 34437535: 9 of 24 diseases, mostly declining).
- **LATE.** A significant positive age moderator, a stronger effect at the 99th than the 90th percentile, allele-frequency decline starting after 70, or a design contrast (top-10% vs attained age).
- **AGE_INVERTING.** A sign change between age bands, each side at least nominally significant, within one study.
- **EARLY_LIFE.** A mortality effect before 40. This is structurally invisible to parental (deaths <40 excluded) and adult-cohort designs.
- **UNKNOWN.** No age-resolved data and an ambiguous mediator, or conflicting evidence.

**Confidence levels:**
- DIRECT: an age-stratified or interaction test significant at FDR;
- DIRECT_WEAK: age-stratified estimates are available but the trend is nominal or non-significant;
- INFERRED: classification rests on the mediating disease;
- UNKNOWN.

## 5. Results (40 loci; counts provisional)

The main new data source is the Timmers 2019 Figure 5 source data. These give per-allele estimates for 24 lifespan variants in 10-year parental age bands, which we pooled over fathers and mothers.

**Overall counts:**
- Classes: 18 MIDLIFE, 12 LIFELONG, 4 LATE, 6 UNKNOWN; no locus met AGE_INVERTING or EARLY_LIFE.
- Confidence: 4 DIRECT, 21 DIRECT_WEAK, 9 INFERRED, 6 UNKNOWN.

**Main findings by locus:**
- **APOE e4** is the only firmly LATE locus. Its magnitude rises across age bands (0.028 → 0.098 → 0.172; moderator P=2.2e-14). This agrees with Joshi 2016 (HR 1.09 → 1.20 in mothers), Timmers 2020 (+32%/decade), Deelen 2019, Mostafavi 2017 and Sebastiani 2019. Wolters 2019 found no age difference in cohorts with mean age 65.5.
- **CHRNA3/5, CDKN2B-AS1 and ABO** are DIRECT MIDLIFE (q = 0.0048, 0.011, 0.0086). CDKN2B-AS1 falls from 0.055 at 40–60 y to 0.008 at 80+.
- **LPA** attenuates but persists (0.109 → 0.053; P=0.04, nominal).
- **SH2B3/ATXN2 and HLA-DQA1** are flat, so LIFELONG (P = 0.91 and 0.82).
- **FOXO3** is UNKNOWN. Parental bands are flat or declining, while centenarian case-control (Flachsbart 2009, 19196970) shows a stronger effect at 100+.
- **5q33.3** illustrates a design trap. Its parental effect sits mostly before 60, yet it was discovered as "survival beyond 90" (24688116). A threshold design integrates earlier mortality, so a 90+ hit does not imply LATE.
- **Healthspan-only pigmentation loci (IRF4, TYR, DEF8)** are INFERRED MIDLIFE and flagged HEALTHSPAN_ONLY.

The table gives a lay report sentence for every locus, for example: "Mainly affects the risk of dying before about 80, through coronary heart disease."

## 6. Interactions

**With pleiotropy.** Trade-offs are age-indexed. SH2B3 C lowers CHD (OR 0.95) but raises cancer (OR 1.03) (31428775). Because CHD's genetic relative risk declines with age while cancer's age profile differs, the net balance can change across ages. APOE e4 shows age- and sex-specific trade-offs between CVD and cancer (23094790, 24497847). A TRADEOFF label should therefore carry the ages over which each arm operates. AGE_INVERTING is reserved for a demonstrated within-lifetime sign change. HTT's paternal 90+ band reversal (P=0.034, 1,853 deaths) does not qualify.

**With the parental-lifespan proxy.** Late effects are under-powered: Timmers 2019 has 1,853 paternal deaths at 90–120 y versus 84,545 at 70–80 y. Many parents of UKB participants are still alive and therefore censored. Early deaths (<40) are excluded. Birth cohorts born around 1900–1950 inflate smoking and CVD loci. Parental-only loci should therefore default to "MIDLIFE or LIFELONG, LATE untested". Loci found only in extreme-survival designs need an age-resolved replication before being classed LATE.

## Implications for longevitymap v2 requirements

1. **Study phenotype class** (11-value enum). Where: studies.csv. Interim, as a controlled prefix in the existing `phenotype` column (e.g., "PARENTAL_LIFESPAN: …"); a dedicated `phenotype_class` column needs a format change.
2. **Score vs annotate role per study.** Where: studies.csv. This needs a format change (`evidence_role` = score|annotate); interim, enforce it in the tiering script from the phenotype class.
3. **Threshold / age band / proxy flag.** Where: studies.csv `phenotype` or `population` text (existing). Structured `age_min`, `age_max`, `proxy` columns need a format change.
4. **Age of action and its confidence.** Where: variants.csv `flags` (existing), e.g. `AGE:LATE;AGECONF:DIRECT`. A dedicated column is optional (format change).
5. **Age-band effect sizes.** Where: studies.csv, one receipt row per age band (existing columns, with the band in `phenotype`). A structured per-band schema needs a format change.
6. **Report sentence.** Where: variants.csv `conclusion` (existing), using the phrase from the age-of-action table.
7. **Absence of risk / presence of protection.** Where: variants.csv `flags` (existing: `PROTECT:ABSENCE_OF_RISK` / `PROTECT:PRESENCE`).
8. **Buffering.** This needs a format change: conditional or epistatic rules referencing another genotype, such as APOE e4 status. Interim, use `flags` CONTEXT:APOE4 plus conclusion text.
9. **HEALTHSPAN_ONLY and BIOMARKER labels.** Where: variants.csv `flags` (existing); the scorer must exclude them from lifespan scoring.
10. **Ancestry non-replication** (e.g., APOE/FOXO3 in Taiwan; Hsieh 2026). Where: `negatives` (existing), with population.
11. **Null depletion findings** (Beekman 2010, Gutman 2020). Where: module-level notes or `negatives` (existing).
12. **Age-indexed trade-offs.** Where: pleiotropy label in `flags` with an age qualifier, e.g. `TRADEOFF:CHD<80|cancer`. Interim, this is existing free-text `flags`; a structured version needs a format change.
13. **Sex-specific age effects** (e4 maternal; CHRNA3/5 paternal; HLA-DRB1*15:01 male). Where: `flags` CONTEXT:sex (existing).
