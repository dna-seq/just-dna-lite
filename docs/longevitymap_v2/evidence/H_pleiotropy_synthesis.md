# Track H: pleiotropy and context-dependence of longevity variants (longevitymap v2)

Scope: how to label *how* a lifespan SNP acts. Evidence: 79 PubMed-verified papers and an Open Targets (OT) PheWAS of 41 variants (27,548 credible-set memberships; 20,211 at p<5e-8). Locus values: `longevity_locus_pleiotropy_assessment.csv` (32 rows); OT disease hits: `ot_phewas_disease_extract.csv`.

## 1. Most lifespan loci act through specific diseases

- **Timmers 2019 (eLife, PMID 30642433)** decomposed parental-lifespan signals. Lifespan-raising alleles go with less cardiometabolic, autoimmune, smoking-related and neuropsychiatric disease, and no locus associated with cancer other than lung cancer. Across the 45 disease SNPs with the largest lifespan variance explained (LVE), 0.43 y² ran through CVD, 0.15 y² through smoking/lung cancer and 0.11 y² through other cancers. APOE alone gave 0.23 y². The authors note that the share of heritability explained by disease SNPs is limited, so the "disease vs. ageing" split stays open.
- **Multivariate scans.** Timmers 2020 (32678081) combined healthspan, parental lifespan and longevity and found 10 shared loci, most of them CVD-associated. Timmers 2022 (37118362; aging-GIP1, 27 regions) used MR to implicate apo(a) and VCAM1. Rosoff 2023 (37550455; mvAge, 38 loci) used drug-target MR to favour PCSK9 inhibition, metformin targets and antihypertensives. Dinh 2026 (41405793) built a five-disease multimorbidity factor whose 263 variants are enriched for extreme-longevity associations. Genomic SEM (Grotzinger 2019, 30962613) is the formal tool for separating shared-factor loci from trait-divergent ones.
- **Genetic correlations.** In Joshi 2017 (29030599), lifespan correlates positively with quitting smoking, education and HDL, and negatively with CAD, smoking, lung cancer, insulin resistance and body fat. MR estimates: −7 months per BMI unit, +11 months per year of education.
- **The OT re-analysis confirms this.** Most lifespan leads carry dense disease profiles: APOE (308 disease-like credible sets), SH2B3 (283), LPA (230), TCF7L2 (235). Only FES/FURIN rs6224, HTT rs61348208 and FOXO3 rs1159806 have almost no disease footprint. They are the current candidates for an "ageing-general / unresolved" label.

## 2. Per-locus PheWAS: beneficial vs harmful effects of the longevity allele

The full table is in the CSV. Recurring patterns:

- **Acts mainly through one disease axis (most loci).** APOE e4 works through dementia plus LDL/CVD. LPA, CDKN2B-AS1, LDLR and CELSR2/SORT1 work through CVD. CHRNA3/5 works through smoking, lung cancer and COPD. TCF7L2 works through T2D. PHTF1/PTPN22-region works through autoimmunity. FTO/MC4R work through adiposity, but neither has a genome-wide-significant SNP-level lifespan credible set in OT, so their direction is inferred via BMI MR. IRF4, TYR and DEF8/MC1R work through skin cancer and pigmentation.
- **Trade-offs (help A, harm B):**
  - **SH2B3 rs3184504.** The C allele protects against autoimmune thyroid disease, T1D, coeliac disease, hypertension and CAD. It is linked to parental extreme longevity (CC vs TT OR 1.18) but also to slightly more cancer (OR 1.03; Kuo 2020, 31428775). The T allele (W262) is linked to lower sepsis mortality (Allenspach 2021, 34740959) and carries a positive-selection signature (Zhernakova 2010, 20560212).
  - **IL6R rs2228145-C.** Lower CRP, CAD, AAA and RA, higher atopic dermatitis/allergy, and lower TB (OR 0.94; Hamilton 2025, 39579785). Reduced IL-6 signalling associates with longer parental lifespan "at the expense of higher atopic risk" (Rosa 2019, 31552141).
  - **PCSK9 R46L.** Lower LDL and CAD, but LDL-lowering PCSK9 variants raise T2D (OR 1.29 per mmol/L; Schmidt 2017).
  - **LPA / CETP.** Very low Lp(a) raises T2D (Gudbjartsson 2019); CETP rs3764261-A lowers CAD but raises AMD (Burgess 2017).
  - **TERT/TERC.** The shorter-telomere alleles lower glioma, lung adenocarcinoma, myeloma and CLL but raise pulmonary fibrosis. Longer telomeres mean more cancer but less CHD, AAA and ILD (Haycock 2017).
  - **CDKN2B-AS1 and ATXN2/BRAP.** Their cancer-protective alleles shorten lifespan through CVD (Timmers 2019).
  - **APOE e4.** Lower CRP and BMI, and protection against obesity, T2D, gallbladder and liver disease (Lumsden 2020). e2e2 carries recessive vascular harms.
- **Net direction** is clear only for loci with a direct GWAS lifespan signal (tier A). For TERT, TERC, CETP rs3764261, CETP rs5882 and KL-VS it is not determinable from current data.

## 3. Antagonistic pleiotropy (AP): grading the evidence

- **Moderate, genome-wide.** Rodríguez 2017 (28812720) found an excess of early–late antagonistic variants enriched in ageing genes. Long & Zhang 2023 (38064565; UKB n=276k) found a strong negative genetic correlation between reproduction and lifespan, and the reproduction PGS rose across 1940–1969 birth cohorts. Xiang 2025 (40792619) used MR to link earlier menarche or first birth to shorter parental lifespan and more AD, T2D and heart disease. Mostafavi 2017 (28873088) found that puberty-delaying variants associate with longer parental lifespan. These are polygenic, population-level findings. They say little about any single SNP.
- **Moderate, locus-specific selection trade-offs.** SH2B3 (selection plus sepsis) and inflammatory loci generally (Raj 2013) point to infection resistance versus autoimmunity. HLA is under balancing selection (Radwan 2020). HLA-DRB1*15:01 lowers longevity in men only (Mendoza-Mejía 2025, 41116190).
- **Weak: APOE e4 early-life benefit.** The evidence is a non-significant survival HR of 0.80 in Ghana (van Exel 2017), cognition under parasite burden in 372 Tsimane (Trumble 2017), a small diarrhoea cohort (Oriá 2010) and a ~1–4% myocardial contraction difference (Topriceanu 2024). Reports should say "hypothesis" rather than "benefit".
- **Allele labels conflict.** Long 2023 calls rs12203592-T "major", but gnomAD (via OT) gives T an AF of 0.168 in non-Finnish Europeans. Re-harmonise any AP allele taken from a paper.

## 4. Gene–environment and context

- **Smoking.** CHRNA3/5 effects run through smoking quantity. The paternal effect is larger (−0.86 y per allele; Joshi 2016). FOXO3 G protected against lung cancer only in former smokers (Chen 2026, 42582819).
- **Hypertension.** FOXO3 G protected against CAD only in hypertensive men (interaction p=0.038; Chen 2024, 39497655).
- **Sex.** APOE e4 has a larger effect on maternal lifespan (sex-difference P=0.011). Mother-only and father-only loci exist (Pilling 2017). Sex direction for FOXO3 is inconsistent across studies (Ji 2022 vs Revelas 2018). Longevity associations are stronger in females in Chinese centenarians (Zeng 2024).
- **Ancestry.** For APOE e3/e4 the AD OR ranges from 4.54 in East Asian to 1.90 in Hispanic individuals, and e2 protection is absent in Hispanic and East Asian individuals (Belloy 2023). The obesity PRS–lifespan effect differs between Japanese and Europeans (Sakaue 2020). Several tag SNPs are essentially European-specific: LPA rs10455872 (EAS AF 0.001), PCSK9 R46L, rs12203592 and CHRNA5 rs16969968. Ancestry-specific loci include BET1L (Japanese) and BMPER (Chinese).
- **Lifestyle and socioeconomic factors.** A lifespan PRS and lifestyle act additively, with no multiplicative interaction (p=0.10; Bian 2024). Lifespan heritability is <10% after assortative mating is accounted for (Ruby 2018). This caps how much any SNP report should imply.
- **Gene–gene.** KL-VS heterozygosity lowers AD only in APOE4 carriers (Belloy 2020).

## 5. Vertical vs horizontal pleiotropy

Vertical pleiotropy means the lifespan effect is mediated through a disease or risk factor: CHRNA5 → smoking, LDLR/PCSK9 → LDL, FTO → BMI. Horizontal pleiotropy means independent paths (Hemani 2018, 29771313). Calling a SNP "pro-longevity" conflates the two. A vertically acting allele is pro-longevity only *conditional on exposure*: CHRNA5 effects should vanish in never-smokers, and drug-target proxies mimic a treatment. Horizontally pleiotropic loci (SH2B3, APOE, HLA) bundle benefits and harms, which MR-Egger, MR-PRESSO and CAUSE are designed to detect. A rulebook should therefore record the mediating pathway.

Sign hazard: lifespan GWAS use opposite conventions. In Timmers, + means longer life; in Pilling Martingale residuals, + means shorter life; in Zenin healthspan, + means an earlier end of healthspan. Some OT credible sets carry apparently inverted signs. I checked consistency against the APOE e4 and LPA anchors.

## 6. Current v1 status

Only 5 of the 32 assessed loci are in v1 (rs429358, rs7412, rs2802292, rs5882, rs9536314). `flags`, `phenotype`, `direction`, `actionability` and `stat_significance` are empty in all 1,022 rows. `category` is pathway-based, not mechanism-based. One rs9536314 row has genotype "A/T", impossible at a T>G site.

## Implications for longevitymap v2 requirements

1. **Pleiotropy label (controlled vocabulary).** Tokens: `MECH:<area>`, `BROAD`, `TRADEOFF:<helps>|<harms>`, `CONTEXT:<modifier>`, `NONADDITIVE`, `UNRESOLVED`, `AP:<weak|moderate|strong>`, `MR:vertical|drug_target_proxy`, `ANCESTRY_TAG`.
   - *Where:* the existing `flags` column, semicolon-separated (currently empty).
   - *How:* curated from the PheWAS extract plus the literature, using the definitions in this document. `MECH` applies when one disease area accounts for most genome-wide-significant disease credible sets in a consistent direction. `TRADEOFF` applies when a genome-wide-significant or MR-supported association runs opposite to the longevity direction.
   - *Report:* a chip for each label.
2. **Mediating disease.** *Where:* existing `phenotype` and `trait_efo_id` for the primary pathway (e.g. EFO for CAD), plus `category` re-coded to mechanism (cvd, dementia, smoking_lung, t2d, autoimmune, adiposity, skin_cancer, ageing_general). *Report:* "acts mainly through: coronary disease".
3. **Per-trait benefit/harm table.** *Where:* needs a new file, `pleiotropy.csv`, with columns rsid, effect_allele, trait, trait_efo_id, direction (benefit/harm for the longevity allele), effect_size, effect_measure, p_value, source_study_id, pmid, ancestry and tier. *How:* machine-filled from OT credible sets (lead or PP≥0.05, p<5e-8) with allele harmonisation, then curator-pruned to at most ~10 distinct diseases. *Report:* a two-column "may lower / may raise" list.
4. **Harmonised longevity allele and sign convention.** *Where:* the existing `effect_allele` and `direction` columns, with `direction` restricted to "effect_allele → longer/shorter life". The source sign convention goes in `studies.csv` (new `sign_convention` column: years | martingale | log-OR | healthspan-hazard) and in `gwas_effects` units. *How:* a compile-time check against anchors (APOE e4 = shorter). *Report:* never raw betas, only "per copy: ~+0.4 y (parental-lifespan units)".
5. **Net direction and evidence tier.** *Where:* `state`/`weight` carry net direction only when the tier is A (direct genome-wide-significant lifespan or longevity signal). Tier goes in `stat_significance` (A/B/C), and `priority` is down-weighted for tiers B/C. A `TRADEOFF` with an unresolved net direction gets `state=neutral`, `weight=0`. A dedicated `mixed` state would need a format change. *Report:* trade-off variants are excluded from any summed longevity score, and the score is labelled as excluding them.
6. **Context modifiers.** *Where:* a new `effect_modifiers.csv` (rsid, modifier [smoking/sex/ancestry/hypertension/APOE4/UV/pathogen], stratum, effect, pmid), plus `CONTEXT:` flags. *How:* curated from stratified or interaction studies; only reported interactions are recorded, never inferred ones. *Report:* "effect seen mainly in smokers / in hypertensive men", with an explicit "not established in your ancestry" banner when the discovery ancestry differs or the allele frequency is under 1%.
7. **Non-additive genotypes.** *Where:* per-genotype rows in `variants.csv` (KL-VS heterozygote, e2e2) and the `haplotypes/diplotypes` format for APOE. Cross-locus conditions (KL-VS × APOE4) need a format change: a `requires_genotype` column. *Report:* the genotype-specific statement, never a per-allele extrapolation.
8. **AP and evolutionary context.** *Where:* README only, plus an `AP:<strength>` flag on loci with locus-specific evidence (SH2B3 moderate, APOE weak). *Report:* an "evolutionary note", labelled hypothesis, with no effect on colour or score.
9. **Report rendering for trade-offs.** Never use a single red/green colour. Use a neutral (grey/violet) balance glyph with both sides listed, the net lifespan arrow only at tier A, and context chips. `actionability` should stay empty for longevity rows. Where a drug-target proxy exists (PCSK9, IL6R, LPA), say that the genotype is not an indication to treat.
10. **Provenance.** `studies.csv` needs one row per claim, including the trade-off claims (e.g. Schmidt 2017 for PCSK9-T2D), with population verbatim. OT-derived rows should cite the study ID (GCST/FinnGen) and the Platform query date.
