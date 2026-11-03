# Track C: rare/protective variants, centenarian sequencing and longevity families (2015–2026)

**Scope.** 97 papers/preprints reviewed in `evidence_table.csv`; 50 variant or gene-level rows in `candidate_variants.csv`. Every PMID title/DOI was re-fetched from PubMed (preprints: Europe PMC + Crossref). Effect sizes come from abstracts or open full text; where they were not read, they are marked NR. Tier scale: **A** replicated, direct lifespan phenotype; **B** large single-biobank, MR or multi-cohort, indirect phenotype; **C** single case-control/candidate; **D** case report, functional-only, family-specific or preprint.

## 1. Centenarian and supercentenarian sequencing: little that is variant-level and replicated
- Sequencing cohorts are small and mostly negative for single variants. WES of 100 centenarians found no rare protein-altering variant or gene burden (Nygaard 2019, PMID 29750252). WGS of 81 semi-supercentenarians vs 36 controls gave only STK17A/COA1 after adjustment and a DNA-repair/clonal-haematopoiesis signal (Garagnani 2021, 33941312). In 1,879 Ashkenazi WES samples, ClinVar/HGMD pathogenic burden did *not* differ between centenarians and controls (Gutman 2020, 32860726). A single supercentenarian lacked the FOXO3 longevity allele (Santos-Pujol 2025, 40997805).
- Rare "centenarian variants" have functional but not statistical support: SIRT6 N308K/A313S (rs201141490/rs183444295; AF 1.0% vs 0.55%, P=0.3; 36215696), IGF1 p.Ile91Leu/p.Ala118Thr (40133344), mitonuclear LRPPRC/CPS1 variants (35948858), cGAS rs200818241 (preprint) and NF1/RAF1 (Leiden, 40442464). None has an independent replication.
- Gaps: no LLFS or SardiNIA sequencing paper reporting variant-level lifespan results and no Japanese supercentenarian WGS paper were found. Japanese data are GWAS preprints (CentPGS, Sasaki 2024/2025); LLFS yields rs6543176/SLC9A2 (39751714; longevity allele also raises cancer risk).

## 2. Evidence by variant class
| Class | Best evidence | Tier | Mechanism |
|---|---|---|---|
| APOE ε2/ε4 | 28,297 participants, 7 studies; ε4 lowers odds of extreme longevity (30060062); also GWAS (36613555: rs429358-T beta 0.84, p=1.9e-36) | A | lipid/neuro |
| FOXO3 rs2802292-G | pooled OR up to 1.45 in males (29890178); OR 1.21 in Chinese (25913413); *null* in Japanese 733/820 and Italians (27621247) | B | insulin/IGF |
| d3-GHR | d3/d3 rises with age in 3 of 4 cohorts; males +26% (p=0.007) (28630896) | B/C | GH/IGF |
| KL-VS (rs9536314+rs9527025) | OR 0.75 for AD in APOE4 carriers, heterozygotes only (32282020); *no* cognitive effect in N=320,861 (39903109) | B | neuro |
| CLEC3B rs13963-G | OR 1.50, p=1.9e-8 East Asian meta (27154906); failed in Caucasians (31570938) | C | ECM |
| CETP rs5882 | Hainan case-control, direction unclear (27633301); MR: CETP inhibition ↑ lifespan (38082436) | C | lipid |
| SIRT6, IGF1, mitonuclear, cGAS | see §1 | D | DNA repair/IGF/mito/immune |

- **Lipid loss-of-function (PCSK9, APOC3, ANGPTL3, ASGR1).** Evidence is for coronary disease (ANGPTL3 LoF OR 0.59, 28538136; ASGR1 del12 −34% CAD, 27192541; APOC3 LoF −41% ischaemic vascular disease, 29348120). Lifespan evidence comes only from Mendelian randomisation: LDLR, CETP and APOC3 proxies lengthen lifespan; PCSK9 proxies do so but not extreme longevity (38082436). No centenarian-enrichment study of these LoFs was retrieved; treat them as healthspan (lipid), not longevity.
- **Alzheimer-resilience variants** (APOE3 Christchurch rs121918393: onset 52 vs 47 y in 27 heterozygotes, 38899694; RELN-COLBOS: one case, 37188781) delay dementia onset but carry no lifespan data and are almost absent from oldest-old cohorts (0/135 and 5/135 carriers, 41640697). Tier D.
- **Telomere and clonal haematopoiesis (CH).** LTL >1 SD shorter implies 2.5 y lower life expectancy at 40 (34611362), yet LTL-associated variants show little association with parental lifespan (31444995). Germline CH loci (TERT rs34002450/rs7705526/rs2853677; TCL1A rs2887399, opposite effects on DNMT3A- vs TET2-CH; 33057201, 35835912) predispose to a state with all-cause-mortality HR 1.34 (38838228); effect on lifespan is therefore indirect. Centenarians carry fewer autosomal mosaic alterations (RR 0.64; 36988570). Somatic CH, mLOY and mCAs cannot be called from a germline VCF.
- **Mitochondrial.** Haplogroup H vs U HR 2.35 for survival past 60 in one isolate (31887371); mtDNA heritability ≥5% in Utah pedigrees (40907250); T3394C anti-longevity in Rugao (25666573); no replicated variant. m.3243A>G is a pathogenic heteroplasmic variant (37988592). mtDNA-CN lowest quintile HR 1.47 (25471480).
- **ADARB1/2 and IGF1R.** The only ADARB1/2 longevity study located is the pre-2015 NECS/SICS/AJCS/JCS paper behind v1 (20011587); no 2015+ replication was found. No 2015+ rare IGF1R-variant paper was found; v1's rs2229765 remains a candidate-gene entry.

## 3. Pathogenic carriage and lifespan
UK Biobank WGS (n=490,086): coding ACMG SF v3.2 P/LP carriers (3.40%) have all-cause mortality HR 1.42 (females) and 1.31 (males) (42586783). PTV burden: BRCA2 HR 2.57, BRCA1 HR 2.36, TET2 HR 1.76, ATM HR 1.65 (discovery; 37117740). Cardiomyopathy-gene carriers HR 1.5 (35544052). The effect is heterogeneous: MODY carriers show no excess mortality (41175096) while lipodystrophy carriers HR 4.02 (42001615). **No paper retrieved reports "years of life lost" for ACMG genes**; the closest numbers are 1.3 y of lifespan variance from rarest-PTV burden (32254024) and the −2.5 y LTL estimate. Do not state years in the module.

## 4. Genotypability from short-read VCF
SNV/indel rows (APOE, FOXO3, KL-VS, CLEC3B, SIRT6, CETP, PCSK9 R46L, APOC3 R19X, CH loci) are directly callable. Needing special handling: APOE ε and KL-VS (two-SNV haplotypes; rs429358/rs7412 double-het is phase-ambiguous); d3-GHR (exon-3 deletion; use tag rs6873545, R²=1 only in YRI/CEU/CHB); ASGR1 del12 (indel); gene-level LoF/ACMG (needs VEP + ClinVar); HLA-B*57:01 (HLA typing); mtDNA (chrM table: haplogroup, heteroplasmy VAF); CNVs; somatic phenomena (CH, mLOY, mCA) not derivable.

## Implications for longevitymap v2 requirements
1. **Add `evidence_tier` (A–D) and cap weights by tier.** Only tier A (APOE) and tier B with direct lifespan phenotype may carry non-zero longevity weight; C/D are informational.
2. **Model APOE as a haplotype/diplotype table** (rs429358 + rs7412), including the ε4 anti-longevity side and ε2/ε4 phase ambiguity, rather than independent SNV rows; do the same for KL-VS (heterozygote-only effect).
3. **Separate three outcome classes**: longevity/lifespan, healthspan/disease-protection (lipid LoF, KL-VS, APOE3Ch), and disease-risk/mortality (pathogenic carriage). Do not sum them into one score.
4. **Add a gene-level pathogenic/LoF table** (BRCA1/2, ATM, TET2, ACMG SF genes) with HR and source, flagged `acmg_sf`; state risk, never "years of life lost" (not supported).
5. **Include new SNVs with ancestry flags**: rs13963 (East Asian only), rs1046896 (C; unreplicated), rs145265196 (rare, unreplicated). Do not apply East Asian or male-only findings to other ancestries.
6. **Use a structural/tag table for d3-GHR** and a **separate mtDNA table** (haplogroup informational only; heteroplasmy table for pathogenic m.3243A>G). Require chrM QC before reporting.
7. **Treat lipid LoF variants (PCSK9 R46L/C679X/Y142X, APOC3 R19X/A43T, ANGPTL3, ASGR1) as lipid/CAD "protective" flags with zero longevity weight**, citing MR only as supporting.
8. **Exclude or quarantine** n=1 genomes, preprint-only variants (cGAS, CentPGS) and functional-only variants (SIRT6, IGF1) from scoring; keep them as tier D annotations.
9. **Record counter-evidence in `studies.csv`** (FOXO3 Japanese/Italian null, CLEC3B in Caucasians, KL-VS cognition null in N=320,861) so conclusions are hedged by ancestry.
10. **Germline CH loci (TERT, TCL1A)** may be included only as "predisposition to clonal haematopoiesis" risk flags; exclude somatic CH, mLOY and mCA.
11. **Verify identifiers at build time**: rs34002450 is now merged in dbSNP (→ rs11278847); several rsIDs here were taken from dbSNP, not paper text (see `source_of_allele`); strand/GRCh38 coordinates must be re-checked.
12. **Drop or demote the v1 ADARB1/2 block** (18 rsIDs; the rows inspected cite only the 2009 study; no 2015+ replication found) to tier C pending evidence.
