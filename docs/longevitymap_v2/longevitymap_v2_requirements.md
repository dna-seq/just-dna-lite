# longevitymap v2: requirements

*Draft 1, 2026-11-03. Target: `just-dna-seq/longevitymap@2.0.0`, GRCh38, just-dna-format 0.7.1 / compiler 0.7.2 / enricher 0.7.3.*

Every PMID cited here was title-checked against PubMed on 2026-11-03. Every number comes from code run in this session or from a sub-agent evidence file listed in §13. Numbers marked *provisional* come from partial inputs; §12 lists the limits.

---

## 0. Summary

**v1 cannot be extended into v2.** v1.2.0 is a faithful port of HAGR's LongevityMap, which has been frozen at Build 3 (24 June 2017). It is mostly candidate-gene evidence, and more than half of it rests on one centenarian GWAS whose predecessor paper was retracted. Since then the field has moved in five directions:

1. **Large genome-wide studies** (parental lifespan in about 1 million people, ≥90th/≥99th-percentile survival, multivariate healthspan) replaced candidate genes. Only 6–7 of their ~120–150 genome-wide-significant rsIDs are in v1.
2. **Most robust lifespan loci act through specific diseases or behaviours**: Alzheimer's disease and cardiovascular disease (APOE), Lp(a) (LPA), LDL (LDLR), smoking (CHRNA3/5) and 9p21 heart disease (CDKN2B-AS1). Several are **trade-offs** (e.g. SH2B3 and CDKN2B-AS1 alleles that protect against cancer shorten life through CVD).
3. **Fine-mapping and gene assignment changed what a SNP means.** Only 11 of 40 lead variants at longevity loci reach PIP ≥ 0.5 in Open Targets. The classic v1 SNP FOXO3 rs2802292 is not in the FOXO3 longevity credible set.
4. **The genetics-versus-environment balance is now quantified.** Common-variant scores add <2 percentage points of mortality variance against 17 for the exposome (Argentieri 2025, PMID 39972219). Lifestyle HR is 1.78 against polygenic HR 1.21 (Bian 2024, PMID 38684374). Heritability estimates range from <10% (Ruby 2018, PMID 30401766) to ~50% for "intrinsic" lifespan (Shenhar 2026, PMID 41610249), which is contested.
5. **Rare-variant, HLA and non-European work** adds signals, but they are small, ancestry-specific or confounded by somatic clonal haematopoiesis (TET2, ASXL1).

**v2 is therefore a re-curated module built around evidence tiers and *how* each variant acts.** It is aimed at three readers (citizen, geneticist, ageing researcher), and it does not sum per-SNP weights into a "longevity score". A seed list of **228 rsIDs in 161 loci** has been assembled ([longevitymap_v2_seed_variants.csv](data/seed_variants.csv)). By the provisional consensus, **11 lead loci are tier A** and 82 are tier B; curation will prune that.

Each scored locus carries **seven axes, reported separately and never merged into one score** (§4.2):
1. evidence tier;
2. mechanism;
3. pleiotropy;
4. **age of action**: lifelong, mainly mid-life, or late-life. Of 40 loci classified so far: 18 mid-life, 12 lifelong, 4 late, 6 unknown;
5. **outcome profile**: healthspan, lifespan, exceptional survival;
6. **actionability**: what, who, when;
7. ancestry/sex context.

Every study row records **which definition of "pro-longevity"** it uses (§4.5).

**Decisions needed from the module author** are in §11. The two that change the most:
- **weights:** recommended is *no weights*, ordering by `priority`;
- **APOE:** recommended is a diplotype inside v2 with longevity-specific conclusions, cross-linked to the existing `apoe_epsilon` module.

---

## 1. Why v2 is a redesign: the v1 audit

v1 tables, profiled with uv on 2026-11-03 ([longevitymap_v1_audit_profile.json](data/v1_audit_profile.json)); the LongevityMap track supplied the Build 3 comparison.

| Property | v1.2.0 | Consequence |
|---|---|---|
| Size | 528 rsIDs, 1,022 genotype rows, 671 study rows, 126 PMIDs, 272 genes | — |
| Source currency | LongevityMap Build 3 (2017-06-24) has 550 entries, 3,144 variants and 884 genes, and has not been updated since (PMIDs 29121237, 37933854). Cited PMIDs date from 1993–2015, median 2009 | The module is stale by construction |
| Concentration | **280 of 516 study-cited rsIDs** come from one paper, Sebastiani 2012 (PMID 22279548). Its 2010 *Science* predecessor is **retracted** (PMID 20595579). Within that 281-SNP classifier, only rs2075650 was genome-wide significant | More than half the module is one overfit classifier, scored as 280 independent "significant" findings |
| Replication | Only **35 rsIDs** have ≥2 independent significant PMIDs, and 12 have ≥3 | — |
| Direction skew | **975 protective vs 47 risk** genotype rows; no neutral rows | The report's "Net weight" is positive for almost everyone |
| Weights | Mechanical dose formula: hom = 2 × het on 478 of 482 rsIDs. Spearman ρ(\|weight\|, number of significant studies) = 0.16 (LongevityMap track). `weighting:` is not declared | Weights do not track evidence |
| Conclusions | **79 distinct conclusions across 1,022 rows**; one study sentence is shared by 548 rows; no row addresses the reader | Unreadable; fails `module-voice` |
| Quantitative fields | Effect allele, effect size and p-value empty on 671 of 671 study rows; no coordinates | Cannot be checked or tiered |
| Categories | 483 rows (47%) are `other` | Grouping carries little information |
| Coverage of modern loci | LPA, CHRNA3/5, CDKN2B-AS1, SH2B3/ATXN2, HLA-DQA1/DRB1, LDLR, FURIN and ZW10 are **absent**. Only 6–7 of ~120–150 genome-wide-significant longevity rsIDs in the GWAS Catalog are in v1 (*provisional*, trait-set dependent) | The best-established signals are missing |

**Out of date is not broken.** v1 met the LongevityMap contract, an inclusive literature index that also recorded negative results. In v2 it is kept as a *legacy and negative-evidence layer* (§4.4), not as the scored core.

---

## 2. What the field now says, and what each finding forces in v2

| Finding | Key sources (PMID) | Requirement it creates |
|---|---|---|
| The phenotype definition decides which loci are found: extreme-percentile survival finds little beyond APOE; parental lifespan finds disease- and behaviour-mediated loci | 31413261, 30642433, 29030599, 32678081 | R-PHENO: every study row records its phenotype class (§6.3) |
| Candidate-gene associations mostly fail to replicate. Only APOE and FOXO3 survived CHARGE; general replication rate is 6 of 166 | 25199915, 11882781, 30642433 | R-TIER: candidate-only rows cannot be tier A/B (§4) |
| Lead SNPs are usually tags. APOE rs429358 has PIP 0.92–1.0; most other leads PIP < 0.5; L2G often disagrees with the nearest gene | 34711957; Open Targets 26.09 via the methodology track | R-CAUSAL: report "marks a region" unless C1; name a gene only at effector confidence E1/E2 (§4.2) |
| Most lifespan signal runs through CVD, dementia and smoking/lung cancer; several loci are trade-offs; effects of the 9 non-APOE loci shrink ~24% per decade of age while the APOE ε4 effect grows ~32% per decade | 30642433, 32678081 | R-MECH and R-PLEIO: mechanism-first organisation, explicit trade-off rendering (§5, §6.2) |
| Long-lived people carry ordinary disease-risk allele loads. AD and CAD risk is specifically depleted | 20921414 (concepts track) | R-VOICE: say "long-lived people carry many risk variants too" (§7) |
| Genetics vs lifestyle: polygenic HR 1.21 vs lifestyle HR 1.78, with no interaction; PRS <2 pp vs exposome 17 pp of mortality variance | 38684374, 39972219 | R-CONTEXT: a mandatory context card in the report (§5.1) |
| Heritability is contested: <10% after correcting for assortative mating; 12–16% in population pedigrees; ~50% "intrinsic" (disputed) | 30401766, 29496957, 41610249 | R-CONTEXT: state the range and name what each estimate measures |
| A parental-lifespan PRS separates the top and bottom deciles by 3.0–6.4 years; the only PGS Catalog longevity score is PGS000906 (330 SNPs, HR 0.89/SD) | 30642433; GWAS track | R-PGS: polygenic summary via the `pgs` pointer, not a sum of weights (§6.5) |
| Non-European loci rarely overlap with European ones (IL6 rs2069837 in Han Chinese, BMPER, BET1L, CLEC3B, Taiwanese loci); 2026 Calabrian GWAS finds APOE/FOXO3 null | 26912274, 33657282, 41949656, 42176242 | R-ANCESTRY: per-row ancestry, ancestry-specific flags, mismatch banner |
| HLA is the most consistent new non-APOE signal (DRB1*15:01 anti-longevity in men; B*57:01 enriched in centenarians) | 41116190, 41135092 | R-HLA: tag SNPs flagged with r²/ancestry; allele-level table deferred (§10) |
| Rare loss-of-function burden: depleted in centenarians, oncogenic genes in UKB; TET2/ASXL1 signals are probably somatic CHIP | 39424787, 40021682, 40232348, 37117627 | R-SCOPE: rare LoF goes to cancer/ACMG modules; v2 holds cross-references only |
| Unbiased mouse genetics (UM-HET3, Diversity Outbred, BXD) shows sex- and age-dependent lifespan QTL, genetics outweighing dietary restriction, and strong G×E. **FGD6** is supported in mice and worms *and* is a human healthspan locus | 36173858, 40326784, 39385029, 34552269 | R-ANIMAL: an orthogonal "animal support" annotation that never contributes to tier (§4.3) |
| **Age of action differs by locus.** In Timmers 2019 age-band data, APOE's per-allele effect rises 0.028 → 0.098 → 0.172 from parental age 40–60 to 80+ (age-moderation P = 2.2×10⁻¹⁴). CHRNA3/5, CDKN2B-AS1 and ABO fade with age; SH2B3/ATXN2 and HLA-DQA1 stay flat. No genome-wide age-varying-hazard lifespan GWAS exists | 30642433, 32678081, 27029810 | R-AGE: age-of-action axis with stated confidence (§4.2) |
| **Different definitions of "pro-longevity" find different things.** Most GWAS lifespan loci are *absence of risk* (the common, non-risk allele at a disease locus). *Presence of protection* is rare (APOE ε2, PCSK9 R46L, LPA loss-of-function). *Buffering* has no genome-wide-significant interaction evidence | definitions track (70 PMIDs) | R-DEF: study phenotype class and protection type per row (§4.5) |
| **Rare-variant sequencing of centenarians is small and mostly negative at variant level.** Pathogenic burden is similar in long-lived people (PMID 32860726). In UK Biobank, carriers of ACMG SF P/LP variants have all-cause mortality HR 1.42 (women) / 1.31 (men). Lipid loss-of-function variants protect against coronary disease, but their lifespan evidence comes only from MR | 29750252, 33941312, 32860726, 30060062, 38082436 | R-SCOPE (unchanged): rare variants as cross-references |
| **Almost no human longevity allele has been tested allele-specifically in mice for lifespan.** The one knock-in with lifespan data is PPARG Pro12Ala, whose benefit is diet-dependent. Direction can disagree across species (GHR) | 19117549, 36215696 | R-ANIMAL-4: direction-concordance flag (§4.3) |
| Reporting standards: PRS-RS (22 items, ancestry); ClinGen risk-allele terms (Established/Likely/Uncertain); Venice credibility grading | 33692554, 38054408, 17898028 | R-TIER labels and R-PGS metadata |

---

## 3. Scope

**In scope (scored or shown by default):**
- common germline variants with a genome-wide-significant association to longevity, lifespan, parental lifespan or healthspan (tiers A/B);
- APOE ε2/ε3/ε4;
- a pointer to a published longevity PGS.

**In scope (research view only, not scored):**
- candidate-gene and legacy LongevityMap rows (tiers C/D);
- loci that predict a biomarker (telomere length, epigenetic and proteomic clocks, mtDNA copy number, mosaic loss of Y). The Healthspan track is explicit that these are **biomarkers, not pro-longevity alleles**: for example, alleles for longer telomeres lower CAD risk but raise several cancers.

**Out of scope (cross-reference only):**

| Topic | Goes to |
|---|---|
| Rare P/LP variants in ACMG SF genes (BRCA1/2, ATM, LDLR familial hypercholesterolaemia) | `pathogenic` / `cancer` / `cardio` modules. v2 keeps `acmg_sf = false` on all common SNPs in ACMG genes (e.g. LDLR rs6511720, rs142158911) |
| CHIP genes (TET2, ASXL1, DNMT3A) | Not genotype-scorable from germline VCF without a VAF check |
| Disease PRS | The PRS tab (just-prs) |
| Structural variants, VNTRs, mtDNA heteroplasmy | Hooks only, using `requires_callable` / `callable_from`. The binning-table consumer is not implemented (`module-consumer` 🚧) |

**Rare-variant handling (from the rare-variant re-run):**
- **R-RARE-1:** model KL-VS (rs9536314 + rs9527025) as a haplotype, and APOE as a diplotype, not as independent SNVs. The d3-GHR deletion is reached via its tag (rs6873545) with `requires_callable`.
- **R-RARE-2:** lipid loss-of-function variants (PCSK9 R46L, APOC3, ANGPTL3, ASGR1) are shown as coronary-protective with lifespan evidence `MR-only`, never above tier B for longevity. APOE3-Christchurch and RELN-COLBOS are Alzheimer's-onset findings from single kindreds and go to the research view.
- **R-RARE-3:** ancestry-restricted signals are recorded with their counter-evidence:
  - CLEC3B rs13963: East Asian only; failed in Caucasians;
  - FOXO3 rs2802292: positive meta-analysis in men; null in Japanese and Italian samples.
- **R-RARE-4:** ADARB1/ADARB2 (18 v1 rsIDs; PMID 20011587) have no replication since 2015 and drop to tier C.
- **R-RARE-5:** germline clonal-haematopoiesis loci (TERT, TCL1A) get only a `ch_predisposition` flag. Somatic CHIP, mosaic loss of Y and mCAs are not callable from a germline VCF.
- **R-RARE-6:** ACMG carrier status is reported as a hazard ratio (UK Biobank: HR 1.42 women / 1.31 men), never as "years lost", and only by cross-reference to the clinical modules.

**Double-counting rule:** a locus that also appears in `cardio`, `lipidmetabolism`, `coronary` or `apoe_epsilon` carries a flag `also_in:<module>`. Its v2 conclusion talks about *lifespan*, not about the disease the other module covers.

---

## 4. Evidence model

### 4.1 Evidence tier: the one axis that gates scoring and default visibility

This merges the rubrics from the methodology, GWAS, preprints, Healthspan and reporting tracks. The labels follow ClinGen's risk-allele language (PMID 38054408) and the voice guide's certainty ladder.

| Tier | Report label (certainty ladder) | Criteria (all must hold) | Default view |
|---|---|---|---|
| **A** | *Well established* | p < 5×10⁻⁸ for a longevity, lifespan, parental-lifespan or healthspan phenotype in a GWAS with N ≥ 100k lives, or ≥ 3k cases above the 90th percentile; independent replication (same allele, same direction; p < 0.05 or consistent meta-analysis); no red-flag heterogeneity | Shown, ordered first |
| **B** | *Likely* | Genome-wide significant locus, plus one of: a single study without independent replication; a replicated locus whose reported SNP is a tag outside the credible set; replication with a much smaller effect; ancestry-specific replication only | Shown |
| **C** | *Early evidence* | Suggestive (p < 1×10⁻⁵), or candidate-gene association replicated only in small or same-group samples, or a preprint-only finding | Research view |
| **D** | *Not supported* | Candidate-gene only with no adequately powered replication, explicitly contradicted (e.g. IL6, USP42, TMTC2 in PMID 30642433), meta-analysis null (PON1, SIRT1, IL6 −174), or retracted or overfit source | Research view, shown as negative evidence |

**Hard rules:**
- **R-TIER-1:** a row whose only support is PMID 22279548 is tier **D**: no weight, `state: neutral`, research view only.
- **R-TIER-2:** an unreplicated centenarian-versus-young-control design caps at tier C, because of cohort and batch confounding.
- **R-TIER-3:** a European-only tier is not transferred to other ancestries; the ancestry banner (§5.4) applies.
- **R-TIER-4:** sub-genome-wide hits, MR-only results and n = 1 supercentenarian genomes are never tier A/B.

### 4.2 Orthogonal axes, reported separately and never folded into the tier

| Axis | Values | Source | Interim home (format 0.7.1) |
|---|---|---|---|
| Causal confidence | C1: PIP ≥ 0.5, or coding with PIP ≥ 0.2 · C2: in a 95% credible set, PIP 0.1–0.5 · C3: in a set, PIP < 0.1 · C4: not in any set or not assessed | Open Targets credible sets (record the release, e.g. 26.09) | `flags: causal:C1` |
| Effector-gene confidence | E1: coding, or L2G ≥ 0.5 plus cis-QTL coloc · E2: L2G ≥ 0.5 or coloc alone · E3: ambiguous · E4: unassessed | Open Targets L2G, coloc H4 ≥ 0.8 | `gene` = effector call; `flags: effector:E2` |
| Mechanism (mediating system) | see §5.2 | Timmers 2019/2020 disease decomposition, Open Targets PheWAS, literature | `category` |
| Pleiotropy | `mech:<area>`, `broad`, `tradeoff`, `context:<modifier>`, `nonadditive`, `ap:<weak\|moderate\|strong>`, `mr:drug_target_proxy`, `ancestry_tag` | Pleiotropy track ([locus table](evidence/H_pleiotropy_loci.csv)) | `flags` (reserved `pleiotropic` also set) plus `negatives` prose |
| Actionability | **Label:** `preventable` (a biomarker a doctor can measure: Lp(a), LDL-C, BP, HbA1c) · `modifiable` (acts through a behaviour: smoking, weight, sun) · `descriptive` (informational). **What:** `act_test:lpa`, `act_test:ldl`, `act_test:bp`, `act_test:hba1c`, `act_screen:skin`, `act_behaviour:smoking`, `act_behaviour:weight`. **Who:** `act_who:self` or `act_who:doctor`. **When:** follows from age of action. MIDLIFE loci acting through CVD or smoking are the most actionable; LATE loci (APOE) are descriptive; trade-off loci get no actionability label | Methodology track; mediating trait | `actionability` (closed vocabulary; v2 never uses `actionable`) plus `flags`. Rule for the conclusion text: *the measured value matters more than the genotype* |
| Age of action | `LIFELONG` (roughly constant across adult ages) · `MIDLIFE` (acts mainly on deaths before ~75–80; fades at the oldest ages) · `LATE` (grows with age or appears mainly at the oldest ages) · `AGE_INVERTING` (direction changes with age) · `EARLY_LIFE` · `UNKNOWN`. Confidence: `DIRECT` (significant age moderation) · `DIRECT_WEAK` (age-band estimates, non-significant moderation) · `INFERRED` (from the onset age of the mediating disease) · `UNKNOWN` | Timmers 2019 age bands (fig. 5 source data), Timmers 2020 (−24%/decade non-APOE; APOE ε4 +32%/decade), Joshi 2016 (sex and age), Deelen 2019 (90th vs 99th percentile). Current classes (40 loci, provisional): 18 MIDLIFE, 12 LIFELONG, 4 LATE (APOE ε4, APOE ε2, MC2R, HLA-DRB1\*15:01), 6 UNKNOWN (incl. FOXO3). None AGE_INVERTING | `flags: age:MIDLIFE; ageconf:DIRECT_WEAK`; one `studies.csv` row per age band. Structured `age_min`/`age_max` would need a format change. Caveat: parental-lifespan data censor late effects |
| Outcome profile | Three cells, each `+` / `0` / `−` / `untested`: **healthspan** (years free of major disease; frailty), **lifespan** (parental or own survival), **exceptional survival** (≥90th/≥99th percentile, the nearest human proxy for maximum lifespan) | Filled from the study phenotype classes the locus was tested in. Timmers 2020 tests the same loci on all three. Zenin 2019 pigmentation loci are healthspan-led. Deelen 2019 finds little beyond APOE at the 99th percentile | `flags: outcome:healthspan+; outcome:lifespan+; outcome:extreme:untested`. **"Untested" is never shown as "no effect"** |
| Protection type | `PROTECT:ABSENCE_OF_RISK` (the common non-risk allele at a disease locus, as for most GWAS loci) · `PROTECT:PRESENCE` (a protective allele: APOE ε2, PCSK9 R46L, LPA loss-of-function) · `PROTECT:BUFFERING` (an effect conditional on another genotype, e.g. KL-VS in APOE4 carriers) | Definitions track | `flags`. Buffering needs conditional rules (format request §10) |
| Context | `sex_specific:<m\|f>`, `age_dependent`, `eur_only_evidence`, `ancestry_specific:<pop>` | Study rows | `flags` |
| Animal support | `animal:genage_mouse`, `animal:mouse_qtl`, `animal:worm_rnai` | GenAge models build (2023-10), PMIDs 36173858, 40326784 | `flags`, plus a `studies.csv` row with study_design `model_organism` |
| LD redundancy | `ld_proxy_of:<lead rsid>` | r² to the lead or the credible set | `flags`; proxies are not scored |

### 4.3 What model-organism evidence may and may not do

GenAge's curated mouse lifespan genes overlap **22 of 272 v1 genes** (45 rsIDs) using NCBI orthologues; upper-cased symbol matching gives 20, missing TP53/Trp53 and AGTR1/Agtr1a. With Open Genes the union is 26 genes (51 rsIDs). The 20 symbol matches are AKT1, APOE, ATM, CDKN1A, ERCC2, GHRHR, IGF1R, IRS2, KL, LMNA, MSTN, NFKB1, PPARG, SERPINE1, SIRT1, SIRT6, SOCS2, SOD2, UCP2 and XRCC5. They overlap only **3 of 71 genes at GWAS-era candidate loci** (TERT, APOE, HTT).

Tables: [GenAge cross-reference](data/genage_crossref.csv); [model-organism re-run, 77 rows](evidence/J_model_organisms_model_evidence.csv).

**Allele-level validation is almost absent.** The only knock-in of a human longevity allele with a lifespan endpoint is **PPARG Pro12Ala** (Heikkinen 2009, PMID 19117549). Ala/Ala mice lived longer on chow, but the benefit was lost on a high-fat diet; v1 carries this SNP (rs1801282). The following have cell-level or no in-vivo lifespan data:
- FOXO3 rs2802292;
- the SIRT6 centenarian alleles N308K/A313S (Simon 2022, *EMBO J*, PMID 36215696; cell-level);
- IGF1R A37T/R407H;
- KL-VS knock-ins (conference abstracts only);
- APOE targeted-replacement lifespan studies.

The near-disjointness has a reason. Candidate genes were mostly *chosen because of* worm, fly and mouse results, and that choice did not make them replicate in humans. So:
- **R-ANIMAL-1:** animal support is shown as "supported in animal studies" in the geneticist and researcher layers. It never raises a tier or a weight.
- **R-ANIMAL-2:** prefer unbiased mouse population genetics to single-gene knockouts:
  - Bou Sleiman 2022 (UM-HET3, 3,276 genotyped ITP mice; sex- and age-dependent QTL; Fgd6, Pdk1, Hipk1, Ddost and Hspg2 validated in *C. elegans*);
  - Mullis 2025 (2,444 DO mice, 8 lifespan loci; chr12 locus also seen in UM-HET3/BXD);
  - Di Francesco 2024 (960 DO mice; genetics influenced lifespan more than dietary restriction);
  - Roy 2021 (BXD; diet × genotype).
  
  **FGD6 rs12830425** is the cleanest cross-species bridge: human multivariate healthspan/lifespan locus (PMID 32678081), and late-life lifespan QTL candidate plus worm RNAi lifespan effect (PMID 36173858).
- **R-ANIMAL-3:** knockout direction does not predict common-allele direction. Apoe knockout mice are short-lived, yet human ε2 is the protective allele, so the report never infers a human allele direction from animal data.
- **R-ANIMAL-4:** record direction concordance as `animal_dir:concordant`, `animal_dir:discordant` or `animal_dir:nonmonotone`.
  - Concordant: Igf1r+/- mice (female +33%) and reduced-function IGF1R alleles in female centenarians.
  - Discordant: GHR knockout lengthens mouse life, while human d3-GHR *raises* GH sensitivity and is male-specific.
  - Non-monotone: KL-VS heterozygote advantage in humans vs steady benefit of Klotho overexpression in mice.
  - Mouse effects never go in `effect_size` and never share a `population` with human cohorts.
- **R-ANIMAL-5:** three v1 SNPs are **not the functionally characterised alleles**: KL rs1207362, IGF1R rs2229765 and SIRT6 rs107251. They drop to tier C/D. Replacement candidates, to be verified at curation:
  - KL-VS (rs9536314 + rs9527025) as a haplotype, scored as a heterozygote-specific modifier;
  - the d3-GHR tag rs6873545;
  - BPIFB4 rs2070325.

### 4.4 Legacy LongevityMap layer

- **R-LEGACY-1:** keep v1's 528 rsIDs reachable in the research view, tiered C or D, with `flags: legacy_longevitymap`, `weight` empty and `state: neutral`, unless a row qualifies for A/B on modern evidence (e.g. APOE). Each row carries one study row per original PMID with `stat_significance` as LongevityMap recorded it.
- **R-LEGACY-2:** do **not** re-sync to the full Build 3 (3,144 variants). Of the 2,348 Build 3 rsIDs absent from v1, 2,339 carry only non-significant entries. They add negative evidence for researchers but no findings, so import them only if a researcher view of negative evidence is wanted (decision D6).
- **R-LEGACY-3:** licence. HAGR is CC BY 3.0; `licensing.csv` gets a row with attribution text.

### 4.5 Which definition of "pro-longevity" each row uses

The definitions track compared 11 definition classes (70 title-verified PMIDs; [comparison](evidence/K_definitions_comparison.csv), [synthesis](evidence/K_definitions_age_synthesis.md)). The 2025–2026 approaches are tabulated in the companion research report (`longevitymap_v2_research_report.html`, tab "Defining pro-longevity").

| Role in v2 | Study phenotype classes |
|---|---|
| **Scoring** (can support tier A/B) | `EXTREME_SURVIVAL_CC` (≥90th/99th percentile, centenarians); `PARENTAL_LIFESPAN`; `OWN_SURVIVAL` (Cox in prospective cohorts); `VIABILITY_AF` (allele-frequency change with age, as confirmation only) |
| **Scoring only with a co-occurring lifespan signal** | `HEALTHSPAN`; `MULTIVARIATE_AGEING` (e.g. healthspan + lifespan + longevity factor) |
| **Annotation only** | `FAMILIAL` (LRC, long-lived families); `DISEASE_DEPLETION` (low polygenic disease burden in the long-lived); `RARE_BURDEN` (gene-level loss-of-function); `EVOLUTIONARY` (trade-off, balancing selection, comparative genomics); `MR` (drug-target or mediator proxies); `BIOMARKER` (clock, telomere, proteomic age — these can point the wrong way: TERT raises intrinsic epigenetic age acceleration) |

- **R-DEF-1:** every `studies.csv` row carries its phenotype class, as a controlled prefix in `study_design` until a dedicated column exists.
- **R-DEF-2:** the report states the protection type in words:
  - "the common version of a disease-risk variant" (absence of risk);
  - "a rare protective version" (presence);
  - "matters only together with …" (buffering).
- **R-DEF-3:** no-depletion and other null findings go in `negatives` and as `not_significant` study rows. Examples: similar pathogenic burden in the long-lived (PMID 32860726); APOE and FOXO3 null in Taiwanese and Calabrian cohorts.

---

## 5. How SNPs are organised for the three readers

### 5.1 Report shape (per-variant findings kind, `module-voice`)

1. **Context card.** Always shown; it is the module's description plus a fixed README section. It carries four facts:
   - "Most of how long people live is not explained by known DNA variants. In large studies, the extra risk from an unhealthy lifestyle was three to four times larger than the extra risk from an unfavourable inherited polygenic score."
   - The heritability range and what each estimate measures.
   - "Long-lived people carry many disease-risk variants too."
   - "Nothing here predicts your lifespan."
2. **APOE result.** One named result per diplotype (ε2/ε3/ε4), longevity-framed, with the Alzheimer's implication stated plainly, and the option to skip it (decision D2).
3. **Main findings, grouped by how they act** (§5.2): tiers A and B only, ordered A before B, then by effect size. Each row shows:
   - a plain label;
   - your copies of the longer-life version (0, 1 or 2);
   - the certainty word;
   - what it acts through;
   - **at what age** it mainly acts, e.g. "mainly affects the risk of dying before about 80, through heart disease";
   - **the outcome strip**: healthy years / length of life / reaching very old age (✓, —, or *not studied*);
   - a two-sided "may lower / may raise" line for trade-off loci;
   - an actionability sentence.
4. **Polygenic summary** (pointer): link to the PRS tab for PGS000906, with its development ancestry. Never shown as predicted age.
5. **Biological-ageing markers** (closed by default): telomere length, clocks and mosaic loss of Y, labelled "tendency of a measurable marker", with no direction colour.
6. **Research view** (toggle, closed): tiers C/D, the legacy LongevityMap layer, negative and contradicted evidence, hallmark tags.
7. **More details** fold (geneticist layer): rsID, GRCh38 position, ref/alt, effect allele, zygosity, effect size with measure and CI, p, phenotype class, cohort N and ancestry, fine-mapping C/E levels, callability, PMIDs with quotes.

### 5.2 Primary grouping: mediating system (`category` vocabulary)

The mediating system is the honest primary axis, because most lifespan signal runs through disease. Hallmarks of ageing (PMID 36599349) are kept as a *secondary research tag*, because GO "aging" is obsolete and hallmark annotation of GWAS genes is sparse.

| `category` key | Report heading (plain) | Example lead loci from the seed (tier) |
|---|---|---|
| `heart_vessels` | Heart and blood vessels | LPA rs10455872 (A), LDLR rs142158911 (A), CDKN2B-AS1 rs1556516 (A), CELSR2/SORT1 rs646776 (A), PCSK9 R46L rs11591147 (B) |
| `brain_memory` | Brain and memory | APOE ε2/ε3/ε4 (A) |
| `smoking_lungs` | Smoking and lungs | CHRNA3/5 rs8042849 (A) |
| `immune_inflammation` | Immune system and inflammation | HLA-DQA1/DRB1 rs34967069 (A), SH2B3/ATXN2 rs11065979 (A), MAGI3/PTPN22 rs1230666 (B), IL6 rs2069837 (B, Chinese), IL6R rs2228145 (B) |
| `metabolism` | Blood sugar and weight | TCF7L2 rs35198068 (B), FTO / MC4R (C, MR-inferred) |
| `skin_sun` | Skin and sun damage (healthspan) | IRF4 rs12203592 (B), TYR rs1126809 (B), DEF8 rs4268748 (B) |
| `general_ageing` | Ageing in general (no single disease) | FOXO3 rs1159806 (B; 0 disease credible sets in Open Targets), HTT rs61348208 (B; 0), ZW10/USP28 rs61905747 (A), FGD6 rs12830425 (B). **Category pending curation:** FES/FURIN rs6224 (A; 22 disease credible sets) and KCNK3 rs1275922 (B; 6 sets, modest cardiometabolic) have disease footprints the pleiotropy track's keyword filter did not resolve |
| `ageing_markers` | Markers of biological ageing (not scored) | TERT rs2736100, TERC rs10936599, clock and LOY loci |
| `legacy_candidate` | Earlier candidate-gene studies (research) | the v1 rows |

The tiers in that table are the *seed consensus* and are provisional until curation (§9 step 2).

**R-CAT-1:** `other` is not allowed. **R-CAT-2:** a hallmark tag is optional in `flags` (`hallmark:deregulated_nutrient_sensing`) and is shown only in the research view. No pathway score.

### 5.3 What each reader sees

| Field | Citizen (default) | Geneticist (More details) | Ageing researcher (research view) |
|---|---|---|---|
| Plain label and result in words | ✓ | ✓ | ✓ |
| Copies of longer-life version | ✓ | + genotype letters, zygosity | ✓ |
| Certainty word (tier) | ✓ | + tier letter and reason | + votes and criteria |
| What it acts through; trade-off line | ✓ | ✓ | + full PheWAS list (`negatives`) |
| Actionability sentence | ✓ (preventable/modifiable wording) | ✓ | ✓ |
| Ancestry caveat | ✓ when mismatched | + study ancestries, N | ✓ |
| rsID, position, ref/alt, effect allele, effect size, CI, p | — | ✓ | ✓ |
| Fine-mapping C-level, effector E-level, L2G gene | — | ✓ | ✓ |
| Animal support, hallmark tags | — | ✓ (animal) | ✓ |
| Tier C/D, legacy, negative evidence | — | — | ✓ |

### 5.4 Ancestry handling

- **R-ANC-1:** `population` is filled on every study row.
- **R-ANC-2:** flag `eur_only_evidence` where every supporting cohort is European.
- **R-ANC-3:** show the sentence "Studied mainly in people of European ancestry; it may apply less to you" when the sample's inferred ancestry differs. This is a consumer request (§8), because no consumer infers ancestry for this module today.
- **R-ANC-4:** never score an ancestry-specific locus (IL6 rs2069837, BMPER, BET1L, CLEC3B, the Taiwanese loci) outside its ancestry. Without inferred ancestry, show it in the research view only.

---

## 6. Data model on format 0.7.1

### 6.1 Files

| File | Use in v2 |
|---|---|
| `module_spec.yaml` | name `longevitymap`, version 2.0.0, `genome_build: GRCh38`, `weighting:` declared (§6.6), `license:`, `authorship:` (ai/agent entries for this curation; human reviewers later) |
| `variants.csv` | lead variants of tier A–D loci, **every genotype** per scored locus |
| `studies.csv` | one row per (rsid, study), with effect statistics and a located quote |
| `haplotypes.csv` + `diplotypes.csv` | APOE ε2/ε3/ε4 (decision D2) |
| `pgs.csv` | PGS000906 (Tesi 2021, 330 SNPs, development EUR). Decision D5 covers PGS000318/319, which are mortality scores, not longevity |
| `gwas_effects.csv` | machine-filled by `enrich_gwas_effects` (budget 1 + 2N requests per variant). Never copied into `weight` |
| `licensing.csv` | HAGR (CC BY 3.0); GWAS Catalog; Open Targets; papers quoted |
| `README.md` | catalog card and the More details layer: context facts, rubric, conversion rules, Open Targets release, what is not covered |

### 6.2 `variants.csv`, column by column

| Column | Rule |
|---|---|
| `rsid` | Lead variant only. Proxies are not rows; they are recorded as `ld_proxy_of` on study rows or in the README. **Do not author coordinates**; let `enrich_module` resolve them (a lesson from the off-by-one corpus) |
| `genotype` | **All three genotypes** of each scored locus. The **most common genotype in the reference population is `neutral`**; the others are `protective` or `risk` relative to it (voice rule: compare with the most common version) |
| `state` | `protective` / `risk` / `neutral` as above. Trade-off loci with unresolved net direction: `neutral` on every genotype |
| `direction` | about `effect_allele`: `protective` / `risk` / `contested` (trade-off) / `unknown`. **Harmonise `effect_allele` to the lifespan-increasing allele** so `direction` reads the same across loci |
| `effect_allele`, `effect_size`, `effect_measure` | From the anchor study. Vocabulary: `beta` with unit stated in `studies.statistical_test` (years per allele, parental doubled), `HR`, `OR` (with p90/p99 stated). **Never convert an OR to years** |
| `stat_significance` | `significant` (genome-wide) / `suggestive` / `not_significant` |
| `conclusion` | Per genotype and self-sufficient; voice rules in §7. Identical text for genotypes that mean the same thing |
| `negatives` | **The trade-off sentence** (what the longer-life version may raise). Required where `flags` contains `tradeoff` |
| `gene` | Effector call (L2G/coloc), not the nearest gene. A locus label goes in `phenotype` when the gene is E3/E4 |
| `phenotype` | Plain outcome label, ≤ 6 words, e.g. "Lp(a) and heart disease" |
| `category` | §5.2 vocabulary |
| `trait_efo_id` | The lifespan trait (OBA_VT0005372 life span; EFO_0007796 parental longevity; EFO_0009762 healthspan). The mediator EFO goes in `flags: mediator:EFO_…` until the format allows a second term (§10) |
| `flags` | `tier:X`, `causal:Cn`, `effector:En`, mechanism and pleiotropy tokens (§4.2), context tokens, `ld_proxy_of`, `legacy_longevitymap`, `replication_failed`, `preprint`, `also_in:<module>`, plus the reserved `pleiotropic` and `conditional` |
| `priority` | Derived from tier: A `high`, B `medium`, C/D `low`. This is the sort key if weights are dropped (decision D1) |
| `actionability` | `preventable` / `modifiable` / `descriptive` only |
| `acmg_sf` | `false` on every row |
| `requires_callable` | `false` for common SNPs, because absence is not informative. The consumer must still show *not screened* rather than *neutral* for positions missing from a variant-only VCF (§8) |
| `curator`, `method` | `defaults:` in the spec (`curator: just-dna-seq`, `method: literature-curated, evidence-tiered`) |

### 6.3 `studies.csv`

`pmid` (or `doi` for preprints, plus `flags: preprint` on the variant), `population`, `p_value` and `p_value_num`, `effect_size`, `effect_measure`, `effect_allele`, and `stat_significance` are required on every row supporting a tier A/B variant.

Other columns:
- `study_design` uses a controlled vocabulary: `parental_lifespan_cox`, `own_survival_cox`, `percentile_case_control_p90`, `percentile_case_control_p99`, `centenarian_case_control`, `multivariate_healthspan_lifespan`, `healthspan_cox`, `candidate_gene`, `meta_analysis`, `model_organism`.
- `statistical_test` names the model, the unit and whether the parental estimate was doubled.
- `provenance_quote` is a verbatim sentence or table cell located by the curator (find-evidence `QUOTING.md`); `curator` records who located it.
- Null and contradicting studies are **kept as rows** with `stat_significance: not_significant`.

### 6.4 APOE

The seed carries rs429358 and rs7412 at tier A, and APOE-region proxies rs2075650, rs4420638, rs769449, rs405509 and rs449647.

- **R-APOE-1:** score APOE once, as an ε diplotype from rs429358 + rs7412. All proxies are `ld_proxy_of` and are not scored.
- **R-APOE-2:** longevity-framed conclusions per diplotype use the ≥90th/≥99th-percentile ORs of Deelen 2019 (PMID 31413261) and the parental-lifespan years of Timmers 2019. State the Alzheimer's implication and the age dependence.
- **R-APOE-3:** before committing, confirm that just-dna-lite renders a module with both `variants.csv` and `diplotypes.csv` (decision D2).

### 6.5 `pgs.csv`

PGS000906: `training_ancestry: EUR`, `research_tier: research_only`, `note` stating the effect (HR 0.89 per SD; about 1 year per SD). Never presented as predicted lifespan. The ID must be opened in the PGS Catalog at curation time; a fabricated ID would compile.

### 6.6 `weighting:` (decision D1)

- **Recommended:** `scale: none`, with the note "this module authors no weights; read direction, tier (`flags`) and the polygenic score; weights are deliberately absent so no per-SNP sum is formed." just-dna-lite already falls back to direction for weight-less modules.
- **Alternative:** an ordinal tier scale, A ±0.5 per allele and B ±0.25 per allele, C/D 0, trade-offs 0. Declare it in `weighting:` and the README, and ask the consumer to hide "Net weight" for this module.

---

## 7. Voice requirements (from `module-voice`)

- **R-VOICE-1:** every conclusion opens with the reader's result, e.g. "You carry two copies of the version linked to longer life…". It says what the variant acts through, how big the effect is in words, how common the genotype is (natural frequency for a named population, or *common/uncommon* if not sourced) and how sure the finding is (certainty word = tier), and it ends with the one limit that matters. Expect 50–160 words.
- **R-VOICE-2:** no rsID, p-value, OR or coordinate in a label or conclusion; those belong in the More details fold.
- **R-VOICE-3:** use association wording ("was more common among people who reached very old age"), never "gene for longevity" or "controls ageing". Say *not destiny* when most carriers are unaffected.
- **R-VOICE-4:** preventable rows name who decides: "a standard blood test your doctor can order shows your actual Lp(a) level, which matters more than this DNA result." Never advise starting or stopping a medicine, supplement or diet. Drug-target loci (PCSK9, IL6R, LPA) are not treatment indications.
- **R-VOICE-5:** trade-off loci get a two-sided sentence in `negatives` and no good/bad colour.
- **R-VOICE-6:** before publishing, run two independent reviews (lay reader; scientific reviewer) on the rendered report, and record them in the README and `authorship:` (kind `ai, agent`).

---

## 8. just-dna-lite (consumer) change requests

The user owns this repo, but these need a decision before v2 renders as intended.

1. **Category prose from the module.** `report_logic.py` hardcodes `LONGEVITY_CATEGORIES` (lipids, insulin, antioxidant…) and gates on `mod_name == "longevitymap"`. Either update the dict to the §5.2 keys, or implement the proposed `report: categories:` block (MODULE_REPORT_CONFIG Tier 1).
2. **Suppress "Net weight" and the positive/negative counters** for this module. Show counts by tier instead, plus the context card.
3. **Render `negatives`** as the "may raise" line, and render `flags` tokens as chips (tier, mechanism, context, ancestry, animal support).
4. **Research-view toggle** that reveals tier C/D and legacy rows.
5. **Three-state join display:** "not screened" for a scored locus absent from a variant-only VCF, distinct from the neutral genotype.
6. **Ancestry banner** using the sample's inferred ancestry, if just-prs or another component can provide it.
7. **Cross-link to the PRS tab** for PGS000906.

---

## 9. Build plan (just-module-creator stages)

This is a redesign, so it is entered as a new spec directory at stage 1 (scaffold) under the same name. v1 stays published and immutable.

1. **Scaffold** (`scaffold_module`): spec with `weighting:`, `license:` and `defaults:`; README skeleton with the context facts and rubric.
2. **Curate lead loci** from the seed list: confirm tier per §4.1, pick one lead per locus, and harmonise the lifespan-increasing allele.
   - Start with the 11 tier-A leads, then triage the 82 tier-B leads, many of which are single-study GWAS Catalog hits.
   - The realistic target is **~25–40 scored loci**.
3. **Evidence** (`find-evidence`): for each anchor study, take effect numbers from the paper's own table or supplement (the GWAS Catalog v2 often leaves beta empty), add a verbatim `provenance_quote`, and resolve sign conventions:
   - Timmers: years, positive = longer;
   - Pilling: Martingale, positive = shorter;
   - Zenin: healthspan hazard, positive = worse.
4. **Enrich** (`enrich_module`): resolve coordinates and catch ref mismatches. Strand errors were the dominant v1 repair (30 corrections in the v1 port log).
5. **Enrich GWAS effects and fine-mapping:** `enrich_gwas_effects` (watch the request budget), plus Open Targets credible-set PIP and L2G written as flags, with the release recorded in the README.
6. **Cross-check** (`check_identifiers`, `review_queue`) → **compile** (`validate_module`, `compile_module --strict`) → `verify_artifact`.
7. **Reviews:** lay and scientific, as in R-VOICE-6.
8. **Trial install** on the two public genomes, only on the author's ask (`module-install-local`).
9. **Rehearse on polygon**, then publish on an explicit yes.

---

## 10. Format (just-dna-format) requests

These are notes to file upstream, never commits there; each has an interim workaround in place.

| Request | Why | Interim |
|---|---|---|
| First-class `evidence_tier` column on VariantRow/StudyRow | Tier gates visibility; flags are untyped | `flags: tier:A` plus `priority` |
| `associations` / pleiotropy table (rsid, allele, trait, EFO, benefit/harm, effect, study) | Per-trait trade-offs are data, not prose | `negatives` prose plus `flags: tradeoff` |
| `effect_modifiers` table (rsid, modifier, stratum, effect, pmid) | Smoking, sex, ancestry and APOE4 strata change meaning | `flags: context:…` plus conclusion text |
| Second EFO field for the mediating trait | `trait_efo_id` must stay the lifespan trait | `flags: mediator:EFO_…` |
| `report:` block (categories, group_by, sort_by, weight_display) | Removes the hardcoded longevity gate | consumer change §8.1 |
| Fine-mapping fields (PIP, credible set id, method, release) on gwas_effects | Causal-confidence axis | `flags: causal:Cn` |
| Allele-level HLA representation with tag-SNP fallback | DRB1*15:01, B*57:01 | tag SNPs with `flags: hla_tag, r2:…` |
| `study_phenotype_class` and `evidence_role` (score vs annotate) on StudyRow | The definition of "pro-longevity" decides what a row may do | controlled prefix in `study_design` |
| Age-band fields (`age_min`, `age_max`, `proxy` parent/self) on StudyRow | Age of action is data | one study row per band, described in `statistical_test` |
| Conditional / epistatic rules (effect of A given genotype at B) | Buffering, e.g. KL-VS in APOE4 carriers | `flags: conditional` (reserved) plus conclusion text |
| Model-organism evidence table (gene, species, model type, lifespan effect, sex, diet, direction concordance) | Keeps animal data out of human effect columns | `studies.csv` rows with design `model_organism` plus flags |

---

## 11. Decisions for the module author (each with a recommended default)

| # | Decision | Recommended |
|---|---|---|
| D1 | Weights | `scale: none`; sort by `priority` (§6.6) |
| D2 | APOE ownership | ε diplotype inside v2 with longevity conclusions, `also_in:apoe_epsilon`, subject to the render check in R-APOE-3 |
| D3 | Name and version | Keep `longevitymap` (the consumer keys on the name) at 2.0.0. Change the title to "Longevity genetics" and keep "LongevityMap" credit in the README |
| D4 | Biological-ageing markers | Include as an unscored, closed section, or leave them to a separate "ageing biomarkers" module later |
| D5 | Mortality PGS (PGS000318/319) | Exclude; they are not longevity scores |
| D6 | Legacy layer depth | v1's 528 rsIDs as research-view rows; do not import the further 2,339 non-significant Build 3 entries |
| D7 | Ancestry-specific loci without ancestry inference | Research view only |

---

## 12. Limits of this review

- **Rare-variant and mouse tracks:** on the first model, both were stopped by a content-safety filter. Both were re-run, at the author's request, on Sonnet 5.5 with the original briefs unchanged, and completed. Remaining limits:
  - rare-variant effect sizes come from abstracts or open-access text, and several rsIDs (PCSK9, APOC3, APOE-Christchurch) were taken from dbSNP after checking gene and protein change;
  - no post-2015 replication was found for ADARB1/2, rare IGF1R variants, LLFS/SardiNIA variant-level work or Japanese supercentenarian WGS (preprints only);
  - in the mouse table, the 16 GenAge-only rows lack paper-verified PMIDs, and worm/fly matches are by symbol only;
  - positional synteny of mouse QTL with human loci was not done.
- **Age of action:** no genome-wide age-varying-hazard lifespan GWAS exists. The classes rest on Timmers 2019 age bands (the track's own inverse-variance pooling of father/mother estimates), Timmers 2020 text statements and inference from the mediating disease. Other limits:
  - three loci used unverified LD proxies;
  - allele labels in the source sheet do not always match the seed orientation (CDKN2B-AS1 to be re-checked);
  - seven tier-B loci have no age-stratified data.

  All classes are provisional.
- **Abstract-only reads:** most per-study facts come from abstracts plus GWAS Catalog records. Full texts were read for Deelen 2019, Timmers 2019/2020, Joshi 2017 and the mouse papers. Budovsky 2013 itself was not accessible; LongevityMap's inclusion rules come from the HAGR pages and NAR updates.
- **GWAS Catalog:** six to eight trait IDs, no child-term expansion, so the count of genome-wide-significant rsIDs (121 in one track, 150 in another) is provisional.
- **Preprint harvest:** bioRxiv was listed partially (49,792 of 130,451 records); medRxiv was complete; Europe PMC preprint search covered the rest.
- **Licences:** Open Genes and HALL data licences are unverified because their sites are blocked in the sandbox. They are not needed for v2 unless their content is imported.
- **Seed tiers** are a mechanical consensus of track proposals. Single-track "A" calls (e.g. CELSR2 rs646776, HLA-DQA1 rs34967069) need curator confirmation.

---

## 13. Evidence files from this session

| Track | Synthesis | Evidence table | Variant/locus table |
|---|---|---|---|
| A: LongevityMap and HAGR, v1 audit | [synthesis](evidence/A_longevitymap_hagr_synthesis.md) | [evidence](evidence/A_longevitymap_hagr_evidence.csv) | [candidates](evidence/A_longevitymap_hagr_candidates.csv) |
| B: common-variant GWAS | [synthesis](evidence/B_gwas_synthesis.md) | [evidence](evidence/B_gwas_evidence.csv) | [candidates](evidence/B_gwas_candidates.csv), [GWAS Catalog leads](evidence/B_gwascatalog_gw_leads.csv) |
| D: healthspan, biological age, heritability | [synthesis](evidence/D_healthspan_synthesis.md) | [evidence](evidence/D_healthspan_evidence.csv) | [candidates](evidence/D_healthspan_candidates.csv) |
| E: 2025–2026 preprints and papers | [synthesis](evidence/E_preprints_2025_2026_synthesis.md) | [evidence](evidence/E_preprints_2025_2026_evidence.csv) | [candidates](evidence/E_preprints_2025_2026_candidates.csv) |
| F: reporting to three audiences | [synthesis](evidence/F_reporting_synthesis.md) | [evidence](evidence/F_reporting_evidence.csv) | — |
| G: SNP evaluation methodology | [synthesis](evidence/G_variant_evaluation_synthesis.md) | [evidence](evidence/G_variant_evaluation_evidence.csv) | [locus assessment](evidence/G_variant_evaluation_loci.csv) |
| H: pleiotropy | [synthesis](evidence/H_pleiotropy_synthesis.md) | [evidence](evidence/H_pleiotropy_evidence.csv) | [locus pleiotropy](evidence/H_pleiotropy_loci.csv) |
| I: conceptual and meta-reviews | [synthesis](evidence/I_concepts_synthesis.md) | [evidence](evidence/I_concepts_evidence.csv) | [approaches](evidence/I_concepts_approaches.csv) |
| C: rare and protective variants (Sonnet 5.5 re-run) | [synthesis](evidence/C_rare_protective_synthesis.md) | [evidence](evidence/C_rare_protective_evidence.csv) | [candidates](evidence/C_rare_protective_candidates.csv) |
| J: mouse and model-organism validation (Sonnet 5.5 re-run) | [synthesis](evidence/J_model_organisms_synthesis.md) | [evidence](evidence/J_model_organisms_evidence.csv) | [model evidence](evidence/J_model_organisms_model_evidence.csv) |
| K: definitions of pro-longevity and age of action | [synthesis](evidence/K_definitions_age_synthesis.md) | [evidence](evidence/K_definitions_age_evidence.csv) | [definitions](evidence/K_definitions_comparison.csv), [age of action](evidence/K_age_of_action.csv), [age bands](evidence/K_timmers2019_age_bands.csv) |
| Merged | — | [model-organism evidence](data/genage_crossref.csv) | [seed variants (228 rsIDs / 161 loci)](data/seed_variants.csv) |
