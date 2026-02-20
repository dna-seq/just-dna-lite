# AI Module Creation

## Vision

Annotation modules in just-dna-lite are **curated SNP filter sets**: a geneticist selects
variants, assigns per-genotype weights/states/conclusions, links literature evidence, and
packages everything as three parquet tables (`weights`, `annotations`, `studies`).

This is labour-intensive but structurally simple — the perfect target for AI assistance.

**Goal**: an agentic pipeline that turns *arbitrary input* (research article, CSV dump,
free-text panel description) into a valid, deployable annotation module.

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  Arbitrary   │      │   Module     │      │   Parquet    │      │  Registered  │
│   Input      │─────▶│   Spec (DSL) │─────▶│   Module     │─────▶│  & Live in   │
│  (article,   │  AI  │  YAML + CSV  │ Det. │  weights/    │ Reg. │  UI + CLI    │
│   CSV, md)   │ Agent│              │Compil│  annotations/│ istry│              │
└──────────────┘      └──────────────┘  er  │  studies     │      └──────────────┘
                                            └──────────────┘
```

The chain has three parts:

| Part | Input → Output | Nature |
|------|---------------|--------|
| **Agent (Geneticist)** | Arbitrary text → Module Spec | Creative, AI-driven |
| **Compiler** | Module Spec → Parquet | Deterministic, tested |
| **Registry** | Parquet → Live module | Automatic (persists to modules.yaml, refreshes discovery) |

The compiler and registry are tools the agent calls to validate, build, and deploy its output — fast feedback loop.

---

## DSL Format: Module Spec

A module spec is a directory containing:

```
my_module/
├── module_spec.yaml   # metadata + settings
├── variants.csv       # weights + annotations (combined)
└── studies.csv        # literature evidence (optional)
```

### `module_spec.yaml`

```yaml
schema_version: "1.0"

module:
  name: my_module                       # machine name, lowercase, underscores
  title: "My Module"                    # human-readable title
  description: "What this module does"  # one-liner
  report_title: "Report Section Title"  # title in PDF/HTML reports
  icon: heart-pulse                     # Fomantic UI icon name
  color: "#21ba45"                      # hex color for UI

defaults:
  curator: ai-module-creator            # default curator for all rows
  method: literature-review             # default annotation method
  priority: medium                      # default priority

genome_build: GRCh38                    # reference genome (positions must match)
```

### `variants.csv`

One row per **(rsid, genotype)** combination. Combines weights + annotation data.

| Column | Required | Type | Description |
|--------|----------|------|-------------|
| `rsid` | yes | string | dbSNP ID, e.g. `rs1801133` |
| `chrom` | no* | string | Chromosome without "chr" prefix, e.g. `1` |
| `start` | no* | int | 1-based genomic position (GRCh38) |
| `ref` | no* | string | Reference allele |
| `alts` | no* | string | Alt allele(s), comma-separated if multiple |
| `genotype` | yes | string | Slash-separated sorted alleles, e.g. `A/G` |
| `weight` | yes | float | Annotation score (positive = protective, negative = risk) |
| `state` | yes | string | One of: `risk`, `protective`, `neutral`, `significant`, `alt`, `ref` |
| `conclusion` | yes | string | Human-readable interpretation for this genotype |
| `priority` | no | string | Priority level (overrides default) |
| `gene` | yes | string | Gene symbol, e.g. `MTHFR` |
| `phenotype` | yes | string | Associated trait/phenotype |
| `category` | yes | string | Grouping category within module |
| `clinvar` | no | bool | Is this variant in ClinVar? |
| `pathogenic` | no | bool | ClinVar pathogenic flag |
| `benign` | no | bool | ClinVar benign flag |
| `curator` | no | string | Overrides default curator |
| `method` | no | string | Overrides default method |

**\* Position columns** (`chrom`, `start`, `ref`, `alts`) can be omitted if the compiler
has rsid resolution enabled. The compiler resolves them from dbSNP. If provided, they're
used as-is (faster, no network call).

**Genotype convention**: alleles are alphabetically sorted and slash-separated.
`A/G` not `G/A`. Homozygous: `T/T`. The compiler normalizes to `List[String]` for parquet.

### `studies.csv`

One row per **(rsid, pmid)** combination.

| Column | Required | Type | Description |
|--------|----------|------|-------------|
| `rsid` | yes | string | dbSNP ID |
| `pmid` | yes | string | PubMed ID (digits only) |
| `population` | no | string | Study population, e.g. `European` |
| `p_value` | no | string | Statistical significance, e.g. `<0.001` |
| `conclusion` | yes | string | Study-specific conclusion |
| `study_design` | no | string | e.g. `meta-analysis`, `GWAS`, `case-control` |

---

## Compiler: Spec → Parquet

The compiler is a deterministic Python function (no AI). It:

1. **Validates** the spec (Pydantic models, required columns, value ranges)
2. **Resolves** missing positions via rsid lookup (optional, requires Ensembl DuckDB)
3. **Normalizes** genotypes (`"A/G"` → `["A", "G"]`), chromosomes, types
4. **Splits** variants.csv into `weights.parquet` + `annotations.parquet`
5. **Writes** `studies.parquet` from studies.csv
6. **Validates** output against the existing pipeline's schema expectations

### Split logic (variants.csv → two parquet tables)

```
variants.csv
    │
    ├──▶ weights.parquet
    │      columns: rsid, chrom, start, ref, alts, genotype, weight,
    │               state, conclusion, priority, module, curator, method,
    │               clinvar, pathogenic, benign, likely_pathogenic, likely_benign
    │
    └──▶ annotations.parquet
           columns: rsid, gene, phenotype, category
           (deduplicated — one row per unique rsid)
```

### Compiler output structure

```
output/my_module/
├── weights.parquet
├── annotations.parquet
└── studies.parquet
```

This is directly compatible with the existing module discovery system — drop it into
any configured source and it's auto-discovered.

---

## Agent Hooks — Python API & CLI

The module registry exposes a complete API for programmatic module management.
An AI agent that produces DSL spec files can compile, register, validate, and
remove modules without any manual steps.

### Python API (`just_dna_pipelines.module_registry`)

All functions are importable from `just_dna_pipelines.module_registry`:

```python
from just_dna_pipelines.module_registry import (
    validate_module_spec,     # dry-run validation (no side effects)
    register_custom_module,   # compile + register + refresh
    unregister_custom_module, # remove + refresh
    list_custom_modules,      # names of custom modules on disk
    get_custom_module_specs,  # {name: output_dir} dict
    refresh_module_registry,  # reload modules.yaml + rediscover
    CUSTOM_MODULES_DIR,       # Path to compiled custom modules
)
```

| Function | Input | Output | Side effects |
|----------|-------|--------|-------------|
| `validate_module_spec(spec_dir)` | Path to spec folder | `ValidationResult` (.valid, .errors, .warnings, .stats) | None |
| `register_custom_module(spec_dir)` | Path to spec folder | `CompilationResult` (.success, .errors, .stats, .output_dir) | Writes parquet, updates modules.yaml, refreshes globals |
| `unregister_custom_module(name)` | Module machine name | `bool` (True if removed) | Deletes parquet, updates modules.yaml, refreshes globals |
| `list_custom_modules()` | — | `List[str]` of names | None |
| `get_custom_module_specs()` | — | `Dict[str, Path]` | None |
| `refresh_module_registry()` | — | `List[str]` of all modules | Reloads config, re-discovers modules |

### Agent workflow (recommended)

```python
from pathlib import Path
from just_dna_pipelines.module_registry import validate_module_spec, register_custom_module

spec_dir = Path("data/module_specs/my_panel/")

# 1. Write module_spec.yaml + variants.csv + studies.csv to spec_dir
#    (agent creates these files)

# 2. Validate (dry-run, no side effects)
validation = validate_module_spec(spec_dir)
if not validation.valid:
    # Fix errors and retry
    print(validation.errors)

# 3. Register (compile + persist + refresh — module is immediately live)
result = register_custom_module(spec_dir)
if result.success:
    print(f"Module registered: {result.stats['module_name']}")
    print(f"  Variants: {result.stats['weights_rows']}")
    print(f"  Output:   {result.output_dir}")
else:
    print(f"Failed: {result.errors}")
```

### CLI (`uv run pipelines module ...`)

```bash
# Validate a spec (no side effects)
uv run pipelines module validate data/module_specs/my_panel/

# Compile + register in one step (equivalent to UI "Add" button)
uv run pipelines module register data/module_specs/my_panel/

# Remove a custom module (equivalent to UI "Remove" button)
uv run pipelines module unregister my_panel

# List custom modules on disk
uv run pipelines module list-custom

# Compile only (writes parquet but does NOT register in modules.yaml)
uv run pipelines module compile data/module_specs/my_panel/ -o data/output/modules/my_panel/
```

### What happens on `register`

1. **Validates** the spec (Pydantic models, CSV rows, cross-row checks)
2. **Compiles** to parquet in `data/output/modules/<module_name>/`
3. **Ensures** a local collection source for `data/output/modules/` exists in `modules.yaml`
4. **Adds** display metadata (title, description, icon, color) from `module_spec.yaml` to `modules.yaml`
5. **Refreshes** the in-memory module discovery (`MODULE_INFOS`, `DISCOVERED_MODULES`)
6. Module is **immediately selectable** in the web UI and CLI without restart

### What happens on `unregister`

1. **Deletes** the parquet directory `data/output/modules/<module_name>/`
2. **Removes** display metadata from `modules.yaml`
3. If no custom modules remain, **removes** the local collection source from `modules.yaml`
4. **Refreshes** in-memory discovery

### Idempotency

`register_custom_module` is idempotent — calling it again for the same spec overwrites
the existing parquet and refreshes metadata. This enables iterative development:
edit the DSL spec, re-register, check annotation results, repeat.

---

## Agent Design (Agno)

### Architecture

```
┌────────────────────────────────────────────┐
│              Module Creator Agent           │
│                                            │
│  System prompt: geneticist persona         │
│  Model: GPT-4o / Claude                    │
│                                            │
│  Tools:                                    │
│  ├─ validate_module_spec → dry-run check   │
│  ├─ register_custom_module → deploy module │
│  ├─ lookup_rsid     → dbSNP/Ensembl info   │
│  ├─ search_pubmed   → find PMIDs           │
│  └─ diff_modules    → compare with ref     │
│                                            │
│  Output: module_spec.yaml + CSVs           │
└────────────────────────────────────────────┘
```

### Agent workflow

1. Parse input (article, CSV, free text)
2. Identify relevant genes and variants
3. For each variant, look up rsid details (position, ref/alt alleles)
4. Assign per-genotype weights, states, and conclusions
5. Find supporting PubMed references
6. Write `module_spec.yaml` + `variants.csv` + `studies.csv` to a spec directory
7. Call `validate_module_spec(spec_dir)` to check for errors
8. If errors → fix files and re-validate (loop)
9. Call `register_custom_module(spec_dir)` to compile + deploy
10. Module is live — can be used for annotation immediately

### Agent tools (Agno tool functions)

| Tool | Input | Output | Side effects |
|------|-------|--------|-------------|
| `validate_module_spec` | spec directory path | ValidationResult (valid/errors/warnings/stats) | None |
| `register_custom_module` | spec dir | CompilationResult (success/errors/stats/output_dir) | Writes parquet, updates modules.yaml |
| `unregister_custom_module` | module name | bool | Deletes parquet, updates modules.yaml |
| `lookup_rsid` | rsid string | position, ref, alts, gene, frequency | Network call to dbSNP |
| `search_pubmed` | query string | list of (pmid, title, abstract) | Network call to NCBI |
| `diff_modules` | compiled dir + reference dir | column-by-column diff | Reads parquet |

---

## Phases

### Phase 1: DSL Schema ✅
**Deliverable**: `just_dna_pipelines/module_compiler/models.py`

- Pydantic 2 models for `ModuleSpecConfig`, `VariantRow`, `StudyRow`
- CSV reader/validator
- YAML reader/validator
- Unit tests for validation (malformed inputs, missing columns, bad genotypes)

### Phase 2: Reverse-Engineer Existing Module ✅
**Deliverable**: `data/module_specs/vo2max/`

- Read vo2max weights/annotations/studies from HuggingFace
- Generate `module_spec.yaml`, `variants.csv`, `studies.csv`
- This proves the DSL can represent real modules

### Phase 3: Compiler ✅
**Deliverable**: `just_dna_pipelines/module_compiler/compiler.py`

- `validate_spec(spec_dir) → ValidationResult`
- `compile_module(spec_dir, output_dir) → CompilationResult`
- rsid resolution via Ensembl DuckDB
- Typer CLI commands: `module validate`, `module compile`

### Phase 4: Round-Trip Test ✅
**Deliverable**: `tests/test_module_compiler.py`

- `existing_module → reverse → DSL → compile → diff → zero`
- Validates the full chain is lossless
- Uses vo2max as the reference module

### Phase 5: Custom Module Registry ✅
**Deliverable**: Module registry API + Web UI + CLI for managing custom modules

- **`module_registry.py`**: Central API — `validate_module_spec`, `register_custom_module`, `unregister_custom_module`, `list_custom_modules`, `refresh_module_registry`
- **Web UI**: Multi-file upload (module_spec.yaml + CSVs), "Remove" button on custom modules, live source display with module count
- **CLI**: `module register`, `module unregister`, `module list-custom`
- **Persistence**: Changes written to project-root `modules.yaml` (sources + display metadata)
- **Discovery refresh**: In-memory `MODULE_INFOS`/`DISCOVERED_MODULES` mutated in-place so Reflex UI and CLI reflect changes without restart
- **Agent hooks**: Python API documented for programmatic use (see above)

### Phase 6: Agno Agent ✅
**Deliverable**: `just_dna_pipelines/agents/module_creator.py` + `module_creator.yaml`

- Declarative agent spec in YAML (system prompt, model config, agent settings)
- Gemini 3 Pro via Agno (`agno.models.google.Gemini`, `vertexai=False`)
- Tool wrappers: `write_spec_files`, `validate_spec`, `register_module`
- CLI: `uv run pipelines agent create-module --file input.md`
- Smoke test passes: mthfr_nad eval → 24 rows, 8 rsids, VALID

### Phase 7 + 8: BioContext KB MCP ✅
**Deliverable**: External biomedical knowledge via hosted MCP server

Both variant lookup and literature search are solved by a single hosted MCP:
**BioContext KB** (`https://biocontext-kb.fastmcp.app/mcp`), integrated via
Agno's `MCPTools(url=...)`.

Available databases: Ensembl, EuropePMC, UniProt, Open Targets, Reactome,
Human Protein Atlas, KEGG, ClinicalTrials.gov, AlphaFold, InterPro, OLS,
STRINGDb, Antibody Registry, PanglaoDb, PRIDE, Drugs@openFDA, bioRxiv,
Google Scholar, grants.gov.

Covers both original phase goals:
- **Variant Recoder / rsid lookup** → Ensembl tools in BioContext KB
- **PubMed / literature search** → EuropePMC tools in BioContext KB

Plus additional capabilities (protein function via UniProt, pathways via
Reactome/KEGG, clinical evidence via Open Targets/ClinicalTrials.gov) that
improve module quality without any custom server code.

**Caution**: STRING responses are very large context consumers — the agent
prompt instructs to prefer UniProt/Reactome over STRINGDb and to use all
external tool calls with moderation (only when genuinely needed).

### Phase 9: Eval & Iteration ✎
**Deliverable**: Pass rate on eval set

- Run agent on freeform test inputs (CYP panel, MTHFR/NAD panel)
- Compare agent output DSL to hand-crafted reference DSL
- Measure: schema validity, variant coverage, weight directionality, study relevance
- Iterate on system prompt and tool design

### Phase 10: Per-Module Report Enhancement (deferred)
**Deliverable**: Category-grouped reports for all modules

Custom modules already appear in the combined longevity report as flat tables (the
existing `build_module_report_data()` + "Other Modules" template section handles them).
This works well enough for now. Future enhancement:

- Extend DSL with optional `categories:` section in `module_spec.yaml` for
  per-category titles and descriptions (like longevity pathway categories)
- Compiler outputs `metadata.json` alongside parquets with category metadata
- `build_module_report_data()` auto-groups by `category` column using metadata
  for titles/descriptions, falling back to titlecased category names
- Unify the longevity-specific and generic template paths so all modules get
  the same category-grouped rendering
- Longevity pathway categories (`LONGEVITY_CATEGORIES` dict) become just the
  default metadata for the `longevitymap` module, not a special case

---

## Eval Test Inputs

Two reference panels serve as agent evaluation cases. Each has:
- **Freeform input**: what a user/geneticist would provide (natural language)
- **Reference DSL**: the expected structured output

See:
- `data/module_specs/evals/cyp_panel/` — Pharmacogenomics CYP panel
- `data/module_specs/evals/mthfr_nad/` — Methylation & NAD+ metabolism panel

### Evaluation criteria

| Criterion | Weight | What to check |
|-----------|--------|---------------|
| Schema validity | Must pass | Compiler validates without errors |
| Variant coverage | High | All key rsids from input are present |
| Genotype completeness | High | All clinically relevant genotypes covered per rsid |
| Weight directionality | High | risk = negative, protective = positive (or justified) |
| State correctness | Medium | States match clinical consensus |
| Conclusion quality | Medium | Accurate, informative, no hallucinated claims |
| Study references | Medium | PMIDs are real and relevant |
| Gene/phenotype accuracy | High | Correct gene symbols and phenotype descriptions |
