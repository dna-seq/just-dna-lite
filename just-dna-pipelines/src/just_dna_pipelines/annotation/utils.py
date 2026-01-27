"""
Utility functions for managing Dagster partitions and VCF discovery.
"""

from pathlib import Path
from dagster import DagsterInstance, success_hook, HookContext


@success_hook
def resource_summary_hook(context: HookContext) -> None:
    """
    Success hook that logs aggregated resource metrics for the entire run.
    
    This provides run-level visibility into:
    - Total duration across all assets
    - Maximum peak memory (bottleneck identification)
    - Average CPU usage
    
    Appears in the run logs at the end of successful runs.
    """
    # Get all events from this run
    run_id = context.run_id
    instance = context.instance
    
    # Query materialization events for this run (Dagster 1.12.x compatible)
    from dagster import DagsterEventType
    
    # Use all_logs instead of get_event_records (EventRecordsFilter doesn't have run_ids in 1.12.x)
    log_entries = instance.all_logs(run_id, of_type=DagsterEventType.ASSET_MATERIALIZATION)
    
    # Extract resource metrics from asset materializations
    total_duration = 0.0
    max_peak_memory = 0.0
    total_cpu = 0.0
    asset_count = 0
    asset_metrics: list[dict] = []
    
    for entry in log_entries:
        # EventLogEntry.asset_materialization returns Optional[AssetMaterialization] directly
        mat = entry.asset_materialization
        if mat is not None:
            metadata = mat.metadata or {}
            
            duration = metadata.get("duration_sec")
            peak_mem = metadata.get("peak_memory_mb")
            cpu = metadata.get("cpu_percent")
            
            if duration is not None or peak_mem is not None:
                asset_name = mat.asset_key.to_user_string()
                asset_info = {"asset": asset_name}
                
                if duration is not None:
                    dur_val = duration.value if hasattr(duration, 'value') else float(duration)
                    total_duration += dur_val
                    asset_info["duration_sec"] = dur_val
                
                if peak_mem is not None:
                    mem_val = peak_mem.value if hasattr(peak_mem, 'value') else float(peak_mem)
                    max_peak_memory = max(max_peak_memory, mem_val)
                    asset_info["peak_memory_mb"] = mem_val
                
                if cpu is not None:
                    cpu_val = cpu.value if hasattr(cpu, 'value') else float(cpu)
                    total_cpu += cpu_val
                    asset_info["cpu_percent"] = cpu_val
                
                asset_metrics.append(asset_info)
                asset_count += 1
    
    if asset_count == 0:
        return
    
    avg_cpu = total_cpu / asset_count if asset_count > 0 else 0.0
    
    # Sort by peak memory to identify bottlenecks
    sorted_by_memory = sorted(asset_metrics, key=lambda x: x.get("peak_memory_mb", 0), reverse=True)
    top_memory_assets = sorted_by_memory[:3]
    
    # Log summary
    context.log.info(
        f"📊 RUN RESOURCE SUMMARY\n"
        f"  Total Duration: {total_duration:.1f}s ({total_duration/60:.1f} min)\n"
        f"  Max Peak Memory: {max_peak_memory:.1f} MB\n"
        f"  Average CPU: {avg_cpu:.1f}%\n"
        f"  Assets with metrics: {asset_count}\n"
        f"  Top memory consumers:\n" +
        "\n".join(f"    - {a['asset']}: {a.get('peak_memory_mb', 0):.1f} MB" for a in top_memory_assets)
    )

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

