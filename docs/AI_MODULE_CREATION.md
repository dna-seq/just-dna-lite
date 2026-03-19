# AI Module Creation

## Vision

Annotation modules in just-dna-lite are curated SNP filter sets: a geneticist selects
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

### Package layout

```
just-dna-pipelines/src/just_dna_pipelines/module_compiler/
├── __init__.py      # Public API re-exports
├── models.py        # Pydantic 2 models (DSL schema + result types)
├── compiler.py      # validate_spec() + compile_module()
└── cli.py           # Typer commands (module validate, module compile)
```

### Compilation pipeline

**Validation** runs before any output is written. Errors are collected and returned as a list.

Field-level (Pydantic): `rsid` matches `^rs\d+$`, `genotype` is alphabetically sorted slash-separated alleles, `state` is one of six valid enum values, `chrom` is 1-22/X/Y/MT, `pmid` is digits-only, `module.name` is lowercase alphanumeric + underscores.

Cross-row: positional consistency (all rows for the same rsid share chrom/start), uniqueness of (rsid, genotype) and (rsid, pmid) pairs, and study rsid coverage warnings.

Directional warnings (not errors): `state=risk` with positive weight, `state=protective` with negative weight.

### Validation vs compilation

| | `validate_spec()` | `compile_module()` |
|-|--------------------|--------------------|
| **Side effects** | None | Writes parquet files |
| **On error** | `valid=False` + error list | `success=False` + error list |

`compile_module` calls `validate_spec` internally — if validation fails, no output is produced.

### Design decisions

CSV is read via stdlib `csv.DictReader` (not Polars) because the `conclusion` field contains commas, quotes, and long text that Polars CSV inference can misparse. Each row is validated through Pydantic before being collected into a DataFrame.

Validation collects all errors, never raises. When used as agent tools, the caller needs a complete error list to fix all issues in one pass.

`annotations.parquet` has one row per rsid. When the same rsid appears with multiple genotypes, the first row's gene/phenotype/category wins. This matches the pipeline's expectation that annotations are variant-level, not genotype-level.

---

## Module Registry — Python API & CLI

The module registry exposes a complete API for programmatic module management.

### Python API (`just_dna_pipelines.module_registry`)

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
| `refresh_module_registry()` | — | `List[str]` of all modules | Reloads config, re-discovers modules |

### CLI (`uv run pipelines module ...`)

```bash
uv run pipelines module validate data/module_specs/my_panel/
uv run pipelines module register data/module_specs/my_panel/
uv run pipelines module unregister my_panel
uv run pipelines module list-custom
uv run pipelines module compile data/module_specs/my_panel/ -o data/output/modules/my_panel/
```

### What happens on `register`

1. Validates the spec (Pydantic models, CSV rows, cross-row checks)
2. Compiles to parquet in `data/output/modules/<module_name>/`
3. Ensures a local collection source for `data/output/modules/` exists in `modules.yaml`
4. Adds display metadata (title, description, icon, color) from `module_spec.yaml` to `modules.yaml`
5. Refreshes in-memory module discovery (`MODULE_INFOS`, `DISCOVERED_MODULES`)
6. Module is immediately selectable in the web UI and CLI without restart

`register_custom_module` is idempotent — calling it again for the same spec overwrites
the existing parquet and refreshes metadata. This enables iterative development:
edit the DSL spec, re-register, check annotation results, repeat.

---

## Agent Design (Agno)

### Solo mode

```
┌────────────────────────────────────────────┐
│              Module Creator Agent           │
│                                            │
│  System prompt: geneticist persona         │
│  Model: Gemini Pro                         │
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

Workflow: parse input → identify variants → look up rsid details → assign per-genotype weights → find PubMed references → write spec files → validate → fix errors (loop up to 10 iterations) → register → module is live.

### Team mode (research swarm)

The team has 3–5 agents depending on which API keys are configured:

| Agent | Role | Model |
|-------|------|-------|
| PI (Principal Investigator) | Coordinator. Delegates tasks, synthesizes consensus, writes final module. | Gemini Pro |
| Researcher 1 | Independent variant research via BioContext MCP. Always present. | Gemini Pro |
| Researcher 2 | Same role, different LLM for diversity. Present if `OPENAI_API_KEY` is set. | GPT |
| Researcher 3 | Same role, third perspective. Present if `ANTHROPIC_API_KEY` is set. | Claude Sonnet |
| Reviewer | Quality review: variant integrity, provenance, weight consistency, PMID validity. | Gemini Flash |

Team flow: PI delegates research to all Researchers in parallel → each returns a variant list → PI synthesizes consensus (variants confirmed by ≥2 researchers are included, weight disagreements use median) → PI sends draft to Reviewer → Reviewer returns ERRORS/WARNINGS/OK → PI fixes errors → writes and registers module.

There are no human-approve/reject steps between phases. The PI orchestrates end-to-end. After completion, the user reviews the module in the editing slot and can iterate via chat.

### BioContext KB MCP

Variant lookup and literature search use a hosted MCP server: BioContext KB (`https://biocontext-kb.fastmcp.app/mcp`), integrated via Agno's `MCPTools(url=...)`.

Available databases: Ensembl, EuropePMC, UniProt, Open Targets, Reactome, Human Protein Atlas, KEGG, ClinicalTrials.gov, AlphaFold, InterPro, OLS, STRINGDb, bioRxiv, Google Scholar.

### Limitations

- Max 5 file attachments per message (PDF, CSV, Markdown, plain text)
- Each Researcher is limited to 9 tool calls to prevent context overflow
- No human-in-the-loop between agent phases
- Gemini key is required; OpenAI and Anthropic keys are optional (add researchers)
- Only GRCh38 and GRCh37 genome builds
- Only SNPs/indels (no structural or copy-number variants)
- No persistent audit trail across page reloads

---

## How modules are discovered and loaded

1. Configuration is read from `modules.yaml` at project root (or fallback inside the package)
2. `discover_all_modules()` iterates over all configured sources
3. For each source, the loader checks the protocol: `hf://` → HuggingFace, `github://` → GitHub, `s3://` → S3, `https://` → HTTP, `/absolute/path` → local filesystem
4. Auto-detection: if `weights.parquet` exists at root → single module; otherwise scan subfolders for a collection
5. Results stored in `MODULE_INFOS` and `DISCOVERED_MODULES` globals, populated at import time
6. `refresh_modules()` re-reads config and re-discovers without process restart

Modules are pure data (YAML + CSV). They have no Python dependencies. The annotation engine loads modules via Polars LazyFrame — no module code is executed. The pipeline joins `weights.parquet` against the normalized VCF using rsid or position matching and appends annotation columns.

### Minimal "Hello World" module

`module_spec.yaml`:
```yaml
schema_version: "1.0"
module:
  name: hello_world
  version: 1
  title: "Hello World"
  description: "Minimal example module with one variant."
  report_title: "Hello World Annotations"
  icon: dna
  color: "#21ba45"
defaults:
  curator: human
  method: literature-review
  priority: low
genome_build: GRCh38
```

`variants.csv`:
```csv
rsid,genotype,weight,state,conclusion,gene,phenotype,category
rs1801133,C/C,0,neutral,"Typical MTHFR activity.",MTHFR,Metabolism,Example
rs1801133,C/T,-0.6,risk,"Reduced MTHFR activity.",MTHFR,Metabolism,Example
rs1801133,T/T,-1.1,risk,"Severely reduced MTHFR activity.",MTHFR,Metabolism,Example
```

Register via web UI (upload files → click Register) or CLI (`uv run pipelines module register path/to/spec/`).

---

## Eval test inputs

Two reference panels serve as agent evaluation cases:
- `data/module_specs/evals/cyp_panel/` — Pharmacogenomics CYP panel
- `data/module_specs/evals/mthfr_nad/` — Methylation & NAD+ metabolism panel

Evaluation criteria: schema validity (must pass), variant coverage, genotype completeness, weight directionality (risk=negative, protective=positive), state correctness, conclusion quality, study reference validity, gene/phenotype accuracy.

---

## Implementation status

All phases are complete: DSL schema, reverse-engineering existing modules, compiler, round-trip testing, custom module registry (API + Web UI + CLI), Agno agent (solo + team), BioContext KB MCP integration. Remaining work: eval iteration on test inputs (Phase 9) and per-module report enhancement (Phase 10, deferred).
