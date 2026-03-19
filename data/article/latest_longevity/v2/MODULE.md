# Module: Latest Longevity

## Purpose
This module highlights the latest findings (as of early 2025) on rare, high-impact genetic variants that affect human lifespan, susceptibility to frailty, and extreme familial longevity. It encapsulates recent evidence identifying novel protective mechanisms, primarily dampening of innate immune signaling and preservation of cellular fitness. It also includes highly pleiotropic variants underlying a multivariate age-related disease factor (mvARD) that shows inverse genetic correlation with extreme longevity.

## Data Sources
- **PMID 41427385 (Putter et al., 2025):** "Rare longevity-associated variants, including a reduced-function mutation in cGAS, identified in multigenerational long-lived families." This hypothesis-free genetic linkage study identified 12 rare protein-altering variants in seven candidate genes (including `CGAS`, `NUP210L`, `SLC27A3`, `CD1A`, `IBTK`, `RARS2`, and `SH2D3A`).
- **PMID 41249831 (Sheikholmolouki et al., 2025):** "The association of the SIRT6 rs117385980 variant with frailty and longevity: an exploratory study." Examines the `SIRT6` stop-gained variant in older adults, discovering potential antagonistic pleiotropy effects regarding extreme old age.
- **Dinh et al., 2025 (GeroScience):** "Genetic links between multimorbidity and human aging." A multivariate genome-wide association study that identified a shared genetic liability (mvARD) across five major age-related diseases (heart attack, high cholesterol, hypertension, stroke, and type 2 diabetes). Lead SNPs were found to be inversely correlated with extreme human longevity.

## Design Decisions
- **cGAS (rs200818241):** Functional data supports that the variant dampens canonical cGAS-STING signaling, leading to reduced cellular senescence. It was weighted highly as a protective allele.
- **SIRT6 (rs117385980):** Due to the complex nature of the stop-gained mutation, the T allele's absence in the oldest-old (80-90 years) and inverse association with extreme lifespan reported in a Finnish cohort informed a designation as a longevity risk, while the T/T homozygote is estimated to be strongly deleterious given the function of SIRT6.
- **Rare Linkage Variants:** Heterozygous variants under linkage peaks discovered in long-lived sibships were scored with moderate positive weights. In absence of functional data for their homozygous states, these genotypes were conservatively included as "alt" states with equivalent weights.
- **mvARD Pleiotropic SNPs:** Added 5 highly pleiotropic lead SNPs from Dinh et al. (2025) associated with the shared cardiometabolic multimorbidity factor (mvARD). Known functional genes in these loci (e.g., *ZNF259*, *SORT1*, *SH2B3*, *TRIB1*, *GCKR*) have been assigned risk or protective weights corresponding to their effects on lipids, blood pressure, and related morbidities, which inversely dictate their impact on extreme longevity.

## Changelog
- **v1** (2025-02-12): Initial creation. Added 11 rare variants across 8 genes based on 2025 findings.
- **v2** (2025-10-XX): Added 5 highly pleiotropic SNPs from Dinh et al. 2025 (mvARD GWAS) representing shared genetic liability for multimorbidity that is inversely correlated with extreme longevity.