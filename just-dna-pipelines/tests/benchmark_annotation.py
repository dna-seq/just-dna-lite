import sys
import os
from pathlib import Path
import logging
from rich.console import Console
from rich.table import Table
import multiprocessing
from typing import Dict, Any

# Add just-dna-pipelines/src to path
just_dna_pipelines_src = Path("just-dna-pipelines/src").absolute()
sys.path.append(str(just_dna_pipelines_src))

from just_dna_pipelines.annotation.logic import annotate_vcf_with_ensembl, annotate_vcf_with_duckdb
from just_dna_pipelines.annotation.configs import AnnotationConfig
from just_dna_pipelines.annotation.duckdb_assets import ensure_ensembl_duckdb_exists
from just_dna_pipelines.annotation.resources import get_default_ensembl_cache_dir

def run_polars_task(vcf_path: Path, ensembl_cache: Path, config: AnnotationConfig, result_dict: Dict):
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger = logging.getLogger("benchmark.polars")
    try:
        _, metadata = annotate_vcf_with_ensembl(
            logger=logger,
            vcf_path=vcf_path,
            ensembl_cache=ensembl_cache,
            config=config,
            user_name="benchmark_user",
            sample_name="polars"
        )
        # Extract raw values from MetadataValue objects
        raw_metadata = {}
        for k, v in metadata.items():
            if hasattr(v, 'value'):
                raw_metadata[k] = v.value
            else:
                raw_metadata[k] = v
        result_dict["polars"] = raw_metadata
    except Exception as e:
        logger.error(f"Polars failed: {e}")
        import traceback
        traceback.print_exc()

def run_duckdb_task(vcf_path: Path, duckdb_path: Path, config: AnnotationConfig, result_dict: Dict):
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger = logging.getLogger("benchmark.duckdb")
    try:
        _, metadata = annotate_vcf_with_duckdb(
            logger=logger,
            vcf_path=vcf_path,
            duckdb_path=duckdb_path,
            config=config,
            user_name="benchmark_user",
            sample_name="duckdb"
        )
        # Extract raw values from MetadataValue objects
        raw_metadata = {}
        for k, v in metadata.items():
            if hasattr(v, 'value'):
                raw_metadata[k] = v.value
            else:
                raw_metadata[k] = v
        result_dict["duckdb"] = raw_metadata
    except Exception as e:
        logger.error(f"DuckDB failed: {e}")
        import traceback
        traceback.print_exc()

def run_benchmark():
    console = Console()
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    logger = logging.getLogger("benchmark")
    
    vcf_path = Path("data/input/users/antonkulaga/antonkulaga.vcf")
    if not vcf_path.exists():
        logger.warning(f"VCF {vcf_path} not found, falling back to test VCF")
        vcf_path = Path("data/input/tests/antku_small.vcf")
        
    logger.info(f"🚀 Benchmarking with VCF: {vcf_path} ({vcf_path.stat().st_size / 1024 / 1024:.2f} MB)")
    
    ensembl_cache = get_default_ensembl_cache_dir()
    logger.info(f"📂 Using Ensembl cache: {ensembl_cache}")
    
    logger.info("🔍 Ensuring Ensembl DuckDB exists...")
    duckdb_path = ensure_ensembl_duckdb_exists(logger)
    
    config = AnnotationConfig(
        vcf_path=str(vcf_path),
        user_name="benchmark_user",
    )
    
    manager = multiprocessing.Manager()
    shared_results = manager.dict()
    
    # Run Polars in separate process
    logger.info("\n⚡ Running Polars (Streaming) in separate process...")
    p = multiprocessing.Process(target=run_polars_task, args=(vcf_path, ensembl_cache, config, shared_results))
    p.start()
    p.join()
    
    # Run DuckDB in separate process
    logger.info("\n🦆 Running DuckDB (Streaming) in separate process...")
    p = multiprocessing.Process(target=run_duckdb_task, args=(vcf_path, duckdb_path, config, shared_results))
    p.start()
    p.join()
    
    # Collect results
    results = []
    if "polars" in shared_results:
        m = shared_results["polars"]
        results.append({
            "Engine": "Polars (Streaming)",
            "Duration (s)": f"{m.get('duration_sec', 0):.2f}",
            "Peak RAM (MB)": f"{m.get('peak_memory_mb', 0):.2f}",
            "CPU (%)": f"{m.get('cpu_percent', 0):.1f}",
            "Output Size (MB)": f"{m.get('file_size_mb', 0):.2f}"
        })
        
    if "duckdb" in shared_results:
        m = shared_results["duckdb"]
        results.append({
            "Engine": "DuckDB (Streaming)",
            "Duration (s)": f"{m.get('duration_sec', 0):.2f}",
            "Peak RAM (MB)": f"{m.get('peak_memory_mb', 0):.2f}",
            "CPU (%)": f"{m.get('cpu_percent', 0):.1f}",
            "Output Size (MB)": f"{m.get('file_size_mb', 0):.2f}"
        })
        
    # Display results
    print("\n")
    table = Table(title=f"Annotation Benchmark (VCF: {vcf_path.name})")
    if results:
        for key in results[0].keys():
            table.add_column(key, justify="right" if key != "Engine" else "left")
        for res in results:
            table.add_row(*[str(val) for val in res.values()])
            
        console.print(table)
        
        # Add summary comparison
        if len(results) == 2:
            p_time = float(results[0]["Duration (s)"])
            d_time = float(results[1]["Duration (s)"])
            p_mem = float(results[0]["Peak RAM (MB)"])
            d_mem = float(results[1]["Peak RAM (MB)"])
            
            time_diff = (p_time / d_time) if d_time > 0 else 0
            mem_diff = (p_mem / d_mem) if d_mem > 0 else 0
            
            console.print(f"\n[bold green]Summary:[/bold green]")
            if time_diff > 1:
                console.print(f"  - DuckDB is [bold]{time_diff:.1f}x faster[/bold] than Polars")
            else:
                console.print(f"  - Polars is [bold]{(1/time_diff):.1f}x faster[/bold] than DuckDB")
                
            if mem_diff > 1:
                console.print(f"  - DuckDB uses [bold]{mem_diff:.1f}x less memory[/bold] than Polars")
            elif mem_diff < 1:
                console.print(f"  - Polars uses [bold]{(1/mem_diff):.1f}x less memory[/bold] than DuckDB")
            else:
                console.print(f"  - Both engines use similar memory")
    else:
        console.print("[red]No results to display[/red]")

if __name__ == "__main__":
    run_benchmark()
