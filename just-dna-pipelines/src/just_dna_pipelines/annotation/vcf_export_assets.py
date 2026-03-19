"""
Dagster assets for exporting annotated parquets to VCF format.

Produces per-module VCF files, an optional Ensembl VCF, and a combined
VCF with all annotations packed into INFO fields.
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
from just_dna_pipelines.annotation.configs import VcfExportConfig
from just_dna_pipelines.annotation.vcf_export_logic import (
    export_parquet_to_vcf,
    export_combined_vcf,
)
from just_dna_pipelines.annotation.resources import get_user_output_dir
from just_dna_pipelines.runtime import resource_tracker


def _vcf_extension(compression: str) -> str:
    """Return file extension based on compression setting."""
    if compression == "bgz":
        return ".vcf.bgz"
    if compression in ("gz", "gzip"):
        return ".vcf.gz"
    return ".vcf"


@asset(
    description=(
        "Export annotated parquets to VCF format. Produces per-module VCF files, "
        "an optional Ensembl-annotated VCF, and a combined VCF with all annotations "
        "packed into INFO fields."
    ),
    compute_kind="vcf_export",
    group_name="user_exports",
    partitions_def=user_vcf_partitions,
    io_manager_key="user_asset_io_manager",
    ins={
        "user_hf_module_annotations": AssetIn(),
        "user_vcf_normalized": AssetIn(),
    },
    metadata={
        "partition_type": "user",
        "output_format": "vcf",
        "storage": "output",
    },
)
def user_vcf_exports(
    context: AssetExecutionContext,
    user_hf_module_annotations: Path,
    user_vcf_normalized: Path,
    config: VcfExportConfig,
) -> Output[Path]:
    """Export annotated parquets to VCF format.

    Output directory::

        data/output/users/{partition_key}/vcf_exports/
            {module}_annotated.vcf.gz
            ensembl_annotated.vcf.gz   (if Ensembl parquet exists)
            all_annotations.vcf.gz     (combined)
    """
    logger = context.log
    partition_key = context.partition_key

    logger.info(f"VCF export for partition: {partition_key}")

    if "/" in partition_key:
        user_name, sample_name = partition_key.split("/", 1)
    else:
        user_name = partition_key
        sample_name = ""

    user_name = config.user_name or user_name
    sample_name = config.sample_name or sample_name

    ext = _vcf_extension(config.compression)

    modules_dir = user_hf_module_annotations
    if not modules_dir.is_dir():
        modules_dir = modules_dir.parent

    export_dir = get_user_output_dir() / partition_key / "vcf_exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    normalized_path = user_vcf_normalized
    if normalized_path.is_dir():
        candidates = list(normalized_path.glob("*.parquet"))
        if candidates:
            normalized_path = candidates[0]

    with resource_tracker("VCF Export", context=context):
        module_parquets: dict[str, Path] = {}
        exported_files: list[str] = []
        total_rows = 0

        weight_files = sorted(modules_dir.glob("*_weights.parquet"))
        if config.modules:
            allowed = set(config.modules)
            weight_files = [f for f in weight_files if f.stem.replace("_weights", "") in allowed]

        for wf in weight_files:
            module_name = wf.stem.replace("_weights", "")
            vcf_out = export_dir / f"{module_name}_annotated{ext}"

            logger.info(f"Exporting module '{module_name}' -> {vcf_out.name}")
            _, rows = export_parquet_to_vcf(wf, vcf_out)
            module_parquets[module_name] = wf
            exported_files.append(vcf_out.name)
            total_rows += rows
            logger.info(f"  {module_name}: {rows} variants")

        ensembl_parquet: Path | None = None
        sample_dir = get_user_output_dir() / partition_key
        ensembl_candidates = list(sample_dir.glob("*_ensembl_annotated.parquet"))
        if ensembl_candidates:
            ensembl_parquet = ensembl_candidates[0]
            vcf_out = export_dir / f"ensembl_annotated{ext}"
            logger.info(f"Exporting Ensembl annotations -> {vcf_out.name}")
            _, rows = export_parquet_to_vcf(ensembl_parquet, vcf_out)
            exported_files.append(vcf_out.name)
            total_rows += rows
            logger.info(f"  ensembl: {rows} variants")

        if normalized_path.exists() and module_parquets:
            combined_vcf = export_dir / f"all_annotations{ext}"
            logger.info(f"Building combined VCF -> {combined_vcf.name}")
            _, rows = export_combined_vcf(
                normalized_parquet=normalized_path,
                module_parquets=module_parquets,
                vcf_path=combined_vcf,
                ensembl_parquet=ensembl_parquet,
            )
            exported_files.append(combined_vcf.name)
            logger.info(f"  combined: {rows} variants")

    total_size_mb = sum(
        f.stat().st_size for f in export_dir.iterdir() if f.is_file()
    ) / (1024 * 1024)

    metadata_dict = {
        "partition_key": MetadataValue.text(partition_key),
        "user_name": MetadataValue.text(user_name),
        "sample_name": MetadataValue.text(sample_name),
        "export_dir": MetadataValue.path(str(export_dir.absolute())),
        "exported_files": MetadataValue.text(", ".join(exported_files)),
        "file_count": MetadataValue.int(len(exported_files)),
        "total_size_mb": MetadataValue.float(round(total_size_mb, 2)),
        "compression": MetadataValue.text(config.compression),
    }

    logger.info(
        f"VCF export complete: {len(exported_files)} files, "
        f"{total_size_mb:.2f} MB total"
    )

    return Output(export_dir, metadata=metadata_dict)
