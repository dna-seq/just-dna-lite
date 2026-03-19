# Module: Latest Longevity

## Purpose
This module highlights the latest findings (as of early 2025) on rare, high-impact genetic variants that affect human lifespan, susceptibility to frailty, and extreme familial longevity. It encapsulates recent evidence identifying novel protective mechanisms, primarily dampening of innate immune signaling and preservation of cellular fitness.

## Data Sources
- **PMID 41427385 (Putter et al., 2025):** "Rare longevity-associated variants, including a reduced-function mutation in cGAS, identified in multigenerational long-lived families." This hypothesis-free genetic linkage study identified 12 rare protein-altering variants in seven candidate genes (including `CGAS`, `NUP210L`, `SLC27A3`, `CD1A`, `IBTK`, `RARS2`, and `SH2D3A`).
- **PMID 41249831 (Sheikholmolouki et al., 2025):** "The association of the SIRT6 rs117385980 variant with frailty and longevity: an exploratory study." Examines the `SIRT6` stop-gained variant in older adults, discovering potential antagonistic pleiotropy effects regarding extreme old age.

## Design Decisions
- **cGAS (rs200818241):** Functional data supports that the variant dampens canonical cGAS-STING signaling, leading to reduced cellular senescence. It was weighted highly as a protective allele.
- **SIRT6 (rs117385980):** Due to the complex nature of the stop-gained mutation, the T allele's absence in the oldest-old (80-90 years) and inverse association with extreme lifespan reported in a Finnish cohort informed a designation as a longevity risk, while the T/T homozygote is estimated to be strongly deleterious given the function of SIRT6.
- **Rare Linkage Variants:** Heterozygous variants under linkage peaks discovered in long-lived sibships were scored with moderate positive weights. In absence of functional data for their homozygous states, these genotypes were conservatively included as "alt" states with equivalent weights.

## Changelog
- **v1** (2025-02-12): Initial creation. Added 11 rare variants across 8 genes based on 2025 findings.