"""
Report generation logic for annotation modules.

Reads annotated parquet files produced by the HF module annotation pipeline,
enriches them with annotations and studies data from HuggingFace,
and renders HTML reports using Jinja2 templates.
"""

from pathlib import Path
from typing import Optional

import polars as pl
from eliot import start_action

from just_dna_pipelines.annotation.hf_modules import (
    ModuleInfo,
    ModuleTable,
    scan_module_table,
    discover_hf_modules,
)


# Longevity pathway categories and their display metadata
LONGEVITY_CATEGORIES: dict[str, dict[str, str]] = {
    "lipids": {
        "title": "Genes involved in lipid transfer and lipid signaling",
        "description": (
            "Lipids play crucial roles in regulating aging and longevity. "
            "They are fundamental structural elements of cellular membranes, "
            "key molecules in energy metabolism, and act as signaling molecules. "
            "Lipid metabolism is not considered a separate longevity pathway, but genes "
            "that regulate lipid transfer, like APOE and CETP, show the strongest "
            "association with longevity."
        ),
    },
    "insulin": {
        "title": "Genes involved in the insulin/IGF-1 signaling pathway",
        "description": (
            "The insulin/insulin-like growth factor (IGF-1) signaling pathway is a key "
            "regulator of metabolism, growth, and aging. It has been extensively studied "
            "in various model organisms and is thought to play an important role in human "
            "aging and longevity. This pathway is also involved in glucose metabolism."
        ),
    },
    "antioxidant": {
        "title": "Genes involved in antioxidant defense",
        "description": (
            "Antioxidant defense plays an important role in the aging process and longevity. "
            "Oxidative stress, caused by an imbalance between reactive oxygen species (ROS) "
            "and the body's ability to neutralize them, is a major contributor to age-related "
            "diseases. The body's antioxidant enzymes (SOD, catalase, glutathione peroxidase) "
            "and non-enzymatic antioxidants (vitamins C and E, glutathione) work together "
            "to neutralize ROS."
        ),
    },
    "mitochondria": {
        "title": "Genes related to mitochondria function",
        "description": (
            "Mitochondria are the powerhouses of the cell, generating ATP for cellular processes. "
            "Mitochondrial dysfunction and increased oxidative stress are believed to play a role "
            "in aging and age-related diseases. Genes involved in mitochondrial function include "
            "UCP genes, respiratory chain genes, SIRT3, PGC1a, and others. They determine how "
            "well you are protected from oxidative stress and how effectively your cells generate energy."
        ),
    },
    "sirtuin": {
        "title": "Genes related to the sirtuin pathway",
        "description": (
            "The sirtuin genes (SIRT1-SIRT7) are involved in regulating DNA repair, metabolism, "
            "and stress response. Activation of sirtuins can increase lifespan in several model "
            "organisms. In humans, variations in SIRT genes have been associated with age-related "
            "diseases such as Alzheimer's, cardiovascular disease, and cancer."
        ),
    },
    "mtor": {
        "title": "Genes related to mTOR pathway",
        "description": (
            "mTOR (mechanistic target of rapamycin) is a protein kinase involved in growth, "
            "metabolism, and aging. While activation promotes cellular growth, chronic activation "
            "has been implicated in age-related diseases. Inhibition of the mTOR pathway can "
            "extend lifespan in mice, flies, and worms."
        ),
    },
    "tumor-suppressor": {
        "title": "Tumor-suppressor genes",
        "description": (
            "Tumor suppressor genes and cell cycle regulators play an important role in aging "
            "and age-related diseases, including cancer. TP53 regulates cellular senescence and "
            "prevents accumulation of damaged cells. CDK dysregulation has been implicated in "
            "cancer and neurodegenerative disorders."
        ),
    },
    "renin-angiotensin": {
        "title": "Genes of the renin-angiotensin system",
        "description": (
            "The renin-angiotensin system (RAS) regulates blood pressure, fluid balance, and "
            "electrolyte homeostasis. RAS influences aging through oxidative stress activation, "
            "inflammation, and cardiovascular disease. It is also implicated in insulin resistance "
            "and regulation of cellular senescence."
        ),
    },
    "heat-shock": {
        "title": "Heat-shock protein genes",
        "description": (
            "HSP (heat shock protein) genes encode chaperone proteins that protect cells from "
            "stress-induced damage. HSPs are involved in protein folding, DNA repair, and apoptosis. "
            "They may help protect cells from accumulated damage caused by stress and environmental factors."
        ),
    },
    "inflammation": {
        "title": "Inflammation and related pathways",
        "description": (
            "Chronic inflammation is a major contributor to aging. It is characterized by sustained "
            "activation of the immune system and release of pro-inflammatory molecules (cytokines, "
            "chemokines, ROS). Chronic inflammation can also activate mTOR and senescence-associated "
            "secretory phenotype (SASP), further exacerbating tissue damage."
        ),
    },
    "genome_maintenance": {
        "title": "Genome maintenance and post-transcriptional processes",
        "description": (
            "Genome maintenance prevents DNA damage and mutations that lead to age-related diseases. "
            "Post-transcriptional processes (RNA splicing, translation, decay) regulate gene expression "
            "to ensure proteins are produced at appropriate levels. Dysregulation of these processes "
            "can lead to shortened lifespans."
        ),
    },
    "other": {
        "title": "Other genes associated with longevity",
        "description": (
            "Although many longevity-associated genes can be classified into definite pathways, "
            "there are other genes that do not fall into these categories."
        ),
    },
}


def _weight_color(weight: float) -> str:
    """Return a CSS color for a weight value. Positive = green, negative = red."""
    if weight > 0:
        intensity = min(int(abs(weight) * 200), 200)
        return f"rgba(0, {100 + intensity}, 0, 0.3)"
    elif weight < 0:
        intensity = min(int(abs(weight) * 200), 200)
        return f"rgba({100 + intensity}, 0, 0, 0.3)"
    return "transparent"


def _genotype_str(genotype: list[str] | None) -> str:
    """Format a genotype list as a human-readable string like 'A/G'."""
    if genotype is None:
        return ""
    return "/".join(genotype)


def _zygosity(genotype: list[str] | None) -> str:
    """Determine zygosity from a genotype list."""
    if genotype is None or len(genotype) < 2:
        return ""
    if genotype[0] == genotype[1]:
        return "hom"
    return "het"


def load_annotated_weights(
    weights_parquet: Path,
    module_name: str,
    module_info: Optional[ModuleInfo] = None,
) -> pl.DataFrame:
    """
    Load annotated weights parquet and enrich with annotation metadata.

    Joins the user's annotated weights with the module's annotations table
    (which has gene, phenotype, category) and the studies table.

    The weights parquet has the actual rsid values in a column named
    ``rsid_{module_name}`` (the plain ``rsid`` column from the VCF is
    typically empty). We resolve the correct column and use it for the
    join against the annotations table.

    Args:
        weights_parquet: Path to the user's {module}_weights.parquet
        module_name: Name of the HF module
        module_info: Optional ModuleInfo for the module

    Returns:
        Enriched DataFrame with annotation and study data joined in.
    """
    with start_action(action_type="load_annotated_weights", module=module_name, path=str(weights_parquet)):
        weights_lf = pl.scan_parquet(weights_parquet)

        # The actual rsid values live in rsid_{module_name}, not the VCF rsid column.
        # Resolve the correct column name for joining.
        schema_cols = weights_lf.collect_schema().names()
        module_rsid_col = f"rsid_{module_name}"
        if module_rsid_col in schema_cols:
            # Rename module-specific rsid column to "rsid" for the join,
            # dropping the original empty rsid column first.
            weights_lf = weights_lf.drop("rsid").rename({module_rsid_col: "rsid"})

        # Load annotations table from HF (has gene, category, phenotype)
        annotations_lf = scan_module_table(module_name, ModuleTable.ANNOTATIONS, module_info=module_info)

        # Join to get gene and category info
        enriched = weights_lf.join(
            annotations_lf.select("rsid", "gene", "category", "phenotype"),
            on="rsid",
            how="left",
            suffix="_ann",
        )

        return enriched.collect()


def load_studies_for_variants(
    rsids: list[str],
    module_name: str,
    module_info: Optional[ModuleInfo] = None,
) -> dict[str, list[dict[str, str]]]:
    """
    Load studies data for a set of rsids from an HF module.

    Returns a mapping of rsid -> list of study dicts.
    """
    with start_action(action_type="load_studies_for_variants", module=module_name):
        studies_lf = scan_module_table(module_name, ModuleTable.STUDIES, module_info=module_info)

        # Filter to relevant rsids
        studies_df = studies_lf.filter(
            pl.col("rsid").is_in(rsids)
        ).collect()

        result: dict[str, list[dict[str, str]]] = {}
        for row in studies_df.iter_rows(named=True):
            rsid = row["rsid"]
            if rsid not in result:
                result[rsid] = []
            result[rsid].append({
                "pmid": row.get("pmid", ""),
                "population": row.get("population", ""),
                "p_value": row.get("p_value", ""),
                "conclusion": row.get("conclusion", ""),
                "study_design": row.get("study_design", ""),
            })

        return result


def build_longevity_report_data(
    weights_parquet: Path,
    module_name: str = "longevitymap",
    module_info: Optional[ModuleInfo] = None,
) -> dict:
    """
    Build the full data structure needed for the longevity report template.

    Reads the annotated weights parquet, enriches with annotations and studies,
    groups variants by longevity pathway category, and computes summary statistics.

    Args:
        weights_parquet: Path to the user's longevitymap_weights.parquet
        module_name: Module name (default: "longevitymap")
        module_info: Optional ModuleInfo

    Returns:
        Dict with keys: categories, summary, module_name
    """
    with start_action(action_type="build_longevity_report_data", path=str(weights_parquet)):
        # Load and enrich weights
        enriched_df = load_annotated_weights(weights_parquet, module_name, module_info)

        # Filter to rows that have a weight (i.e., were actually annotated)
        annotated = enriched_df.filter(pl.col("weight").is_not_null())

        # Get all rsids for study lookup
        rsids = annotated.select("rsid").unique().to_series().to_list()
        studies_by_rsid = load_studies_for_variants(rsids, module_name, module_info)

        # Assign null categories to "other"
        annotated = annotated.with_columns(
            pl.col("category").fill_null("other").alias("category")
        )

        # Group variants by category
        categories: dict[str, dict] = {}
        for cat_key, cat_meta in LONGEVITY_CATEGORIES.items():
            cat_variants = annotated.filter(pl.col("category") == cat_key)

            if cat_variants.height == 0:
                categories[cat_key] = {
                    "title": cat_meta["title"],
                    "description": cat_meta["description"],
                    "variants": [],
                    "positive_count": 0,
                    "negative_count": 0,
                    "total_count": 0,
                }
                continue

            variants: list[dict] = []
            for row in cat_variants.iter_rows(named=True):
                weight = row.get("weight", 0.0) or 0.0
                genotype = row.get("genotype")
                rsid = row.get("rsid", "")

                variant = {
                    "rsid": rsid,
                    "gene": row.get("gene", ""),
                    "genotype_str": _genotype_str(genotype),
                    "ref": row.get("ref", ""),
                    "alt": "/".join(row.get("alts", []) or []),
                    "zygosity": _zygosity(genotype),
                    "weight": weight,
                    "weight_color": _weight_color(weight),
                    "state": row.get("state", ""),
                    "priority": row.get("priority", ""),
                    "conclusion": row.get("conclusion", ""),
                    "method": row.get("method", ""),
                    "clinvar": row.get("clinvar", False),
                    "pathogenic": row.get("pathogenic", False),
                    "benign": row.get("benign", False),
                    "studies": studies_by_rsid.get(rsid, []),
                }
                variants.append(variant)

            # Sort by absolute weight descending for better readability
            variants.sort(key=lambda v: abs(v["weight"]), reverse=True)

            positive = sum(1 for v in variants if v["weight"] > 0)
            negative = sum(1 for v in variants if v["weight"] < 0)

            categories[cat_key] = {
                "title": cat_meta["title"],
                "description": cat_meta["description"],
                "variants": variants,
                "positive_count": positive,
                "negative_count": negative,
                "total_count": len(variants),
            }

        # Summary statistics
        total_positive = sum(c["positive_count"] for c in categories.values())
        total_negative = sum(c["negative_count"] for c in categories.values())
        total_variants = sum(c["total_count"] for c in categories.values())
        total_weight = annotated.select("weight").sum().item() if annotated.height > 0 else 0.0

        summary = {
            "total_variants": total_variants,
            "total_positive": total_positive,
            "total_negative": total_negative,
            "total_weight": round(total_weight, 2) if total_weight else 0.0,
        }

        return {
            "categories": categories,
            "summary": summary,
            "module_name": module_name,
        }


def build_module_report_data(
    weights_parquet: Path,
    module_name: str,
    module_info: Optional[ModuleInfo] = None,
) -> dict:
    """
    Build report data for a generic HF annotation module
    (lipidmetabolism, coronary, vo2max, etc.).

    These modules don't use longevity pathway categories;
    variants are displayed in a single flat table.

    Args:
        weights_parquet: Path to the user's {module}_weights.parquet
        module_name: Module name
        module_info: Optional ModuleInfo

    Returns:
        Dict with keys: variants, summary, module_name
    """
    with start_action(action_type="build_module_report_data", module=module_name, path=str(weights_parquet)):
        enriched_df = load_annotated_weights(weights_parquet, module_name, module_info)
        annotated = enriched_df.filter(pl.col("weight").is_not_null())

        rsids = annotated.select("rsid").unique().to_series().to_list()
        studies_by_rsid = load_studies_for_variants(rsids, module_name, module_info)

        variants: list[dict] = []
        for row in annotated.iter_rows(named=True):
            weight = row.get("weight", 0.0) or 0.0
            genotype = row.get("genotype")
            rsid = row.get("rsid", "")

            variant = {
                "rsid": rsid,
                "gene": row.get("gene", ""),
                "genotype_str": _genotype_str(genotype),
                "ref": row.get("ref", ""),
                "alt": "/".join(row.get("alts", []) or []),
                "zygosity": _zygosity(genotype),
                "weight": weight,
                "weight_color": _weight_color(weight),
                "state": row.get("state", ""),
                "priority": row.get("priority", ""),
                "conclusion": row.get("conclusion", ""),
                "method": row.get("method", ""),
                "clinvar": row.get("clinvar", False),
                "pathogenic": row.get("pathogenic", False),
                "benign": row.get("benign", False),
                "population": row.get("population", ""),
                "p_value": row.get("p_value", ""),
                "studies": studies_by_rsid.get(rsid, []),
            }
            variants.append(variant)

        variants.sort(key=lambda v: abs(v["weight"]), reverse=True)

        positive = sum(1 for v in variants if v["weight"] > 0)
        negative = sum(1 for v in variants if v["weight"] < 0)

        summary = {
            "total_variants": len(variants),
            "total_positive": positive,
            "total_negative": negative,
            "total_weight": round(sum(v["weight"] for v in variants), 2),
        }

        return {
            "variants": variants,
            "summary": summary,
            "module_name": module_name,
        }


# Display names for modules (loaded from modules.yaml via module_config)
from just_dna_pipelines.module_config import build_display_names_dict
from just_dna_pipelines.annotation.hf_modules import DISCOVERED_MODULES as _DISCOVERED

MODULE_DISPLAY_NAMES: dict[str, str] = build_display_names_dict(_DISCOVERED)


def generate_longevity_report(
    modules_dir: Path,
    output_path: Path,
    module_names: Optional[list[str]] = None,
    user_name: str = "",
    sample_name: str = "",
) -> Path:
    """
    Generate a full longevity HTML report from annotated parquet files.

    Reads all available module parquet files from the modules directory,
    builds report data structures, and renders the Jinja2 template.

    Args:
        modules_dir: Directory containing {module}_weights.parquet files
        output_path: Where to write the output HTML
        module_names: Optional list of modules to include. If None, auto-discovers.
        user_name: User name for report header
        sample_name: Sample name for report header

    Returns:
        Path to the generated HTML report
    """
    import jinja2

    with start_action(action_type="generate_longevity_report", modules_dir=str(modules_dir)):
        # Discover module infos
        module_infos = discover_hf_modules()

        # Find available parquet files
        available_modules: list[str] = []
        if module_names:
            for name in module_names:
                parquet_path = modules_dir / f"{name}_weights.parquet"
                if parquet_path.exists():
                    available_modules.append(name)
        else:
            for parquet_file in sorted(modules_dir.glob("*_weights.parquet")):
                mod_name = parquet_file.stem.replace("_weights", "")
                available_modules.append(mod_name)

        # Build report data for each module
        longevity_data: Optional[dict] = None
        other_modules_data: list[dict] = []

        for mod_name in available_modules:
            parquet_path = modules_dir / f"{mod_name}_weights.parquet"
            info = module_infos.get(mod_name)

            if mod_name == "longevitymap":
                longevity_data = build_longevity_report_data(parquet_path, mod_name, info)
            else:
                mod_data = build_module_report_data(parquet_path, mod_name, info)
                mod_data["display_name"] = MODULE_DISPLAY_NAMES.get(mod_name, mod_name.replace("_", " ").title())
                other_modules_data.append(mod_data)

        # Load and render template
        template_dir = Path(__file__).parent / "templates"
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_dir)),
            autoescape=True,
        )
        # Register custom filters
        env.filters["weight_color"] = _weight_color
        env.filters["genotype_str"] = _genotype_str

        template = env.get_template("longevity_report.html.j2")

        html = template.render(
            user_name=user_name,
            sample_name=sample_name,
            longevity=longevity_data,
            other_modules=other_modules_data,
            module_display_names=MODULE_DISPLAY_NAMES,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")

        return output_path
