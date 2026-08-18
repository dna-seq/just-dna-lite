# Releasing the annotation modules on 0.5

> **We are on format 0.6 since 2026-08-18** (format 0.6.1 / compiler 0.6.1 / enricher 0.6.2). The runbook below still applies step for step; two things in it read differently. The licence sidecar is now written as **`licensing.csv`** (`sources.csv` is the deprecated spelling — still read, warned, removed at 1.0), and **every `artifact.digest` moved at the version boundary** while no `content_signature` did, so a digest that differs from a 0.5 record is the compiler version and not a content change. Republishing the ten modules remains the maintainer's call; they are still 0.5 artifacts on purpose. See CLAUDE.md § *What 0.6 changed on our side*.

The build-and-publish runbook for the ten `just-dna-seq` modules, on `just-dna-format` 0.5.0 /
`just-dna-compiler` 0.5.1 / `just-dna-enricher` 0.5.1. The registry is
`https://module-registry.just-dna.life` (it answered to `module-marketplace.` until 2026-08-10).

Publishing itself is **the maintainer's call and the maintainer's hands** — nothing below is run
automatically. Every command is idempotent to *build*; only the `publish` / `upload` lines write
anywhere public.

## The modules

| module | route | built by | source |
|---|---|---|---|
| `coronary` | curated variants | `v1-port port` | `dna-seq/just_coronary` SQLite |
| `thrombophilia` | curated variants | `v1-port port` | `dna-seq/just_thrombophilia` SQLite |
| `lipidmetabolism` | curated variants | `v1-port port` | `dna-seq/just_lipidmetabolism` SQLite |
| `vo2max` | curated variants | `v1-port port` | `dna-seq/just_vo2max` SQLite |
| `longevitymap` | curated variants | `v1-port port` | `dna-seq/just_longevitymap` SQLite |
| `superhuman` | curated variants | `v1-port port` | `dna-seq/just_superhuman` SQLite + curation CSV |
| `cardio` | ClinVar gene panel | `v1-port clinvar` | ClinVar snapshot + `just_cardio` gene list |
| `cancer` | ClinVar gene panel | `v1-port clinvar` | ClinVar snapshot + `just_cancer` gene list |
| `pathogenic` | ClinVar genome-wide | `v1-port clinvar` | ClinVar snapshot (no gene filter) |
| `pharmgkb` | drug response | `v1-port pharmgkb` | ClinPGx clinical annotations |

## 0. Provision the references (once)

Everything downstream reads local snapshots; none of the builds fetch a reference themselves.

```bash
uv run pipelines ensembl-setup                       # 25 parquet, ~14 GB, verified + DuckDB
uv run just-dna-enricher cache pull --use non-commercial
uv run just-dna-enricher cache status                # all six lines should read "present"
```

`cache pull` writes to the platformdirs default (`~/.cache/just-dna-pipelines/`) while
`cache status` and every resolver read `$JUST_DNA_PIPELINES_CACHE_DIR`. If `.env` points the cache
elsewhere — it does here, at `/data/just-dna-lite/.cache/just-dna-pipelines` — move the pulled
snapshots there, or `status` will report them absent immediately after a successful pull:

```bash
mv ~/.cache/just-dna-pipelines/{clinvar,clinpgx,cpic,gnomad_constraint} \
   "$JUST_DNA_PIPELINES_CACHE_DIR"/
```

## 1. Build

```bash
uv run pipelines v1-port port --all                  # the six curated modules
uv run pipelines v1-port clinvar --all               # cardio, cancer, pathogenic
uv run pipelines v1-port pharmgkb                    # drug response
```

Each writes `data/interim/v1_port/<name>/`: the authored spec (`module_spec.yaml` + CSVs), the
enricher's `resolution.csv` (+ `literature.csv` where studies exist), the compiled parquet and
`manifest.json`, and a provenance log.

Useful flags: `--offline` (no live Ensembl/gnomAD/PubMed — faster, but leaves indel VRS ids
unminted), `--no-literature`, `--no-compile`, `--min-review-stars N` (ClinVar panels).

**Panel resolution is one call again.** It used to need slicing into 10k-row batches, because the
enricher's ClinVar reader was quadratic in module size and `cardio` never finished; enricher **0.5.2**
joins a probe table instead, and 76,078 rows now resolve in 13 s with the rate *improving* as the
module grows. The batching and its resume logic are removed. `scripts/finish_pathogenic.py` remains
for re-resolving and recompiling an already-drafted spec without paying for the draft again.

**The ClinVar panels resolve offline by design, and that caps VRS coverage at about half.** A VRS
allele id for a substitution mints from the allele strings alone; an indel or MNV has to be justified
against the reference *sequence*, which only an online run can fetch. Panel-scale online minting is
tens of thousands of sequence lookups, so the panels are built offline and say so — `cardio` came out
at 2,871/5,620 alleles identified (51%). The curated modules and `pharmgkb` are small enough to run
online and reach 99–100%. Raising panel coverage means re-running `just-dna-enricher enrich` on the
built spec without `--offline`, which is a decision about time and API budget, not a code change.

### What the build produced (2026-08-10)

| module | weights | annotations | studies | literature | coords | digest |
|---|---:|---:|---:|---:|---|---|
| coronary | 81 | 77 | 118 | 59 | 81/81 | `65496ede` |
| thrombophilia | 24 | 22 | 27 | 25 | 24/24 | `294eb72e` |
| lipidmetabolism | 45 | 41 | 41 | 36 | 45/45 | `c22a7f6e` |
| vo2max | 39 | 28 | 19 | 7 | 39/39 | `89d5a1e0` |
| longevitymap | 1,039 | 528 | 671 | 162 | 1,018/1,039 | `7ac6a922` |
| superhuman | 190 | 101 | 103 | 37 | 190/190 | `c4bdab0c` |
| pharmgkb | — | — | — | — | 147/147 loci (1,482 `pharm_variants` rows) | `cef74d5b` |
| cardio | 115,060 | 115,060 | 121,467 | — | 115,060/115,060 | `a45a9926` |
| cancer | 139,254 | 139,254 | 138,240 | — | 139,254/139,254 | `4e9e0dff` |
| pathogenic | 617,001 | 617,001 | 622,507 | — | 617,001/617,001 | `8a291cad` |

**Panel digests move on every rebuild, with or without a content change.** `licensing.csv` carries a
`fetched_at` stamped when the row is drafted, and `sources.parquet` is one of the four files
`artifact.digest` is a Merkle root over — isolated by editing only that field and recompiling. So
treat the hashes above as identifying *these* builds, not the content: a rebuild from the same
snapshot produces different ones. Recompiling an untouched spec is reproducible; re-drafting is not.
The six curated modules and `pharmgkb` were not re-drafted for 0.5.2 and keep the digests listed
above (`vo2max` was recompiled to confirm: identical).

The panels: `cardio` 297 genes, `cancer` 293, `pathogenic` 4,793 (402,218 pathogenic + 214,942
likely-pathogenic). Every row carries a coordinate and a typed `clin_sig`.

**Zygosity is per contig, and the row counts show it.** A ClinVar record on a diploid contig
contributes two rows (heterozygous + homozygous); one on the mitochondrial genome or chrY contributes
**one**, with a single-allele genotype, because a two-allele call there asserts a second copy that
does not exist. That is 130 rows in `cardio` and 159 in `pathogenic` — the reason those two are
115,060 and 617,001 rather than 115,190 and 617,160. The compiler flags the mistake itself
(*"chrom=MT is not diploid here"*), which is how it was caught; `test_modules_0_5.py` now pins both
halves of the rule.

Two numbers that moved and should not surprise anyone reading a diff:

- **longevitymap 1,043 → 1,039 weight rows, 3,102 → 671 studies.** Four rows whose genotype is not
  among the locus's resolved alleles were dropped (see [V1_PARITY.md](V1_PARITY.md) § Findings), and
  2,431 study rows cited rsIDs the module does not weight. Both are named in `v1_port.log`.
- **21 longevitymap weight rows have no coordinate**, on nine rsIDs whose every authored genotype
  the resolved locus refuses. They compile and are reported; they cannot match a VCF.

## 2. Pre-publish check against the live registry

The registry runs the same compiler and the same network tier a publish would, and reports
`would_publish`. It writes nothing, but it **does** authenticate.

```bash
export MARKETPLACE_TOKEN=…                              # the key that owns just-dna-seq
uv run python scripts/registry_precheck.py              # every built module
uv run python scripts/registry_precheck.py pharmgkb --json /tmp/pre.json
uv run python scripts/registry_precheck.py --offline    # validation tier only, fast
uv run python scripts/registry_precheck.py --namespace sandbox   # rehearse without the real key
```

**The token has to own the namespace it checks.** Both endpoints authenticate, and a key without the
capability gets `403 insufficient_capability`. Check which account a key is before blaming the spec:

```bash
curl -s -H "Authorization: Bearer $MARKETPLACE_TOKEN" \
  https://module-registry.just-dna.life/api/v1/auth/whoami
```

The `just-dna-seq` key returns `{"account":"just-dna-seq","namespaces":["just-dna-seq"]}`. Note that
the `REGISTRY_TOKEN` value in `.env` is **not** it — it resolves to `test-publisher-185bb3`
(`test-namespace`, `test-namespace2`), which is a known bug: a UI branch overwrites that variable.
`REGISTRY_TOKEN_SANDBOX` owns `sandbox`. Rehearsing under `--namespace sandbox` is a valid substitute
when the real key is unavailable, since what the server validates is the uploaded spec rather than
the name it would be published under.

**A spec over 25 MiB cannot be *checked*, and gzip does not help there.** `cancer` is 47.3 MB of CSV
and gets `413 upload_too_large` ("the limit is 26214400"); all three ClinVar panels are over it.
Compression is not a way round it on this endpoint — three things were tried against the live server,
all rejected:

| attempt | result |
|---|---|
| `Content-Encoding: gzip` on the multipart body (45.1 MiB → 4.1 MiB) | `400` — "error parsing the body"; the server does not decompress requests |
| members gzipped individually as `variants.csv.gz` | `422 missing_spec_files: module_spec.yaml` |
| the whole spec as one `spec.tar.gz` file | `422 missing_spec_files: module_spec.yaml` |

`/check` and `/validate` want plain files with their real names. So for an oversized panel the
rehearsal is the **local** strict validation — the same code the server's `/validate` runs, minus the
network tier — and it passes: `cancer` is valid, 136,662 variants across 293 genes.

```bash
uv run pipelines module validate data/interim/v1_port/cancer --strict
```

**Gzip *is* the answer for publishing, on the archive endpoint.** `marketplace import-module` takes a
zip/tar.gz, and the API is explicit that "a spec archive is recompiled directly… same guards as
`publish`" — the same server-side compile over a different transport, not a trust downgrade. All
three panels fit compressed, though `pathogenic` only just:

| panel | raw multipart | tar.gz | vs the 25 MiB limit |
|---|---:|---:|---|
| cardio | 37.1 MiB | **3.5 MiB** | fits |
| cancer | 45.1 MiB | **4.1 MiB** | fits |
| pathogenic | 193.1 MiB | **19.1 MiB** | fits, with 6 MiB of headroom |

`pathogenic` is the one to watch: a future ClinVar release that grows the pathogenic set by ~30% puts
it over, and there is no third route. Worth asking the operator to raise
`upload_too_large` before that happens rather than after.

```bash
d=data/interim/v1_port/cancer
tar -czf /tmp/cancer_spec.tar.gz -C $d module_spec.yaml $(cd $d && ls *.csv *.log)
uv run pipelines marketplace import-module just-dna-seq cancer 2.0.0 /tmp/cancer_spec.tar.gz \
  --changelog "$CL_CANCER"     # the full text is in § Changelogs to publish with
```

`import-module` has no dry run, so it publishes; and it needs a **publish-capable** key — the
`sandbox` token returns `403 insufficient_capability` on it even though it can `/check` and
`/validate` fine, so the route cannot be rehearsed under sandbox either.

The check is also **rate-limited per account** — it is the service's most expensive endpoint — so a
back-to-back run of several modules returns `429`. The script backs off (30 s → 60 s → 120 s → 240 s)
rather than reporting a failure, since a 429 says "not yet", not "would not publish".

**Above 500 authored rows the script switches to `/validate`.** `/check` refuses a bigger module
outright — `422 too_many_variants`: *"528 variants exceeds the enrichment limit of 500 … or ask the
operator to raise `REGISTRY_ENRICH_MAX_VARIANTS`"* — and the refusal gates the whole endpoint, so
`?offline=true` does not get past it either. `/validate` is not limited and is the tier that decides
`would_publish`; what is lost is the network findings, not the verdict. `--online-all` forces
`/check` anyway; on a genome-wide panel that is hours, since the online tier paces gnomAD at roughly
six seconds per twenty variants.

### Results, 2026-08-10 (namespace `just-dna-seq`, the real key)

| module | verdict | endpoint | findings |
|---|---|---|---|
| coronary | `would_publish=True` | `/check` | 2 gene symbols HGNC does not recognise |
| thrombophilia | `would_publish=True` | `/check` | 1 stale symbol; 1 indel VRS id not recomputable server-side |
| lipidmetabolism | `would_publish=True` | `/check` | 1 stale symbol; 1 orphan study |
| vo2max | `would_publish=True` | `/check` | 1 stale symbol (`FLJ44450`, reported not guessed) |
| superhuman | `would_publish=True` | `/check` | gene symbols now clean; 71 unverifiable indel VRS ids (all minted, none wrong) |
| longevitymap | `valid=True` | `/validate` | 9 unresolvable rsIDs; over the 500-variant `/check` limit |
| pharmgkb | `valid=True` | `/validate` | 3 unverifiable indel VRS ids; VRS 262/262 |
| cancer | `valid=True` (local `--strict`) | — | `413 upload_too_large`: 47.3 MB against a 25 MiB limit |
| cardio, pathogenic | pending | — | rebuilding for the non-diploid-contig fix |

`superhuman`'s and `coronary`'s symbol findings shrank between the 2026-08-09 sandbox run and this
one because `normalize_genes` landed in between; what remains resolves to nothing in NCBI
`gene_info` and is reported rather than guessed.

The stale gene symbols in the first four are what `normalize_genes` was added for; the ones that
remain (`FLJ44450`) resolve to nothing and are reported rather than guessed.

## 3. Publish

Two stores. **The registry is primary**; the HuggingFace collection is legacy and kept in sync until
the migration is finished.

```bash
export MARKETPLACE_URL=https://module-registry.just-dna.life   # also set in .env
export MARKETPLACE_TOKEN=…            # the key that owns just-dna-seq — NOT $REGISTRY_TOKEN, see above
```

**The client had to be swapped, and it reads `.env` itself.** `just-dna-marketplace` 0.8.1 (the old
package name, and its last release) parses `GET /api/v1/version` expecting a `marketplace` field;
registry 0.11.0 returns `registry`, so its compatibility guard raised a pydantic `ValidationError`
**before sending any request** — every subcommand, `publish` included, was dead against the current
server. The dependency is now `just-dna-registry>=0.11.0`, matching the deployed server exactly,
taken from `/data/sources/just-dna-marketplace` because PyPI stops at 0.9.1. Confirm with:

```bash
uv run pipelines marketplace version     # client 0.11.0 / server 0.11.0 / compatible ✓
```

**0.11 renamed the environment variables and calls `load_dotenv()` itself**, so `.env` beats
anything exported in the shell: it reads `REGISTRY_URL` / `REGISTRY_TOKEN`, not `MARKETPLACE_*`. A
stale `REGISTRY_TOKEN` therefore surfaces as `403 insufficient_capability` on check and publish —
auth-shaped, but easy to misread as a permissions problem with the namespace. Always confirm the key
first (see below). `.env` now carries both spellings of both variables.

**Since 0.11 the client does the pre-publish check natively**, so for one module prefer it over the
batch script:

```bash
uv run pipelines marketplace check    just-dna-seq vo2max data/interim/v1_port/vo2max --identifiers
uv run pipelines marketplace validate just-dna-seq vo2max data/interim/v1_port/vo2max
```

### The republish, and the versions to use

**The registry was wiped.** All nine `just-dna-seq` modules published on 2026-07-09 are gone —
`marketplace list` returns only `eric-mods/lactose_tolerance`. The versions and changelogs below were
captured off the 0.9.1 server before the wipe (`data/mirror/republish-plan.json` in the mirror tree);
they are recorded here because a changelog should read as one continuous history rather than
restarting at "initial release" every time a server is rebuilt.

| module | was | republish as | why |
|---|---|---|---|
| coronary | 1.0.0 | **1.1.0** | same curation, 0.5 shape |
| lipidmetabolism | 1.0.0 | **1.1.0** | same curation, 0.5 shape |
| thrombophilia | 1.0.0 | **1.1.0** | same curation, 0.5 shape |
| vo2max | 1.0.0 | **1.1.0** | same curation, 0.5 shape |
| longevitymap | 1.1.0 | **1.2.0** | 0.5 shape + 4 unmatchable rows pruned |
| superhuman | 2.3.0 | **2.4.0** | same v2 curation, 0.5 shape |
| cardio | 1.0.0 | **2.0.0** | rebuilt on a different route; selection and grounding both change |
| cancer | 1.0.0 | **2.0.0** | as cardio |
| pathogenic | 1.0.0 | **2.0.0** | as cardio |
| pharmgkb | — | **1.0.0** | new module |

The three panels take a **major**, not a minor: the variant selection changed (a review-status floor
was introduced), the grounding changed from one blanket citation to ClinVar's own per-variant
literature links, and the row counts moved materially — `cancer` ~145k → 139,254, `cardio` ~123k →
115,060, `pathogenic` ~674k → 617,001. Someone pinned to `1.x` should not silently receive that.

**The `superhuman` 136 → 190 row count — resolved, and *not* a 0.5 artifact.** 2.3.0's changelog
quoted 136 genotype rows; this build has 190 over the same 37 genes / 101 rsIDs, curation CSV
unchanged. The 0.5 rebuild is not the cause: the adapter's authored `variants.csv` is already 190
rows and the compile is 1:1 (verified 190 → 190 weights; every other curated module shows the same
authored-vs-compiled parity, so 0.5 does **not** expand per allele at compile time). The 190 was
established on **2026-07-07 — a month before the 0.5 line landed (2026-08-08)** — by two adapter
changes on the 0.2/0.3 line: the multiallelic genotype-reconstruction fix (`_superhuman_genotypes`
now emits het+hom for **every** single-base ALT at a multiallelic locus rather than only the first,
so a triallelic `both` allele yields up to 6 rows — e.g. `rs1168015`, `rs6179`, `rs12105165`), and
the addition of PCSK9 R46L (`rs11591147`, 2 rows). The 136 was the count *before* that fix and is
simply stale. Composition of the 101 rsIDs: **58** curated rsID-scoped alleles (incl. the 6 refresh
additions) + **43** gene-level deletion-class variants for NTRK1/RIMS1/SCN9A. Integrity of the 0.5
build checked and clean: all 101 rsIDs grounded (0 ungrounded rows; every study rsID present in
weights; all PMIDs digit-only), coords 190/190, `state=protective` on every row, VRS ids minted into
`resolution.csv` (`vrs_id`), and `variant_key=rsid` + empty `direction` match every other 0.5 module
(the app's report reads `state`, not `direction`, so beneficial rendering is intact). Nothing broke.

### Changelogs to publish with

Each entry is the previously published text, followed by what this run adds. Copy the whole thing
into `--changelog`.

**coronary 1.1.0**
> Coronary-artery-disease risk variants. Generation-I OakVar module ported to the current format; 27
> curated variants with weights carried verbatim and digit-only PMIDs. — Rebuilt on just-dna-format
> 0.5: coordinates now arrive from an enricher-produced `resolution.csv` instead of a compile-time
> Ensembl lookup, `weights` carries the 37-column 0.5 shape, and `literature.csv` pins 59 citations
> against PubMed/Crossref. 81 weight rows, 77 annotations, 118 studies. Gene symbols reconciled:
> `CXCL12 (LINC02881)` → CXCL12, `GUCYA3` → GUCY1A1.

**lipidmetabolism 1.1.0**
> Lipid-metabolism and cardiovascular-risk variants. Generation-I port; 15 curated variants, weights
> verbatim, digit-only PMIDs. — Rebuilt on format 0.5 (resolution.csv, 37-column weights,
> literature.csv with 36 citations). 45 weight rows, 41 annotations, 41 studies. `ABCG8, ABCG5`
> split to ABCG8; one orphan study row dropped.

**thrombophilia 1.1.0**
> Inherited blood-clotting risk variants (Factor V Leiden, prothrombin, and related loci).
> Generation-I port; curated weights verbatim, grounded studies with digit-only PMIDs. — Rebuilt on
> format 0.5 (resolution.csv, 37-column weights, literature.csv with 25 citations). 24 weight rows,
> 22 annotations, 27 studies. `SERPINE` corrected to SERPINE1 on rs1799889.

**vo2max 1.1.0**
> Athletic-performance / VO2max variants. Generation-I port; 13 curated variants, weights verbatim,
> digit-only PMIDs. Hand-drawn lungs+DNA logo. — Rebuilt on format 0.5 (resolution.csv, 37-column
> weights, literature.csv with 7 citations). 39 weight rows, 28 annotations, 19 studies. `BIRC7,
> YTHDF1` split to BIRC7; `FLJ44450` matches no current NCBI symbol and is reported, not guessed.

**longevitymap 1.2.0**
> Longevity-associated variants from the LongevityMap database. Full source parity at 528/528 rsids
> and 1043 genotype rows — heterozygous genotypes reconstructed from the curated effect allele,
> closing the earlier multiallelic gap. Weights verbatim, digit-only PMIDs. — Rebuilt on format 0.5
> (resolution.csv, 37-column weights, literature.csv with 162 citations). 1,039 weight rows: four
> were dropped because their genotype is not among the locus's resolved alleles (`rs699` A/T and T/T
> against A/G, `rs1207362` C/C against G/T, `rs2107538` A/A against C/T) — Generation-I curation
> following a paper's strand rather than the reference's, and unmatchable against any VCF. 2,431
> orphan study rows citing unweighted rsIDs also removed, leaving 671. Nine rsIDs remain unresolved
> and are reported.

**superhuman 2.4.0**
> Elite/beneficial-variant module, v2. Narrowed from the raw 1,243-variant dbSNP dump to 101 curated
> protective alleles across 37 genes — 58 named rsID-scoped alleles plus gene-level deletion sets for
> NTRK1/RIMS1/SCN9A — all grounded on human-verified PubMed citations (no fabricated PMIDs). Each
> allele expands to one genotype row per zygosity/ALT (het + hom across multiallelic loci), giving
> 190 weight rows. Adds March-2026 findings (TPH2, COMT, BDNF, CETP, APOE-Christchurch) plus PCSK9
> R46L (rs11591147), and corrects mislabeled entries. — Rebuilt on format 0.5 (resolution.csv,
> 37-column weights, literature.csv with 37 citations). 190 weight rows / 101 annotations across 37
> genes; the curation is unchanged.

**cardio 2.0.0**
> Pathogenic variants in cardiac-disease genes — a ClinVar gene panel. — Rebuilt from the raw-VCF
> route onto the just-dna-enricher ClinVar **snapshot** (release 2026-06-27, pinned by sha256 in the
> spec's `panel:` block). Variants are authored by identity — rsID, or the whole coordinate where one
> rsID names several alleles — and resolved offline from that same snapshot, so the build is
> reproducible without a network. Every row carries a typed `clin_sig`. A review-status floor of 1★
> now excludes the "no assertion criteria provided" submissions the previous build mixed in silently.
> Grounding is per variant from ClinVar's own literature links (up to 3 each) rather than one blanket
> citation of the resource paper, which remains the fallback where ClinVar links no paper. 115,060
> weight rows across 297 genes, 121,467 studies; each record contributes both zygosities on a diploid
> contig and a single-allele genotype on the mitochondrial genome (130 rows), where a two-allele call
> would assert a second copy that does not exist.

**cancer 2.0.0**
> Pathogenic variants in cancer-predisposition genes — a ClinVar gene panel. — Rebuilt on the
> just-dna-enricher ClinVar snapshot (release 2026-06-27, sha256-pinned); see the cardio 2.0.0 notes
> for the route. 139,254 weight rows across 293 genes, 138,240 studies, typed `clin_sig` throughout,
> 1★ review floor, per-variant ClinVar citations.

**pathogenic 2.0.0**
> Genome-wide ClinVar pathogenicity flag. — Rebuilt on the just-dna-enricher ClinVar snapshot
> (release 2026-06-27, sha256-pinned); see the cardio 2.0.0 notes for the route. 617,001 weight rows
> across 4,793 genes (402,218 pathogenic + 214,942 likely-pathogenic), 622,507 studies. The gene set
> is derived from the snapshot itself rather than authored, so `panel.genes` is empty — the module is
> a genome-wide flag and says so. 159 mitochondrial and chrY rows carry single-allele genotypes.

**pharmgkb 1.0.0** — new module
> Drug response by genotype, from the ClinPGx (PharmGKB) clinical annotations. Supersedes the
> Generation-I `just_drugs` module, which shipped 1,063 ungraded PharmGKB *variant* annotations —
> one row per study finding, with "Significance: no" rows mixed in — and was never migrated for want
> of a schema. This is the aggregated *clinical* annotations instead, at evidence levels
> 1A/1B/2A/2B: the tiers whose variant-drug association is replicated in significant studies, with
> 1A/1B also appearing in a prescribing guideline or drug label. Levels 3 (single study) and 4 (case
> reports) are excluded, which is most of the upgrade. 1,482 rows over 219 clinical annotations, 147
> variants, 55 drugs, 33 genes; one row per (variant, drug, genotype, effect category), because a
> single variant carries separate and sometimes opposed efficacy, toxicity and pharmacokinetic
> findings. Conclusions are ClinPGx's own published sentences, transcribed rather than summarized.
> ClinPGx is CC BY-SA 4.0 and forbids sale, so `licensing.csv` records `commercial_use=false` /
> `declared_use=non_commercial` and the compiler refuses to build without that declaration.

### 3a. Registry (primary) — server-side recompile from the spec

Arguments are `<namespace> <name> <version> <spec_dir>`. The server recompiles, so what is uploaded
is the authored spec, not the parquet.

**`pharmgkb` will publish as `trusted: false`, and that is the honest label.** Registry 0.11.3 made
the facet three-valued and sets it `false` for any module whose compiled output has a positional
table joining by rsID only — which `pharm_variants.csv` does, on all 1,482 rows. It publishes
normally (`would_publish` is true, checked live); the facet says a consumer joining by position gets
nothing from it, which is true until the compiler applies `resolution.csv` to the 0.4 families
(upstream RM43). Do not treat it as a defect to clear before publishing.

The six small modules go through `publish` (multipart); the three panels are over the 25 MiB limit
and go through `import-module` with a tar.gz. Changelog text is in the section above — it is long,
so keep it in a variable rather than inline.

```bash
M=data/interim/v1_port

# The six that fit the multipart route.
uv run pipelines marketplace publish just-dna-seq coronary        1.1.0 $M/coronary        --changelog "$CL_CORONARY"
uv run pipelines marketplace publish just-dna-seq thrombophilia   1.1.0 $M/thrombophilia   --changelog "$CL_THROMBOPHILIA"
uv run pipelines marketplace publish just-dna-seq lipidmetabolism 1.1.0 $M/lipidmetabolism --changelog "$CL_LIPIDMETABOLISM"
uv run pipelines marketplace publish just-dna-seq vo2max          1.1.0 $M/vo2max          --changelog "$CL_VO2MAX"
uv run pipelines marketplace publish just-dna-seq longevitymap    1.2.0 $M/longevitymap    --changelog "$CL_LONGEVITYMAP"
uv run pipelines marketplace publish just-dna-seq superhuman      2.4.0 $M/superhuman      --changelog "$CL_SUPERHUMAN"
uv run pipelines marketplace publish just-dna-seq pharmgkb        1.0.0 $M/pharmgkb        --changelog "$CL_PHARMGKB"

# The three panels: archive first (see the size table above), then import.
for m in cardio cancer pathogenic; do
  tar -czf /tmp/${m}_spec.tar.gz -C $M/$m module_spec.yaml $(cd $M/$m && ls *.csv *.log)
done
uv run pipelines marketplace import-module just-dna-seq cardio     2.0.0 /tmp/cardio_spec.tar.gz     --changelog "$CL_CARDIO"
uv run pipelines marketplace import-module just-dna-seq cancer     2.0.0 /tmp/cancer_spec.tar.gz     --changelog "$CL_CANCER"
uv run pipelines marketplace import-module just-dna-seq pathogenic 2.0.0 /tmp/pathogenic_spec.tar.gz --changelog "$CL_PATHOGENIC"
```

Because the registry was wiped there is no current latest to supersede, so plain `publish` /
`import-module` is right. On a server that still holds the old versions, use
`update-module-version` instead — it checks the new version actually supersedes the current one:

```bash
uv run pipelines marketplace update-module-version just-dna-seq superhuman 2.4.0 $M/superhuman
```

### 3b. HuggingFace collection (legacy mirror)

All ten modules go here. This uploads the **compiled** artifacts — not the spec — to
`datasets/just-dna-seq/annotators/data/<name>/`, one commit per module. **39.6 MiB in total**,
`pathogenic` being 27.3 MiB of it.

**Step 0 — authenticate.** There is no HF token on this machine right now (`get_token()` returns
None), so this is a real prerequisite rather than a formality. The account needs *write* access to
the `just-dna-seq` org.

```bash
hf auth login                       # or: export HF_TOKEN=hf_…
uv run python -c "from huggingface_hub import whoami; print(whoami()['name'])"
```

**Step 1 — dry run, and read the file lists.** Writes nothing and contacts nobody.

```bash
MODULES="coronary thrombophilia lipidmetabolism vo2max longevitymap superhuman pharmgkb cardio cancer pathogenic"
for m in $MODULES; do uv run pipelines v1-port publish "$m" --dry-run; done
```

The argument is a module **name** resolved under `--out` (default `data/interim/v1_port`), or a
**directory** — `uv run pipelines v1-port publish data/interim/v1_port/coronary --dry-run` does the
same thing, and is how you publish a module built somewhere else. The name in the collection is the
directory's own basename either way.

Expect **7 files** for the six curated modules (`weights`, `annotations`, `studies`, `sources`,
`literature`.parquet + `manifest.json` + `logo.png`), **6** for the three panels, which have no
`literature.parquet` because their grounding is per-variant ClinVar citations rather than a literature
pass, and **3** for `pharmgkb` (`pharm_variants` + `sources`.parquet + `manifest.json`) — it is led by
a 0.4 table and has neither annotations nor studies. A module printing fewer than its shape calls for
is missing an artifact; rebuild it rather than publishing a partial one.

**Step 2 — publish.** Sequential on purpose: each is its own commit, and a failure halfway leaves the
earlier ones intact and re-runnable (`upload_folder` overwrites by path).

```bash
for m in $MODULES; do
  echo "── $m"
  uv run pipelines v1-port publish "$m" || { echo "FAILED: $m"; break; }
done
```

**Step 3 — verify from the outside**, not from the log. Run discovery against the live collection,
which is the check that matters: it answers "does the app see the module", not merely "did files
land".

```bash
uv run pipelines clear-module-cache    # so this reads the collection, not yesterday's copy
uv run pipelines list-modules
```

Every published module must appear in that table. A module whose files uploaded but which is absent
here is not discoverable, which for the app's purposes means not published.

The enricher's own publisher is the canonical 0.5 surface and does the same upload, if you would
rather not go through the port CLI:

```bash
uv run just-dna-enricher upload data/interim/v1_port/coronary --repo just-dna-seq/annotators
```

**`pharmgkb` is led by `pharm_variants.parquet` and has no `weights.parquet`**, which is fine:
discovery probes every family in `module_config.LEAD_TABLES`, so it is found, published and annotated
like any other module. Two consequences worth knowing. Its rows carry no coordinates — the compiler
materializes the 0.4 families verbatim from their CSV and applies `resolution.csv` to
`weights.parquet` only — so annotation joins it on **rsid + genotype** instead of by position; a VCF
with no rsIDs in its `ID` column will match nothing from it. And its report rows are ordered by
ClinPGx evidence level rather than by weight, since it has no weights to rank.

## 4. After publishing

- Add any new module to `modules.yaml` under `module_metadata:` if it is not there already
  (`pharmgkb` is; `drugs` remains as the Generation-I alias).
- `uv run pipelines clear-module-cache` so the app re-discovers.
- Update `docs/V1_PARITY.md`.

## What changed in these builds, and why a version bump is unavoidable

- **Resolution moved out of the compiler.** The port now runs `just-dna-enricher enrich` and ships
  `resolution.csv`; the compile is inject-only. `compile_module(ensembl_cache=…)` is deprecated and
  goes at 1.0.
- **`weights` 19–20 → 37 columns, `annotations` 5 → 8, `studies` 7 → 19**, and `variant_key` is now
  a GA4GH VRS identifier rather than `chrom:start:ref`. Every digest moves. See
  [MODULE_FORMAT_0_5_MIGRATION.md](MODULE_FORMAT_0_5_MIGRATION.md).
- **`literature.csv` is new** on the curated modules: PubMed/Crossref identity for every cited PMID,
  written once and then read offline.
- **The three ClinVar modules are rebuilt, not re-ported** — see
  [V1_PARITY.md](V1_PARITY.md) §4.
