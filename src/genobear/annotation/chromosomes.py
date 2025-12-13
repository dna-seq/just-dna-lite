"""Chromosome-related utilities for Polars LazyFrames."""

from __future__ import annotations

import polars as pl


def add_chromosome_candidate_columns(
    lf: pl.LazyFrame,
    *,
    chrom_col: str = "chrom",
    stripped_col: str = "chrom_stripped",
    chr_prefixed_col: str = "chrom_chr",
    chr_prefixed_upper_col: str = "chrom_chr_upper",
) -> pl.LazyFrame:
    """
    Add candidate chromosome columns for matching chromosome-split filenames.

    This does **not** assume chromosomes are numeric. It emits multiple candidates:
    - `stripped_col`: stripped original value (NULL if empty)
    - `chr_prefixed_col`: "chr" + (value without leading "chr" if present)
    - `chr_prefixed_upper_col`: same as above, but uppercases the suffix (helps "x"->"X")
    """
    stripped_expr = pl.col(chrom_col).cast(pl.Utf8).str.strip_chars()
    stripped = (
        pl.when(stripped_expr.is_null() | (stripped_expr.str.len_chars() == 0))
        .then(None)
        .otherwise(stripped_expr)
        .alias(stripped_col)
    )

    # Two-step: Polars expressions in one `with_columns()` cannot depend on columns
    # created earlier in the same call.
    lf2 = lf.with_columns(stripped)

    # If already starts with "chr" (case-insensitive), drop that prefix before re-adding "chr".
    base = pl.col(stripped_col)
    suffix = (
        pl.when(base.is_null())
        .then(None)
        .when(base.str.to_lowercase().str.starts_with("chr"))
        .then(base.str.slice(3))
        .otherwise(base)
    )

    chr_prefixed = pl.concat_str([pl.lit("chr"), suffix]).alias(chr_prefixed_col)
    chr_prefixed_upper = pl.concat_str([pl.lit("chr"), suffix.str.to_uppercase()]).alias(chr_prefixed_upper_col)

    return lf2.with_columns([chr_prefixed, chr_prefixed_upper])


def rewrite_chromosome_column_to_chr_prefixed(
    lf: pl.LazyFrame,
    *,
    chrom_col: str = "chrom",
) -> pl.LazyFrame:
    """
    Rewrite `chrom_col` into a `chr*` form.

    - "1" -> "chr1"
    - "chr1" / "CHR1" -> "chr1"
    - NULL/empty stays NULL
    """
    c = pl.col(chrom_col).cast(pl.Utf8).str.strip_chars()
    rewritten = (
        pl.when(c.is_null() | (c.str.len_chars() == 0))
        .then(None)
        .when(c.str.to_lowercase().str.starts_with("chr"))
        .then(pl.concat_str([pl.lit("chr"), c.str.slice(3)]))
        .otherwise(pl.concat_str([pl.lit("chr"), c]))
        .alias(chrom_col)
    )
    return lf.with_columns(rewritten)


def rewrite_chromosome_column_strip_chr_prefix(
    lf: pl.LazyFrame,
    *,
    chrom_col: str = "chrom",
) -> pl.LazyFrame:
    """
    Rewrite `chrom_col` to strip a leading 'chr' prefix (case-insensitive).

    - "chr1" / "CHR1" -> "1"
    - "1" -> "1"
    - NULL/empty stays NULL
    """
    c = pl.col(chrom_col).cast(pl.Utf8).str.strip_chars()
    rewritten = (
        pl.when(c.is_null() | (c.str.len_chars() == 0))
        .then(None)
        .when(c.str.to_lowercase().str.starts_with("chr"))
        .then(c.str.slice(3))
        .otherwise(c)
        .alias(chrom_col)
    )
    return lf.with_columns(rewritten)


def has_chr_prefix(chrom_values: list[str | None]) -> bool:
    """
    Check if any chromosome values in the list have a 'chr' prefix (case-insensitive).

    Args:
        chrom_values: List of chromosome string values (may contain None)

    Returns:
        True if at least one value starts with 'chr' (case-insensitive)
    """
    return any(
        (c is not None) and str(c).lower().startswith("chr") for c in chrom_values
    )


def detect_chrom_style_from_values(chrom_values: list[str | None]) -> str:
    """
    Detect the chromosome naming style from a list of values.

    Args:
        chrom_values: List of chromosome string values (may contain None)

    Returns:
        "chr_prefixed" if values have 'chr' prefix, "no_prefix" otherwise
    """
    if has_chr_prefix(chrom_values):
        return "chr_prefixed"
    return "no_prefix"


def detect_chrom_style_from_lazyframe(
    lf: pl.LazyFrame,
    chrom_col: str = "chrom",
    sample_limit: int = 100,
) -> str:
    """
    Detect chromosome naming style from a LazyFrame using unique chromosome values.

    Args:
        lf: LazyFrame to sample from
        chrom_col: Name of the chromosome column
        sample_limit: Deprecated. Kept for backwards compatibility; unique values are used instead.

    Returns:
        "chr_prefixed" or "no_prefix"
    """
    chrom_values = (
        lf.select(pl.col(chrom_col).cast(pl.Utf8).unique())
        .collect()
        .get_column(chrom_col)
        .to_list()
    )
    return detect_chrom_style_from_values(chrom_values)


def harmonize_chrom_column(
    input_lf: pl.LazyFrame,
    reference_lf: pl.LazyFrame,
    chrom_col: str = "chrom",
    sample_limit: int = 256,
) -> tuple[pl.LazyFrame, str | None]:
    """
    Harmonize chromosome column naming between input and reference LazyFrames.

    Detects whether input and reference use 'chr' prefix style, and rewrites
    the input to match the reference if they differ.

    Args:
        input_lf: Input LazyFrame to potentially rewrite
        reference_lf: Reference LazyFrame to match style against
        chrom_col: Name of the chromosome column
        sample_limit: Deprecated. Kept for backwards compatibility; unique values are used instead.

    Returns:
        Tuple of (possibly rewritten input LazyFrame, rewrite action taken or None)
        The rewrite action is one of: "to_chr_prefixed", "strip_chr_prefix", or None
    """
    # Collect unique chrom values from input
    input_chroms = (
        input_lf.select(pl.col(chrom_col).cast(pl.Utf8).unique())
        .collect()
        .get_column(chrom_col)
        .to_list()
    )
    input_has_chr = has_chr_prefix(input_chroms)

    # Collect unique chrom values from reference
    reference_chroms = (
        reference_lf.select(pl.col(chrom_col).cast(pl.Utf8).unique())
        .collect()
        .get_column(chrom_col)
        .to_list()
    )
    reference_has_chr = has_chr_prefix(reference_chroms)

    # Rewrite input to match reference if needed
    rewrite_applied: str | None = None
    if reference_has_chr and not input_has_chr:
        input_lf = rewrite_chromosome_column_to_chr_prefixed(input_lf, chrom_col=chrom_col)
        rewrite_applied = "to_chr_prefixed"
    elif (not reference_has_chr) and input_has_chr:
        input_lf = rewrite_chromosome_column_strip_chr_prefix(input_lf, chrom_col=chrom_col)
        rewrite_applied = "strip_chr_prefix"

    return input_lf, rewrite_applied


def get_input_chrom_style_and_values(
    input_lf: pl.LazyFrame,
    chrom_col: str = "chrom",
) -> tuple[str, set[str]]:
    """
    Get chromosome style and unique values from input LazyFrame.

    This does one collect to get unique chromosome values from the input,
    which is typically small (VCF files have limited chromosomes).

    Args:
        input_lf: Input LazyFrame
        chrom_col: Name of the chromosome column

    Returns:
        Tuple of (style: "chr_prefixed" or "no_prefix", set of unique chrom values)
    """
    input_chroms = (
        input_lf.select(pl.col(chrom_col).cast(pl.Utf8).unique())
        .collect()
        .get_column(chrom_col)
        .to_list()
    )
    style = detect_chrom_style_from_values(input_chroms)
    chrom_set = {c for c in input_chroms if c is not None}
    return style, chrom_set


def normalize_chrom_value(chrom: str, target_style: str) -> str:
    """
    Normalize a chromosome value to match target style.

    Args:
        chrom: Chromosome value (e.g., "1", "chr1", "X", "chrX")
        target_style: Either "chr_prefixed" or "no_prefix"

    Returns:
        Normalized chromosome value
    """
    chrom = chrom.strip()
    if not chrom:
        return chrom

    has_prefix = chrom.lower().startswith("chr")

    if target_style == "chr_prefixed":
        if has_prefix:
            # Normalize to "chr" + suffix (handling case)
            return "chr" + chrom[3:]
        else:
            return "chr" + chrom
    else:  # no_prefix
        if has_prefix:
            return chrom[3:]
        else:
            return chrom


