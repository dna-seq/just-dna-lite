"""
Dagster assets for generating HTML reports from annotated parquet outputs.

Report assets depend on the corresponding module annotation assets
and produce self-contained HTML reports that can be downloaded or shared.
"""

from pathlib import Path

from dagster import (
    asset,
    AssetExecutionContext,
    AssetIn,
    Output,
    MetadataValue,
)

from just_dna_pipelines.annotation.assets import user_vcf_partitions
from just_dna_pipelines.annotation.configs import ReportConfig
from just_dna_pipelines.annotation.report_logic import generate_longevity_report
from just_dna_pipelines.annotation.resources import get_user_output_dir
from just_dna_pipelines.runtime import resource_tracker


@asset(
    description="Longevity HTML report generated from annotated module parquets. "
                "Produces a self-contained HTML file with variant tables grouped by longevity pathway.",
    compute_kind="report",
    group_name="user_reports",
    partitions_def=user_vcf_partitions,
    io_manager_key="user_asset_io_manager",
    ins={
        "user_hf_module_annotations": AssetIn(),
    },
    metadata={
        "partition_type": "user",
        "output_format": "html",
        "storage": "output",
        "report_type": "longevity",
    },
)
def user_longevity_report(
    context: AssetExecutionContext,
    user_hf_module_annotations: Path,
    config: ReportConfig,
) -> Output[Path]:
    """
    Generate a longevity HTML report from annotated module parquets.

    This asset depends on `user_hf_module_annotations` which produces
    per-module parquet files. The report:
    1. Reads each module's weights parquet
    2. Enriches with annotations (gene, category) and studies from HuggingFace
    3. Groups longevitymap variants by longevity pathway category
    4. Renders a self-contained HTML report with expandable variant details

    Output:
        data/output/users/{partition_key}/reports/longevity_report.html
    """
    logger = context.log
    partition_key = context.partition_key

    logger.info(f"Generating longevity report for partition: {partition_key}")
    logger.info(f"Module annotations directory: {user_hf_module_annotations}")

    # Parse partition key for user/sample names
    if "/" in partition_key:
        user_name, sample_name = partition_key.split("/", 1)
    else:
        user_name = partition_key
        sample_name = ""

    # Override with config if provided
    user_name = config.user_name or user_name
    sample_name = config.sample_name or sample_name

    # Resolve modules directory (where the parquets live)
    modules_dir = user_hf_module_annotations
    if not modules_dir.is_dir():
        # If the IO manager returned a file path, use its parent
        modules_dir = modules_dir.parent

    # Determine output path
    if config.output_path:
        output_path = Path(config.output_path)
    else:
        output_dir = get_user_output_dir() / partition_key / "reports"
        output_path = output_dir / "longevity_report.html"

    # Get selected modules
    module_names = config.modules if config.modules else None

    with resource_tracker("Generate Longevity Report", context=context):
        report_path = generate_longevity_report(
            modules_dir=modules_dir,
            output_path=output_path,
            module_names=module_names,
            user_name=user_name,
            sample_name=sample_name,
        )

    # Compute report size
    report_size_kb = report_path.stat().st_size / 1024

    # Count parquet files used
    parquet_files = list(modules_dir.glob("*_weights.parquet"))

    metadata_dict = {
        "partition_key": MetadataValue.text(partition_key),
        "user_name": MetadataValue.text(user_name),
        "sample_name": MetadataValue.text(sample_name),
        "report_path": MetadataValue.path(str(report_path.absolute())),
        "report_size_kb": MetadataValue.float(round(report_size_kb, 1)),
        "modules_dir": MetadataValue.path(str(modules_dir.absolute())),
        "parquet_files_used": MetadataValue.int(len(parquet_files)),
        "module_names": MetadataValue.text(
            ", ".join(f.stem.replace("_weights", "") for f in parquet_files)
        ),
    }

    logger.info(f"Report generated: {report_path} ({report_size_kb:.1f} KB)")

    return Output(report_path, metadata=metadata_dict)
