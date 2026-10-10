# Supplementary Table S4. Module sources

Registry state at 2026-10-10 18:00 UTC, https://module-registry.just-dna.life, namespace `just-dna-seq` (registry 0.27.0, module format 0.7.1). The registry is a live catalogue: modules published or versioned after this time are not described here, and later versions of these modules may differ. Each published version is immutable, so the version and artifact digest below identify exactly the artifact this table was read from.

Every value is read from the module's own published files: `manifest.json` (identity, curator, method, publication time, digest), `sources.parquet` (the source databases, with their release where the build recorded one), `studies.parquet` and the lead table (the PubMed IDs each row cites), `literature.parquet` (the DOI PubMed gives for each PMID) and the build log shipped with the module. First author and year come from PubMed (esummary) and are given for the literature-curated modules. For the database-derived modules the curated source is the database release; the papers that database links to are counted here and listed in `S4_module_citations.csv`.

Curator types: **Expert**, the manifest states method `expert-curated` (literature modules curated by hand in Generation I and ported to the current format); **Database-derived**, the licence sidecar names a database feeding the annotation layer, and the rows were drafted mechanically from that release. Ensembl and ClinVar entries on the *resolution* layer only place an rsID on GRCh38; they are not evidence.

The legacy HuggingFace mirror (`just-dna-seq/annotators`) differs from the registry for: `cancer` (mirror 2.0.0, sha256:908e6a81f6d57efe39cc9d4c89435ae03b6872e0da294305d5cb0fcca84cf8ef); `cardio` (mirror 2.0.0, sha256:85702d9fd3716661e20005295308721619dc2159f07e4790088eb84e945b783d); `pathogenic` (mirror 2.0.0, sha256:30a52528fd9b6a96bb1f96817d0f8a0a49a5d4642708d678cd8e261e0e0db76a); `superhuman` (mirror 1.2.3, sha256:0000000000000000000000000000000000000000000000000000000000000000). The registry is the reference.

## Summary

| Module | Version | Published | Curator type | Source database (release) | Lead rows | Study rows | Cited papers |
|---|---|---|---|---|---|---|---|
| Cancer (`cancer`) | 2.0.0 | 2026-09-26 | Database-derived (ClinVar) | ClinVar `clinvar_2026-06-27` | 141,616 | 140,934 | 9,830 |
| Cardio (`cardio`) | 2.0.0 | 2026-09-26 | Database-derived (ClinVar) | ClinVar `clinvar_2026-06-27` | 115,382 | 122,297 | 8,530 |
| Coronary (`coronary`) | 1.1.0 | 2026-09-26 | Expert | none (literature curation) | 81 | 118 | 59 |
| Lipid Metabolism (`lipidmetabolism`) | 1.1.0 | 2026-09-26 | Expert | none (literature curation) | 45 | 44 | 37 |
| Longevity Map (`longevitymap`) | 1.2.0 | 2026-09-26 | Expert | none (literature curation) | 1,022 | 671 | 126 |
| Pathogenic (`pathogenic`) | 2.0.0 | 2026-09-27 | Database-derived (ClinVar) | ClinVar `clinvar_2026-06-27` | 618,629 | 626,088 | 51,758 |
| Pharmacogenomics (`pharmgkb`) | 1.0.0 | 2026-09-26 | Database-derived (ClinPGx) | ClinPGx `clinpgx_2025-07-05` | 1,531 | 0 | 0 |
| Superhuman (`superhuman`) | 2.4.0 | 2026-09-26 | Expert | none (literature curation) | 99 | 74 | 29 |
| Thrombophilia (`thrombophilia`) | 1.1.0 | 2026-09-26 | Expert | none (literature curation) | 24 | 27 | 24 |
| VO2 Max (`vo2max`) | 1.1.0 | 2026-09-26 | Expert | none (literature curation) | 39 | 19 | 7 |

## Cancer (`cancer`)

Pathogenic variants in cancer-predisposition genes (ClinVar gene panel).

- **Version** 2.0.0, published 2026-09-26 23:51 UTC; artifact `sha256:f626fb73de07268ee0a0a6328842d0043d72e397dfa22a63b6797f9704f69fb6`.
- **Curator type** Database-derived (ClinVar) (licence sidecar: ClinVar feeds the annotation layer; manifest curator `just-dna-seq`, method `clinvar-aggregate`).
- **Built from** just-dna-enricher clinvar_draft.draft_gene_panel (0.5 snapshot) (release `2026-06-27`, sha256:20f5fbae2a6528a2bfbfdd114a431855c072c2e9f3692b821ad60b33f52c5fbf).
- **Databases by layer** ClinVar (annotation layer, public-domain, release `clinvar_2026-06-27`); ClinVar (resolution layer, public-domain).
- **Selection recorded by the build** clin_sig = likely_pathogenic, pathogenic; min_review_stars = 1; max_citations = 3; genes_requested = 425; genes_matched = 298; clinvar_records = 70658.
- **Counts** 141,616 `weights` rows, 70,658 variants, 298 genes; 140,934 study rows citing 9,830 distinct PubMed IDs (0 with a DOI).

The 9,830 PubMed IDs are the source database's own literature links, transcribed as the release gives them and not checked here; see `S4_module_citations.csv`.

## Cardio (`cardio`)

Pathogenic variants in cardiac-disease genes (ClinVar gene panel).

- **Version** 2.0.0, published 2026-09-26 23:48 UTC; artifact `sha256:5a80ed9951df400ebbb2f2ca7e024cdbbca339a04907f9257b5eb1852a766e55`.
- **Curator type** Database-derived (ClinVar) (licence sidecar: ClinVar feeds the annotation layer; manifest curator `just-dna-seq`, method `clinvar-aggregate`).
- **Built from** just-dna-enricher clinvar_draft.draft_gene_panel (0.5 snapshot) (release `2026-06-27`, sha256:20f5fbae2a6528a2bfbfdd114a431855c072c2e9f3692b821ad60b33f52c5fbf).
- **Databases by layer** ClinVar (annotation layer, public-domain, release `clinvar_2026-06-27`); ClinVar (resolution layer, public-domain).
- **Selection recorded by the build** clin_sig = likely_pathogenic, pathogenic; min_review_stars = 1; max_citations = 3; genes_requested = 327; genes_matched = 297; clinvar_records = 57696.
- **Counts** 115,382 `weights` rows, 57,696 variants, 297 genes; 122,297 study rows citing 8,530 distinct PubMed IDs (0 with a DOI).

The 8,530 PubMed IDs are the source database's own literature links, transcribed as the release gives them and not checked here; see `S4_module_citations.csv`.

## Coronary (`coronary`)

Coronary artery disease risk associations.

- **Version** 1.1.0, published 2026-09-26 23:43 UTC; artifact `sha256:5e96a2ccbcb306de9f079b1ce11990d95c728066786897aa1b4d36bdb1c4bd3b`.
- **Curator type** Expert (manifest curator `just-dna-seq`, method `expert-curated`).
- **Built from** Generation-I module `dna-seq/just_coronary`, file `just_coronary__coronary.sqlite` (sha256:11a8fb70b48dc0b7719e4c445f29a91bacaae9ba751d4b141dd9638161c59f34).
- **Databases by layer** Ensembl (resolution layer, Apache-2.0).
- **Counts** 81 `weights` rows, 27 variants, 22 genes; 118 study rows citing 59 distinct PubMed IDs (56 with a DOI).

| First author | Year | PMID | DOI | Rows citing |
|---|---|---|---|---|
| McPherson R | 2007 | 17478681 | 10.1126/science.1142447 | 1 |
| Samani NJ | 2007 | 17634449 | 10.1056/NEJMoa072366 | 7 |
| Wellcome Trust Case Control Consortium | 2007 | 17554300 | 10.1038/nature05911 | 7 |
| Kathiresan S | 2008 | 18193044 | 10.1038/ng.75 | 1 |
| Sandhu MS | 2008 | 18262040 | 10.1016/S0140-6736(08)60208-1 | 1 |
| Schunkert H | 2008 | 18362232 | 10.1161/CIRCULATIONAHA.107.730614 | 1 |
| Baudhuin LM | 2009 | 19956433 |  | 11 |
| Chasman DI | 2009 | 18775538 | 10.1016/j.atherosclerosis.2008.07.019 | 1 |
| Clarke R | 2009 | 20032323 | 10.1056/NEJMoa0902604 | 1 |
| Cluett C | 2009 | 20031606 | 10.1161/CIRCGENETICS.108.825935 | 1 |
| Ding K | 2009 | 19750184 | 10.1161/CIRCGENETICS.108.816751 | 4 |
| Farzaneh-Far R | 2009 | 19171343 | 10.1016/j.atherosclerosis.2008.12.026 | 1 |
| Jayasinghe SR | 2009 | 20098575 |  | 1 |
| Karvanen J | 2009 | 18979498 | 10.1002/gepi.20374 | 1 |
| Kathiresan S | 2009 | 19060906 | 10.1038/ng.291 | 1 |
| Muendlein A | 2009 | 19380133 | 10.1016/j.atherosclerosis.2009.02.040 | 1 |
| Samani NJ | 2009 | 19164808 | 10.1161/ATVBAHA.108.181388 | 2 |
| Yan Y | 2009 | 20017983 | 10.1186/1753-6561-3-s7-s118 | 4 |
| Bressler J | 2010 | 19955471 | 10.1093/aje/kwp377 | 2 |
| Kiechl S | 2010 | 20847302 | 10.1161/ATVBAHA.110.213785 | 1 |
| Linsel-Nitschke P | 2010 | 19660754 | 10.1016/j.atherosclerosis.2009.06.034 | 1 |
| Martinelli N | 2010 | 20810930 | 10.1182/blood-2010-03-277079 | 1 |
| Waterworth DM | 2010 | 20864672 | 10.1161/ATVBAHA.109.201020 | 2 |
| Coronary Artery Disease (C4D) Genetics Consortium | 2011 | 21378988 | 10.1038/ng.782 | 2 |
| Ellis KL | 2011 | 21984477 | 10.1161/CIRCGENETICS.111.960336 | 1 |
| Franceschini N | 2011 | 22042884 | 10.1161/CIRCGENETICS.111.960096 | 2 |
| Koch W | 2011 | 21264445 | 10.1160/TH10-10-0641 | 1 |
| Saade S | 2011 | 22216278 | 10.1371/journal.pone.0029427 | 1 |
| Schunkert H | 2011 | 21378990 | 10.1038/ng.784 | 9 |
| Angelakopoulou A | 2012 | 21804106 | 10.1093/eurheartj/ehr225 | 4 |
| Arregui M | 2012 | 22207032 | 10.1016/j.gene.2011.12.009 | 1 |
| Braun TR | 2012 | 22623978 | 10.1371/journal.pone.0037056 | 1 |
| Ference BA | 2012 | 23083789 | 10.1016/j.jacc.2012.09.017 | 1 |
| Grallert H | 2012 | 22003152 | 10.1093/eurheartj/ehr372 | 1 |
| Deloukas P | 2013 | 23202125 | 10.1038/ng.2480 | 6 |
| Huang Y | 2013 | 23531450 | 10.1016/j.gene.2013.02.047 | 1 |
| Lim S | 2013 | 23659870 | 10.1016/j.atherosclerosis.2013.03.037 | 1 |
| Zhang L | 2013 | 23380588 | 10.1016/j.clinbiochem.2013.01.013 | 1 |
| Dechamethakun S | 2014 | 24573017 | 10.5551/jat.22640 | 1 |
| Dichgans M | 2014 | 24262325 | 10.1161/STROKEAHA.113.002707 | 3 |
| Hirokawa M | 2015 | 24916648 | 10.1038/ejhg.2014.110 | 1 |
| Nikpay M | 2015 | 26343387 | 10.1038/ng.3396 | 4 |
| Piryaei M | 2015 | 26629484 |  | 1 |
| Zhong JY | 2015 | 26436499 | 10.4238/2015.October.2.8 | 1 |
| Liu S | 2016 | 27664493 | 10.1016/j.arcmed.2016.07.014 | 1 |
| Chen M | 2017 | 28614256 | 10.1097/MD.0000000000007179 | 1 |
| Guo Y | 2017 | 28710368 | 10.1038/s41598-017-05381-2 | 1 |
| Nelson CP | 2017 | 28714975 | 10.1038/ng.3913 | 2 |
| Xu B | 2018 | 30278588 | 10.1097/MD.0000000000012641 | 1 |
| Zhou W | 2018 | 30104761 | 10.1038/s41588-018-0184-y | 1 |
| van der Harst P | 2018 | 29212778 | 10.1161/CIRCRESAHA.117.312086 | 1 |
| Hall KT | 2019 | 31228190 | 10.1093/eurheartj/ehz384 | 2 |
| Karami F | 2019 | 30507093 | 10.22074/cellj.2019.5692 | 1 |
| Li JL | 2019 | 31883534 | 10.1186/s12944-019-1177-2 | 1 |
| Rodríguez-Arellano ME | 2020 | 32858814 | 10.3390/medicina56090427 | 1 |
| Yang X | 2020 | 32067586 | 10.1161/JAHA.119.014333 | 1 |
| van Zuydam NR | 2020 | 33321069 | 10.1161/CIRCGEN.119.002769 | 3 |
| Song Y | 2021 | 33632238 | 10.1186/s12967-021-02751-3 | 2 |
| Rayat S | 2022 | 35768776 | 10.1186/s12872-022-02695-6 | 1 |

## Lipid Metabolism (`lipidmetabolism`)

Lipid metabolism and cardiovascular risk variants.

- **Version** 1.1.0, published 2026-09-26 23:44 UTC; artifact `sha256:30814dd7460d9e90f71adb61a34696a1f938cc3315db03895c8d5b0774fc6a48`.
- **Curator type** Expert (manifest curator `just-dna-seq`, method `expert-curated`).
- **Built from** Generation-I module `dna-seq/just_lipidmetabolism`, file `just_lipidmetabolism__lipid_metabolism.sqlite` (sha256:4eed07c0d2cbaeda1b868de4c83b244203f6b00819ae5e61e7eec7ddbe51eac2).
- **Databases by layer** Ensembl (resolution layer, Apache-2.0).
- **Counts** 45 `weights` rows, 15 variants, 12 genes; 44 study rows citing 37 distinct PubMed IDs (36 with a DOI).

| First author | Year | PMID | DOI | Rows citing |
|---|---|---|---|---|
| Hu Y | 2006 | 16741292 | 10.1194/jlr.M600108-JLR200 | 1 |
| Zee RY | 2006 | 16651467 | 10.1161/CIRCULATIONAHA.106.615401 | 1 |
| Pare G | 2007 | 17357073 | 10.1086/513286 | 1 |
| Kathiresan S | 2008 | 18193044 | 10.1038/ng.75 | 1 |
| Lu Y | 2008 | 18660489 | 10.1194/jlr.M800232-JLR200 | 1 |
| Thompson A | 2008 | 18560005 | 10.1001/jama.299.23.2777 | 1 |
| Aulchenko YS | 2009 | 19060911 | 10.1038/ng.269 | 1 |
| Deo RC | 2009 | 19148283 | 10.1371/journal.pgen.1000342 | 1 |
| Kathiresan S | 2009 | 19060906 | 10.1038/ng.291 | 3 |
| Liu Y | 2009 | 19057464 | 10.1097/FPC.0b013e32831e030e | 1 |
| Ridker PM | 2009 | 20031564 | 10.1161/CIRCGENETICS.108.817304 | 1 |
| Ronald J | 2009 | 19951432 | 10.1186/1476-511X-8-52 | 1 |
| Smith CE | 2009 | 19424489 | 10.1371/journal.pone.0005465 | 1 |
| Ariza MJ | 2010 | 20429872 | 10.1186/1471-2350-11-66 | 3 |
| Chang MH | 2010 | 20406466 | 10.1186/1471-2350-11-62 | 1 |
| Jarvik GP | 2010 | 19965587 | 10.1194/jlr.M000125 | 1 |
| Lu Y | 2010 | 20832063 | 10.1016/j.atherosclerosis.2010.08.053 | 1 |
| Dumitrescu L | 2011 | 21738485 | 10.1371/journal.pgen.1002138 | 1 |
| Kristiansson K | 2012 | 22399527 | 10.1161/CIRCGENETICS.111.961482 | 1 |
| Toms TE | 2012 | 22174202 | 10.3899/jrheum.110683 | 1 |
| Mäkelä KM | 2013 | 23247145 | 10.1161/CIRCGENETICS.112.964965 | 1 |
| Willer CJ | 2013 | 24097068 | 10.1038/ng.2797 | 1 |
| Postmus I | 2014 | 25350695 | 10.1038/ncomms6068 | 1 |
| Liu C | 2015 | 26629186 |  | 1 |
| Guo SX | 2016 | 27608031 | 10.3390/ijerph13090882 | 1 |
| Nagy R | 2017 | 28270201 | 10.1186/s13073-017-0414-4 | 1 |
| Paththinige CS | 2017 | 28577571 | 10.1186/s12944-017-0488-4 | 1 |
| Zhou YJ | 2017 | 28035729 | 10.1002/jgm.2941 | 1 |
| Hoffmann TJ | 2018 | 29507422 | 10.1038/s41588-018-0064-5 | 2 |
| Al-Bustan SA | 2019 | 30944368 | 10.1038/s41598-019-42021-3 | 1 |
| Bentley AR | 2019 | 30926973 | 10.1038/s41588-019-0378-y | 1 |
| Gurdasani D | 2019 | 31675503 | 10.1016/j.cell.2019.10.004 | 1 |
| Semaev S | 2019 | 31739638 | 10.3390/biom9110739 | 1 |
| Richardson TG | 2020 | 32203549 | 10.1371/journal.pmed.1003062 | 1 |
| Abdulfattah SY | 2021 | 34156559 | 10.1186/s43141-021-00193-4 | 1 |
| Graham SE | 2021 | 34887591 | 10.1038/s41586-021-04064-3 | 2 |
| Harshfield EL | 2021 | 34503513 | 10.1186/s12916-021-02087-1 | 2 |

## Longevity Map (`longevitymap`)

Longevity-associated genetic variants from LongevityMap database.

- **Version** 1.2.0, published 2026-09-26 23:44 UTC; artifact `sha256:2c6a4d51433e9afaf4a73b30f94045f97068ac252d02643065311809defb886c`.
- **Curator type** Expert (manifest curator `just-dna-seq`, method `expert-curated`).
- **Built from** Generation-I module `dna-seq/just_longevitymap`, file `just_longevitymap__longevitymap.sqlite` (sha256:f4a6439e8646b8febc6a208b198b54450f6b8e6a844c4dad50867a0887e294a7).
- **Databases by layer** Ensembl (resolution layer, Apache-2.0).
- **Counts** 1,022 `weights` rows, 528 variants, 272 genes; 671 study rows citing 126 distinct PubMed IDs (124 with a DOI).

| First author | Year | PMID | DOI | Rows citing |
|---|---|---|---|---|
| Eggertsen G | 1993 | 8403397 | 10.1093/clinchem/39.10.2125 | 1 |
| Kervinen K | 1994 | 8155090 | 10.1016/0021-9150(94)90011-6 | 1 |
| Louhija J | 1994 | 8018664 | 10.1161/01.atv.14.7.1084 | 1 |
| Schächter F | 1994 | 8136829 | 10.1038/ng0194-29 | 1 |
| Ruiu G | 1995 | 8541369 | 10.1007/BF03324333 | 1 |
| Galinsky D | 1997 | 9105559 | 10.1016/s0021-9150(96)06027-3 | 1 |
| Mannucci PM | 1997 | 9108791 | 10.1161/01.atv.17.4.755 | 1 |
| Jian-Gang Z | 1998 | 9792194 | 10.1016/s0047-6374(98)00067-0 | 1 |
| Bladbjerg EM | 1999 | 10494771 | 10.1055/s-0037-1614336 | 1 |
| Heijmans BT | 1999 | 10520809 | 10.1016/s0735-1097(99)00337-x | 1 |
| Blanché H | 2001 | 11280044 | 10.1016/s0764-4469(00)01274-9 | 1 |
| Bonafè M | 2001 | 11500818 | 10.1002/1521-4141(200108)31:8&#60;2357::aid-immu2357&#62;3.0.co;2-x | 1 |
| Frisoni GB | 2001 | 11213279 | 10.1093/gerona/56.2.m75 | 1 |
| Lottermoser K | 2001 | 11485022 | 10.1007/s001090100192 | 1 |
| Rea IM | 2001 | 11470126 | 10.1016/s0047-6374(01)00278-0 | 1 |
| Wang XY | 2001 | 11640949 | 10.1016/s0047-6374(01)00338-4 | 2 |
| Bonafè M | 2002 | 12082503 | 10.1038/sj.ejhg.5200806 | 1 |
| Lio D | 2002 | 11772518 | 10.1016/s0531-5565(01)00198-x | 1 |
| Lio D | 2002 | 11857058 | 10.1038/sj.gene.6363827 | 2 |
| Schwanke CH | 2002 | 12185856 | 10.1590/s0066-782x2002000600004 | 1 |
| Altomare K | 2003 | 14501185 | 10.1023/a:1025182615693 | 1 |
| Choi YH | 2003 | 12634288 | 10.1093/gerona/58.3.m227 | 1 |
| Geesaman BJ | 2003 | 14615589 | 10.1073/pnas.1936249100 | 1 |
| Lio D | 2003 | 12676903 | 10.1136/jmg.40.4.296 | 2 |
| Rea IM | 2003 | 12714267 | 10.1016/s0047-6374(03)00036-8 | 1 |
| Ross OA | 2003 | 12714268 | 10.1016/s0047-6374(03)00037-x | 3 |
| Shabalin AV | 2003 | 14743603 |  | 1 |
| Xia Y | 2003 | 12889841 | 10.1007/BF03324487 | 1 |
| Bruunsgaard H | 2004 | 15271127 | 10.1111/j.1532-5415.2004.52369.x | 1 |
| Capurso C | 2004 | 15236771 | 10.1016/j.exger.2004.03.037 | 1 |
| Christiansen L | 2004 | 15130757 | 10.1016/j.mad.2004.03.004 | 1 |
| Christiansen L | 2004 | 15241482 | 10.1038/sj.ejhg.5201235 | 2 |
| Naumova E | 2004 | 15050300 | 10.1016/j.exger.2003.08.014 | 4 |
| Pes GM | 2004 | 15462469 | 10.1007/BF03327391 | 3 |
| Pesch B | 2004 | 15177664 | 10.1016/j.toxlet.2004.01.025 | 1 |
| Rea IM | 2004 | 15050299 | 10.1016/j.exger.2003.11.019 | 1 |
| Singh R | 2004 | 15190186 | 10.1023/B:BGEN.0000031154.57176.4f | 1 |
| Bathum L | 2005 | 16015282 | 10.1038/sj.ejhg.5201468 | 1 |
| Hurme M | 2005 | 15664628 | 10.1016/j.mad.2004.10.001 | 1 |
| Mayila W | 2005 | 16086293 |  | 1 |
| Nebel A | 2005 | 15911777 | 10.1073/pnas.0408670102 | 1 |
| Reiner AP | 2005 | 15939070 | 10.1016/j.atherosclerosis.2005.01.028 | 2 |
| Soto-Vega E | 2005 | 16269080 | 10.1186/1742-4933-2-13 | 1 |
| Stessman J | 2005 | 15621215 | 10.1016/j.mad.2004.08.025 | 1 |
| Atzmon G | 2006 | 16602826 | 10.1371/journal.pbio.0040113 | 1 |
| Grimaldi MP | 2006 | 16387839 | 10.1189/jlb.0705416 | 2 |
| Seripa D | 2006 | 16960022 | 10.1093/gerona/61.9.918 | 1 |
| Singh R | 2006 | 16804002 | 10.1196/annals.1354.040 | 1 |
| Stakias N | 2006 | 17234815 | 10.1093/gerona/61.12.1228 | 1 |
| Terry DF | 2006 | 17027907 | 10.1016/j.mad.2006.08.007 | 1 |
| Frayling TM | 2007 | 17301041 | 10.1093/gerona/62.1.73 | 1 |
| Listì F | 2007 | 17048073 | 10.1007/s10522-006-9041-y | 1 |
| Lunetta KL | 2007 | 17903295 | 10.1186/1471-2350-8-S1-S13 | 1 |
| Neville MJ | 2007 | 17339647 | 10.1093/gerona/62.2.202 | 1 |
| Bojesen SE | 2008 | 18256523 | 10.4161/cc.7.2.5249 | 1 |
| Cardelli M | 2008 | 18511747 | 10.1093/gerona/63.5.454 | 1 |
| Willcox BJ | 2008 | 18765803 | 10.1073/pnas.0801030105 | 5 |
| Anselmi CV | 2009 | 19415983 | 10.1089/rej.2008.0827 | 4 |
| Atzmon G | 2009 | 19837933 | 10.1210/jc.2009-0808 | 2 |
| Flachsbart F | 2009 | 19196970 | 10.1073/pnas.0809594106 | 15 |
| Gravina S | 2009 | 20126416 | 10.18632/aging.100041 | 2 |
| Lescai F | 2009 | 19367319 | 10.1038/ejhg.2009.54 | 1 |
| Li Y | 2009 | 19793722 | 10.1093/hmg/ddp459 | 5 |
| Nebel A | 2009 | 19698732 | 10.1016/j.mad.2009.08.004 | 3 |
| Park JW | 2009 | 19641380 | 10.3858/emm.2009.41.11.083 | 18 |
| Pawlikowska L | 2009 | 19489743 | 10.1111/j.1474-9726.2009.00493.x | 3 |
| Sebastiani P | 2009 | 20011587 | 10.1371/journal.pone.0008210 | 18 |
| Soerensen M | 2009 | 19428448 | 10.1016/j.mad.2009.01.005 | 2 |
| Beekman M | 2010 | 20921414 | 10.1073/pnas.1003540107 | 2 |
| Chen T | 2010 | 20816691 | 10.1016/j.mad.2010.08.009 | 1 |
| Emanuele E | 2010 | 20230275 | 10.1089/rej.2009.0970 | 1 |
| Khabour OF | 2010 | 20201642 | 10.3109/13685531003657800 | 2 |
| Khabour OF | 2010 | 20518833 | 10.1111/j.1744-313X.2010.00925.x | 2 |
| Kulminski AM | 2010 | 20399803 | 10.1016/j.mad.2010.04.001 | 1 |
| Soerensen M | 2010 | 20849522 | 10.1111/j.1474-9726.2010.00627.x | 10 |
| Ulybina YM | 2010 | 20434535 | 10.1016/j.exger.2010.04.007 | 1 |
| Zeng Y | 2010 | 20884733 | 10.1093/gerona/glq156 | 5 |
| Zhang WG | 2010 | 20633545 | 10.1016/j.cca.2010.06.030 | 2 |
| Albani D | 2011 | 22115178 | 10.3109/13685538.2011.607521 | 2 |
| Corbo RM | 2011 | 20819792 | 10.1093/gerona/glq160 | 1 |
| Deelen J | 2011 | 21418511 | 10.1111/j.1474-9726.2011.00705.x | 10 |
| Kayaaltı Z | 2011 | 21277639 | 10.1016/j.archger.2011.01.001 | 2 |
| Kleindorp R | 2011 | 21388494 | 10.1111/j.1474-9726.2011.00698.x | 2 |
| Malovini A | 2011 | 21612516 | 10.1089/rej.2010.1114 | 2 |
| McKay GJ | 2011 | 21498624 | 10.1093/aje/kwr015 | 2 |
| Napolioni V | 2011 | 21865054 | 10.1016/j.cyto.2011.07.023 | 3 |
| Nebel A | 2011 | 21740922 | 10.1016/j.mad.2011.06.008 | 2 |
| Piaceri I | 2011 | 21297266 | 10.3233/JAD-2011-101791 | 1 |
| Rose G | 2011 | 22216339 | 10.1371/journal.pone.0029650 | 4 |
| Barbieri M | 2012 | 21340542 | 10.1007/s11357-011-9210-z | 4 |
| Campa D | 2012 | 23133589 | 10.1371/journal.pone.0045232 | 1 |
| Conneely KN | 2012 | 22340368 | 10.1111/j.1474-9726.2012.00808.x | 4 |
| Dato S | 2012 | 22743239 | 10.1016/j.mad.2012.06.004 | 4 |
| Huffman DM | 2012 | 22496539 | 10.1093/gerona/gls103 | 3 |
| Kim S | 2012 | 21972126 | 10.1007/s10522-011-9360-5 | 1 |
| Laplana M | 2012 | 22265023 | 10.1016/j.cyto.2011.12.021 | 2 |
| Sebastiani P | 2012 | 22279548 | 10.1371/journal.pone.0029848 | 280 |
| Shi H | 2012 | 22445811 | 10.1016/j.neurobiolaging.2012.02.014 | 2 |
| Soerensen M | 2012 | 22406557 | 10.1016/j.exger.2012.02.010 | 17 |
| Yashin AI | 2012 | 22533364 | 10.1089/rej.2011.1257 | 27 |
| Zhao L | 2012 | 23020224 | 10.1111/acel.12011 | 3 |
| Beekman M | 2013 | 23286790 | 10.1111/acel.12039 | 1 |
| Benigni A | 2013 | 22569962 | 10.1007/s11357-012-9408-8 | 2 |
| Di Cianni F | 2013 | 22576335 | 10.1007/s11357-012-9416-8 | 15 |
| Di Pietro F | 2013 | 23125046 | 10.1093/gerona/gls223 | 1 |
| Edwards DR | 2013 | 22773346 | 10.1007/s11357-012-9447-1 | 1 |
| Figarska SM | 2013 | 23505545 | 10.1371/journal.pone.0058636 | 1 |
| Garatachea N | 2013 | 23354683 | 10.1007/s11357-013-9513-3 | 1 |
| Gentschew L | 2013 | 24146173 | 10.1007/s10522-013-9470-3 | 3 |
| Hornstrup LS | 2013 | 23580146 | 10.1161/ATVBAHA.113.301273 | 1 |
| Lindahl-Jacobsen R | 2013 | 23051975 | 10.1093/gerona/gls192 | 2 |
| Montesanto A | 2013 | 23572278 | 10.1007/s10522-013-9421-z | 1 |
| Nygaard M | 2013 | 22929028 | 10.1038/ejhg.2012.196 | 1 |
| Piaceri I | 2013 | 22960875 | 10.1007/s10072-012-1188-5 | 1 |
| Schupf N | 2013 | 23040522 | 10.1016/j.neurobiolaging.2012.08.019 | 1 |
| Soerensen M | 2013 | 22234866 | 10.1007/s11357-011-9373-7 | 20 |
| Albani D | 2014 | 23839864 | 10.1007/s11357-013-9559-2 | 2 |
| Dato S | 2014 | 24462499 | 10.1016/j.exger.2014.01.014 | 33 |
| Debrabant B | 2014 | 24518833 | 10.1038/ejhg.2013.299 | 11 |
| Deelen J | 2014 | 24688116 | 10.1093/hmg/ddu139 | 2 |
| Kolovou G | 2014 | 23389097 | 10.1177/0003319712475075 | 1 |
| Morris BJ | 2014 | 23770741 | 10.1093/gerona/glt082 | 1 |
| Pinós T | 2014 | 24163049 | 10.1007/s11357-013-9593-0 | 1 |
| Han J | 2015 | 25305471 | 10.1016/j.trsl.2014.09.008 | 3 |
| Kim S | 2015 | 25682868 | 10.18632/oncotarget.2877 | 10 |
| Rose G | 2015 | 26254886 | 10.1016/j.mad.2015.08.003 | 2 |

## Pathogenic (`pathogenic`)

Genome-wide ClinVar pathogenic / likely-pathogenic variant flag.

- **Version** 2.0.0, published 2026-09-27 00:06 UTC; artifact `sha256:540a59613d80e25c873ee3c3c1c8f36005abb1b12d14165ba91f426dca750ed8`.
- **Curator type** Database-derived (ClinVar) (licence sidecar: ClinVar feeds the annotation layer; manifest curator `just-dna-seq`, method `clinvar-aggregate`).
- **Built from** just-dna-enricher clinvar_draft.draft_gene_panel (0.5 snapshot) (release `2026-06-27`, sha256:20f5fbae2a6528a2bfbfdd114a431855c072c2e9f3692b821ad60b33f52c5fbf).
- **Databases by layer** ClinVar (annotation layer, public-domain, release `clinvar_2026-06-27`); ClinVar (resolution layer, public-domain).
- **Selection recorded by the build** clin_sig = likely_pathogenic, pathogenic; min_review_stars = 1; max_citations = 3; genes_requested = 4793; genes_matched = 4793; clinvar_records = 308990.
- **Counts** 618,629 `weights` rows, 308,990 variants, 4,793 genes; 626,088 study rows citing 51,758 distinct PubMed IDs (0 with a DOI).

The 51,758 PubMed IDs are the source database's own literature links, transcribed as the release gives them and not checked here; see `S4_module_citations.csv`.

## Pharmacogenomics (`pharmgkb`)

Drug response by genotype, from the ClinPGx (PharmGKB) clinical annotations at evidence levels 1A/1B/2A/2B.

- **Version** 1.0.0, published 2026-09-26 23:45 UTC; artifact `sha256:aeb2b46111d3186ff3622cc25d3376b526fa31183c65e8322d18e139e19360a7`.
- **Curator type** Database-derived (ClinPGx) (licence sidecar: ClinPGx feeds the annotation layer; manifest curator `ai-module-creator`, method `literature-review` (the format's defaults, not a statement)).
- **Built from** just-dna-enricher clinpgx_draft.draft_pharm_variants (0.5 snapshot) (release `clinpgx_2025-07-05`, sha256:9c6512c54f3c9321effacb11178fb2ae1c45fa3f1710f08c3c365ee7537ced07).
- **Databases by layer** ClinPGx (annotation layer, CC-BY-SA-4.0, release `clinpgx_2025-07-05`); Ensembl (resolution layer, Apache-2.0).
- **Selection recorded by the build** min_evidence_level = 2B; supersedes = dna-seq/just_drugs data/annotation_tab.tsv (PharmGKB variant annotations); clinical_annotations = 240; drugs = 65; genes = 35.
- **Counts** 1,531 `pharm_variants` rows, 35 genes; 0 study rows citing 0 distinct PubMed IDs (0 with a DOI).

No row of this artifact cites a PubMed ID; its evidence is the database release above.

## Superhuman (`superhuman`)

Elite performance and rare beneficial variants.

- **Version** 2.4.0, published 2026-09-26 23:45 UTC; artifact `sha256:c64102efadc92c827fe57cba08049e480c56f0d5fbe4588dcd54aafc2c437122`.
- **Curator type** Expert (manifest curator `just-dna-seq`, method `expert-curated`).
- **Built from** Generation-I module `dna-seq/just_superhuman`, file `just_superhuman__superhuman.sqlite` (sha256:88fdc4971f67695723fb668211a0c342debe76998c5aabd530299dfcabd24ddc).
- **Databases by layer** ClinVar (resolution layer, public-domain); Ensembl (resolution layer, Apache-2.0).
- **Counts** 99 `weights` rows, 74 variants, 28 genes; 74 study rows citing 29 distinct PubMed IDs (28 with a DOI).

| First author | Year | PMID | DOI | Rows citing |
|---|---|---|---|---|
| Indo Y | 1996 | 8696348 | 10.1038/ng0896-485 | 25 |
| Samson M | 1996 | 8751444 | 10.1038/382722a0 | 1 |
| Barzilai N | 2003 | 14559957 | 10.1001/jama.290.15.2030 | 1 |
| Egan MF | 2003 | 12553913 | 10.1016/s0092-8674(03)00035-7 | 1 |
| Lindesmith L | 2003 | 12692541 | 10.1038/nm860 | 1 |
| Zubieta JK | 2003 | 12595695 | 10.1126/science.1078546 | 1 |
| Johnson ML | 2004 | 15615112 |  | 1 |
| Schuelke M | 2004 | 15215484 | 10.1056/NEJMoa040933 | 5 |
| Cohen JC | 2006 | 16554528 | 10.1056/NEJMoa054013 | 1 |
| Cox JJ | 2006 | 17167479 | 10.1038/nature05413 | 9 |
| Duerr RH | 2006 | 17068223 | 10.1126/science.1135245 | 1 |
| Yoshiura K | 2006 | 16444273 | 10.1038/ng1733 | 1 |
| Zuo L | 2006 | 16603077 | 10.1186/1744-9081-2-13 | 1 |
| Corella D | 2007 | 17446329 | 10.1373/clinchem.2006.084863 | 1 |
| Downes K | 2010 | 20844740 | 10.1371/journal.pone.0012646 | 1 |
| Genovese G | 2010 | 20647424 | 10.1126/science.1193032 | 2 |
| Jonsson T | 2012 | 22801501 | 10.1038/nature11283 | 1 |
| Junnila RK | 2013 | 23591370 | 10.1038/nrendo.2013.67 | 1 |
| Flannick J | 2014 | 24584071 | 10.1038/ng.2915 | 1 |
| Asante EA | 2015 | 26061765 | 10.1038/nature14510 | 1 |
| Bosch L | 2017 | 28499359 | 10.1186/s12879-017-2448-z | 3 |
| Laas K | 2017 | 28342337 | 10.1016/j.jad.2017.03.045 | 1 |
| Abul-Husn NS | 2018 | 29562163 | 10.1056/NEJMoa1712191 | 1 |
| Ilardo MA | 2018 | 29677510 | 10.1016/j.cell.2018.03.054 | 1 |
| Arboleda-Velasquez JF | 2019 | 31686034 | 10.1038/s41591-019-0611-3 | 1 |
| Habib AM | 2019 | 30929760 | 10.1016/j.bja.2019.02.019 | 1 |
| Koromina M | 2019 | 29243543 | 10.1080/15622975.2017.1417637 | 1 |
| Xing L | 2019 | 31619542 | 10.1126/scitranslmed.aax2014 | 1 |
| Paul MM | 2022 | 35022694 | 10.1093/brain/awac011 | 7 |

## Thrombophilia (`thrombophilia`)

Inherited blood-clotting risk variants (Factor V Leiden, prothrombin, and related loci).

- **Version** 1.1.0, published 2026-09-26 23:44 UTC; artifact `sha256:6bd966c7fd96cffae582794977e3fdae8bf05faf66ebc29c239a1b048c2d6c42`.
- **Curator type** Expert (manifest curator `just-dna-seq`, method `expert-curated`).
- **Built from** Generation-I module `dna-seq/just_thrombophilia`, file `just_thrombophilia__thrombophilia.sqlite` (sha256:6724afb711d2a8d8a9f040d9a8cdcf134ba9d73968a9142b5f1672cdb74746de).
- **Databases by layer** Ensembl (resolution layer, Apache-2.0).
- **Counts** 24 `weights` rows, 8 variants, 8 genes; 27 study rows citing 24 distinct PubMed IDs (24 with a DOI).

| First author | Year | PMID | DOI | Rows citing |
|---|---|---|---|---|
| Weiss EJ | 1996 | 8598867 | 10.1056/NEJM199604253341703 | 1 |
| Pastinen T | 1998 | 9700201 | 10.1093/hmg/7.9.1453 | 2 |
| De Stefano V | 1999 | 10477778 | 10.1056/NEJM199909093411104 | 1 |
| Gerhardt A | 2000 | 10666427 | 10.1056/NEJM200002103420602 | 1 |
| Undas A | 2001 | 11723016 | 10.1161/hc4701.099787 | 1 |
| Juul K | 2004 | 14996674 | 10.7326/0003-4819-140-5-200403020-00008 | 1 |
| Su S | 2006 | 16424345 | 10.1161/01.ATV.0000204731.17646.f2 | 1 |
| Li Y | 2009 | 19583818 | 10.1111/j.1538-7836.2009.03544.x | 1 |
| Pezzini A | 2009 | 19404532 | 10.1160/th08-11-0747 | 1 |
| Austin H | 2011 | 21232005 | 10.1111/j.1538-7836.2011.04185.x | 1 |
| Heit JA | 2011 | 21463476 | 10.1111/j.1538-7836.2011.04272.x | 1 |
| El-Galaly TC | 2013 | 23150947 | 10.1111/bjh.12132 | 1 |
| Lantz M | 2013 | 22784820 | 10.1016/j.jstrokecerebrovasdis.2012.06.002 | 1 |
| Simone B | 2013 | 23900608 | 10.1007/s10654-013-9825-8 | 2 |
| Zhao L | 2013 | 23180602 | 10.1093/molehr/gas056 | 1 |
| Rovite V | 2014 | 25091233 | 10.1016/j.thromres.2014.07.011 | 1 |
| Hu X | 2017 | 29235504 | 10.1038/s41598-017-17537-1 | 1 |
| Klarin D | 2017 | 28373160 | 10.1161/CIRCGENETICS.116.001643 | 1 |
| Canseco-Avila LM | 2019 | 31354890 | 10.1155/2019/5769514 | 1 |
| Lindström S | 2019 | 31420334 | 10.1182/blood.2019000435 | 2 |
| Zeng J | 2019 | 30466296 | 10.1177/2047487318799467 | 1 |
| Geng B | 2020 | 31948344 | 10.1177/0268355519897552 | 1 |
| Goumidi L | 2021 | 33512453 | 10.1182/blood.2020008997 | 1 |
| Liu T | 2021 | 34707639 | 10.3389/fgene.2021.717621 | 1 |

## VO2 Max (`vo2max`)

Athletic performance and oxygen uptake capacity variants.

- **Version** 1.1.0, published 2026-09-26 23:44 UTC; artifact `sha256:1a743e13710660f465d316d5163452e8695ed9ded09d82f45d1fae19b4e27c24`.
- **Curator type** Expert (manifest curator `just-dna-seq`, method `expert-curated`).
- **Built from** Generation-I module `dna-seq/just_vo2max`, file `just_vo2max__vo2max.sqlite` (sha256:c328c54b051c1c0fdbc0490a5a8a4c6998311da0204371755ddc50b1decd641d).
- **Databases by layer** Ensembl (resolution layer, Apache-2.0).
- **Counts** 39 `weights` rows, 13 variants, 12 genes; 19 study rows citing 7 distinct PubMed IDs (7 with a DOI).

| First author | Year | PMID | DOI | Rows citing |
|---|---|---|---|---|
| Rico-Sanz J | 2003 | 12783984 | 10.1152/physiolgenomics.00165.2002 | 1 |
| Thompson PD | 2004 | 14767871 | 10.1016/j.metabol.2003.09.010 | 2 |
| Bouchard C | 2011 | 21183627 | 10.1152/japplphysiol.00973.2010 | 9 |
| Thomaes T | 2011 | 21967077 | 10.1186/1471-2156-12-84 | 1 |
| Ghosh S | 2013 | 23990238 | 10.1152/japplphysiol.01487.2012 | 3 |
| Yu B | 2014 | 24571688 | 10.1186/1476-511X-13-40 | 2 |
| Zarebska A | 2014 | 25435667 | 10.5604/20831862.1120932 | 1 |
