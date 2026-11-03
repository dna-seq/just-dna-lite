# Track J: validation of human longevity loci in mice and other model organisms

All PMIDs below were resolved to titles through PubMed E-utilities on 2026-11-03. Key points come from abstracts unless noted. Counts for v1 are computed from the supplied `variants.csv` (272 genes, 528 rsIDs).

## 1. Main finding

Almost no human longevity allele has been tested as an allele in a mouse with a lifespan readout. Mouse lifespan evidence is overwhelmingly gene-level (knockout, hypomorph, transgene), and for several loci its direction is opposite to, or not comparable with, the human allele.

| Locus | Closest in-vivo evidence | Allele-specific test? | Direction vs human |
|---|---|---|---|
| PPARG Pro12Ala (rs1801282, in v1) | Ala/Ala knock-in lived longer on chow; benefit lost on high-fat diet (19117549) | Yes, only true knock-in with lifespan | Plausibly concordant; gene-by-diet dependent |
| IGF1R | Igf1r+/- lived 26% longer overall; females +33%, males +16% (ns) (12483226); smaller on C57BL/6J (23898955) | Human A37T/R407H tested in MEFs only (21388493); no knock-in | Concordant; female bias matches female-centenarian enrichment (18316725) |
| GHR | GHR-/- lifespan extension (12933651, 10875265); adult-onset knockout extends maximal lifespan in females only (27732088) | Ghrd3 mouse exists, no lifespan (34559564) | Opposite: d3-GHR raises GH sensitivity and is male-specific in humans (28630896) |
| KL (KL-VS) | kl mutant short-lived (9363890); transgenic overexpression extends lifespan (16123266, 41916755) | Humanised KL variants in B6 mice exist, conference abstracts only, transcriptomics, no lifespan | Unclear: humans show heterozygote advantage but homozygote disadvantage (15677572) |
| SIRT6 | Transgenic overexpression: males only (22367546); both sexes (34050173) | Centenarian allele studied in cells/hESC (36215696, 42370242 preprint); no mouse | Unclear: allele has weaker deacetylase, stronger mono-ADP-ribosylation |
| FOXO3 | Foxo3 needed for dietary-restriction benefit (25808402) | rs2802292 and rs12206094/rs4946935 enhancer assays and isogenic HAP1 cells only (29733381, 29234056) | Cell-level concordant; no mouse test found |
| APOE | Targeted-replacement mice show lipid, vascular and brain-metabolome phenotypes (9218423, 18755411, 40898377, 42103698) | Yes (allele-specific), but no lifespan study found | Healthspan markers favour E2 over E4; lifespan untested |
| CETP | Transgenic expression is pro-atherogenic (8316302, 16946130) but protective in ovariectomised LDLR-KO mice (12518020) | Mouse is a non-expressing host; no I405V model | Unclear; sign depends on background |
| APOC3, PCSK9, ANGPTL3 | Knockouts have lipid phenotypes (15805190, 11788823); human loss-of-function lowers CVD risk (24941082, 16554528, 28538136) | No lifespan data found | Not model-validated for longevity |
| BPIFB4 (rs2070325) | AAV transfer of LAV allele delays frailty and senescence in old mice (31461407, 35087020) | Allele-contrast gene transfer, not knock-in; lifespan not reported | Concordant (healthspan) |
| mTOR/S6K1, TERT, CDKN2A/B, ADARB1/2 | S6K1 KO and mTOR hypomorph extend lifespan (19797661, 23994476); AAV-Tert +24%/+13% median (22585399); Ink4/Arf extra copies extend median longevity (19239418); worm adr-1/adr-2 loss halves median survival (20011587) | None | Only CDKN2B (rs1063192) and ADARB1/2 are in v1; MTOR, RPS6KB1, TERT, CDKN2A are absent |

No knock-in of a human longevity regulatory variant (FOXO3, KL-VS, IGF1R, SIRT6) with a lifespan endpoint was found in 2020-2026 PubMed/Europe PMC searches (search coverage is limited, so treat as provisional). The Hernández-Arciga 2025 IR/IGF1R knock-in (41217825) is derived from a Drosophila substitution, not a human allele, and reports no lifespan.

## 2. Unbiased mouse genetics (reported at abstract or text level)

- UM-HET3 (36173858): one sex-independent Chr12 QTL, female Chr3 and male Chr2/Chr10 QTLs, several visible only in older animals. Candidates Hipk1, Ddost, Hspg2, Fgd6 and Pdk1 were validated in C. elegans. The task mentioned Vezf1; I found no Vezf1 in the full text. A candidate named Vezt appears among top-scoring genes for late male QTLs, so the name may have been mis-transcribed.
- Diversity Outbred (40326784): 8 lifespan loci across 2,444 mice; one sex-dependent, one diet-specific. Cdkn2b emerges as a DO candidate for an aortic phenotype (41758904).
- Nature 2026 (42020758): 29 Vita loci with age- and sex-specific effects whose polarity often inverts with age; effects stronger in males. Besides the gene-ranking resource of 36173858, this is the only explicit mouse-to-human test I found: APEH is supported by human parental-longevity GWAS (BH -log P 3.7 for paternal age at death), whereas four Vita1a candidates showed no significant Mendelian-randomisation effect.
- BXD and inbred panels: lifespan QTLs (20305363), HFD shortens lifespan 12% (34552269), IGF1 level tracks lifespan across 31 inbred strains (19627267, 22566614).
- None of Hipk1, Ddost, Hspg2, Fgd6, Pdk1 or APEH is a v1 gene. Mouse QTL loci therefore add new candidate loci rather than validating v1 SNPs. Systematic positional synteny with human GWAS loci was not performed; only the APEH comparison above was found.

## 3. Cross-species cross-reference of v1

Methods: GenAge Build 21 `genage_models.csv` joined to v1 genes through NCBI mouse-human orthologues (plus Agtr1a to AGTR1 added manually), and the Open Genes API (2,405 genes, queried 2026-11-03) matched by exact symbol.

- GenAge mouse lifespan entries: **22 of 272 v1 genes (8.1%), covering 45 of 528 rsIDs (8.5%)**. Symbol matching alone gave 20; TP53 (Trp53) and AGTR1 (Agtr1a) were missed. Effects: 9 increase, 8 decrease, 5 increase-and-decrease. GenAge detail pages did not expose primary PMIDs in my scrape, so GenAge-only rows in the CSV are not paper-verified.
- Open Genes: 113 v1 genes present; **23 carry mammalian lifespan evidence (47 rsIDs)**. Union with GenAge mouse: **26 genes (51 rsIDs)**. Open Genes adds HSPA1A, NR3C1, SIRT3, UCP1; GenAge adds ATM, CDKN1A, SERPINE1.
- Any model-organism entry (GenAge other organisms by symbol, Open Genes non-mammalian): 34 genes. This figure is provisional because symbol matching for worm, fly and yeast was not orthologue-aware (the NCBI ortholog file lacked these taxa against human in my filter).
- The v1 variants at the best-validated loci are not the validated alleles: KL is rs1207362 (not KL-VS), IGF1R is rs2229765 (not A37T/R407H), SIRT6 is rs107251 (not N308K/A313S).

## 4. Translatability caveats

1. Lab-mouse lifespan magnitudes (e.g. +33% in Igf1r+/- females) are not transferable to humans; Igf1r penetrance already differs between 129/SvPas and C57BL/6J (23898955).
2. Knockouts and transgenes alter dosage grossly; human longevity variants are typically common regulatory or hypomorphic changes (FOXO3 enhancers) with small effects. Deletion of the 9p21 orthologous interval raises mortality (20173736) without being an allele swap.
3. Sex pattern is not conserved: mouse effects are female-biased for Igf1r and adult-onset Ghr knockout, male-biased for Sirt6 (2012), while d3-GHR is male-specific in humans. Mouse QTLs are largely sex-specific.
4. Context dependence: Pro12Ala benefit disappears on high-fat diet; CETP changes sign with background; humanised APOE3 mice show exaggerated atherosclerosis.
5. Mouse-human comparisons can be fragile (23401516 versus the re-analysis 25092317).

## Implications for longevitymap v2 requirements

1. **Gene-level model evidence as a separate layer.** Store GenAge/Open Genes-style evidence (organism, manipulation, lifespan effect, sex, PMID) as a new optional gene-level table, e.g. `model_evidence.csv`, using the columns of the CSV delivered here; this needs a format change. Interim: add a `flags` token such as `mouse_lifespan_gene` and a README note. Report: a "Model-organism evidence" badge per gene, visually separate from variant evidence, stating that it is gene-level, not allele-level.
2. **Validation tier per variant.** Tier 0 gene-level only; tier 1 allele-specific in cells (FOXO3 rs2802292, SIRT6, IGF1R); tier 2 allele-specific in vivo (PPARG rs1801282; KL-VS humanised mice, lifespan pending). Interim: put the tier text in `studies.csv` `study_design` and a `flags` token; filtering and sorting need a new column. Report: show the tier next to each conclusion.
3. **Direction concordance flag.** Mark discordant loci (GHR/d3-GHR) and non-monotone loci (KL-VS) with a `flags` token and explain in `conclusion`. Existing `direction` and per-genotype `weight`/`state` rows can carry the KL-VS pattern (heterozygote favourable, homozygote unfavourable). Report: an amber caution line, "mouse knockout extends lifespan; human allele increases function".
4. **Sex specificity.** Record sex of the effect in `studies.csv` (population column can state "male-specific"), but a structured `sex` column is needed for filtering. Report: show sex-limited effects explicitly and do not apply them to the other sex without a note.
5. **Context fields.** Gene-by-diet and strain background (Pro12Ala, Igf1r) go in `conclusion` and README now; a structured `context` column would need a format change. Report: a one-line "depends on" note.
6. **Do not label v1 proxies as validated.** Relabel v1 KL rs1207362, IGF1R rs2229765 and SIRT6 rs107251 in `conclusion` as "not the functionally characterised allele". Candidate new rows: KL-VS (rs9536314, rs9527025, to be defined in the haplotypes table as a linked haplotype), BPIFB4 rs2070325, d3-GHR tag rs6873545. Before adding SIRT6 N308K/A313S and IGF1R A37T/R407H, resolve their rsIDs from dbSNP; I could not verify them. Report: show haplotype-level calls, not single SNPs.
7. **Species column in provenance.** Mouse or worm rows must not share `population` with human cohorts. A `species`/`model` column in `studies.csv` is needed (format change); until then write the model in `study_design` and never put mouse effect sizes in `effect_size`.
8. **Candidate loci from unbiased mouse genetics** (APEH, Hipk1, Pdk1 and others) go through `gwas_effects` or a PGS pointer after human lookup, not into variants.csv by mouse evidence alone. Report: none unless a human association exists.
9. **Lipid genes without lifespan data** (APOC3, PCSK9, ANGPTL3): describe evidence as cardiometabolic, not longevity-validated; use `category` = lipids and a `flags` token.
10. **Standing disclaimer** in README and report footer: mouse lifespan evidence supports mechanism plausibility and priority, not individual prediction.
