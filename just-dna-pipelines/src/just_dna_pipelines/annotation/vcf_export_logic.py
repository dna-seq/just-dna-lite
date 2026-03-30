"""
Logic for exporting annotated parquets back to VCF format.

Uses ``polars-bio``'s ``write_vcf`` for the core VCF structure (header,
coordinate handling, compression).  Extra annotation columns are currently
dropped by polars-bio (INFO always written as ``"."``) so we patch the
output to inject ``##INFO`` header lines and fill the INFO column.

Once polars-bio supports writing non-core columns into INFO
(see https://github.com/biodatageeks/polars-bio/issues/312), the
``_patch_vcf_info`` post-processing step can be removed entirely.
"""

import gzip
from datetime import datetime
from pathlib import Path
from typing import Optional

import polars as pl
import polars_bio as pb
from eliot import start_action

VCF_CORE_COLUMNS = {"chrom", "start", "end", "id", "ref", "alt", "qual", "filter"}

# Columns that come from FORMAT fields or genotype computation —
# never belong in the INFO field.
_FORMAT_COLUMNS = {"genotype", "GT", "GQ", "DP", "AD", "VAF", "PL", "MIN_DP"}

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


def _detect_annotation_columns(
    schema: pl.Schema,
    explicit: Optional[list[str]] = None,
) -> list[str]:
    """Return the annotation column names that should go into INFO."""
    if explicit is not None:
        return explicit
    return [
        c for c in schema.names()
        if c not in VCF_CORE_COLUMNS
        and c not in _FORMAT_COLUMNS
        and c != "rsid"
    ]


def _build_info_series(df: pl.DataFrame, annotation_cols: list[str]) -> pl.Series:
    """Build a string Series of VCF INFO values from annotation columns.

    Each row becomes ``KEY1=VAL1;KEY2=VAL2;...``.  Rows where every
    annotation column is null produce ``"."``.
    """
    if not annotation_cols:
        return pl.Series("_INFO", ["." for _ in range(len(df))])

    parts: list[pl.Expr] = []
    for col in annotation_cols:
        parts.append(
            pl.concat_str(
                [pl.lit(f"{col}="), pl.col(col).cast(pl.Utf8).fill_null(".")],
                separator="",
            )
        )

    info_df = df.select(
        pl.concat_str(parts, separator=";").alias("_INFO")
    )
    return info_df.get_column("_INFO")


def _prepare_core_df(df: pl.DataFrame) -> pl.DataFrame:
    """Prepare a DataFrame for ``pb.write_vcf()``.

    - Renames ``rsid`` -> ``id``
    - Casts ``start`` / ``end`` to ``UInt32`` (required by polars-bio)
    - Keeps only the columns polars-bio understands
    """
    cols = df.columns
    rename: dict[str, str] = {}
    if "rsid" in cols and "id" not in cols:
        rename["rsid"] = "id"

    if rename:
        df = df.rename(rename)
        cols = df.columns

    cast_exprs: list[pl.Expr] = []
    for c in cols:
        if c in ("start", "end") and df.schema[c] != pl.UInt32:
            cast_exprs.append(pl.col(c).cast(pl.UInt32))
        else:
            cast_exprs.append(pl.col(c))

    df = df.select(cast_exprs)

    keep = [c for c in ["chrom", "start", "end", "id", "ref", "alt", "qual", "filter"] if c in df.columns]
    return df.select(keep)


def _patch_vcf_info(
    vcf_path: Path,
    info_series: pl.Series,
    info_fields: list[tuple[str, str]],
) -> None:
    """Patch a polars-bio-generated VCF to include annotation INFO values.

    Reads the file, injects ``##INFO`` header lines, and replaces the
    ``INFO`` column (which polars-bio writes as ``"."``) with actual values.

    This function is the only custom VCF logic — remove it once polars-bio
    natively supports writing INFO fields.
    """
    is_gz = vcf_path.name.endswith(".gz") or vcf_path.name.endswith(".bgz")
    opener = gzip.open if is_gz else open

    with opener(str(vcf_path), "rt") as fh:
        lines = fh.readlines()

    info_header_lines = [
        f'##INFO=<ID={name},Number=1,Type={vtype},Description="{name} annotation">\n'
        for name, vtype in info_fields
    ]

    patched: list[str] = []
    data_idx = 0
    info_values = info_series.to_list()

    for line in lines:
        if line.startswith("#CHROM"):
            patched.extend(info_header_lines)
            patched.append(line)
        elif line.startswith("#"):
            patched.append(line)
        else:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 8 and data_idx < len(info_values):
                parts[7] = info_values[data_idx] if info_values[data_idx] is not None else "."
                data_idx += 1
            patched.append("\t".join(parts) + "\n")

    with opener(str(vcf_path), "wt") as fh:
        fh.writelines(patched)


def export_parquet_to_vcf(
    parquet_path: Path,
    vcf_path: Path,
    annotation_columns: Optional[list[str]] = None,
) -> tuple[Path, int]:
    """Export an annotated parquet to VCF format.

    Uses ``pb.write_vcf()`` for the core VCF structure and patches the
    INFO column with annotation values afterwards.

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
        schema = df.schema
        row_count = len(df)

        ann_cols = _detect_annotation_columns(schema, annotation_columns)
        info_series = _build_info_series(df, ann_cols)
        info_fields_typed = [(c, _polars_dtype_to_vcf_type(schema[c])) for c in ann_cols if c in schema]

        core_df = _prepare_core_df(df)
        pb.write_vcf(core_df, str(vcf_path))

        if ann_cols:
            _patch_vcf_info(vcf_path, info_series, info_fields_typed)

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
        schema = df.schema
        ann_cols = _detect_annotation_columns(schema)
        info_series = _build_info_series(df, ann_cols)
        info_fields_typed = [(c, _polars_dtype_to_vcf_type(schema[c])) for c in ann_cols if c in schema]

        core_df = _prepare_core_df(df)
        pb.write_vcf(core_df, str(vcf_path))

        if ann_cols:
            _patch_vcf_info(vcf_path, info_series, info_fields_typed)

        action.log(
            message_type="info",
            step="combined_write_vcf_complete",
            rows=len(df),
            info_fields=len(ann_cols),
        )
        return vcf_path, len(df)
