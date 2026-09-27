# Releasing the annotation modules on 0.7

The build-and-publish record for the ten `just-dna-seq` modules on **`just-dna-format` 0.7.0 /
`just-dna-compiler` 0.7.1 / `just-dna-enricher` 0.7.2**, published to the registry
(`https://module-registry.just-dna.life`, namespace `just-dna-seq`) on **2026-09-27**. This continues
the history in [MODULE_RELEASE_0_5.md](MODULE_RELEASE_0_5.md); the version numbers, parity notes and the
0.5-era changelogs live there, and the per-version changelogs actually published under 0.7 are recorded
verbatim below so the history stays continuous.

Build commands are unchanged from the 0.5 runbook:

```bash
uv run pipelines v1-port port --all        # six curated Gen-I ports
uv run pipelines v1-port clinvar --all     # cardio / cancer / pathogenic
uv run pipelines v1-port pharmgkb          # drug response (ClinPGx)
```

## What 0.7 changed for the artifacts

Rebuilding on the 0.7 surfaces changed the compiled output, not just the compiler version:

- **39-column `weights`** (the 0.6/0.7 additive shape: `variant_key`, `clin_sig`, `requires_callable`,
  …), up from the 37-column 0.5 shape.
- The licence sidecar is written as **`licensing.csv`** (the deprecated `sources.csv` is swept before
  enrich by `v1_port/runner.py`).
- Every module publishes a **`manifest.json`** attesting the artifact.
- **`clinvar_panel.py` no longer writes the deprecated `panel:` block** (format 1.0 removes it); its
  provenance moved to `clinvar_panel.log` (reference sha, significance predicate, requested gene list).
- **`pharmgkb` now places every row at genomic coordinates.** Since format 0.6 (RM43) the compiler
  resolves the `pharm_variants` lead table, so the module joins by position (48 drug-gene matches on a
  real WGS sample) instead of the rsID-only fallback the 0.5 artifact was stuck in (0 of 1,482 placed).
- **`superhuman` indel re-anchor.** 21 indel rsIDs whose coordinates the Ensembl resolution cache
  anchored one base off the caller/ClinVar convention are re-anchored to ClinVar's placement before
  compile (`v1_port/reanchor.py`), recovering carrier findings the position join silently dropped. See
  the upstream cases below.

The two curated modules whose row counts moved (`longevitymap` 1039 → 1022, `superhuman` 190 → 99) both
moved for correctness, not loss — the changelogs below state why in each case.

## What was published (2026-09-27, namespace `just-dna-seq`)

| module | version | transport | rows | notes |
|---|---|---|---|---|
| coronary | 1.1.0 | `registry publish` | 81 | curation unchanged |
| thrombophilia | 1.1.0 | `registry publish` | 24 | curation unchanged |
| lipidmetabolism | 1.1.0 | `registry publish` | 45 | curation unchanged |
| vo2max | 1.1.0 | `registry publish` | 39 | curation unchanged |
| longevitymap | 1.2.0 | `registry publish` | 1022 | reference-strand fix (was 1039) |
| superhuman | 2.4.0 | `registry publish` | 99 | anti-fabrication + indel re-anchor (was 190) |
| cardio | 2.0.0 | `registry import-module` | 115,382 | ClinVar panel |
| cancer | 2.0.0 | `registry import-module` | 141,616 | ClinVar panel |
| pathogenic | 2.0.0 | `registry import-module` | 618,629 | genome-wide flag |
| pharmgkb | 1.0.0 | `registry publish` | 1,531 | now position-joined (was 0/1482 placed) |

- **Transport.** The six ports and pharmgkb go via `registry publish <spec_dir>` (server-side recompile,
  all under the 25 MiB multipart limit). The three ClinVar panels exceed that limit, so they go via
  `registry import-module <tar.gz>` packing `module_spec.yaml + *.csv + *.log` — no parquets (the server
  recompiles from the spec) and, note, **no `logo.png`** (see metadata below). `pathogenic`'s archive is
  20 MiB of the 25 MiB ceiling; a future ClinVar release that grows the pathogenic set will need
  `upload_too_large` raised, as there is no third transport.
- **Digests** are held per version on the registry (`manifest.artifact.digest`). `pathogenic@2.0.0`
  verifies at `sha256:540a59613d80e25c873ee3c3c1c8f36005abb1b12d14165ba91f426dca750ed8` (verify-download
  after the disconnect below).
- **Post-publish metadata** (both amendable, out of the digest, no version bump): the three panels'
  logos were set with `registry amend-logo` (the `import-module` archive carried none), and a one-line
  card subtitle was set on all ten with `registry set-short-description`.

## The `pathogenic` import disconnect (resolved)

The `pathogenic` `import-module` raised `httpx.RemoteProtocolError: Server disconnected without sending a
response` mid-upload. It nonetheless **committed**: `registry list` shows it with the right stats and a
verify-download passes. The server finished the recompile and disconnected before returning the response
— the write succeeded, only the response was lost (a proxy/gateway timeout across the 20 MiB upload plus
the 618k-row recompile). Under `set -e` this halted the publish script before the HuggingFace mirror
step. Filed as registry **S26**. Lesson: on a large-import disconnect, verify with `list`/`find-by-hash`
rather than retry (a retry hits the immutable-version rejection).

## Upstream cases filed from this release

Consumer field notes (see the working agreement in CLAUDE.md — notes only, the maintainers triage):

- **just-dna-format** `docs/CONSUMER_SUGGESTIONS.md`: **S117** the Ensembl cache anchors an insertion
  class one base off the caller/ClinVar convention (→ RM267 + RM268); **S120** the format declares no
  coordinate-normalization convention, so a legal respelling is a silent join miss (→ RM270); **S121**
  single-authority resolution validates against itself, so a wrong anchor is confirmed not caught, and a
  cross-authority discordance should warn/withhold (folded into RM267).
- **just-dna-registry** `docs/CONSUMER_SUGGESTIONS.md`: **S25** `import-module` publishes with no logo
  while `publish` carries one, silently; **S26** the large-import commit-then-disconnect above.

## Changelogs published with (0.7)

Each is the text passed to `--changelog` at publish, continuing the 0.5 entries in
[MODULE_RELEASE_0_5.md](MODULE_RELEASE_0_5.md). The source of record is
`just_dna_pipelines`'s release scratch (`changelogs_0_7.sh`), reproduced here verbatim.

**coronary 1.1.0**
> Coronary-artery-disease risk variants. Generation-I OakVar module ported to the current format; 27 curated variants with weights carried verbatim and digit-only PMIDs. Rebuilt on format 0.5 (resolution.csv, 37-column weights, 59 citations); 81 weight rows, 77 annotations, 118 studies; gene symbols reconciled (CXCL12 (LINC02881) -> CXCL12, GUCYA3 -> GUCY1A1). — Rebuilt on just-dna-format 0.7.0 / compiler 0.7.1 / enricher 0.7.2: weights now the 39-column 0.6/0.7 shape (variant_key, clin_sig, requires_callable, ...), licence recorded as licensing.csv, and the module publishes a manifest.json attesting the artifact. 81 weight rows / 81 annotations / 118 studies, curation unchanged.

**thrombophilia 1.1.0**
> Inherited blood-clotting risk variants (Factor V Leiden, prothrombin, and related loci). Generation-I port; curated weights verbatim, grounded studies with digit-only PMIDs. Rebuilt on format 0.5 (resolution.csv, 37-column weights, 25 citations); 24 weight rows, 22 annotations, 27 studies; SERPINE corrected to SERPINE1 on rs1799889. — Rebuilt on just-dna-format 0.7.0 / compiler 0.7.1 / enricher 0.7.2: 39-column weights, licensing.csv, manifest.json. 24 weight rows / 24 annotations / 27 studies, curation unchanged.

**lipidmetabolism 1.1.0**
> Lipid-metabolism and cardiovascular-risk variants. Generation-I port; 15 curated variants, weights verbatim, digit-only PMIDs. Rebuilt on format 0.5 (resolution.csv, 37-column weights, 36 citations); 45 weight rows, 41 annotations, 41 studies; ABCG8, ABCG5 split to ABCG8, one orphan study dropped. — Rebuilt on just-dna-format 0.7.0 / compiler 0.7.1 / enricher 0.7.2: 39-column weights, licensing.csv, manifest.json. 45 weight rows / 45 annotations / 44 studies, curation unchanged.

**vo2max 1.1.0**
> Athletic-performance / VO2max variants. Generation-I port; 13 curated variants, weights verbatim, digit-only PMIDs. Rebuilt on format 0.5 (resolution.csv, 37-column weights, 7 citations); 39 weight rows, 28 annotations, 19 studies; BIRC7, YTHDF1 split to BIRC7; FLJ44450 matches no current NCBI symbol and is reported, not guessed. — Rebuilt on just-dna-format 0.7.0 / compiler 0.7.1 / enricher 0.7.2: 39-column weights, licensing.csv, manifest.json. 39 weight rows / 39 annotations / 19 studies, curation unchanged.

**longevitymap 1.2.0**
> Longevity-associated variants from the LongevityMap database. Full source parity at 528/528 rsids, heterozygous genotypes reconstructed from the curated effect allele. Weights verbatim, digit-only PMIDs. Rebuilt on format 0.5 (resolution.csv, 37-column weights, 162 citations). — Rebuilt on just-dna-format 0.7.0 / compiler 0.7.1 / enricher 0.7.2: 39-column weights, licensing.csv, manifest.json. 1022 weight rows (was 1039), 528/528 rsids preserved, 671 studies. The row change is a correctness fix, not a loss: 0.7 resolution places every genotype on the GRCh38 reference strand, so each genotype now contains its reference allele and can match a VCF. The 0.5 build followed the source's strand and carried genotype rows whose reference allele was absent (e.g. rs1050450, ref G, authored C/T and T/T) or duplicated across both strands (rs26802: C/C,C/T,G/G,G/T); those are corrected.

**superhuman 2.4.0**
> Elite/beneficial-variant module, v2. Narrowed from the raw 1,243-variant dbSNP dump to 101 curated protective alleles across 37 genes, all grounded on human-verified PubMed citations (no fabricated PMIDs). Adds March-2026 findings (TPH2, COMT, BDNF, CETP, APOE-Christchurch) and PCSK9 R46L; corrects mislabeled entries. Rebuilt on format 0.5 (resolution.csv, 37-column weights, 37 citations); curation unchanged. — Rebuilt on just-dna-format 0.7.0 / compiler 0.7.1 / enricher 0.7.2: 39-column weights, licensing.csv, manifest.json. 99 weight rows (was 190), 74 studies; curation still 101 protective alleles / 37 genes. The row change is a correctness fix: the port no longer emits a genotype for an unnamed allele at a multi-allelic locus, because guessing which ALT is protective fabricated claims — rs334 asserted A/T, C/T and G/T all as malaria resistance when only T>A is HbS. Those rows are dropped and reported. And 21 indel rsIDs whose coordinates the Ensembl resolution cache anchored one base off the caller/ClinVar convention are re-anchored to ClinVar's placement (the dbSNP authority for the rsID), recovering carrier findings a position join silently dropped — e.g. HSD17B13 rs72613567, SCN9A rs77944059, CCR5-Δ32 rs333; rs80356676 takes ClinVar's real NTRK1 variant over a mis-resolution.

**superhuman 2.5.0** (staged; republish is the maintainer's call, not yet published)
> Curation corrections over 2.4.0, carried in data/curation/superhuman.csv (each reported as a build warning); content only, no schema change, so a minor bump. 86 weight rows (was 99), 72 rsids. Fixed an inverted direction on IFIH1 rs1990760: the type 1 diabetes risk allele is T (Thr946) and the protective allele is C (Ala946) (Smyth 2006 PMID 16699517, confirmed 35867130 / 39373578), so the C/T and T/T rows that read "lower risk" were the risk genotypes; C/T is dropped and the protective finding re-keyed to C/C with a small-effect note. Dropped three fabricated multi-allelic genotype sets that named alleles no source stated: ABCC11 rs17822931 G/G (the no-odour genotype is T/T), and MSTN rs12105165 / rs3187415 (every-combination rows at multi-allelic loci). Dropped FUT2 rs601338 A/G (secretor status is dominant; the norovirus-resistance and Crohn's rows are recessive, A/A only). Split CCR5 rs333 into homozygous Delta32 (strong HIV resistance) and heterozygous (slower progression, not full resistance), each with its own trade-off. Reframed conclusions that headlined layer-3 codes or overstated evidence: FAAH rs324420 (removed the FAAH-OUT/Habib microdeletion attribution, a different variant), APOE Christchurch rs121918393 (a single case report, not a definitive PSEN1-E280A resilience claim), APOA2 rs5082 (neutral gene-diet framing, bare "Obesity" trade-off cleared), GHR rs2940928 (short-stature trade-off as a sentence). Added an animal-study caveat to the MSTN atherosclerosis claim, softened the APOL1 kidney-risk note to two copies, expanded the remaining terse tags into full conclusions, and removed the last two em-dashes from module prose.

**cardio 2.0.0**
> Pathogenic variants in cardiac-disease genes — a ClinVar gene panel. Rebuilt from the raw-VCF route onto the just-dna-enricher ClinVar snapshot (release 2026-06-27, sha256-pinned): variants authored by identity and resolved offline from that snapshot, typed clin_sig throughout, 1-star review floor, per-variant ClinVar citations (up to 3 each). — Rebuilt on just-dna-format 0.7.0 / compiler 0.7.1 / enricher 0.7.2: 39-column weights, licensing.csv, manifest.json. 115,382 weight rows across 297 genes, 122,297 studies. The deprecated panel: block is no longer written (format 1.0 removes it); the snapshot it pinned is now recorded on the licence row's dataset column and in clinvar_panel.log (reference sha, significance predicate, requested gene list).

**cancer 2.0.0**
> Pathogenic variants in cancer-predisposition genes — a ClinVar gene panel. Rebuilt on the just-dna-enricher ClinVar snapshot (release 2026-06-27, sha256-pinned); see cardio for the route. Typed clin_sig throughout, 1-star review floor, per-variant ClinVar citations. — Rebuilt on just-dna-format 0.7.0 / compiler 0.7.1 / enricher 0.7.2: 39-column weights, licensing.csv, manifest.json. 141,616 weight rows across 298 genes, 140,934 studies. The deprecated panel: block is no longer written; provenance moved to the licence row's dataset column and clinvar_panel.log.

**pathogenic 2.0.0**
> Genome-wide ClinVar pathogenicity flag. Rebuilt on the just-dna-enricher ClinVar snapshot (release 2026-06-27, sha256-pinned); see cardio for the route. The gene set is derived from the snapshot itself, so it is a genome-wide flag rather than a curated panel. — Rebuilt on just-dna-format 0.7.0 / compiler 0.7.1 / enricher 0.7.2: 39-column weights, licensing.csv, manifest.json. 618,629 weight rows across 4,793 genes, 626,088 studies. The deprecated panel: block is no longer written; provenance moved to the licence row's dataset column and clinvar_panel.log.

**pharmgkb 1.0.0**
> Drug response by genotype, from the ClinPGx (PharmGKB) clinical annotations. Supersedes the Generation-I just_drugs module. Aggregated clinical annotations at evidence levels 1A/1B/2A/2B; one row per (variant, drug, genotype, effect category). Conclusions are ClinPGx's own published sentences, transcribed rather than summarized. ClinPGx is CC BY-SA 4.0 and forbids sale, so licensing.csv records commercial_use=false / declared_use=non_commercial. — Rebuilt on just-dna-format 0.7.0 / compiler 0.7.1 / enricher 0.7.2. 1,531 rows (was 1,482), and every row now carries genomic coordinates: since format 0.6 (RM43) the compiler resolves the pharm_variants lead table, so the module joins by genomic position — matched 48 drug-gene rows on a real whole-genome sample — instead of the rsID-only fallback the 0.5 artifact was stuck in (0 of 1,482 rows placed). Adds per-annotation pmid citations and requires_callable. Publishes trusted:false at the registry, which is correct for a mechanically-aggregated PGx module.

## HuggingFace mirror

The HuggingFace collection (`just-dna-seq/annotators`) is the legacy mirror, kept in sync via
`pipelines v1-port publish <name>` (uploads the compiled parquets + `logo.png` directly, so no separate
logo step is needed there — unlike the registry panels, which needed `amend-logo`).

**Done 2026-09-27**: all ten mirrored, no errors (9 files each for the ports, 8 for the ClinVar panels,
6 for pharmgkb — lead table + side parquets + `manifest.json` + `logo.png`). To re-run:

```bash
for m in coronary thrombophilia lipidmetabolism vo2max longevitymap superhuman \
         cardio cancer pathogenic pharmgkb; do uv run pipelines v1-port publish "$m"; done
```
