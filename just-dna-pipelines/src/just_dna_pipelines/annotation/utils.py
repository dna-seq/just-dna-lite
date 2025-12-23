"""
Utility functions for managing Dagster partitions and VCF discovery.
"""

from pathlib import Path
from dagster import DagsterInstance

from just_dna_pipelines.annotation.assets import user_vcf_partitions
from just_dna_pipelines.annotation.resources import get_user_input_dir


def discover_vcf_partitions(verbose: bool = True) -> list[str]:
    """
    Scan data/input/users/ for VCF files and return partition keys.
    
    Returns:
        List of partition keys in format: {user_name}/{sample_name}
    """
    user_input_dir = get_user_input_dir()
    
    if not user_input_dir.exists():
        if verbose:
            print(f"❌ User input directory does not exist: {user_input_dir}")
        return []
    
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
            
            if verbose:
                print(f"  📄 Found: {vcf_file.relative_to(user_input_dir.parent.parent)} → partition: {partition_key}")
    
    return discovered_partitions


def sync_vcf_partitions(instance: DagsterInstance = None, verbose: bool = True) -> tuple[list[str], list[str]]:
    """
    Discover VCF files and add missing partitions to Dagster.
    
    Returns:
        Tuple of (new_partitions, existing_partitions)
    """
    if instance is None:
        instance = DagsterInstance.get()
    
    discovered = discover_vcf_partitions(verbose=verbose)
    
    if not discovered:
        if verbose:
            print("\n⚠️  No VCF files found in data/input/users/")
        return [], []
    
    # Get existing partitions
    existing = set(instance.get_dynamic_partitions(user_vcf_partitions.name))
    new = [p for p in discovered if p not in existing]
    
    if new:
        if verbose:
            print(f"\n✅ Adding {len(new)} new partitions:")
            for p in new:
                print(f"   + {p}")
        
        instance.add_dynamic_partitions(user_vcf_partitions.name, new)
    else:
        if verbose:
            print(f"\n✓ All {len(discovered)} VCF files already have partitions")
    
    return new, list(existing)


def list_vcf_partitions(instance: DagsterInstance = None) -> list[str]:
    """List all existing VCF partitions in Dagster."""
    if instance is None:
        instance = DagsterInstance.get()
    
    return instance.get_dynamic_partitions(user_vcf_partitions.name)

