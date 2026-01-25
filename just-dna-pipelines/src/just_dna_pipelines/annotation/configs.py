"""
Dagster configuration classes for annotation pipelines.
"""

from typing import Optional
import psutil

from dagster import Config

from just_dna_pipelines.models import SampleInfo
from just_dna_pipelines.annotation.hf_modules import AnnotatorModule


def get_default_duckdb_memory_limit() -> str:
    """
    Calculate a sensible DuckDB memory limit based on available system memory.
    
    Strategy:
    - Use 75% of available RAM for DuckDB (leave 25% for OS/other processes)
    - Minimum: 8GB (genomic data needs substantial memory)
    - Maximum: 128GB (reasonable upper bound)
    
    Returns:
        Memory limit string like "32GB"
    """
    available_gb = psutil.virtual_memory().total / (1024**3)
    
    # Use 75% of available RAM
    duckdb_gb = int(available_gb * 0.75)
    
    # Enforce bounds
    duckdb_gb = max(8, min(duckdb_gb, 128))
    
    return f"{duckdb_gb}GB"


def get_default_duckdb_threads() -> int:
    """
    Calculate default thread count based on CPU cores.
    
    Strategy:
    - Use 75% of available cores (leave some for OS)
    - Minimum: 2
    - Maximum: 16 (diminishing returns beyond this)
    """
    cpu_count = psutil.cpu_count(logical=True) or 4
    threads = max(2, min(int(cpu_count * 0.75), 16))
    return threads


class EnsemblAnnotationsConfig(Config):
    """Configuration for the Ensembl annotations asset."""
    repo_id: str = "just-dna-seq/ensembl_variations"
    cache_dir: Optional[str] = None
    token: Optional[str] = None
    force_download: bool = False
    allow_patterns: Optional[list[str]] = None


class DuckDBConfig(Config):
    """
    Configuration for DuckDB memory and performance settings.
    
    By default, memory_limit and threads are auto-detected based on system resources.
    You can override them for specific use cases (e.g., constrained environments).
    """
    memory_limit: Optional[str] = None  # Auto-detect if None (75% of RAM, min 8GB)
    threads: Optional[int] = None  # Auto-detect if None (75% of CPUs, min 2)
    temp_directory: str = "/tmp/duckdb_temp"  # Where to spill to disk
    preserve_insertion_order: bool = False  # Allow reordering for efficiency
    enable_object_cache: bool = True  # Cache parsed Parquet metadata
    
    def get_memory_limit(self) -> str:
        """Get memory limit, using auto-detection if not explicitly set."""
        return self.memory_limit or get_default_duckdb_memory_limit()
    
    def get_threads(self) -> int:
        """Get thread count, using auto-detection if not explicitly set."""
        return self.threads or get_default_duckdb_threads()


class AnnotationConfig(Config, SampleInfo):
    """Configuration for VCF annotation.
    
    Inherits sample metadata from SampleInfo:
    - sample_name: Technical identifier for the sample
    - sample_description: Human-readable description
    - sequencing_type: Type of sequencing (full genome, exome, etc.)
    - species: Species name (default: Homo sapiens)
    - reference_genome: Reference genome build (default: GRCh38)
    """
    vcf_path: str
    user_name: Optional[str] = None  # Optional user identifier
    variant_type: str = "SNV"
    join_columns: Optional[list[str]] = None
    output_path: Optional[str] = None
    compression: str = "zstd"
    info_fields: Optional[list[str]] = None
    with_formats: Optional[bool] = None  # Whether to extract FORMAT fields. If None, auto-detected in read_vcf_file.
    format_fields: Optional[list[str]] = None  # Specific FORMAT fields to extract
    duckdb_config: Optional[DuckDBConfig] = None  # Optional DuckDB tuning


class HfModuleAnnotationConfig(Config, SampleInfo):
    """
    Configuration for annotating VCF with HuggingFace modules.
    
    The HF modules (just-dna-seq/annotators) are self-contained and include
    all annotation data. No Ensembl join is required.
    
    VCF must have FORMAT fields (GT) to compute genotype for joining with
    the weights table. The genotype is computed as List[String] sorted alphabetically.
    """
    vcf_path: str
    user_name: Optional[str] = None
    
    # Module selection - list of module names (all by default)
    # Valid values: longevitymap, lipidmetabolism, vo2max, superhuman, coronary, drugs
    modules: Optional[list[str]] = None  # None means all modules
    
    # Output settings
    output_dir: Optional[str] = None  # If None, uses data/output/users/{user_name}/modules/
    compression: str = "zstd"
    
    # VCF parsing options
    info_fields: Optional[list[str]] = None
    format_fields: Optional[list[str]] = None  # Default: ["GT", "GQ", "DP", "AD", "VAF", "PL"]
    
    def get_modules(self) -> list[AnnotatorModule]:
        """Get list of modules to annotate with."""
        if self.modules is None:
            return AnnotatorModule.all_modules()
        return [AnnotatorModule.from_string(m) for m in self.modules]


