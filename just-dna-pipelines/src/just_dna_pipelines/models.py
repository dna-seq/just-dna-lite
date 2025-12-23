from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict
import polars as pl


class ResourceReport(BaseModel):
    """Report on resource usage for a task or flow."""
    name: str
    duration: float
    cpu_usage_percent: float
    peak_memory_mb: float
    memory_delta_mb: float
    start_time: float
    end_time: float
    start_mem: int
    end_mem: int
    memory_delta: int


class SampleInfo(BaseModel):
    """Information about a genomic sample."""
    sample_name: Optional[str] = None  # Optional sample identifier technical name
    sample_description: Optional[str] = None  # Optional human-readable description
    sequencing_type: str = "full genome"  # full genome, methylation array, exome, microarray
    species: str = "Homo sapiens"
    reference_genome: str = "GRCh38"

class ModuleDependency(BaseModel):
    """A dependency on another Just DNA Pipelines module."""
    name: str
    url: str
    version: Optional[str] = None

class ModuleManifest(BaseModel):
    """Manifest for a Just DNA Pipelines module (app)."""
    name: str
    version: str
    description: str = ""
    author: str = ""
    dependencies: List[ModuleDependency] = []
    entrypoint: str = "definitions.py"


class AnnotationResult(BaseModel):
    """Result of an annotation flow."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    annotated_dataframe: pl.LazyFrame
    ensembl_cache_path: Path
    annotated_vcf_path: Optional[Path] = None


class DownloadResult(BaseModel):
    """Result of a download task or flow."""
    ensembl_cache_path: Path


class SplitResult(BaseModel):
    """Result of splitting parquet files by variant type."""
    split_variants_dict: Dict[str, List[Path]]


class PreparationResult(BaseModel):
    """Result of a VCF preparation flow."""
    urls: List[str]
    vcf_local: List[Path]
    vcf_parquet_path: List[Path]
    split_variants_dict: Optional[Dict[str, List[Path]]] = None


class SingleUploadResult(BaseModel):
    """Result of uploading a single file to Hugging Face Hub."""
    file: str
    uploaded: bool
    reason: str
    local_size: int
    remote_size: Optional[int] = None
    path_in_repo: Optional[str] = None


class BatchUploadResult(BaseModel):
    """Result of uploading multiple files to Hugging Face Hub."""
    uploaded_files: List[SingleUploadResult]
    num_uploaded: int
    num_skipped: int

