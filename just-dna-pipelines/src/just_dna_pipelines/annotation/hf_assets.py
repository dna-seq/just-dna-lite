"""
Dagster assets for HuggingFace module annotation.

These assets annotate user VCF files with modules from the
just-dna-seq/annotators HuggingFace repository.

The modules are self-contained - they include all annotation data
and don't require Ensembl joins.
"""

from pathlib import Path

from dagster import (
    asset,
    AssetExecutionContext,
    Output,
    MetadataValue,
    AssetIn,
    AssetSpec,
)

from just_dna_pipelines.annotation.assets import user_vcf_partitions
from just_dna_pipelines.annotation.configs import HfModuleAnnotationConfig
from just_dna_pipelines.annotation.hf_modules import (
    AnnotatorModule,
    ModuleTable,
    HF_REPO_ID,
    AnnotationManifest,
)
from just_dna_pipelines.annotation.hf_logic import annotate_vcf_with_all_modules
from just_dna_pipelines.annotation.resources import ensure_vcf_in_user_input_dir


# ============================================================================
# SOURCE ASSETS - HUGGINGFACE ANNOTATOR MODULES
# ============================================================================

# External source asset representing the HuggingFace annotators repository
hf_annotators_dataset = AssetSpec(
    key="hf_annotators_dataset",
    description="Remote annotator modules on HuggingFace Hub (just-dna-seq/annotators). "
                "Contains longevitymap, lipidmetabolism, vo2max, superhuman, coronary, drugs modules.",
    metadata={
        "source": "HuggingFace Hub",
        "repo_id": HF_REPO_ID,
        "type": "external_dataset",
        "url": f"https://huggingface.co/datasets/{HF_REPO_ID}",
        "modules": ", ".join(m.value for m in AnnotatorModule.all_modules()),
    },
)


# ============================================================================
# USER MODULE ANNOTATION ASSET
# ============================================================================

@asset(
    description="User VCF annotated with HuggingFace modules. "
                "Produces one parquet file per selected module containing genotype-specific annotations.",
    compute_kind="polars",
    partitions_def=user_vcf_partitions,
    io_manager_key="user_asset_io_manager",
    ins={
        "user_vcf_source": AssetIn(),  # Partition dependency for lineage
    },
    deps=[hf_annotators_dataset],  # Lineage to HF source
    metadata={
        "partition_type": "user",
        "output_format": "parquet",
        "storage": "output",
        "annotation_source": "huggingface_modules",
    },
)
def user_hf_module_annotations(
    context: AssetExecutionContext,
    user_vcf_source: dict,
    config: HfModuleAnnotationConfig,
) -> Output[Path]:
    """
    Annotate user VCF with selected HuggingFace modules.
    
    This asset:
    1. Reads the user's VCF with FORMAT fields (including genotype)
    2. For each selected module, joins with the weights table on rsid + genotype
    3. Outputs one parquet file per module
    4. Returns a manifest describing all outputs
    
    The genotype column is computed from GT field as List[String] sorted alphabetically,
    matching the format in the HF modules.
    
    Output structure:
    data/output/users/{user}/{sample}/modules/
    ├── longevitymap_weights.parquet
    ├── lipidmetabolism_weights.parquet
    ├── ...
    └── manifest.json
    """
    logger = context.log
    partition_key = context.partition_key
    
    logger.info(f"HF Module annotation for partition: {partition_key}")
    logger.info(f"VCF source metadata: {user_vcf_source}")
    
    # Parse partition key
    if "/" in partition_key:
        user_name, sample_name = partition_key.split("/", 1)
    else:
        user_name = partition_key
        sample_name = config.sample_name
    
    # Override with config if provided
    user_name = config.user_name or user_name
    sample_name = config.sample_name or sample_name
    
    vcf_path = Path(config.vcf_path)
    
    # Ensure VCF is in expected directory
    vcf_path = ensure_vcf_in_user_input_dir(vcf_path, user_name, logger)
    
    # Run annotation with all selected modules
    manifest, metadata_dict = annotate_vcf_with_all_modules(
        logger=logger,
        vcf_path=vcf_path,
        config=config,
        user_name=user_name,
        sample_name=sample_name,
    )
    
    # Add partition metadata
    metadata_dict["partition_key"] = MetadataValue.text(partition_key)
    
    # Return the manifest path (directory containing all module outputs)
    output_dir = Path(manifest.modules[0].weights_path).parent if manifest.modules else Path(config.output_dir or "")
    
    return Output(output_dir, metadata=metadata_dict)


# ============================================================================
# CONVENIENCE FUNCTION FOR CREATING MODULE-SPECIFIC SOURCE ASSETS
# ============================================================================

def create_module_source_assets() -> list[AssetSpec]:
    """
    Create source asset specs for each HF module.
    
    These are informational assets showing what modules are available.
    Useful for the Dagster UI to show the full lineage.
    """
    assets = []
    for module in AnnotatorModule.all_modules():
        for table in ModuleTable:
            assets.append(
                AssetSpec(
                    key=["hf_modules", module.value, table.value],
                    description=f"{module.value} {table.value} from HuggingFace annotators",
                    metadata={
                        "module": module.value,
                        "table": table.value,
                        "url": f"hf://datasets/{HF_REPO_ID}/data/{module.value}/{table.value}.parquet",
                    },
                    deps=[hf_annotators_dataset],
                )
            )
    return assets


# Pre-create the module source assets for inclusion in Definitions
hf_module_source_assets = create_module_source_assets()
