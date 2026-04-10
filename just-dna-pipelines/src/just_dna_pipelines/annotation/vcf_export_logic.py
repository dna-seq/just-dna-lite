"""
Logic for exporting annotated parquets back to VCF format.

Uses ``polars-bio``'s ``write_vcf`` with ``set_source_metadata`` to register
INFO field definitions so that annotation columns are written natively into
the VCF INFO column.
"""

from pathlib import Path
from typing import Optional

import polars as pl
import polars_bio as pb
from eliot import start_action

VCF_CORE_COLUMNS = {"chrom", "start", "end", "id", "ref", "alt", "qual", "filter"}

# Columns from FORMAT fields / genotype computation — never go into INFO.
_FORMAT_COLUMNS = {"genotype", "GT", "GQ", "DP", "AD", "VAF", "PL", "MIN_DP"}

_POLARS_TO_VCF_TYPE: dict[type, str] = {
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
    return _POLARS_TO_VCF_TYPE.get(type(dtype), "String")


def _detect_annotation_columns(
    schema: pl.Schema,
    explicit: Optional[list[str]] = None,
) -> list[str]:
    """Return column names that should be written into the VCF INFO field."""
    if explicit is not None:
        return explicit
    return [
        c for c in schema.names()
        if c not in VCF_CORE_COLUMNS
        and c not in _FORMAT_COLUMNS
        and c != "rsid"
    ]


def _prepare_for_write_vcf(df: pl.DataFrame, annotation_columns: list[str]) -> pl.DataFrame:
    """Prepare a DataFrame for ``pb.write_vcf()``.

    - Renames ``rsid`` -> ``id``
    - Fills missing required columns (``end``, ``qual``, ``filter``)
    - Casts ``start`` / ``end`` to ``UInt32``
    - Drops FORMAT/genotype columns (not part of VCF INFO)
    - Registers INFO field metadata via ``pb.set_source_metadata``
    """
    cols = df.columns

    if "rsid" in cols and "id" not in cols:
        df = df.rename({"rsid": "id"})
        cols = df.columns

    if "end" not in cols:
        df = df.with_columns((pl.col("start") + pl.lit(1)).alias("end"))
    if "qual" not in cols:
        df = df.with_columns(pl.lit(None, dtype=pl.Float64).alias("qual"))
    if "filter" not in cols:
        df = df.with_columns(pl.lit(".").alias("filter"))

    cast_exprs: list[pl.Expr] = []
    for c in df.columns:
        if c in ("start", "end") and df.schema[c] != pl.UInt32:
            cast_exprs.append(pl.col(c).cast(pl.UInt32))
        else:
            cast_exprs.append(pl.col(c))
    df = df.select(cast_exprs)

    drop_cols = [c for c in df.columns if c in _FORMAT_COLUMNS]
    if drop_cols:
        df = df.drop(drop_cols)

    if annotation_columns:
        info_fields = {
            col: {
                "number": "1",
                "type": _polars_dtype_to_vcf_type(df.schema[col]),
                "description": f"{col} annotation",
            }
            for col in annotation_columns
            if col in df.columns
        }
        if info_fields:
            pb.set_source_metadata(
                df, format="vcf", header={"info_fields": info_fields}
            )

    return df


def export_parquet_to_vcf(
    parquet_path: Path,
    vcf_path: Path,
    annotation_columns: Optional[list[str]] = None,
) -> tuple[Path, int]:
    """Export an annotated parquet to VCF format.

    Annotation columns are written into the VCF INFO field natively via
    ``pb.set_source_metadata`` + ``pb.write_vcf``.

    Args:
        parquet_path: Input annotated parquet.
        vcf_path: Output VCF path (.vcf.gz for compressed).
        annotation_columns: Columns to pack into INFO. If ``None``,
            auto-detected (all non-core VCF columns).

    Returns:
        ``(vcf_path, row_count)``
    """
    with start_action(
        action_type="export_parquet_to_vcf",
        parquet_path=str(parquet_path),
        vcf_path=str(vcf_path),
    ) as action:
        df = pl.read_parquet(parquet_path)
        ann_cols = _detect_annotation_columns(df.schema, annotation_columns)

        df = _prepare_for_write_vcf(df, ann_cols)
        row_count = len(df)

        vcf_path.parent.mkdir(parents=True, exist_ok=True)
        pb.write_vcf(df, str(vcf_path))

        action.log(
            message_type="info",
            step="write_vcf_complete",
            rows=row_count,
            info_fields=len(ann_cols),
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
    columns prefixed with the module name.  Ensembl annotations are joined
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
                and c not in _FORMAT_COLUMNS
                and c != "rsid"
                and c not in available_join_cols
            ]
            if not annotation_cols:
                continue

            rename_map = {c: f"{module_name}_{c}" for c in annotation_cols}
            select_cols = mod_join_cols + annotation_cols
            mod_subset = mod_lf.select(select_cols).rename(rename_map)
            mod_subset = mod_subset.unique(subset=mod_join_cols)

            base_lf = base_lf.join(mod_subset, on=mod_join_cols, how="left")
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
                    and c not in _FORMAT_COLUMNS
                    and c != "rsid"
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

        df = base_lf.collect()
        ann_cols = _detect_annotation_columns(df.schema)
        df = _prepare_for_write_vcf(df, ann_cols)

        vcf_path.parent.mkdir(parents=True, exist_ok=True)
        pb.write_vcf(df, str(vcf_path))

        action.log(
            message_type="info",
            step="combined_write_vcf_complete",
            rows=len(df),
            info_fields=len(ann_cols),
        )
        return vcf_path, len(df)
