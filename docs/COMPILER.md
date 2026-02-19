# Module Compiler

Deterministic compiler that converts a **Module Spec** (YAML + CSV) into the
three-parquet-table format consumed by just-dna-lite's annotation pipeline.

```
module_spec.yaml ─┐
variants.csv ─────┼──▶ compiler ──▶ weights.parquet
studies.csv ──────┘                 annotations.parquet
                                    studies.parquet
```

This package is intentionally **decoupled** from the rest of the pipeline.
Its only dependencies are polars, pydantic, pyyaml, typer, and rich — all
already in the project. It can be extracted into a standalone library without
code changes.

---

## Package Layout

```
just-dna-pipelines/src/just_dna_pipelines/module_compiler/
├── __init__.py      # Public API re-exports
├── models.py        # Pydantic 2 models (DSL schema + result types)
├── compiler.py      # validate_spec() + compile_module()
└── cli.py           # Typer commands (module validate, module compile)
```

CLI is mounted into the root `pipelines` app via `app.add_typer()` in
`src/just_dna_lite/cli.py`.

---

## CLI Usage

```bash
# Validate a spec (no output written)
uv run pipelines module validate data/module_specs/evals/mthfr_nad/

# Compile to parquet (default output: data/output/modules/<name>/)
uv run pipelines module compile data/module_specs/evals/cyp_panel/

# Compile with explicit output directory and compression
uv run pipelines module compile data/module_specs/evals/mthfr_nad/ \
    --output data/output/modules/mthfr_nad/ \
    --compression snappy
```

---

## Python API

```python
from pathlib import Path
from just_dna_pipelines.module_compiler import validate_spec, compile_module

# Validate only
result = validate_spec(Path("data/module_specs/evals/cyp_panel/"))
assert result.valid
print(result.stats)  # {'variant_rows': 21, 'unique_rsids': 7, ...}

# Compile
result = compile_module(
    Path("data/module_specs/evals/cyp_panel/"),
    Path("data/output/modules/cyp_panel/"),
)
assert result.success
print(result.stats)  # {'weights_rows': 21, 'annotations_rows': 7, ...}
```

---

## Input: Module Spec DSL

A module spec is a directory with up to three files:

### `module_spec.yaml` (required)

```yaml
schema_version: "1.0"

module:
  name: cyp_panel                          # ^[a-z][a-z0-9_]*$
  title: "CYP Drug Metabolism"
  description: "Cytochrome P450 pharmacogenomic variants"
  report_title: "Pharmacogenomics — CYP Panel"
  icon: pill                               # Fomantic UI icon name
  color: "#a333c8"                         # 6-digit hex

defaults:
  curator: ai-module-creator
  method: literature-review
  priority: high                           # low | medium | high

genome_build: GRCh38
```

### `variants.csv` (required)

One row per **(rsid, genotype)** combination.

| Column | Required | Type | Notes |
|--------|----------|------|-------|
| `rsid` | yes | string | Must match `rs\d+` |
| `chrom` | no* | string | 1-22, X, Y, MT (no "chr" prefix; auto-stripped) |
| `start` | no* | int | 1-based GRCh38 position |
| `ref` | no* | string | Reference allele |
| `alts` | no* | string | Comma-separated alt alleles |
| `genotype` | yes | string | Slash-separated, alphabetically sorted: `A/G` not `G/A` |
| `weight` | yes | float | Positive = protective, negative = risk |
| `state` | yes | string | `risk` · `protective` · `neutral` · `significant` · `alt` · `ref` |
| `conclusion` | yes | string | Human-readable interpretation |
| `priority` | no | string | Overrides `defaults.priority` |
| `gene` | yes | string | Gene symbol |
| `phenotype` | yes | string | Trait/phenotype |
| `category` | yes | string | Grouping within the module |
| `clinvar` | no | bool | ClinVar presence flag |
| `pathogenic` | no | bool | ClinVar pathogenic flag |
| `benign` | no | bool | ClinVar benign flag |
| `curator` | no | string | Overrides `defaults.curator` |
| `method` | no | string | Overrides `defaults.method` |

**\* Position columns**: if any of `chrom`/`start` is provided, both must be
present. `ref`/`alts` require `chrom`+`start`. All can be omitted —
the compiler resolves them from the local Ensembl DuckDB cache.

### `studies.csv` (optional)

One row per **(rsid, pmid)** combination.

| Column | Required | Type | Notes |
|--------|----------|------|-------|
| `rsid` | yes | string | Must match `rs\d+` |
| `pmid` | yes | string | Digits only |
| `population` | no | string | Study population |
| `p_value` | no | string | Statistical significance |
| `conclusion` | yes | string | Study-specific conclusion |
| `study_design` | no | string | e.g. meta-analysis, GWAS, case-control |

---

## Compilation Pipeline

### Step 1: Validate

All validation runs before any output is written. Errors are collected and
returned as a list — never raises exceptions.

**Field-level (Pydantic):**

- `rsid` matches `^rs\d+$`
- `genotype` is two alleles, slash-separated, alphabetically sorted, uppercase nucleotides
- `state` is one of the six valid enum values
- `priority` is `low`/`medium`/`high`
- `chrom` is 1-22/X/Y/MT (auto-strips "chr" prefix)
- `pmid` is digits-only
- `color` is 6-digit hex
- `module.name` is lowercase alphanumeric + underscores

**Cross-row:**

- Positional consistency: all rows for the same rsid must share `chrom`/`start`
- Uniqueness: `(rsid, genotype)` pairs in variants, `(rsid, pmid)` pairs in studies
- Study rsid coverage: warns if studies reference rsids absent from variants

**Directional (warnings, not errors):**

- `state=risk` with `weight > 0`
- `state=protective` with `weight < 0`

### Step 2: Build weights.parquet

Each validated variant row becomes one row in weights. Transforms applied:

| CSV value | Parquet value | Type |
|-----------|---------------|------|
| `genotype: "A/G"` | `["A", "G"]` | `List(Utf8)` |
| `alts: "A,G"` | `["A", "G"]` | `List(Utf8)` |
| `chrom: "chr1"` | `"1"` | `Utf8` |
| (missing priority) | `defaults.priority` | `Utf8` |
| (missing curator) | `defaults.curator` | `Utf8` |
| (missing method) | `defaults.method` | `Utf8` |
| (missing clinvar/pathogenic/benign) | `false` | `Boolean` |
| — | `module: config.module.name` | `Utf8` (injected) |
| — | `likely_pathogenic: false` | `Boolean` (injected) |
| — | `likely_benign: false` | `Boolean` (injected) |

Full schema (18 columns):

```
rsid            Utf8
chrom           Utf8
start           Int64
ref             Utf8
alts            List(Utf8)
genotype        List(Utf8)
weight          Float64
state           Utf8
conclusion      Utf8
priority        Utf8
module          Utf8
curator         Utf8
method          Utf8
clinvar         Boolean
pathogenic      Boolean
benign          Boolean
likely_pathogenic Boolean
likely_benign   Boolean
```

### Step 3: Build annotations.parquet

Deduplicated by rsid — one row per unique rsid, keeping the first
occurrence's gene/phenotype/category.

```
rsid       Utf8
gene       Utf8
phenotype  Utf8
category   Utf8
```

### Step 4: Build studies.parquet (if studies.csv exists)

Direct 1:1 mapping from CSV rows.

```
rsid          Utf8
pmid          Utf8
population    Utf8
p_value       Utf8
conclusion    Utf8
study_design  Utf8
```

### Output

```
output/<module_name>/
├── weights.parquet         # zstd compressed (configurable)
├── annotations.parquet
└── studies.parquet          # only if studies.csv was provided
```

This directory is directly compatible with the module discovery system —
drop it into any configured source and it auto-discovers.

---

## Validation vs Compilation

| | `validate_spec()` | `compile_module()` |
|-|--------------------|--------------------|
| **Input** | spec directory | spec directory + output directory |
| **Side effects** | None | Writes parquet files |
| **Returns** | `ValidationResult` | `CompilationResult` |
| **On error** | `valid=False` + error list | `success=False` + error list |
| **Warnings** | Included | Forwarded from validation |
| **Stats** | variant/rsid/gene counts | row counts per output table |

`compile_module` calls `validate_spec` internally — if validation fails,
no output is produced.

---

## Test Coverage

37 tests in `just-dna-pipelines/tests/test_module_compiler.py`, organized into
five groups:

| Group | Tests | What's covered |
|-------|-------|----------------|
| `TestModuleSpecConfig` | 4 | YAML loading, module name/version validation |
| `TestVariantRow` | 7 | rsid format, genotype sorting, state enum, chrom normalization, position completeness |
| `TestStudyRow` | 2 | Valid study, invalid pmid |
| `TestValidation` | 8 | Both eval specs valid, nonexistent/empty dirs, missing CSV, malformed rows, duplicates, weight warnings |
| `TestCompilation` | 14 | Both eval specs compile, schema correctness, content verification, deduplication, positions, alts as list, optional studies |
| `TestRoundTrip` | 2 | Deterministic output (compile twice → identical parquet) |

Both `data/module_specs/evals/mthfr_nad/` and `data/module_specs/evals/cyp_panel/`
are used as real inputs throughout.

---

## Design Decisions

**CSV via stdlib `csv.DictReader`, not Polars.**
The conclusion field contains commas, quotes, and long text. Python's CSV
reader handles RFC 4180 quoting reliably. Polars CSV inference can misparse
quoted fields with embedded commas. Each row is individually validated through
Pydantic before being collected into a DataFrame for parquet output.

**Validation collects all errors, never raises.**
Both `validate_spec` and `compile_module` return result objects with error
lists. This is deliberate: when used as agent tools, the caller needs a
complete error list to fix all issues in one pass rather than hitting them
sequentially.

**Separate validate and compile.**
Validation is cheap and useful on its own (agent feedback loop). Compilation
is a superset that validates first, then writes. No partial output on error.

**Deduplication strategy for annotations.**
`annotations.parquet` has one row per rsid. When the same rsid appears with
multiple genotypes in `variants.csv`, the first row's gene/phenotype/category
wins. This matches the existing pipeline's expectation that annotations are
variant-level, not genotype-level.

---

## Future Work

- **rsid resolution** (implemented): Missing `chrom`/`start`/`ref`/`alts` are
  resolved from the local Ensembl DuckDB (`ensembl_variations` view).
  The resolver auto-downloads parquet data via HfFileSystem if the cache is
  missing. Bidirectional: rsid→position and position→rsid
- **Round-trip from existing modules**: Reverse-engineer an existing HuggingFace
  module into the spec DSL format, compile it back, and diff against the
  original (Phase 4 from AI_MODULE_CREATION.md)
- **Agent tool wrappers**: Expose `validate_spec` and `compile_module` as
  Agno tools for the module creator agent (Phase 5)
