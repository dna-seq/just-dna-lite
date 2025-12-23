"""
Dagster sensors for annotation pipelines.

Sensors automatically detect changes and trigger materializations.
"""

from pathlib import Path

from dagster import (
    sensor,
    SensorEvaluationContext,
    RunRequest,
    SkipReason,
    DagsterRunStatus,
)

from just_dna_pipelines.annotation.assets import user_vcf_partitions
from just_dna_pipelines.annotation.resources import get_user_input_dir


@sensor(
    name="discover_user_vcf_files",
    description="Automatically discovers VCF files in user input directories and creates partitions for them.",
    minimum_interval_seconds=60,  # Check every minute
)
def discover_user_vcf_sensor(context: SensorEvaluationContext):
    """
    Sensor that scans data/input/users/ for VCF files and ensures
    partitions exist for each user/sample combination.
    
    Partition naming: {user_name}/{sample_name}
    - user_name: directory name under data/input/users/
    - sample_name: VCF filename without extension
    """
    user_input_dir = get_user_input_dir()
    
    if not user_input_dir.exists():
        return SkipReason(f"User input directory does not exist: {user_input_dir}")
    
    # Scan for all VCF files
    discovered_partitions = []
    
    for user_dir in user_input_dir.iterdir():
        if not user_dir.is_dir():
            continue
            
        user_name = user_dir.name
        
        # Find all VCF files in this user's directory
        vcf_files = list(user_dir.glob("*.vcf")) + list(user_dir.glob("*.vcf.gz"))
        
        for vcf_file in vcf_files:
            # Sample name is the filename without extension(s)
            sample_name = vcf_file.name.replace(".vcf.gz", "").replace(".vcf", "")
            partition_key = f"{user_name}/{sample_name}"
            discovered_partitions.append(partition_key)
    
    if not discovered_partitions:
        return SkipReason("No VCF files found in user input directories")
    
    # Check which partitions need to be added
    existing_partitions = set(
        context.instance.get_dynamic_partitions(user_vcf_partitions.name)
    )
    new_partitions = [p for p in discovered_partitions if p not in existing_partitions]
    
    if new_partitions:
        # Add new partitions
        context.instance.add_dynamic_partitions(
            user_vcf_partitions.name,
            new_partitions
        )
        context.log.info(f"Added {len(new_partitions)} new partitions: {new_partitions}")
        return SkipReason(
            f"Discovered and added {len(new_partitions)} new VCF partitions: {', '.join(new_partitions)}"
        )
    else:
        return SkipReason(
            f"All {len(discovered_partitions)} VCF files already have partitions"
        )

