"""
Dagster jobs for annotation pipelines.

Jobs define complete workflows that can be triggered manually or scheduled.
"""

from dagster import job, AssetSelection, define_asset_job

from just_dna_pipelines.annotation.ops import annotate_user_vcf_op, annotate_user_vcf_duckdb_op


@job(
    description="Annotate user VCF files with Ensembl annotations. Use this for per-user processing.",
    tags={"multi-user": "true", "vcf": "annotation"},
)
def annotate_vcf_job():
    """
    Job for annotating user VCF files.
    
    This is the pattern for multi-user scenarios:
    - The op reads the Ensembl cache directly from disk
    - No complex asset loading - just use the cache path
    - Each job run processes one user's VCF
    """
    annotate_user_vcf_op()


@job(
    description="Annotate user VCF files using DuckDB. Faster for large datasets.",
    tags={"multi-user": "true", "vcf": "annotation", "duckdb": "true"},
)
def annotate_vcf_duckdb_job():
    """
    Ad-hoc job for annotating user VCF files using DuckDB.
    
    This matches the pattern of annotate_vcf_job but uses the
    DuckDB engine for faster joins.
    """
    annotate_user_vcf_duckdb_op()


build_ensembl_duckdb_job = define_asset_job(
    name="build_ensembl_duckdb_job",
    selection=AssetSelection.assets("ensembl_duckdb"),
    description="Build DuckDB database from Ensembl Parquet annotations for faster queries.",
    tags={"reference": "true", "duckdb": "true"},
)

