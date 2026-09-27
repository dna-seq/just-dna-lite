# Agent Guidelines: just-dna-lite

## Repository layout

A **uv workspace** with two members: `just-dna-pipelines/` (pipeline + CLI library) and `webui/`
(Reflex UI). Shared folders at the root: `data/`, `docs/`, `logs/`, `notebooks/`. `prepare-annotations`
and `just-prs` are sometimes added to the workspace; both are **read-only**. Check
`prepare-annotations/AGENTS.md` for shared Dagster patterns and adopt better ones here.

### Running

- `uv run start` from the repo root starts the full stack (`uv run dagster` for pipelines only).
  `uv run serve` is the single-process server (demos, workshops, no hot reload); it owns the Granian
  workers and the compute pool, so it never `waitpid(-1)`s.
- **Launchers never exec a uv console-script wrapper.** Locked-down Windows (AppLocker, Smart App
  Control) blocks the unsigned `.venv\Scripts\*.exe`. Every hop is `sys.executable -m <module>`:
  `just_dna_lite.cli start`, `webui.run`, `just_dna_lite.dg dev` (a shim; `dagster_dg_cli` has no
  `__main__`, and `python -m dagster dev` is deprecated). Build argv with `process.dg_dev_argv` /
  `webui_dev_argv`. Fenced by `tests/test_cli_entrypoints.py`.
- **Ctrl+C must kill the whole Dagster daemon tree.** `dg` is detached (`start_new_session` on POSIX,
  `CREATE_NEW_PROCESS_GROUP` on Windows); `just_dna_lite.process` sends SIGINT then SIGKILL (POSIX) or
  `CTRL_BREAK_EVENT` then `TerminateProcess` (Windows). Startup reaps stale Reflex processes holding
  port 3000. A second `uv run start` is last-writer-wins. See `tests/test_process_shutdown.py`.
- Port cleanup (`_kill_port_owner`, `uv run kill-ports`) goes through `process.find_port_listeners`,
  **listeners only** (a bare `lsof -ti :port` also matches a browser connected to 3000).
  `JUST_DNA_START_KILL_PORTS` stays off by default: 8000/8001 may belong to unrelated tools.
- If `uv run start` resolves to a dependency's `start` (e.g. `prs-ui`'s), uv kept stale wrappers: bump
  the root `just-dna-lite` version and `uv sync`. Never rename the command or duplicate entries.

## Dependency pins

- The **only** `==` pin in the workspace (including sibling repos) is `reflex==0.9.12` in
  `webui/pyproject.toml`. Everything else floats on `>=`. No `constraint-dependencies` or
  `override-dependencies` exist anywhere.
- Deliberate ceilings: `grpcio<1.82` and `grpcio-health-checking<1.82` in lockstep (1.82 gencode needs
  protobuf 7.35, dagster caps `protobuf<7`); `google-genai<2.0`; `requires-python >=3.13,<3.14`.
- `agno[mcp]>=3.0.10`: agno 3 imports the mcp 2.x names, so depend on its extra; never re-add a bare
  `mcp<2.0` cap.
- Format libs: `just-dna-format>=0.7.1`, `just-dna-compiler>=0.7.2`, `just-dna-enricher>=0.7.3` (the
  `v0.7.3` cut, 2026-09-27; a derivation-only patch, no field/table/parameter/warning code moved, no
  compiled module needs recompiling — corrections reach a module only via `enrich --rederive`).
  `just-dna-registry>=0.27.0` **moves with the format pin**: `contract_compatible` treats a `0.x`
  format minor as breaking on either side, so a mismatched pair refuses to publish with no obvious
  cause. The format minor is still `0.7`, so this bump is not contract-forced; 0.27.0's only client
  change is an opt-in `RegistryClient.publish(pack=…)` needing a 0.27 server, which we do not pass.
  Check a server with `curl -s $REGISTRY_URL/api/v1/version`.
- **Upgrading reflex does not upgrade `reflex-components-*`.** Upgrade them explicitly, then compare
  `uv pip list | grep reflex` with the release notes:
  `uv lock --upgrade-package reflex-components-core --upgrade-package reflex-components-radix && uv sync`.
  Transitive caps shift between reflex releases (e.g. `wrapt`); either direction is expected.
- `webui/reflex.lock/package.json` and `bun.lock` are generated; never hand-edit, regenerate both
  together (`frozen_lockfile` fails fast on drift).

## Coding standards

- Type hints everywhere. `pathlib` for paths. Absolute imports only. **No inline imports** (the one
  exception: a module-level `try/except ImportError` for an optional dependency).
- Avoid try/except unless the error is genuinely expected; never nest them.
- Polars over pandas; lazy (`scan_parquet`) and streaming (`sink_parquet`); pre-filter before joins.
- Typer for CLIs, Pydantic 2 for data classes, Eliot for structured logging.
- Data lives in `data/input`, `data/interim`, `data/output`. Create missing directories in code.
- No placeholder paths, no legacy shims: refactor aggressively.
- Read terminal warnings, deprecations especially; your API knowledge may be stale.
- Versions live in `pyproject.toml`, never `__init__.py`. Avoid `__all__`.
- `uv sync` / `uv add` only, never `uv pip install`.
- **No paths outside this repo in this file**, except cache dirs (`~/.cache/...`). Name another repo by
  its PyPI package or `https://github.com/dna-seq/<repo>`; a sibling `../` or absolute path resolves
  only on the machine that wrote it.
- **`[tool.uv.sources]` holds workspace members only.** A `path =` / `editable =` source pointing at a
  sibling checkout makes `uv sync` fail on every other machine. Test unpublished libs with an
  uncommitted override.
- **A pin that won't resolve is waited for, not rerouted.** Poll `curl -s https://pypi.org/pypi/<pkg>/json`
  with backoff (30s, 1m, 2m, 4m, 8m, 15m), then stop and report. No path source, vendoring or downgrade.
- When an outdated-API mistake causes a crash or major logic failure, record the correct usage in this
  file.

## Module configuration (`modules.yaml`)

`modules.yaml` lists module **sources** (any fsspec URL), optional **display metadata** (`title`,
`description`, `icon`, `color`, `report_title`), the **Ensembl reference** (`ensembl_source.repo_id`),
`quality_filters`, `registries` and `immutable_mode`. Modules are always auto-discovered; unlisted ones
get generated defaults.

- **Layering**: the git-tracked repo-root file holds defaults (bundled fallback:
  `just-dna-pipelines/src/just_dna_pipelines/modules.yaml`). Runtime writes go to the gitignored working
  copy `data/interim/modules.yaml` via `get_config_path()`. `_load_config()` **merges** the working copy
  over the defaults (`module_metadata` dict-merged, `sources` unioned by url, `registries` by key). Never
  substitute one for the other: a working copy that replaced the defaults stripped every built-in
  module's metadata.
- **A broken working copy is recovered from; a broken default is not.** `_load_config()` runs at import
  (`MODULES_CONFIG`), so a raise there shows up as Dagster's traceback-less `Error loading repository
  location`. `_read_yaml_tolerant` falls back to defaults and `_warn_unusable_working_copy` reports on
  eliot **and** as a `UserWarning`. The default keeps the raising `_read_yaml` (recovering would yield
  zero sources and a healthy-looking app that annotates nothing). `save_config` moves an unparseable copy
  to `modules.yaml.corrupt` instead of overwriting it. `module_registry`'s three register/unregister
  paths read the copy alone (unmerged) through `module_config.read_config_for_update`. Tests:
  `just-dna-pipelines/tests/test_modules_yaml_recovery.py`, which derives its baseline by running the
  loader with no working copy, never by reading `modules.yaml`: `_drop_project_runtime_sources` strips
  the repo-local sources whenever `JUST_DNA_PIPELINES_OUTPUT_DIR` is set, and any test module's
  `load_env()` sets it session-wide.
- Never hardcode module lists, metadata, HF repo URLs or the Ensembl repo id: use `get_module_meta()`,
  `build_module_metadata_dict()`, `MODULES_CONFIG.sources`, `MODULES_CONFIG.ensembl_source.repo_id`.
- Source URL forms: `org/repo` or `hf://datasets/org/repo`, `github://org/repo`, `https://…`, `s3://…`,
  `gcs://…`. A lead table at the root means a single module; subfolders with one mean a collection;
  override with `kind: module|collection`.
- A **lead table** is any family in `module_config.LEAD_TABLES` (`weights` for most, or `pharm_variants`,
  `diplotypes`, `pgs`, …). Adding a family there teaches discovery and the publisher at once. Never test
  for `weights.parquet` alone: that hid `pharm_variants`-led modules from discovery and the publish pane.
  `module_config.has_lead_table` / `find_lead_table` are the local twin of discovery's
  `hf_modules._find_lead_table`.
- Key files: `module_config.py` (models, loader, helpers), `annotation/hf_modules.py` (discovery,
  `MODULE_INFOS`, `DISCOVERED_MODULES`).

## MCP server (`just_dna_pipelines.lite_mcp`)

`uv run pipelines mcp` (stdio) and `uv run pipelines mcp --transport http` expose samples, modules,
trial installs, background annotation jobs, results and module validation to MCP clients. `uv run
start` also serves HTTP on `JUST_DNA_MCP_PORT` (default 3006) unless `JUST_DNA_MCP_HTTP=false`.
Full reference: **[docs/MCP_SERVER.md](docs/MCP_SERVER.md)**. Rules that keep it working:

- **No tool does annotation work in-process.** `start_annotation` writes
  `data/interim/lite_mcp/jobs/<id>/job.json` and spawns `python -m just_dna_pipelines.lite_mcp.worker`
  (never a fork, never a console-script wrapper); the worker owns `job.json` from then on, and the
  server records the pid in `worker.pid` rather than rewriting it. State lives on disk so a stdio
  server restarted by the next client session can still report on an earlier job.
- **`annotation_runner.run_annotation` is the one path for a sample's run**, shared by `uv run
  annotate` and the worker. It picks `annotate_modules_and_report_job` (no normalization) when
  `normalized_parquet_is_current` says the parquet matches the quality-filter hash in force, else
  `annotate_and_report_job`. Config for a job must only name assets in its selection;
  `test_the_runner_config_validates_against_the_job_it_is_for` fences that for all three jobs.
  `webui.state._normalize_run_config_if_stale` still carries its own copy of the staleness test.
- **`install_module` copies, never recompiles or symlinks,** and only replaces what its own ledger
  (`data/interim/lite_mcp/installs.json`) says it installed: a registry install under the same name
  is refused, as is a name another source already supplies (discovery would shadow it).
- **Validation reads presence from `user_vcf_normalized.parquet` and matches from the job's own
  snapshot** of `{module}_weights.parquet` (`jobs/<id>/results/<user>__<sample>/`). In a run's
  output the module's rsID is `rsid_{module}`; plain `rsid` is the VCF's ID cell, often empty.
- **Findings stay three-valued**: `not_assessed` when a check could not run, never silence.
- **A phenotype module goes through `get_results`, not `validate_module`.** The worker snapshots
  `{module}_phenotypes.parquet`, `get_results` returns its per-gene calls (`phenotype_calls`), and
  `validate_module` refuses it with the reason, because every check there is about per-variant weights.
- **When the stack is up, give the live UI URLs.** A reply that uses the MCP while `uv run start` is up
  includes the web UI and Dagster addresses, read from the launcher banner or the listening ports, never
  assumed: Reflex prints another port when 3000 is taken (a leftover `prs-ui` often holds it); Dagster
  is `http://127.0.0.1:3005` unless `DAGSTER_PORT` / `--dagster-port` moved it. `:3006/mcp` is the
  protocol endpoint, not a page.
- **Seeing the tools means the MCP Inspector**: `npx @modelcontextprotocol/inspector
  http://127.0.0.1:3006/mcp` against the running server (substitute the live port). `fastmcp dev apps`
  lists only `@app.ui()` tools (none here), and `fastmcp dev inspector` starts a second server. Quote the
  URL the Inspector prints, token included, and leave it running.

## Shared format libraries

The module schema, compiler and enricher are published libraries shared with `just-dna-marketplace` and
`just-dna-agents`. **Never vendor or fork them, and never assume a symbol is unused** because this repo
does not call it.

- `just_dna_format`: `spec` (authored models), `manifest`, `integrity`, `identity`, `vocab`
  (`RSID_PATTERN` lives here, not in `spec`), `alleles`, `derive`, `layout`, `vrs`.
- `just_dna_compiler`: import from **`just_dna_compiler.compiler`** (`validate_spec`, `compile_module`,
  `reverse_module`); the package root exports nothing. `resolution` is table-injected only.
- `just_dna_enricher`: enrichment and the DuckDB Ensembl `resolver` (`resolve_variants`,
  `EnsemblReferenceError`). Inject-only: it never downloads a reference.
- `just_dna_pipelines.module_compiler` is a re-export shim; import from the libs in new code. The one
  local piece is `module_compiler/resolver.py::ensure_resolver_db` (HF download + DuckDB build), which
  `register_custom_module` and the pipelines `resolve_variants` wrapper use to auto-provision.
- **Filing upstream**: never edit or commit the
  [just-dna-compiler](https://github.com/dna-seq/just-dna-compiler) repo (renamed from `just-dna-format`;
  the PyPI names are unchanged), and never touch its `ROADMAP.md` or `CHANGELOG.md`. Append a
  `## Sn — <what happened>` section to its `docs/CONSUMER_SUGGESTIONS.md`, claiming the id with
  `.claude/triage-state.py --next` in that repo. Write a report (what you ran, expected, got, did
  meanwhile), not a request. That note is the whole job. Its ROADMAP's "Not format scope" section rules
  out diplotype *callers* (measurement is ours) and assigns RM7, the report-card schema, to us.

### Contract facts that bite

- **Versioning**: a new optional column is a minor. `artifact.digest` moves on every recompile across a
  version boundary; `content_signature` (authored identity) does not. Re-pin anything that caches a
  digest; keying on `content_signature` needs nothing. We cache neither. 1.0 will remove `state`.
- **Three artifact generations are live**: 0.3 on HuggingFace, 0.5 (backup at
  `data/interim/v1_port_0_5/`, gitignored) and 0.7 (the rebuilt `data/interim/v1_port/`). Every read path
  must handle all three; classify by the columns and values present, never by family name or era.
- `variant_key` is the authored identity: the rsid for rsid-authored rows, a `ga4gh:VA.…` id for a
  coordinate-authored SNV, else `chrom:start:ref[:alts]`. Per-ALT VRS ids for rsid modules are in
  `resolution.csv`. `ModuleInfo.version` is a SemVer **string**.
- **`direction` and `clin_sig` are authored-optional and often empty.** The compiler never fills a blank
  cell. Read through `report_logic._effective_direction` / `_effective_clin_sig`: column first, else
  `derive.direction_from_state(state, weight)` / `derive.clin_sig_from_booleans`. Any new parquet-side
  read must do the same. Never round-trip `clin_sig` through the booleans (they cannot say
  `likely_pathogenic`). `direction == "contested"` is a finding, distinct from `unknown`; sign 0, no
  colour.
- **`locus_count > 1` marks an expansion member** (one rsid placed at N loci). Defaults to 1, so test
  `> 1`, never truthiness. `None` (pre-0.6) and `1` render nothing; do not coalesce `None` to `1`. Keep
  the pre-0.6 `ref`-spelling guard beside it; it only sees members disagreeing on `ref`. Restoration
  withholds an expansion member (it would fabricate N results); a *called* one is a real observation, so
  the report keeps it with a *Position ambiguous* caveat naming N.
- **`ARTIFACT_PARQUETS`, `LEAD_PARQUETS`**: import, never re-list. `module_config.LEAD_TABLE_CSVS` is the
  single lead-family to CSV map. `tests/test_format_0_6.py` asserts set equality with the compiler.
- **Licence sidecar**: reach it through `just_dna_format.layout` (`resolve_sidecar`,
  `sidecar_write_path`, `sidecar_candidates`), never by name. Both spellings present raises
  `SidecarCollision`. The rename stops at the file: `licensing.csv` → `sources.parquet` →
  `manifest.sources`; do not rename the latter two.
- **`manifest.weighting`** says what scale `weight` is on. Absent means unstated, never comparable. We
  never aggregate `weight` across modules; if you do, that block is the gate.
- **`StudyRow.variant_key` may be `None`** (a citation for a bin boundary). Do not coerce it; handle the
  null in any join on it.
- `studies.parquet` `confidence` renders **with its `confidence_unit` or not at all**.
  `pharm_variants.pmid` renders as *Citation* beside *Evidence level*, both or neither.
- `clin_sig_concordance.parquet` (via `ModuleInfo.concordance_url`) is joined on
  `(variant_key, genotype)`; `discordant` renders *Authorities disagree*. Nothing picks a winner;
  `unchecked` renders nothing.
- Restoration never reads a missing call as reference inside GIAB's low-mappability + segdup mask
  (`hard_regions.py`); outside it, on WGS with a call in the flank, `requires_callable` rows restore too.
  Mask unavailable → old rule: `requires_callable == True` blocks; `False` and null keep the row. Write
  `is_null() | ~col`, not `fill_null(False)`.
- Enricher exceptions: we hold no `except` around enricher passes. If you add one, order narrow-first
  (the unavailability type is a subclass).
- **Never match warning prose.** Classify a compiler finding with `Compilation.warnings_summary` /
  `carried`. `trusted` is read from the registry (`_trust_word` keeps it tri-state); `UNJOINABLE_PHRASE`
  is the registry's. `pharmgkb` publishing as `trusted: false` is correct, not a defect.
- `validate_spec().stats` keys: `variant_count`, `unique_rsids`, `gene_count`, `genes`, `categories`,
  `study_count`, `module_name`.

### Build traps

- **`compile_module(resolve_with_ensembl=False)` disables all resolution**, including an injected
  `resolution.csv`, and compiles "successfully" with `chrom=None` everywhere. Use
  `compile_module(spec, out, resolve_with_ensembl=True, ensembl_cache=None)`.
- **`load_env()` before the first `resolve_*_reference()` in a process**, or the first default cache dir
  resolves from platformdirs and returns `None`.
- **Provision caches with `uv run pipelines prepare-caches`** (`caches.prepare_caches`), never
  `just-dna-enricher cache pull` (removed upstream; pulled only published lanes, to the wrong dir).
- `just_dna_pipelines.enricher_cli` mounts `just_dna_enricher.cli` behind a guarded import (it failed
  beside dagster's protobuf before enricher 0.7.2). Do not import `just_dna_enricher.cli` anywhere else.
  `just_dna_lite.cli` owns the installed script.
- `draft_gene_panel` aborts on ClinVar's malformed 9-digit PMIDs; `v1_port/clinvar_panel.py` passes
  `max_citations=0` and drafts its own filtered `studies.csv`.
- Since format 0.6 the compiler places `pharm_variants` / `haplotypes` / `heteroplasmy` from
  `resolution.csv` too (`manifest.compilation.positional_rows[_placed]`; `None` = not counted). Older
  artifacts still carry null coordinates, hence value-based routing below.
- `v1_port/runner.py` clears every sidecar candidate before `enrich` so the rebuild writes
  `licensing.csv`. `clinvar_panel.py` writes no `panel:` block; its provenance (incl. `panel_genes`) is
  in `clinvar_panel.log`.
- **`v1_port/runner.py` re-anchors indel coordinates to ClinVar before compile** (`reanchor.py`,
  gated `module.needs_ensembl`). The enricher resolves rsID→coordinate from the Ensembl cache alone
  (every `resolution.csv` row is `authority=ensembl`) and validates ref/alt against that same source,
  so an Ensembl-dump insertion anchored one base off the caller/ClinVar convention ships
  self-consistent and unmatchable — the position join silently drops real carriers (measured on
  `superhuman`: rs72613567 `4:87310241 A>AA` where callers/ClinVar carry `4:87310240 T>TA`, +2 others).
  Upstream: **S117** (the Ensembl anchor defect, → RM267 + RM268), **S120** (the format declares no
  coordinate-normalization convention, so a legal respelling is a silent miss), **S121** (single-authority
  resolution with no cross-authority discordance check). **RM268 shipped in enricher 0.7.3** but fixes
  only the *live REST rung* (`ref='-'` at the interbase `start`, e.g. `rs8176719` ABO O1); **RM267 — the
  Ensembl VCF-*dump* insertions anchored one base early, which is the class reanchor.py compensates for —
  is still open upstream**, so this build-side re-anchor stays. RM267 assigns it here.
  `reanchor_indels_to_clinvar` adopts ClinVar's `(start, ref, alt)` for a single-alt indel rsID ClinVar
  places differently (ClinVar/dbSNP is the rsID authority), clears the now-wrong VRS id, and re-derives
  the genotype by zygosity role; **multi-allelic authored rows and rsIDs ClinVar does not carry are left
  alone and reported, never guessed**. Reference-free on purpose — left-alignment would need the GRCh38
  FASTA (not a guaranteed workspace asset) and would rewrite the authored genotype, and it cannot fix the
  −1 class ClinVar simply has right. Verified: superhuman's dropped findings match again on
  antonkulaga (+2) and newton_winter (+2). Tests: `tests/test_reanchor.py`.

### Building and releasing modules

Runbook: [docs/MODULE_RELEASE_0_5.md](docs/MODULE_RELEASE_0_5.md); what each module is:
[docs/V1_PARITY.md](docs/V1_PARITY.md). Republishing is the maintainer's call.

```bash
uv run pipelines v1-port port --all        # six curated Gen-I ports
uv run pipelines v1-port clinvar --all     # cardio / cancer / pathogenic
uv run pipelines v1-port pharmgkb          # drug response (ClinPGx)
uv run python scripts/registry_precheck.py --namespace sandbox   # publish dry run
```

The pre-check token must own the namespace: `REGISTRY_TOKEN` owns `test-namespace*`,
`REGISTRY_TOKEN_SANDBOX` owns `sandbox` (on prod). Neither owns `just-dna-seq`.

## Annotation engine (`hf_logic.py`)

The engine reads five lead-table columns (`rsid`, `chrom`, `start`, `ref`, `genotype`) and left-joins
the rest opaquely, so every artifact column reaches the output parquet. Anything missing from a report
was lost in the report, not here.

- **Discovery attests from `manifest.artifact.files`** where a source publishes a manifest (all ten
  modules in `just-dna-seq/annotators` do), and probes only when there is none (`None`, never an empty
  set). The HF publisher never deletes, so probing can find a stale parquet and misread the module's
  kind. A partial manifest that omits the lead parquet makes the module invisible to discovery while
  `list-custom` still lists it. `logo` and `metadata` always probe.
- Discovery keeps `identity.version`, `artifact.digest` and `weighting` on `ModuleInfo`
  (`manifest_version` / `manifest_digest` / `manifest_weighting`) for `read_module_provenance`, and
  `published_at` / `identity.namespace` (`manifest_published_at` / `manifest_namespace`) for
  `module_source` (`hf` | `catalog` | `local` | `remote`), the analysis picker's source tag. A
  Catalog install is a local directory whose manifest carries the registry's `published_at`; never
  infer it from the `{namespace}__{name}` install key, since `__` is legal in a module name.
- **Everything discovery calls must be defined above `MODULE_INFOS = discover_hf_modules()`.** A
  `NameError` there is caught per source, so discovery silently returns nothing.
  `tests/test_consumer_handoff.py` probes a local directory to catch this offline.
- **Classify a lead table by schema** (`_lead_join_strategy` → `position` | `rsid` | `unsupported`).
  Keyless families raise `UnsupportedLeadTable`, which the per-module loop records and skips. Null
  coordinates downgrade to an rsid + genotype join; a VCF with no rsIDs then raises
  `UnsupportedLeadTable` (`step="vcf_has_no_rsids"`) before writing anything, because that pairing is
  unassessable, not zero.
- **`_normalize_lead_genotype` splits on `/` or `|` and never sorts** (sorting folds phased `A|G` and
  `G|A` into one key). The VCF side always sorts, so a phased authored genotype in non-sorted order can
  never match; `_unmatchable_phased_rows` logs it (`step="phased_rows_cannot_match"`).
  `report_logic._genotype_alleles` is the Python twin via `just_dna_format.alleles.split_genotype`;
  `tests/test_format_0_6.py::TestOneGenotypeSplit` holds them equal. `report_logic._genotype_join_key`
  is the opposite operation (rebuilds the authored key, so it sorts unphased). Document the three
  together.
- **The position join requires `ref` agreement** where the module states one. Without it `G>A` matched
  `GTGTCT>A` at the same locus (6 of 9 "pathogenic" findings on one sample were that).
- **Contigs go through `just_dna_format.vrs.normalize_chrom`**, mapped over distinct contigs as one
  vectorized replace. A `^chr` strip turns `chrM` into `M` and silently drops all mtDNA.
- **The rsid join explodes semicolon-separated VCF IDs** (`_vcf_rsid_join_keys` → `_rsid_join_key`,
  dropped after the join).
- **A local module URL is a bare path, never `file://`** (`hf_modules._build_url`): `file://C:/…` parses
  `C:` as a host. Ask `local_module_path` / `is_local_module_url`, never `startswith("/")`. Tests:
  `just-dna-pipelines/tests/test_local_module_urls.py`.
- **Return matched rows, not the parquet height** (the position join keeps unmatched rows on purpose).
  `annotate_vcf_with_module_weights` returns `(path, num_matched, restoration_stats)`.
- **Sort immediately before `sink_parquet`.** The streaming left join emits a non-deterministic
  multiset; the sort is a barrier that fixes it without `collect()`. Never remove it or turn it into a
  `collect()`. `restoration._with_flanking_distance` sorts its `join_asof` inputs for the same reason.
  After touching the engine, report or restoration, run `scripts/regression_snapshot.py`
  (`snapshot` / `compare`; baseline in `data/interim/regression_baseline/`).
- `AnnotationManifest` records `output_dir`, per-module `lead_table`, `skipped_modules` and
  `failed_modules`. Never derive the output dir from `modules[0]`.

### Compound phenotypes (`phenotype_caller.py`)

A module with `haplotypes` plus a combiner (`diplotypes`, or `allele_function` + `activity_phenotype`)
is a phenotype module (`hf_modules.module_kind`). `annotate_vcf_with_all_modules` dispatches it to
`phenotype_caller.call_phenotype_module` before the weights path, writing `{module}_phenotypes.parquet`
and counting calls apart from variants (`manifest.phenotype_calls`). Both combiners are read; phase
comes from `GT` `|` plus an equal non-null `PS` (already in the normalized parquet when the VCF has it,
so do not add it to normalization); an indel site also matches its event respelled within 10 bp, and a
non-unique window is `no_call`, never restored. Diploid only. Contract and pilots (ABO, FUT2, APOE,
HFE): [docs/PHENOTYPE_CALLS.md](docs/PHENOTYPE_CALLS.md). Hom-ref sites reuse
`restoration.restorable_sites`. `validate_modules` drops a module name discovery does not know without
an error, so a script that imports discovery before `load_env()` silently runs none of the locally
registered modules — load `.env` first.

### Reference-genotype restoration (`restoration.py`)

A variant-only VCF has no record where the sample is hom-ref, so an authored hom-ref row (e.g.
lactose `G/G`) could never match. Restoration infers those rows, scoped to the module's authored
hom-ref sites, marking them `genotype_evidence = restored_hom_ref` (vs `called`). Design follows
`just_prs.reference_allele`, but gated far more strictly because each row becomes a sentence about a
person. **No on/off flag**: `RestorationContext.enabled` measures the callset. Gates, all required:

- **Variant-only**, per `infer_genotype_input_mode` run on the **normalized parquet** (our
  `pass_filters` already drops `RefCall`, so a gVCF arrives variant-only).
- **Whole-genome**, per `detect_callset_scope`: `MIN_WGS_SITES` (1M) and `MIN_WGS_BREADTH` (0.75, share
  of span within one flank of a call; WGS measures ~0.95, a clustered callset ~0.21). Do not replace
  breadth with a gap percentile; clustered calls fool it.
- The site was **not emitted** by the caller.
- A called variant within `restoration_max_flank_bp` (default 10 kb), recorded on `restored_flank_bp`.
  Not a callability proof, so restored rows render with an `inferred` badge. Never merge the two
  categories.
- Not an expansion member (`locus_count > 1`, plus the pre-0.6 `ref` guard). Not `requires_callable`.
- `hom_ref_rows` returns `None` for a lead table without `ref`/coordinates (exclusion by schema).

The restored frame is built from `vcf_lf.limit(0)` + `hstack`, so it inherits the schema. Restored
counts (`total_variants_restored`) stay apart from annotated counts. Tests: `tests/test_restoration.py`.

**Do not implement `requires_callable`/`callable_from`/`quality_from`/`min_quality` as bare column
lookups.** `user_vcf_normalized` flattens INFO and FORMAT into one namespace (`AF`, `DP`, `MQ`, `AD`
collide). Prerequisites: keep the namespaces distinct and accept `INFO/DP` / `FORMAT/DP` (RM53); QUAL
inverts on reference records (RM57); for gVCF use `MIN_DP` with interval containment. Read
`just-dna-format/docs/PROPOSAL_0_6.md` (RM53–RM67) before touching this seam.

## Report (`report_logic.py` + `longevity_report.html.j2`)

- **Join `annotations.parquet` by the finest key present** (`_annotations_keying`): `genotype`
  (0.6+, via `_genotype_key_expr`), else dedup on `variant_key` (0.5), else `rsid` (0.3). Joining a
  poly-effect module on `rsid` alone multiplied rows up to ×2.85. `tests/test_module_roundtrip.py` checks
  `_genotype_key_expr` reproduces every key the compiler wrote.
- **Render if present, never a fixed field list.** `_AUTHORED_AXES` flows into the view model, each with
  an `{% if %}` row. `test_a_populated_0_5_axis_reaches_the_html` guards it.
- Routing dispatches on the manifest's `lead_table` (default `"weights"`). `pharm_variants` gets a
  drug-keyed section ranked by ClinPGx evidence.
- **Modules not read in this run** renders `skipped` (about the module, retry won't help) and `failed`
  (about this run, usually actionable) separately via `build_module_exclusions`, with the engine's reason
  verbatim. Otherwise a silent skip reads as "nothing found".
- **Modules in this report** renders `version` / `digest` / `source_url` / `weighting` from
  `read_module_provenance`. All tri-state: `None` renders *Not stated*. Version falls back to the spec
  (`module_config.spec_version`). **The digest is the module's claim, not verified**: nothing calls
  `verify_manifest` yet. If you wire it, `require_marketplace=True` rejects every local compile.
- Source credits list terms only for `layer == "annotation"`; permission booleans are tri-state.
- Variant tables are one macro (`variant_rows` / `variant_table`). JS constraints: the detail row is the
  immediate next sibling; preview rows carry `data-preview-row` (the detail row must not);
  `preview_row_limit` comes from `report_logic.TABLE_PREVIEW_ROWS`; detail `colspan` equals the header
  `<th>` count (9).
- Title and filename derive from the module: single-module runs use its `report_title` and a slug
  (`report_title_for_modules` / `report_filename_stem`), multi-module runs `Genomic Annotation Report` /
  `report`. **Glob reports as `*.html` and pick by mtime.**
- Each rsID row has four AI prompt links (`_build_variant_ai_links`); clicking sends that genotype to a
  third party, never automatically. They are ~half the file size. Keep icons as one `<symbol>` set with
  `<use>`. Phenotype results get the same four (`_build_phenotype_ai_links`); the privacy note lives in
  each button's tooltip and `aria-label`, and in full under *How to read this report*.
- **Phenotype modules render in `phenotype_section.html.j2`**, each as its own subsection so two of them
  never read as one. A result is an open block (plain headline, the
  module's conclusion, a **More details** fold with the fitting pairs, activity score, phase, how each
  position was read, the module's rule tables, build notes), never a card nested in a card. The module's
  title and description come from `modules.yaml`, else its own `manifest.json` (`module_display`), and
  its README's `## How this works` section follows the results, closed (`readme_section`): each result explains its own terms, so an open explanation above it read as repetition.
- **A simple module shows Positive / Negative / Net weight and coloured weights only when it has a
  direction** (`module_is_directional`: some row of its lead table, not just the rows this person
  matched, has an effective direction of `protective` or `risk`). A trait module (personality, taste)
  signs its weights by "more of the trait" and marks directions `unknown`/`neutral`; it renders plain
  weights and one sentence saying so (`apply_directionality`).
- **Phenotype modules share one *Combined results* section after the per-position modules**, with one
  introduction; each module is a subsection that ends with a table of every position it reads
  (`phenotype_members`: gene, rsID, what the file showed, how it was read, which versions it marks).
- **A phenotype result read from assumed positions says so as its last sentence**, visible without a
  click: `restored_hom_ref` sites are an inference from nearby coverage, and a missing call can mean the
  stretch was never read (APOE sits in a GC-rich stretch sequencing often misses). The badge inside
  More details alone left a definite-looking "You have two copies of ε3" on top of it.
- **Only verified link targets.** `dbsnp_url` (rsIDs) and `hgnc_url` (gene symbols, human only) build a
  link only for a well-formed identifier; PubMed uses its canonical `/{pmid}/` form. Positions get no
  link: Ensembl's gene/location URLs now 404 or redirect into a JS browser, and UCSC sits behind a bot
  check, so none could be verified; an rsID's dbSNP page states its GRCh38 position. GenAge was dropped
  because a gene it does not index renders a blank page. Before adding a target, fetch a seeded sample
  of rendered links and check each page names the identifier (JS pages via `google-chrome --dump-dom`;
  PubMed blocks scripts, so check PMIDs through E-utilities `esummary`).
- The end of the report: *How to read this report* stays visible; *Modules not read* keeps one visible
  sentence naming them with the reasons folded; module versions and data sources sit in one folded
  *Technical details* section. All templates render through `report_environment()`, shared with tests.

## Report voice (mandatory for module text and templates)

Two audiences with equal weight: people without a science background, and professionals. Full guide:
[docs/REPORT_VOICE.md](docs/REPORT_VOICE.md); the module-author twin is the `module-voice` skill in
[just-module-creator](https://github.com/dna-seq/just-module-creator).

- **Three layers, each in its place.** The result (the `phenotype` label and a conclusion's first
  sentence), what it means (the rest of the conclusion), and **More details** (rsIDs, coordinates,
  subtype codes, statistics: `haplotypes.csv`, `studies.csv`, `README.md`, the fold). No layer-3 codes in a
  label or conclusion.
- **Simple is not telegraphic.** Full sentences about the reader ("You have blood group AB"): what they
  have, what they would notice compared with people who carry the most common version (not always the
  reference genome's) with its size and certainty, what the gene does, how common it is, the practical
  meaning, the main limit. When no noticeable difference is known, say so; a description of the gene's
  job is never a substitute.
- **Every term is explained at first mention, in that text.** Each conclusion is read alone, so ε4 or
  C282Y is explained in the conclusion that uses it, not in another result or in *How this works*.
- **Results first; notices at the end.** Interpretation, research-use and privacy text live once in *How
  to read this report*; a caveat about one result is that result's last sentence.
- Practical notes are welcome when the evidence is clear, always naming who decides anything medical;
  never tell a reader to change a medicine, supplement, diet or treatment.
- Same result, same label, same conclusion (the report groups candidate pairs by label).
- Before publishing a module, two independent reviewer agents read the rendered report: a lay reader and
  a scientific reviewer (`docs/REPORT_VOICE.md` § *Independent review before publishing*).

## Registry stores (`registries:` in `modules.yaml`)

The Catalog talks to one server at a time, chosen in the store selector.

| key | URL | token env |
|-----|-----|-----------|
| `prod` | `https://module-registry.just-dna.life` | `REGISTRY_TOKEN` |
| `polygon` (test ground) | `https://module-polygon.just-dna.life` | `REGISTRY_TOKEN_POLYGON` |

- `RegistryStore` (`module_config.py`) is the model; use `get_registry_stores()` / `get_registry_store()`
  / `default_registry_store()`. Never hardcode a registry URL.
- `$REGISTRY_URL` picks the opening store (the CLI, `registry_org_cli` and `registry_precheck.py` read
  it); an unknown URL joins as store `env`. Selection is per session, never persisted.
- `registry_identity.json` holds one slot per store plus `install_id`. Every client call goes through
  `RegistryState._client_args()`; `_reset_for_store_switch()` clears catalog, account and publish state.
- **Tokens are per store, one-way.** `set_env_var` writes only the selected store's `token_env`, and
  `_ensure_identity` never reads `$REGISTRY_TOKEN` back. A polygon token in `REGISTRY_TOKEN` shows up as
  `403 insufficient_capability`. `REGISTRY_TOKEN_SANDBOX` is the `sandbox` namespace on prod.
- Installs land at `CUSTOM_MODULES_DIR/{namespace}__{name}` regardless of store (known limitation).
- **Failures name the server**: route through
  `webui.registry_errors.report_registry_failure(action, url, exc)`. The public registry is IPv4-only,
  so an IPv6-only client gets ENETUNREACH while HuggingFace works.
- **Contract refusals say which side is behind**: `describe_contract_mismatch(url, e.server, e.client)`
  judges by API version then format version, never the registry package version.
  `RegistryState.contract_mismatch` holds the banner text.
- Tests (network-free): `tests/test_registry_stores.py`, `tests/test_registry_error_messages.py`.

## Immutable (public demo) mode

Full docs: [docs/IMMUTABLE_MODE.md](docs/IMMUTABLE_MODE.md). `JUST_DNA_IMMUTABLE_MODE=true` (checked
first) or `immutable_mode.enabled` disables uploads and serves `default_samples`; `allow_zenodo_import`
toggles Zenodo import.

- Never hardcode Zenodo URLs: use `get_immutable_config().default_samples`. Give each sample a
  `filename` so startup resolves locally without a Zenodo metadata call.
- `validate_zenodo_record()` checks open access, permissive licence and a VCF before download. Zenodo
  metadata is recorded on the `user_vcf_source` materialization.
- `safe_user_id` is always `"public"` in this mode.
- Public genomes: Anton Kulaga (Zenodo 18370498, CC0, `antonkulaga.vcf`) and Livia Zaharia (Zenodo
  19487816, CC-BY-4.0, `SIMHIFQTILQ.hard-filtered.vcf.gz`).
- FAQ page `/faq` renders `docs/FAQ.md`.

## VCF quality filtering

`quality_filters` in `modules.yaml` (`pass_filters: ["PASS", "."]`, `min_depth`, `min_qual`; null or 0
disables; absent section = no filtering) is applied in `user_vcf_normalized`. A non-partitioned
`quality_filters_config` asset hashes it, so a change marks normalized partitions stale.

- **Never bypass**: every annotation path reads the normalized parquet, never the raw VCF.
- `RefCall` reference blocks are dropped on purpose.
- `build_quality_filter_expr()` matches column names case-insensitively and casts DP/QUAL to numeric.
- **The caller's verdict first; thresholds judge only what a record states** (`unstated_metrics`,
  default `keep`). `min_depth` reads `DP`, else DRAGEN's `JDP`. A PASS record stating no depth or QUAL
  is judged by FILTER alone: a VCF `.` is unknown, not zero. Before this, `DP >= 10` evaluated to null
  and dropped every call of DRAGEN's RH, GBA, CYP21A2 and CYP2D6 targeted callers (116 in Livia's VCF),
  at exactly the paralogous loci where they beat the small-variant caller. FILTER is never overridden
  (`TargetedConflict` stays dropped). Normalization reports `kept_depth_unstated` /
  `kept_qual_unstated`; the field is in `config_hash`. Tests: `test_quality_filters.py`.
- `sex="Female"` logs a warning for chrY variants but never removes them.

## Dagster pipeline

Architecture and troubleshooting: [docs/DAGSTER_GUIDE.md](docs/DAGSTER_GUIDE.md); first-run config:
[docs/CLEAN_SETUP.md](docs/CLEAN_SETUP.md).

Jobs: `normalize_vcf_job` (auto on upload), `annotate_and_report_job` (default: normalize → HF modules
→ report), `annotate_all_job` (adds Ensembl DuckDB), `annotate_ensembl_only_job`. Ensembl assets
(`user_annotated_vcf`, `user_annotated_vcf_duckdb`) **must** depend on `user_vcf_normalized` and take
`normalized_parquet=`; never re-read the raw VCF.

**Mandatory in every asset and job:**

```python
from just_dna_pipelines.runtime import resource_tracker
from just_dna_pipelines.annotation.utils import resource_summary_hook

with resource_tracker("my_asset", context=context):   # context= or no UI charts
    ...
my_job = define_asset_job(name="my_job", selection=..., hooks={resource_summary_hook})  # a set
```

### Patterns

- Software-defined assets over ops; every asset in `Definitions(assets=[...])`.
- IO managers: reference data → `annotation_cache_io_manager` (`~/.cache/just-dna-pipelines/`); user
  data → `user_asset_io_manager` (`data/output/users/{user}/`). `pl.LazyFrame` assets use
  `PolarsParquetIOManager`; `Path` assets add `"dagster/column_schema": polars_schema_to_table_schema(path)`.
- `sink_parquet`, never `.collect().write_parquet()` on large data. DuckDB for big joins with
  `memory_limit` and `temp_directory`. Limit parallelism with `op_tags={"dagster/concurrency_key": …}`.
- Validation via `@asset_check`, selected with `AssetSelection.checks_for_assets(...)`.
- Dynamic partitions: discovery asset calls `context.instance.add_dynamic_partitions(PARTS.name, keys)`;
  partitioned assets read `context.partition_key`.
- **Ensembl cache**: flat `ensembl_variations/data/homo_sapiens-chr*.parquet`, downloaded by
  `annotation/ensembl_download.py`. `ensembl_annotations` verifies each file against HF size + SHA256
  and re-downloads only mismatches (`.part` then replace; `<file>.sha256` stamps skip rehashing). Never
  revert to "any parquet present, skip" (a damaged file caused `Out of buffer`). Readers glob
  `*.parquet`, never the bare directory. `verify-ensembl` ignores the stamps and rehashes everything.
- **polars-bio**: `scan_vcf` (0.23+) has no `thread_num`; `just_dna_pipelines.io.read_vcf_file` maps it
  to `concurrent_fetches`. Don't read PGEN with it (a hardcoded 512 MB `max_companion_bytes` cap refuses
  the PGS Catalog `.pvar.zst`, polars-bio#453); just-prs stays on `pgenlib`. `pb.write_vcf` writes
  `INFO=.` unless `pb.set_source_metadata(df, format="vcf", header={"info_fields": {...}})` registers each
  field first (`number`, `type`, `description`), and it needs all 8 core columns with `start`/`end` as
  `UInt32` (fill `end = start + 1`, `qual = None`, `filter = "."`).
- **Never `huggingface_hub.snapshot_download`** (duplicates into the HF blob store). Use
  `HfFileSystem(token=get_token())` and `fs.get(remote, local)` file by file.

### Dagster 1.13 API facts

- No `get_dagster_context()`: pass `context`. `context.log.info()` takes no `metadata=`; use
  `context.add_output_metadata()`.
- Run events: `instance.all_logs(run_id, of_type=...)`, not `EventRecordsFilter(run_ids=...)`. Use
  `EventLogEntry.asset_materialization`.
- Timestamps live on `RunRecord` (`instance.get_run_records()`: `start_time`, `end_time`), not
  `DagsterRun`.
- Partition via tags: `create_run_for_job(..., tags={"dagster/partition": pk})`.
- Asset job run config uses the `"ops"` key, not `"assets"`.
- `defs.resolve_job_def(name)`, `defs.resolve_all_asset_specs()`. The `dagster job execute` CLI is out.
- Same `DAGSTER_HOME` for UI and execution.

### Running jobs from the web UI

1. Create the run, then try `instance.submit_run(run_id, workspace=None)` (`_try_submit_to_daemon`
   returns `(ok, error)`; keep logic out of the `except`).
2. On failure (usually "External pipeline origin must be set"), run the job in a **spawned child** via
   `webui.compute.jobs` (`submit_job` / `await_job`, see `execute_job_with_run_discovery`). Never run
   `execute_in_process` in the ASGI process or its threads.
3. Track in-flight runs in `UploadState._active_inproc_runs` so shutdown can cancel them; startup
   cancels orphaned `NOT_STARTED` runs. Manual cleanup: `uv run pipelines cleanup-runs [--status STARTED]
   [--dry-run]`. Fallback runs cannot be re-executed from the Dagster UI.
4. Button state is **per file** (`selected_file_is_running`), never a global `self.running`.

CLI tools may call `job_def.execute_in_process(run_config=..., instance=..., tags=...)` directly, after
adding the dynamic partition if missing.

Anti-patterns: silently falling back to the raw VCF when the normalized parquet is missing (show an
error or a prominent banner); `asyncio.to_thread` with Dagster objects (pyo3 panic `Cannot drop pointer
into Python heap`); run config for unselected assets (validation error); suspended jobs holding DuckDB
file locks; hardcoded asset names (use `defs.resolve_all_asset_specs()`).

## Process model and fork safety (mandatory)

**Never `fork()` a process that has used Polars, polars-bio or DuckDB.** The child inherits the Rayon
pool's latches without its threads and the next parallel op hangs forever, GIL released, SIGKILL only.
Write-up: [docs/GRANIAN_POLARS_FORK_DEADLOCK.md](docs/GRANIAN_POLARS_FORK_DEADLOCK.md).

- `serve()` calls `webui.forksafety.apply_process_model_guards()` **before importing reflex** (pins
  Granian, forces `spawn`, unmutes the fork warning, installs a fork tripwire). Do not remove or reorder.
- All `multiprocessing` passes `multiprocessing.get_context("spawn")` explicitly. Every entry point is
  `__main__`-guarded.
- `POLARS_MAX_THREADS=1` does not help. `run_in_executor` does not make native work safe (pools are
  process-global); use it for blocking I/O only.
- All Polars / DuckDB / polars-bio / Dagster work goes through `webui.compute` (`pool` for short queries,
  `jobs` for runs). The ASGI process only marshals.
- **Grid pages must be O(page)**: sort once to a temp parquet, then slice (a multi-key
  `sort().slice()` re-sorts the whole frame per click). The sort artifact's name includes the source
  path, not just the state class.
- **Ctrl+C**: importing Polars installs a SIGINT handler with `SA_RESTART`, so a blocking `proc.wait()`
  never sees `KeyboardInterrupt`. Call `just_dna_lite.process.install_launcher_signal_handlers` before
  any wait on a child (first signal interrupts, second force-kills; SIGTERM and Ctrl+Z share the path).
  Tests: `tests/test_launcher_shutdown.py`, `tests/test_process_shutdown.py`.

## Reflex UI

Visual design: [docs/DESIGN.md](docs/DESIGN.md) ("chunky and tactile", Fomantic classes, flexbox
layouts, icons ≥2rem, semantic colours `success`/`error`/`info` for benign/pathogenic/VUS).

**Verify UI changes**: watch the running app's terminal for `ImportError`, `AttributeError`,
`Invalid icon tag` or tracebacks during compile, wait for "Compiling: 100%", then check
http://localhost:3000 renders and responds. `Killing worker-0 after it refused to gracefully stop`
during hot reload is harmless. After PRS/Compare changes, restart: hot reload can pair old
`annotate.py` with new state.

### Rules

- **Anything over ~1 s is `@rx.event(background=True)`** with brief `async with self:` blocks and the
  work in a pure function off the state lock; snapshot the inputs into locals in the first block. A
  `yield` generator holds the lock for its whole run and freezes the UI. `@rx.background` does not exist.
- **Upload / select-file handlers return `list[EventSpec]`, never `yield` them.** Reflex 0.9 marks the
  generator's `EventFuture` done when it exhausts, and a yielded EventSpec re-dispatched after that
  raises `Cannot add a child to an EventFuture that is already done`. Same rule as `poll_run_status`.
- **Icons**: use `fomantic_icon()` from `webui.components.layout`, not `rx.icon()`. Names must be static
  strings (switch with `rx.match`). Fomantic names are space-separated (`arrow up`); the helper maps
  common hyphenated Lucide names, in the order `circle-check`, `heart-pulse` (never underscores).
- Reactive styling via `rx.cond`, never a Python `if`. `class_name`, never `class`.
- `rx.foreach` dict values are `Any`: cast with `.to(int)` / `.to(bool)`.
- Per-row UI state (e.g. a busy button) is a bool stamped on the row (`item["busy"].to(bool)`), not a
  comparison of a global var to the item. Don't blanket `disabled=` primary buttons (looks pressed).
- `_underscore` vars never reach the client: a remount `key=` must be public (`form_key`). Reset uploads
  with `rx.clear_selected_files(...)` and don't debounce those setters.
- Fomantic: segments, buttons, labels, dividers, messages and `top attached tabular menu` +
  `bottom attached segment` tabs (state-toggled `active item`, content via `rx.match`) work. `ui grid`,
  `ui fixed menu` and accordions don't: use flexbox. Checkboxes need the Fomantic
  `div.ui.checkbox > input + label` structure, not `rx.checkbox`.
- **SSR is on only when the prerender runs in bun** (`rxconfig._ssr_build_runs_under_bun`): bun
  present **and no `node` on PATH**. `@mui/x-data-grid` imports its own `.css`, which Node's ESM
  loader rejects, so a Node prerender fails every route with a 500. `react-router`'s shebang is
  `env node`, so bun runs Node whenever Node exists; "bun installed" is not the test. `reflex export`
  fixes SSR before loading `rxconfig`, so test the gate with `uv run serve`.
- Custom routes: pass a FastAPI app as `rx.App(api_transformer=api)`. They are served by the **backend**
  only. Never hardcode port 8000: `webui.run` picks a free port into `API_URL` / `REFLEX_BACKEND_PORT`;
  `webui/deployment_urls.py` builds the browser URL (`PUBLIC_BACKEND_URL` overrides `API_URL`);
  `backend_api_url` never returns `""`.

## PRS (`just-prs>=0.10.0`, `prs-ui>=0.3.16`)

`PRSState(PRSComputeStateMixin, LazyFrameGridMixin, rx.State)` is independent of `UploadState` (own grid
mixin; a substate would clash in the MRO) and defines `genome_build`, `cache_dir`, `status_message`
itself. Genome build: `GRCh38`/`T2T-CHM13v2.0` → `GRCh38`; `GRCh37`/`hg19` → `GRCh37`. Only GRCh38 is
fully supported. A GRCh37 sample scores against the PGS Catalog's **harmonized** scoring files for that
build; the VCF itself is never lifted over. `just_prs.liftover` is not a VCF liftover and cannot be
reused for annotation.

- **Genotypes**: `initialize_prs_for_file(parquet_path, genome_build)` calls
  `set_prs_genotypes_lf(pl.scan_parquet(path))`. Normalized parquets keep polars-bio `start`; just-prs wants `pos`. Always go through
  `_get_genotypes_lf()` / `_scan_prs_genotypes()`; never feed a raw `scan_parquet` to
  `infer_sample_ancestry` or `compute_prs`. Never pass a LazyFrame between states; rescan the path.
- **Everything PRS is per genome.** `UploadState.select_file()` resets Output/PRS/trait grid views
  (`SafeGridMixin.reset_grid_view_state`) **before** changing `selected_file`, then calls
  `PRSState.reset_for_genome_switch`, even while the new parquet is still normalizing. Clear
  `prs_results`, the chart spec and `prs_results_source_file`; compute snapshots `prs_compute_token` and
  discards stale writes. After updating `prs_results`, rebuild `prs_results_rows` / `_columns` /
  `_column_groups`. Switching the file also clears the comparison.
- **Annotations and reports are per sample** (`data/output/users/{user}/{sample}/`). `select_file`
  clears `output_files` / `report_files` at once; the background loader publishes only when
  `outputs_loaded_for_file == selected_file`, and tab badges and empty states read those gated lists.
- The right-panel workspace is keyed on `UploadState.selected_file`: remount the whole sample tree, never
  keep per-genome widgets.
- Use the prs-ui workbench (`prs_workbench_mode_panel`, `trait_selector`, `prs_scores_selector`), with
  ancestry on the current-sample row. No second upload, no toolbar population selector. **Add for
  comparison** adds a left-panel peer (same species, build, ready parquet) in one click, labelled
  `Sample Name (filename)`. Compute stays on `PRSState`; `PRSTraitState` only selects traits and syncs
  PGS IDs. Comparisons are not checkpointed to Dagster.
- By Trait groups with prs-ui's `trait_group_by`. Search and a contains-filter on either trait column
  match **both** the mapped and the reported name (`trait_search`), and longevity / lifespan / life span
  rows also match age, aging and ageing (`_AGING_SEARCH_TOKEN`, whole words, so "imaging" stays out).
  `PRSTraitState.load_traits` passes `eager_value_options_row_limit=0`, like prs-ui.
- Pass `normalizing=False` to the workbench, **never** `UploadState.vcf_preview_loading` (it locks the
  grids while the Input tab pages). The By PRS extract comes from the mixin; don't reimplement it.

## Tests

- Real data, ground truth computed at test time; fixed seeds; run `pytest -vvv`. New markdown goes in
  `docs/`.
- Assert relationships: set equality over counts, input vs output counts, join cardinality and nulls,
  round trips. Domain constants from a spec are fine; counts copied from data inspection are not.
- Include negative, boundary, null, unicode and malformed cases. Use `xfail` with a reason for known
  data issues.
- Parametrize instead of copying; delete tests another test fully covers.
- **Never claim a test would have caught a bug without running it against the buggy code** and showing
  it fail, then pass on the fix.
- Avoid existence-only asserts (`len(df) > 0`) as the sole check, and mocking transformations instead of
  running them.

## Writing preferences

- User docs: images on top, caveats after Quick Start, short jargon-free intros; details go in `docs/`.
- Natural prose: no em-dashes, filler transitions or marketing voice. Never invent documentation.
- Don't overpromise: GRCh37, T2T, microarray/23andMe and ROGEN results are planned, not done. GRCh37
  is "done, not done": PRS works through the Catalog's per-build harmonized scores, but annotation is
  GRCh38-only because no VCF liftover exists. Never write "liftover support added". The tool
  annotates an existing VCF by joining it against module databases; it does not call variants or draw
  gene-disease inferences (bioRxiv/medRxiv rejected the preprint on that point; it is on arXiv, framed
  as a methods/software paper).
- Global framing, not EU-only; EHDS is one example among many.
- Workshop proposals: written for organizers; "instructor", not "facilitator"; no manifesto tone; no
  "neat"/"slippery"/"primer"; separate "will get" from "will not get"; Roman numerals for generations.
- Update related docs (this file, `docs/DAGSTER_GUIDE.md`) in the same change as the code.
- For upstream bugs (e.g. `prs-ui`), prefer a copy-paste upstream prompt over a local patch.
- When given a minimal working example, wire it in directly.
- Output filenames describe content (`_ensembl_annotated.parquet`); reports are timestamped.
- CLI commands are uv workspace `[project.scripts]`, not `subprocess` wrappers. Data access goes through
  fsspec, not symlinks.

## Workspace facts

- Related repos: `just-prs` (read-only here), `reflex-mui-datagrid`, `just-biomarkers`, `dna-seq`,
  `prepare-annotations`.
- Runs on Linux, macOS (incl. Apple Silicon) and native Windows (`windows/` scripts). Nix:
  `nix develop`, `uv sync`, `uv run start`.
- The AI Module Creator uses Agno and can target OpenAI-compatible local models (Ollama, vLLM).
- README images live in `images/`; use `<img>` inside HTML `<div>` blocks.
- Load `.env` with `runtime.load_env()` before reading `JUST_DNA_PIPELINES_CACHE_DIR` or
  `JUST_DNA_PIPELINES_OUTPUT_DIR`, **never a bare `load_dotenv()`**: it climbs past the checkout and read
  another project's `~/sources/.env` (its `DEPLOY_URL` ended up in every report link). `load_env` stops at
  the workspace root (`find_workspace_root`, `$JUST_DNA_PIPELINES_ROOT` first) and falls back to
  `.env.template`. just-dna-registry calls a bare `load_dotenv()` on import, so every
  `import just_dna_registry…` sits inside `with environ_guard():`, after `load_env()`. Tests:
  `tests/test_load_env_bounded.py`.
- `just-dna-seq/annotators` on HuggingFace hosts ten modules, all publishing a
  `manifest.json` (see `docs/V1_PARITY.md`).
- Container: no GHCR image yet; `compose.yaml` builds locally. The `Containerfile` needs
  `chmod -R 777 .venv` (rootless Podman) and `UV_FROZEN=1`. Workshops live in `docs/workshops/`. Keep
  pytest in root dev dependencies. There is no `uv bundle`.
