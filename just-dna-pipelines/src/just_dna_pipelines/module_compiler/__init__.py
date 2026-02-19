"""
Module Compiler: DSL spec → deployable parquet module.

Converts a module specification directory (YAML + CSV files) into the
three-parquet-table format used by just-dna-lite's annotation pipeline:
weights.parquet, annotations.parquet, and studies.parquet.

This package is intentionally decoupled from the rest of the pipeline
and can be extracted into a standalone library.
"""

from just_dna_pipelines.module_compiler.models import (
    CompilationResult,
    Defaults,
    ModuleInfo,
    ModuleSpecConfig,
    StudyRow,
    ValidationResult,
    VariantRow,
)
from just_dna_pipelines.module_compiler.compiler import (
    compile_module,
    reverse_module,
    validate_spec,
)
from just_dna_pipelines.module_compiler.resolver import resolve_variants
