# Module: Familial Longevity & cGAS-STING Signalling

## Purpose
This module annotates rare, high-impact genetic variants associated with familial longevity. It focuses on the discovery of protective missense variants that contribute to extended healthspan and cellular lifespan, in particular a reduced-function variant in the cGAS gene which dampens canonical cGAS-STING signalling and delays cellular senescence.

## Data Sources
- **bioRxiv Preprint**: "Rare longevity-associated variants, including a reduced-function mutation in CGAS, identified in multigenerational long-lived families" (DOI: 10.1101/2025.12.04.689698)
- **Leiden Longevity Study (LLS)**: Genomic regions linked to ancestral familial longevity using nonagenarian sibships.
- **Nature 2023 Study (PMID: 37532932)**: Grounding evidence that cGAS-STING signalling drives ageing-related inflammation and neurodegeneration.

## Design Decisions
- **CGAS rs200818241**: Documented as the primary longevity variant identified in the preprint. The D452V (T->A) missense mutation significantly dampens cGAS protein stability. As this is highly protective, the `A/T` genotype was given a weight of +0.8, and the `A/A` genotype +1.2.
- **Additional Longevity Variants**: Included prominent rare variants from genes identified via linkage analysis (SH2D3A, RARS2, SLC27A3) that were shown to be enriched in long-lived families compared to standard controls.
- **Variant Prioritization**: Only the strongest candidates from the collapsing filtering strategy were selected, focusing on those present across multiple independent long-lived families.

## Changelog
- **v1** (2025-05-18): Initial creation — added rare familial longevity variants in CGAS, SH2D3A, RARS2, and SLC27A3.