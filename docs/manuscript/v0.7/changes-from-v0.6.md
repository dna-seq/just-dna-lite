# Changes from v0.6 to v0.7

153 segments in NEW, 153 in OLD: 0 new, 0 removed, 52 revised, 2 with new rounds alone (text unchanged); 1 change(s) no segment covers.
Why comes from the co-authors' comments ledger where a row answers a comment; the rest is empty: write it from the record, never as a guess.

| Id | Where | Was | Now | Why |
|---|---|---|---|---|
| (none) | Just-DNA-Lite: a Local-First, Open-Source Platform for Personal Genome … | > **Draft v0.6 (Paper 1 of 2).** … | > **Draft v0.7 (Paper 1 of 2).** … |  |
| C2a | Abstract | … platform annotates a whole-genome VCF and computes polygenic risk … | … platform annotates a whole-genome variant file (VCF) and computes polygenic risk … |  |
| P1 | 1.1 Background and Significance | Researchers and individuals who receive raw variant … | Researchers who receive raw variant … |  |
| C3 | 1.1 Background and Significance | Several companies now offer direct-to-consumer sequencing services … | That raw data can now come from sequencing: several companies offer direct-to-consumer sequencing services … |  |
| R3 | 1.1 Background and Significance | Existing solutions generally belong to two … models from the PGS Catalog, the open database of published polygenic scores, or access to a … | Existing solutions for reading a personal genome generally belong to two … models from the PGS Catalog (the open database of published polygenic scores) or access to a … |  |
| C36a | 1.1 Background and Significance | … models from the PGS Catalog, the open database of published polygenic scores, or access to a … | … models from the PGS Catalog (the open database of published polygenic scores) or access to a … |  |
| R4 | 1.1 Background and Significance | … the genetics of longevity illustrates the need for such extensible annotation tools. After correction for extrinsic … association with longevity, but we found no tool that makes it straightforward to annotate a personal VCF against these databases transparently and extensibly. More broadly, variant-trait associations are published faster than any … team can integrate them, which supports the case for … (9 more words) | … the genetics of longevity shows why annotation tools need to be extensible. After correction for extrinsic … association with longevity, but none of the tools compared in Table S7 documents in full both a local graphical interface and annotation sets added without code. Variant-trait associations are also published faster than any … team can integrate them, so a platform … (8 more words) |  |
| R5 | 1.2 Overview of Just-DNA-Lite | (changed only inside C5) | (changed only inside C5) |  |
| C5 | 1.2 Overview of Just-DNA-Lite | … Supplementary S1 describes Generation I. | … Supplementary S1 describes Generation I, and Figure S1 gives a historical overview of its module domains. |  |
| C6 | 1.2 Overview of Just-DNA-Lite | … this workflow at different points: the main features are listed below, and Box 1 names the … | … this workflow at different points; Box 1 names the … |  |
| F1 | 1.2 Overview of Just-DNA-Lite | … agreement and disagreement are visible (Figure 3). The scoring files, cleaned … times faster than the Generation I workflow, and … a typical polygenic score in under a tenth … 1b, 2 and 3). - **Local.** Annotation and … | … agreement and disagreement are visible. The scoring files, cleaned … times faster than the configured Generation I workflow, and … a typical polygenic score from a prepared genome in under a tenth … 1b, 2 and 3). The links show what each module's curators recorded; whether a module records its sources faithfully was not tested (Section 5.4). - **Local.** … (2 more words) |  |
| F2 | 1.2 Overview of Just-DNA-Lite | … installed on their own computer, after trying the public … | … installed on their own computer from a terminal (Code Availability), after trying the public … |  |
| T1 | 2.1 Annotation Pipeline | … et al., 2025), Polars for columnar processing and … | … et al., 2025), Polars (Vink et al., 2026) for columnar processing and … |  |
| N5 | 2.1 Annotation Pipeline | … file is read with polars-bio, "a Python library that enables fast, parallel and out-of-core operations on large genomic interval datasets" (Wiewiórka et al., 2025). | … file is read with polars-bio (Wiewiórka et al., 2025). |  |
| J19 | 2.1 Annotation Pipeline | … the pipeline performs a streaming join between the … | … the pipeline performs a Polars streaming join between the … |  |
| I2 | 2.1 Annotation Pipeline | The module joins use Polars streaming execution. The optional Ensembl annotation … | The optional Ensembl annotation … |  |
| R8 | 2.2 Annotation Modules as Data | … may accompany the module. This route lets authors prepare annotation content without writing Python code. CSV files are used … | … may accompany the module. CSV files are used … |  |
| C10 | 2.2 Annotation Modules as Data | without writing Python code. CSV files are used … | CSV files are used … |  |
| R10 | 2.3 Web Interface and Self-Exploration | … The web interface is built with Reflex (Reflex, 2026), a Python framework that compiles to React; the whole interface is written in Python. | … The web interface is written entirely in Python with Reflex (Reflex, 2026), a framework that compiles to React. |  |
| N7 | 2.3 Web Interface and Self-Exploration | … hosted demonstration at https://lite.just-dna.life/ provides access using public genomic data only; uploads of private genome files are disabled in this deployment. | … hosted demonstration at https://lite.just-dna.life/ runs on public genomes only; uploads of private genome files are disabled there. |  |
| R11 | 3. Algorithm and Implementation: Annotation Modules and Polygenic … | … et al., 2018; ClinPGx, Whirl-Carrillo et al., 2021), … designed so that other researchers (e.g. bioinformaticians and geneticists) can add their own … | … et al., 2018; ClinPGx, formerly PharmGKB, Whirl-Carrillo et al., 2021), … designed so that other researchers, such as bioinformaticians and geneticists, can add their own … |  |
| C13a | 3. Algorithm and Implementation: Annotation Modules and Polygenic … | … et al., 2018; ClinPGx, Whirl-Carrillo et al., 2021) | … et al., 2018; ClinPGx, formerly PharmGKB, Whirl-Carrillo et al., 2021) |  |
| T2 | 3. Algorithm and Implementation: Annotation Modules and Polygenic … | … drug-response associations (Table 1). These were the linked questions behind Generation I. | … drug-response associations (Table 1). |  |
| J8 | 3.1 Longevity Variants Module (example) | … not a longevity score. The report groups variants … | … not a longevity score. Of the module's 1,022 genotype rows, 975 carry a positive weight and 47 a negative one, so a report's mostly positive counts reflect the module's construction. The report groups variants … |  |
| N9 | 3.1 Longevity Variants Module (example) | … survival during old age. The reader can therefore inspect which studies and populations underlie the annotation. The weight ranks the … diagram reconstructs recorded report fields; the conclusion excerpt is … | … survival during old age. The weight ranks the … diagram reconstructs recorded report fields, with the category and population names reworded for reading; the conclusion excerpt is … |  |
| T3 | 3.1 Longevity Variants Module (example) | … during old age. The reader can therefore inspect which studies and populations underlie the annotation. The weight ranks the curated … | … during old age. The weight ranks the curated … |  |
| F3 | 3.2 Polygenic Risk Scores | **A catalogue that works out of the box.** The scoring files, metadata … release by scoring seven public test genomes with it. … fails a scale check (across the test genomes, a median of at … is also withheld when too few of its variants match … its reference distribution has zero or undefined spread. Section 4.3 … Each computed … (42 more words) | **A prepared catalogue.** The scoring files, metadata … release by scoring seven test genomes with it. … fails a scale check (over the test genomes that fall there, a median of at … is also withheld when fewer than half of its variants match … its reference distribution has undefined spread. Section 4.3 … Each computed score carries one of … (193 more words) |  |
| N10 | 3.2 Polygenic Risk Scores | … the percentile of the most reliable of these models (the one with the highest numeric quality score, which combines reported discrimination, evaluation cohort size and coverage), the number of models, absolute risk (shown only … and the spread of the models' percentiles. The chart places each … and quality label; the ten rows shown are sorted from the highest … (11 more words) | … the percentile of the model the interface calls most reliable (the one ranked first by the numeric quality score of Section 3.2, a rule combining reported discrimination, evaluation cohort size and coverage that has not been validated against measured performance), the number of these models (94; the chart's title counts all 101), absolute risk (shown only … and the … (48 more words) |  |
| J11 | 3.2.1 Standalone PRS Use and MCP Access | … the software through typed tools rather than write their own analysis code. The PRS tools cover … | … the software through typed tools. The PRS tools cover … |  |
| R14 | 3.2.1 Standalone PRS Use and MCP Access | … PGS IDs, variant-match rates, model quality tiers, reference populations, percentiles and … | … PGS IDs, variant-match rates, quality labels, reference populations, percentiles and … |  |
| V14 | 3.2.2 Ancestry Inference | … one of five superpopulations (AFR, AMR, EAS, EUR, SAS), and 53,526 autosomal biallelic … | … one of five superpopulations (AFR 681, AMR 351, EAS 507, EUR 525, SAS 511), and 53,526 autosomal biallelic … |  |
| C18 | 3.3 Additional Trait Annotation Modules | … against the primary literature). Table S4 gives each module's curation and every source it cites. | … against the primary literature). |  |
| DS1 | 3.3 Additional Trait Annotation Modules | These modules work by … | Table S4 gives each module's curation and every source it cites. These modules work by … |  |
| F4 | 3.4 Growing the Module Ecosystem | The registry works like an app store for this content. A researcher claims a namespace … | In the registry, a researcher claims a namespace … |  |
| A3a | 4.1 Annotation Speed | … 181-fold speedup; across the three call sets Generation I … it was 128- to 231-fold (Table 2). Most Generation I runs on the other two call sets were made with the … | … 181-fold speedup; across the two call sets Generation I … it was 128- to 181-fold (Table 2). Most Generation I runs on Livia Zaharia's genome were made with the … |  |
| B22 | 4.1 Annotation Speed | … benchmark in Section 4.2. Three more inputs vary the … 19487816, CC BY 4.0), the HG002 reference sample … study (Poplin et al., 2018), and an earlier, unpublished call set of Anton Kulaga's genome (the 2023 call set), on which the earlier Generation I times were measured (Supplementary S2). The benchmark scripts, the … | … benchmark in Section 4.2. Two more inputs vary the … 19487816, CC BY 4.0), and the HG002 reference sample … study (Poplin et al., 2018). The benchmark scripts, the … |  |
| B24 | 4.1 Annotation Speed | … Generation I, OakVar 2.13.1 with its modules and … on Anton Kulaga's published call set and once on his 2023 call set with the … light use (Generation I on the 2023 call set and on Livia Zaharia's genome), … | … Generation I, OakVar 2.13.1 (Oak Bioinformatics, 2026) with its modules and … on Anton Kulaga's published call set with the … light use (Generation I on Livia Zaharia's genome), … |  |
| C22 | 4.1 Annotation Speed | … standard deviation. For the three genomes Generation I ran … Generation I runs on the 2023 call set and Livia Zaharia's genome were … \| \| **Anton Kulaga, 2023 call set (unpublished)** \| \| \| \| \| \| \| Generation II, warm \| 11 \| 16.2 (16.1–16.4) \| 16.2 ± 0.0 \| 0.1 \| — \| \| Generation II, … (61 more words) | … standard deviation. For the two genomes Generation I ran … Generation I runs on Livia Zaharia's genome were … \| \| **Anton Kulaga, published call set, against … |  |
| A3h | 4.2 PRS Computation | … for DuckDB and Polars alike. Median runtimes (min–max) were … s (0.602–3.51) for PLINK2 (Tables 3 and 4). Of the remaining absolute … | … for DuckDB and Polars alike (Table 4). Median runtimes (min–max) were … s (0.602–3.51) for PLINK2 (Table 3). Of the remaining absolute … |  |
| A3b | 4.2 PRS Computation | The earlier benchmark with just-prs 0.10.1, which … by position alone, is documented in Supplementary S3, so that its results remain traceable to the recorded protocol. | The earlier run with just-prs 0.10.1, which … by position alone, is in Supplementary S3 with its recorded protocol. |  |
| B30 | 4.2 PRS Computation | … the just-prs 0.10.2 rerun. "Excl." excludes the 7 PGS IDs with ≥ 1M variants. The speedup is PLINK2's … divided by the engine's; the median of the per-score ratios is shown beside it. PLINK2 runs as a … *N* scored \| Median (all), s \| Mean (all), s \| Median (excl. 7 with ≥ 1M variants), s \| PLINK2 … (62 more words) | … the just-prs 0.10.2 rerun. The speedup is PLINK2's … divided by the engine's; leaving out the 7 PGS IDs with ≥ 1M variants, or taking the median of the per-score ratios instead, gives the same values to the precision shown. PLINK2 runs as a … *N* scored \| Median (min–max), s \| Mean, s \| PLINK2 median ÷ engine … (41 more words) |  |
| C27 | 4.2 PRS Computation | (text unchanged) | (text unchanged) |  |
| B31 | 4.2 PRS Computation | (text unchanged) | (text unchanged) |  |
| F6 | 4.3 PGS Catalog Coverage | … “cannot be scored” (Table S5). These categories assess scoring-file … matched the reference panel or their reference distribution had zero or undefined spread. The 6,117 scores that … | … “cannot be scored” (Table S5; Figure S5 shows how the weight on unplaceable rows is distributed). These categories assess scoring-file … matched the reference panel (12) or their reference distribution had undefined spread (1). The 6,117 scores that … |  |
| F7 | 4.4 Ancestry Classification | … own superpopulation (2,566 of 2,575); seven of the nine … groups separate within the panel; accuracy on admixed genomes and … | … own superpopulation (2,566 of 2,575; 95% Wilson interval 99.34 to 99.82%); seven of the nine … groups separate within the panel. It is likely an optimistic estimate for the deployed path, which was not tested: that path projects a single VCF with FRAPOSA and codes absent sites as homozygous reference. Accuracy on admixed genomes and … |  |
| R17 | 5.1 Limitations of Variant Annotation | … derived from predominantly European cohorts, so associations may not … | … derived from predominantly European cohorts (Lambert et al., 2021), so associations may not … |  |
| R19 | 5.2 Local Processing and Data Privacy | … other parts of the workflow. Optional AI explanations and MCP clients, for example, require a separate assessment. In an annotation report, … model, to the provider. More generally, when an assistant uses an … | … other parts of the workflow, and the optional AI explanations and MCP clients need a privacy assessment of their own. In an annotation report, … model, to the provider. When an assistant uses an … |  |
| R22 | 5.4 Limitations | (changed only inside C2d) | (changed only inside C2d) |  |
| C2d | 5.4 Limitations | … runtime was measured on four whole-genome call sets from three people, three of the call sets public, and score agreement … | … runtime was measured on three whole-genome call sets from three people, all public, and score agreement … |  |
| R24 | 5.6 Conclusion | … show annotation 128 to 231 times faster than the … run on the same machine and close numerical agreement between scoring engines, on four call sets from three people for annotation and one for scoring. Evaluation across individuals, reference … the findings it reports. Researchers can begin with the public-data demonstration, inspect the sources behind a report, and then … (12 more words) | … show annotation 128 to 181 times faster than the … run on the same machine, on the two call sets Generation I ran on, and close numerical agreement between scoring engines on one genome; Generation II annotation was timed on three call sets from three people. Evaluation across individuals, reference … the findings it reports. Its public demonstration runs … (16 more words) |  |
| A3c | 5.6 Conclusion | show annotation 128 to 231 times faster than the … run on the same machine and close numerical agreement between scoring engines, on four call sets from three people for annotation and one for scoring. | show annotation 128 to 181 times faster than the … run on the same machine, on the two call sets Generation I ran on, and close numerical agreement between scoring engines on one genome; Generation II annotation was timed on three call sets from three people. |  |
| V3 | Data Availability | … (Google, 2020; https://storage.googleapis.com/deepvariant/case-study-outputs/1.0.0/WGS/output/HG002.output.vcf.gz). The 2023 call set of Anton Kulaga's genome (DeepVariant 1.3.0), on which the earlier Generation I times were measured, is not deposited. The annotation modules of Table … the versions the benchmark used (Table S4), and the … the ancestry model (just-dna-seq, 2026c), the reference distributions (just-dna-seq, 2026d) and the Ensembl Variation … rerun reported in … (6 more words) | … (Google, 2020; https://storage.googleapis.com/deepvariant/case-study-outputs/1.0.0/WGS/output/HG002.output.vcf.gz). The annotation modules of Table … the versions the benchmark downloaded from the registry and checked by digest (Table S4), and the … the ancestry model (just-dna-seq, 2026c; revision db1a17c of 27 September 2026), the reference distributions (just-dna-seq, 2026d; revision 5570095 of 2 September 2026) and the Ensembl Variation … rerun reported in Section 4.2, made … (17 more words) |  |
| V4 | Ethics Statement | … open licence (see Data Availability); Anton Kulaga's genome is also analysed in an earlier, unpublished call set. Each consents to the … | … open licence (see Data Availability). Each consents to the … |  |
| RC5b | Bibliography | … Biology*, 17, 122. https://doi.org/10.1186/s13059-016-0974-4 Pagel, K. A., et … | … Biology*, 17, 122. https://doi.org/10.1186/s13059-016-0974-4 Oak Bioinformatics (2026). OakVar, version 2.13.1 [software]. https://github.com/rkimoakbioinformatics/oakvar Pagel, K. A., et … |  |
| I11 | Bibliography | … Medicine*, 20(12), 1515–1521. https://doi.org/10.1038/gim.2018.38 | … Medicine*, 20(12), 1515–1521. https://doi.org/10.1038/gim.2018.38 Vink, R., et al. (2026). pola-rs/polars [software]. Zenodo. https://doi.org/10.5281/zenodo.7697217 |  |

## The record behind each row

For whoever writes Why, not for co-authors. Lines are in the marked masters.
- (none): unmarked, line 3 → 3; no segment covers it.
- C2a: revised, line 28 → 28; rounds 14 → 15; new rounds by claude:2026-10-28.
- P1: revised, line 44 → 44; rounds 2 → 3; new rounds by claude:2026-10-28.
- C3: revised, line 51 → 51; rounds 7 → 8; new rounds by claude:2026-10-28.
- R3: revised, line 54 → 54; rounds 5 → 6; new rounds by claude:2026-10-28.
- C36a: revised, line 55 → 55; rounds 4 → 5; new rounds by claude:2026-10-28.
- R4: revised, line 58 → 58; rounds 7 → 12; new rounds by claude:2026-10-28 (×5).
- R5: revised, line 71 → 71; rounds 2 → 2; changed only inside C5.
- C5: revised, line 72 → 72; rounds 6 → 7; new rounds by claude:2026-10-28.
- C6: revised, line 77 → 77; rounds 7 → 9; new rounds by claude:2026-10-28 (×2).
- F1: revised, line 81 → 81; rounds 5 → 6; new rounds by claude:2026-10-28.
- F2: revised, line 92 → 92; rounds 3 → 4; new rounds by claude:2026-10-28.
- T1: revised, line 112 → 112; rounds 3 → 4; new rounds by claude:2026-10-28.
- N5: revised, line 120 → 120; rounds 2 → 4; new rounds by claude:2026-10-28 (×2).
- J19: revised, line 124 → 124; rounds 6 → 7; new rounds by claude:2026-10-28.
- I2: revised, line 124 → 124; rounds 1 → 2; new rounds by claude:2026-10-28.
- R8: revised, line 140 → 140; rounds 2 → 3; new rounds by claude:2026-10-28.
- C10: revised, line 141 → 141; rounds 2 → 3; new rounds by claude:2026-10-28.
- R10: revised, line 154 → 154; rounds 7 → 8; new rounds by claude:2026-10-28.
- N7: revised, line 158 → 158; rounds 1 → 2; new rounds by claude:2026-10-28.
- R11: revised, line 170 → 170; rounds 2 → 3; new rounds by claude:2026-10-28.
- C13a: revised, line 171 → 171; rounds 3 → 4; new rounds by claude:2026-10-28.
- T2: revised, line 178 → 178; rounds 2 → 4; new rounds by claude:2026-10-28 (×2).
- J8: revised, line 205 → 205; rounds 9 → 10; new rounds by claude:2026-10-28.
- N9: revised, line 209 → 209; rounds 5 → 6; new rounds by claude:2026-10-28.
- T3: revised, line 210 → 210; rounds 5 → 6; new rounds by claude:2026-10-28.
- F3: revised, line 229 → 229; rounds 7 → 12; new rounds by claude:2026-10-28 (×5).
- N10: revised, line 248 → 248; rounds 8 → 14; new rounds by claude:2026-10-28 (×6).
- J11: revised, line 260 → 260; rounds 2 → 3; new rounds by claude:2026-10-28.
- R14: revised, line 264 → 264; rounds 5 → 6; new rounds by claude:2026-10-28.
- V14: revised, line 274 → 274; rounds 6 → 7; new rounds by claude:2026-10-28.
- C18: revised, line 280 → 280; rounds 5 → 6; new rounds by claude:2026-10-28.
- DS1: revised, line 281 → 281; rounds 1 → 2; new rounds by claude:2026-10-28.
- F4: revised, line 289 → 289; rounds 4 → 5; new rounds by claude:2026-10-28.
- A3a: revised, line 301 → 301; rounds 12 → 13; new rounds by claude:2026-10-28.
- B22: revised, line 307 → 307; rounds 7 → 8; new rounds by claude:2026-10-28.
- B24: revised, line 311 → 311; rounds 5 → 6; new rounds by claude:2026-10-28.
- C22: revised, line 315 → 315; rounds 6 → 7; new rounds by claude:2026-10-28.
- A3h: revised, line 354 → 349; rounds 4 → 5; new rounds by claude:2026-10-28.
- A3b: revised, line 358 → 353; rounds 6 → 8; new rounds by claude:2026-10-28 (×2).
- B30: revised, line 362 → 357; rounds 4 → 5; new rounds by claude:2026-10-28.
- C27: rounds, line 382 → 377; rounds 8 → 10; new rounds by claude:2026-10-28 (×2).
- B31: rounds, line 386 → 381; rounds 9 → 11; new rounds by claude:2026-10-28 (×2).
- F6: revised, line 394 → 389; rounds 1 → 2; new rounds by claude:2026-10-28.
- F7: revised, line 402 → 397; rounds 1 → 4; new rounds by claude:2026-10-28 (×3).
- R17: revised, line 417 → 412; rounds 6 → 7; new rounds by claude:2026-10-28.
- R19: revised, line 427 → 422; rounds 6 → 7; new rounds by claude:2026-10-28.
- R22: revised, line 443 → 438; rounds 10 → 10; changed only inside C2d.
- C2d: revised, line 444 → 439; rounds 5 → 6; new rounds by claude:2026-10-28.
- R24: revised, line 455 → 450; rounds 8 → 12; new rounds by claude:2026-10-28 (×4).
- A3c: revised, line 456 → 451; rounds 9 → 11; new rounds by claude:2026-10-28 (×2).
- V3: revised, line 501 → 496; rounds 7 → 9; new rounds by claude:2026-10-28 (×2).
- V4: revised, line 511 → 506; rounds 4 → 5; new rounds by claude:2026-10-28.
- RC5b: revised, line 600 → 595; rounds 1 → 2; new rounds by claude:2026-10-28.
- I11: revised, line 622 → 619; rounds 1 → 2; new rounds by claude:2026-10-28.
