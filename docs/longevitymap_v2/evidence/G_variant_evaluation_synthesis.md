# Track G: Methodology for evaluating SNP-level longevity associations (longevitymap v2)

Scope: how a v2 row should be graded. All PMIDs are in the evidence table (titles checked against PubMed, 2026-11-03); locus facts come from Open Targets 26.09 (locus CSV).

## 1. Causal variant vs tag
- A lead SNP marks an LD block, not necessarily the causal variant. Fine-mapping (SuSiE, PMID 37220626; SuSiE-RSS on summary statistics, 35853082; FINEMAP, 26773131) assigns each variant a posterior inclusion probability (PIP). It also builds 95% credible sets, each expected to contain one causal variant (review: 29844615).
- SuSiE/FINEMAP can be overconfident; SuSiE-inf/FINEMAP-inf are better calibrated (38036779). Open Targets 26.09 labels its sets "SuSiE-inf" or "PICS". PICS sets are built from curated top hits with no in-sample LD, so their PIPs are approximate.
- Functional priors (PolyFun, 33199916; +20–32% PIP>0.95 variants) and multi-ancestry fine-mapping (41491094) narrow sets. About 90% of autoimmune causal variants are non-coding (25363779); single-variant resolution needs very large N (28658209).
- **Longevity data (Open Targets, 16 longevity/lifespan studies):** 57 credible sets with 40 distinct lead variants; 37 PICS and 20 SuSiE-inf; median set size 9.
  - Only 11/40 distinct leads reach PIP≥0.5.
  - APOE rs429358 is the exception (PIP 0.92–1.0 in every longevity set).
  - Several LongevityMap/v1 "classic" SNPs are not in any longevity credible set. FOXO3 rs2802292 appears in 214 sets (mostly adiposity traits) with max PIP 0.16, and is absent from the FOXO3 longevity set, whose lead is rs1159806 (38 variants, lead PIP 0.06). 5q33.3 rs2149954 appears in 114 sets (mostly blood pressure) with max PIP 0.10. TOMM40 rs2075650 is an APOE-region tag.
- **Implication for reports:** a lead rsID should be worded as "marks a region associated with…", not "this variant causes…". Mechanistic language is reserved for PIP≥0.5 or a coding variant with experimental support.

## 2. Effector-gene assignment
- The nearest gene is often wrong. SMR prioritised many genes that were not the nearest to the top SNP (27019110). L2G, a model trained on 445 gold-standard loci, outperforms distance, and L2G genes are enriched for approved drug targets (OR 8.1; 34711957; Platform integration 39657122).
- Colocalisation (coloc posterior H4, 24830394; coloc-SuSiE for multiple causal variants, 34587156; SMR/HEIDI, 27019110) and TWAS (26854917) add expression evidence. TWAS is LD-confounded (30926968). GWAS and eQTL studies also systematically detect different kinds of variants (37857933), and colocalisation explains only about 8% of trait genes (36515579).
- Reporting standards are not settled (40442285). PEGASUS (bioRxiv 2026, not peer reviewed; 42367912) proposes a metadata standard, a per-locus evidence matrix and a short predicted-effector-gene list.
- **Open Targets L2G on the test loci:** APOE 0.97 (coding, PIP ~1; confident). LDLR 0.96 (gene confident; variant not: 49-variant set, PIP 0.04). SH2B3 0.95 (SuSiE-inf lead PIP 0.25; >80 trans-pQTL colocalisations, highly pleiotropic). LPA 0.56–0.76 vs PLG 0.27–0.34 (rs10455872 PIP 0.38; second signal rs186696265 PIP 0.93). CDKN2B 0.36–0.49 (23–53 variants; CDKN2B eQTL colocalisation). CHRNA5 0.17–0.74 vs CHRNA3/PSMA4, study-dependent. FOXO3 0.42 (Timmers 2019 discusses SESN1). ZW10/USP28 unresolved: CLDN25 0.35, ZW10 0.20, colocalisation with USP28. EBF1 top only in blood-pressure sets. HLA-DQA1: no Open Targets credible set retrieved.

## 3. Statistical robustness
- **Significance threshold.** P<5e-8 corresponds to about 1 million independent common-variant tests in Europeans, and roughly twice that in Africans (18348202). Timmers 2019 used 2.5e-8.
- **Candidate-gene studies mostly failed.** Only 6 of 166 repeatedly studied associations replicated consistently (11882781). In longevity:
  - Except for APOE, the candidate genes failed in a large case-control sample (18034366).
  - CHARGE replicated only APOE and FOXO3 (25199915).
  - Timmers 2019 found contradictory evidence at IL6, ANKRD20A9P, USP42 and TMTC2. FOXO3 and EBF1 replicated, but with smaller effects (30642433).
- **Winner's curse.** First reports overestimate effects; heterogeneity is common (11600885). Correction predicts same-ancestry replication; LD differences reduce cross-ancestry replication (28715421).
- **Grading.** Venice rates amount of evidence, replication and bias protection A/B/C (17898028). Bayes factors/BFDP avoid P-value dependence on N and MAF (18642345, 17668372, 15026468). Replication needs same SNP/proxy, same direction, independent sample (17554299).

## 4. Biases specific to longevity
- **Survivorship and selection.**
  - UK Biobank shows healthy-volunteer bias (28641372). Weighting for participation changes SNP effects (37106081).
  - Collider and index-event bias distort associations whenever selection depends on disease or survival (29040562, 30952951, 31373921).
  - An apparent APOE ε4–stroke-onset association is likely survival bias (39286457). APOE–mortality estimates are also fragile to analytic choices (41799341).
- **Centenarian vs young-control designs.** Cases and controls differ in birth cohort and often genotyping batch. The 2010 Science centenarian-signature paper was retracted (20595579); v1 inherits 280 rsIDs from its 2012 successor (22279548). Price-style PCA (16862161) adjusts for ancestry but cannot remove cohort or birth-year effects.
- **Parental-lifespan proxy.** Offspring carry half of each parent's genotype, so estimates are doubled for carriers (29030599; 28092683). Lifespan heritability is probably <10% (30401766).
- **Age- and sex-varying effects.**
  - APOE ε4 costs about 1.24 years of maternal life per allele, and CHRNA3/5 about 0.86 years of paternal life, with strong age and sex dependence (27029810).
  - ε4 still raises death risk beyond ages reached by fewer than 1% of people (30060062). Most other lifespan SNPs act more on early than on extreme-age mortality (30642433).
- **Ancestry.**
  - APOE effects differ even among European sub-ancestries (31724059).
  - Allele frequencies diverge sharply (gnomAD ALT allele frequency via Open Targets): LPA rs10455872-G is 0.069 in NFE vs 0.001 in EAS; rs11065979-T is 0.445 vs 0.002; FOXO3 rs2802292-T is 0.61 in NFE vs 0.24 in AFR.
  - Non-European studies find different loci (36737517, 41949656); PRS portability is poor (30926966).

## 5. Actionability
- **Clinical frameworks.** ClinGen scores severity, likelihood, efficacy and burden (27124788) with 4-level assertions (38757444) and a 2026 population-screening adaptation (42771580). ACMG SF v3.3 (40568962) and CDC Tier 1 (24398597: HBOC, Lynch, FH) concern rare P/LP variants, not common longevity SNPs; screening finds under-treated FH carriers (28008010, 32719484).
- **Modifiable mediators.** Many longevity loci act through measurable risk factors: LDL-C (LDLR, APOE), Lp(a) (LPA; the EAS consensus supports measuring Lp(a) at least once, 36036785), blood pressure (EBF1, SH2B3) and smoking (CHRNA3/5). MR estimates one BMI unit at −7 months of lifespan (29030599). Genetic risk is modifiable by lifestyle (27959714).
- **Drug-target loci:** PCSK9 (16554528; R46L in healthy ≥70-year-olds, 34341098), IL6R (22421340), ANGPTL3 (28538136), APOC3 (24941081), HMGCR (25262344); genetic support raises drug success (38632401, 31830040).

**Proposed actionability tiers and wording:**
1. **Clinical.** Use only when a P/LP variant sits in an ACMG SF or Tier 1 gene. Defer to the clinical modules: "This result may have medical implications; confirm with clinical testing and a genetics professional."
2. **Biomarker-actionable.** "This variant is associated with [Lp(a)/LDL-C/BP]. A standard blood test or measurement your doctor can order shows your actual level, which matters more than the genotype."
3. **Lifestyle-relevant.** "The association appears to act largely through [smoking/BMI]; the behaviour, not the variant, is the modifiable part."
4. **Informational.** "Research association with lifespan; no recommended action."

## 6. Effect-size communication
- Report effects in one consistent unit, chosen per study design:
  - years per allele (parental-lifespan Cox models, with parental estimates doubled);
  - HR per allele;
  - OR for reaching the 90th or 99th survival percentile (31413261).
- Joshi 2017 converts hazard to years with "10% HR ≈ 1 year", from a Gompertz-derived 1% hazard ≈ 0.108 years. Timmers 2019 rescales longevity ORs using APOE as an empirical anchor.
- **Pitfalls:**
  - An extreme-survival OR is not a hazard ratio.
  - Parental estimates are halved unless doubled.
  - Effects are per allele, not per genotype, and assume additivity.
  - Effects are age/sex-dependent population averages (rs1556516-G: +0.25 years, about 3 months; 30642433).

## Evidence-grading rubric (per variant)
- **Tier A (robust):** P<5e-8 in a GWAS with N≥100k lives or ≥3k cases above the 90th percentile; independent replication (same allele direction, P<0.05 or consistent meta-analysis); no red-flag heterogeneity; Venice A/A/≥B.
- **Tier B (supported):** locus is genome-wide significant, but either (a) the reported SNP is a tag outside the credible set, (b) there is replication but with a substantially smaller effect, or (c) there is only one GWAS without independent replication.
- **Tier C (suggestive):** P<1e-5, or a candidate-gene association replicated only in small or same-group samples.
- **Tier D (unsupported or contradicted):** candidate-gene only with no adequately powered replication, or explicitly contradicted (e.g. IL6, USP42, TMTC2 in 30642433).
- **Orthogonal axes, reported separately:**
  - Causal confidence: C1 PIP≥0.5 or coding with PIP≥0.2; C2 in a 95% credible set with PIP 0.1–0.5; C3 in a set with PIP<0.1; C4 not in any credible set or not assessed.
  - Effector confidence: E1 coding variant or L2G≥0.5 plus cis-QTL colocalisation; E2 L2G≥0.5 or colocalisation alone; E3 ambiguous; E4 unassessed.
  - Actionability tier as defined in section 5.

## Implications for longevitymap v2 requirements
1. **`evidence_tier` (A–D).** Needs a new column. As an interim measure, write it to `flags` as `evtier:A`. Computed from the rubric using GWAS significance, replication flags and Venice-style bias notes curated per study. Report: badge plus one-line reason.
2. **Fine-mapping (`credible_set_id`, `pip`, `finemap_method`, `ot_release`).** Needs a new format element, preferably extended `gwas_effects` rows. Machine-filled from Open Targets `credibleSets`/`locus` using the module's longevity study list. Add a `flags` token `tag_not_in_credible_set` when absent. Report: "marks a region" vs "likely causal".
3. **Effector gene.** Keep `gene` as the effector call. Add new columns `locus_label`, `gene_method` (coding/L2G/coloc/nearest) and `l2g_score`. Computed from Open Targets L2G plus cis-QTL colocalisation (H4≥0.8). Report the locus name, and name a gene only at E1/E2.
4. **LD redundancy.** Use `flags` `ld_proxy_of:<rsid>` and move APOE into the haplotypes/diplotypes table. Curated by r² against the credible set. Report: no double counting, so rs2075650 is not reported separately from APOE.
5. **`actionability`.** Existing column, restricted to the vocabulary clinical / biomarker / lifestyle / informational. Add a new `mediator_trait` plus `mediator_efo_id`, or reuse `trait_efo_id` only if the format allows a second EFO term. Report: use the tier wording above.
6. **`acmg_sf`.** Must stay false for common SNPs in ACMG SF genes (e.g. LDLR rs6511720, rs142158911). It can be true only for P/LP variants, which belong in other modules. Enforce with a compile check.
7. **Effect fields (`effect_size`, `effect_measure`, `effect_allele`).** Use a controlled vocabulary: years_per_allele, HR, OR_p90, OR_p99. studies.csv records whether the effect was doubled from a parental estimate. Report: years only when the source gives them; never convert an OR to years in the report.
8. **`study_design`.** studies.csv vocabulary: parental_lifespan_cox, own_survival_cox, percentile_case_control, centenarian_case_control, candidate_gene. A centenarian vs young-control design without replication caps the variant at Tier C. Report: show design.
9. **`population`.** studies.csv, plus `flags` `eur_only_evidence`. Annotate gnomAD allele frequency by ancestry at runtime. Report: "evidence mainly from European-ancestry cohorts; may not apply to you" when the user's inferred ancestry differs.
10. **Age and sex modifiers.** `flags` `sex_specific`, `age_dependent`. Curated from SSE P-values in Timmers 2019 and from Joshi 2016. Report: state which sex or age range the evidence covers.
11. **`stat_significance`.** Best P and threshold; replication P in studies.csv.
12. **Contradicted v1 rows.** Keep them as Tier D with state neutral, or drop them, and record the contradiction in the README. `weight` scales with tier, and Tier D gets weight 0.
13. **README.** Document Open Targets release, thresholds, conversion rules, rubric, and that heritability <10% means no individual lifespan prediction.
