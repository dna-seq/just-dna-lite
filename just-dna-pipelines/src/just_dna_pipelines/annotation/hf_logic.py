"""
Logic for annotating VCF files with HuggingFace modules.

This module contains the core annotation logic using lazy Polars
for memory-efficient processing. HF modules are self-contained
and don't require Ensembl joins.

Modules are identified by string names (e.g., "longevitymap") rather than
enums, enabling dynamic discovery of new modules from the HF repository.
"""

from pathlib import Path
from typing import Optional

import polars as pl
from dagster import MetadataValue
from eliot import start_action
from just_dna_format.vrs import normalize_chrom

from just_dna_pipelines.io import read_vcf_file
from just_dna_pipelines.runtime import resource_tracker
from just_dna_pipelines.annotation.hf_modules import (
    MODULE_INFOS,
    ModuleTable,
    ModuleOutputMapping,
    AnnotationManifest,
    scan_module_table,
    get_module_info,
    read_module_provenance,
    ModuleInfo,
)
from just_dna_pipelines.annotation.configs import HfModuleAnnotationConfig
from just_dna_pipelines.annotation.resources import get_user_output_dir
from just_dna_pipelines.annotation.restoration import (
    EVIDENCE_CALLED,
    EVIDENCE_COLUMN,
    RestorationContext,
    build_restoration_context,
    restored_rows,
)


def prepare_vcf_for_module_annotation(
    vcf_path: Path,
    info_fields: Optional[list[str]] = None,
    format_fields: Optional[list[str]] = None,
) -> pl.LazyFrame:
    """
    Read and prepare VCF for module annotation.
    
    Ensures VCF has:
    - rsid column (from 'id' column, may be null/empty for position-based join)
    - genotype column as List[String] sorted alphabetically
    - Normalized chrom column (without 'chr' prefix for HF module compatibility)
    
    Args:
        vcf_path: Path to the VCF file
        info_fields: Optional INFO fields to extract
        format_fields: Optional FORMAT fields (must include GT for genotype)
        
    Returns:
        LazyFrame with genotype column ready for joining
    """
    with start_action(action_type="prepare_vcf_for_module_annotation", vcf_path=str(vcf_path)):
        # Read VCF with FORMAT fields enabled (needed for genotype)
        lf = read_vcf_file(
            vcf_path,
            info_fields=info_fields,
            save_parquet=None,  # Don't auto-save, we'll control output
            with_formats=True,
            format_fields=format_fields,
        )
        
        # Ensure we have an rsid column (copy from 'id' if exists)
        schema = lf.collect_schema()
        if "id" in schema.names() and "rsid" not in schema.names():
            lf = lf.rename({"id": "rsid"})
        
        # Normalize chromosome: strip 'chr' prefix if present for HF module compatibility
        if "chrom" in schema.names():
            lf = lf.with_columns(
                pl.col("chrom").str.replace(r"^chr", "").alias("chrom")
            )
        
        return lf


def prepare_vcf_rsid_only(
    vcf_path: Path,
    info_fields: Optional[list[str]] = None,
    format_fields: Optional[list[str]] = None,
) -> pl.LazyFrame:
    """
    Prepare VCF and filter to only variants with rsids.
    
    Use this when you want to join strictly on rsid + genotype.
    """
    lf = prepare_vcf_for_module_annotation(vcf_path, info_fields, format_fields)
    
    # Filter to only variants with rsid starting with "rs"
    return lf.filter(
        pl.col("rsid").is_not_null() & 
        pl.col("rsid").str.starts_with("rs")
    )


class UnsupportedLeadTable(Exception):
    """A module's lead table carries no key this engine can join a VCF on.

    Raised rather than returned so the per-module loop can tell "this family is not annotatable
    yet" apart from "this module is broken", and skip it without failing the whole run.
    """


def _normalize_lead_genotype(lead_lf: pl.LazyFrame) -> pl.LazyFrame:
    """Put a lead table's `genotype` in the representation `weights.parquet` already uses.

    `weights.parquet` stores a genotype as `List(Utf8)`, but the 0.4 table families
    (`pharm_variants` and friends) are materialized verbatim from their authored CSV and keep the
    authored string, e.g. `"G/G"`. The VCF side is always `List(Utf8)`
    (`io._compute_genotype_expr`), so joining a 0.4 family straight to it raises
    `SchemaError: datatypes of join keys don't match`.

    This mirrors the compiler's own `_split_genotype` exactly — split on `/` or `|`, drop empty
    fragments, **do not sort** — so a 0.4 table reaches the join in the same shape the compiler
    would have given the same alleles in `weights.parquet`. Sorting here would be a second,
    divergent convention, and on a phased genotype it would destroy information: the format's
    grammar requires an unphased `A/G` to be sorted already and holds a phased `A|G` in
    *homolog order*, which `weights.parquet` preserves (phase itself travels in its own `phased`
    column). Sorting would make `G|A` and `A|G` one key and manufacture a match the module never
    stated.

    Note the VCF side sorts unconditionally, so a phased authored genotype in non-sorted order
    matches nothing — the same as for a weights-led module, which is the point: this function
    removes a representation difference, it does not invent matching semantics.

    The Python twin for a row already read out of a parquet is `report_logic._genotype_alleles`.
    """
    schema = lead_lf.collect_schema()
    if "genotype" not in schema.names() or schema["genotype"] != pl.String:
        return lead_lf
    return lead_lf.with_columns(
        pl.col("genotype")
        .str.replace_all(r"\|", "/")
        .str.split("/")
        .list.eval(pl.element().filter(pl.element().str.len_chars() > 0))
        .alias("genotype")
    )


def _normalize_vcf_contigs(vcf_lf: pl.LazyFrame) -> pl.LazyFrame:
    """Fold the VCF's contig spellings onto the ones a module writes.

    Stripping a leading `chr` is not enough, and the gap is silent. Real GRCh38 files split on the
    mitochondrion: Ensembl-style writes `MT`, while the analysis set most pipelines align against
    (hs38DH) writes `chrM`, which our strip turned into `M` — a contig no module has, so **every
    mitochondrial annotation was dropped without a word**. One of the three samples in this repo is
    exactly that case, and `heteroplasmy` is an entire 0.4 table family about mtDNA.

    `just_dna_format.vrs.normalize_chrom` is the format's own folding (it is what mints VRS ids),
    so using it is what keeps our spelling and the module's identical by construction rather than by
    a rule we maintain. It is total — a scaffold or an HLA contig comes back unchanged rather than
    raising — so unmatched contigs simply stay unmatched, as they should.

    Mapped over the *distinct* contigs (a few thousand at most) and applied as one vectorized
    replace, rather than a per-row Python call over millions of variants.
    """
    if "chrom" not in vcf_lf.collect_schema().names():
        return vcf_lf
    contigs = vcf_lf.select(pl.col("chrom").unique()).collect().to_series().to_list()
    mapping = {
        contig: normalize_chrom(contig)
        for contig in contigs
        if contig is not None and normalize_chrom(contig) != contig
    }
    if not mapping:
        return vcf_lf
    return vcf_lf.with_columns(pl.col("chrom").replace(mapping))


# VCF §1.6.1.3: ID is a *semicolon-separated list* of identifiers, so one record may legitimately
# carry `rs123;rs456`. The authored side names exactly one variant per row (`validate_rsid`), so the
# split belongs to the consumer — and nothing in the format says so, which is why this is spelled
# out here (just-dna-format ROADMAP RM64).
_VCF_ID_SEP: str = ";"
# The column the rsid join actually keys on. Held apart from `rsid` so the output parquet keeps the
# record's ID verbatim rather than whichever member happened to match.
_RSID_KEY: str = "_rsid_join_key"


def _vcf_rsid_join_keys(vcf_lf: pl.LazyFrame) -> pl.LazyFrame:
    """Add one row per identifier a VCF record carries, keyed in `_RSID_KEY`.

    A no-op in row count for the usual single-ID record, and it keeps a null ID as one null row
    rather than dropping it.
    """
    # `empty_as_null=True` is pinned rather than left to the default, which flips in Polars 2.0:
    # an identifier-less record must survive as one null-keyed row, never be dropped from the VCF.
    return vcf_lf.with_columns(
        pl.col("rsid").str.split(_VCF_ID_SEP).alias(_RSID_KEY)
    ).explode(_RSID_KEY, empty_as_null=True)


def _vcf_has_rsids(vcf_lf: pl.LazyFrame) -> bool:
    """Whether a prepared VCF carries any rsID at all.

    An rsid join against a VCF whose ID column is empty throughout matches nothing, and the run
    otherwise reports success with zero annotations — indistinguishable from a genome that simply
    carries none of the module's variants.
    """
    if "rsid" not in vcf_lf.collect_schema().names():
        return False
    return bool(
        vcf_lf.select(
            (pl.col("rsid").is_not_null() & pl.col("rsid").str.starts_with("rs")).any()
        )
        .collect()
        .item()
    )


def _lead_join_strategy(lead_lf: pl.LazyFrame) -> tuple[str, str]:
    """How a module's lead table can be joined to a VCF, and why — `(strategy, reason)`.

    Classified by the schema the table actually has, not by its family name: ten families exist
    today and the format keeps adding them, so a name-keyed switch would need editing every
    release while a schema-keyed check absorbs new families for free.

    - `position` — `chrom`/`start` exist *and* hold at least one value. A table typed with
      coordinates but null throughout (any rsid-authored 0.4 table, since the compiler applies
      `resolution.csv` to `weights.parquet` alone) is not positionally joinable, and treating it
      as if it were annotates nothing instead of erroring.
    - `rsid` — no usable coordinates, but `rsid` + `genotype` are there.
    - `unsupported` — neither. `diplotypes`, `pgs`, `allele_function` and the binning families
      carry no per-variant key at all; the caller skips them with the reason recorded rather than
      dying on a `ColumnNotFoundError`.
    """
    schema = set(lead_lf.collect_schema().names())
    if {"chrom", "start"}.issubset(schema) and bool(
        lead_lf.select(pl.col("chrom").is_not_null().any()).collect().item()
    ):
        return "position", "lead table carries coordinates"
    if {"rsid", "genotype"}.issubset(schema):
        return "rsid", "lead table carries no coordinates; joining on rsid + genotype instead"
    missing = sorted({"rsid", "genotype"} - schema)
    return "unsupported", (
        "lead table has no populated coordinates and no rsid + genotype to fall back on "
        f"(missing: {', '.join(missing)})"
    )


def annotate_vcf_with_module_weights(
    vcf_lf: pl.LazyFrame,
    module_name: str,
    output_path: Path,
    compression: str = "zstd",
    join_on: str = "position",
    module_info: Optional[ModuleInfo] = None,
    restoration: Optional[RestorationContext] = None,
) -> tuple[Path, int, dict[str, int]]:
    """
    Annotate VCF variants with a module's weights table.
    
    Supports two join strategies:
    - "position": Join on chrom + start + ref + alt, then filter by genotype (default)
    - "rsid": Join on rsid + genotype (requires VCF to have rsids)
    
    Uses streaming sink_parquet for memory efficiency.
    
    Args:
        vcf_lf: Prepared VCF LazyFrame with genotype column
        module_name: Name of the annotator module (e.g., "longevitymap")
        output_path: Where to write the output parquet
        compression: Parquet compression (default: zstd)
        join_on: Join strategy - "position" or "rsid"
        module_info: Optional ModuleInfo for the module
        restoration: Sample-side inputs for reference-genotype restoration. When given (and the
            callset is variant-only), the module's authored hom-ref rows at sites the callset never
            emitted are appended, marked ``genotype_evidence="restored_hom_ref"``. See
            ``restoration`` for why this is the annotator's call and not the module's.

    Returns:
        Tuple of (output_path, num_matched_variants, restoration_stats).

        **The count is matched rows, not written rows.** A position join keeps every unmatched VCF
        row (the report needs them to distinguish "probed and did not match" from "never looked"), so
        the parquet's height is a *positions probed* number. Reporting it as "variants annotated"
        made `total_variants_annotated` read 567 against a real 259 on a WGS genome, and told the
        user "cancer: 29 variants" for a module that annotated none of them.
    """
    with start_action(action_type="annotate_with_module_weights", module=module_name, join_on=join_on) as action:
        # Load the module's lead table (lazy) — weights for most modules, pharm_variants for a
        # pharmacogenomics one — and put its genotype in the VCF's representation before any join.
        weights_lf = scan_module_table(module_name, ModuleTable.LEAD, module_info=module_info)
        weights_lf = _normalize_lead_genotype(weights_lf)

        # A position join needs coordinates, and the 0.4 table families are materialized verbatim
        # from their authored CSV — the compiler applies resolution.csv to weights.parquet only. So a
        # pharm_variants-led module reaches us with chrom/start null on every row and would join to
        # nothing at all. Fall back to rsid rather than silently annotating zero variants, and stop
        # outright when there is nothing to fall back on.
        strategy, reason = _lead_join_strategy(weights_lf)
        if strategy == "unsupported":
            raise UnsupportedLeadTable(f"{module_name}: {reason}")
        if join_on == "position" and strategy == "rsid":
            action.log(
                message_type="info",
                step="join_strategy_downgraded",
                module=module_name,
                reason=reason,
            )
            join_on = "rsid"

        if join_on == "rsid":
            # Join on rsid + genotype (requires VCF to have rsids)
            #
            # A VCF whose ID column is empty throughout — DeepVariant output among others — matches
            # such a module on nothing at all. That is a property of the input, not a failure, but
            # it must not read as "this module found nothing in you".
            if not _vcf_has_rsids(vcf_lf):
                action.log(
                    message_type="info",
                    step="vcf_has_no_rsids",
                    module=module_name,
                    reason=(
                        "this VCF carries no rsIDs, and the module can only be joined on rsid + "
                        "genotype, so no variant can match"
                    ),
                )

            # Key on each identifier the record carries, not on the raw ID cell (RM64).
            vcf_keyed = _vcf_rsid_join_keys(vcf_lf)
            module_rsids = weights_lf.select(pl.col("rsid").alias(_RSID_KEY)).unique()
            vcf_filtered = vcf_keyed.join(module_rsids, on=_RSID_KEY, how="semi")

            annotated_lf = vcf_filtered.join(
                weights_lf,
                left_on=[_RSID_KEY, "genotype"],
                right_on=["rsid", "genotype"],
                how="left",
                suffix=f"_{module_name}"
            ).drop(_RSID_KEY)
        else:
            # Join on position (chrom, start) + genotype
            # HF modules use 'start' for position, VCF also uses 'start' after polars-bio parsing

            # The HF weights table has: chrom, start, ref, alts (list), genotype (list)
            # VCF has: chrom, start, ref, alt (string), genotype (list)

            # First, get position keys from module
            module_positions = weights_lf.select(["chrom", "start"]).unique()

            # Semi-join to filter VCF to only positions in module
            vcf_filtered = vcf_lf.join(
                module_positions,
                on=["chrom", "start"],
                how="semi"
            )

            # Join on position + genotype. The genotype lists hold allele *strings*, not GT
            # indices, so matching them already requires the alleles themselves to agree — but
            # only for the alleles the sample carries. The module's `ref` used to be dropped
            # outright to avoid a name collision, which left nothing to catch two different
            # representations of the same locus (indel left-alignment above all). Keep it under
            # the suffix and require agreement where the module states one.
            annotated_lf = vcf_filtered.join(
                weights_lf,
                on=["chrom", "start", "genotype"],
                how="left",
                suffix=f"_{module_name}"
            )
            module_ref = f"ref_{module_name}"
            ref_agrees = pl.col(module_ref).is_null() | (pl.col(module_ref) == pl.col("ref"))
            # A left join keeps unmatched VCF rows with every module column null; those carry a
            # null module ref and survive, which is what `report_logic._annotated_rows` expects.
            #
            # String equality is the right test *here*, though it is the wrong test in general —
            # one indel has several valid spellings, which is what `just_dna_format.alleles`
            # (`parsimony_reduce` / `event_profile`) exists to compare. It is sufficient on the set
            # this filter can actually see: for a row to reach it, the genotype allele lists already
            # matched, so a differing `ref` means the genotype was hom-alt and only the ALT strings
            # coincided — and then the two records delete different numbers of bases, which is a
            # *positive* contradiction under that algebra rather than a spelling difference. Checked
            # against it on every real discard; see `TestPositionJoinRequiresRefAgreement`.
            #
            # Costs one extra pass over a frame the semi-join has already made small.
            discarded = (
                annotated_lf.filter(~ref_agrees).select(pl.len()).collect().item()
            )
            if discarded:
                action.log(
                    message_type="info",
                    step="ref_mismatch_discarded",
                    module=module_name,
                    num_discarded=discarded,
                    reason=(
                        "matched position and genotype but the module states a different ref "
                        "allele — a different variant whose ALT string happens to coincide"
                    ),
                )
            annotated_lf = annotated_lf.filter(ref_agrees)

        # Mark every row the caller actually supplied, so the restored rows appended below are
        # distinguishable from them in the parquet itself and not only in the report.
        annotated_lf = annotated_lf.with_columns(
            pl.lit(EVIDENCE_CALLED).alias(EVIDENCE_COLUMN)
        )

        restoration_stats: dict[str, int] = {}
        if restoration is not None:
            extra, restoration_stats = restored_rows(
                vcf_lf, weights_lf, module_name, restoration
            )
            if extra is not None:
                annotated_lf = pl.concat([annotated_lf, extra], how="diagonal_relaxed")
                action.log(
                    message_type="info",
                    step="hom_ref_restored",
                    module=module_name,
                    **restoration_stats,
                )

        # Write to parquet using streaming
        output_path.parent.mkdir(parents=True, exist_ok=True)
        annotated_lf.sink_parquet(output_path, compression=compression)

        # Two numbers, because they answer different questions and conflating them is how a module
        # that annotated nothing reported 29 variants. `written` is what the parquet holds — the
        # position join keeps unmatched rows on purpose. `matched` is what was actually annotated,
        # detected the same way `report_logic._annotated_rows` detects it.
        written_lf = pl.scan_parquet(output_path)
        num_written = written_lf.select(pl.len()).collect().item()
        num_matched = (
            written_lf.filter(pl.col("module").is_not_null()).select(pl.len()).collect().item()
            if "module" in written_lf.collect_schema().names()
            else num_written
        )

        action.log(
            message_type="info",
            step="weights_annotation_complete",
            module=module_name,
            num_matched=num_matched,
            num_written=num_written,
            join_on=join_on,
            output_path=str(output_path)
        )

        return output_path, num_matched, restoration_stats


def download_file(url: str, output_path: Path) -> Path:
    """Download a file from a URL or HuggingFace."""
    import requests
    
    # hf:// protocol handling
    if url.startswith("hf://"):
        from huggingface_hub import hf_hub_download, get_token
        
        # hf://datasets/owner/repo/data/module/file -> owner/repo, data/module/file
        # HuggingFace repo IDs are "owner/repo", so we need BOTH parts
        remainder = url.replace("hf://datasets/", "")
        parts = remainder.split("/")
        
        # Take first TWO parts for repo_id (owner/repo format)
        repo_id = f"{parts[0]}/{parts[1]}"
        
        # Everything after owner/repo is the file path
        subpath = "/".join(parts[2:])
        
        # Get token to access private repos (if logged in)
        token = get_token()
        
        downloaded_path = hf_hub_download(
            repo_id=repo_id,
            filename=subpath,
            repo_type="dataset",
            token=token,
        )
        import shutil
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(downloaded_path, output_path)
        return output_path
    
    # Zenodo URL handling
    if "zenodo.org/record" in url or "zenodo.org/api/records" in url:
        # If it's a record URL but not a direct content link, we might need to resolve it
        if "content" not in url and "/files/" in url:
             # Already a file link, might work directly or need /content
             pass
    
    # Regular URL handling
    response = requests.get(url, stream=True)
    response.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return output_path


def annotate_vcf_with_all_modules(
    logger,
    vcf_path: Path,
    config: HfModuleAnnotationConfig,
    user_name: str,
    sample_name: Optional[str] = None,
    normalized_parquet_path: Optional[Path] = None,
) -> tuple[AnnotationManifest, dict]:
    """
    Annotate VCF with all selected HF modules.

    Produces one parquet per module, `{module}_weights.parquet`, holding the VCF joined to that
    module's *lead* table. The name says weights because every downstream consumer globs for it;
    which family actually led is recorded as `lead_table` on the manifest entry, so a
    `pharm_variants`-led module is not silently read as a weights one.

    A module that cannot be annotated does not take the others down with it: an unjoinable lead
    family is skipped and a failing one is recorded, both with their reason, and the run continues.

    Args:
        logger: Logger instance
        vcf_path: Path to input VCF (used as fallback and for manifest metadata)
        config: HfModuleAnnotationConfig with module selection
        user_name: User identifier for output organization
        sample_name: Optional sample name
        normalized_parquet_path: If provided, read pre-normalized parquet instead
            of parsing the raw VCF.  The parquet is expected to already have
            chromosomes stripped of 'chr', 'id' renamed to 'rsid', and genotype
            computed.
        
    Returns:
        Tuple of (AnnotationManifest, metadata_dict)
    """
    module_infos = MODULE_INFOS
    selected_names = config.get_modules()
    
    sample_name = sample_name or config.sample_name or vcf_path.stem
    
    # Determine output directory
    if config.output_dir:
        output_dir = Path(config.output_dir)
    else:
        output_dir = get_user_output_dir() / user_name / sample_name / "modules"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Annotating with modules: {selected_names}")
    
    with resource_tracker("Annotate VCF with HF Modules") as tracker:
        if normalized_parquet_path is not None and normalized_parquet_path.exists():
            logger.info(f"Using pre-normalized parquet: {normalized_parquet_path}")
            vcf_lf = pl.scan_parquet(str(normalized_parquet_path))
        else:
            logger.info(f"Preparing VCF from scratch: {vcf_path}")
            vcf_lf = prepare_vcf_for_module_annotation(
                vcf_path,
                info_fields=config.info_fields,
                format_fields=config.format_fields,
            )

        # Fold contig spellings onto the module's once, here, rather than per module — and on both
        # inputs, since a normalized parquet written before this existed still carries `M` for the
        # mitochondrion.
        vcf_lf = _normalize_vcf_contigs(vcf_lf)

        # Sample-side inputs for reference-genotype restoration, computed once for all modules: the
        # callset's own (chrom, start) set is a 4.3M-row frame on a WGS genome and every module
        # would otherwise rebuild it.
        restoration = build_restoration_context(vcf_lf, config.restoration_max_flank_bp)
        logger.info(
            f"Reference-genotype restoration: "
            f"{'ON' if restoration.enabled else 'OFF'} — callset is "
            f"{restoration.mode.value} / {restoration.scope.value}; {restoration.scope_reason}"
            + (f" (flank <= {config.restoration_max_flank_bp:,} bp)" if restoration.enabled else "")
        )

        # Process each module
        module_outputs: list[ModuleOutputMapping] = []
        total_annotated = 0
        total_restored = 0
        skipped: dict[str, str] = {}
        failed: dict[str, str] = {}
        restored_by_module: dict[str, int] = {}

        for module_name in selected_names:
            logger.info(f"Processing module: {module_name}")
            info = module_infos[module_name]

            # Weights (genotype-specific) - main annotation.
            #
            # Modules are remote, user-selectable and third-party, so an artifact this engine
            # cannot join is a condition of normal operation rather than a bug to surface as a
            # crash — and one such module must not cost the user every other module's annotation.
            # Register the outcome here and let the caller decide what to say about it.
            weights_path = output_dir / f"{module_name}_weights.parquet"
            try:
                weights_path, num_weights, restore_stats = annotate_vcf_with_module_weights(
                    vcf_lf, module_name, weights_path, config.compression,
                    module_info=info, restoration=restoration,
                )
            except UnsupportedLeadTable as exc:
                skipped[module_name] = str(exc)
                logger.warning(f"  Skipping {module_name}: {exc}")
                continue
            except Exception as exc:
                failed[module_name] = f"{type(exc).__name__}: {exc}"
                logger.error(f"  Failed to annotate {module_name}: {exc}")
                continue

            # Download logo if exists
            logo_path = None
            if info.logo_url:
                try:
                    ext = info.logo_url.split(".")[-1]
                    target = output_dir / f"{module_name}_logo.{ext}"
                    logo_path = str(download_file(info.logo_url, target))
                    logger.info(f"  Downloaded logo: {logo_path}")
                except Exception as e:
                    logger.warning(f"  Failed to download logo for {module_name}: {e}")

            # Download metadata if exists
            metadata_json_path = None
            if info.metadata_url:
                try:
                    target = output_dir / f"{module_name}_metadata.json"
                    metadata_json_path = str(download_file(info.metadata_url, target))
                    logger.info(f"  Downloaded metadata: {metadata_json_path}")
                except Exception as e:
                    logger.warning(f"  Failed to download metadata for {module_name}: {e}")
            
            # Record which module bytes produced these rows. Without it a rendered report cannot be
            # tied to the module version behind it, and nothing can answer "which of my saved
            # results are stale" — the missing prerequisite under any later verification harness.
            module_version, module_digest = read_module_provenance(info)
            module_output = ModuleOutputMapping(
                module=module_name,
                lead_table=info.lead_table,
                weights_path=str(weights_path),
                logo_path=logo_path,
                metadata_path=metadata_json_path,
                version=module_version,
                digest=module_digest,
                source_url=info.source_url or info.lead_url or None,
            )
            
            total_annotated += num_weights
            module_outputs.append(module_output)

            restored = restore_stats.get("restored", 0)
            if restored:
                restored_by_module[module_name] = restored
                total_restored += restored

            suffix = (
                f" ({restored} restored from reference, "
                f"{restore_stats.get('hom_ref_rows', 0)} hom-ref rows authored)"
                if restored else ""
            )
            logger.info(f"  {module_name}: {num_weights} variants annotated{suffix}")
    
    # Get execution metrics from resource tracker
    from datetime import datetime, timezone
    duration_sec = None
    cpu_percent = None
    peak_memory_mb = None
    
    if "report" in tracker:
        report = tracker["report"]
        duration_sec = round(report.duration, 2)
        cpu_percent = round(report.cpu_usage_percent, 1)
        peak_memory_mb = round(report.peak_memory_mb, 2)
    
    # Build manifest with execution metrics
    manifest = AnnotationManifest(
        user_name=user_name,
        sample_name=sample_name,
        source_vcf=str(vcf_path),
        output_dir=str(output_dir),
        modules=module_outputs,
        skipped_modules=skipped,
        failed_modules=failed,
        total_variants_annotated=total_annotated,
        restored_variants=restored_by_module,
        total_variants_restored=total_restored,
        duration_sec=duration_sec,
        cpu_percent=cpu_percent,
        peak_memory_mb=peak_memory_mb,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    
    # Write manifest to JSON
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2))
    logger.info(f"Manifest written to: {manifest_path}")
    
    # Build metadata for Dagster
    metadata_dict = {
        "user_name": MetadataValue.text(user_name),
        "sample_name": MetadataValue.text(sample_name),
        "source_vcf": MetadataValue.path(str(vcf_path.absolute())),
        "output_dir": MetadataValue.path(str(output_dir.absolute())),
        "manifest_path": MetadataValue.path(str(manifest_path.absolute())),
        "modules_processed": MetadataValue.int(len(module_outputs)),
        "modules_requested": MetadataValue.int(len(selected_names)),
        "module_names": MetadataValue.text(", ".join(m.module for m in module_outputs)),
        "total_variants_annotated": MetadataValue.int(total_annotated),
        "compression": MetadataValue.text(config.compression),
    }

    # A module that produced nothing is as much a result as one that did, so name it rather than
    # leaving the user to infer it from a shorter module list.
    if skipped:
        metadata_dict["modules_skipped"] = MetadataValue.json(skipped)
    if failed:
        metadata_dict["modules_failed"] = MetadataValue.json(failed)
    if restored_by_module:
        metadata_dict["variants_restored"] = MetadataValue.json(restored_by_module)
        metadata_dict["total_variants_restored"] = MetadataValue.int(total_restored)
    
    # Add resource metrics to Dagster metadata
    if duration_sec is not None:
        metadata_dict.update({
            "duration_sec": MetadataValue.float(duration_sec),
            "cpu_percent": MetadataValue.float(cpu_percent),
            "peak_memory_mb": MetadataValue.float(peak_memory_mb),
        })
    
    # Add sample/subject metadata from SampleInfo base class
    if config.species:
        metadata_dict["species"] = MetadataValue.text(config.species)
    if config.reference_genome:
        metadata_dict["reference_genome"] = MetadataValue.text(config.reference_genome)
    if config.sample_description:
        metadata_dict["sample_description"] = MetadataValue.text(config.sample_description)
    if config.sequencing_type:
        metadata_dict["sequencing_type"] = MetadataValue.text(config.sequencing_type)
    
    # Add user-provided metadata (well-known optional fields)
    if config.subject_id:
        metadata_dict["subject_id"] = MetadataValue.text(config.subject_id)
    if config.sex:
        metadata_dict["sex"] = MetadataValue.text(config.sex)
    if config.tissue:
        metadata_dict["tissue"] = MetadataValue.text(config.tissue)
    if config.study_name:
        metadata_dict["study_name"] = MetadataValue.text(config.study_name)
    if config.description:
        metadata_dict["description"] = MetadataValue.text(config.description)
    
    # Add arbitrary custom metadata fields (user-defined key-value pairs)
    if config.custom_metadata:
        # Store the full dict as JSON for complete access
        metadata_dict["custom_metadata"] = MetadataValue.json(config.custom_metadata)
        # Also add each field individually with a "custom/" prefix for visibility in Dagster UI
        for key, value in config.custom_metadata.items():
            # Sanitize key to be a valid metadata key (alphanumeric + underscore)
            safe_key = "".join(c if c.isalnum() or c == "_" else "_" for c in key)
            metadata_dict[f"custom/{safe_key}"] = MetadataValue.text(str(value))
    
    return manifest, metadata_dict
