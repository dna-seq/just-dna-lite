# Human longevity genetics: approaches, architecture models and what they imply for longevitymap v2

Track I, 2026-11-03. Based on 139 PubMed-verified records (24 reviews, 16 meta-analyses, 8 perspectives, 91 primary; 48 from 2024–2026). Claims come from abstracts. PMIDs are in brackets.

## 1. Phenotype definition decides what is found

Four phenotype families coexist, and each yields a different set of loci.

- **Extreme survival percentiles.** Deelen et al. defined cases as surviving beyond the 90th/99th birth-cohort survival percentile, with controls at or below the 60th [31413261]. Only APOE ε4/ε2 and one new locus reached significance. Top-1% designs (≥96 y men, ≥100 y women for the 1900 cohort) separate true extreme-survival variants from mortality-selection artefacts [28329165, 36613555].
- **Parental lifespan.** This proxy reaches around 1M parental lifespans [29030599, 29227965, 30642433]. It yields dozens of loci, but they are dominated by disease and behaviour: APOE, LPA, CHRNA3/5 (smoking), CDKN2B-AS1. Dementia, CVD and lung-cancer variants explain most of the variance [30642433].
- **Healthspan and multivariate factors.** Healthspan [30729179], the healthspan + lifespan + longevity combination [32678081], mvAge (effective n≈1.9M) [37550455] and aging-GIP1 [37118362] gain power. Their composite effects are not on a lifespan scale.
- **Familial longevity.** Longevity is transmitted as a quantitative trait from the top 10% of survivors upward [30617297]. The Longevity Relatives Count shows transmission only when ≥20% of relatives are long-lived, so many centenarians are phenocopies [32352215]. Ancestral longevity tracks up to a decade of extra healthspan [37500622]. The familial mortality advantage fades by age 100 [34929024]. Centenarians' offspring show compression of morbidity across three cohorts (HR 0.58 for death) [42646838, 27377170, 22219514].

Healthy ageing ("Wellderly") is distinct: no known longevity variants, but lower AD/CAD genetic risk [27114037].

A "longevity" label is therefore meaningless without the phenotype, age threshold and control definition. Pooling heterogeneous definitions inflates false negatives and biases estimates [28143747].

## 2. The candidate-gene era: why most associations failed

Narrative reviews agree that only APOE and FOXO3A replicate in nearly every population [35628444, 28951210, 37137499]. Recurrent problems were:

- small samples;
- controls decades younger, and therefore from different birth cohorts;
- ancestry mismatch;
- sex- or population-specific subgroup findings;
- biological plausibility from model organisms taken as prior evidence.

SIRT1 shows the last problem clearly: it had no association in 1,573 German long-lived individuals [16257164].

Pooled estimates (as reported in the abstracts):

| Gene / variant | Pooled result | PMID |
|---|---|---|
| APOE ε4 carriage | OR 0.43 (0.36–0.50); ε2/ε3 OR 1.35 (1.06–1.72) | 25385258 |
| APOE (7 cohorts, 28,297 people) | ε4 harmful even beyond 1% survival age; ε2 benefit attenuates | 30060062 |
| ACE DD (Caucasian) | OR 1.25 (1.02–1.54); AI-assisted update OR 1.41 (1.19–1.67) | 23623925, 36834822 |
| FOXO3A rs2802292 | OR 1.36 (1.10–1.69); males 1.54; not in females | 24589462 |
| FOXO3 (4 centenarian studies) | 17 variants replicate for reaching top 1%; none affect mortality beyond | 28977569 |
| CETP I405V | 405V OR 0.81 (0.74–0.88) against longevity, opposite to original Ashkenazi direction | 23977315 |
| IL6 −174 | overall OR 0.96 (0.77–1.20) null; only Italian male centenarians | 18930842 |
| PON1 Q192R | null in 9,580 individuals | 20362697 |
| Five-variant meta-analysis | ACE, APOE, FOXO3A, KL-VS, IL6 ORs 0.42–1.45 | 29890178 |

APOE effects also vary by ancestry and country of residence [31724059]. Implication: v1's 975 of 1,022 rows labelled "protective", with empty effect columns, overstate the evidence.

## 3. Models of genetic architecture

1. **Polygenic common variants.** Loci are many, with small effects; PGS deciles differ by about 5 years [30642433]. Per-person prediction is weak and time-dependent (HR ~0.7–1.2) [40680229].
2. **Absence of risk alleles.** Long-lived people carry as many CAD, cancer and T2D risk alleles as controls [20921414, 25664523], with similar ClinVar/LoF burden [32860726, 25390934]. Disease-specific depletion is nevertheless real:
   - cognitively healthy centenarians have >5-fold lower AD PRS than AD cases [38634500];
   - AD protection grows with extreme age, by about one allele per 5 years [40615639];
   - lower CAD PGS explains up to 20% of the CVD delay in long-lived families [42065824];
   - 9p21 risk alleles are depleted in centenarians [37605876].
3. **Rare protective and depleted-damage variants.** The strongest burden-level evidence is:
   - centenarians carry 11–22% fewer rare LoF variants [39424787];
   - the rarest PTVs cost 0.4–1.3 years of healthspan or lifespan [32254024];
   - rare coding variants converge on IIS/AMPK [37117627] and mTOR [40232348];
   - SIRT6 N308K/A313S [36215696] and a CGAS missense variant (preprint) [41427385] are functionally characterised.

   Biobank exomes find lifespan-shortening LoF mostly in cancer and clonal-haematopoiesis genes (BRCA1/2, ATM, TET2, DNMT3A) [37117740, 40021682].
4. **Buffering, trade-offs and age-dependence.**
   - Buffered-deleterious genotypes (MTP) show U-shaped age trajectories [22496539].
   - Risk alleles can be neutral or pro-longevity in context [26306600, 32130932].
   - Centenarians carry higher SCZ/T2D PRS [35754110].
   - Disease alleles raise fertility [42481894].
   - In mice, lifespan QTL effects invert with age [42020758].
5. **Heritability.** Twin estimates are 20–25%. Assortative-mating-corrected pedigree estimates fall below 10% [30401766]. In 2026, correcting for extrinsic mortality gave intrinsic-lifespan heritability above 50% [41610249, 41610247]. LLFS finds heritable healthy-ageing phenotypes little explained by common variants, suggesting family-private rare variants [34739053]. The debate is unresolved and says nothing about individuals.

## 4. Novel approaches, 2022–2026

- **Mendelian randomization.** MR prioritises causal, modifiable mediators:
  - LDL-c: −1.2 y lifespan per SD, with a PCSK9-specific effect [33704808];
  - LPA and VCAM1 [37118362];
  - IL6R [31552141], haptoglobin [34704651] and translation machinery [35078808];
  - telomere length trades CHD against cancer [31444995];
  - causal CpG clocks separate damage from adaptation [38243142].
- **Multi-omic and organ clocks.** Proteomic clocks predict 18 diseases [39117878]. Organ-age gaps predict organ disease [38057571]. A youthful brain/immune proteome gives mortality HR 0.44–0.60, and youthful brains may buffer APOE4 [40634782, 41299092]. Metabolomic scores predict 5–10-year mortality better than clinical risk factors [31431621, 39504246]. Standards remain unsettled [38355974, 42162380].
- **Exposome plus polygenic integration.** The exposome adds 17 percentage points of mortality variance against <2 for disease PRSs [39972219]. Lifestyle (HR 1.78) outweighs genetic predisposition (HR 1.21) without interaction [38684374].
- **Pathway, hallmark and network aggregation.** Five pathways are consistently supported (IIS, DNA-damage response, immunity, cholesterol, telomeres) [37941149]. Hallmark modules map onto the interactome [42362889, 36599349], although hallmarks are not causal paradigms [34271186]. Lifespan GWAS signal concentrates in homeostatic microglia networks [39778705].
- **Comparative genomics.** Bowhead CIRBP-enhanced DNA repair [41162698], naked mole-rat cGAS [41066557] and rockfish aryl-hydrocarbon metabolism (also enriched in human 99th-percentile GWAS) [36630509]. Long-lived-mammal amino-acid states are 81.2% invariant in humans and 99.78% below 1% frequency [34297086]. They inform gene priors, not genotype rows.
- **Somatic mosaicism.** Centenarians carry fewer mCAs (RR 0.637) [36988570]. TET2/ASXL1 signals in longevity exomes probably reflect clonal haematopoiesis [37117740, 40232348]. Somatic burden is a weak general driver of ageing [38490496]. N-of-1 multi-omics of extreme agers is hypothesis-generating [40997805, 42240775].
- **Long-read sequencing.** More than 60% of SVs are missed by short reads (preprint) [41282933]. A TERT VNTR is depleted in African American centenarians [34155099].
- **AI.** AlphaMissense classifies 89% of missense variants [37733863]; LLM-derived biological age [40702324]. Only 3% of ageing-AI studies include in vivo validation [41685266].

## 5. Open problems and best practice for individual translation

Open problems:

- non-European cohorts;
- birth-cohort-matched controls;
- age-varying effects;
- separating disease-mediated from "ageing-rate" loci;
- rare-variant replication;
- somatic contamination of blood-derived calls;
- calibrating PGS beyond Europeans.

Reviews converge on these practices:

- report phenotype, population and design per claim;
- prefer pooled or replicated estimates;
- carry null results;
- avoid summing single SNPs into a deterministic "longevity score";
- contextualise genetics against modifiable risk.

## Implications for longevitymap v2 requirements

1. **Evidence tier per row.** Proposed tiers: genome-wide replicated, meta-analysis-pooled, single candidate study, rare/family or functional, preprint.
   - *Where:* now as `flags` tokens (`gwas_replicated`, `meta_pooled`, `single_study`, `family_rare`, `preprint`); `priority` derived from tier. Needs a new `evidence_tier` column for clean filtering.
   - *Report:* a tier badge on every hit; single-study rows hidden by default or marked "unreplicated".
2. **Phenotype definition per claim.**
   - *Where:* fill the `phenotype` column, empty in all 1,022 v1 rows, with a controlled vocabulary: `extreme_longevity_99pct`, `longevity_90pct`, `centenarian_vs_younger`, `parental_lifespan`, `healthspan`, `multivariate_ageing`. Needs new studies.csv columns `case_definition` and `control_definition`.
   - *Report:* "associated with reaching the top 1% of survival", not "longer life".
3. **Carry null and contradictory evidence.** Examples: PON1, SIRT1, IL6 overall null, CETP direction flip, FOXO3 no effect beyond the top 1%.
   - *Where:* studies.csv rows with null results; variants `state`/`weight`=0 plus flags `replication_failed` or `meta_null`.
   - *Report:* "tested, not confirmed".
4. **Transcribe effect sizes.**
   - *Where:* `effect_size`, `effect_measure`, `stat_significance` (all empty in v1) from pooled meta-analyses (table in §2).
   - *Report:* OR with CI and the comparison it refers to. No years-of-life conversion unless the source gives one.
5. **Population and sex specificity.**
   - *Where:* studies.csv `population` (exists); flags `ancestry_specific`, `sex_specific`; README note on APOE/CETP shifts.
   - *Report:* show the tested population and warn when effects were confined to one sex or ancestry.
6. **Architecture class.**
   - *Where:* new `architecture_class` column: `common_polygenic`, `disease_risk_depletion`, `rare_protective`, `buffering_conditional`. Interim: flags.
   - *Report:* group hits by class, with the sentence "long-lived people carry many disease risk alleles too".
7. **Disease-mediated loci.** Examples: APOE, LPA, CHRNA3/5, CDKN2B-AS1.
   - *Where:* `trait_efo_id` for the mediating disease; conclusion text cross-references the relevant disease module; README rule against double counting.
   - *Report:* "this effect operates mainly through Alzheimer's / cardiovascular risk".
8. **Age- and genotype-conditional effects.**
   - *Where:* flags `age_dependent_effect`, `conditional_on_genotype` (e.g., APOE4 background).
   - *Report:* a caveat that the effect may differ at different ages or genetic backgrounds.
9. **No ad-hoc polygenic sum.**
   - *Where:* the `pgs` table points to PGS Catalog lifespan/longevity scores. README states that variants.csv weights must not be summed.
   - *Report:* if a PGS is shown, give deciles with uncertainty and the exposome contrast (<2 vs 17 percentage points).
10. **Somatic and CH awareness.**
    - *Where:* flag `possible_somatic_CH` for TET2/ASXL1/DNMT3A calls. Needs VAF in `quality_from`/`min_quality` or a new VAF field. Defer BRCA1/2/ATM LoF to ACMG modules via `acmg_sf`.
    - *Report:* "may reflect blood clonal expansion; not interpretable as inherited longevity".
11. **Callability of indels and repeats.** Examples: ACE I/D, TERT VNTR.
    - *Where:* `requires_callable`/`callable_from` (exist).
    - *Report:* "not assessable from this data type" instead of a silent negative.
12. **Pathway vocabulary.**
    - *Where:* replace v1 `category`="other" (483 rows) with a controlled set of the five consistent pathways plus hallmark terms; README cites the source framework.
    - *Report:* grouping only, with no pathway score.
13. **MR and comparative support as annotations, not rows.**
    - *Where:* flags `mr_supported` and `comparative_support` (gene level). Species variants never become variants.csv rows.
    - *Report:* "causal evidence for the mediator (e.g., LDL, IL6R)" as the actionable layer.
14. **README framing.**
    - *Where:* README.
    - *Content:* the heritability range (<10% to >50%, contested 2026), the dominance of modifiable factors, familial longevity information outside the genotype, and an explicit statement that measured biomarkers or clocks outperform genotype for individual ageing estimates.
