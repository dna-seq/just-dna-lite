# Richer Ensembl annotation for just-dna-lite: split-parquet layout built from the new Ensembl variation VCF

**Date:** 2026-11-03
**Status:** IN PROGRESS (research and sample measurements done; no repo code changed yet)
**Bead(s):** none (no beads database in this repo)
**Epic:** none
**Chain:** `standalone-91828aa3` seq `1`
**Parent:** `none — first in chain`
**Prior chain:** none — first in chain

---

## Reference Documents

- `CLAUDE.md` (repo root): project conventions. Relevant sections: "Dagster pipeline → Ensembl cache",
  "Shared format libraries" (the enricher's DuckDB Ensembl `resolver`), "Coding standards", "Tests".
- `docs/DAGSTER_GUIDE.md`: asset/job layout for `annotate_all_job` and `annotate_ensembl_only_job`.
- `modules.yaml`: `ensembl_source.repo_id: just-dna-seq/ensembl_variations` (never hardcode it; read
  `MODULES_CONFIG.ensembl_source.repo_id`).

## The Goal

just-dna-lite's optional "Ensembl annotation" step joins a person's normalized VCF against a 13.7 GB
parquet cache (`just-dna-seq/ensembl_variations` on HuggingFace). The user's complaint: that cache
mostly carries **boolean flags** ("is in ClinVar", `CLIN_pathogenic`, `E_gnomAD`...), which is useless for
general annotation. The goal is a richer, still-downloadable, DuckDB-friendly reference built from the
**new Ensembl platform's precomputed variation VCF** (VEP 116 consequences, ClinVar significance, REVEL,
AlphaMissense, CADD, SpliceAI, gnomAD v4.1 per-population AF), split into several parquet "column
groups" so users download only what they need. The immediate task for the next session (running on a
server with bandwidth/disk) is to **prototype the layout on all of chr21 and benchmark it** against the
current single-table join.

## Where We Are

- **Ensembl beta is now the main site.** `beta.ensembl.org` 301-redirects to `www.ensembl.org`; switch-over
  August 2026. **Ensembl 116 (June 2026) is the last classic release**; classic FTP, REST, Perl API, MySQL
  and VEP caches are frozen at 116. New model: rolling "partial releases" bundled into dated
  "integrated releases" (first: 2026-07).
- **The new human GRCh38 variation VCF** (verified by HEAD + reading records):
  `https://ftp.ebi.ac.uk/pub/ensemblorganisms/GCA/000/001/405/29/ensembl/2026_04/variation/2026_07_13/variation.vcf.gz`
  — 133 GB, bgzipped, has `.tbi`, Last-Modified 2026-07-21. dbSNP 157 variants run through VEP 116
  (GENCODE 50, ClinVar 202509, COSMIC 102). Ensembl says the FTP path layout "will likely change".
- **CSQ field has 135 pipe-separated subfields** (full list in Evidence). Key ones: `Consequence`,
  `IMPACT`, `SYMBOL`, `Gene`, `Feature`, `BIOTYPE`, `HGVSc`, `HGVSp`, `SIFT`, `PolyPhen`, `CLIN_SIG`,
  `PUBMED`, `PHENO`, `PHENOTYPES`, `CADD_PHRED`, `CADD_RAW`, `REVEL`, four SpliceAI DS + four DP,
  `am_class`, `am_pathogenicity`, `ClinPred`, `MaveDB_score`, `MaveDB_urn`, and ~65 gnomAD exomes/genomes
  AF/AC/AN fields per population.
- **Other INFO fields:** `SOURCE`, `END`, `SVLEN`, `NODEID`, `RAF` (gnomAD genomes 4.1 AF),
  `NTCSQ`, `NRCSQ`, `NGENE`, `NVPHN`, `NGPHN`, `NCITE`.
- **VEP was run with `--gencode_primary`**: only GENCODE Primary transcripts; **no MANE_SELECT or
  CANONICAL** fields. CADD header says non-commercial use only.
- **ClinVar in the new file is real values, not flags**, but: `CLIN_SIG` is attached to the **rsID**, not
  the allele (rs80357906 shows `risk_factor&pathogenic&uncertain_significance`); **no review status,
  no ClinVar ID, no disease name**. `PHENOTYPES` is mostly gene-level noise (every BRCA1 record lists the
  same Cancer Gene Census tumour types). **HGVSc/HGVSp were empty in every coding record sampled**
  (BRCA1 chr17:43,057,050-43,057,075).
- **Current cache explained** (inspected `~/.cache/just-dna-pipelines/ensembl_variations/data/homo_sapiens-chr21.parquet`):
  14,433,262 rows, 118 row groups, ZSTD. Columns: `chrom, start, end, id, ref, alt, alts, qual, filter`,
  ~30 booleans (`COSMIC_101, ClinVar_202502, dbSNP_156, HGMD-PUBLIC_20204, E_*, CLIN_*`), `TSA, MA, MAF,
  MAC, AA`. `id`+`start`+`end` = **74% of the bytes**; booleans compress to ~0. No consequence, gene,
  scores or per-population frequency. Total cache 25 files, ~13.7 GB (HF card dated 2026-01-15).
- **Current join code:** `just-dna-pipelines/src/just_dna_pipelines/annotation/logic.py::annotate_vcf_with_duckdb`
  (~line 194). Opens `ensembl_variations.duckdb` read-only, harmonizes chr prefix, then
  `COPY (SELECT v.*, e.* EXCLUDE (join_cols) FROM read_parquet(vcf) v LEFT JOIN {view_name} e ON ...) TO out`.
  The view is created in `annotation/duckdb_assets.py` (~line 104-119):
  `CREATE OR REPLACE VIEW ensembl_variations AS SELECT * FROM read_parquet('{parquet_pattern}', ...)`.
- **Download/verify:** `annotation/ensembl_download.py` (size + SHA256 per file, `.part` then replace,
  `<file>.sha256` stamps). CLI entry points in `src/just_dna_lite/cli.py` (~lines 615-830:
  `download_ensembl_cache`, `_fetch_ensembl_manifest`, duckdb path `ensembl_variations/ensembl_variations.duckdb`).
- **Size measurements done** on a 2 Mb chr21 sample (33-35 Mb): see Evidence tables. Headline: per-allele
  slim parquet ≈ **20 GB** genome-wide, per-transcript slim ≈ **30 GB**, all fields ≈ **100 GB**.
- **Split-layout measurements done** on the same sample: core ≈ 12 GB (7 GB without rsID), consequence
  2.8, clinical 0.1, predictors-without-CADD 1.7, CADD 5.8, freq global 3.7, freq populations 5.8,
  transcripts 7.1 GB.
- **Join benchmark done** (53,364 simulated sample rows): wide 77 ms; split with naive view 249 ms;
  split with sample→core first, then sidecars by `row_idx` **104 ms** (1.35× wide).
- **dbNSFP checked** (site + column list): current release 5.4a (Aug 2026, GENCODE 50 / Ensembl 116),
  86,701,498 nsSNVs + 2,582,202 ssSNVs, 37 predictors, ~50 GB academic zip, CC BY-NC-ND 4.0,
  institutional-email registration. Has full ClinVar columns per allele, MANE flag, VEP+snpEff HGVS.
- **Telegram scan done** ((sci)Berloga Bioinformatics chat, 2,000 messages 2026-10-01..11-03): main
  recommendation was dbNSFP; plus gnomAD, REVEL, SpliceAI, MaveDB, dbSNP VCF. Details in Evidence.
- **Nothing in the repo has been changed.** All test scripts/outputs lived in a local scratchpad that the
  server will not have; the scripts are reproduced verbatim in "Code Analysis" below.

## What We Tried (Chronological)

1. **Search past Claude sessions for an earlier "Ensembl beta / VCF annotation" session** →
   `search_session_transcripts` for "ensembl", "Ensembl release", "ensembl beta", "beta.ensembl", "VEP",
   "vcf annotation", "GENCODE", "archive.ensembl" → nothing matched. Likely a claude.ai chat or deleted
   session. Abandoned; redid the research.
2. **Subagent web research on Ensembl beta** → found the new platform status, the new FTP layout, the
   133 GB VCF, GraphQL has no variant queries, REST not being ported, new web VEP with many plugins
   (AlphaMissense, REVEL, ClinPred, EVE, SpliceAI, CADD, GERP, gnomAD, All of Us, ClinVar, GWAS Catalog,
   GenCC, LOEUF/pLI, later AlphaGenome). Nothing found on command-line VEP caches after 116.
3. **Subagent Telegram scan** (read-only) → dbNSFP the strongest lead; no ready-made local bundle
   recommended. echtvar, FAVOR, Hugging Face variant datasets never came up.
4. **Read the new VCF directly**: first ~3 MB via `curl -r 0-3000000` + `zcat` for header and INFO list
   (25,794 records decoded); then **remote tabix with pysam** (`pysam.TabixFile(URL)`) for BRCA1 and CFTR
   regions. Worked without downloading the 133 GB file. `tabix`/`bcftools` were not installed locally;
   `uv run --with pysam` solved it.
5. **Checked dbNSFP** via `curl https://www.dbnsfp.org/`, `/download`, and
   `https://dist.genos.us/release/dbNSFP5.4a_variant.columns.txt` (509 lines).
6. **Inspected current parquet schema and per-column compressed sizes** (pyarrow metadata over all
   row groups of chr21).
7. **Size estimate, 3 layouts** (`est.py`): tabix-fetch chr21:33,000,000-35,000,000 (761,952 records,
   3.17 GB raw text, 97 MB gzip-6 ≈ bgzip size), explode CSQ, write zstd parquet. Scale factors:
   (a) ratio to 97 MB gzip ≈ ratio to 133 GB; (b) old-cache region (708k rows, 10.3 MB) vs 13.7 GB total.
   Both agreed.
8. **Split column-group sizes** (`split.py`): per-allele table with `row_idx`, sidecars sparse (only rows
   with any non-null value), zstd level 9, row groups 500k.
9. **Join benchmark** (`bench.py`, `bench2.py`) in DuckDB, 8 threads, best of 5:
   - naive view (core LEFT JOIN sidecars, then sample join) → 249 ms (**3.2× slower** than wide). DuckDB did
     NOT push the sample join below the sidecar LEFT JOINs.
   - sample → core first (CTE), then LEFT JOIN sidecars on `row_idx` → 104 ms (1.35×). Same output counts.
   - `core_only` run crashed only in the verification query (output has no `SYMBOL`); timing printed
     before was irrelevant. Not a real failure.

## Key Decisions

- **Split into several parquet column groups joined in DuckDB** (user asked; agreed). Reason is
  **download size and licence isolation, not speed**: parquet is columnar, so one wide file already reads
  only projected columns. If everyone downloaded everything, one wide file would be simpler and faster.
- **Link groups by `(chrom, row_idx)`**, not by repeating chrom/pos/ref/alt/rsID in each file. `row_idx`
  is monotone within a chromosome, so it compresses to almost nothing; repeating keys would cost
  gigabytes (rsID alone ≈ 5 GB).
- **Sidecars are sparse** (only rows with data). ClinVar labels exist for <1% of alleles → 0.1 GB.
- **Query order is mandatory**: sample → core on chrom/pos/ref/alt first, then sidecars on `row_idx`.
  Rejected: a single `ensembl_variations` view that LEFT JOINs everything (3.2× slower measured).
- **A manifest with one release id** for all groups; refuse to join groups from different releases
  (`row_idx` is only valid within one build → silent wrong annotations otherwise).
- **Hive-partition by chromosome**: `core/chrom=21/…parquet`, read with `hive_partitioning=true`.
- **CADD in its own group**: 5.8 GB alone (scores almost every variant) and non-commercial licence.
- **Keep rsID (`id`) and current column names in core**: the enricher's resolver
  (`just_dna_enricher.resolver`, provisioned by `module_compiler/resolver.py::ensure_resolver_db`)
  resolves module rsIDs → coordinates from this cache. Dropping `id` breaks module compilation. Alternative
  considered: a separate rsID→position table used only by the resolver (saves ~5 GB on core).
- **For ClinVar, prefer ClinVar's own GRCh38 VCF** for the `clinical` group (per-allele CLNSIG,
  CLNREVSTAT, CLNDN), because the Ensembl file's `CLIN_SIG` is per rsID with no review status/disease.
- **dbNSFP is complementary, not a replacement**: coding SNVs only (no indels, non-coding, synonymous),
  but every *possible* such SNV (covers novel variants) and 37 predictors + per-allele ClinVar. Licence
  CC BY-NC-ND likely forbids redistributing a derived slim parquet → users would register and download it
  themselves. Not decided.

## Evidence & Data

### Parquet vs VCF (user was confused; clarified)
Parquet does compress. The "1.5×" compared *different content*: new rich per-allele parquet (~20 GB) vs
today's flag-only parquet (13.7 GB). Same content: 133 GB VCF.gz → ~20 GB slim parquet (6-7×).
On identical content (all fields, per transcript) parquet alone gave ~1.3× (133 → ~100 GB); the rest of
the saving comes from per-allele rows, dropping ~100 gnomAD AC/AN columns, and float32 numbers.

### Layout size estimate (chr21:33-35 Mb sample, scaled to genome)

| Layout | Rows in region | Size in region | Genome estimate |
|---|---:|---:|---:|
| Original VCF, gzip-6 of tabix records | 761,952 records | 97 MB | 133 GB |
| Parquet, every CSQ field, per transcript | 2,074,381 | 76.4 MB | ~100 GB |
| Parquet, selected fields, per transcript | 2,074,381 | 22.0 MB | ~30 GB |
| Parquet, selected fields, per allele (most severe IMPACT) | 892,665 | 14.5 MB | ~20 GB |
| Current just-dna-lite parquet (same region) | 707,847 | 10.3 MB | 13.7 GB |

Selected fields: Consequence, IMPACT, SYMBOL, Gene, Feature, BIOTYPE, HGVSc, HGVSp, Amino_acids,
Protein_position, SIFT, PolyPhen, CLIN_SIG, PUBMED, CADD_PHRED, REVEL, am_pathogenicity, am_class,
ClinPred, SpliceAI DS AG/AL/DG/DL, gnomAD exomes AF, gnomAD genomes AF + 8 population AFs (float32).

### Split column groups (same sample, zstd-9, row group 500k, SCALE = 13.7e9 / old-region bytes)

| Group | Rows with data (of 889,400 alleles) | Region | Genome |
|---|---:|---:|---:|
| core (row_idx, pos, ref, alt, id) | 889,400 | 9.1 MB | ~12.1 GB |
| core without rsID | 889,400 | 5.2 MB | ~7.0 GB |
| consequence | 694,689 | 2.1 MB | ~2.8 GB |
| clinical (CLIN_SIG, PUBMED, PHENO, SOMATIC) | 6,615 | 0.0 MB | ~0.1 GB |
| predictors incl. CADD | 855,885 | 4.8 MB | ~6.4 GB |
| predictors without CADD | 393,578 | 1.3 MB | ~1.7 GB |
| CADD only | 841,291 | 4.3 MB | ~5.8 GB |
| freq global (gnomAD exomes/genomes AF) | 499,826 | 2.7 MB | ~3.7 GB |
| freq populations (8 pops × exomes/genomes AF) | 499,813 | 4.3 MB | ~5.8 GB |
| transcripts (all, 10 cols) | 2,074,381 | 5.3 MB | ~7.1 GB |

Non-null counts among 889,400 alleles: SYMBOL 694,689; CLIN_SIG 5,144; REVEL 17,033; CADD 841,291;
gnomAD genomes AF 439,510.

Proposed bundles: default = core + consequence + clinical + predictors(no CADD) + freq ≈ 20 GB
(≈ 15 GB without rsID in core). Optional: CADD (5.8), freq_populations (5.8), transcripts (7.1).

### DuckDB join benchmark (53,364 sample rows = 5% of region alleles + 20% shifted "novel" rows)

| Query | Best of 5 | Output (rows, non-null SYMBOL, non-null REVEL) |
|---|---:|---|
| Sample LEFT JOIN one wide parquet (core+4 groups pre-joined) | 72-77 ms | 53,364 / 35,138 / 891 |
| Sample LEFT JOIN view(core LEFT JOIN 4 sidecars) | 248.6 ms | identical |
| CTE: sample LEFT JOIN core → then LEFT JOIN 4 sidecars on row_idx | 103.5 ms | identical |

Caveat: tiny region and fake sample; real genome scale is dominated by file scan time and must be
re-measured on a whole chromosome with a real normalized VCF.

### Current cache chr21 per-column compressed size (of ~192 MB)

| Column | MB | % |
|---|---:|---:|
| id | 68.0 | 35.4 |
| end | 37.6 | 19.6 |
| start | 37.1 | 19.3 |
| alts.list.element | 11.5 | 6.0 |
| alt | 9.7 | 5.0 |
| ref | 8.1 | 4.2 |
| AA | 7.6 | 3.9 |
| MAF / MAC | 2.3 / 1.9 | 1.2 / 1.0 |
| all ~30 booleans | ≤1.8 each, most 0.0 | ~0 |

In a 200k-row sample: dbSNP_156 true 200,000; E_Freq 195,699; E_gnomAD 70,868; E_TOPMed 28,657;
E_1000G 18,875; ClinVar_202502 0; CLIN_pathogenic 1.

### Sample records from the new VCF (remote tabix, BRCA1 chr17)

```
17 43057062 rs80357906 T TG   frameshift_variant BRCA1 ENST00000357654.9 CLIN_SIG=risk_factor&pathogenic&uncertain_significance CADD 33 gnomAD_exomes_AF 6.90961e-05 (14+ PUBMED ids)
17 43057071 rs397509246 C A,G,T missense_variant CLIN_SIG=likely_pathogenic REVEL 0.768 am_pathogenicity 0.904 CADD 28.2 PUBMED 17308087&12497638&2144777&35132179&40851390
17 43057052 rs80356854 C A,G,T missense&splice_region CLIN_SIG=uncertain_significance REVEL 0.566 AM 0.4042 CADD 32 gnomAD_exomes_AF 6.84131e-07
17 43057058 rs1597810460 G A,C,T synonymous CLIN_SIG=likely_benign CADD 5.663
```
HGVSc/HGVSp empty in all of these. First records of chr1 (pos 10001+) are upstream/downstream MODIFIER
rows with only CADD.

### Full CSQ subfield order (1-based)
1 Allele 2 Consequence 3 IMPACT 4 SYMBOL 5 Gene 6 Feature_type 7 Feature 8 BIOTYPE 9 EXON 10 INTRON
11 HGVSc 12 HGVSp 13 cDNA_position 14 CDS_position 15 Protein_position 16 Amino_acids 17 Codons
18 Existing_variation 19 ALLELE_NUM 20 DISTANCE 21 STRAND 22 FLAGS 23 VARIANT_CLASS 24 SPDI
25 SYMBOL_SOURCE 26 HGNC_ID 27 ENSP 28 SOURCE 29 SIFT 30 PolyPhen 31 AF 32-36 AFR/AMR/EAS/EUR/SAS_AF
37 CLIN_SIG 38 SOMATIC 39 PHENO 40 PUBMED 41 VAR_SYNONYMS 42-46 MOTIF_NAME/MOTIF_POS/HIGH_INF_POS/
MOTIF_SCORE_CHANGE/TRANSCRIPTION_FACTORS 47 CADD_PHRED 48 CADD_RAW 49 REVEL 50-53 SpliceAI_pred_DP_AG/AL/DG/DL
54-57 SpliceAI_pred_DS_AG/AL/DG/DL 58 SpliceAI_pred_SYMBOL 59 PHENOTYPES 60-62 IntAct_feature_type/
interaction_ac/pmid 63 AA 64 MaveDB_score 65 MaveDB_urn 66 am_class 67 am_pathogenicity
68 DownstreamProtein 69 ProteinLengthChange 70 ClinPred 71 gnomAD_exomes 72-74 gnomAD_exomes_AF/AC/AN
75-101 gnomAD_exomes_{AF,AC,AN}_{afr,amr,asj,eas,fin,mid,nfe,remaining,sas} 102 gnomAD_genomes
103-105 gnomAD_genomes_AF/AC/AN 106-135 gnomAD_genomes_{AF,AC,AN}_{afr,ami,amr,asj,eas,fin,mid,nfe,remaining,sas}

### Other Ensembl resources (frozen at 116)
- VEP caches: `https://ftp.ensembl.org/pub/release-116/variation/indexed_vep_cache/` —
  `homo_sapiens_vep_116_GRCh38.tar.gz` 26 GB, merged 28 GB, refseq 25 GB.
- Plugin data (Enformer, LOEUF, MaveDB, SpliceAI, SpliceVault, promoter): `.../release-116/variation/`.
- Per-chromosome classic VCFs `.../release-116/variation/vcf/homo_sapiens/` (chr1 902 MB; only chrMT and
  somatic have `incl_consequences`); clinically_associated 4.3 MB; phenotype_associated 52 MB.
- Older new-FTP human builds: 135 GB (VEP 115, ClinVar 202409), 210 GB (VEP 113).
- GraphQL `https://www.ensembl.org/data/graphql`: gene/transcript/region/genome only, no variants.

### dbNSFP 5.4a facts (from dbnsfp.org and dbNSFP5.4a_variant.columns.txt)
- Columns include: `pos(1-based)` (hg38), `ref`, `alt`, `rs_dbSNP`, `HGVSc_snpEff`, `HGVSp_snpEff`,
  `HGVSc_VEP`, `HGVSp_VEP`, `MANE` (Select/Plus Clinical per transcript), `clinvar_id`, `clinvar_clnsig`,
  `clinvar_trait`, `clinvar_review`, `clinvar_hgvs`, `clinvar_var_source`, `clinvar_MedGen_id`,
  `clinvar_OMIM_id`, `clinvar_Orphanet_id`, `ESM1b_pred`, `AlphaMissense_pred`, …
- 37 predictors: SIFT, SIFT4G, PROVEAN, Polyphen2-HDIV/HVAR, MutationTaster 2021, MutationAssessor,
  FATHMM-XF coding, CADD, VEST4, DANN, MetaSVM, MetaLR, MetaRNN, Eigen, Eigen-PC, M-CAP, REVEL, MutPred2,
  MVP, gMVP, MPC, PrimateAI, DEOGEN2, ALoFT, BayesDel, ClinPred, LIST-S2, VARITY, ESM1b, AlphaMissense,
  PHACTboost, MutFormer, MutScore, MisFit, popEVE, GPN-MSA. Plus PhyloP/phastCons/GERP, frequencies
  (1000G, gnomAD v4.1 + v2.1.1, TOPMed, All of Us, RGC Million Exome, ALFA) and a gene table.
- Also ships a single tabix-indexed BGZF per build for VEP/SnpSift. Academic branch "a", commercial "c".

### Telegram ((sci)Berloga Bioinformatics, chat id -1001140011731, @sberlogabio) — resources mentioned
- dbNSFP + its benchmark page https://www.dbnsfp.org/benchmark/ (MetaRNN leads; "VEP doesn't have all").
- gnomAD for benign/frequency (with a warning against hard AF>0.0001 "benign" cutoffs; biostars 9623349).
- REVEL and SpliceAI as the most useful predictors; skepticism about AlphaMissense.
- MaveDB API (noisy DMS scores), ProteinGym, varianteffect.org VEP atlas (benchmarks, not bulk data).
- Older: dbSNP VCF `https://ftp.ncbi.nih.gov/snp/latest_release/VCF/GCF_000001405.25.gz` (+.tbi), match on
  chrom-pos-ref-alt not rsID; "VEP + ClinVar + dbNSFP, skip ANNOVAR"; MyVariant.info.

## Code Analysis

### Existing code to change (read before editing)
- `just-dna-pipelines/src/just_dna_pipelines/annotation/logic.py::annotate_vcf_with_duckdb` — builds
  `COPY (SELECT v.*, e.* EXCLUDE (join_columns) FROM read_parquet(vcf) v LEFT JOIN {view_name} e ON …)`.
  Under the split layout this must become: join VCF → core, then LEFT JOIN each present sidecar on
  `(chrom, row_idx)` (CTE form). Chromosome prefix harmonization logic stays.
- `annotation/duckdb_assets.py` (~L76-119) — creates `VIEW ensembl_variations` over one glob. Will need
  per-group views (or just the core view) plus manifest/release validation.
- `annotation/ensembl_download.py` — per-file size+SHA256 verification against HF; extend to groups and
  the release-id check. CLAUDE.md: never revert to "any parquet present, skip"; readers glob `*.parquet`.
- `src/just_dna_lite/cli.py` (~615-830) — download/verify/build-duckdb commands.
- `module_compiler/resolver.py::ensure_resolver_db` + `just_dna_enricher.resolver` — consume the cache
  for rsID→coordinate. Core must stay compatible (`id`, `chrom`, `start`, `ref`, `alt` names; check exact
  expectations in the enricher before renaming `pos`→`start`).
- CLAUDE.md rules that apply: Ensembl assets must take `normalized_parquet=`; `resource_tracker` +
  `resource_summary_hook` in every asset/job; `sink_parquet` not collect; DuckDB `memory_limit` +
  `temp_directory`; never `snapshot_download` (use `HfFileSystem.get` per file); no inline imports.

### Scripts used (reproduce on the server; run with `uv run --no-project --with pysam --with polars --with duckdb python -I script.py OUTDIR`)

`est.py` — tabix sample → three parquet layouts + old-cache comparison:
```python
import pysam, gzip, os, sys, polars as pl
U='https://ftp.ebi.ac.uk/pub/ensemblorganisms/GCA/000/001/405/29/ensembl/2026_04/variation/2026_07_13/variation.vcf.gz'
OUT=sys.argv[1]; CH,S,E='21',33_000_000,35_000_000
t=pysam.TabixFile(U)
fmt=[l for l in t.header if l.startswith('##INFO=<ID=CSQ')][0].split('Format: ')[1].rstrip('">').split('|')
lines=list(t.fetch(CH,S,E))
raw='\n'.join(lines).encode(); gzb=len(gzip.compress(raw,6))
full=[]
for l in lines:
    f=l.split('\t'); info=dict(x.split('=',1) for x in f[7].split(';') if '=' in x)
    for c in info.get('CSQ','').split(','):
        d=dict(zip(fmt,c.split('|')))
        full.append({'chrom':f[0],'pos':int(f[1]),'id':f[2],'ref':f[3],'alt':d['Allele'],**{k:(d[k] or None) for k in fmt if k!='Allele'}})
df=pl.DataFrame(full,infer_schema_length=None); df.write_parquet(f'{OUT}/full.parquet',compression='zstd')
# slim_per_transcript = selected KEEP cols with numeric casts to Float32;
# slim_per_allele = sort by IMPACT rank (HIGH<MODERATE<LOW<MODIFIER) and group_by(chrom,pos,id,ref,alt).first()
# old = scan old chr21 parquet filtered start in [S,E]
```
NOTE: VCF `ALT` may be multi-allelic; CSQ `Allele` is the per-allele key used as `alt`. For indels the
CSQ `Allele` is VEP-trimmed (e.g. `-` or the inserted bases) — **must be mapped back to the VCF REF/ALT
spelling** via `ALLELE_NUM` (subfield 19) before joining to a normalized VCF. The sample script did NOT
do this mapping; indel rows in the sample therefore carry VEP allele strings. Fix in the real build.

`split.py` — per-allele table with `row_idx`, write sparse sidecars:
```python
al=(tx.with_columns(pl.col('IMPACT').replace_strict(rank,default=4).alias('_r')).sort(['pos','ref','alt','_r'])
      .group_by(['chrom','pos','ref','alt'],maintain_order=True).first().drop('_r')
      .with_row_index('row_idx').with_columns(pl.col('pos').cast(pl.UInt32)))
def w(name,df,sparse_on=None):
    if sparse_on: df=df.filter(pl.any_horizontal([pl.col(c).is_not_null() for c in sparse_on]))
    df.write_parquet(f'{S}/split_{name}.parquet',compression='zstd',compression_level=9,row_group_size=500_000)
```

`bench2.py` — the query shape that worked (keep this ordering):
```sql
WITH m AS (
  SELECT v.*, c.row_idx, c.id
  FROM 'sample_vcf.parquet' v LEFT JOIN 'split_core.parquet' c USING (pos, ref, alt)
)
SELECT m.*, g0.* EXCLUDE (row_idx), g1.* EXCLUDE (row_idx), g2.* EXCLUDE (row_idx), g3.* EXCLUDE (row_idx)
FROM m
LEFT JOIN 'split_consequence.parquet'        g0 USING (row_idx)
LEFT JOIN 'split_clinical.parquet'           g1 USING (row_idx)
LEFT JOIN 'split_predictors_no_cadd.parquet' g2 USING (row_idx)
LEFT JOIN 'split_freq_global.parquet'        g3 USING (row_idx);
```
(Genome-wide: add `chrom` to every join key; files hive-partitioned by `chrom=`.)

## Files Changed

### Source code
- none

### Docs
- `plans/handoffs/HANDOFF_ensembl-split-parquet_2026-11-03.md` — this file.

### Data & results
- Sample outputs (full.parquet, slim_*.parquet, split_*.parquet, wide.parquet, sample_vcf.parquet,
  old.parquet) were in a local scratchpad only; **not available on the server**. Regenerate with the
  scripts above.

## User Feedback & Preferences

- Main complaint: the current Ensembl cache "often had only bool value like 'is in clinvar' which was not
  helpful for general annotation". Richer values are the point.
- Assumed dbNSFP is "like dbSNP but way better" — corrected: it is a precomputed predictor/annotation
  table for every possible coding/splice SNV, not a variant catalog.
- Was confused that parquet could be "larger" — explanation must always compare like with like
  (same content VCF vs parquet; or old vs new content).
- Wants it **DuckDB-friendly**, and proposed **several connected parquets downloaded by need** ("major data,
  additional fields, etc.") joined like a relational DB.
- Asked explicitly whether splitting loses speed → answered with a measurement; expects numbers, not
  reassurance.
- Wants work continued by a Claude on a server (bandwidth/disk for the 133 GB file).
- Standing preference (global CLAUDE.md): commit and push to main without asking; no PRs unless required.
- Interested in the Ensembl beta specifically for "better vcf annotation".

## Where We're Going

1. **Full-chr21 prototype on the server.** `tabix` the whole chr21 from the 133 GB URL (or download the
   file once: it's the server's job), map CSQ `Allele` back to VCF REF/ALT via `ALLELE_NUM`, normalize
   alleles the same way `user_vcf_normalized` does, build core + sidecars with `row_idx`, hive-partitioned.
2. **Benchmark against reality**: current single-table join (download `homo_sapiens-chr21.parquet` from
   `just-dna-seq/ensembl_variations`) vs wide vs split-CTE, using a real normalized sample parquet
   (public genomes: Zenodo 18370498 `antonkulaga.vcf`, Zenodo 19487816 Livia's VCF) restricted to chr21.
   Report sizes per group and timings; confirm the 20/30/100 GB extrapolation.
3. **Decide the ClinVar source**: compare Ensembl `CLIN_SIG` vs ClinVar GRCh38 VCF (CLNSIG/CLNREVSTAT/CLNDN)
   on chr21 matched alleles; likely build `clinical` from ClinVar.
4. **Check resolver compatibility**: read `just_dna_enricher.resolver` to see which columns it needs from
   the cache; decide core-with-rsID vs separate rsID→position table.
5. **Write a design doc** in `docs/` (manifest schema with release id, group list, bundles, query shape)
   before touching `logic.py` / `duckdb_assets.py` / `ensembl_download.py`.
6. Optional: evaluate dbNSFP 5.4a as an extra user-downloaded group (licence prevents redistribution).

## Risks & Blockers

- New Ensembl FTP paths "will likely change"; update cadence of `variation.vcf.gz` undocumented.
- Indel allele spelling (VEP-trimmed CSQ `Allele`) vs normalized VCF spelling: a wrong mapping silently
  drops indel annotations. See CLAUDE.md's reanchor notes (Ensembl dump insertions can be anchored one
  base off ClinVar/caller convention: RM267 still open upstream).
- Licences: CADD non-commercial; dbNSFP CC BY-NC-ND (no derived redistribution); check REVEL and
  AlphaMissense terms before publishing a derived HF dataset under Apache-2.0 as the current card says.
- `row_idx` across releases: must be guarded by a manifest release id or annotations go wrong silently.
- Estimates come from one gene-dense 2 Mb region (could be off 20-30%).

## Open Questions

- Will Ensembl publish VEP caches / command-line VEP beyond 116? Not found.
- Are HGVSc/HGVSp populated anywhere in the new VCF (empty in every sampled coding record)?
- Does the enricher resolver need `end`, `alts` or other columns besides `chrom/start/id/ref/alt`?
- Should novel (non-dbSNP) variants get consequences at all? That would require local VEP 116 (26 GB cache).
- Single wide parquet vs split: final call after the full-chromosome benchmark.

## Quick Start for Next Session

```bash
# Repo
cd just-dna-lite && git pull

# Read first
less CLAUDE.md   # Ensembl cache + Dagster + shared libs sections
less just-dna-pipelines/src/just_dna_pipelines/annotation/logic.py          # annotate_vcf_with_duckdb
less just-dna-pipelines/src/just_dna_pipelines/annotation/duckdb_assets.py  # VIEW creation
less just-dna-pipelines/src/just_dna_pipelines/annotation/ensembl_download.py
less just-dna-pipelines/src/just_dna_pipelines/module_compiler/resolver.py

# Source data
URL=https://ftp.ebi.ac.uk/pub/ensemblorganisms/GCA/000/001/405/29/ensembl/2026_04/variation/2026_07_13/variation.vcf.gz
curl -sI $URL | head -5          # expect 200, ~133 GB
# remote chr21 slice without full download (pysam):
uv run --no-project --with pysam python -I -c "import pysam;t=pysam.TabixFile('$URL');print(sum(1 for _ in t.fetch('21')))"

# Current cache for comparison (chr21 only)
uv run --no-project --with huggingface_hub python -I -c "from huggingface_hub import HfFileSystem as F;F().get('datasets/just-dna-seq/ensembl_variations/data/homo_sapiens-chr21.parquet','old_chr21.parquet')"

# Next action
# Build the chr21 core + sidecars (row_idx, sparse, hive by chrom), with CSQ Allele mapped to VCF REF/ALT
# via ALLELE_NUM, then benchmark current vs wide vs split-CTE on a real normalized chr21 sample.
```
