# Track D — Genetics of healthspan, biological ageing rate and heritability (2018–2026)

Evidence table: [longevity_trackD_evidence.csv](../evidence/D_healthspan_evidence.csv) (64 records; 60 PMIDs title-verified via PubMed esummary, 4 preprints title-verified via Crossref). Candidate variants: [longevity_trackD_candidate_variants.csv](../evidence/D_healthspan_candidates.csv) (52 rows, 49 unique rsIDs; 47 not in v1.2.0). Effect alleles come from GWAS Catalog v2 REST or from main-text tables in open-access full texts, as recorded in `source_of_allele`.

## 1. How heritable is lifespan?
- **Pedigree estimates are low.** Ruby et al. 2018 (Genetics; PMID 30401766) found that in-law correlations capture most of the familial resemblance in lifespan. After modelling assortative mating, true heritability was "well below 10%". Kaplanis et al. 2018 (Science; PMID 29496957) give h² ≈ 12% (mid-parent) to 16% (sex-concordant relatives), with ~4% dominance. These figures come from the bioRxiv copy of Kaplanis, because that was the version available.
- **The 2026 upward revision.** Shenhar, …, Alon 2026 (Science; PMID 41610249) model twins reared together and apart and remove extrinsic mortality (accidents, infections). They report intrinsic-lifespan heritability above 50%. Two 2026 preprints dispute this: infection mortality is itself heritable (Hamilton), and omitting heritable extrinsic risk biases Falconer h² upward by +2.8 to +18.9 pp (Kornilov). **Status: contested.** The defensible user message is "roughly 10–25% of lifespan variation is familial or genetic in historical populations. Estimates of up to ~50% for intrinsic (age-related) mortality are debated."
- **The measured genome explains much less.** A parental-lifespan polygenic score spans ~5 years between the top and bottom deciles (Timmers 2019, eLife; PMID 30642433). The rarest protein-truncating variants account for 0.4 years of healthspan and 1.3 years of lifespan variability (Shindyapina 2020; PMID 32254024).

## 2. Genetics versus lifestyle: magnitudes a report should state
| Source | Genetic contribution | Environment/lifestyle contribution |
|---|---|---|
| Argentieri 2025 Nat Med (PMID 39972219; n=492,567) | PRS for 22 diseases: <2 pp extra mortality variance beyond age+sex | Exposome (25 factors): +17 pp |
| Bian 2024 BMJ Evid-Based Med (PMID 38684374; n=353,742) | Short- vs long-lifespan PRS: HR 1.21 (1.16–1.26) | Unfavourable vs favourable lifestyle: HR 1.78 (1.71–1.85); both: HR 2.04; no multiplicative interaction (p=0.10) |
| Sakaue 2020 Nat Med (PMID 32251405; n=675,898) | SBP PRS: HR 1.03 per SD for shorter lifespan, trans-ethnic | BMI PRS effect differs between Japanese and Europeans |
| Codd 2021 Nat Genet (PMID 34611362) | LTL >1 SD shorter at age 40: 2.5 years lower life expectancy (observational) | — |

PRS do dominate for dementias and breast, prostate and colorectal cancer (10.3–26.2%; Argentieri 2025). For all-cause lifespan, the lifestyle HR excess is ~3–4× the polygenic one.

## 3. Robust lead variants by candidate sub-panel
**Longevity / lifespan core (Tier A).** APOE ε4 rs429358-C (OR 0.60 for reaching the 90th percentile) and ε2 rs7412-T (OR 1.28) (Deelen 2019; PMID 31413261). Timmers 2019 parental-lifespan loci, in years per protective allele: rs429358-T +1.06, LPA rs10455872-A +0.76, CHRNA3/5 rs8042849-T +0.44, ATXN2/SH2B3 rs11065979-C +0.28. Further loci: CDKN2B-AS1, FURIN, HLA-DQA1, LDLR, and HP (also MR-supported; Perrot 2021). **IL6 rs2069837-A** is genome-wide significant in Europeans (Deelen 2019) and in Han Chinese (Zeng 2016; PMID 26912274; OR 1.64), making it the strongest new cross-ancestry candidate. GPR78 rs7676745-A (OR 0.67) is significant in one study only, so it is tier B.

**Healthspan core.** Timmers 2020 (Nat Commun; PMID 32678081) report 10 loci whose A1 allele raises healthspan, parental lifespan and longevity together: SLC4A7, LINC02513, FOXO3 rs1159806-T, ZW10, FGD6, LPA, CDKN2B-AS1 rs7859727-C, TOX3, LDLR and APOE. FOXO3 rs1159806 is in LD (r²>0.4) with v1 rs2802292. Zenin 2019 (PMID 30729179) adds the replicated TCF7L2 rs34872471-C (shorter healthspan; log HR 0.061), which is also the top cardiometabolic-multimorbidity hit (Zhao 2024). Zenin's pigmentation loci (IRF4, TYR, DEF8) probably act through skin cancer; TYR and DEF8 did not replicate.

**Frailty.** Atkins 2021 (FI, SNP h² 11%), Ye 2023 (Fried score; 37 loci; PRS OR 1.27 in HRS) and Mak 2025 (HFRS; FinnGen+UKB ~0.9M; 53 lead variants; h² ~6%; APOE strongest). The Catalog gives no effect alleles for Mak, so only the Atkins leads (HLA-DQB1 rs9275160, HTT rs82334) are in the candidate CSV.

**Biological ageing rate (biomarker loci).**
- Epigenetic clocks: McCartney 2021 (137 loci; top hits include CREB3L3 rs73538174 for PhenoAge, NHLRC1 for IEAA, F2RL3/SIN3B for GrimAge) and Lu 2018 (TERT).
- Telomere length: Codd 2021 (197 sentinels; alleles taken from Li 2020 AJHG) and Nakao 2026 (All of Us + UKB, 234 loci, including ancestry- and female-specific loci).
- mtDNA copy number: Gupta 2023 (WGS, 92 loci; LONP1, TFAM).
- Mosaic loss of Y: Thompson 2019 (156 loci) and Francis 2024 (MVP preprint, 380 loci). Mosaic loss of X: Liu 2024.
- Proteomic age: Mörseburg 2025 (BRCA1, POLR2A, TET2) and Argentieri 2025 (medRxiv preprint; 27 loci; rg with longevity −0.83).

TL alleles are **not** pro-longevity alleles: genetically longer LTL lowers CAD risk but raises several cancers (Li 2020).

**Organ ageing.** Wen 2024 (9 organ systems; 393 locus–BAG pairs) and Zhu 2025 (13 proteomic organ ages; 119 loci) keep their alleles in unextracted supplements. Brain age (Jawinski 2025; 59 loci; SNP h² 23–29%) is dominated by the MAPT/KANSL1 inversion region. Oh 2025 (non-genetic) offers framing: an aged-brain proteome confers Alzheimer's risk (HR 3.1) similar to one APOE4 copy.

**Intrinsic capacity, resilience, healthy ageing.** Intrinsic capacity has 10 loci (Beyene 2025; SNP h² 19.5–25.2%; no effect alleles in the Catalog). Cognitive resilience (Phillips 2025) and Super Seniors (Hoque 2026) have no genome-wide-significant hits. None of these is ready for a variant panel.

## 4. Mendelian randomisation (causal levers)
- Longevity at the ≥90th percentile (van Oort 2021; PMID 33107078), per SD: BMI OR 0.80, education OR 1.64, LDL-C OR 0.75, smoking initiation 0.75; SBP OR 0.96 per mmHg.
- SBP and parental lifespan: −0.20 parental-age z per SD (Chan 2021).
- Lipid drug targets (Chen 2023; PMID 38082436): LDLR, CETP and APOC3 extend lifespan; HMGCR and PCSK9 lengthen lifespan but not extreme longevity.
- mvAge (Rosoff 2023, n_eff ~1.9M): metformin targets, thiazolidinediones and PCSK9 inhibition show benefit.
- IL-6: genetically reduced signalling is linked to longer parental lifespan but more atopy (Rosa 2019; PMID 31552141). IL6R eQTLs colocalise with parental survival (Leung 2026).

## 5. Sex and ancestry
Large GWAS are almost all European (UKB, FinnGen). Sex-specific loci: Pilling 2017, Zeng 2018 (suggestive) and Nakao 2026 (one female-specific TL locus). LOY is male-only and LOX female-only. East-Asian clock and frailty GWAS (Lin 2022, Oh 2026, Kwak 2026) are small and unreplicated.

## Implications for longevitymap v2 requirements
1. **Split the module into sub-panels** carried in a `subpanel`/category field: `longevity_core`, `lifespan_core`, `healthspan_core`, `frailty`, `biological_ageing_rate`, `organ_ageing`. Only the first four feed a longevity score. Biomarker loci (clocks, TL, mtDNA-CN, LOY/LOX, brain age) are reported as biomarker tendencies, never summed into lifespan.
2. **Tier the evidence.**
   - **A:** genome-wide significant in a ≥300k GWAS and replicated independently (APOE, LPA, CHRNA3/5, CDKN2B-AS1, LDLR, ATXN2/SH2B3, TCF7L2, IL6 rs2069837).
   - **B:** genome-wide significant in one analysis only (the 5 new Timmers 2020 loci, GPR78, Zenin pigmentation loci).
   - **C:** v1 candidate-gene rows without genome-wide replication, labelled "historical/candidate" with weight ≤ tier B.
   - Exclude sub-genome-wide hits (Zeng 2018, Kwak 2026, Hoque 2026, Phillips 2025).
3. **Use `gwas_effects` for every tier A/B row**, keeping the native measure (years per allele, −log HR, OR at the 90th/99th percentile, log HR for healthspan). Derive `weight` by a documented monotone transform, and always state the measure.
4. **Model APOE as ε2/ε3/ε4 diplotypes** (rs429358 + rs7412) with the Deelen ORs, and drop the per-SNP APOE rows to avoid double counting. De-duplicate LD pairs the same way: FOXO3 rs1159806 vs v1 rs2802292, and CDKN2B-AS1 rs1556516 vs rs7859727.
5. **Add a `pgs` table** pointing to PGS Catalog scores for parental lifespan, healthspan, frailty, LTL and epigenetic age acceleration. The IDs were not verified in this track. Present the polygenic score, not single SNPs, as the main genetic summary (~5 years between top and bottom deciles).
6. **State the section 2 magnitudes in the report**: genetic HR 1.21 vs lifestyle HR 1.78; <2 pp vs 17 pp of mortality variance; heritability <10% to ~25%, with a contested ~50% for intrinsic mortality. Say plainly that a healthy lifestyle largely offsets genetic risk.
7. **Annotate each mediated locus with its mechanism** (smoking: CHRNA3/5; lipids: LPA/LDLR; T2D: TCF7L2; skin cancer: IRF4/TYR; autoimmunity: HLA/MAGI3) and the matching modifiable factor. Drug-target MR (PCSK9, HMGCR, LDLR, CETP, APOC3, IL6R, metformin) goes in the conclusion text, not the weight.
8. **Take `population` from each study.** Flag European-only rows and hedge conclusions for other ancestries. Highlight IL6 rs2069837 as cross-ancestry replicated. Mark LOY rows male-only and LOX rows female-only.
9. **Label TL alleles "biomarker", never "pro-longevity".** MR effects on cancer and on vascular disease point in opposite directions.
10. **Use the `heteroplasmy` table only as a research note** (Gupta 2023, chrM:302). There is no lifespan-grade evidence yet.
11. **Re-derive GRCh38 positions and ref/alt from dbSNP for the 47 new rsIDs, and check strand, before compiling.** The Catalog gives only the effect allele.
12. **Hold back proteomic and organ-age GWAS variants** (Zhu 2025, Wen 2024, the Argentieri 2025 preprint) until their supplementary tables are curated.
