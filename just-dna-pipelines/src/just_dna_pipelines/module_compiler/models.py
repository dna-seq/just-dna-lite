"""
Compatibility shim — the schema now lives in the published ``just-dna-format`` package.

This module used to hold the DSL/schema models. Those were extracted to ``just-dna-format``
(``just_dna_format.spec`` for the authored DSL, ``just_dna_compiler.models`` for the compile
result types) so the schema is shared verbatim by just-dna-pipelines, just-dna-registry, and
just-dna-agents. Import sites inside this repo keep working via these re-exports; new code should
import from ``just_dna_format`` / ``just_dna_compiler`` directly.

Note: the old dead constant ``VALID_PRIORITIES`` (never referenced by a validator) was
intentionally not carried into ``just-dna-format``; see just-dna-format/docs/ROADMAP.md.

Since just-dna-format 0.4.0 the identifier grammars live in ``just_dna_format.vocab``, shared
across the authored models. ``ALLELE_PATTERN`` is still re-exported from ``spec`` for backwards
compatibility, but ``RSID_PATTERN`` is not, so it comes from ``vocab`` directly.
"""

from just_dna_compiler.models import CompilationResult, ValidationResult
from just_dna_format.spec import (
    ALLELE_PATTERN,
    SCHEMA_VERSION,
    VALID_CHROMOSOMES,
    VALID_STATES,
    Defaults,
    ModuleInfo,
    ModuleSpecConfig,
    StudyRow,
    VariantRow,
)
from just_dna_format.vocab import RSID_PATTERN

__all__ = [
    "ALLELE_PATTERN",
    "RSID_PATTERN",
    "SCHEMA_VERSION",
    "VALID_CHROMOSOMES",
    "VALID_STATES",
    "CompilationResult",
    "Defaults",
    "ModuleInfo",
    "ModuleSpecConfig",
    "StudyRow",
    "ValidationResult",
    "VariantRow",
]
