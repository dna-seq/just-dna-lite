# Agent Guidelines

This document outlines the coding standards and practices for **just-dna-lite**.

---

## Repository Layout (uv workspace)

This repo is a **uv workspace** with two member projects:

- `just-dna-pipelines/`: pipeline/CLI library (Python package: `just-dna-pipelines`)
- `webui/`: Reflex Web UI (Python package: `webui`)

Shared, repo-level folders live at the workspace root (e.g. `data/`, `docs/`, `logs/`, `notebooks/`).

We sometimes (for example purposes) add prepare-annotations to the workspace. This folder is READ-ONLY you are not allowed to make changes in it!

### Running the App

The recommended way to start the application is from the repo root:

- `uv run start` - Starts the Reflex Web UI development server.

**Ctrl+C must kill the Dagster daemon tree, not just `dg`.** Launchers detach `dg` (`start_new_session` on POSIX, `CREATE_NEW_PROCESS_GROUP` on Windows). Shutdown is in `just_dna_lite.process`: POSIX uses SIGINT then SIGKILL; Windows uses `CTRL_BREAK_EVENT` then `TerminateProcess`. Startup also reaps leftover Reflex UI processes for this workspace so a stale frontend cannot keep port 3000. A second `uv run start` is last-writer-wins (no pidfile); the dying instance only reaps PIDs that already existed when shutdown began. Ctrl+Z/`SIGTSTP` is POSIX-only. See `tests/test_process_shutdown.py`.

### uv Script Entry Point Collisions

If `uv run start` or another project script unexpectedly resolves to a dependency's script
(for example `prs-ui`'s `start` instead of Just-DNA-Lite's `start`), do **not** rename the
user-facing command or duplicate script entries in workspace members. This can happen after
dependency upgrades when uv keeps stale generated wrappers in `.venv/bin`. Bump the main
`just-dna-lite` package version after upgrading dependencies, then run `uv sync` so uv rebuilds
and reinstalls the root package entry points. The root package's script should own public commands
like `start`.

---

## Dependency Pins — Where Every Version Constraint Lives

Audited 2026-07-28 across all nested `pyproject.toml` files in the multi-repo workspace. Consult
this before hunting for a version pin; **do not re-derive it by grepping every repo.**

### Every `pyproject.toml` in the workspace (and whether it hard-pins)

| File | Package | Hard `==` pins? |
|------|---------|-----------------|
| `pyproject.toml` (root) | `just-dna-lite` | no — but has deliberate ceilings, see below |
| `just-dna-pipelines/pyproject.toml` | `just-dna-pipelines` | none |
| `webui/pyproject.toml` | `webui` | **yes — `reflex==X` (the only `==` pin in the whole workspace)** |
| `../just-prs/pyproject.toml` | `just-prs-workspace` | none |
| `../just-prs/just-prs/pyproject.toml` | `just-prs` | none |
| `../just-prs/prs-ui/pyproject.toml` | `prs-ui` | none (`reflex>=`, `reflex-components-*>=`, `reflex-mui-datagrid>=`) |
| `../just-prs/prs-pipeline/pyproject.toml` | `prs-pipeline` | none |
| `../just-dna-format/pyproject.toml` | (workspace root) | none |
| `../just-dna-format/schema/pyproject.toml` | `just-dna-format` | none |
| `../just-dna-format/compiler/pyproject.toml` | `just-dna-compiler` | none |
| `../just-dna-format/enricher/pyproject.toml` | `just-dna-enricher` | none |
| `../just-dna-marketplace/pyproject.toml` | `just-dna-registry` | none |
| `../reflex-mui-datagrid/pyproject.toml` | `reflex-mui-datagrid` | none (`reflex>=0.9.4`) |
| `../reflex-mui-datagrid/examples/datagrid_demo/pyproject.toml` | `datagrid-demo` | none |

**Takeaway: the single hard `==` pin in the entire workspace is `reflex` in `webui/pyproject.toml`.**
Everything else floats on `>=`.

### Non-`==` constraints that still deliberately hold versions back

All in the **root** `pyproject.toml`:

- `grpcio-health-checking<1.82` and `grpcio<1.82` — 1.82.0 ships `_pb2` gencode built against
  protobuf 7.35, but dagster caps `protobuf<7`; the resolved protobuf 6.x is then older than the
  gencode and dagster fails to import. Keep both in lockstep. (Reason is already commented inline.)
- `google-genai>=1.71.0,<2.0` (also repeated in `webui/pyproject.toml`)
- `requires-python = ">=3.13, <3.14"`
- `agno` is pinned **by git rev**, not version, in root `[tool.uv.sources]`.

There are **no** `[tool.uv] constraint-dependencies` / `override-dependencies` anywhere.

### Upgrading Reflex: the `reflex-components-*` family does NOT follow

`reflex` requires its siblings with `>=` only (`reflex-components-core>=`, `-radix>=`, …), so
bumping the `reflex==` pin and running `uv sync` upgrades **only** `reflex` + `reflex-base` and
leaves every `reflex-components-*` at its already-locked version. Each reflex release is tested
against specific companion versions (check its release notes), so upgrade them explicitly:

```bash
uv lock --upgrade-package reflex-components-core --upgrade-package reflex-components-radix
uv sync
```

Then verify with `uv pip list | grep reflex` against the release notes. Note reflex also caps some
transitive deps (0.9.7 added `wrapt<2.2`, which *downgrades* `wrapt` — expected, not a mistake).

### Frontend (npm) pins

`webui/reflex.lock/package.json` + `bun.lock` are **generated** by reflex — never hand-edit. Reflex
0.9.7 added `rx.Config.frozen_lockfile` (default `True`): if those two drift out of sync, bun's
install fails fast instead of silently updating. Regenerate both together.

---

## Coding Standards

- **Avoid nested try-catch**: try catch often just hide errors, put them only when errors is what we consider unavoidable in the use-case
- **Type hints**: Mandatory for all Python code.
- **Pathlib**: Always use for all file paths.
- **No relative imports**: Always use absolute imports.
- **No inline imports**: All imports must be at the module top level. Never use `from X import Y` inside functions or methods. The only exception is guarded `try/except ImportError` for optional dependencies at module level.
- **Polars**: Prefer over Pandas. Use lazyframes (`scan_parquet`) and streaming (`sink_parquet`) for efficiency.
- **Memory efficient joins**: Pre-filter dataframes before joining to avoid materialization.
- **Data Pattern**: Use `data/input`, `data/interim`, `data/output`.
- **Typer CLI**: Mandatory for all CLI tools.
- **Pydantic 2**: Mandatory for data classes.
- **Eliot**: Used for structured logging and action tracking.
- **Pay attention to terminal warnings**: Always check terminal output for warnings, especially deprecation ones. AI knowledge of APIs can be outdated; these warnings are critical hints to update code to the current version.
- **No placeholders**: Never use `/my/custom/path/` in code.
- **No legacy support**: Refactor aggressively; do not keep old API functions.
- **Dependency Management**: Use `uv sync` and `uv add`. NEVER use `uv pip install`.
- **No dependency paths outside this repo**: `[tool.uv.sources]` may only contain workspace members
  (`{ workspace = true }`). Never add a `path =` / `editable =` entry pointing at a sibling checkout
  (`just-dna-marketplace`, `just-prs`, `just-dna-format`, …) — the absolute path does not exist on
  other machines, in CI, or in containers, and `uv sync` then hard-fails with
  `Distribution not found at: file:///…` before a venv can even be created. Every shared lib we
  consume is published. Test unpublished libs with a temporary uncommitted override only.
- **A pin that will not resolve is something you wait for, not something you reroute**: when a needed
  version is not on PyPI yet, poll for it with exponential backoff for up to ~30 minutes total
  (30s, 1m, 2m, 4m, 8m, 15m) and then stop and report that it is still unpublished. Never work around
  it with a local path source, a vendored copy, or a quiet downgrade of the pin. Poll the index
  directly (`curl -s https://pypi.org/pypi/<pkg>/json`), not by re-running `uv sync` in a loop.
- **Versions**: Do not hardcode versions in `__init__.py`; use `project.toml`.
- **Avoid __all__**: Avoid `__init__.py` with `__all__` as it confuses where things are located.
- **Cross-Project Knowledge**: We sometimes add `prepare-annotations` to the workspace. This folder is **READ-ONLY**. You MUST check `@prepare-annotations/AGENTS.md` for shared Dagster patterns, resource tracking, and best practices. If you find a superior pattern there that is applicable to `just-dna-lite`, you should adopt it and update this file.
- **Self-Correction**: If you make an API mistake that leads to a system error (e.g. a crash or a major logic failure due to outdated knowledge), you MUST update this file (`AGENTS.md`) with the correct API usage or pattern. This ensures future agents don't repeat the same mistake.

---

## Module Configuration (`modules.yaml`)

Annotation module sources and display metadata are configured in **`modules.yaml`**. The loader checks two locations (first found wins):

1. **Project root** (`./modules.yaml`) — preferred, easy for users to find and edit
2. **Package directory** (`just-dna-pipelines/src/just_dna_pipelines/modules.yaml`) — bundled fallback

This is the single source of truth for:

1. **Sources** to scan for modules (any fsspec-compatible URL: HuggingFace, GitHub, HTTP, S3, etc.)
2. **Display metadata** overrides (title, description, icon, color, report_title) for known modules
3. **Ensembl reference dataset** (`ensembl_source.repo_id`) — the HuggingFace dataset used for Ensembl variation annotation

**Modules are always auto-discovered** from the configured sources. The YAML only provides optional display overrides. Modules not listed in `module_metadata` get auto-generated defaults (titlecased name, generic icon, default color).

**Read/write separation**: The repo-root `modules.yaml` is git-tracked and read-only (defaults). All runtime mutations (register/unregister custom modules) write to a working copy at `data/interim/modules.yaml` (gitignored). On first write the repo default is copied as seed. The loader checks working copy → repo root → package dir (first found wins).

### Key files

- **`modules.yaml`** (project root): Git-tracked defaults — sources, Ensembl reference, quality filters, metadata overrides
- **`data/interim/modules.yaml`**: Mutable working copy (gitignored) — written by register/unregister
- **`module_config.py`**: Pydantic models (`Source`, `ModuleMetadata`, `EnsemblSource`, `ModulesConfig`), YAML loader, helper functions (`get_module_meta()`, `build_module_metadata_dict()`, etc.)
- **`annotation/hf_modules.py`**: Discovery logic — scans sources via fsspec, builds `MODULE_INFOS` and `DISCOVERED_MODULES`

### Adding a new module source

1. Upload data to any fsspec-accessible location (HF repo, GitHub, HTTP server, S3, etc.)
2. Add the source URL to `modules.yaml` under `sources:`
3. Optionally add display metadata under `module_metadata:`
4. Modules are auto-discovered on next startup

### Source types (auto-detected from URL)

- `org/repo` (shorthand) or `hf://datasets/org/repo` → HuggingFace
- `github://org/repo` → GitHub via fsspec
- `https://...` → HTTP/HTTPS via fsspec
- `s3://...`, `gcs://...` → cloud storage via fsspec

### Module vs Collection

Each source can be a single module or a collection:
- **Auto-detect** (default): a *lead table* at root = single module; subfolders with one = collection.
  The lead table is any family in `module_config.LEAD_TABLES` — `weights.parquet` for most modules,
  or a 0.4 family (`pharm_variants`, `diplotypes`, `pgs`, …) for one that has no weights. Probing for
  `weights.parquet` alone used to make a pharmacogenomics module undiscoverable, and therefore
  unpublishable to HuggingFace. Add a new family to that tuple and discovery and the publisher both
  learn it at once. A 0.4-led table has no coordinates (the compiler applies `resolution.csv` to
  `weights.parquet` only), so annotation joins it on rsid + genotype instead of by position.
- **Override**: `kind: module` or `kind: collection` in the YAML source entry

### Important patterns

- **Never write to repo-root `modules.yaml`** — use `get_config_path()` which returns the working copy at `data/interim/modules.yaml`
- **Never hardcode module lists or metadata in Python files** — always use `get_module_meta()` or `build_module_metadata_dict()` from `module_config`
- **Never hardcode HF repo URLs** — use `DEFAULT_REPOS` or `MODULES_CONFIG.sources` from `module_config`
- **Never hardcode Ensembl repo ID** — `EnsemblAnnotationsConfig.repo_id` defaults to `MODULES_CONFIG.ensembl_source.repo_id`
- `HF_DEFAULT_REPOS`, `HF_REPO_ID` in `hf_modules.py` are backward-compatible aliases sourced from the YAML

---

## Shared Module Format & Compiler Libraries (`just-dna-format` / `just-dna-compiler`)

The annotation-module **schema** (authored DSL spec + `manifest.json` contract + integrity/identity)
and the **reference compiler** (spec directory → parquet artifact + manifest) were extracted out of
this repo into two published libraries. **Do not re-vendor or fork them here.**

- **`just-dna-format`** (`just_dna_format`, Pydantic + stdlib only):
  - `spec` — authored DSL: `ModuleSpecConfig`, `VariantRow`, `StudyRow`, `ModuleInfo` (+ `VALID_STATES`, `VALID_CHROMOSOMES`, `RSID_PATTERN`, `ALLELE_PATTERN`, `SCHEMA_VERSION`)
  - `manifest` — `ModuleManifest` + `Identity`/`Display`/`Stats`/`Compilation`/`FileEntry`/`Artifact`, `read_manifest`/`write_manifest`
  - `integrity` — `sha256_file`, `artifact_digest` (Merkle root), `build_artifact`, `verify_manifest`
  - `identity` — name/namespace rules, SemVer `Version`, `canonical_id`, legacy `vN → N.0.0`
- **`just-dna-compiler`** (`just_dna_compiler`, adds polars/duckdb): `validate_spec`,
  `compile_module` (emits `manifest.json` with input/artifact hashes + digest), `reverse_module`.
- **`just-dna-enricher`** (`just_dna_enricher`, added in the 0.5 line): the network/reference tier —
  Ensembl/ClinVar/gnomAD/PGx enrichment, and the Ensembl `resolver` (`EnsemblReferenceError`,
  `resolve_variants`). Still **inject-only**: it never downloads a reference.

These libraries are **shared by three repos**: `just-dna-lite` (this one), `just-dna-marketplace`,
and `just-dna-agents`. Treat them as an external contract; **do not assume a symbol is unused** just
because grep finds no consumer in this repo — the other repos may use it.

### How they're wired into this repo
- `just_dna_pipelines.module_compiler` is now a **thin re-export shim** over the libs
  (`models.py` → `just_dna_format.spec` + `just_dna_compiler.models`; `compiler.py` →
  `just_dna_compiler.compiler`). Prefer importing from the libs directly in new code.
- **Ensembl provisioning stays local** (the only non-shim piece): `module_compiler/resolver.py`
  keeps `ensure_resolver_db` (HF download + DuckDB build) because the libs are inject-only.
  `register_custom_module` and the pipelines `resolve_variants` wrapper auto-provision the cache and
  inject it; the bare `compile_module` re-export and the `pipelines module compile` CLI stay
  inject-only (skip resolution with a warning if no cache is present).

### Where things moved in the 0.5 line (format 0.5.0 / compiler 0.5.1 / enricher 0.5.1)

Two import sites in this repo had to move; both are one-liners, but neither is greppable from the
old name, so check here first:

- `RSID_PATTERN` left `just_dna_format.spec` for **`just_dna_format.vocab`** (0.4.0), where the
  identifier grammars now live shared across the authored models. `ALLELE_PATTERN` is still
  re-exported from `spec` for backwards compatibility — `RSID_PATTERN` is not.
- `just_dna_compiler.resolver` is **gone**. The DuckDB-backed lookup moved to
  **`just_dna_enricher.resolver`** (same `resolve_variants(variants, ensembl_cache=...)` signature
  and `EnsemblReferenceError`). What remains in the compiler is `just_dna_compiler.resolution`,
  which is purely table-injected (`resolve_from_table`) and takes no DuckDB path at all.

**The 0.5 digest window is closed:** anything that moves a compiled module's `artifact.digest` — a
new column, a requiredness or identity change — is a 1.0 in the format repo, so 0.5.x is a stable
target. Note the three packages version independently (enricher can take a patch on its own).

**From the 0.4.0 schema change:** compiled artifacts gained ~14 columns (`variant_key`,
`effect_size`, `clin_sig`, `acmg_sf`, …), so freshly compiled modules no longer match the modules
published on HuggingFace under 0.3.x. `VariantRow.variant_key` is frozen at load, so the resolver no
longer backfills `chrom`/`start` onto a keyed row. **But `variant_key` is the *authored identity*, not
always a VRS id** (`derive_variant_key`, format `base.py`): an rsid-authored row keeps its **rsid**
(case 1 — which is why every Gen-I port shows `variant_key=rsid`, not `ga4gh:…`), a coordinate-authored
single-base substitution mints a `ga4gh:VA.…` VRS id (case 2), and everything else is
`chrom:start:ref[:alts]` (case 3). The per-ALT VRS ids for an rsid-authored module live in
`resolution.csv`'s `vrs_id` column, not in `weights.parquet`. `ModuleInfo.version` is a SemVer
**string** (an unquoted `1` in YAML loads as an int and is rejected) — the AI module creator's
template already emits it correctly.

**`direction`/`stat_significance` are authored-optional 0.3 axes and are empty on every Gen-I port**
(those modules were authored against 0.2, when only `state` existed). `weights.parquet` carries the
**authored** value verbatim — the compiler never fills a cell the author left blank (report-never-
repair), so a legacy module's empty `direction` is *correct*, not missing. The mapping
`direction ← state`(+`weight` sign) is a **Python read-time accessor only**
(`VariantRow.effective_direction` / `derive.direction_from_state`), unreachable from a SQL/polars read
of the parquet. **Format 1.0 removes `state` — consumers must key on `direction`.** `report_logic`
is already ready: `_effective_direction(direction, state, weight)` returns the `direction` column when
present, else `direction_from_state(state, weight)` (the format's pure leaf), and
`_variant_sign`/`_variant_color` go through it — so benefit colouring behaves identically on 0.5
(empty `direction` → derived from `state`) and survives the 1.0 `state` removal (populated `direction`
→ used directly). **Any new parquet-side read of `direction`/`stat_significance` must do the same** —
derive with `just_dna_format.derive.direction_from_state(state, weight)`; never treat the empty 0.5
column as directionless. Whether the artifact itself should carry the derived axes is a format-0.6
question tracked in just-dna-format's ROADMAP.

**Status (2026-08-09):** the tests are re-baselined and green, and all ten modules are rebuilt under
0.5 in `data/interim/v1_port/`. What is left is **republishing**, which is the maintainer's call —
see [docs/MODULE_RELEASE_0_5.md](docs/MODULE_RELEASE_0_5.md).

### Contract facts (0.1.0 libs)
- `validate_spec().stats` keys: `variant_count`, `unique_rsids`, `gene_count`, `genes` (sorted list),
  `categories` (sorted list), `study_count`, `module_name` — renamed from the old
  `unique_genes`/`study_rows`/`unique_variants`.
- `VALID_PRIORITIES` and `PMID_PATTERN` are intentionally **not** in `just_dna_format.spec` (dead
  code in the old schema; the live study rule is only "pmid non-empty").

### 0.5 traps that cost real time (MANDATORY reading before touching a module build)

**`compile_module(resolve_with_ensembl=False)` is the master switch for resolution, not a choice of
reference.** The name reads as "do not use Ensembl", which is what a migration to `resolution.csv`
wants — but it also disables the injected-table path, so a module with a complete `resolution.csv`
compiles **successfully** with `chrom=None` on every weight row. Those rows can never match a VCF.
The 0.5 call is `compile_module(spec, out, resolve_with_ensembl=True, ensembl_cache=None)`.

**Call `load_env()` before the first `resolve_*_reference()` in a process.** The enricher's resolvers
call `load_env()` inside `_resolve_parquet_cache`, but pass `default_*_cache_dir()` as an *argument* —
evaluated before that call. So the **first** resolve in a fresh process computes its default from
platformdirs and returns `None` even when `$JUST_DNA_PIPELINES_CACHE_DIR` names a full cache; every
later call is fine. `v1_port/runner.py` and `tests/test_modules_0_5.py` both `load_env()` at import
for exactly this reason.

**`just-dna-enricher cache pull` writes where `cache status` does not look.** Same root cause: `pull`
lands in `~/.cache/just-dna-pipelines/` while every resolver reads the configured cache dir, so
`status` reports "absent" straight after a successful pull. Move them:
`mv ~/.cache/just-dna-pipelines/{clinvar,clinpgx,cpic,gnomad_constraint} "$JUST_DNA_PIPELINES_CACHE_DIR"/`.

**`clinvar_draft` raises on ClinVar's own citation ids.** `var_citations.txt` carries 632k
PubMedCentral ids and a few malformed "PubMed" ones (Variation 12606 cites `168335863`, nine digits);
`StudyRow.pmid` takes at most eight digits, and `draft_gene_panel` aborts the whole panel on the first
one. `v1_port/clinvar_panel.py` passes `max_citations=0` and drafts its own `studies.csv` with a PMID
filter.

**`enrich()` was quadratic in module size — fixed in enricher 0.5.2, and the workarounds are gone.**
Kept here because the symptom is so misleading: `cardio` sat at **12% CPU with no disk I/O for two
hours**, which reads like a deadlock and was one enormous DuckDB expression tree. The ClinVar reader
OR-chained one predicate per allele, which cannot be folded into a hash probe, so cost grew with
`alleles × rows`. 0.5.2 joins a probe table instead. Measured here after the bump: **76,078 rows
resolve in 13.3 s (0.17 ms/row), and the rate improves with size** — against 4.6 ms/row before.

Two mitigations existed and have been **removed** rather than left dormant: `enrich_in_batches`
(10k-row slicing with resume) and `PANEL_VERIFY_CLIN_SIG=False`. If you are reading old code or an
old branch that still has them, they are dead weight now. The `clin_sig` skip in particular is better
in the library than it was here: 0.5.2 compares the module's `panel:` pin against the snapshot's
`release.json` and skips **only on an established match**, so a hand-authored module or one pinned to
a different release still gets checked — where the local flag was unconditional. The reason travels
on `EnrichmentResult.clin_sig_not_checked`, so an empty conflict list is no longer ambiguous.

All five are filed upstream in `/data/sources/just-dna-format/docs/ROADMAP.md`.

**Resolution is scoped to `variants.csv`, so a 0.4-family table joins by rsID only.** The compiler
materializes `pharm_variants` / `haplotypes` / `heteroplasmy` verbatim from their authored CSV and
applies `resolution.csv` to `weights.parquet` alone — so an rsid-authored PGx module compiles clean,
validates, publishes, and carries a null `chrom`/`start` on every row. Compiler **0.5.3** makes this
visible rather than silent (`_check_positional_joinability`, a warning in both plain and `--strict`,
naming how many rows are unplaced *and* how many `resolution.csv` could place); it does **not** fill
them. Materializing the coordinate breaks Principle 7 — `reverse_module` would read it back as
authored — so the fix waits on RM43 and a `0.4`-family equivalent of `VariantRow.authored_ident`.

Two consequences live here. `hf_logic.annotate_vcf_with_module_weights` detects the null-coordinate
case and downgrades a position join to **rsid + genotype**, because the alternative is annotating
nothing at all; a VCF with no rsIDs in `ID` (DeepVariant output among them) therefore matches such a
module on nothing, and the engine now says so (`step="vcf_has_no_rsids"`) rather than reporting a
silent zero. And registry **0.11.3** reads the same warning to make `trusted` three-valued, so
`pharmgkb` publishes as `trusted: false` — correct, not a defect to work around.

### The annotating engine's side of the contract (`hf_logic.py`)

The engine projects **nothing** from a module's lead table — it reads five columns (`rsid`, `chrom`,
`start`, `ref`, `genotype`) and left-joins the rest opaquely, so all 37 columns of a 0.5 artifact
already reach the output parquet. Anything missing from a report is missing *in the report*, not
dropped here. Three rules it does enforce, each with a failure it exists to prevent:

- **A lead table is classified by the schema it has, not by its family name** (`_lead_join_strategy`
  → `position` | `rsid` | `unsupported`). Ten families exist and the format keeps adding them;
  `diplotypes`, `pgs`, `allele_function` and the binning families carry no per-variant key at all, and
  used to raise `ColumnNotFoundError` **and abort every other selected module with it**. They now
  raise `UnsupportedLeadTable`, which the per-module loop records and skips past. Adding a family to
  `LEAD_TABLES` therefore cannot break annotation for anyone else.
- **`_normalize_lead_genotype` puts the lead table's genotype in the representation
  `weights.parquet` already uses**, mirroring the compiler's own `_split_genotype`: split on `/` or
  `|`, drop empties, **never sort**. The 0.4 families are materialized verbatim and keep the authored
  `"C/C"` string, so joining one straight to the VCF's `List(Utf8)` is a `SchemaError` — which is why
  `pharmgkb` could not be annotated at all. **Do not sort here**: the grammar already requires an
  unphased `A/G` to be sorted, and a phased `A|G` is held in *homolog order*
  (`AuthoredModel._validate_genotype`: "phase encodes which allele sits on which homolog"), so
  sorting folds `A|G` and `G|A` into one key and manufactures a match the module never stated. The
  first version of this function sorted, and no test in the corpus could have caught it — nothing we
  ship carries a phased genotype. `report_logic._genotype_alleles` is the Python twin; keep the two
  documented together.
- **The position join requires `ref` agreement where the module states one.** Genotype lists hold
  allele *strings*, so matching them constrains the alleles the sample carries — but the module's
  `ref` used to be dropped outright, so `G>A` matched a module's `GTGTCT>A` at the same locus. On one
  real sample that was **6 of 9** reported `pathogenic` findings, every one a different variant whose
  ALT happened to coincide. String equality is the wrong test for indels in general — one indel has
  several valid spellings, which is what `just_dna_format.alleles` (`parsimony_reduce` /
  `event_profile`) is for — but it is right on the set this filter reaches, and that is pinned by a
  test rather than assumed: once the genotype has matched, a differing `ref` means the two records
  delete different numbers of bases, which that algebra calls a **positive contradiction**. Verified
  on all eight real cases (6 contradictions, 2 matches, no "unknown" residual). The genuinely lost
  matches are elsewhere — two spellings anchored at *different* positions never meet in a position
  join at all, and settling those needs the enricher's sequence access.

- **Contig spellings go through `just_dna_format.vrs.normalize_chrom`, not a `^chr` strip.** Stripping
  alone turns an hs38DH sample's `chrM` into `M`, which no module writes, so **every mitochondrial
  annotation vanished silently** — one of the three samples in this repo is that case, and
  `heteroplasmy` is a whole 0.4 family about mtDNA. Using the format's own folding is what keeps our
  spelling and the module's identical by construction. Mapped over the *distinct* contigs and applied
  as one vectorized replace; a per-row Python call over millions of variants is not acceptable here.
- **The rsid join keys on each identifier a record carries.** A VCF ID is a semicolon-separated list
  (`rs123;rs456`), and the authored side names exactly one variant per row, so the split is the
  consumer's job (just-dna-format RM64). `_vcf_rsid_join_keys` explodes into `_rsid_join_key`, which
  is dropped after the join so the output keeps the record's ID verbatim.

`AnnotationManifest` records `output_dir`, per-module `lead_table`, and `skipped_modules` /
`failed_modules` by reason — do not reconstruct the output directory from `modules[0]`, which is not
there when every module was skipped.

**A run also records which module *bytes* produced it** — `ModuleOutputMapping.version` / `digest` /
`source_url`, filled by `read_module_provenance` (`hf_modules.py`) and rendered as the report's
"Modules in this report" table. Without it a saved report cannot be tied to the module version behind
it and nothing can answer *which of my results are stale*, which is also the missing prerequisite
under any later verification harness (the format tier's RM7). Three rules:
- **All three are tri-state**: `None` means *not established*, never "unversioned". Only an
  acquisition path that puts `manifest.json` on disk (a registry install or a local compile) can
  answer at all — `scan_module_table` reads a remote parquet URL and never fetches a manifest, so an
  HF-discovered module states `source_url` and nothing else. The template renders the rest as
  *Not stated*.
- **The digest is the module's claim, not a check.** Nothing in this repo calls
  `just_dna_format.integrity.verify_manifest` (the verify-then-install flow in
  `docs/MODULE_MARKETPLACE_SPEC.md` is specified and unimplemented, and marked as such), so it ties a
  report to a *stated* identity. Do not present it to a reader as verification. If you do wire
  verification: `require_marketplace=True` is the default and would reject every locally-compiled
  module, whose `compiled_by` is null by design.
- **Version falls back from `identity.version` to the authored spec** (`module_config.spec_version`),
  because the compiler leaves identity null — the registry stamps it at publish. Six of our own
  Gen-I ports author `version: null`, so *Not stated* is currently the common case; that is the
  porting pipeline's gap, not the report's.

**"Is this a module" is one predicate, `module_config.has_lead_table` / `find_lead_table`** — the
local-filesystem twin of discovery's fsspec `_find_lead_table`, both keyed on `LEAD_TABLES`. Probing
`weights.parquet` is not the test: a drug-response module carries `pharm_variants` and no weights, and
testing for weights in `list_custom_modules`, `get_custom_module_specs` and the webui's
`_scan_local_modules` left a `pharm_variants`-led registry install annotatable but **absent from the
publish/edit pane**, so it could not be published or edited at all. A new 0.4 family is one edit in
`LEAD_TABLES` for both sides.

**The count the engine returns is matched rows, never the parquet's height.** A position join keeps
every unmatched VCF row on purpose (the report needs them to tell "probed and did not match" apart
from "never looked"), so the height is a *positions probed* number. Reporting it as variants
annotated made `total_variants_annotated` read **567 against a real 259** on Anton's genome and told
the user "cancer: 29 variants" for a module that annotated none. `annotate_vcf_with_module_weights`
returns `(path, num_matched, restoration_stats)`; both numbers travel on the eliot log
(`num_matched` / `num_written`) because they answer different questions.

### Reference-genotype restoration (`restoration.py`)

A module may author a row whose genotype **is** the reference genotype — `lactose_tolerance` states
`G/G` for rs4988235 ("adult-type hypolactasia"), the most common lactose result there is. A
variant-only callset emits no record where the sample matches the reference, so that row could never
match and the reader was told "no variants found" instead of their result. **Whether such a row is
reachable is a property of the callset, not of the module** — a gVCF carries the reference block, an
array genotypes every probe, a variant-only VCF carries nothing — so the module cannot mark these
rows and the decision lives here. Corpus-wide it is not a rarity: 193 of longevitymap's 1039 rows,
and one row in three of every hand-curated module.

The design is `just-prs`'s (`just_prs.reference_allele`, `just_prs.prs.RestorationScope`, whose
docstring names just-dna-lite as the embedder that would inject its own position set). Three
properties are taken directly: restoration is **scoped to a supplied position set** (a module's
authored hom-ref sites, tiny — 2 for lactose, 193 rows for longevitymap), provenance is a
**tri-state carried on the row** (`genotype_evidence` ∈ `called` | `restored_hom_ref`), and a case
that cannot be established **stays unestablished** rather than being filled.

Where we deliberately diverge: `compute_prs` fills hom-ref for *every* absent locus with a known
reference allele and no locality gate — sound when one wrong locus among thousands moves a score by a
rounding error, not sound when one restored row becomes one rendered sentence about a person. So:

**There is no on/off config flag, deliberately.** Whether a hom-ref row can be inferred is a fact
about the callset, and the callset is in front of us — `RestorationContext.enabled` measures it and
nothing else decides. A default would only be a guess at what the two gates below already establish,
and a wrong guess either fabricates rows on an exome or withholds real results on a genome. The one
real parameter is `restoration_max_flank_bp`.

- **Only a `variant_only` callset is restored into**, classified by `infer_genotype_input_mode` (a
  re-derivation of just-prs's private `_infer_genotype_input_mode`: `<NON_REF>` allele or `RefCall`
  filter). **Classify the parquet, not the raw VCF** — our own `pass_filters` drops `FILTER=RefCall`,
  so a real gVCF arrives here already stripped of reference blocks and is variant-only *as far as
  annotation is concerned*; classifying the raw file would disable restoration and leave those rows
  unreportable from either direction.
- **Only a whole-genome callset is restored into** (`detect_callset_scope` → `CallsetScope`). This is
  the gate `GenotypeInputMode` cannot supply and the one that matters most: on an exome or panel the
  overwhelming majority of the genome was never captured, so absence carries no information — and the
  per-site flanking test is *actively misleading* there, because exonic calls cluster densely enough
  that an uncaptured intronic site kilobases away still has a neighbour. Two signals:
  `MIN_WGS_SITES` (1M; WGS carries 4.3–4.7M across every sample here, an exome ~50–100k) and
  `MIN_WGS_BREADTH` (0.75) — the share of the callset's span lying within one flank of a call, i.e.
  **the same question the per-site test asks, applied genome-wide**, so the two gates are one rule at
  two scales. Measured **0.942–0.950** on all four real samples against **0.21** for a clustered
  callset of comparable size. A gap percentile was tried first and **rejected**: 20 calls 50 bp apart
  every 100 kb puts 95% of gaps at 50 bp, so p90 reports it dense while 79% of the span is nowhere
  near a call. Breadth weights a gap by its length instead of counting it once.
- **A site the caller emitted is never restored.** It was observed; whatever it says there is the
  answer.
- **A site needs a called variant within `restoration_max_flank_bp` (default 10 kb)**, and the
  distance travels on `restored_flank_bp`. This is coarse and is *not* a callability proof — the
  rigorous test is `requires_callable` / `callable_from` (RM6) against a gVCF's `MIN_DP` with
  interval containment, and those are **unpopulated across the whole corpus**. Until they are, this
  is the strongest honest gate, which is why the evidence column exists and why the report renders
  restored rows with an `inferred` badge and an explicit "this can also mean the position was not
  covered" note. **Never merge the two categories.**
- `hom_ref_rows` returns `None` for a lead table with no `ref`/coordinates, so `pharm_variants` is
  excluded **by schema rather than by name** — format 0.6's RM43 fill switches it on with no code
  change here.

The restored frame is built by pouring module values into `vcf_lf.limit(0)` and `hstack`-ing, so it
carries the annotated schema by construction rather than by a hand-maintained copy that drifts the
first time the VCF reader gains a column. `restored_variants` / `total_variants_restored` on the
manifest are held apart from `total_variants_annotated` for the same reason the column is: these were
inferred, never observed. Tests: `tests/test_restoration.py` (which `load_env()`s at import — locally
registered modules are discovered from `JUST_DNA_PIPELINES_OUTPUT_DIR`).

**Read `just-dna-format/docs/PROPOSAL_0_6.md` before touching this seam again.** Its RM53–RM67 cluster
is a VCF-4.4 audit of exactly the assumptions a consumer makes, and three of its items were live
defects here (RM60, RM64) or corrected our reading of the contract (RM63 — the `variants.csv`
genotype docstring's "which homolog" claim is acknowledged overreach, being reworded to "phase
recorded but unaddressable"; do not build on it either way, since artifact self-consistency with
`_split_genotype` is the argument that actually decides how a consumer spells a genotype).

**The withholding directives are blocked on our own parquet, not merely unused.** `requires_callable`
/ `callable_from` and `quality_from` / `min_quality` are unpopulated on every module in the corpus, so
nothing is lost by not honouring them today — but do not implement them as a bare column lookup when
something does populate them. `user_vcf_normalized` flattens INFO and FORMAT into **one** namespace,
and `AF`, `DP`, `MQ` and `AD` all collide there; a bare pointer resolved against it reads a
well-formed number of the wrong kind without error (format RM53 — `AF` as INFO is a cohort frequency,
as FORMAT it is this person's fraction). Three prerequisites, all named upstream: keep the two
namespaces distinguishable in the parquet and accept the qualified `INFO/DP` / `FORMAT/DP` pointer
form (RM53); remember QUAL inverts on a reference record, which is exactly where a
`requires_callable` row is evaluated (RM57); and for a gVCF read `MIN_DP` with interval containment
rather than `DP` with an equality join on position (RM57's second half).

### The report's side of the contract (`report_logic.py` + `longevity_report.html.j2`)

The engine projects nothing, so all 37 columns of a 0.5 artifact reach the user's parquet; the report
is where they were being lost (it read ~14 and rendered 11). Four rules now hold it to the contract.

- **`annotations.parquet` is keyed per *annotation*, not per variant, so joining it on `rsid` fans a
  poly-effect variant out into one report row each** — measured coronary **81 → 231** (×2.85),
  lipidmetabolism ×2.73, vo2max ×2.15, inflating `total_variants` and every count derived from it.
  `_join_annotations` detects the key from the columns present (`_annotations_keying`) because three
  artifact generations are live at once: 0.3 on HuggingFace (rsid only), 0.5 as we compile today
  (`variant_key`, no genotype), 0.6 (`genotype`, per format **RM80**). Dedup-on-`variant_key` is used
  **only** in the 0.5 era, where the artifact offers no finer key — the RM80 reply rejects it as the
  general answer, since a genuine poly-effect variant is one locus with two real annotations.
- **`_effective_clin_sig` is the exact counterpart of `_effective_direction`** — authored column
  first, else `derive.clin_sig_from_booleans`. COMPILER.md: the fallback "lives in Python and does
  not travel with the parquet", so a polars-side consumer applies it itself. Prefer the column and
  never round-trip: the booleans cannot express `likely_pathogenic`, and reading them rendered
  **214,827 `likely_pathogenic` rows identically to 402,174 `pathogenic`** ones.
- **`_genotype_join_key` sorts an unphased genotype; the engine's `_normalize_lead_genotype` must
  not.** They look like the same operation and are opposites: this rebuilds the *authored* key the
  module wrote (COMPILER.md § Reverse — phased keeps order and joins on `|`, unphased sorts and joins
  on `/`), whereas the engine matches a sample's call against the artifact's own representation and
  sorting there would fold `A|G` and `G|A` into one key. Keep the two documented together, as with
  `_genotype_alleles`, which this is the inverse of.
- **Render-if-present, never a fixed field list.** `_AUTHORED_AXES` is carried into the view model
  and each axis gets an `{% if %}` row in the template macro, so a module that populates
  `effect_size` or `negatives` shows it the day it publishes. Most are empty across our whole corpus,
  but **that is a property of the corpus, not the format** — every module we hold is a Gen-I port
  authored against 0.2 and mechanically uplifted, and the compiler correctly never fills a cell an
  author left blank. A fixed field list is exactly how the template came to render 11 of 37;
  `test_a_populated_0_5_axis_reaches_the_html` fails the day one is dropped again, and its converse
  pins that an absent value emits no row rather than a blank one.

Two structural changes go with them. Report routing dispatches on **`lead_table`** (read from the
run's `manifest.json` through `AnnotationManifest`, whose default supplies `"weights"` for manifests
written before the engine knew about lead tables) instead of a hardcoded `== "longevitymap"`, so a
`pharm_variants`-led module gets a drug-keyed section ranked by ClinPGx evidence — the right shape
for a module whose every weight is `0.0`. And the report now credits its sources: discovery gained
`sources_url` / `ModuleTable.SOURCES`, and the footer lists distinct terms across the modules
rendered, **restricted to `layer == "annotation"`** (SCHEMAS.md § SourceRow — only that layer carries
the derivative-work obligation; Ensembl at layer `resolution` is recorded without tainting).
Permission booleans stay **tri-state**: `None` means the terms could not be established, which the
footer renders as "Not stated" and never as permission.

The two variant tables were near-duplicate copies that had already drifted; they are now one Jinja
macro (`variant_rows` / `variant_table_head`). Three constraints the inline JS imposes on it: the
detail row must be the **immediate next sibling** (no wrapper), `collapseExpandAll` picks expandable
rows by `children.length > 3` (so the summary row keeps >3 cells and the detail row stays a single
`colspan` cell), and that `colspan` must equal the header's `<th>` count.

### Building and releasing the modules

See **[docs/MODULE_RELEASE_0_5.md](docs/MODULE_RELEASE_0_5.md)** for the full runbook and
**[docs/V1_PARITY.md](docs/V1_PARITY.md)** for what each module is.

```bash
uv run pipelines v1-port port --all        # the six curated Gen-I ports (enrich → literature → compile)
uv run pipelines v1-port clinvar --all     # cardio / cancer / pathogenic, from the ClinVar snapshot
uv run pipelines v1-port pharmgkb          # drug response, from the ClinPGx clinical annotations
uv run python scripts/registry_precheck.py --namespace sandbox   # live pre-publish check
```

The pre-check posts the authored spec to the registry's `POST /api/v1/modules/{ns}/{name}/check` —
the full publish dry run, returning `would_publish`. **The token must own the namespace being
checked**; `REGISTRY_TOKEN` in `.env` currently owns `test-namespace`/`test-namespace2` and
`REGISTRY_TOKEN_SANDBOX` owns `sandbox`, not `just-dna-seq`, so rehearse under `--namespace sandbox`.

### `modules.yaml`: the working copy is *merged* over the defaults, never substituted

`_load_config()` layers `data/interim/modules.yaml` (or the `JUST_DNA_PIPELINES_OUTPUT_DIR`-derived
runtime copy) on top of the repo-root file, dict-merging `module_metadata` and unioning `sources`.
It used to be first-found-wins, which meant that once `register_custom_module` wrote a working copy
naming one custom module, **every built-in module silently lost its display metadata** — in the app
and in every spec a port wrote. Keep the merge; `save_config` patches only those two keys for the
same reason.

### Working agreement: propose shared changes via the format repo's docs (don't manage that repo)

When you find something that belongs in the shared schema/compiler (a bug, a missing field, a
tightening, a parity gap), **do not edit or commit the `just-dna-format` repo** — we consume it, we
don't own it. Just leave a note in its docs, which act as that repo's kanban intake; the format-repo
owners pick it up as needed:

- **`/data/sources/just-dna-format/docs/ROADMAP.md`** — backlog / proposed changes (kanban first
  column: "sticking a note", handled as needed).
- **`/data/sources/just-dna-format/docs/CHANGELOG.md`** — record cross-repo integration changes made
  on **our** (consumer) side, so parallel agents in the other repos aren't surprised.

Writing the note is the whole job on that side — do not follow it up with commits or PRs there.

---

## Immutable (Public Demo) Mode

See **[docs/IMMUTABLE_MODE.md](docs/IMMUTABLE_MODE.md)** for full documentation.

Immutable mode disables file uploads and serves only pre-configured public genomes from Zenodo. Controlled by the `JUST_DNA_IMMUTABLE_MODE=true` env var and `immutable_mode:` section in `modules.yaml`.

### Key files

| File | What it does |
|------|-------------|
| `modules.yaml` (`immutable_mode:` section) | Default samples, disclaimer, `allow_zenodo_import` flag |
| `module_config.py` (`ImmutableModeConfig`, `DefaultSample`) | Pydantic models, `is_immutable_mode()`, `get_immutable_config()` |
| `annotation/resources.py` | `validate_zenodo_record()`, `resolve_default_samples()` |
| `webui/state.py` | `is_immutable_mode` var, `handle_zenodo_import()`, guards on upload/delete |
| `webui/pages/annotate.py` | Conditional left panel (upload form vs disclaimer, Zenodo import, public genome hint) |
| `webui/components/layout.py` | "Public Demo" topbar badge, FAQ nav tab (always visible) |
| `webui/pages/faq.py` | FAQ page at `/faq` — loads content from `docs/FAQ.md` |
| `docs/FAQ.md` | FAQ content (markdown) — user, scientific, legal, technical questions |

### Deployment modes

| Mode | File Upload | Zenodo Import | Use Case |
|------|------------|---------------|----------|
| Normal (default) | Yes | Yes | Local/personal |
| Immutable + `allow_zenodo_import: true` | No | Yes | Workshop/conference |
| Immutable + `allow_zenodo_import: false` | No | No | Strict public demo |

### Important patterns

- **Never hardcode Zenodo URLs in Python** — use `get_immutable_config().default_samples`
- **Default samples should include `filename`** — startup resolves `data/input/users/public/` and the Zenodo cache before any network call; without `filename`, record URLs require a Zenodo metadata request.
- **`is_immutable_mode()`** checks env var first, then YAML `enabled` flag
- **`validate_zenodo_record()`** verifies open access, permissive license, and VCF presence before any download
- **Zenodo metadata is tracked in Dagster** — `source: "zenodo"`, `zenodo_url`, `zenodo_doi`, `zenodo_license`, `zenodo_creator` on `user_vcf_source` materialization
- **`progress_status`** state var provides phase-specific messages during downloads and normalization
- **In immutable mode, `safe_user_id` is always `"public"`** — all users share the same data directory

### Known public genomes

- **Anton Kulaga** (CC-Zero): `https://zenodo.org/records/18370498` — `antonkulaga.vcf` (482 MB)
- **Livia Zaharia** (CC-BY-4.0): `https://zenodo.org/records/19487816` — `SIMHIFQTILQ.hard-filtered.vcf.gz` (349 MB)

---

## VCF Quality Filtering

Quality filters are configured in `modules.yaml` under `quality_filters:` and applied during normalization (`user_vcf_normalized` asset). All downstream assets receive filtered data.

### Configuration (`modules.yaml`)

```yaml
quality_filters:
  pass_filters: ["PASS", "."]  # FILTER column values to keep (null to disable)
  min_depth: 10                 # Minimum DP (null/0 to disable)
  min_qual: 20                  # Minimum QUAL (null/0 to disable)
```

- **gVCF support**: Reference blocks (`FILTER=RefCall`, `GT=0/0`) are correctly dropped by `pass_filters` since `RefCall` is not in `["PASS", "."]`. This is intentional — ref blocks have no alt allele and would never match annotation module weights.
- **Backward compatible**: If `quality_filters` is absent from YAML, no filtering occurs (all fields default to `None`).

### Config Asset Pattern

A non-partitioned `quality_filters_config` asset materializes the current filter settings from `modules.yaml`. `user_vcf_normalized` depends on it.

**When `modules.yaml` changes:**
1. Re-materialize `quality_filters_config` (its `DataVersion` is a hash of the filter config)
2. Dagster marks `user_vcf_normalized` partitions as stale
3. Re-materialize stale partitions to apply new filters

### Key files

- **`modules.yaml`**: `quality_filters` section (single source of truth)
- **`module_config.py`**: `QualityFilters` model, `build_quality_filter_expr()` helper
- **`annotation/assets.py`**: `quality_filters_config` asset, filter application in `user_vcf_normalized`

### chrY Warning for Female Samples

When `sex="Female"` is set in `NormalizeVcfConfig`, the normalization asset logs a warning if chrY variants are found (e.g., `"WARNING: 1200 chrY variants found in female-labeled sample"`) but **never removes them**. This is informational only — QC filters (FILTER, depth, qual) handle the actual cleanup. We deliberately avoid sex-based chromosome filtering to prevent data loss for XXY, XYY, and other karyotype variations.

### Important patterns

- **Never bypass quality filters** — all VCF annotation paths should read from the normalized (and filtered) parquet, not raw VCF
- **Column name detection is case-tolerant** — `build_quality_filter_expr()` searches for `(filter, Filter, FILTER)`, `(DP, Dp, dp)`, `(qual, Qual, QUAL)` to handle different VCF parser conventions
- **Cast before comparison** — DP and QUAL columns are cast to numeric types before threshold comparison to handle string-typed parquet columns

---

## Dagster Pipeline

**For any Dagster-related changes, architecture, or troubleshooting, see [docs/DAGSTER_GUIDE.md](docs/DAGSTER_GUIDE.md).** The guide explains the full pipeline (VCF normalization → HF annotation + optional Ensembl → reports), output paths, jobs, and known quirks (e.g. polars-bio non-fatal Rust panic).

**Shared normalization**: Both HF module annotation and Ensembl annotation read from `user_vcf_normalized` (quality-filtered, chr-stripped parquet). Ensembl assets (`user_annotated_vcf`, `user_annotated_vcf_duckdb`) depend on `user_vcf_normalized` — they do NOT re-parse the raw VCF.

**Jobs:**
- `annotate_and_report_job`: normalize → HF modules → report (default)
- `annotate_all_job`: normalize → HF modules + Ensembl DuckDB → report (when Ensembl toggle is on in UI)
- `annotate_ensembl_only_job`: normalize → Ensembl DuckDB only (no HF modules, no report)
- `normalize_vcf_job`: normalize only (auto-runs on upload)

### Resource Tracking (MANDATORY)

**Always track CPU and RAM consumption** for all compute-heavy assets using `resource_tracker` from `just_dna_pipelines.runtime`:

```python
from just_dna_pipelines.runtime import resource_tracker

@asset
def my_asset(context: AssetExecutionContext) -> Output[Path]:
    with resource_tracker("my_asset", context=context):
        # ... compute-heavy code ...
        pass
```

**Important:** Always pass `context=context` to enable Dagster UI charts. Without it, metrics only go to Eliot logs.
This automatically logs to Dagster UI: `duration_sec`, `cpu_percent`, `peak_memory_mb`, `memory_delta_mb`.

### Run-Level Resource Summaries (MANDATORY)

All jobs must include the `resource_summary_hook` from `just_dna_pipelines.annotation.utils` to provide aggregated resource metrics at the run level:

```python
from just_dna_pipelines.annotation.utils import resource_summary_hook

my_job = define_asset_job(
    name="my_job",
    selection=AssetSelection.assets(...),
    hooks={resource_summary_hook},  # Note: must be a set, not a list
)
```

This hook logs a summary at the end of each successful run: Total Duration, Max Peak Memory, and Top memory consumers.

### Dagster Version Notes (1.13.x)

**API differences from newer versions (MANDATORY reference):**
- `get_dagster_context()` does NOT exist - you must pass `context` explicitly.
- `context.log.info()` does NOT accept a `metadata` keyword argument - use `context.add_output_metadata()` separately.
- `EventRecordsFilter` does NOT have `run_ids` parameter - use `instance.all_logs(run_id, of_type=...)` instead.
- For asset materializations, use `EventLogEntry.asset_materialization` (returns `Optional[AssetMaterialization]`), not `DagsterEvent.asset_materialization`.
- `hooks` parameter in `define_asset_job` must be a `set`, not a list: `hooks={my_hook}`.
- Use `defs.resolve_all_asset_specs()` instead of deprecated `defs.get_all_asset_specs()`.

### Project-Specific Patterns

- **Auto-configuration**: Dagster config is automatically created on first run. See **[docs/CLEAN_SETUP.md](docs/CLEAN_SETUP.md)**.
- **Declarative Assets**: We prioritize Software-Defined Assets (SDA) over imperative ops.
- **IO Managers**: Reference assets (Ensembl, ClinVar, etc.) use `annotation_cache_io_manager` → stored in `~/.cache/just-dna-pipelines/`.
- **User assets** use `user_asset_io_manager` → stored in `data/output/users/{user_name}/`.
- **Ensembl cache layout**: Flat chromosome parquets at `~/.cache/just-dna-pipelines/ensembl_variations/data/homo_sapiens-chr*.parquet`. Downloaded via fsspec (`HfFileSystem`). The repo is configured in `modules.yaml` under `ensembl_source:`. DuckDB creates a single `ensembl_variations` VIEW over all files.
- **Lazy materialization**: Assets check if cache exists before downloading.
- **Start UI**: `uv run start` (full stack) or `uv run dagster` (pipelines only).

### Asset Return Types

| Asset Returns | IO Manager | Use Case |
|---------------|------------|----------|
| `pl.LazyFrame` | `polars_parquet_io_manager` | Small parquet, schema visibility |
| `Path` | Custom IO manager | Large data, DuckDB joins, file uploads |
| `dict` | Default | API responses, upload results |

### Key Rules

- **dagster-polars**: Use `PolarsParquetIOManager` for `LazyFrame` assets → automatic schema/row count in UI
- **Path assets**: Add `"dagster/column_schema": polars_schema_to_table_schema(path)` for schema visibility
- **Asset checks**: Use `@asset_check` for validation; include via `AssetSelection.checks_for_assets(...)`
- **Streaming**: Use `lazy_frame.sink_parquet()`, never `.collect().write_parquet()` on large data
- **DuckDB**: Use for large joins (out-of-core); set `memory_limit` and `temp_directory`
- **Concurrency**: Use `op_tags={"dagster/concurrency_key": "name"}` to limit parallel execution

### Dynamic Partitions Pattern

1. Create partition def: `PARTS = DynamicPartitionsDefinition(name="files")`
2. Discovery asset registers partitions: `context.instance.add_dynamic_partitions(PARTS.name, keys)`
3. Partitioned assets use: `partitions_def=PARTS`, access `context.partition_key`
4. Collector depends on partitioned output via `deps=[partitioned_asset]`, scans filesystem for results

### Execution

- **Python API only**: `defs.resolve_job_def(name)` + `job.execute_in_process(instance=instance)`
- **Same DAGSTER_HOME** for UI and execution: `dg dev -m module.definitions`
- **All assets in `Definitions(assets=[...])`** for lineage visibility in UI

### API Gotchas

**Never use `huggingface_hub.snapshot_download` for large datasets:**

`snapshot_download` duplicates data into HuggingFace's own blob store (`~/.cache/huggingface/`) and then copies/links to `local_dir`. This wastes disk space and is unreliable. Instead, use **fsspec** via `HfFileSystem` for direct file-by-file downloads into our cache:

```python
# WRONG - duplicates data in HF blob store, unreliable local_dir population
from huggingface_hub import snapshot_download
snapshot_download(repo_id="org/repo", local_dir=cache_dir, ...)

# CORRECT - direct download via fsspec, files land exactly where we want
from huggingface_hub import HfFileSystem, get_token
fs = HfFileSystem(token=get_token())
for remote_path in fs.ls("datasets/org/repo/data", detail=False):
    if remote_path.endswith(".parquet"):
        fs.get(remote_path, str(local_path))
```

This pattern is also future-proof: swapping `HfFileSystem` for any other fsspec backend (S3, GCS, HTTP) requires minimal changes.

**polars-bio `scan_vcf` API changed (0.23+):**

- `IOOperations.scan_vcf()` no longer accepts `thread_num`.
- Use `concurrent_fetches` instead.
- In `just_dna_pipelines.io.read_vcf_file()`, keep `thread_num` only as backward-compatible API and map it to `concurrent_fetches`.

**polars-bio `write_vcf` with custom INFO fields requires `set_source_metadata`:**

Without `pb.set_source_metadata()`, extra columns on the DataFrame are silently dropped and the VCF always outputs `INFO=.`. Register INFO field definitions **before** calling `pb.write_vcf()`:

```python
import polars_bio as pb

pb.set_source_metadata(df, format="vcf", header={
    "info_fields": {
        "AF": {"number": "A", "type": "Float", "description": "Allele Frequency"},
        "gene": {"number": "1", "type": "String", "description": "Gene symbol"},
    }
})
pb.write_vcf(df, str(out_vcf))
```

Each `info_fields` entry requires `number`, `type`, and `description`. `type` is one of `Integer`, `Float`, `String`, `Flag`, `Character`; `number` is `1`, `A`, `R`, `G`, or `.`. See https://biodatageeks.org/polars-bio/features/#setting-custom-metadata.

`write_vcf` also requires all 8 core VCF columns (`chrom`, `start`, `end`, `id`, `ref`, `alt`, `qual`, `filter`) with `start`/`end` as `UInt32`. When exporting from parquets that lack some of these, fill defaults: `end = start + 1`, `qual = None`, `filter = "."`.

**Timestamps are on `RunRecord`, not `DagsterRun`:**

```python
# WRONG - DagsterRun has no start_time/end_time
runs = instance.get_runs(limit=10)
for run in runs:
    print(run.start_time)  # AttributeError!

# CORRECT - Use get_run_records() to access timestamps
records = instance.get_run_records(limit=10)
for record in records:
    run = record.dagster_run
    # record.start_time and record.end_time are Unix timestamps (floats)
    # record.create_timestamp is a datetime object
    started = datetime.fromtimestamp(record.start_time) if record.start_time else None
```

**Partition keys via tags, not direct parameter:**

```python
# WRONG - create_run_for_job doesn't accept partition_key
run = instance.create_run_for_job(job_def=job, partition_key=pk)

# CORRECT - pass partition via tags
run = instance.create_run_for_job(
    job_def=job,
    run_config=config,
    tags={"dagster/partition": pk},
)
```

**Web UI Job Execution Pattern (TRY-DAEMON-WITH-FALLBACK):**

For the Reflex Web UI, we use a hybrid approach: try daemon-based execution first, but fall back to `execute_in_process` if submission fails. **Critical: Keep business logic outside exception handlers.**

```python
# RECOMMENDED PATTERN - Separate business logic from exception handling

# 1. Create run
job_def = defs.resolve_job_def(job_name)
run = instance.create_run_for_job(
    job_def=job_def,
    run_config=run_config,
    tags={"dagster/partition": partition_key},
)
run_id = run.run_id

# 2. Try daemon submission (register failure, don't process it)
daemon_success, daemon_error = self._try_submit_to_daemon(instance, run_id)

# 3. Handle success/failure outside exception handler
if daemon_success:
    # Poll status asynchronously via poll_run_status()
    yield rx.toast.info("Job started")
else:
    # Fall back to execute_in_process as background task (non-blocking)
    self._add_log(f"Daemon failed: {daemon_error}")
    yield rx.toast.info("Running in-process - please wait...")
    
    # Launch in thread pool without awaiting (keeps UI responsive)
    # CRITICAL: Use run_in_executor, NOT asyncio.create_task or asyncio.to_thread
    # Those cause pyo3 panics with Dagster objects
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        None,  # Use default executor
        self._execute_inproc_with_state_update,
        instance, job_name, run_config, partition_key, run_id, sample_name
    )
    # Background task will update state when complete

# Helper methods (separate concerns):
def _try_submit_to_daemon(self, instance, run_id) -> tuple[bool, str]:
    """Try daemon submission. Returns (success, error_message)."""
    try:
        instance.submit_run(run_id, workspace=None)
        return (True, "")
    except Exception as e:
        return (False, str(e))

def _execute_inproc_with_state_update(self, ...) -> None:
    """Execute in-process and update state. Called from thread pool via run_in_executor."""
    try:
        # Execute synchronously (caller handles threading via run_in_executor)
        result = self._execute_job_in_process(...)
        # Update UI state with result (self.running = False, etc.)
        self.running = False
        self.last_run_success = result.success
    except Exception as e:
        # Update UI state for failure
        self.running = False
        self.last_run_success = False
```

**Why this pattern is better:**
- ✅ Business logic outside exception handlers (cleaner separation of concerns)
- ✅ Exception handlers only register failures, don't process them
- ✅ Control flow is linear and easy to follow
- ✅ Each method has single responsibility
- ✅ **UI stays responsive** - Background task doesn't block event handler

**Critical: UI Responsiveness and Python/Rust Thread Safety**

NEVER await long-running operations in Reflex event handlers - it blocks the entire UI. Also, be careful with threading when using Dagster (which has Rust/pyo3 internals):

```python
# BAD - Blocks UI until job completes (minutes!)
fallback_result = await self._execute_inproc_with_state_update(...)
if fallback_result["success"]:
    yield rx.toast.success("Done")

# BAD - asyncio.to_thread() with Dagster objects causes pyo3 panic:
# "Cannot drop pointer into Python heap without the thread being attached"
result = await asyncio.to_thread(self._execute_job_in_process, ...)

# BAD - asyncio.create_task() on sync function
asyncio.create_task(self._execute_inproc_with_state_update(...))  # Not async!

# GOOD - Use run_in_executor for thread-safe background execution
loop = asyncio.get_event_loop()
loop.run_in_executor(None, self._execute_inproc_with_state_update, ...)
# UI remains responsive, thread-safe, no pyo3 panics
```

**Why run_in_executor works:** It properly manages the Python GIL when moving objects between threads, unlike `asyncio.to_thread()` which can cause pyo3 (Python/Rust bridge) panics with Dagster objects.

**Why `submit_run(workspace=None)` fails in web UIs:**

Daemon-based execution requires `ExternalPipelineOrigin` which needs workspace context. Web UI state doesn't have easy access to workspace context, so `submit_run(run_id, workspace=None)` fails with "Expected non-None value: External pipeline origin must be set for submitted runs". The fallback to `execute_in_process` handles this reliably.

**Critical: Per-file running state (not global)**

Button enable logic must check if the **selected file** is running, not if **any** job is running globally. This allows concurrent jobs on different files:

```python
# BAD - blocks ALL files when ANY file is running
@rx.var
def can_run_annotation(self) -> bool:
 return bool(self.selected_file) and len(self.selected_modules) > 0 and not self.running

# GOOD - only blocks the selected file if it's running
@rx.var
def can_run_annotation(self) -> bool:
 if not self.selected_file or not self.selected_modules:
 return False
 
 # Check if SELECTED file has a running job
 for run in self.runs:
 if run.get("filename") == self.selected_file:
 if run.get("status") in ("RUNNING", "QUEUED", "STARTING"):
 return False
 
 return True

# Helper computed var for UI elements
@rx.var
def selected_file_is_running(self) -> bool:
 """Check if the currently selected file has a running job."""
 if not self.selected_file:
 return False
 for run in self.runs:
 if run.get("filename") == self.selected_file:
 if run.get("status") in ("RUNNING", "QUEUED", "STARTING"):
 return True
 return False
```

Use `selected_file_is_running` for UI elements (button text, icons, spinners) instead of global `self.running` flag.

**Critical: Orphaned Run Cleanup (execute_in_process survival)**

When using `execute_in_process` in web UIs, runs are abandoned (stuck in STARTED status) on server restart. Implement these safeguards:

1. **Startup cleanup** - Clean up NOT_STARTED runs (daemon submission failures):

```python
def _cleanup_orphaned_runs(self) -> int:
 """Clean up NOT_STARTED runs on startup (daemon submission failures)."""
 instance = get_dagster_instance()
 not_started_records = instance.get_run_records(
 filters=RunsFilter(statuses=[DagsterRunStatus.NOT_STARTED]),
 limit=100,
 )
 cleaned_count = 0
 for record in not_started_records:
 run = record.dagster_run
 instance.report_run_canceled(run, message="Orphaned run from daemon submission failure")
 cleaned_count += 1
 return cleaned_count

async def on_load(self):
 """Load state and clean up orphaned runs."""
 cleaned = self._cleanup_orphaned_runs()
 if cleaned > 0:
 self._add_log(f"🧹 Cleaned up {cleaned} orphaned run(s) from previous session")
 # ... rest of on_load logic
```

2. **Track active in-process runs** - Use class variable to track which runs are executing in-process:

```python
class MyState(rx.State):
 # Class variable shared across all instances
 _active_inproc_runs: Dict[str, str] = {} # {run_id: partition_key}
 
 def _execute_inproc_with_state_update(self, ...):
 actual_run_id = None
 try:
 result = self._execute_job_in_process(...)
 actual_run_id = result.run_id
 # Track this run
 MyState._active_inproc_runs[actual_run_id] = partition_key
 # ... process result
 finally:
 # Clean up tracker
 if actual_run_id and actual_run_id in MyState._active_inproc_runs:
 del MyState._active_inproc_runs[actual_run_id]
```

3. **SIGTERM handler** - Mark STARTED runs as CANCELED on shutdown (in app.py):

```python
import signal
import atexit

def cleanup_active_runs():
 """Mark all active in-process runs as CANCELED on shutdown."""
 try:
 from my_app.state import MyState
 from dagster import DagsterInstance
 
 active_runs = MyState._active_inproc_runs.copy()
 if not active_runs:
 return
 
 instance = DagsterInstance.get()
 for run_id in active_runs:
 run = instance.get_run_by_id(run_id)
 if run:
 instance.report_run_canceled(
 run,
 message="Web server shutdown - in-process execution terminated"
 )
 except Exception as e:
 print(f"Warning: Failed to cleanup active runs: {e}")

# Register cleanup handlers
signal.signal(signal.SIGTERM, lambda sig, frame: (cleanup_active_runs(), sys.exit(0)))
signal.signal(signal.SIGINT, lambda sig, frame: (cleanup_active_runs(), sys.exit(0)))
atexit.register(cleanup_active_runs)
```

4. **CLI cleanup command** - Manual cleanup for orphaned runs:

```bash
# Clean up NOT_STARTED runs (daemon failures)
uv run pipelines cleanup-runs

# Clean up STARTED runs (abandoned in-process executions)
uv run pipelines cleanup-runs --status STARTED

# Dry-run to see what would be cleaned
uv run pipelines cleanup-runs --status STARTED --dry-run
```

**For CLI Tools: Direct `execute_in_process`**

CLI tools can use `execute_in_process` directly (no fallback needed):

```python
# For CLI tools - execute_in_process (no daemon required, runs synchronously)
job_def = defs.resolve_job_def(job_name)

# Ensure partition exists (for dynamic partitions)
existing = instance.get_dynamic_partitions(partition_def.name)
if partition_key not in existing:
    instance.add_dynamic_partitions(partition_def.name, [partition_key])

result = job_def.execute_in_process(
    run_config=run_config,
    instance=instance,
    tags={"dagster/partition": partition_key},
)
if result.success:
    print("Job completed successfully")
else:
    print(f"Job failed: {result.all_events}")
```

**Trade-offs of try-daemon-with-fallback pattern:**

✅ **Benefits:**
- UI responsive when daemon works (job runs in daemon, not blocking web server)
- Reliable when daemon fails (falls back to execute_in_process)
- Background threading keeps execute_in_process from blocking UI

❌ **Limitations:**
- Runs created via execute_in_process fallback cannot be re-executed from Dagster UI (missing `remote_job_origin`)
- Execute_in_process runs in web server process (mitigated by background threading via `asyncio.to_thread`)

**Asset job config uses "ops" key, not "assets":**

```python
# WRONG - "assets" key causes DagsterInvalidConfigError
run_config = {
    "assets": {"user_hf_module_annotations": {"config": {...}}}
}

# CORRECT - use "ops" key for asset job config
run_config = {
    "ops": {"user_hf_module_annotations": {"config": {...}}}
}
```

**Run logs via `all_logs`, not `EventRecordsFilter`:**

```python
# WRONG - EventRecordsFilter doesn't have run_ids
records = instance.get_event_records(EventRecordsFilter(run_ids=[run_id]))

# CORRECT - use all_logs(run_id)
events = instance.all_logs(run_id)
```

**`submit_run()` with workspace context - use try/fallback pattern:**

```python
# Web UI pattern: Try daemon submission, fall back to execute_in_process
try:
    instance.submit_run(run_id, workspace=None)
    # Success: daemon will run the job, poll status via poll_run_status()
except Exception as e:
    # Daemon rejected run (needs ExternalPipelineOrigin/workspace context)
    # Fall back to execute_in_process which runs reliably without workspace context
    result = await asyncio.to_thread(
        self._execute_job_in_process,
        instance, job_name, run_config, partition_key
    )
    # Update UI state with result immediately (no polling needed)
```

**Critical discovery:** Wrong parameter `workspace_process_context=None` caused TypeError → triggered fallback → job ran successfully via `execute_in_process`. The "correct" `workspace=None` is worse because it doesn't error immediately - daemon accepts submission but then rejects run with "External pipeline origin must be set", leaving run stuck in NOT_STARTED.

### Anti-Patterns

- `dagster job execute` CLI (deprecated)
- Hardcoded asset names; use `defs.get_all_asset_specs()`
- **Silent fallbacks when primary data is missing** — If normalized parquet does not exist (e.g. user_vcf_normalized), do NOT silently fall back to raw VCF and display it as if it were normalized. Users will not know the data source differs. Either show an explicit error ("Run normalization first") or a very prominent banner ("Using raw VCF — normalize job has not run"). See [docs/DAGSTER_GUIDE.md](docs/DAGSTER_GUIDE.md) § VCF Normalization.
- **Ensembl assets bypassing user_vcf_normalized** — `user_annotated_vcf` and `user_annotated_vcf_duckdb` MUST depend on `user_vcf_normalized` and pass the normalized parquet via `normalized_parquet=` parameter. Never read the raw VCF directly in annotation assets.
- Config for unselected assets (validation errors)
- Suspended jobs holding DuckDB file locks
- **Accessing `run.start_time` on DagsterRun** - use RunRecord instead
- **Using `submit_run(run_id, workspace=None)` without fallback in web UIs** - daemon rejects run, leaves it stuck in NOT_STARTED; always implement fallback to `execute_in_process`
- **Using global `self.running` flag for button enable logic** - blocks ALL files when ANY file is running; use per-file running state instead
- **Expecting Dagster UI re-execution to work for `execute_in_process` runs** - not supported, but acceptable trade-off

---

## Test Generation Guidelines

- **Real data + ground truth**: Use actual source data, auto-download if needed, and compute expected values at runtime.
- **Deterministic coverage**: Use fixed seeds or explicit filters; include representative and edge cases.
- **Meaningful assertions**: Prefer relationships and aggregates over existence-only checks.
- **Verbosity**: Run `pytest -vvv`.
- **Docs**: Put all new markdown files (except README/AGENTS) in `docs/`.

### What to Validate

- **Counts & aggregates**: Row counts, sums/min/max/means, distinct counts, and distributions.
- **Joins**: Pre/post counts, key coverage, cardinality expectations, nulls introduced by outer joins, and a few spot-checks.
- **Transformations**: Round-trip survival, subset/superset semantics, value mapping, key preservation.
- **Data quality**: Format/range checks, outliers, malformed entries, duplicates, referential integrity.

### Avoiding LLM "Reward Hacking" in Tests

- **Runtime ground truth**: Query source data at test time instead of hardcoding expectations.
- **Seeded sampling**: Validate random records with a fixed seed, not just known examples.
- **Negative & boundary tests**: Ensure invalid inputs fail; probe min/max, empty, unicode.
- **Derived assertions**: Test relationships (e.g., input vs output counts), not magic numbers.
- **Allow expected failures**: Use `pytest.mark.xfail` for known data quality issues with a clear reason.

### Test Structure Best Practices

- **Parameterize over duplicate**: If testing the same logic on multiple outputs, use `@pytest.mark.parametrize` instead of copy-pasting tests.
- **Set equality over counts**: Prefer `assert set_a == set_b` over `assert len(set_a) == 270` - set comparison catches both missing and extra values.
- **Delete redundant tests**: If test A (e.g., set equality) fully covers test B (e.g., count check), keep only test A.
- **Domain constants are OK**: Hardcoding expected enum values or well-known constants from specs is fine; hardcoding row counts or unique counts derived from data inspection is not.

### Verifying Bug-Catching Claims

When claiming a test "would have caught" a bug, **demonstrate it**:

1. **Isolate the buggy logic** in a test or script
2. **Run it and show failure** against correct expectations
3. **Then show the fix passes** the same test

Never claim "tests would have caught this" without running the buggy code against the test.

### Anti-Patterns to Avoid

- Testing only "happy path" with trivial data
- Hardcoding expected values that drift from source (use derived ground truth)
- Mocking data transformations instead of running real pipelines
- Ignoring edge cases (nulls, empty strings, boundary values, unicode, malformed data)
- **Claiming tests "would catch bugs" without demonstrating failure on buggy code**

**Meaningless Tests to Avoid** (common AI-generated anti-patterns):

```python
# BAD: Existence-only checks as the sole validation
assert "name" in df.columns
assert len(df) > 0

# BAD: Hardcoded counts derived from data inspection
assert len(source_ids) == 270  # will break when source changes

# BAD: Redundant with set equality test
assert len(output_cats) == 12  # already covered by subset check

# ACCEPTABLE: Required columns as prerequisites
required_cols = {"id", "name", "value"}
assert required_cols.issubset(df.columns)

# GOOD: Set equality from source data
source_ids = set(source_df["id"].unique().drop_nulls().to_list())
output_ids = set(output_df["id"].unique().drop_nulls().to_list())
assert source_ids == output_ids

# GOOD: Domain knowledge constants (from spec, not data inspection)
assert valid_states == {"active", "inactive", "pending"}  # from API spec
```

---

## Process Model & Fork Safety (MANDATORY)

**Never `fork()` a process that has already used Polars, polars-bio, or DuckDB.**

Polars' Rayon pool is created on the **first Polars operation**, not at import. A
forked child inherits the pool's latches but none of its worker threads, so the first
parallel op parks forever. It parks with the GIL released, so Python signal handlers
never run: no traceback, SIGTERM ignored, SIGKILL only. Rayon workers are named
`polars-<n>` in `/proc/self/task/*/comm` and are invisible to Python's `threading`
module, which is why this ships unnoticed. CPython's own
`DeprecationWarning: ... fork() may lead to deadlocks` is swallowed by the default
`ignore::DeprecationWarning` filter because the fork happens outside `__main__`.

Full write-up and reproductions: **[docs/GRANIAN_POLARS_FORK_DEADLOCK.md](docs/GRANIAN_POLARS_FORK_DEADLOCK.md)**.

### Rules

- **`serve()` calls `apply_process_model_guards()` from `webui/src/webui/forksafety.py`
  before importing reflex.** It pins `REFLEX_USE_GRANIAN` (Reflex's `should_use_granian()`
  is a `find_spec` heuristic that otherwise silently selects `gunicorn --preload`,
  which forks after importing the app), forces the `spawn` start method, unmutes the
  fork warning, and installs an `os.register_at_fork` tripwire. Do not remove or reorder.
- **Any `multiprocessing` use must pass a `spawn` context explicitly** —
  `mp_context=multiprocessing.get_context("spawn")`. Never rely on the platform default.
- **Spawned children re-import `__main__`,** so every entry point must be
  `__main__`-guarded or the worker dies with the `freeze_support()` RuntimeError.
  uv-generated console scripts already are; bare scripts are not.
- **`POLARS_MAX_THREADS=1` does not fix this.** Measured at 1, 4 and 16 threads, a forked
  child hangs every time — even one Rayon worker is lost to the fork. It is the intuitive
  mitigation and it is ineffective, while costing all Polars parallelism. Use spawn.
- **`run_in_executor(None, ...)` does NOT make native-parallel work safe.** It moves the
  Python frame to another thread; Rayon/Tokio/DuckDB pools are process-global. Use it for
  blocking I/O only, never as the answer to a native deadlock or to CPU-heavy Polars work.
- **All Polars / DuckDB / polars-bio / Dagster work goes through `webui.compute`** —
  `compute.pool` for short queries, `compute.jobs` for Dagster runs. The ASGI process
  marshals arguments and results and nothing else.
- **Grid pages must be O(page), not O(rows).** `lf.sort(...).slice(offset, n)` re-sorts the
  whole frame on every click (Polars only pushes a dynamic predicate down for single-key
  sorts; multi-key sorts fully materialize). Sort once to a temp parquet, then slice pages
  off that artifact.

### Ctrl+C: importing Polars takes SIGINT away, with `SA_RESTART`

**A blocking `proc.wait()` is not interruptible in any process that imported Polars.**
Polars installs its own SIGINT handler through `sigaction` with `SA_RESTART` set, so the
kernel *restarts* the interrupted `waitpid` instead of returning `EINTR`. CPython never
reaches the bytecode loop where Python-level handlers run, so `KeyboardInterrupt` is not
raised until the child exits by itself. Measured: a bare interpreter blocked in
`Popen.wait()` is interrupted at once; the same code after `import polars` ignores every
SIGINT. This is why `uv run start` sat through a dozen Ctrl+C presses with the whole stack
still up — and because every child is started with `start_new_session=True`, the terminal's
SIGINT does not reach them either. The launcher is the only process that can act on it.

- **`install_launcher_signal_handlers` (in `just_dna_lite.process`) is what makes the wait
  interruptible again**, and not only because it routes first/second signals: CPython's
  `signal.signal()` registers with `sa_flags = 0`, which clears `SA_RESTART`. Call it
  **before** blocking on any child — `start_all` inline, `start_dagster` through
  `_run_managed_foreground`. A launcher that goes back to a bare `proc.wait()` without it is
  silently uninterruptible again, with no symptom other than Ctrl+C doing nothing.
- **The first signal raises `KeyboardInterrupt` into the main flow; the second force-kills**
  the snapshotted tree and exits. SIGTERM and Ctrl+Z enter the same path, so `kill
  <launcher>` tears the stack down instead of orphaning it.
- Regression tests: `tests/test_launcher_shutdown.py` pins the SA_RESTART mechanism, an
  unclaimed wait sleeping through Ctrl+C, and the claimed wait breaking within a tick.
  `tests/test_process_shutdown.py` covers what shutdown does once it starts.

---

## Reflex UI Framework

The webui uses **Reflex** (Python-based React framework). See **[docs/DESIGN.md](docs/DESIGN.md)** for visual design.

### UI Change Verification Workflow (MANDATORY)

When making significant UI changes, follow this workflow:

1. **Make changes** to UI code (state.py, annotate.py, layout.py, etc.)
2. **Check terminal for compile errors**: Run `uv run start` and monitor the terminal output for:
   - `ImportError` - Missing or renamed imports
   - `AttributeError` - Wrong API usage (e.g., `App.api_route` doesn't exist)
   - `Warning: Invalid icon tag` - Wrong icon names (use hyphenated Lucide names)
   - Traceback errors during "Compiling" phase
3. **Verify app starts successfully**: Look for "App running at: http://localhost:3000"
4. **Check browser**: Navigate to http://localhost:3000 and verify:
   - Page loads without blank screen
   - Key UI elements are visible (tabs, buttons, panels)
   - Interactive elements work (tab switching, file selection, etc.)
5. **Fix any issues** before considering the task complete

**Common compile-time errors:**
- `ModuleNotFoundError` - Add missing dependency with `uv add <package>`
- `ImportError: cannot import name 'X'` - Function was renamed/removed, update imports
- `AttributeError: 'App' object has no attribute 'Y'` - Wrong Reflex API, check docs

**Terminal monitoring tip**: Reflex hot-reloads on file changes. After editing, wait for "Compiling: 100%" message before checking the browser.

**Note on worker warnings**: During hot reload, Reflex may show `[WARNING] Killing worker-0 after it refused to gracefully stop`. This is normal behavior when the worker is busy processing a request during reload. It does not indicate a Dagster issue or data corruption.

### Critical Reflex Patterns

**0. Use `@rx.event(background=True)` for heavy computation, NEVER synchronous generators:**

Reflex generator event handlers (`yield`) hold the state lock for their **entire** execution. `yield` sends state deltas but does NOT release the lock — other events queue up and fire all at once when the generator finishes, making the UI completely unresponsive. This applies to both direct generators and `yield from` delegation to mixin generators.

For any operation taking more than ~1 second (PRS computation, file processing, API calls), use `@rx.event(background=True)` with `async with self:` for state access:

```python
# BAD — holds state lock for entire loop, UI frozen during computation
def compute_heavy_stuff(self) -> Any:
    self.computing = True
    yield  # sends update but does NOT release lock
    for item in self.items:
        result = expensive_function(item)  # blocks everything
        self.progress += 1
        yield  # UI appears frozen, events queue up
    self.computing = False

# GOOD — state lock released between iterations, UI stays responsive
@rx.event(background=True)
async def compute_heavy_stuff(self) -> None:
    async with self:  # brief lock: read inputs, set computing=True
        items = list(self.items)
        self.computing = True

    for i, item in enumerate(items):
        async with self:  # brief lock: progress update
            self.progress = i

        # Heavy work runs WITHOUT state lock — UI responsive
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, expensive_function, item)

    async with self:  # brief lock: store results
        self.computing = False
        self.results = results
```

Key rules:
- `@rx.background` does NOT exist in Reflex 0.8.x — always use `@rx.event(background=True)`
- Extract heavy work into pure functions (no `self` access) and run via `run_in_executor`
- Snapshot all needed state vars into locals inside the first `async with self:` block
- Keep `async with self:` blocks as brief as possible (only read/write state)

**1. Use `fomantic_icon()` instead of `rx.icon()`:**

Lucide icons (via `rx.icon()`) often fail to load or trigger terminal warnings in this environment. Use the `fomantic_icon()` helper from `webui.components.layout` instead. It maps common Lucide names to Fomantic UI equivalents.

```python
from webui.components.layout import fomantic_icon

# GOOD - consistent and reliable
fomantic_icon("dna", size=24, color="#2185d0")

# BAD - triggers "Invalid icon tag" warnings
fomantic_icon("dna", size=24)
```

**2. Icons require STATIC strings:**

Even with `fomantic_icon()`, you cannot pass a dynamic `rx.Var` as the name. Use `rx.match` for dynamic selection.

```python
# CRASHES
fomantic_icon(module["icon_name"], size=24)

# WORKS
rx.match(
    module["name"],
    ("heart", fomantic_icon("heart", size=24)),
    ("star", fomantic_icon("star", size=24)),
    fomantic_icon("database", size=24),  # default
)
```

**3. Icon naming:**

`fomantic_icon()` handles mapping for common names, but generally use Fomantic UI icon names (space-separated) or common hyphenated names which the helper will map.

Verified icons (mapped by helper): `circle-check`, `circle-x`, `circle-alert`, `circle-play`, `cloud-upload`, `upload`, `download`, `file-text`, `files`, `dna`, `heart`, `heart-pulse`, `activity`, `zap`, `droplets`, `pill`, `loader-circle`, `refresh-cw`, `external-link`, `terminal`, `database`, `boxes`, `inbox`, `history`, `chart-bar`, `play`.

**4. Use `rx.cond()` for reactive styling:**

```python
# GOOD - reactive
class_name=rx.cond(is_active, "ui primary button", "ui button")

# BAD - not reactive, evaluated once at compile time
class_name="ui primary button" if is_active else "ui button"
```

**4. rx.foreach with dictionaries:**

Values from dicts in `rx.foreach` are typed as `Any`. This can cause type errors in components that expect specific types (e.g. `rx.checkbox` expecting `bool`). Cast when needed using `.to()`:

```python
# Cast to int for text/formatting
rx.text(item["count"].to(int))

# Cast to bool for control props
rx.checkbox(checked=item["is_checked"].to(bool))
```

**5. Use `class_name` not `class`:**

Reflex uses `class_name` for CSS classes. Using `class` will cause a Python `SyntaxError` as it is a reserved keyword.

```python
# GOOD
rx.box(class_name="ui segment")

# BAD - SyntaxError
rx.box(class="ui segment")
```

### Reflex Anti-Patterns

- **Dynamic icon names** - Will crash with "Icon name must be a string"
- **Underscore icon names** - Use hyphens: `heart-pulse` not `heart_pulse`
- **Wrong icon order** - It's `circle-check` not `check-circle`
- **Python conditionals for state** - Use `rx.cond()` instead
- **Missing `.to()` casts in foreach** - Can cause type errors
- **Awaiting long-running tasks in event handlers** - Blocks entire UI. Submit to `webui.compute`; `loop.run_in_executor()` is for blocking I/O only
- **Treating `run_in_executor(None, ...)` as making native work safe** - It moves the Python frame to another thread, but Rayon/Tokio/DuckDB pools are process-global. It neither prevents a fork deadlock nor bounds memory. See Process Model & Fork Safety
- **Using `asyncio.to_thread()` with Dagster objects** - Causes pyo3 panic "Cannot drop pointer into Python heap". Dagster runs belong in `webui.compute.jobs` (a spawned child), not in any thread of the ASGI process
- **Forking after Polars/polars-bio/DuckDB has been used** - Silent, unkillable deadlock on the next parallel op. See Process Model & Fork Safety
- **Blocking in `proc.wait()` without claiming SIGINT first** - `import polars` installs an SA_RESTART SIGINT handler, so the wait is restarted instead of interrupted and Ctrl+C does nothing at all. Call `install_launcher_signal_handlers` before the wait. See Process Model & Fork Safety
- **Business logic in exception handlers** - Makes code hard to follow; separate concerns with dedicated methods
- **Synchronous generator (`yield`) for CPU-heavy loops** - Generator event handlers hold the state lock for the entire execution. `yield` sends state deltas to the frontend but does NOT release the lock. All queued events (tab clicks, button presses) are blocked until the generator finishes. Use `@rx.event(background=True)` for anything that takes more than ~1 second.
- **Underscore-prefixed state vars are backend-only** - Reflex does not send `_foo` to the client. A remount token used as `key=` on uncontrolled inputs (`default_value`) must be a public var (`form_key`, not `_form_key`), or the Add Sample fields keep the typed values after upload. Also return `rx.clear_selected_files(...)` and do not debounce those setters — a late debounce can write the old value back after reset.
- **Using `@rx.background`** - Does NOT exist in Reflex 0.8.x. Use `@rx.event(background=True)` instead.

### Fomantic UI + Reflex Gotchas

**1. Fomantic UI Grid does NOT work reliably in Reflex:**

```python
# UNRELIABLE - columns may stack vertically instead of side-by-side
rx.el.div(
    rx.el.div(..., class_name="five wide column"),
    rx.el.div(..., class_name="six wide column"),
    class_name="ui grid",
)

# GOOD - use CSS flexbox for multi-column layouts
rx.el.div(
    rx.el.div(left, style={"flex": "0 0 30%"}),
    rx.el.div(center, style={"flex": "0 0 40%"}),
    rx.el.div(right, style={"flex": "1 1 30%"}),
    style={"display": "flex", "flexDirection": "row"},
)
```

**2. Fomantic UI Menu may not render horizontally:**

Use flexbox for reliable horizontal menus instead of `ui fixed menu`.

**3. Fomantic UI Checkbox requires specific HTML structure:**

```python
# BAD - rx.checkbox() doesn't use Fomantic styling
rx.checkbox(checked=is_checked)

# GOOD - proper Fomantic checkbox structure
rx.el.div(
    rx.el.input(type="checkbox", checked=is_checked, read_only=True),
    rx.el.label("Label"),
    on_click=handler,
    class_name=rx.cond(is_checked, "ui checked checkbox", "ui checkbox"),
)
```

**4. What DOES work from Fomantic UI in Reflex:**
- `ui segment`, `ui raised segment` - work well
- `ui button`, `ui primary button` - work well
- `ui label`, `ui mini label`, `ui green label` - work well
- `ui divider` - works well
- `ui message` - works well
- `ui top attached tabular menu` + `ui bottom attached segment` - works well for tabs (with state-based class toggling)

**5. What does NOT work reliably:**
- `ui grid` with column widths - use flexbox instead
- `ui fixed menu` - use flexbox instead
- `ui accordion` - may need JS initialization
- Native `rx.checkbox()` styling - use Fomantic structure instead

**6. Fomantic UI Tabs (state-based, no jQuery):**

```python
# Tab menu - use state-based class toggling
def tab_menu() -> rx.Component:
    return rx.el.div(
        rx.el.a(
            "Tab 1",
            class_name=rx.cond(MyState.active_tab == "tab1", "active item", "item"),
            on_click=lambda: MyState.switch_tab("tab1"),
        ),
        rx.el.a(
            "Tab 2",
            class_name=rx.cond(MyState.active_tab == "tab2", "active item", "item"),
            on_click=lambda: MyState.switch_tab("tab2"),
        ),
        class_name="ui top attached tabular menu",
    )

# Tab content - use rx.match for dynamic content
rx.el.div(
    rx.match(
        MyState.active_tab,
        ("tab1", tab1_content()),
        ("tab2", tab2_content()),
        tab1_content(),  # default
    ),
    class_name="ui bottom attached segment",
)
```

**7. Custom API endpoints with api_transformer:**

```python
from fastapi import FastAPI
from fastapi.responses import FileResponse

# Create FastAPI app for custom routes
api = FastAPI()

@api.get("/api/download/{filename}")
async def download_file(filename: str) -> FileResponse:
    return FileResponse(path=file_path, filename=filename)

# Pass to Reflex app
app = rx.App(
    theme=None,
    api_transformer=api,  # Mounts custom routes
)
```

---

## PRS Integration (Polygenic Risk Scores)

The web UI integrates the `prs-ui` PyPI package for polygenic risk score computation using PGS Catalog data.

### Dependencies

- **`just-prs>=0.9.0`**: Core library — PRS computation, PGS Catalog client, scoring file parsing
- **`prs-ui>=0.3.15`**: Reusable Reflex components — `PRSComputeStateMixin`, `prs_workbench_mode_panel()`, score grid, results table

Both are added to `webui/pyproject.toml`.

### Architecture

`PRSState` is an independent `rx.State` subclass (not a substate of `UploadState`) with its own `LazyFrameGridMixin` for the PGS Catalog scores DataGrid. This parallels `OutputPreviewState`.

```python
from prs_ui import PRSComputeStateMixin

class PRSState(PRSComputeStateMixin, LazyFrameGridMixin, rx.State):
    genome_build: str = "GRCh38"
    cache_dir: str = str(resolve_cache_dir())  # ~/.cache/just-prs/
    status_message: str = ""
```

### Data flow

1. User selects a VCF file in the left panel
2. `UploadState.select_file()` resets Output/PRS/trait grid views first, then remounts the workspace and calls `PRSState.reset_for_genome_switch` (even if the new parquet is not ready yet), then `PRSState.initialize_prs_for_file(parquet_path, genome_build)` when it is
3. `PRSState` creates a `pl.scan_parquet()` LazyFrame from the normalized parquet and calls `set_prs_genotypes_lf(lf)` (preferred input method — lazy, memory-efficient)
4. PGS Catalog scores are loaded into the MUI DataGrid for selection
5. User selects scores and clicks Compute — `PRSState.compute_selected_prs()` runs
6. Results with quality assessment, percentiles, and effect sizes are displayed

### Genome build mapping

`current_reference_genome` from file metadata maps directly to PRS genome builds:
- `"GRCh38"`, `"T2T-CHM13v2.0"` → `"GRCh38"` (default)
- `"GRCh37"`, `"hg19"` → `"GRCh37"`

### Key files

| File | What it does |
|------|-------------|
| `webui/src/webui/state.py` (`PRSState`) | PRS computation state, inherits `PRSComputeStateMixin` + `LazyFrameGridMixin` |
| `webui/src/webui/pages/annotate.py` | PRS tab uses the prs-ui workbench layout with a current-sample row instead of a second VCF upload |

### Important patterns

- **LazyFrame is the preferred input** — `set_prs_genotypes_lf(pl.scan_parquet(path))` avoids redundant I/O. The parquet path is also set as string fallback.
- **`PRSState` needs `genome_build`, `cache_dir`, `status_message`** — these are vars on the state itself (not inherited from `UploadState`), because `PRSComputeStateMixin` reads them via `self.genome_build` etc.
- **Match the prs-ui workbench, not a second upload.** The PRS tab uses `prs_workbench_mode_panel` plus `trait_selector` / `prs_scores_selector` inside Radix By Trait / By PRS tabs. Ancestry is shown on the current-sample row; do not add a toolbar population selector or a second VCF upload. Compute stays on `PRSState`; `PRSTraitState` only selects traits and syncs PGS IDs.
- **Independent `LazyFrameGridMixin`** — `PRSState` gets its own grid vars, completely separate from `UploadState`'s VCF grid and `OutputPreviewState`'s output grid.
- **PRS results are per-genome** — `select_file` must reset PRS sample state even when the new parquet is still normalizing. `prs_results`, the Altair/iframe chart (`selected_result_*`), and `prs_results_source_file` belong to one sample. Compute snapshots `prs_compute_token` + the parquet path and must discard writes if the user switched genomes. Never treat a leftover PGS ID as "already computed" for a different file.
- **Remount the sample workspace, not individual widgets** — the right-panel tabs/content wrap with `key=UploadState.selected_file`. One sample = one React tree (grids, Vega charts, reports, analysis). Destroying that subtree is cheap; the cost is the parquet page. Do not keep a widget per genome, and do not reuse one MUI/Vega instance across partitions. The left file list and top nav stay mounted. Sort artifacts must include the source path, not just the state class name.
- **Grid filters/sorts are per-sample** — `select_file` must reset Output/PRS/trait grid views *before* changing `selected_file`, then remount. MUI keeps a local `useState` filter model and can replay the previous sample's filters on unmount; `SafeGridMixin.reset_grid_view_state` clears every `lf_grid_*` filter/sort/selection field, bumps `lf_grid_view_token` (used as the grid `key`), and drops one matching remount replay. Quality-filter settings from `modules.yaml` are global and should stay the same.

### Anti-patterns

- **Never make PRSState a substate of UploadState** — it needs its own `LazyFrameGridMixin` instance; mixing into UploadState would create MRO conflicts.
- **Never pass UploadState's internal LazyFrame across states** — Reflex states are isolated; create a new `pl.scan_parquet()` LazyFrame from the shared parquet path instead.
- **Never keep the previous genome's `prs_results` or chart spec across a file switch** — the chart panel is gated on `selected_result_spec != {}`, so an uncleared Vega spec keeps showing the old sample. Compute also skips PGS IDs already present in `prs_results`, which turns a leftover Oksana score into a no-op on Livia.

---

## Design System

For UI/frontend changes, see **[docs/DESIGN.md](docs/DESIGN.md)**.

Key principles:
- **"Chunky & Tactile"** aesthetic with high affordance
- **Fomantic UI** component classes (segments, buttons, labels work best)
- **CSS Flexbox** for layouts (not Fomantic grid)
- **Oversized icons** (min 2rem), **large buttons**, **generous spacing**
- **Semantic colors**: `success` (benign), `error` (pathogenic), `info` (VUS)

---

## Learned User Preferences

- When writing READMEs or user-facing docs: put images at the top, place caveats after Quick Start, and keep intros concise while avoiding technical jargon (e.g., "VCF", "Polars", "DuckDB"). Move deep implementation details to `docs/`.
- Write in natural, human prose avoiding AI-typical patterns (em-dashes, filler transitions, marketing voice). Never hallucinate documentation.
- Don't overpromise unimplemented features (like 23andMe/microarray support). Balance credibility with honesty: ROGEN results are planned/future work, not finished outcomes. Never claim the tool solves alignment or variant calling — it only handles annotation of an existing VCF.
- Update related documentation (AGENTS.md, DAGSTER_GUIDE.md) immediately whenever code is refactored.
- For upstream PyPI dependencies (like `prs-ui`), try to fix bugs locally or provide copy-paste prompts for upstream fixes rather than patching locally.
- Use fsspec-based access patterns instead of symlinks. Cache HuggingFace data in the project's own cache using fsspec/HfFileSystem, never use `snapshot_download`.
- Avoid `subprocess` complexity for CLI commands; use uv workspace `[project.scripts]` instead. Automatically create missing directories in code rather than expecting users to `mkdir`.
- Output file names must reflect semantic content (e.g., `_ensembl_annotated.parquet`), not implementation details. Reports should be timestamped to avoid overwriting previous runs.
- When the user gives a minimal working example or pattern, wire it in directly instead of over-exploring alternatives.
- Use global/inclusive framing in docs and UI: avoid EU-only language; users from any country should feel welcome. Reference EHDS as one example among international open health data initiatives.
- When describing the platform in papers/docs, frame it as a bioinformatics tool that *joins* VCF data against module databases to add annotations. Never imply the VCF already contains annotations or that the tool makes gene-disease inferences.
- For workshop/conference proposals: primary readers are organizers, not participants. Address conference themes implicitly (don't name-drop). Use "instructor" not "facilitator". Avoid manifesto/advocacy tone, words like "neat"/"slippery"/"primer", and never leak AI instructions into document text. Clearly separate "will get" vs "will not get". Use Roman numerals for generation labels (Gen I, Gen II).

## Learned Workspace Facts

- This is a multi-root uv workspace: `just-dna-lite` (main) and `just-prs` (read-only reference). Never modify files in `just-prs`. `just-prs` was developed specifically for Just-DNA-Lite but released as a standalone library. Related repos: `just-dna-lite`, `just-prs`, `reflex-mui-datagrid`, `just-biomarkers`, `dna-seq`, `prepare-annotations`.
- The annotation-module schema + compiler live in two shared published libs — `just-dna-format` (`just_dna_format`) and `just-dna-compiler` (`just_dna_compiler`) — consumed by `just-dna-lite`, `just-dna-marketplace`, and `just-dna-agents`. We consume them (do not fork/vendor); propose changes only as notes in `/data/sources/just-dna-format/docs/{ROADMAP,CHANGELOG}.md`, never by committing to that repo. See the "Shared Module Format & Compiler Libraries" section above.
- The project runs on Linux, macOS, native Windows, and Apple Silicon Macs. Critical native deps have working wheels; Windows scripts live in `windows/`, and the Nix workflow is `nix develop` then `uv sync` then `uv run start`.
- The AI Module Creator uses the Agno agentic framework, which allows configuring OpenAI API-compatible local models (e.g., Ollama or vLLM) for complete privacy.
- Images for README live in `images/` at the project root. Use `<img>` tags (not markdown syntax) for images inside HTML `<div>` blocks.
- Only GRCh38 VCF files are fully supported (GRCh37, T2T, and microarray are planned). VCF normalization renames `start` to `pos`; PRS computation must account for this, runs in Reflex rather than Dagster, and must clear/rebuild `prs_results_rows`, `prs_results_columns`, and `prs_results_column_groups` after updating `prs_results`.
- `rx.icon()` (Lucide) icons often fail in this Reflex setup; use `fomantic_icon()` from `webui.components.layout` instead. Fomantic icon names are space-separated (e.g., `arrow up`), not hyphenated Lucide-style.
- Backend API port is auto-resolved at startup; never hardcode port 8000. Custom API routes (via `api_transformer`) are only served by the Reflex **backend**; the frontend dev server does NOT proxy arbitrary `/api/...` paths. `webui/deployment_urls.py` builds the browser-reachable base URL: `PUBLIC_BACKEND_URL` overrides `API_URL` (needed when the image sets `API_URL=http://localhost:8000`). `webui.run` selects a free backend port and persists it in `API_URL` / `REFLEX_BACKEND_PORT`; `backend_api_url` reads those so the browser constructs direct URLs (e.g. `/api/report/...`). A leftover `API_URL=http://localhost:8000` must not win when Reflex actually bound 8002. Never return `""` from `backend_api_url` — relative URLs 404 on the frontend.
- Always load `.env` via `load_dotenv()` or equivalent before using `os.getenv` for config paths (`JUST_DNA_PIPELINES_CACHE_DIR`, `JUST_DNA_PIPELINES_OUTPUT_DIR`, etc.).
- Public genomes for demos: Anton Kulaga (Zenodo 18370498, CC-Zero, 482 MB) and Livia Zaharia (Zenodo 19487816, CC-BY-4.0, 349 MB). Both are configured as `default_samples` in `modules.yaml` `immutable_mode:` section. The app can also import arbitrary Zenodo records with open-access + permissive license + VCF via the "Import from Zenodo" UI.
- 6 expert-curated annotation modules exist on HuggingFace (`just-dna-seq/annotators`): `coronary`, `lipidmetabolism`, `longevitymap`, `superhuman`, `vo2max`, and `thrombophilia` (ported from Generation-I `dna-seq/just_thrombophilia` and published 2026-07, via `pipelines v1-port`). PharmGKB (drugs) has NOT been migrated from Generation I. HuggingFace `just-dna-seq` org hosts 6 datasets and 1 model (`GenNet`).
- The first preprint was rejected by bioRxiv ("inference drawn between gene(s) and disease(s)") and medRxiv; published on arXiv instead. To avoid repeat rejection, frame the manuscript as a bioinformatics methods/software paper, not a genomic medicine paper.
- `ghcr.io/dna-seq/just-dna-lite:latest` container image does not exist on GHCR yet; `compose.yaml` builds locally. The `Containerfile` needs `chmod -R 777 .venv` for Podman rootless compatibility and `UV_FROZEN=1` to prevent re-syncing. Workshop materials live in `docs/workshops/`. Pytest must stay in workspace root dev dependencies for `uv run pytest`, and `uv` does NOT have a `uv bundle` command as of April 2026.
