# Supplementary Table S14. The expert-curated trait modules in three states: Generation I, Just-DNA-Lite v1.1.0 and the proposed Generation II

This table follows four modules curated by hand in Generation I (O. Borysova) through three states:

1. **Generation I.** The original OakVar module databases (`dna-seq/just_coronary`, `just_lipidmetabolism`,
   `just_vo2max`, `just_thrombophilia`; SHA-256 as recorded in each build log). These are the modules users of the
   Generation I platform received.
2. **Just-DNA-Lite v1.1.0.** The same content converted to the current module format and published on 2026-09-26
   (registry namespace `just-dna-seq`; identical copies on the Hugging Face mirror and in a local install). The
   conversion corrected errors only through tracked, evidence-backed override files
   (`v1_port/data/curation/<module>.csv`, commit 6f79855). All 22 weight and conclusion overrides were confirmed present
   in all three copies.
3. **Proposed Generation II (v2.0.0).** The 2026 rebuild. It keeps every v1.1.0 row, corrects the errors listed here and adds every
   independent genome-wide-significant lead of the largest 2021–2026 GWAS of each trait plus functional variants. Each
   variant carries an evidence tier. It has been rehearsed on the test registry and is not yet published.

Every finding is listed in `S14_generation1_module_audit.csv`.

## How the content was checked
1. **Corrections made during the Generation I → II conversion ("port").** Each Generation I module (an OakVar SQLite
   file from the `dna-seq/just_<module>` repositories; SHA-256 in each build log) was converted to the current module
   format by `just-dna-pipelines/src/just_dna_pipelines/v1_port/`, giving the published v1.1.0. The converter copies
   authored cells verbatim. Errors were fixed only through tracked override files
   (`v1_port/data/curation/<module>.csv`, commit 6f79855, 2026-08-19), each giving the new value and its evidence,
   checked against the module's own cited study, its own prose and the EBI GWAS Catalog. Every applied override is
   reported in the module's `v1_port.log`, from which these counts are taken. "Corrected at port" therefore means
   present in Generation I and absent from v1.1.0; "still in v1.1.0" means present in the published version today.
2. **Manual reading of every genotype row** of v1.1.0 (189 rows in the four modules) on 2026-11-03. The reading was
   supported by automated checks: weight sign against `state`, the genotype each conclusion makes a claim about against
   the row's own genotype (order- and strand-insensitive), conclusions shared by differently weighted genotypes, and
   loci with no zero-weight genotype.
3. **Comparison with current GWAS.** For every single-nucleotide variant with genome-wide-significant (p < 5×10⁻⁸)
   associations for the module's trait in the GWAS Catalog (REST v2, retrieved 2026-11-03), the allele the module
   scores as risk was compared with the risk allele those publications report. Strand-ambiguous A/T and C/G SNPs were
   excluded.

**Error** means the content is wrong on its own terms: a sign opposite to the cited study or the row's own text, a
conclusion that names another genotype, a conclusion that contradicts its weight, a wrong citation or transcription,
or a genotype that cannot exist. **Outdated** means the content matched the evidence available when it was curated
in Generation I (repositories last updated by May 2023, Table S2) but later and larger studies no longer support it. **Notes** are design choices worth knowing that
are not errors.

## Comparison

| Module | Measure | Generation I | Just-DNA-Lite v1.1.0 (current) | Proposed Generation II v2.0.0 |
|---|---|---|---|---|
| **Coronary Artery Disease** | Variants | 27 | 27 | 342 (315 new) |
| | Genotype rows | 81 | 81 | 1026 |
| | Genes | 22 | 22 | 283 |
| | Cited papers (PMIDs) | 59 | 59 | 63 |
| | Variants with an error (findings) | 12 (21) | 8 (8) | 0 (0): the 8 corrected, each with a recorded reason; none found in new rows by the internal checks |
| | Risk allele agrees with current GWAS | 11 of 15 | 15 of 16 | legacy 15 of 16; new rows 29 of 29 sampled |
| | Outdated legacy variants (no GWS support or contradicted) | 9 | 9 | 9, labelled by tier |
| | Evidence tiers S / A / B / C / D | none | none | 4 / 120 / 209 / 8 / 1 |
| **Lipid Metabolism** | Variants | 15 (+1 listed without genotypes) | 15 | 1062 (1047 new) |
| | Genotype rows | 45 | 45 | 3186 |
| | Genes | 13 | 12 | 854 |
| | Cited papers (PMIDs) | 39 | 37 | 45 |
| | Variants with an error (findings) | 4 (10) | 1 (1) | 0 (0): the 1 corrected, each with a recorded reason; none found in new rows by the internal checks |
| | Risk allele agrees with current GWAS | 11 of 12 | 12 of 12 | legacy 12 of 12; new rows 24 of 24 sampled |
| | Outdated legacy variants (no GWS support or contradicted) | 8 | 8 | 8, labelled by tier |
| | Evidence tiers S / A / B / C / D | none | none | 10 / 341 / 711 / 0 / 0 |
| **VO2 Max** | Variants | 13 | 13 | 152 (139 new) |
| | Genotype rows | 39 | 39 | 456 |
| | Genes | 12 | 12 | 132 |
| | Cited papers (PMIDs) | 7 | 7 | 12 |
| | Variants with an error (findings) | 1 (1) | 0 (0) | 0 (0); none found in new rows by the internal checks |
| | Risk allele agrees with current GWAS | not checkable | not checkable | legacy not checkable; new instrument rows 137 of 137 match the source table |
| | Outdated legacy variants (no GWS support or contradicted) | 13 | 13 | 13, labelled by tier |
| | Evidence tiers S / A / B / C / D | none | none | 0 / 3 / 11 / 137 / 1 |
| **Thrombophilia** | Variants | 9 | 8 | 223 (215 new) |
| | Genotype rows | 29 | 24 | 597 |
| | Genes | 8 | 8 | 146 |
| | Cited papers (PMIDs) | 25 | 24 | 31 |
| | Variants with an error (findings) | 6 (9) | 5 (6) | 0 (0): the 6 corrected, each with a recorded reason; none found in new rows by the internal checks |
| | Risk allele agrees with current GWAS | 4 of 4 | 4 of 4 | legacy 4 of 4; new rows 10 of 10 sampled |
| | Outdated legacy variants (no GWS support or contradicted) | 4 | 4 | 4, labelled by tier |
| | Evidence tiers S / A / B / C / D | none | none | 75 / 20 / 124 / 1 / 3 |
| **All four** | Variants | 64 | 63 | 1779 |
| | Genotype rows | 194 | 189 | 5265 |
| | Variants with an error (findings) | 23 (41) | 14 (15) | 0 (0): all 15 corrected; none found in new rows by the internal checks |
| | Risk allele agrees with current GWAS | 26 of 31 | 31 of 32 | legacy 31 of 32; new rows 63 of 63 sampled, VO2 Max 137 of 137 |
| | Outdated legacy variants | 34 | 34 | 34, labelled by tier |
| | Evidence tiers S / A / B / C / D | none | none | 89 / 484 / 1055 / 146 / 5 |

"Risk allele agrees" counts the checkable single-nucleotide variants, excluding strand-ambiguous ones. In Generation I
the risk allele was inverted at 5 checkable variants: 9p21 rs4977574, LPA rs3798220, MTHFD1L rs6922269, APOB rs515135 and
SORT1 rs12740374. The conversion fixed all but APOB rs515135, whose direction 2022 GWAS contradict. One more coronary
variant (rs11206510) becomes checkable in v1.1.0 because the conversion gave its risk homozygote a weight. For
Generation II new rows, all 1,716 new variants passed the internal checks (sign, additivity, zero baseline). A random
sample was compared trait-matched with the GWAS Catalog; VO2 Max new rows were checked against the source study's
table (Cai et al. 2023, PMID 37400433).

In Generation II the 15 findings still present in v1.1.0 are corrected (24 cell edits on 17 genotype rows). Each correction changes only the wrong cell and is recorded in the module's `provenance.json` and `logs/authoring.log`, with the source it was checked against. The corrections were made under the maintainer's decision and still need confirmation by the original curator. The `main`-branch compiler's own check for conclusions written for another genotype (RM279, just-dna-compiler commit a665df2) independently flags 4 of these rows in v1.1.0 and none in v2.0.0.

## Findings by category

| Category | Generation I | v1.1.0 | Proposed Generation II |
|---|---|---|---|
| E1 risk direction inverted (weight sign) | 13 | 0 | 0 |
| E2 conclusion names the wrong genotype or direction | 13 | 4 | 0 |
| E3 conclusion contradicts the row's weight | 4 | 4 | 0 |
| E4 citation or transcription error | 5 | 3 | 0 |
| E5 genotype not representable | 2 | 0 | 0 |
| E6 weight inconsistent with the cited estimate | 4 | 4 | 0 |
| N1 one p-value given beside several papers | 3 | 0 | 0 |
| N2 gene symbol not current | 6 | 1 | 1 |
| N3 no zero (reference) genotype | 9 | 9 | 7 |
| N4 one conclusion shared by differently weighted genotypes | 12 | 12 | 12 |
| N5 conclusions are bare labels | 1 | 1 | 1 |
| O1 direction contradicted by current GWAS | 1 | 1 | 1 (labelled by tier) |
| O2 no genome-wide-significant support for the trait | 22 | 22 | 22 (labelled by tier) |
| O3 candidate-gene claim not supported by large GWAS | 3 | 3 | 3 (labelled by tier) |
| O4 HDL-raising allele scored protective | 5 | 5 | 5 (labelled by tier) |
| O5 claim outside the module's subject | 2 | 2 | 2 (labelled by tier) |

## Examples present in v1.1.0 (corrected in v2.0.0)
- **Conclusion names another genotype** (thrombophilia): the prothrombin G20210A homozygote row (rs1799963 A/A) says
  "GA carriers have 6.74x risk". The fibrinogen rs1800790 A/A row says "GA variant". The ABO rs2519093 C/T row says
  "TT genotype". The factor V Leiden homozygote row (rs6025 T/T) opens with the C/C sentence "CC genotype is NOT
  associated with increased risk".
- **Conclusion contradicts its weight**: the 9p21 rs4977574 G/G row is scored risk (−1.54), but its text says "Your
  genotype GG does not contain the risk". SERPINE1 rs1799889 G/G is scored risk while its text says the risk "is not
  increased". FURIN rs17514846 rows describe increased risk while every genotype has weight 0.
- **Weights not following the cited estimate**: rs7250581 and rs688034 are scored as risk on estimates whose
  confidence intervals include 1 (OR 1.06, 0.79–1.43; OR 1.11, 0.98–1.25). rs17228212 and rs11206510 give the
  heterozygote the same weight as the homozygote.
- **Text errors**: the CNNM2 rs12413409 rows quote an aspirin-trial result for a different SNP (rs7692387). The
  APOE rs429358 C/T conclusion stops mid-sentence.
- **Outdated**: 22 legacy variants have no genome-wide-significant association with their trait (all 13 VO2 Max
  training-response SNPs, 8 coronary and 1 thrombophilia). MTHFR C677T, SERPINE1 4G/5G and ITGB3 PlA1/A2 are not
  venous-thromboembolism loci in the 81,190-case GWAS of Ghouse et al. 2023 (PMID 36658437). Five lipid variants score
  the HDL-raising allele as protective, although Mendelian randomisation indicates HDL cholesterol is not causal for coronary disease (Voight et al. 2012, PMID 22607825).

## Limitations
- The manual reading was done by an AI agent and needs confirmation by a human curator before these numbers are
  published. The categories are judgements; the CSV gives the evidence for each.
- Superhuman (74 variants) was audited only through its port log. Its separate curation passes (commits c9b55ca and 087f9c2, 2026-09-27, towards a version 2.5.0 not on the production registry, whose latest is 2.4.0) are not counted here. That log records 27 rsIDs at multi-allelic loci with
  no allele named, 2 duplicate rows, one outdated gene symbol, and 1,141 unnamed dbSNP variants kept out of the module.
  Its v2.4.0 rows make no genotype-specific claims and carry no weights, so the row checks above do not apply. Its text
  was not assessed at this depth.
- VO2 Max direction could not be compared, because no genome-wide-significant fitness association exists for its SNPs.
- GWAS Catalog publications can share cohorts, so agreement here means "reported again", not independent replication.
- The 22 coronary, 1 lipid and 6 VO2 Max entries where one p-value stands beside several papers are noted (N1), not
  counted as errors.
