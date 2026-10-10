# C36: Comparison with other tools (draft for Paper 1, Just-DNA-Lite)

Status: DRAFT. Not applied to any repository file. All tool cells were filled from each project's own documentation, README or paper, opened on 2026-10-10. "?" means the project's own material did not state it.

---

## 1. Table

**Table X.** Documented features of Just-DNA-Lite and tools for personal-genome annotation, polygenic scoring and AI-assisted interpretation, as of 10 October 2026. Feature comparison only; no cell is a claim about accuracy, speed or usability.

| Tool | Runs locally (no upload) | Graphical interface | Add annotation sets without code | PRS (PGS Catalog) | Ancestry-aware percentiles | Human-readable report | AI-assistant (MCP) access | Open source (licence) | Last release (date) | Reference |
|---|---|---|---|---|---|---|---|---|---|---|
| **Just-DNA-Lite** | Yes | Yes (local web UI) | Yes | Yes | Yes | Yes | Yes | Yes (AGPL-3.0) | v0.3.18 (2026-08-16) | this work |
| *Variant annotation engines* | | | | | | | | | | |
| Ensembl VEP | Yes (also hosted) | Hosted web form only^a^ | Yes | No | n/a | Partial^b^ | No^c^ | Yes (Apache-2.0) | 116.3 (2026-10-09) | McLaren et al., 2016 |
| ANNOVAR | Yes (also hosted: wANNOVAR) | Hosted web form only^a^ | Yes | No | n/a | No | No | No (free for non-commercial use) | ? (2025-03-02)^d^ | Wang et al., 2010 |
| SnpEff / SnpSift | Yes | No | Yes | No | n/a | Partial^b^ | No | Yes (MIT) | 5.4c (2026-02-23) | Cingolani et al., 2012a, 2012b |
| vcfanno | Yes | No | Yes | No | n/a | No | No | Yes (MIT) | 0.3.9 (2026-06-16) | Pedersen et al., 2016 |
| echtvar | Yes | No | Yes | No | n/a | No | No | Yes (MIT) | 0.2.4 (2026-04-30) | Pedersen & de Ridder, 2023 |
| *Personal-genome platforms and reports* | | | | | | | | | | |
| OpenCRAVAT | Yes (also hosted) | Yes (local web UI; also hosted) | Partial^cc^ | No | n/a | Partial^dd^ | Partial^ee^ | Yes (MIT) | 3.2.1 (2026-10-08) | Pagel et al., 2020 |
| OakVar^e^ | Yes | Yes (local web UI) | Partial^cc^ | ?^ff^ | ?^ff^ | Partial^dd^ | No | No (proprietary; free for non-commercial use after registration) | 2.13.1 (2026-08-30) | no paper (GitHub) |
| GenomeChronicler | Yes | No | ? | No | n/a | Yes (PDF) | No | ?^gg^ | 0.91 (2019-10-26); fixes merged 2026-07-09 | Guerra-Assunção et al., 2020 |
| SNPedia / Promethease | No (upload to paid service) | Hosted web form | No | ? | ? | Yes (interactive HTML) | ? | No (closed service; SNPedia content CC BY-NC-SA 3.0) | n/a (service operating 2026-10-10)^hh^ | Cariaso & Lennon, 2012 |
| impute.me (discontinued 2022) | Partial (hosted; local Docker route documented) | Hosted web form | ? | Partial^ii^ | Yes (Z-scores per 1000 Genomes superpopulation) | Partial | n/a | Yes (LGPL-3.0; code no longer on GitHub) | 1.0.7 (2021-11-02)^jj^ | Folkersen et al., 2020 |
| VCFshiny | Yes | Yes (local web UI) | Partial^f^ | No | n/a | Partial^g^ | No | Yes (MIT) | none tagged; last code commit 2024-10-16 | Chen et al., 2023 |
| PharmCAT | Yes | No | Partial^h^ | No | n/a | Yes | No | Yes (MPL-2.0) | 3.4.0 (2026-07-14) | Sangkuhl et al., 2020; Li et al., 2023 |
| ACVI-Med | Yes (self-hosted) | Yes (local web UI) | Partial^i^ | ? | n/a | Partial^g^ | No | Yes (MIT) | none tagged; last commit 2026-05-28 | Stadler et al., 2026 |
| Personal-Genome-Pipeline | Yes | No | Partial^j^ | Yes | Yes | Yes | No | Yes (GPL-3.0-or-later) | 0.8.2 (2026-07-01) | no paper (GitHub) |
| *Polygenic score tools* | | | | | | | | | | |
| PLINK 2 | Yes | No | n/a^k^ | Partial^l^ | ? | ? | No | Yes (GPL-3.0) | 2.0.0-a.7.11 (2026-10-01) | Chang et al., 2015 |
| PRSice-2 | Yes | No | n/a^k^ | No^m^ | ? | Partial^n^ | No | Yes (GPL-3.0) | 2.3.5 (2021-09-20)^o^ | Choi & O'Reilly, 2019 |
| pgsc_calc | Yes | No | n/a^k^ | Yes^p^ | Yes (optional) | Partial^q^ | No | Yes (Apache-2.0) | 2.3.0 (2026-06-03) | Lambert et al., 2024 |
| GenoPred | Yes | No | n/a^k^ | Yes | Partial^r^ | Yes | No | Yes (GPL-3.0) | 2.3.3 (2025-11-27) | Pain et al., 2024 |
| Imputation Server PGS / pgs-calc | Yes (pgs-calc; server requires upload) | Hosted web form only^a^ | n/a^k^ | Yes | No^s^ | Partial^q^ | No | Yes (MIT) | pgs-calc 1.6.2 (2025-10-28) | Forer et al., 2024 |
| PRSKB | Yes (CLI; web version computes in the browser) | Yes (web page, in-browser) | n/a^k^ | Partial^t^ | Partial^u^ | Partial^v^ | No | No (free for academic use) | 1.0.0 (2022-06-23); last commit 2024-08-22 | Page et al., 2022 |
| PGS Browser / pgsb-cli | Yes (scoring); interpretation hosted | Partial^w^ | n/a^k^ | Yes | Partial^x^ | Partial^v^ | No | No (CC BY-NC-ND 4.0) | none tagged; last commit 2026-05-14 | Kolosov et al., 2026 |
| *AI-assistant and LLM interpretation* | | | | | | | | | | |
| GeneChat MCP | Yes^y^ | No | No | Yes (4 bundled scores) | No | Partial^z^ | Yes | Yes (MIT) | none tagged; last commit 2026-04-13 | no paper (GitHub) |
| DeepRare | Partial^aa^ | Hosted web app (by request) | ? | No | n/a | Yes (hosted app) | No^bb^ | No (CC BY-NC 4.0) | none tagged; last commit 2026-04-14 | Zhao et al., 2026 |

**Column definitions.** *Runs locally*: the core analysis runs on the user's machine without uploading the genome to a third-party server; "also hosted" marks tools that additionally offer an upload service. *Graphical interface*: a GUI for the core analysis, either local or hosted (stated). *Add annotation sets without code*: a user adds a new annotation source by supplying data files and configuration, without writing program code (n/a for tools that do not annotate variants). *PRS (PGS Catalog)*: computes scores from PGS Catalog scoring files; Partial when only generic user-formatted weights are accepted. *Ancestry-aware percentiles*: places the score against a reference population matched to, or chosen for, the sample's ancestry. *Human-readable report*: output meant to be read by a person (narrative or interpreted summary), beyond an annotated VCF or table; Partial for run statistics, QC dashboards or interactive tables without interpretation. *AI-assistant access*: an MCP server (or documented LLM tool interface) from the project itself. *Last release*: latest tagged release on GitHub or the official download page; where none exists, the last commit.

**Table notes.**
^a^ The local version is command-line only; the graphical interface requires uploading data to the hosted service.
^b^ HTML run summary with variant-consequence statistics and charts; no interpretation of individual findings.
^c^ No Ensembl MCP server; third-party wrappers exist (e.g. VEPmcp), which call the Ensembl REST API rather than a local VEP.
^d^ The 2025-03-02 software update is announced without a version label.
^e^ OakVar is a fork of OpenCRAVAT; Generation I of Just-DNA-Seq was built on it, and its author is a co-author of this paper.
^f^ Users select from ANNOVAR's database list in the interface; adding an own source is not documented.
^g^ Interactive tables and plots (VCFshiny) or ACMG-guided tiering for clinicians (ACVI-Med); no exported narrative report described.
^h^ Custom named-allele definitions (JSON) for pharmacogene diplotype calling only.
^i^ Additional sources are added at the VEP annotation step (`--custom`); the importer then indexes any INFO/CSQ field without code.
^j^ A PGS Catalog score is added by one line in a configuration table; the annotation databases are a fixed set.
^k^ Not a variant-annotation tool.
^l^ Generic score files (variant, allele, weight); the documentation does not mention the PGS Catalog format, which needs column mapping.
^m^ Computes PRS from GWAS summary statistics by clumping and thresholding; precomputed weights can be supplied (`--no-clump`) but the PGS Catalog is not mentioned.
^n^ Plots of model fit across a cohort, not a per-person result.
^o^ No release since 2021; occasional fixes to 2026-04-10, and the site states the software is being rebuilt.
^p^ The README states that whole-genome sequencing VCFs are not currently supported directly (gVCF conversion suggested).
^q^ HTML report of score distributions and variant-matching QC across samples, not a per-person narrative.
^r^ Scores are standardised against an ancestry-matched reference (PC projection); percentiles are not described.
^s^ Ancestry is estimated, but used only to warn about or exclude mismatched samples.
^t^ Uses NHGRI-EBI GWAS Catalog associations, not PGS Catalog scoring files; user summary statistics accepted.
^u^ Percentile against a user-chosen cohort (UK Biobank by default; 1000 Genomes superpopulations available), not matched automatically.
^v^ Tabular output with standardised scores or percentiles; interactive web views (PGS Browser) or website plots limited to precomputed data (PRSKB).
^w^ A hosted Shiny application that takes the locally computed percentile, sex and age; the genome never reaches it, and scoring itself is command line.
^x^ Scores adjusted for the first five genetic principal components; the reference distribution is FinnGen.
^y^ The VCF stays local, but tool responses (genotypes, interpretations) go to the user's LLM provider unless a local model is used; the same boundary applies to Just-DNA-Lite's MCP server.
^z^ A structured genome summary tool; narrative text comes from the client's language model.
^aa^ Exomiser runs on the VCF locally; the reasoning tier calls a commercial LLM API unless the code is adapted, and the authors recommend their hosted application.
^bb^ The paper describes the agent architecture as "inspired by" MCP; no MCP server is offered to outside clients.

^cc^ Prebuilt annotation modules install from a store through the interface; authoring a new annotator requires editing a Python file.
^dd^ Interactive result viewer and tabular, Excel or VCF reporters; no narrative report described in the core documentation.
^ee^ An official MCP server (Oct 2025) hosted at mcp.opencravat.org, which annotates single variants through public OpenCRAVAT services; it has no access to a user's local genome or jobs.
^ff^ Not mentioned in OakVar's own documentation. An OakVar module from the authors' Generation I Just-DNA-Seq (Kulaga et al., 2024) computed PGS Catalog scores as percentiles against simulated gnomAD-frequency genotypes, without ancestry matching.
^gg^ No licence file in the repository; the paper describes the pipeline as "fully open source".
^hh^ Promethease has been owned by MyHeritage since 2019; reports cost US$25. SNPedia editing has been sparse since 2023.
^ii^ Scores from GWAS summary statistics and LDpred weights for 1,859 GWAS and 634 UK Biobank traits; the PGS Catalog is not mentioned.
^jj^ The site redirects to a commercial service (Nucleus Genomics) since June 2022; the repository now holds only a README.

**Cell convention.** "No" means the project's documentation or paper, read in full, describes the tool's scope without the feature; "?" means the material available did not settle it.

---

## 2. Evidence notes (all accessed 2026-10-10)

### Just-DNA-Lite (own row; from the repository at commit a3fa348)
- **Runs locally: Yes.** README.md, "Upload a genome file ... The app runs on your computer. The file stays there."; installation via `uv run start` on Linux, macOS and Windows. Paper §5.2: reference datasets are downloaded and cached, the genome is not uploaded. Caveat carried in note y: MCP tool outputs reach whatever model provider the assistant uses (docs/MCP_SERVER.md, "What the agent reads, however, goes to whichever model provider the agent uses").
- **Graphical interface: Yes (local web UI).** Reflex app in `webui/`; README "Open the address the terminal prints, usually http://localhost:3000".
- **Add annotation sets without code: Yes.** A module is `module_spec.yaml` plus CSV tables (`variants.csv`, `studies.csv`, ...) compiled by just-dna-compiler (paper §2.2). The web UI accepts an uploaded module folder and registers it (`webui/src/webui/state.py:5934`, `register_custom_module`, defined in `just-dna-pipelines/src/just_dna_pipelines/module_registry.py:130`). Compiled modules are also discovered from any fsspec source listed in `modules.yaml` and installed from the registry (https://module-registry.just-dna.life).
- **PRS (PGS Catalog): Yes.** just-prs (>=0.10.0, `pyproject.toml`), paper §3.2: "access to all 5,000+ scoring files in the PGS Catalog".
- **Ancestry-aware percentiles: Yes.** Paper §3.2: scores of the 3,202 individuals of the 1000 Genomes panel summarised per superpopulation (AFR, AMR, EAS, EUR, SAS); the web UI infers the sample's superpopulation with `catalog.infer_sample_ancestry` (`webui/src/webui/state.py:4637`) and the user can choose another.
- **Human-readable report: Yes.** HTML report rendered from `just-dna-pipelines/src/just_dna_pipelines/annotation/templates/longevity_report.html.j2`, written for lay and professional readers (docs/REPORT_VOICE.md).
- **AI-assistant (MCP) access: Yes.** `just_dna_pipelines.lite_mcp` (`uv run pipelines mcp`, stdio or HTTP; docs/MCP_SERVER.md) lists samples and modules, installs modules, runs annotation jobs and returns results; just-prs-mcp exposes PRS operations (paper §3.2.1).
- **Licence:** AGPL-3.0 (`LICENSE`).
- **Last release:** GitHub release v0.3.18, 2026-08-16 (`gh release list -R dna-seq/just-dna-lite`). The `main` branch is at 0.3.25 (`pyproject.toml`), unreleased.

### Ensembl VEP
- Docs index: https://www.ensembl.org/info/docs/tools/vep/index.html (now redirects to https://jun2026.archive.ensembl.org/info/docs/tools/vep/index.html): "Web interface: Point-and-click interface", "Command line tool ... For large volumes of data", "REST API". Scope: "predicts the effect of your variants (SNPs, insertions, deletions, CNVs or structural variants)".
- Web input: .../vep/online/input.html (file upload, pasted data or URL; no own annotation files in the web form).
- Custom annotation: .../vep/script/vep_custom.html: "Ensembl VEP can integrate custom annotation from standard format files into your results by using the --custom flag" (BED, GFF, GTF, VCF tabix-indexed; bigWig).
- Report: .../vep/vep_formats.html, `[output_file]_summary.html` with run statistics and charts.
- Licence: https://github.com/Ensembl/ensembl-vep (LICENSE, Apache License 2.0).
- Release: https://github.com/Ensembl/ensembl-vep/releases, release/116.3, 2026-10-09. Ignore the stray tag `release/168` (a 2024 Docker workflow commit).
- MCP: none from Ensembl; third-party VEPmcp (https://github.com/not-a-feature/VEPmcp) and effieklimi/ensembl-mcp-server wrap the REST API.
- No VEP paper newer than 2016 found; the documentation still cites McLaren et al. (2016).

### ANNOVAR
- Download and licence: https://annovar.openbioinformatics.org/en/latest/user-guide/download/ ("registration required"); https://www.openbioinformatics.org/annovar/annovar_download_form.php: "freely available to personal, academic and non-profit use only"; commercial users license from QIAGEN.
- Custom databases: .../user-guide/filter/ ("Users have the flexibility to supply a custom-made annotation file", `-dbtype generic`, `-dbtype vcf`); .../user-guide/region/ ("use the BED file as database directly").
- Output: .../user-guide/startup/ (`*_multianno.txt`, `*_multianno.vcf`, CSV); no report.
- Hosted: https://wannovar.wglab.org/ (submission to the web server, results by email; updated to the 2024 version on 2024-07-12).
- Release: docs home news entry 2025Mar02, "new ANNOVAR version is available" (previous software release 2020Jun08; database updates continue to 2026-09-25).

### SnpEff / SnpSift
- https://pcingola.github.io/SnpEff/: "Genetic variant annotation, and functional effect prediction toolbox"; "Latest version 5.4c (2026-02-23)".
- SnpSift annotate: https://pcingola.github.io/SnpEff/snpsift/annotate/: "Annotate using fields from another VCF file (e.g. dbSnp, ClinVar, ExAC, etc.)".
- Summary HTML: https://pcingola.github.io/SnpEff/snpeff/outputsummary/ (run statistics).
- Licence: https://pcingola.github.io/SnpEff/license/: "released as MIT".
- No GUI documented (Galaxy wrappers are third party).

### vcfanno
- https://github.com/brentp/vcfanno (README): "annotate your VCF with any number of INFO fields from any number of VCFs or BED files. It uses a simple conf file"; "Users can add as many [[annotation]] blocks to the conf file as desired"; "We are actively developing vcfanno". Licence MIT. Release v0.3.9, 2026-06-16 (GitHub releases).

### echtvar
- https://github.com/brentp/echtvar (README): "Users can make their own echtvar archives with `echtvar encode`", configured by a JSON5 field list. Licence MIT. Release v0.2.4, 2026-04-30 (GitHub releases).

### OpenCRAVAT
- Docs https://docs.opencravat.org/en/latest/index.html: "There is a web-based version of OpenCRAVAT (https://run.opencravat.org) but it can also be installed locally"; quickstart (.../quickstart.html): "The web interface is started by running a local web server, then connecting it using a browser."
- Authoring: .../Annotator-Tutorial.html: `oc new annotator`, load data into SQLite, then edit `annotate()` in `<modulename>.py`.
- PRS: the store catalogue https://store.opencravat.org/manifest.yml (336 modules) contains no polygenic or PGS module.
- Report: store manifest lists Excel, TSV, CSV, text and VCF reporters and a variant report web app.
- MCP: README https://github.com/KarchinLab/open-cravat ("Announcing the OpenCRAVAT MCP Server"); https://github.com/KarchinLab/oc-mcp: "runs as a Cloudflare Worker ... and proxies requests to public OpenCRAVAT services" (coordinate, rsID, CAid or HGVS; GRCh38).
- Licence: LICENSE, "MIT License Copyright (c) 2025 KarchinLab".
- Release: PyPI open-cravat 3.2.1, 2026-10-08 (GitHub release 3.2.0, 2026-10-07). No 2023–2026 tool paper found in Europe PMC.

### OakVar
- Docs https://rkimoakbioinformatics.github.io/oakvar/install_system/ (`pip install oakvar`); .../oakvar/gui/ ("launched by ov gui ... A web server will be started"); .../oakvar/devguide_modules/ (an annotator implements `annotate()` in a Python file); .../oakvar/ai_ml/ (DataFrame export only, no LLM or MCP).
- Licence: https://github.com/rkimoakbioinformatics/oakvar LICENSE: "Copyright (c) 2024 Oak Bioinformatics, LLC All rights reserved ... For personal use of non-commercial nature, you may use this software after registering". The first LICENSE (2022) was BSD-3-Clause; relicensed in steps from 2022-08 to 2024-11.
- Release: PyPI oakvar 2.13.1, 2026-08-30 (last GitHub release object v2.12.24, 2026-01-26). No OakVar paper found.
- Conflict of interest: Ryangguk Kim, OakVar's author and co-founder of Oak Bioinformatics, is a co-author of this paper; Generation I of Just-DNA-Seq was built on OakVar.

### GenomeChronicler
- Paper https://www.frontiersin.org/articles/10.3389/fgene.2020.518644/full: "The analysis can be run in a self-contained environment without requiring internet access"; "The main output of GenomeChronicler is a report in PDF format" (SNPedia, ClinVar, GET-Evidence, gnomAD), plus an Excel file; ancestry PCA against 1000 Genomes; "A set of scripts to regenerate these SQLite databases is also provided"; no PRS.
- Repo https://github.com/PGP-UK/GenomeChronicler: Docker/Singularity CLI (`--bamFile`, `--vcfFile`, `--customTemplate` for LaTeX layout); no LICENSE file; release 0.91, 2019-10-26; dormant 2023-10 to 2026-07-09 (two merged PRs).

### SNPedia / Promethease
- https://promethease.com: "builds a personal DNA report based on connecting a file of DNA genotypes to the scientific findings cited in SNPedia ... Most reports cost $25"; report "will be emailed to me as an attachment".
- https://promethease.com/privacy (last update April 15 2025): "MyHeritage Ltd. ... has acquired Promethease. See blog post from September 2019".
- SNPedia:Copyrights (read through https://bots.snpedia.com MediaWiki API): content under "Creative Commons Attribution-Noncommercial-Share Alike 3.0 United States License". Sample HTML reports at files.snpedia.com/reports/promethease_data/.
- No mention of polygenic scores or AI access on the pages read.

### impute.me
- Paper https://www.frontiersin.org/articles/10.3389/fgene.2020.00578/full: users "upload it at impute.me"; "1,859 traits from genome-wide association studies"; "weightings from the LDpred algorithm"; scores "scaled such that the mean of a population is zero and the standard deviation (SD) is 1, according to the relevant 1000 Genomes super-population"; JSON summary of all calculations.
- Archived repo https://web.archive.org/web/20211224132708/https://github.com/lassefolkersen/impute-me: "LGPL-3.0 License", "v1.0.7 Latest Nov 2, 2021", local Docker route.
- Discontinued: Wayback snapshots show the site live on 2022-05-16 and redirecting to https://mynucleus.com from 2022-06-13 (still on 2026-10-10); current README: "Impute.me have been moved to https://mynucleus.com".
- DNA.Land (Yuan et al., 2018), mentioned in the paper's lineage, closed as an academic project on 2019-09-30 (DNA Land Medium post, 2019-09-16, via web.archive.org/web/20191017030642); not tabulated.

### VCFshiny
- Paper: https://academic.oup.com/bioinformaticsadvances/article/3/1/vbad107/7252269: launched locally with `startVCFshiny()`; users "annotate, filter, visualize, and export variants without any programming knowledge requirement"; "two annotation methods, Annovar and VariantAnnotation"; results "presented in a data table format"; "available under an MIT open source license".
- Repo: https://github.com/123xiaochen/VCFshiny (the paper prints github.com/123xiaochen/VCF-shiny). No tags; last code commit 2024-10-16; README-only commits 2026-07-01.

### PharmCAT
- https://pharmcat.clinpgx.org/ and https://pharmcat.clinpgx.org/using/Running-PharmCAT/: `java -jar ... -vcf <vcf_file>`; Docker; custom named-allele definitions via `-def <dir>`; HTML report "the default if no format is specified"; scope is star alleles, diplotypes, phenotypes and CPIC/DPWG/FDA recommendations. Licence MPL-2.0 (https://github.com/PharmGKB/PharmCAT). Release v3.4.0, 2026-07-14.

### ACVI-Med
- Paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC13069756/: "containerized client-server software platform" that "can be institutionally self-hosted"; "Users access the application via their web browser"; "published under the MIT license"; "currently restricted to research use". The backend queries PanelApp, HPO and ClinGen daily.
- Repo: https://github.com/moritzstadler/acvi-med ("Only annotated files can be imported"; VEP `--custom` in ANNOTATION.md). No tags; last commit 2026-05-28.
- Aimed at clinical teams (multi-user, trio filtering), not at individuals.

### Personal-Genome-Pipeline
- https://github.com/GeiserX/Personal-Genome-Pipeline (README): "Everything runs locally in Docker containers"; "No script uploads your data"; "Ends in an HTML report and a MultiQC summary"; GPL-3.0-or-later.
- docs/25-prs.md: scores via pgsc_calc from PGS Catalog GRCh38-harmonised files; "To add a score, add a line to assets/pgs_scores.tsv"; "each score is also given as a percentile: where your score falls among the reference samples whose genetic ancestry is most similar to yours".
- docs/30-vcfanno.md: fixed set of annotation databases (CADD, SpliceAI, REVEL, AlphaMissense).
- No GUI, no MCP or LLM component in the repository tree. Release v0.8.2, 2026-07-01; created 2026-03-30. No peer-reviewed paper.

### PLINK 2
- https://www.cog-genomics.org/plink/2.0/score: generic score file (variant ID column, allele column, coefficient column); no mention of the PGS Catalog; points to LDpred2 and PRSice-2 for more sophisticated PRS. No percentile or reference-population output on that page.
- Licence: https://github.com/chrchang/plink-ng/blob/master/2.0/COPYING (GPL-3.0; bundled libraries LGPL-3.0).
- Release: v2.0.0-a.7.11, 2026-10-01 (GitHub releases; the site lists "Alpha 7.11 (1 Oct)").

### PRSice-2
- https://choishingwan.github.io/PRSice/ and .../command_detail/: "High-resolution scoring (PRS calculated across a large number of P-value thresholds)"; `--base` GWAS summary statistics; `--no-clump`; `--no-regress`; results "plotted in several formats (bar plots, high-res plots, quantile plots)". The site states: "We are currently re-building PRSice with best practices".
- Licence GPL-3.0; release 2.3.5, 2021-09-20; last commit 2026-04-10 (https://github.com/choishingwan/PRSice).

### pgsc_calc
- https://pgsc-calc.readthedocs.io/en/latest/: "calculate a polygenic score (PGS) using scoring files published in the Polygenic Score (PGS) Catalog"; Apache 2.0; Nextflow with Docker/Singularity/Conda.
- Ancestry: .../explanation/geneticancestry.html (1000 Genomes reference, PCA, Random Forest); .../explanation/output.html (`percentile_MostSimilarPop`, Z_norm1, Z_norm2; `report.html` "should open in a web browser"). Enabled with `--run_ancestry`.
- Custom scores: .../how-to/calculate_custom.html (`--scorefile`).
- README https://github.com/PGScatalog/pgsc_calc: whole-genome sequencing data are not currently supported directly.
- Release v2.3.0, 2026-06-03 (pre-release v3.0.0-alpha.1, 2025-12-10).

### GenoPred
- https://opain.github.io/GenoPred/pipeline_readme.html: Snakemake with conda, Docker/Singularity containers; "PGS Catalogue score files can be directly downloaded by GenoPred, by using the PGS ID"; `[target_name]-report.html` and per-individual reports (`indiv_report = T`).
- https://opain.github.io/GenoPred/pipeline_technical.html: "target sample scores are standardised according to the mean and SD of the score in an ancestry-matched reference".
- Licence GPL-3.0; release v2.3.3, 2025-11-27 (https://github.com/opain/GenoPred).

### Imputation Server PGS / pgs-calc
- https://imputationserver.readthedocs.io/en/latest/pgs/getting-started/: data "uploaded from your local file system to Michigan Imputation Server".
- Paper https://academic.oup.com/nar/article/52/W1/W70/7665593: browser workflow after upload; "also available as a standalone tool called pgs-calc"; ancestry estimated by kNN in HGDP PCA space and used for warnings and exclusion.
- https://github.com/lukfor/pgs-calc: "supports PGS Catalog format", `--report-html`, own weight files; MIT; v1.6.2, 2025-10-28. Server: https://github.com/genepi/imputationserver2 v2.0.12, 2026-03-12.

### PRSKB
- Paper https://pmc.ncbi.nlm.nih.gov/articles/PMC9438378/: "Polygenic risk scores are calculated client-side, meaning no private data ever reaches our servers"; TSV output; website visualisations only for precomputed scores.
- README https://github.com/kauwelab/PolyRiskScore: GWAS Catalog associations; users may upload their own GWAS summary statistics; "freely available for academic and not-for-profit use. However, commercial use is regulated by © 2020 Brigham Young University."
- Docs https://polyriskscore.readthedocs.io/en/latest/: `-q` cohort for percentile rank, default UK Biobank, also AFR, AMR, EAS, EUR, SAS, ADNI.
- Release v1.0.0, 2022-06-23; last commit 2024-08-22; https://prs.byu.edu/ online.

### PGS Browser / pgsb-cli
- Paper https://pmc.ncbi.nlm.nih.gov/articles/PMC13439439/: pgsb-cli is a "Docker-based command-line tool that runs locally"; "only these aggregated percentiles need to be sent to the web interface"; web app built with Shiny; reference distributions from FinnGen; PGS Catalog models.
- README https://github.com/ArtomovLab/PGS_Browser: "Data are processed locally and are never sent to external servers!"; PC1–PC5 ancestry adjustment; CC BY-NC-ND 4.0. The repository holds the Docker wrapper script, not the CLI source. No tags; last commit 2026-05-14. https://pgs.nchigm.org/ online.

### GeneChat MCP
- https://github.com/natecostello/genechat-mcp (README): "a local-first MCP server that annotates your whole-genome VCF once, then serves it as tools"; "tool responses ... are sent to your LLM provider"; `calculate_prs` with PGS Catalog weights (four scores in `data/seed/prs_weights.tsv`); `src/genechat/tools/calculate_prs.py` notes that "percentile ranking requires a reference population"; fixed annotation flags (`--clinvar --gnomad --snpeff --dbsnp`); MIT. No tags, not on PyPI; last commit 2026-04-13. No paper.

### DeepRare
- Preprint https://arxiv.org/html/2506.20430v2: genotype input is "the raw Variant Call Format (VCF) file generated from Whole Exome Sequencing"; web application at http://raredx.cn by access request; reports "exported as PDF or Word documents"; system "inspired by the Model Context Protocol (MCP)".
- Repo https://github.com/MAGIC-AI4Med/DeepRare: CC BY-NC 4.0; local LLM requires modifying `api/interface.py`; last commit 2026-04-14. Clinical rare-disease diagnosis, included as the nearest peer-reviewed LLM system operating on an individual's VCF.

### Considered and not tabulated
- genome-mcp (Noella-John1997): three commits, about 15 variants, self-described educational project; superseded by GeneChat.
- BioChef (BMC Bioinformatics 2026, doi:10.1186/s12859-026-06431-1): in-browser workflow builder; no personal-genome interpretation.
- BioVault web app: claims in-browser analysis but names no source code, licence or organisation.
- VarChat (Bioinformatics 2024, doi:10.1093/bioinformatics/btae183): single-variant LLM summaries, hosted only, no source.
- GeneGPT, GeneAgent, CIViC MCP and other knowledge-base MCP servers: query databases or gene sets, do not take a personal VCF.
- MySeq (2019): in-browser and comparable, but outside the 2023–2026 window.
- Commercial services (DNA Complete, Dante Labs, Sequencing.com): proprietary, upload-based; already discussed in the Introduction.

---

## 3. Discussion paragraph

Table X lists the features that tools for personal-genome annotation and polygenic scoring document for themselves, as of 10 October 2026. Variant annotation engines such as VEP, ANNOVAR, SnpEff, vcfanno and echtvar accept new annotation files through configuration, but they write annotated variant files rather than reports and do not compute polygenic scores, while pgsc_calc and GenoPred score PGS Catalog models against ancestry-matched references from the command line without annotating variants against curated trait tables. Several projects combine parts of both: OpenCRAVAT and OakVar offer local web interfaces with installable annotation modules, Personal-Genome-Pipeline joins local annotation and pgsc_calc scoring in an HTML report, PGS Browser computes scores locally and interprets percentiles on a hosted page, and GeneChat and the OpenCRAVAT MCP server make variant annotation available to AI assistants. Among the tools surveyed, Just-DNA-Lite is the one whose documentation describes all of these features together; the table records whether a feature is documented, not how well it works, and does not compare annotation content, score validity or usability.

---

## 4. Reference entries to add

Paper style (author, year, title, *journal*, volume(issue), pages, doi). All DOIs resolved through https://doi.org and matched against https://api.crossref.org/works/<doi> (plain URLs, no contact parameters) on 2026-10-10. Entries marked † are 2023–2026.

Cariaso, M., & Lennon, G. (2012). SNPedia: a wiki supporting personal genome annotation, interpretation and analysis. *Nucleic Acids Research*, 40(D1), D1308–D1312. doi:10.1093/nar/gkr798.
Chang, C. C., Chow, C. C., Tellier, L. C. A. M., Vattikuti, S., Purcell, S. M., & Lee, J. J. (2015). Second-generation PLINK: rising to the challenge of larger and richer datasets. *GigaScience*, 4, 7. doi:10.1186/s13742-015-0047-8.
† Chen, T., et al. (2023). VCFshiny: an R/Shiny application for interactively analyzing and visualizing genetic variants. *Bioinformatics Advances*, 3(1), vbad107. doi:10.1093/bioadv/vbad107. (Already in the v0.3 reference additions.)
Choi, S. W., & O'Reilly, P. F. (2019). PRSice-2: Polygenic Risk Score software for biobank-scale data. *GigaScience*, 8(7), giz082. doi:10.1093/gigascience/giz082.
Cingolani, P., Platts, A., Wang, L. L., Coon, M., Nguyen, T., Wang, L., Land, S. J., Lu, X., & Ruden, D. M. (2012a). A program for annotating and predicting the effects of single nucleotide polymorphisms, SnpEff: SNPs in the genome of *Drosophila melanogaster* strain w1118; iso-2; iso-3. *Fly*, 6(2), 80–92. doi:10.4161/fly.19695.
Cingolani, P., Patel, V. M., Coon, M., Nguyen, T., Land, S. J., Ruden, D. M., & Lu, X. (2012b). Using *Drosophila melanogaster* as a model for genotoxic chemical mutational studies with a new program, SnpSift. *Frontiers in Genetics*, 3, 35. doi:10.3389/fgene.2012.00035. (Crossref gives no article number; 35 is taken from the DOI suffix.)
Folkersen, L., Pain, O., Ingason, A., Werge, T., Lewis, C. M., & Austin, J. (2020). Impute.me: an open-source, non-profit tool for using data from direct-to-consumer genetic testing to calculate and interpret polygenic risk scores. *Frontiers in Genetics*, 11, 578. doi:10.3389/fgene.2020.00578.
† Forer, L., Taliun, D., LeFaive, J., Smith, A. V., Boughton, A. P., Coassin, S., Lamina, C., Kronenberg, F., Fuchsberger, C., & Schönherr, S. (2024). Imputation Server PGS: an automated approach to calculate polygenic risk scores on imputation servers. *Nucleic Acids Research*, 52(W1), W70–W77. doi:10.1093/nar/gkae331.
Guerra-Assunção, J. A., Conde, L., Moghul, I., Webster, A. P., Ecker, S., Chervova, O., Chatzipantsiou, C., Prieto, P. P., Beck, S., & Herrero, J. (2020). GenomeChronicler: the Personal Genome Project UK genomic report generator pipeline. *Frontiers in Genetics*, 11, 518644. doi:10.3389/fgene.2020.518644.
† Kolosov, N., Reeve, M. P., Della Briotta Parolo, P., Kurki, M. I., Llorens, V., Sipilä, T. P., Herman, A., Molotkov, I., Aavikko, M., Ripatti, S., Palotie, A., Daly, M. J., & Artomov, M. (2026). PGS Browser: a public platform for personalized polygenic score analysis and interpretation. *Nature Communications*, 17, 7806. doi:10.1038/s41467-026-74461-7.
† Lambert, S. A., Wingfield, B., Gibson, J. T., et al. (2024). Enhancing the Polygenic Score Catalog with tools for score calculation and ancestry normalization. *Nature Genetics*, 56(10), 1989–1994. doi:10.1038/s41588-024-01937-x.
† Li, B., Sangkuhl, K., Keat, K., Whaley, R. M., Woon, M., Verma, S., Dudek, S., Tuteja, S., Verma, A., Whirl-Carrillo, M., Ritchie, M. D., & Klein, T. E. (2023). How to run the Pharmacogenomics Clinical Annotation Tool (PharmCAT). *Clinical Pharmacology & Therapeutics*, 113(5), 1036–1047. doi:10.1002/cpt.2790.
McLaren, W., Gil, L., Hunt, S. E., Riat, H. S., Ritchie, G. R. S., Thormann, A., Flicek, P., & Cunningham, F. (2016). The Ensembl Variant Effect Predictor. *Genome Biology*, 17, 122. doi:10.1186/s13059-016-0974-4.
Page, M. L., Vance, E. L., Cloward, M. E., et al. (2022). The Polygenic Risk Score Knowledge Base offers a centralized online repository for calculating and contextualizing polygenic risk scores. *Communications Biology*, 5, 899. doi:10.1038/s42003-022-03795-x.
Pagel, K. A., Kim, R., Moad, K., Busby, B., Zheng, L., Tokheim, C., Ryan, M., & Karchin, R. (2020). Integrated informatics analysis of cancer-related variants. *JCO Clinical Cancer Informatics*, 4, 310–317. doi:10.1200/CCI.19.00132.
† Pain, O., Al-Chalabi, A., & Lewis, C. M. (2024). The GenoPred pipeline: a comprehensive and scalable pipeline for polygenic scoring. *Bioinformatics*, 40(10), btae551. doi:10.1093/bioinformatics/btae551.
Pedersen, B. S., Layer, R. M., & Quinlan, A. R. (2016). Vcfanno: fast, flexible annotation of genetic variants. *Genome Biology*, 17, 118. doi:10.1186/s13059-016-0973-5.
† Pedersen, B. S., & de Ridder, J. (2023). Echtvar: compressed variant representation for rapid annotation and filtering of SNPs and indels. *Nucleic Acids Research*, 51(1), e3. doi:10.1093/nar/gkac931.
Sangkuhl, K., Whirl-Carrillo, M., Whaley, R. M., et al. (2020). Pharmacogenomics Clinical Annotation Tool (PharmCAT). *Clinical Pharmacology & Therapeutics*, 107(1), 203–210. doi:10.1002/cpt.1568.
† Stadler, M., Gansberger, S., Borik-Heil, L., Griss, J., Okamoto, I., Weninger, W. P., & Wielscher, M. (2026). ACVI-Med, an open source variant interpretation tool for medical genomics. *BMC Bioinformatics*, 27, 85. doi:10.1186/s12859-026-06414-2.
Wang, K., Li, M., & Hakonarson, H. (2010). ANNOVAR: functional annotation of genetic variants from high-throughput sequencing data. *Nucleic Acids Research*, 38(16), e164. doi:10.1093/nar/gkq603.
† Zhao, W., Wu, C., Fan, Y., et al. (2026). An agentic system for rare disease diagnosis with traceable reasoning. *Nature*, 651(8106), 775–784. doi:10.1038/s41586-025-10097-9.

Software without a paper (cite as software, accessed 10 October 2026):
† Costello, N. (2026). GeneChat MCP server [software]. https://github.com/natecostello/genechat-mcp.
† GeiserX (2026). Personal-Genome-Pipeline, version 0.8.2 [software]. https://github.com/GeiserX/Personal-Genome-Pipeline.
† KarchinLab (2025). OpenCRAVAT MCP server [software]. https://github.com/KarchinLab/oc-mcp.
† Oak Bioinformatics (2026). OakVar, version 2.13.1 [software]. https://github.com/rkimoakbioinformatics/oakvar.

Already cited in Paper 1 and used in the table: Kulaga et al. (2024), Just-DNA-Seq (for note ff). Author names for the GitHub-only entries are the repository owners' handles or display names; confirm before submission.
