"""Parse VCF files into Polars LazyFrames for annotation."""

from pathlib import Path
from typing import Union

import polars as pl
from eliot import start_action

from genobear.io import read_vcf_file


def load_vcf_as_lazy_frame(
    vcf_path: Union[str, Path],
    info_fields: Union[list[str], None] = None,
) -> pl.LazyFrame:
    """
    Load VCF file as a Polars LazyFrame for annotation.
    
    This function reads the VCF file and returns a LazyFrame that can be
    used for joining with annotation data.
    
    Args:
        vcf_path: Path to the VCF file (can be .vcf or .vcf.gz)
        info_fields: List of INFO fields to extract (if None, extracts all)
        
    Returns:
        Polars LazyFrame containing VCF data
        
    Example:
        >>> vcf_lf = load_vcf_as_lazy_frame("sample.vcf.gz")
        >>> print(vcf_lf.schema)
    """
    with start_action(
        action_type="load_vcf_as_lazy_frame",
        vcf_path=str(vcf_path)
    ) as action:
        # Read VCF file using genobear's read_vcf_file
        vcf_lazy = read_vcf_file(vcf_path, info_fields=info_fields, save_parquet=None)
        
        # Get schema info for logging
        schema = vcf_lazy.collect_schema()
        
        action.log(
            message_type="info",
            step="vcf_loaded",
            num_columns=len(schema),
            columns=list(schema.names())
        )
        
        return vcf_lazy

