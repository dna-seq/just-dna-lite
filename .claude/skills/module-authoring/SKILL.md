---
name: module-authoring
description: Author, resolve, compile and publish a just-dna annotation module — the spec directory layout, the CSV column contracts and vocabularies, the enrich→compile pipeline, and the checks that decide whether a module will publish. Use when creating a new annotation module, editing an existing spec (variants.csv, pharm_variants.csv, module_spec.yaml), debugging a validate/compile failure, or preparing a module for the registry.
---

# Authoring an annotation module

A module is a **directory of authored CSVs plus a YAML header**. A compiler turns it into parquet
with a content-addressed manifest. You never write parquet by hand and never commit coordinates you
looked up yourself — a separate resolution step fills those and records where they came from.

Three packages, three jobs. Keep them straight; most confusion comes from mixing them up.

| package | CLI | does | never does |
|---|---|---|---|
| `just-dna-format` | — | the schema: models, vocabularies, identity rules | touch the network |
| `just-dna-compiler` | `just-dna-compiler` | spec directory → parquet + `manifest.json` | touch the network |
| `just-dna-enricher` | `just-dna-enricher` | resolve rsIDs→coordinates, fill citations, mint VRS ids | decide what a variant *means* |

The compiler is **inject-only**: it reads a `resolution.csv` the enricher produced. It will not go
and look a coordinate up for you.

## The workflow

```bash
uv run just-dna-compiler scaffold my_module --name my_module        # 1. skeleton
#                                                                     2. fill the YAML placeholders
#                                                                     3. author the CSVs by hand
uv run just-dna-compiler hint variants.csv --file my_module/variants.csv   # 4. writes nothing
uv run just-dna-enricher  enrich  my_module                         # 5. → resolution.csv
uv run just-dna-enricher  literature my_module                      # 6. → literature.csv (online)
uv run just-dna-compiler validate my_module --strict                # 7. the publish gate
uv run just-dna-compiler compile  my_module my_module/out --strict  # 8. → parquet + manifest.json
```

**Step 2 is not optional.** `scaffold` writes `<<REPLACE>>` into `module.title`, `description` and
`report_title`; leaving any of them fails validation with *"unreplaced template placeholder"*. The
same convention appears wherever a tool refuses to invent a value for you.

`hint` takes the **table kind as a positional** plus `--file` (or `--row` for inline text) — it lints
CSV text, not a directory. Its `info:` lines are worth reading: they name the columns deliberately
left to you, because filling them from the same source a later check compares them against would
make that check vacuous.

Steps 5 and 6 are the only ones that use the network. Once `resolution.csv` and `literature.csv`
exist they *are* the pin: every later compile is offline and reproducible.

A successful compile prints four hashes — `digest`, `content_signature`, `resolution_signature`, and
the resolution mode. Recompiling an untouched spec must reproduce all of them.

In this repo the same tiers are mounted on one CLI, which is usually what you want because it loads
`.env` for cache paths: `uv run pipelines module …`, `uv run pipelines enrich …`.

## Directory layout

```
my_module/
  module_spec.yaml     # required: identity + display
  variants.csv         # the lead table (or pharm_variants.csv, diplotypes.csv, pgs.csv …)
  studies.csv          # required when variants.csv is present: the grounding
  resolution.csv       # produced by `enrich` — coordinates + VRS ids. Commit it.
  literature.csv       # produced by `literature` — PMID/DOI existence. Commit it.
  licensing.csv        # required when data came from a licence-bearing source
                       # (`sources.csv` is the deprecated 0.5 spelling — read, warned, gone at 1.0)
  logo.png             # optional
```

One CSV = one concern. A module leads with **exactly one** primary table. A drug-response module
carries `pharm_variants.csv` and **no** `variants.csv`.

## module_spec.yaml

```yaml
schema_version: "1.0"          # always this
module:
  name: my_module              # lowercase alphanumeric + underscores. `my-module` is rejected.
  version: "1.0.0"             # SemVer STRING. Unquoted 1 parses as int and is rejected.
  title: My Module
  description: One sentence a non-specialist can read.
  report_title: What the report section is called
  icon: heart
  color: "#db2828"
genome_build: GRCh38
license: CC0-1.0               # SPDX id; must not contradict licensing.csv
authorship:
  - who: your-name
    role: created
    kind: [human]
```

`module:` is `extra="forbid"` — a typo like `colour:` is a hard error, not a silent drop.

## variants.csv

**Always required:** `genotype`, `state`, `conclusion`
**Identity — one of:** `rsid` **or** `chrom` + `start`
**Optional:** `ref`, `alts`, `weight`, `negatives`, `priority`, `gene`, `phenotype`, `category`,
`clinvar`, `pathogenic`, `benign`, `curator`, `method`, `direction`, `stat_significance`,
`effect_size`, `effect_measure`, `effect_allele`, `flags`, `trait_efo_id`, `clin_sig`,
`requires_callable`, `acmg_sf`, `actionability`, `callable_from`, `quality_from`, `min_quality`

Do **not** author `variant_key` or `authored_ident` — the compiler derives them, and `variant_key`
is frozen at load, so an authored one is not overwritten.

```csv
rsid,genotype,weight,state,conclusion,gene,clin_sig
rs1801133,A/A,-0.5,risk,Reduced MTHFR activity; homozygous,MTHFR,
rs1801133,A/G,-0.25,risk,Reduced MTHFR activity; heterozygous,MTHFR,
rs1801133,G/G,0.0,neutral,Normal MTHFR activity,MTHFR,
```

### Vocabularies (closed — anything else is rejected)

- **`state`**: `alt`, `neutral`, `protective`, `ref`, `risk`, `significant`
- **`direction`**: `neutral`, `protective`, `risk`, `unknown`
- **`stat_significance`**: `not_significant`, `significant`, `suggestive`, `unknown`
- **`clin_sig`**: `affects`, `association`, `benign`, `conflicting`, `drug_response`,
  `likely_benign`, `likely_pathogenic`, `not_provided`, `other`, `pathogenic`, `protective`,
  `risk_factor`, `uncertain_significance`
- **`flags`** (open list, `;`-separated in a cell; these are reserved): `conditional`, `phased`,
  `pleiotropic`
- **`chrom`**: `1`–`22`, `X`, `Y`, `MT` — no `chr` prefix (`chr1` is normalized, `NC_…` is not)

### Genotype rules

1. **Alphabetically sorted.** `A/G`, never `G/A`. An unphased genotype is a *set*; two spellings of
   one call would be two rows.
2. **Alleles are `[ACGT]+`**, and must be drawn from `{ref} ∪ alts` at that locus. A genotype whose
   alleles are not at the locus can never match a VCF.
3. **Non-diploid contigs take a single allele.** On `MT` (haploid) and on `Y` outside the
   pseudoautosomal regions (hemizygous) write `G`, not `G/G` or `A/G` — a two-allele call there
   asserts a second copy that does not exist. The compiler warns if you get this wrong, but only
   warns, and the warning is aggregated, so on a large module it is easy to miss. PAR1/PAR2 on Y
   *are* diploid; a mixed mitochondrial population is heteroplasmy and belongs in
   `heteroplasmy.csv`, not in a het genotype.
4. **Indels are spelled out**: `A/AG`, `C/CTT` — reference-anchored, VCF convention.
5. `ref`/`alts` may only appear **with** `chrom`+`start`. You cannot attach alleles to a bare rsID.

### Author by identity, not by coordinate

Prefer `rsid` alone and let `enrich` fill the coordinate. Author `chrom`+`start`+`ref`+`alts` only
when there is no rsID (roughly 10% of ClinVar pathogenic variants), or when one rsID names several
alleles at a locus and the row must say which.

## studies.csv

**Always required:** `pmid`. **Identity — one of:** `rsid` or `chrom` (+`start`, `ref`).
Optional: `population`, `p_value`, `conclusion`, `study_design`, `doi`, `trait_efo_id`,
`effect_size`, `effect_measure`, `stat_significance`, `provenance_quote`, `provenance_regex`.

- A study **must carry the same identity its variant row got.** If the variant is keyed by
  coordinate, the study must be too, or it is an orphan.
- **`pmid` is 1–8 digits.** Nine-digit ids are not PubMed ids and are rejected.
- Never invent a PMID. Verify each one resolves before writing it.

## pharm_variants.csv (drug response)

**Always required:** `drug`, `conclusion`. **Identity — one of:** `rsid` or `chrom`+`start`.
Optional: `ref`, `gene`, `genotype`, `phenotype_category`, `annotation_id`, `response`,
`evidence_level`, `trait_efo_id`.

The duplicate key is `(variant, drug, genotype, phenotype_category, annotation_id)` — one variant and
drug legitimately carry separate efficacy, toxicity and pharmacokinetic rows, and they can disagree.
`phenotype_category` is closed: `dosage`, `efficacy`, `metabolism_pk`, `other`, `pd`, `toxicity`.
This module type carries **no** `variants.csv` and needs no `studies.csv`.

## resolution.csv — produced, committed, never hand-edited

`enrich` writes one row per resolved locus: `variant_key, rsid, chrom, start, ref, alts,
genome_build, vrs_id, source, status, …`. It is what makes a compile offline and reproducible, and
it travels with the module.

- **Existing rows are authoritative and merged, never overwritten.** To re-resolve after changing
  the authored table, **delete `resolution.csv` first** — otherwise stale rows survive silently.
- A locus whose authored genotype it cannot host is **left out** and reported. That is deliberate:
  recording it would hand the compiler a locus it must drop.
- `--offline` restricts to local caches. Substitution VRS ids mint offline; **indels and MNVs need
  the reference sequence**, so an offline run leaves them unminted (expect ~50% coverage on an
  indel-heavy module, ~99% online).

## licensing.csv and licensing

**The file is `licensing.csv` from format 0.6 on.** `sources.csv` is the deprecated spelling: still
read, warned about, and removed at 1.0 (RM51). A drafting pass writes whichever copy the module already
carries and creates the new name when there is none, so you normally never choose — but if you are
hand-editing, use `licensing.csv`, and **never let both exist**: two copies of a fact-hashed,
hand-editable table are two claims, so the compiler refuses rather than picking a winner. Reach for it
in code through `just_dna_format.layout` (`resolve_sidecar`, `sidecar_write_path`), never by name.

**The rename stops at the file.** The compiled parquet is still `sources.parquet` and the manifest key
is still `manifest.sources`, both for the whole 0.x tail, because they sit inside `artifact.digest` or
are published keys. So a module reads `licensing.csv` → `sources.parquet` → `manifest.sources`. That is
a real legibility cost, taken knowingly; do not "finish" the rename.

Any module built from a licence-bearing source needs a `SourceRow` recording the terms. Passes that
read such a source write it for you. Two rules that bite:

- The compiler **refuses to build** content from a no-sale source unless `declared_use` is recorded.
  Delete the cell and the compile fails — that is the gate working.
- `license:` in the YAML must not contradict `licensing.csv`. A ClinVar module declaring `CC0-1.0`
  warns, because the source row says `public-domain`; they are the same grant, but the check compares
  spellings. Match the source's spelling.

## Verification — and what `--strict` changes

```bash
uv run just-dna-compiler hint variants.csv --file my_module/variants.csv   # rewrites nothing
uv run just-dna-compiler validate  my_module --strict
uv run just-dna-compiler signature my_module    # content signature, no compile
uv run just-dna-compiler compile   my_module out/ --strict
```

**Author against `--strict`, because that is what a registry runs.** The difference is not cosmetic:

| condition | plain | `--strict` |
|---|---|---|
| genotype allele not among the locus's alleles | warning, **valid** | **error, invalid** |
| two-allele genotype on `MT`/`Y` | warning | warning |
| unresolved rows (no coordinate) | warning | counts against publishability |

A plain `compile` **succeeds** through both of the above. So "it compiled" is not evidence the module
is correct — a module can compile cleanly and contain rows that will never match a genome.

Check what you shipped, don't assume:

```bash
uv run python -c "
import polars as pl; w = pl.read_parquet('out/weights.parquet')
print(w.height, 'rows;', w.filter(pl.col('chrom').is_not_null()).height, 'with a coordinate')"
```

`0 with a coordinate` means resolution did not reach the compile — see the trap below.

## Traps that cost real time

Current as of **compiler/enricher 0.5.2**.

**`compile_module(resolve_with_ensembl=False)` disables `resolution.csv` too.** The name reads as
"don't use Ensembl", which is exactly what a spec carrying its own resolution wants. It is the master
switch for *all* resolution: set it False and every row compiles with `chrom=None`, and the compile
**succeeds** — it warns, but a script checking only the exit status ships a module that can never
match a genome. The correct call is `resolve_with_ensembl=True, ensembl_cache=None`: switch on, no
cache, injected-table path.

**Deleting `resolution.csv` is part of a rebuild.** Existing rows are authoritative and merged, so a
fix that changes an authored allele will not show up until you delete the file first. That is
deliberate — the table is a pin, not a cache.

**A drafted panel does not need a zygosity decision on every row.** `draft_gene_panel` writes the sole
expressible genotype where the contig leaves nothing open — the mitochondrial genome, and chrY outside
the pseudoautosomal regions, decided per locus — and keeps `<<REPLACE>>` only where a real judgement
remains. If you expand placeholders into both zygosities, expand *only* what is still a placeholder;
do not key that off the contig yourself.

**`licensing.csv` must cover every source your fact tables cite**, including PubMed if you carry
studies. A missing row is a warning, not an error, so it is easy to ship without noticing.

**A re-draft always changes `artifact.digest`, even when the data is identical.** `licensing.csv`
carries a `fetched_at` timestamp stamped when the row is written, and `sources.parquet` is one of the
parquets the digest is a Merkle root over — nineteen of them as of 0.6, not four — so two builds of
byte-identical content, an hour apart, are two different artifacts. Verified by changing *only* `fetched_at` and recompiling: the digest
moves. Consequences worth planning around:

- **Recompiling is reproducible; re-drafting is not.** `compile` twice on an untouched spec gives the
  same digest every time. That is the property to test, and the checklist below says so.
- **Do not treat a digest change as evidence that content changed.** Diff the tables.
- **Digest-based dedup will miss matches** across rebuilds, so `find-by-hash` cannot recognise a
  module you rebuilt without editing.

If you need a rebuild to be digest-stable, keep the previous `licensing.csv` rather than letting the
draft re-stamp it.

**Upgrading a module to 0.6 moves its `artifact.digest` on its own**, with no edit at all: the compiler
emits new stamped columns (`weights.parquet` went 37 → 39). `content_signature` — the authored-content
identity, and the one that claims a dedup slot — does **not** move, measured at 0/11 and 0/16 upstream.
So re-pin stored digests at the version boundary and do not read the change as a content change.

## Publishing

Version deliberately. A rebuild that changes the compiled shape still moves `artifact.digest`, so it
needs a version either way; a rebuild that changes *what variants are in the module* or how they are
grounded is a **major**, because someone pinned to the old major would silently receive different
content.

```bash
uv run pipelines marketplace validate <ns> <name> <spec_dir>            # server-side, no publish
uv run pipelines marketplace check    <ns> <name> <spec_dir> --identifiers
uv run pipelines marketplace publish  <ns> <name> <version> <spec_dir> --changelog "…"
```

- `check` = validate **plus** network checks (`ref` against the genome, rsID currency, VRS coverage);
  it returns `would_publish`, the one field to branch on. It has a variant ceiling, so a large module
  gets `422 too_many_variants` — use `validate`, which has no network tier and decides publishability.
- A spec whose raw parts exceed the server's transfer bound needs `--pack` (client-side tar.gz).
- Write the changelog as a continuation of the previous one, not a fresh "initial release".

There is a **second, separate** destination: the HuggingFace annotator collection, which the app
discovers directly. It takes the **compiled** artifacts rather than the spec, and the two are
published independently — no command does both, and that is deliberate for now.

```bash
uv run pipelines v1-port publish <module_dir|name> --dry-run   # prints the exact file list
uv run pipelines v1-port publish <module_dir|name>             # needs HF_TOKEN / `hf auth login`
```

Discovery decides a directory is a module by probing every family in `module_config.LEAD_TABLES`, so
a module led by a 0.4 table (`pharm_variants.parquet`, `diplotypes.parquet`, `pgs.parquet`, …)
publishes here too — add a new family to that tuple and it becomes discoverable and publishable at
once. Verify with `pipelines list-modules`, which answers whether the app can see the module rather
than merely whether files landed.

A 0.4-led module is joined against the VCF on **rsid + genotype**, not by position: the compiler
materializes those families verbatim from their authored CSV and applies `resolution.csv` to
`weights.parquet` only, so their `chrom`/`start` arrive null. `validate` and `compile` both warn
about this per table, naming how many rows are unplaced and how many `resolution.csv` could place —
the warning is expected on an rsid-authored PGx module, is never a `--strict` error, and is not
something you can clear by editing the spec. Author the rsid, and expect no matches from a VCF whose
`ID` column is empty. Such a module also publishes to the registry as `trusted: false`, which is the
facet reporting that same fact rather than a problem with your module.

## Checklist before you call a module done

- [ ] `validate --strict` passes
- [ ] every weight row has a coordinate (or you can say why not)
- [ ] genotypes sorted; single-allele on `MT`/`Y`; alleles drawn from the locus
- [ ] every PMID verified to exist, 1–8 digits, and reachable from a weighted variant
- [ ] `resolution.csv` and `literature.csv` committed alongside the CSVs
- [ ] `licensing.csv` present (not `sources.csv`, and never both) and consistent with `license:` if a
      licensed source was used
- [ ] `module.version` is a quoted SemVer string
- [ ] a second **compile** of the untouched spec reproduces the same `artifact.digest` (a re-**draft**
      will not — `licensing.csv` re-stamps `fetched_at`, which is inside the digest)
