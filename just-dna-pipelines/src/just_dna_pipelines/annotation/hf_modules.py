"""
HuggingFace Annotator Modules - Enum and utilities.

This module defines the available annotation modules from the
just-dna-seq/annotators HuggingFace repository and provides
utilities for loading them.
"""

from enum import Enum
from typing import Optional

import polars as pl
from pydantic import BaseModel


class AnnotatorModule(str, Enum):
    """
    Available annotation modules from HuggingFace (just-dna-seq/annotators).
    
    Each module provides three tables:
    - annotations.parquet: Variant facts (rsid, gene, phenotype, category)
    - studies.parquet: Literature evidence (rsid, pmid, population, p_value)
    - weights.parquet: Curator scores (rsid, genotype, weight, state, conclusion)
    """
    LONGEVITYMAP = "longevitymap"
    LIPIDMETABOLISM = "lipidmetabolism"
    VO2MAX = "vo2max"
    SUPERHUMAN = "superhuman"
    CORONARY = "coronary"
    # DRUGS module is planned but not yet available in the HF repo
    
    @classmethod
    def all_modules(cls) -> list["AnnotatorModule"]:
        """Return all available modules."""
        return list(cls)
    
    @classmethod
    def from_string(cls, value: str) -> "AnnotatorModule":
        """Parse module from string (case-insensitive)."""
        value_lower = value.lower()
        for module in cls:
            if module.value == value_lower:
                return module
        raise ValueError(f"Unknown module: {value}. Available: {[m.value for m in cls]}")


class ModuleTable(str, Enum):
    """Tables available in each HF annotator module."""
    ANNOTATIONS = "annotations"
    STUDIES = "studies"
    WEIGHTS = "weights"


# HuggingFace repository info
HF_REPO_ID = "just-dna-seq/annotators"
HF_BASE_URL = f"hf://datasets/{HF_REPO_ID}/data"


def get_module_table_url(module: AnnotatorModule, table: ModuleTable) -> str:
    """
    Get the HuggingFace URL for a specific module table.
    
    Example: hf://datasets/just-dna-seq/annotators/data/longevitymap/weights.parquet
    """
    return f"{HF_BASE_URL}/{module.value}/{table.value}.parquet"


def scan_module_table(
    module: AnnotatorModule,
    table: ModuleTable,
    cache_dir: Optional[str] = None,
) -> pl.LazyFrame:
    """
    Lazily scan a module table from HuggingFace.
    
    Uses Polars' native HF support for efficient streaming.
    
    Args:
        module: The annotator module to load
        table: Which table to load (annotations, studies, weights)
        cache_dir: Optional local cache directory (uses HF cache by default)
        
    Returns:
        LazyFrame for memory-efficient processing
    """
    url = get_module_table_url(module, table)
    return pl.scan_parquet(url)


def scan_module_weights(module: AnnotatorModule) -> pl.LazyFrame:
    """Convenience function to scan a module's weights table."""
    return scan_module_table(module, ModuleTable.WEIGHTS)


def scan_module_annotations(module: AnnotatorModule) -> pl.LazyFrame:
    """Convenience function to scan a module's annotations table."""
    return scan_module_table(module, ModuleTable.ANNOTATIONS)


def scan_module_studies(module: AnnotatorModule) -> pl.LazyFrame:
    """Convenience function to scan a module's studies table."""
    return scan_module_table(module, ModuleTable.STUDIES)


class ModuleOutputMapping(BaseModel):
    """Mapping of output files to their source modules."""
    module: str
    annotations_path: Optional[str] = None
    weights_path: Optional[str] = None
    studies_path: Optional[str] = None
    
    
class AnnotationManifest(BaseModel):
    """Manifest describing all annotation outputs for a user's VCF."""
    user_name: str
    sample_name: str
    source_vcf: str
    modules: list[ModuleOutputMapping]
    total_variants_annotated: int = 0
