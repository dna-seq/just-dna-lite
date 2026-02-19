# AI Module Creation — Roadmap

## Vision

Annotation modules in just-dna-lite are **curated SNP filter sets**: a geneticist selects
variants, assigns per-genotype weights/states/conclusions, links literature evidence, and
packages everything as three parquet tables (`weights`, `annotations`, `studies`).

This is labour-intensive but structurally simple — the perfect target for AI assistance.

**Goal**: an agentic pipeline that turns *arbitrary input* (research article, CSV dump,
free-text panel description) into a valid, deployable annotation module.

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  Arbitrary   │      │   Module     │      │   Parquet    │
│   Input      │─────▶│   Spec (DSL) │─────▶│   Module     │
│  (article,   │  AI  │  YAML + CSV  │ Det. │  weights/    │
│   CSV, md)   │ Agent│              │Compil│  annotations/│
└──────────────┘      └──────────────┘  er  │  studies     │
                                            └──────────────┘
```

The chain has two halves:

| Half | Input → Output | Nature |
|------|---------------|--------|
| **Agent (Geneticist)** | Arbitrary text → Module Spec | Creative, AI-driven |
| **Compiler** | Module Spec → Parquet | Deterministic, tested |

The compiler is a tool the agent calls to validate and build its output — fast feedback loop.

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
2. **Resolves** missing positions via rsid lookup (optional, requires network)
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

### Compiler CLI

```bash
# Validate only (no output)
uv run pipelines module-validate data/module_specs/my_module/

# Compile to parquet
uv run pipelines module-compile data/module_specs/my_module/ --output data/output/modules/my_module/

# Round-trip test: compile and diff against existing module
uv run pipelines module-diff data/module_specs/vo2max/ --reference hf://datasets/just-dna-seq/annotators/data/vo2max/
```

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
│  ├─ validate_spec   → run compiler check   │
│  ├─ compile_module  → build parquet        │
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
6. Write module_spec.yaml + variants.csv + studies.csv
7. Call `validate_spec` to check for errors
8. If errors → fix and re-validate (loop)
9. Call `compile_module` to produce parquet
10. Return the compiled module

### Agent tools (Agno tool functions)

| Tool | Input | Output | Side effects |
|------|-------|--------|-------------|
| `validate_spec` | spec directory path | validation result (ok / errors list) | None |
| `compile_module` | spec dir + output dir | compilation result + stats | Writes parquet files |
| `lookup_rsid` | rsid string | position, ref, alts, gene, frequency | Network call to dbSNP |
| `search_pubmed` | query string | list of (pmid, title, abstract) | Network call to NCBI |
| `diff_modules` | compiled dir + reference dir | column-by-column diff | Reads parquet |

---

## Phases

### Phase 1: DSL Schema ✎
**Deliverable**: `just_dna_pipelines/annotation/module_spec.py`

- Pydantic 2 models for `ModuleSpecConfig`, `VariantRow`, `StudyRow`
- CSV reader/validator
- YAML reader/validator
- Unit tests for validation (malformed inputs, missing columns, bad genotypes)

### Phase 2: Reverse-Engineer Existing Module ✎
**Deliverable**: `data/module_specs/vo2max/`

- Read vo2max weights/annotations/studies from HuggingFace
- Generate `module_spec.yaml`, `variants.csv`, `studies.csv`
- This proves the DSL can represent real modules

### Phase 3: Compiler ✎
**Deliverable**: `just_dna_pipelines/annotation/module_compiler.py`

- `validate_spec(spec_dir) → ValidationResult`
- `compile_module(spec_dir, output_dir) → CompilationResult`
- rsid resolution (optional, via Ensembl REST or dbSNP)
- Typer CLI commands: `module-validate`, `module-compile`

### Phase 4: Round-Trip Test ✎
**Deliverable**: `tests/test_module_compiler.py`

- `existing_module → reverse → DSL → compile → diff → zero`
- Validates the full chain is lossless
- Uses vo2max as the reference module

### Phase 5: Agno Agent ✎
**Deliverable**: `just_dna_pipelines/agents/module_creator.py`

- Agent with geneticist system prompt
- Tool wrappers for validate/compile/lookup/search
- Integration with Agno framework
- Eval harness using test inputs (see below)

### Phase 6: Eval & Iteration ✎
**Deliverable**: Pass rate on eval set

- Run agent on freeform test inputs (CYP panel, MTHFR/NAD panel)
- Compare agent output DSL to hand-crafted reference DSL
- Measure: schema validity, variant coverage, weight directionality, study relevance
- Iterate on system prompt and tool design

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
