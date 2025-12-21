"""Prefect-based preparation pipelines for genomic data sources."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any

from prefect import task, flow, get_run_logger
import polars as pl
from platformdirs import user_cache_dir

from genobear.pipelines.registry import store, PipelineCategory
from genobear.runtime import prefect_flow_run
from genobear.preparation.vcf_downloader import (
    list_paths,
    download_path,
    convert_to_parquet,
    validate_downloads_and_parquet,
)
from genobear.preparation.huggingface_uploader import (
    collect_parquet_files,
    upload_parquet_to_hf,
)
from genobear.preparation.dataset_card_generator import (
    generate_clinvar_card,
    generate_ensembl_card,
)

# Prefect tasks for preparation steps
list_paths_task = task(list_paths, name="List Remote Paths")
download_path_task = task(download_path, name="Download Path")
convert_to_parquet_task = task(convert_to_parquet, name="Convert to Parquet")
validate_task = task(validate_downloads_and_parquet, name="Validate Downloads")

@task(name="Split Parquet Files")
def split_parquets_task(
    parquet_paths: List[Path],
    explode_snv_alt: bool = True,
    write_to: Optional[Path] = None,
) -> Dict[str, List[Path]]:
    """Split parquet files by variant type (TSA)."""
    from genobear.preparation.vcf_parquet_splitter import split_variants_by_tsa
    
    results = {}
    for p in parquet_paths:
        split_dict = split_variants_by_tsa(
            parquet_path=p,
            explode_snv_alt=explode_snv_alt,
            write_to=write_to,
        )
        for k, v in split_dict.items():
            if k not in results:
                results[k] = []
            if isinstance(v, list):
                results[k].extend(v)
            else:
                results[k].append(v)
    return results


def get_default_dest_dir() -> Path:
    """Get the default destination directory for downloads."""
    root_dir = Path("data") / "input"
    root_dir.mkdir(parents=True, exist_ok=True)
    return root_dir


@store.register(
    name="prepare_vcf_source",
    description="Generic flow to download, convert, and optionally split VCF data",
    category=PipelineCategory.PREPARATION,
    author="GenoBear",
    tags=["vcf", "download", "preparation"],
    source="builtin",
)
@flow(name="Prepare VCF Source")
def prepare_vcf_source_flow(
    url: str,
    pattern: Optional[str] = None,
    name: str = "downloads",
    dest_dir: Optional[str] = None,
    with_splitting: bool = False,
    explode_snv_alt: bool = True,
    profile: bool = True,
) -> Dict[str, Any]:
    """Generic flow to download, convert, and optionally split VCF data."""
    logger = get_run_logger()
    dest_path = Path(dest_dir) if dest_dir else get_default_dest_dir()
    
    with prefect_flow_run(f"Prepare {name}", profile=profile):
        # 1. List paths
        urls = list_paths_task(url=url, pattern=pattern)
        
        # 2. Download files in parallel
        vcf_local_futures = [
            download_path_task.submit(url=u, name=name, dest_dir=dest_path)
            for u in urls
        ]
        vcf_locals = [f.result() for f in vcf_local_futures]
            
        # 3. Convert to parquet in parallel
        conversion_futures = [
            convert_to_parquet_task.submit(vcf_path=vcf_p)
            for vcf_p in vcf_locals
        ]
        vcf_parquet_paths = [f.result()[1] for f in conversion_futures]
            
        # 4. Validate
        validate_task(urls=urls, vcf_local=vcf_locals, vcf_parquet_path=vcf_parquet_paths)
        
        results = {
            "urls": urls,
            "vcf_local": vcf_locals,
            "vcf_parquet_path": vcf_parquet_paths,
        }
        
        # 5. Optional splitting
        if with_splitting:
            split_results = split_parquets_task(
                parquet_paths=vcf_parquet_paths,
                explode_snv_alt=explode_snv_alt,
                write_to=dest_path / "splitted_variants" if dest_path else None
            )
            results["split_variants_dict"] = split_results
            
        return results


@store.register(
    name="prepare_dbsnp",
    description="Download and prepare dbSNP data",
    category=PipelineCategory.PREPARATION,
    author="GenoBear",
    tags=["dbsnp", "download", "preparation", "vcf"],
    source="builtin",
)
@flow(name="Prepare dbSNP")
def prepare_dbsnp_flow(
    build: str = "GRCh38",
    dest_dir: Optional[str] = None,
    with_splitting: bool = False,
    profile: bool = True,
) -> Dict[str, Any]:
    """Prefect flow for dbSNP preparation."""
    if build == "GRCh38":
        base_url = "https://ftp.ncbi.nlm.nih.gov/snp/latest_release/VCF/"
        pattern = r"GCF_000001405\.40\.gz$"
    elif build == "GRCh37":
        base_url = "https://ftp.ncbi.nlm.nih.gov/snp/latest_release/VCF/"
        pattern = r"GCF_000001405\.25\.gz$"
    else:
        raise ValueError(f"Unsupported build: {build}")
        
    return prepare_vcf_source_flow(
        url=base_url,
        pattern=pattern,
        name=f"dbsnp_{build.lower()}",
        dest_dir=dest_dir,
        with_splitting=with_splitting,
        profile=profile,
    )


@store.register(
    name="prepare_gnomad",
    description="Download and prepare gnomAD data",
    category=PipelineCategory.PREPARATION,
    author="GenoBear",
    tags=["gnomad", "download", "preparation", "vcf"],
    source="builtin",
)
@flow(name="Prepare gnomAD")
def prepare_gnomad_flow(
    version: str = "v4",
    dest_dir: Optional[str] = None,
    with_splitting: bool = False,
    profile: bool = True,
) -> Dict[str, Any]:
    """Prefect flow for gnomAD preparation."""
    if version == "v4":
        base_url = "https://gnomad-public-us-east-1.s3.amazonaws.com/release/4.0/vcf/"
        pattern = r"gnomad\.v4\.0\..+\.vcf\.bgz$"
    elif version == "v3":
        base_url = "https://gnomad-public-us-east-1.s3.amazonaws.com/release/3.1.2/vcf/"
        pattern = r"gnomad\.v3\.1\.2\..+\.vcf\.bgz$"
    else:
        raise ValueError(f"Unsupported version: {version}")
        
    return prepare_vcf_source_flow(
        url=base_url,
        pattern=pattern,
        name=f"gnomad_{version}",
        dest_dir=dest_dir,
        with_splitting=with_splitting,
        profile=profile,
    )

@store.register(
    name="prepare_clinvar",
    description="Download and prepare ClinVar data",
    category=PipelineCategory.PREPARATION,
    author="GenoBear",
    tags=["clinvar", "download", "preparation", "vcf"],
    source="builtin",
)
@flow(name="Prepare ClinVar")
def prepare_clinvar_flow(
    dest_dir: Optional[str] = None,
    with_splitting: bool = False,
    profile: bool = True,
) -> Dict[str, Any]:
    """Prefect flow for ClinVar preparation."""
    return prepare_vcf_source_flow(
        url="https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/",
        pattern=r"clinvar\.vcf\.gz$",
        name="clinvar",
        dest_dir=dest_dir,
        with_splitting=with_splitting,
        profile=profile,
    )

@store.register(
    name="prepare_ensembl",
    description="Download and prepare Ensembl variation data",
    category=PipelineCategory.PREPARATION,
    author="GenoBear",
    tags=["ensembl", "download", "preparation", "vcf"],
    source="builtin",
)
@flow(name="Prepare Ensembl")
def prepare_ensembl_flow(
    dest_dir: Optional[str] = None,
    with_splitting: bool = False,
    pattern: Optional[str] = None,
    profile: bool = True,
) -> Dict[str, Any]:
    """Prefect flow for Ensembl preparation."""
    return prepare_vcf_source_flow(
        url="https://ftp.ensembl.org/pub/current_variation/vcf/homo_sapiens/",
        pattern=pattern or r"homo_sapiens-chr([^.]+)\.vcf\.gz$",
        name="ensembl_variations",
        dest_dir=dest_dir,
        with_splitting=with_splitting,
        profile=profile,
    )
