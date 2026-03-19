"""
Logic for exporting annotated parquets back to VCF format.

Uses polars-bio's write_vcf when possible (DataFrames that originated from
scan_vcf retain coordinate-system metadata). For parquets read via
scan_parquet (no metadata), falls back to manual VCF construction.
"""

import gzip
from datetime import datetime
from pathlib import Path
from typing import Optional

import polars as pl
import polars_bio as pb
from eliot import start_action

VCF_CORE_COLUMNS = {"chrom", "start", "end", "id", "ref", "alt", "qual", "filter"}

POLARS_TO_VCF_TYPE: dict[type, str] = {
    pl.Int8: "Integer",
    pl.Int16: "Integer",
    pl.Int32: "Integer",
    pl.Int64: "Integer",
    pl.UInt8: "Integer",
    pl.UInt16: "Integer",
    pl.UInt32: "Integer",
    pl.UInt64: "Integer",
    pl.Float32: "Float",
    pl.Float64: "Float",
    pl.Boolean: "Flag",
}


def _polars_dtype_to_vcf_type(dtype: pl.DataType) -> str:
    """Map a polars dtype to a VCF INFO Type string."""
    return POLARS_TO_VCF_TYPE.get(type(dtype), "String")


def _prepare_df_for_vcf(
    lf: pl.LazyFrame,
    annotation_columns: Optional[list[str]] = None,
) -> tuple[pl.DataFrame, list[str]]:
    """Prepare a LazyFrame for VCF export.

    - Renames ``rsid`` -> ``id`` (VCF convention)
    - Detects annotation columns (non-core VCF columns)
    - Packs annotation columns into a single ``INFO`` string column
    - Drops annotation and non-VCF columns, keeps VCF core + INFO

    Returns the collected DataFrame and the list of annotation field names
    used in the INFO column.
    """
    schema = lf.collect_schema()
    col_names = schema.names()

    rename_map: dict[str, str] = {}
    if "rsid" in col_names and "id" not in col_names:
        rename_map["rsid"] = "id"

    if rename_map:
        lf = lf.rename(rename_map)
        col_names = [rename_map.get(c, c) for c in col_names]

    if annotation_columns is None:
        annotation_columns = [c for c in col_names if c not in VCF_CORE_COLUMNS]

    if not annotation_columns:
        return lf.collect(), []

    info_parts: list[pl.Expr] = []
    for col in annotation_columns:
        dtype = schema.get(col if col not in rename_map.values() else col)
        if dtype is None:
            original = next((k for k, v in rename_map.items() if v == col), col)
            dtype = schema.get(original)
        info_parts.append(
            pl.concat_str(
                [pl.lit(f"{col}="), pl.col(col).cast(pl.Utf8).fill_null(".")],
                separator="",
            )
        )

    lf = lf.with_columns(
        pl.concat_str(info_parts, separator=";").alias("INFO")
    )

    keep_cols = [c for c in ["chrom", "start", "end", "id", "ref", "alt", "qual", "filter"] if c in col_names or c in rename_map.values()]
    keep_cols.append("INFO")
    lf = lf.select(keep_cols)

    return lf.collect(), annotation_columns


def _write_vcf_manual(
    df: pl.DataFrame,
    vcf_path: Path,
    info_fields: list[tuple[str, str]],
    compress: bool = True,
) -> int:
    """Write a DataFrame to VCF using manual string formatting.

    Args:
        df: DataFrame with VCF core columns + ``INFO`` string column.
        vcf_path: Output path (.vcf or .vcf.gz).
        info_fields: List of ``(field_name, vcf_type)`` for ##INFO header lines.
        compress: Whether to gzip the output.

    Returns:
        Number of data rows written.
    """
    vcf_path.parent.mkdir(parents=True, exist_ok=True)

    header_lines = [
        "##fileformat=VCFv4.3",
        f'##source=just-dna-pipelines-vcf-export {datetime.now().strftime("%Y-%m-%d")}',
    ]
    for field_name, vcf_type in info_fields:
        header_lines.append(
            f'##INFO=<ID={field_name},Number=1,Type={vcf_type},Description="{field_name} annotation">'
        )

    col_header = "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO"
    header_lines.append(col_header)
    header_text = "\n".join(header_lines) + "\n"

    schema_names = df.columns
    has_end = "end" in schema_names
    has_qual = "qual" in schema_names
    has_filter = "filter" in schema_names
    has_info = "INFO" in schema_names

    select_cols = ["chrom", "start"]
    if has_end:
        select_cols.append("end")
    select_cols.append("id")
    select_cols.extend(["ref", "alt"])
    if has_qual:
        select_cols.append("qual")
    if has_filter:
        select_cols.append("filter")
    if has_info:
        select_cols.append("INFO")

    row_df = df.select([
        pl.col("chrom").cast(pl.Utf8).fill_null("."),
        pl.col("start").cast(pl.Utf8),
        pl.col("id").cast(pl.Utf8).fill_null("."),
        pl.col("ref").cast(pl.Utf8).fill_null("."),
        pl.col("alt").cast(pl.Utf8).fill_null("."),
        (pl.col("qual").cast(pl.Utf8).fill_null(".") if has_qual else pl.lit(".")),
        (pl.col("filter").cast(pl.Utf8).fill_null(".") if has_filter else pl.lit(".")),
        (pl.col("INFO").fill_null(".") if has_info else pl.lit(".")),
    ])

    tsv_text = row_df.write_csv(separator="\t", include_header=False)

    opener = gzip.open if compress else open
    mode = "wt" if compress else "w"
    with opener(str(vcf_path), mode) as fh:
        fh.write(header_text)
        fh.write(tsv_text)

    return len(df)


def export_parquet_to_vcf(
    parquet_path: Path,
    vcf_path: Path,
    annotation_columns: Optional[list[str]] = None,
) -> tuple[Path, int]:
    """Export an annotated parquet to VCF format.

    Tries ``pb.write_vcf()`` first (fast, preserves coordinate metadata).
    Falls back to manual VCF construction if polars-bio fails (e.g. missing
    coordinate metadata from a ``scan_parquet``-sourced DataFrame).

    Args:
        parquet_path: Input annotated parquet.
        vcf_path: Output VCF path (.vcf.gz for compressed).
        annotation_columns: Columns to pack into INFO. If None, auto-detected
            (all non-core VCF columns).

    Returns:
        ``(vcf_path, row_count)``
    """
    with start_action(
        action_type="export_parquet_to_vcf",
        parquet_path=str(parquet_path),
        vcf_path=str(vcf_path),
    ) as action:
        lf = pl.scan_parquet(parquet_path)
        schema = lf.collect_schema()

        df, info_field_names = _prepare_df_for_vcf(lf, annotation_columns)
        row_count = len(df)

        info_fields_typed = [
            (name, _polars_dtype_to_vcf_type(schema.get(name, pl.Utf8)))
            for name in info_field_names
        ]

        try:
            pb.write_vcf(df, str(vcf_path))
            action.log(
                message_type="info",
                step="write_vcf_polars_bio",
                rows=row_count,
            )
        except Exception as exc:
            action.log(
                message_type="warning",
                step="write_vcf_fallback",
                reason=str(exc),
            )
            compress = str(vcf_path).endswith(".gz")
            _write_vcf_manual(df, vcf_path, info_fields_typed, compress=compress)
            action.log(
                message_type="info",
                step="write_vcf_manual_complete",
                rows=row_count,
            )

        return vcf_path, row_count


def export_combined_vcf(
    normalized_parquet: Path,
    module_parquets: dict[str, Path],
    vcf_path: Path,
    ensembl_parquet: Optional[Path] = None,
) -> tuple[Path, int]:
    """Build a combined VCF from the normalized parquet + all annotation parquets.

    Starting from the full normalized VCF (all user variants), left-joins each
    module's weights parquet on ``(chrom, start, ref, alt)`` and adds annotation
    columns prefixed with the module name. Ensembl annotations are joined
    similarly if available.

    Args:
        normalized_parquet: Path to ``user_vcf_normalized.parquet``.
        module_parquets: ``{module_name: parquet_path}`` for each HF module.
        vcf_path: Output VCF path.
        ensembl_parquet: Optional Ensembl annotated parquet.

    Returns:
        ``(vcf_path, row_count)``
    """
    with start_action(
        action_type="export_combined_vcf",
        vcf_path=str(vcf_path),
        modules=list(module_parquets.keys()),
        has_ensembl=ensembl_parquet is not None,
    ) as action:
        base_lf = pl.scan_parquet(normalized_parquet)
        base_schema = base_lf.collect_schema()

        join_cols = ["chrom", "start", "ref", "alt"]
        available_join_cols = [c for c in join_cols if c in base_schema.names()]
        if len(available_join_cols) < 2:
            action.log(
                message_type="warning",
                step="insufficient_join_columns",
                available=available_join_cols,
            )
            return export_parquet_to_vcf(normalized_parquet, vcf_path)

        for module_name, mod_path in module_parquets.items():
            mod_lf = pl.scan_parquet(mod_path)
            mod_schema = mod_lf.collect_schema()

            mod_join_cols = [c for c in available_join_cols if c in mod_schema.names()]
            if not mod_join_cols:
                action.log(
                    message_type="warning",
                    step="skip_module_no_join_cols",
                    module=module_name,
                )
                continue

            annotation_cols = [
                c for c in mod_schema.names()
                if c not in VCF_CORE_COLUMNS
                and c not in {"rsid", "genotype", "GT", "GQ", "DP", "AD", "VAF", "PL", "MIN_DP"}
                and c not in available_join_cols
            ]

            if not annotation_cols:
                continue

            rename_map = {c: f"{module_name}_{c}" for c in annotation_cols}
            select_cols = mod_join_cols + annotation_cols
            mod_subset = mod_lf.select(select_cols).rename(rename_map)

            mod_subset = mod_subset.unique(subset=mod_join_cols)

            base_lf = base_lf.join(
                mod_subset,
                on=mod_join_cols,
                how="left",
            )

            action.log(
                message_type="info",
                step="module_joined",
                module=module_name,
                annotation_cols=list(rename_map.values()),
            )

        if ensembl_parquet is not None and ensembl_parquet.exists():
            ens_lf = pl.scan_parquet(ensembl_parquet)
            ens_schema = ens_lf.collect_schema()

            ens_join_cols = [c for c in available_join_cols if c in ens_schema.names()]
            if ens_join_cols:
                ens_annotation_cols = [
                    c for c in ens_schema.names()
                    if c not in VCF_CORE_COLUMNS
                    and c not in {"rsid", "genotype", "GT", "GQ", "DP", "AD", "VAF", "PL", "MIN_DP"}
                    and c not in available_join_cols
                ]
                if ens_annotation_cols:
                    ens_rename = {c: f"ensembl_{c}" for c in ens_annotation_cols}
                    ens_subset = ens_lf.select(ens_join_cols + ens_annotation_cols).rename(ens_rename)
                    ens_subset = ens_subset.unique(subset=ens_join_cols)
                    base_lf = base_lf.join(ens_subset, on=ens_join_cols, how="left")
                    action.log(
                        message_type="info",
                        step="ensembl_joined",
                        annotation_cols=list(ens_rename.values()),
                    )

        schema = base_lf.collect_schema()
        annotation_columns = [
            c for c in schema.names()
            if c not in VCF_CORE_COLUMNS
            and c not in {"rsid", "genotype", "GT", "GQ", "DP", "AD", "VAF", "PL", "MIN_DP"}
        ]

        df, info_field_names = _prepare_df_for_vcf(base_lf, annotation_columns)
        row_count = len(df)

        info_fields_typed = [
            (name, _polars_dtype_to_vcf_type(schema.get(name, pl.Utf8)))
            for name in info_field_names
        ]

        try:
            pb.write_vcf(df, str(vcf_path))
            action.log(message_type="info", step="combined_write_vcf_polars_bio", rows=row_count)
        except Exception as exc:
            action.log(message_type="warning", step="combined_write_vcf_fallback", reason=str(exc))
            compress = str(vcf_path).endswith(".gz")
            _write_vcf_manual(df, vcf_path, info_fields_typed, compress=compress)
            action.log(message_type="info", step="combined_write_vcf_manual", rows=row_count)

        return vcf_path, row_count
