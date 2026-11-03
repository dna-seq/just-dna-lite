# Track E — 2025–2026 preprints and publications on human longevity genomics

Scope: bioRxiv/medRxiv 2025-01-01 → 2026-11-03, PubMed 2025–2026, and Europe PMC preprint index, as of 2026-11-03. Every PMID and DOI in the companion tables was checked in code: the title was retrieved from PubMed esummary and/or Crossref. Alleles were taken from paper text or tables, PubMed abstracts, or GWAS Catalog v2; the `source_of_allele` column records which. Coverage limits are listed at the end.

## Search yield
- PubMed: 2,027 records were screened. Core query: 687 (2026) + 739 (2025). Clock query: 111. Somatic-mosaicism query: 56. Targeted mtDNA/long-read/ancestry/replication/review queries: 143 additional records. Records were ranked by keyword pre-score and then by an automated title/abstract screen. 130 were classed as highly relevant and reviewed at title/abstract level; key papers were read in full text.
- medRxiv: the full 2025-01→2026-11 listing was harvested (30,229 unique preprints) and keyword-screened.
- bioRxiv: the API listing was harvested only in part (49,792 of 130,451 records; Jan 2025–Apr 2026). This gap was covered with the Europe PMC preprint index, which returned 432 hits, 247 of them after removing non-human studies.
- The evidence table has 50 items (ranked; relevance 1–3). The candidate-variant table has 41 rows; 39 of these rsIDs/alleles are not in v1.

## What is new

**1. New loci, mostly underpowered and population-specific.**
- *Taiwanese, East Asian* (Hsieh 2026, GeroScience): age-stratified GWAS at ≥85, ≥90 and ≥95 years. Discovery reached only suggestive significance (p<1e-5). 14 of 51 lead SNPs replicated nominally in a second Taiwanese cohort. Several replicating alleles are essentially absent in Europeans, e.g. rs75737809-A, OR 0.32; validation OR 0.18, p=1.1e-7. In Table 4, three of the 14 "replicated" SNPs have the opposite OR direction to discovery. We flag these as exclusions.
- *Japanese* (Sasaki 2025, Research Square, unpublished): 964 centenarians, 173 of them supercentenarians, vs 7,306 controls. Genome-wide hits were APOE (rs429358 and rs7412) and a new Japanese-specific intronic EYS variant, rs75571981. The authors also built a centenarian PGS (8,534 SNVs) that modifies the effects of risk factors on disability-free survival.
- *Calabrian* (Beccacece 2026): n=705. One genome-wide hit (LINC00865 rs11186068, per GWAS Catalog). Most loci did not replicate, and APOE and FOXO3 were not associated.
- *UK Biobank survival GWAS* (Park 2025, Nat Commun): ZSCAN23 rs6902687-C reduces lifespan (p=2.7e-8). Rare-variant burden in TET2, ASXL1, BRCA1/2, ATM and others shortens lifespan.

**2. Rare-variant and familial studies.**
- German WES (Kolbe 2025): rare alleles enriched in long-lived individuals cluster in mTOR signalling (SIK3, FLCN, RPS6, among others). ORs are 3–43 from tiny allele counts and come from a single study.
- Leiden linkage (Putter 2025, bioRxiv, unpublished): rare CGAS rs200818241 (p.D452V) dampens cGAS–STING signalling.
- Functional follow-ups of private familial or centenarian variants: NF1, RAF1, SIRT6, UBE3C.
- WGS of the Long Life Family Study: SLC9A2 rs6543176. Its longevity allele also raises cancer risk.

**3. HLA is the most consistent new non-APOE signal.**
- HLA-DRB1*15:01 is anti-longevity in men (German discovery, Danish and UKB replication). It is tagged by rs3135388-A.
- HLA-B*57:01 has OR ≈0.68 across 2,597 European centenarians.
- Dutch 100-plus preprints: six AD- or autoimmune-associated HLA alleles fall on three haplotypes and are depleted in cognitively healthy centenarians. The 2026 haplotype fine-mapping separates protective DRB1*04 from harmful DRB1*01:01.
- These effects act at the allele or haplotype level, not the single-SNP level.

**4. Polygenic and pleiotropy findings.**
- A low genetic burden for disease, especially CAD and AD (with APOE excluded), underlies multigenerational longevity and centenarian status (Sant'Anna Barbosa Ferreira 2026; Bae 2026).
- A polygenic lifespan score gives HR 0.84 per SD for mortality (Tynkkynen 2026).
- Disease-risk alleles are on average anti-longevity and pro-fertility (antagonistic pleiotropy; Brigos-Barril 2026, Nat Ecol Evol).
- Disease-susceptibility loci barely predict disease-specific survival (Yang 2025, Nat Genet). A 2026 preprint attributes this to low power.

**5. New methods.**
- *Long-read sequencing*: TMEM106B haplotype T3, enriched in centenarians, carries a ~19 kb rearrangement (Salazar, preprint). Endogenous viral element burden differs between AD and centenarians. Nanopore methylation of 7,284 blood samples revealed parent-of-origin ageing at imprinted loci.
- *Somatic mosaicism*: CHIP and mosaic chromosomal alterations independently raise mortality. The measurement method shifts mLOY prevalence from 5.3% to 19.2%. Germline TERT, IL6R, TCL1A and MSI2 variants modulate clone growth.
- *AI and proteomic clocks*: organ-specific plasma-proteome clocks; GWAS of proteomic age (27 loci, rg with longevity −0.83). Their loci are largely pQTLs of the clock's own proteins.
- *Monogenic*: ACMG secondary-finding genotypes (3.4% of 490k UKB WGS participants) raise all-cause mortality, HR 1.31–1.42.

**6. Controversies and failed replications.**
- *Heritability*: Shenhar 2026 (Science) reported intrinsic lifespan h² >50%. Two 2026 preprints dispute it (Hamilton; Kornilov, who estimates +22% inflation of the frailty variance). Independent pedigree work estimates lower values: Utah nuclear h² 23–26% plus mtDNA ≥5%; Dutch pedigrees ~0.19–0.23.
- *Germline vs somatic confound*: ASXL1/TET2 truncating variants are depleted in UKB survival analyses but enriched in German long-lived individuals. Blood WES picks up CHIP, so the sign depends on the age of the sampled group.
- *Null results*:
  - IL6R Asp358Ala is null for survival to 90 (OR 1.00, WHI).
  - APOE and AD PRS are null for SuperAging.
  - APOE and FOXO3 are null in Calabria.
  - FOXO3 rs2802292 is protective only in men with angina (CHAMP).
- *Ancestry*: APOE ε2 protection is questioned in admixed Brazilians, and APOE ε4 effects differ in non-industrial populations. Within Italy, centenarians carry more Western Hunter-Gatherer ancestry, so allele-frequency signals can be confounded by ancestry.

## Implications for longevitymap v2 requirements

1. **Tier every row by evidence, not by source database.**
   - Tier A: genome-wide significant in ≥2 independent cohorts, or a consortium meta-analysis. Example: APOE ε2/ε4.
   - Tier B: genome-wide significant in one study, or replicated nominally in ≥2 cohorts with consistent direction. Examples: ZSCAN23, EYS, HLA-DRB1*15:01.
   - Tier C: suggestive or nominal, a single rare-variant study, or a preprint.
   - Tier D: functional or familial only. Examples: CGAS, NF1, RAF1, SIRT6.
   - Weights should scale with tier. Tier C/D rows should default to weight 0 or display-only.
2. **Require explicit effect-allele and direction provenance.** Add a `direction_basis` field: paper text, table column layout, GWAS Catalog, or interpreted. Reject rows whose effect allele is "NR" or "?" from weighted scoring. Several 2025–26 papers do not state the allele (Hoque, Gurinovich, the Sasaki EYS variant).
3. **Add a direction-consistency check across discovery and replication.** Hsieh's rs373800184, rs117082375 and rs61838431 flip OR between tables and must be excluded.
4. **Store ancestry per study row and restrict scoring by ancestry.** Taiwanese and Japanese loci (and Calabrian loci) should only contribute for matched ancestries. Store allele frequencies per population (the Hsieh tables provide EAS/EUR/TWB).
5. **Add an `hla_alleles` (haplotype) table** keyed on HLA allele names. Tag SNPs (rs3135388-A, rs2395029-G) go in a fallback column with their r² and ancestry. Do not score the six Dutch HLA alleles as independent: they form three haplotypes.
6. **Add a `gene_burden` / rare-variant table**: gene, variant class, carrier HR/OR. Examples: ASXL1, TET2, BRCA1/2, ATM LoF from UKB; RWDD1 missense from German WES. Mark CHIP-driver genes (ASXL1, TET2, DNMT3A, SF3B1, SRSF2, PPM1D, JAK2) "somatic-confounded" and do not count them as germline longevity evidence from blood-derived data.
7. **Model antagonistic pleiotropy explicitly.** Allow a row to carry a longevity effect plus linked disease risks, e.g. SLC9A2 rs6543176 (longevity vs cancer) and APOE ε4 (environment-dependent). Phrase conclusions conditionally.
8. **Use the `pgs` table for polygenic findings** rather than importing hundreds of sub-threshold SNPs. Pointers: PGS Catalog lifespan, CAD and AD-protective scores, plus any published CentPGS weights once released. Record that per-SD effects are modest (HR ~0.84).
9. **Exclude** the following, or put them in a separate non-scoring "context" layer:
   - clock-GWAS loci (proteomic, epigenetic, MRI, retinal age-gap), since these are pQTL- or trait-driven;
   - MR-only exposure studies;
   - n=1 supercentenarian genomes;
   - private familial variants;
   - long-read-only variant classes (EVEs, SVs) until callable from standard user VCFs.
10. **Add `copynumbers` / structural-variant hooks** with a `callable_from` constraint (long-read only) for future rows such as the TMEM106B T3 rearrangement. Keep `heteroplasmy` and mtDNA haplogroup support: pedigree data attribute ≥5% of longevity variance to mtDNA, but no specific variant is yet supported.
11. **Monogenic anti-longevity layer.** Optionally link ACMG SF pathogenic genotypes as Tier B anti-longevity flags (HR 1.3–1.4 in UKB WGS), with clinical-referral wording rather than a longevity weight.
12. **Track preprint status.** Store `peer_reviewed` (yes/no) and `published_doi`, and re-check at each release. bioRxiv/medRxiv `published` fields lagged for every journal version found here (e.g. Brigos-Barril, Shenhar, Beccacece).
13. **Carry the heritability caveat into the UI.** The genetic contribution to lifespan is disputed (≈6–26% in pedigrees vs >50% "intrinsic" in modelling). Reports should state that known variants explain a small fraction of lifespan variance.
