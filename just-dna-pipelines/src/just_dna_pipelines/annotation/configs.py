"""
Dagster configuration classes for annotation pipelines.
"""

from typing import Optional
import psutil

from dagster import Config

from just_dna_pipelines.models import SampleInfo
from just_dna_pipelines.module_config import DEFAULT_REPOS
from just_dna_pipelines.annotation.hf_modules import DISCOVERED_MODULES, validate_modules


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
    Configuration for annotating VCF with annotation modules.
    
    Modules are discovered dynamically from configured sources (modules.yaml).
    Sources can be HuggingFace repos, GitHub repos, HTTP URLs, or any
    fsspec-compatible URL. By default, uses sources from modules.yaml.
    
    Pass None for modules to use all discovered modules, or a list of
    specific module names to use a subset.
    
    VCF must have FORMAT fields (GT) to compute genotype for joining with
    the weights table. The genotype is computed as List[String] sorted alphabetically.
    
    VCF Source Options (use ONE of these):
    - vcf_path: Local path to VCF file
    - zenodo_url: Zenodo record URL (e.g., https://zenodo.org/records/18370498)
    
    User Metadata:
    - subject_id: Optional subject/patient identifier
    - study_name: Optional study or project name  
    - description: Optional human-readable description
    - custom_metadata: Arbitrary key-value pairs provided by the user
    """
    vcf_path: Optional[str] = None
    zenodo_url: Optional[str] = None  # Zenodo record or file URL
    user_name: Optional[str] = None
    
    # Repositories to scan for modules (from modules.yaml)
    repos: list[str] = DEFAULT_REPOS
    
    # Module selection - list of module names (all discovered modules by default)
    modules: Optional[list[str]] = None  # None means all discovered modules from the repos
    
    # Output settings
    output_dir: Optional[str] = None  # If None, uses data/output/users/{user_name}/modules/
    compression: str = "zstd"
    
    # VCF parsing options
    info_fields: Optional[list[str]] = None
    format_fields: Optional[list[str]] = None  # Default: ["GT", "GQ", "DP", "AD", "VAF", "PL"]
    
    # User-provided metadata (optional, flexible)
    subject_id: Optional[str] = None  # Subject/patient identifier
    sex: Optional[str] = None  # Biological sex (Male/Female/N/A/Other)
    tissue: Optional[str] = None  # Sample tissue source
    study_name: Optional[str] = None  # Study or project name
    description: Optional[str] = None  # Human-readable description/notes
    custom_metadata: Optional[dict[str, str]] = None  # Arbitrary user-defined key-value pairs
    
    def get_modules(self) -> list[str]:
        """
        Get list of modules to annotate with.
        
        Discovers modules from the configured repos and returns the
        selected subset (or all if none specified).
        """
        from just_dna_pipelines.annotation.hf_modules import discover_hf_modules
        
        # Discover modules from the configured repos
        module_infos = discover_hf_modules(self.repos)
        discovered_names = sorted(list(module_infos.keys()))
        
        if self.modules is None:
            return discovered_names
            
        # Validate selected modules
        valid = []
        requested = [m.lower() for m in self.modules]
        for name in discovered_names:
            if name.lower() in requested:
                valid.append(name)
        return valid
    
    def resolve_vcf_path(self, logger=None) -> str:
        """
        Resolve the VCF path from the configured source.
        
        Supports:
        - vcf_path: Local file path (returned as-is)
        - zenodo_url: Downloads from Zenodo and returns cached path
        
        Returns:
            String path to the VCF file
            
        Raises:
            ValueError: If no source is configured or both are provided
        """
        from just_dna_pipelines.annotation.resources import download_vcf_from_zenodo
        
        if self.vcf_path and self.zenodo_url:
            raise ValueError("Provide only one of vcf_path or zenodo_url, not both")
        
        if self.zenodo_url:
            vcf_path = download_vcf_from_zenodo(self.zenodo_url, logger=logger)
            return str(vcf_path)
        
        if self.vcf_path:
            return self.vcf_path
        
        raise ValueError("Must provide either vcf_path or zenodo_url")


class NormalizeVcfConfig(Config, SampleInfo):
    """Configuration for VCF normalization asset.

    Reads a raw VCF, strips 'chr' prefix from chromosomes (case-insensitive),
    renames 'id' -> 'rsid', computes genotype, applies quality filters from
    modules.yaml, and sinks to parquet.
    """
    vcf_path: str
    user_name: Optional[str] = None
    compression: str = "zstd"
    info_fields: Optional[list[str]] = None
    format_fields: Optional[list[str]] = None
    sex: Optional[str] = None  # Biological sex for chrY warning (informational only, never filters)


class ReportConfig(Config):
    """
    Configuration for generating HTML reports from annotated parquet files.    The report asset depends on module annotation outputs and produces
    a self-contained HTML report.
    """
    user_name: Optional[str] = None  # Override partition-derived user name
    sample_name: Optional[str] = None  # Override partition-derived sample name
    modules: Optional[list[str]] = None  # Specific modules to include (None = all available)
    output_path: Optional[str] = None  # Custom output path (default: data/output/users/{partition}/reports/)