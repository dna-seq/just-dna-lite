"""
Module Spec Compiler: validates a module spec directory and compiles it
to the three-parquet-table format (weights, annotations, studies).

Public API:
    validate_spec(spec_dir)   → ValidationResult
    compile_module(spec_dir, output_dir) → CompilationResult
    reverse_module(parquet_dir, output_dir, metadata) → Path
"""

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import polars as pl
import yaml
from pydantic import ValidationError

from just_dna_pipelines.module_compiler.models import (
    CompilationResult,
    ModuleSpecConfig,
    StudyRow,
    ValidationResult,
    VariantRow,
)


# ── File loading helpers ───────────────────────────────────────────────────────


def _load_yaml(path: Path) -> Tuple[Optional[ModuleSpecConfig], List[str]]:
    """Load and validate module_spec.yaml. Returns (config, errors)."""
    errors: List[str] = []
    if not path.exists():
        return None, [f"module_spec.yaml not found at {path}"]
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        return None, ["module_spec.yaml is empty"]
    try:
        config = ModuleSpecConfig.model_validate(raw)
        return config, []
    except ValidationError as exc:
        for err in exc.errors():
            loc = " → ".join(str(x) for x in err["loc"])
            errors.append(f"module_spec.yaml [{loc}]: {err['msg']}")
        return None, errors


def _load_csv_rows(
    path: Path,
    row_model: type,
    file_label: str,
) -> Tuple[List[Any], List[str], List[str]]:
    """
    Load a CSV file and validate each row against a Pydantic model.

    Returns (valid_rows, errors, warnings).
    """
    errors: List[str] = []
    warnings: List[str] = []
    rows: List[Any] = []

    if not path.exists():
        return [], [f"{file_label} not found at {path}"], []

    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return [], [f"{file_label} has no header row"], []

        for line_num, raw_row in enumerate(reader, start=2):
            cleaned = {
                k.strip(): (v.strip() if isinstance(v, str) and v.strip() != "" else None)
                for k, v in raw_row.items()
                if k is not None
            }
            try:
                row = row_model.model_validate(cleaned)
                rows.append(row)
            except ValidationError as exc:
                for err in exc.errors():
                    loc = " → ".join(str(x) for x in err["loc"])
                    errors.append(f"{file_label} line {line_num} [{loc}]: {err['msg']}")

    return rows, errors, warnings


# ── Cross-row validation ───────────────────────────────────────────────────────


def _cross_validate_variants(
    variants: List[VariantRow],
) -> Tuple[List[str], List[str]]:
    """Validate consistency across variant rows. Returns (errors, warnings)."""
    errors: List[str] = []
    warnings: List[str] = []

    # Positional consistency: all rows for the same variant must have same chrom/start
    key_positions: Dict[str, Tuple[Optional[str], Optional[int]]] = {}
    for row in variants:
        key = row.variant_key
        pos = (row.chrom, row.start)
        if key in key_positions:
            if key_positions[key] != pos:
                errors.append(
                    f"Inconsistent positions for {key}: "
                    f"{key_positions[key]} vs {pos}"
                )
        else:
            key_positions[key] = pos

    # Genotype uniqueness: (variant_key, genotype) must be unique
    seen_keys: set[Tuple[str, str]] = set()
    for row in variants:
        key = (row.variant_key, row.genotype)
        if key in seen_keys:
            errors.append(
                f"Duplicate (variant, genotype): ({row.variant_key}, {row.genotype})"
            )
        seen_keys.add(key)

    # Weight direction sanity: risk states should have non-positive weights
    for row in variants:
        if row.weight is None:
            continue
        label = row.variant_key
        if row.state == "risk" and row.weight > 0:
            warnings.append(
                f"{label} genotype {row.genotype}: state='risk' but weight={row.weight} > 0"
            )
        if row.state == "protective" and row.weight < 0:
            warnings.append(
                f"{label} genotype {row.genotype}: state='protective' but weight={row.weight} < 0"
            )

    return errors, warnings


def _cross_validate_studies(
    studies: List[StudyRow], variant_keys: set[str]
) -> Tuple[List[str], List[str]]:
    """Validate study rows against variant keys. Returns (errors, warnings)."""
    errors: List[str] = []
    warnings: List[str] = []

    study_keys = {row.variant_key for row in studies}
    orphan_keys = study_keys - variant_keys
    if orphan_keys:
        warnings.append(
            f"Studies reference variants not in variants.csv: {sorted(orphan_keys)}"
        )

    # Uniqueness of (variant_key, pmid) — warning, not error (existing modules have dupes)
    seen: set[Tuple[str, str]] = set()
    for row in studies:
        key = (row.variant_key, row.pmid)
        if key in seen:
            warnings.append(f"Duplicate (variant, pmid): ({row.variant_key}, {row.pmid})")
        seen.add(key)

    return errors, warnings


# ── Public API ─────────────────────────────────────────────────────────────────


def validate_spec(spec_dir: Path) -> ValidationResult:
    """
    Validate a module spec directory without producing output.

    Checks:
    - module_spec.yaml structure and values
    - variants.csv rows against Pydantic model
    - studies.csv rows (if present)
    - Cross-row consistency (positions, uniqueness, weight direction)

    Returns a ValidationResult with errors, warnings, and summary stats.
    """
    spec_dir = Path(spec_dir)
    all_errors: List[str] = []
    all_warnings: List[str] = []

    if not spec_dir.is_dir():
        return ValidationResult(
            valid=False,
            errors=[f"Spec directory does not exist: {spec_dir}"],
        )

    # 1. Load YAML
    config, yaml_errors = _load_yaml(spec_dir / "module_spec.yaml")
    all_errors.extend(yaml_errors)

    # 2. Load variants
    variants, var_errors, var_warnings = _load_csv_rows(
        spec_dir / "variants.csv", VariantRow, "variants.csv"
    )
    all_errors.extend(var_errors)
    all_warnings.extend(var_warnings)

    # 3. Load studies (optional)
    studies_path = spec_dir / "studies.csv"
    studies: List[StudyRow] = []
    if studies_path.exists():
        studies, study_errors, study_warnings = _load_csv_rows(
            studies_path, StudyRow, "studies.csv"
        )
        all_errors.extend(study_errors)
        all_warnings.extend(study_warnings)

    # 4. Cross-validation
    if variants:
        cross_errors, cross_warnings = _cross_validate_variants(variants)
        all_errors.extend(cross_errors)
        all_warnings.extend(cross_warnings)

        variant_keys = {v.variant_key for v in variants}
        if studies:
            study_errors, study_warnings = _cross_validate_studies(studies, variant_keys)
            all_errors.extend(study_errors)
            all_warnings.extend(study_warnings)

    # 5. Compute stats
    stats: Dict[str, Any] = {}
    if variants:
        variant_keys_set = {v.variant_key for v in variants}
        rsids = {v.rsid for v in variants if v.rsid is not None}
        genes = {v.gene for v in variants}
        categories = {v.category for v in variants}
        stats = {
            "variant_rows": len(variants),
            "unique_rsids": len(rsids),
            "unique_variants": len(variant_keys_set),
            "unique_genes": len(genes),
            "categories": sorted(categories),
            "study_rows": len(studies),
        }
        if config:
            stats["module_name"] = config.module.name

    return ValidationResult(
        valid=len(all_errors) == 0,
        errors=all_errors,
        warnings=all_warnings,
        stats=stats,
    )


def compile_module(
    spec_dir: Path,
    output_dir: Path,
    compression: str = "zstd",
    resolve_with_ensembl: bool = True,
    ensembl_cache: Optional[Path] = None,
) -> CompilationResult:
    """
    Compile a module spec directory into deployable parquet files.

    Steps:
    1. Validate the spec (fails fast on errors)
    2. Optionally resolve rsid<->position via Ensembl DuckDB
    3. Build weights.parquet from variants.csv
    4. Build annotations.parquet (deduplicated by variant key) from variants.csv
    5. Build studies.parquet from studies.csv (if present)

    The output directory will contain: weights.parquet, annotations.parquet,
    and optionally studies.parquet. This is directly compatible with the
    module discovery system.

    Args:
        spec_dir: Path to the module spec directory.
        output_dir: Directory for output parquet files.
        compression: Parquet compression codec.
        resolve_with_ensembl: If True (default), resolve missing rsid/position
            fields using Ensembl DuckDB. Auto-downloads data if needed.
        ensembl_cache: Explicit path to Ensembl parquet cache. If None,
            uses the default cache location.
    """
    spec_dir = Path(spec_dir)
    output_dir = Path(output_dir)

    # Validate first
    validation = validate_spec(spec_dir)
    if not validation.valid:
        return CompilationResult(
            success=False,
            errors=validation.errors,
            warnings=validation.warnings,
        )

    # Re-load (validation already proved these are valid)
    config, _ = _load_yaml(spec_dir / "module_spec.yaml")
    assert config is not None
    variants, _, _ = _load_csv_rows(spec_dir / "variants.csv", VariantRow, "variants.csv")

    studies: List[StudyRow] = []
    if (spec_dir / "studies.csv").exists():
        studies, _, _ = _load_csv_rows(spec_dir / "studies.csv", StudyRow, "studies.csv")

    all_warnings = list(validation.warnings)

    # Resolve missing rsid/position fields from Ensembl
    if resolve_with_ensembl:
        from just_dna_pipelines.module_compiler.resolver import resolve_variants
        variants, resolve_warnings = resolve_variants(variants, ensembl_cache)
        all_warnings.extend(resolve_warnings)

    # Build parquet tables
    module_name = config.module.name
    weights_df = _build_weights(variants, config)
    annotations_df = _build_annotations(variants, module_name)
    studies_df = _build_studies(studies, module_name) if studies else None

    # Write output
    output_dir.mkdir(parents=True, exist_ok=True)

    weights_path = output_dir / "weights.parquet"
    weights_df.write_parquet(weights_path, compression=compression)

    annotations_path = output_dir / "annotations.parquet"
    annotations_df.write_parquet(annotations_path, compression=compression)

    stats: Dict[str, Any] = {
        "module_name": config.module.name,
        "weights_rows": weights_df.height,
        "annotations_rows": annotations_df.height,
        "weights_columns": weights_df.columns,
        "annotations_columns": annotations_df.columns,
    }

    if studies_df is not None:
        studies_path = output_dir / "studies.parquet"
        studies_df.write_parquet(studies_path, compression=compression)
        stats["studies_rows"] = studies_df.height
        stats["studies_columns"] = studies_df.columns
    else:
        stats["studies_rows"] = 0

    return CompilationResult(
        success=True,
        output_dir=output_dir,
        errors=[],
        warnings=all_warnings,
        stats=stats,
    )


# ── Parquet builders ───────────────────────────────────────────────────────────


def _build_weights(variants: List[VariantRow], config: ModuleSpecConfig) -> pl.DataFrame:
    """Build the weights.parquet DataFrame from validated variant rows."""
    defaults = config.defaults
    module_name = config.module.name

    records: List[Dict[str, Any]] = []
    for v in variants:
        # Priority: use row override, then default, then None
        priority = v.priority if v.priority is not None else defaults.priority
        records.append(
            {
                "rsid": v.rsid,
                "genotype": v.genotype.split("/"),
                "module": module_name,
                "weight": v.weight,
                "state": v.state,
                "priority": priority,
                "conclusion": v.conclusion,
                "curator": v.curator or defaults.curator,
                "method": v.method or defaults.method,
                "chrom": v.chrom,
                "start": v.start,
                "end": v.start,
                "ref": v.ref,
                "alts": v.alts.split(",") if v.alts else None,
                "clinvar": v.clinvar if v.clinvar is not None else False,
                "pathogenic": v.pathogenic if v.pathogenic is not None else False,
                "benign": v.benign if v.benign is not None else False,
                "likely_pathogenic": False,
                "likely_benign": False,
            }
        )

    schema = {
        "rsid": pl.Utf8,
        "genotype": pl.List(pl.Utf8),
        "module": pl.Utf8,
        "weight": pl.Float64,
        "state": pl.Utf8,
        "priority": pl.Utf8,
        "conclusion": pl.Utf8,
        "curator": pl.Utf8,
        "method": pl.Utf8,
        "chrom": pl.Utf8,
        "start": pl.UInt32,
        "end": pl.UInt32,
        "ref": pl.Utf8,
        "alts": pl.List(pl.Utf8),
        "clinvar": pl.Boolean,
        "pathogenic": pl.Boolean,
        "benign": pl.Boolean,
        "likely_pathogenic": pl.Boolean,
        "likely_benign": pl.Boolean,
    }

    return pl.DataFrame(records, schema=schema)


def _build_annotations(
    variants: List[VariantRow], module_name: str
) -> pl.DataFrame:
    """
    Build the annotations.parquet DataFrame.

    Deduplicated by variant_key — one row per unique variant, keeping the first
    occurrence's gene/phenotype/category.
    """
    seen_keys: set[str] = set()
    records: List[Dict[str, Optional[str]]] = []
    for v in variants:
        key = v.variant_key
        if key not in seen_keys:
            records.append(
                {
                    "rsid": v.rsid,
                    "module": module_name,
                    "gene": v.gene or "",
                    "phenotype": v.phenotype or "",
                    "category": v.category or "",
                }
            )
            seen_keys.add(key)

    schema = {
        "rsid": pl.Utf8,
        "module": pl.Utf8,
        "gene": pl.Utf8,
        "phenotype": pl.Utf8,
        "category": pl.Utf8,
    }

    return pl.DataFrame(records, schema=schema)


def _build_studies(studies: List[StudyRow], module_name: str) -> pl.DataFrame:
    """Build the studies.parquet DataFrame from validated study rows."""
    records: List[Dict[str, Any]] = []
    for s in studies:
        records.append(
            {
                "rsid": s.rsid,
                "module": module_name,
                "pmid": s.pmid,
                "population": s.population,
                "p_value": s.p_value,
                "conclusion": s.conclusion,
                "study_design": s.study_design,
            }
        )

    schema = {
        "rsid": pl.Utf8,
        "module": pl.Utf8,
        "pmid": pl.Utf8,
        "population": pl.Utf8,
        "p_value": pl.Utf8,
        "conclusion": pl.Utf8,
        "study_design": pl.Utf8,
    }

    return pl.DataFrame(records, schema=schema)


# ── Reverse engineering ────────────────────────────────────────────────────────


def reverse_module(
    parquet_dir: Path,
    output_dir: Path,
    module_name: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    report_title: Optional[str] = None,
    icon: str = "database",
    color: str = "#6435c9",
) -> Path:
    """
    Reverse-engineer a parquet module into the module spec DSL format.

    Reads weights.parquet, annotations.parquet, and studies.parquet from
    parquet_dir and writes module_spec.yaml + variants.csv + studies.csv
    into output_dir.

    Returns the output_dir path.
    """
    parquet_dir = Path(parquet_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    weights_df = pl.read_parquet(parquet_dir / "weights.parquet")

    if module_name is None:
        if "module" in weights_df.columns:
            module_name = weights_df["module"].drop_nulls().unique().to_list()[0]
        else:
            module_name = parquet_dir.name

    default_curator = _most_common(weights_df, "curator") or "unknown"
    default_method = _most_common(weights_df, "method") or "unknown"

    default_priority: Optional[str] = None
    if "priority" in weights_df.columns:
        non_null = weights_df["priority"].drop_nulls()
        if non_null.len() > 0:
            default_priority = non_null.mode().to_list()[0]

    annotations_df: Optional[pl.DataFrame] = None
    ann_path = parquet_dir / "annotations.parquet"
    if ann_path.exists():
        annotations_df = pl.read_parquet(ann_path)

    # Build module_spec.yaml
    defaults_dict: Dict[str, Any] = {
        "curator": default_curator,
        "method": default_method,
    }
    if default_priority is not None:
        defaults_dict["priority"] = default_priority

    spec = {
        "schema_version": "1.0",
        "module": {
            "name": module_name,
            "title": title or module_name.replace("_", " ").title(),
            "description": description or f"Annotation module: {module_name}",
            "report_title": report_title or module_name.replace("_", " ").title(),
            "icon": icon,
            "color": color,
        },
        "defaults": defaults_dict,
        "genome_build": "GRCh38",
    }
    yaml_path = output_dir / "module_spec.yaml"
    yaml_path.write_text(
        yaml.dump(spec, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )

    # Annotations lookup: rsid -> (gene, phenotype, category)
    ann_lookup: Dict[str, Dict[str, str]] = {}
    if annotations_df is not None:
        for row in annotations_df.iter_rows(named=True):
            ann_lookup[row["rsid"]] = {
                "gene": row.get("gene", ""),
                "phenotype": row.get("phenotype", ""),
                "category": row.get("category", ""),
            }

    _write_variants_csv(
        weights_df, ann_lookup, default_curator, default_method,
        default_priority, output_dir / "variants.csv",
    )

    studies_path = parquet_dir / "studies.parquet"
    if studies_path.exists():
        studies_df = pl.read_parquet(studies_path)
        _write_studies_csv(studies_df, output_dir / "studies.csv")

    return output_dir


def _most_common(df: pl.DataFrame, col: str) -> Optional[str]:
    """Return the most common non-null value in a column, or None."""
    if col not in df.columns:
        return None
    non_null = df[col].drop_nulls()
    if non_null.len() == 0:
        return None
    return non_null.mode().to_list()[0]


def _write_variants_csv(
    weights_df: pl.DataFrame,
    ann_lookup: Dict[str, Dict[str, str]],
    default_curator: str,
    default_method: str,
    default_priority: Optional[str],
    output_path: Path,
) -> None:
    """Write variants.csv from weights parquet + annotations lookup."""
    fieldnames = [
        "rsid", "chrom", "start", "ref", "alts", "genotype",
        "weight", "state", "conclusion", "priority",
        "gene", "phenotype", "category",
        "clinvar", "pathogenic", "benign", "curator", "method",
    ]
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in weights_df.iter_rows(named=True):
            rsid = row.get("rsid") or ""
            ann = ann_lookup.get(rsid, {})

            genotype_list = row.get("genotype", [])
            genotype_str = "/".join(genotype_list) if genotype_list else ""

            alts_list = row.get("alts")
            alts_str = ",".join(alts_list) if alts_list else ""

            curator = row.get("curator", "")
            method = row.get("method", "")
            curator_out = curator if curator != default_curator else ""
            method_out = method if method != default_method else ""

            priority = row.get("priority")
            priority_out = priority if priority != default_priority else ""

            clinvar = row.get("clinvar", False)
            pathogenic = row.get("pathogenic", False)
            benign = row.get("benign", False)

            writer.writerow({
                "rsid": rsid,
                "chrom": row.get("chrom", ""),
                "start": row.get("start", ""),
                "ref": row.get("ref", ""),
                "alts": alts_str,
                "genotype": genotype_str,
                "weight": row.get("weight") if row.get("weight") is not None else "",
                "state": row.get("state", ""),
                "conclusion": row.get("conclusion", ""),
                "priority": priority_out,
                "gene": ann.get("gene", ""),
                "phenotype": ann.get("phenotype", ""),
                "category": ann.get("category", ""),
                "clinvar": str(clinvar).lower() if clinvar else "",
                "pathogenic": str(pathogenic).lower() if pathogenic else "",
                "benign": str(benign).lower() if benign else "",
                "curator": curator_out,
                "method": method_out,
            })


def _write_studies_csv(studies_df: pl.DataFrame, output_path: Path) -> None:
    """Write studies.csv from studies parquet."""
    fieldnames = ["rsid", "pmid", "population", "p_value", "conclusion", "study_design"]
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in studies_df.iter_rows(named=True):
            pmid = row.get("pmid")
            if pmid is None or str(pmid).strip() == "":
                continue
            writer.writerow({
                "rsid": row["rsid"],
                "pmid": str(pmid).strip(),
                "population": row.get("population") or "",
                "p_value": row.get("p_value") or "",
                "conclusion": row.get("conclusion") or "",
                "study_design": row.get("study_design") or "",
            })
