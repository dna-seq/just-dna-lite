"""
Round-trip tests for the module compiler.

Downloads each existing HuggingFace module, reverse-engineers it into the
module spec DSL, compiles the DSL back to parquet, and compares the result
against the original. This validates that the compiler is feature-complete
for filter-based annotation modules.

Requires network access (downloads from HuggingFace).
"""

from pathlib import Path
from typing import Dict, Optional, Set

import polars as pl
import pytest

from just_dna_pipelines.module_compiler.compiler import (
    compile_module,
    reverse_module,
    validate_spec,
)

HF_REPO = "just-dna-seq/annotators"

MODULE_METADATA: Dict[str, Dict[str, str]] = {
    "longevitymap": {
        "title": "Longevity Map",
        "description": "Longevity-associated genetic variants from LongevityMap database",
        "report_title": "Longevity Variants",
        "icon": "heart-pulse",
        "color": "#21ba45",
    },
    "lipidmetabolism": {
        "title": "Lipid Metabolism",
        "description": "Lipid metabolism and cardiovascular risk variants",
        "report_title": "Lipid Metabolism",
        "icon": "droplets",
        "color": "#fbbd08",
    },
    "vo2max": {
        "title": "VO2 Max",
        "description": "Athletic performance and oxygen uptake capacity variants",
        "report_title": "VO2max / Athletic Performance",
        "icon": "activity",
        "color": "#2185d0",
    },
    "superhuman": {
        "title": "Superhuman",
        "description": "Elite performance and rare beneficial variants",
        "report_title": "Superhuman / Elite Performance",
        "icon": "zap",
        "color": "#00b5ad",
    },
    "coronary": {
        "title": "Coronary",
        "description": "Coronary artery disease risk associations",
        "report_title": "Coronary Artery Disease",
        "icon": "heart",
        "color": "#db2828",
    },
}

MODULES = [m for m in MODULE_METADATA if m != "longevitymap"]


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def hf_cache(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Download all HF module parquets to a shared temp directory."""
    cache = tmp_path_factory.mktemp("hf_modules")
    for mod in MODULES:
        mod_dir = cache / mod
        mod_dir.mkdir()
        base_url = f"hf://datasets/{HF_REPO}/data/{mod}"
        for table in ["weights", "annotations", "studies"]:
            url = f"{base_url}/{table}.parquet"
            try:
                df = pl.read_parquet(url)
                df.write_parquet(mod_dir / f"{table}.parquet")
            except Exception:
                pass
    return cache


@pytest.fixture(scope="module")
def reversed_specs(hf_cache: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Reverse-engineer all downloaded modules into spec DSL."""
    specs_dir = tmp_path_factory.mktemp("reversed_specs")
    for mod in MODULES:
        parquet_dir = hf_cache / mod
        if not (parquet_dir / "weights.parquet").exists():
            continue
        meta = MODULE_METADATA[mod]
        reverse_module(
            parquet_dir=parquet_dir,
            output_dir=specs_dir / mod,
            module_name=mod,
            title=meta["title"],
            description=meta["description"],
            report_title=meta["report_title"],
            icon=meta["icon"],
            color=meta["color"],
        )
    return specs_dir


@pytest.fixture(scope="module")
def compiled_modules(
    reversed_specs: Path, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    """Compile all reversed specs back to parquet."""
    compiled_dir = tmp_path_factory.mktemp("compiled")
    for mod in MODULES:
        spec_dir = reversed_specs / mod
        if not spec_dir.exists():
            continue
        result = compile_module(spec_dir, compiled_dir / mod)
        assert result.success, f"Compile failed for {mod}: {result.errors}"
    return compiled_dir


# ── Tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestReverseValidation:
    """All reversed specs must validate cleanly."""

    @pytest.mark.parametrize("mod", MODULES)
    def test_reversed_spec_validates(self, reversed_specs: Path, mod: str) -> None:
        spec_dir = reversed_specs / mod
        if not spec_dir.exists():
            pytest.skip(f"{mod} not downloaded")
        result = validate_spec(spec_dir)
        assert result.valid, f"{mod} validation errors: {result.errors}"


@pytest.mark.integration
class TestRoundTripSchema:
    """Compiled output must match the original HF module schemas."""

    @pytest.mark.parametrize("mod", MODULES)
    def test_weights_columns_match(
        self, hf_cache: Path, compiled_modules: Path, mod: str
    ) -> None:
        orig_path = hf_cache / mod / "weights.parquet"
        comp_path = compiled_modules / mod / "weights.parquet"
        if not orig_path.exists():
            pytest.skip(f"{mod} not downloaded")

        orig = pl.read_parquet(orig_path)
        comp = pl.read_parquet(comp_path)

        orig_cols = set(orig.columns)
        comp_cols = set(comp.columns)
        assert comp_cols == orig_cols, (
            f"{mod} weights column mismatch: "
            f"missing={orig_cols - comp_cols}, extra={comp_cols - orig_cols}"
        )

    @pytest.mark.parametrize("mod", MODULES)
    def test_annotations_columns_match(
        self, hf_cache: Path, compiled_modules: Path, mod: str
    ) -> None:
        orig_path = hf_cache / mod / "annotations.parquet"
        comp_path = compiled_modules / mod / "annotations.parquet"
        if not orig_path.exists():
            pytest.skip(f"{mod} not downloaded")

        orig = pl.read_parquet(orig_path)
        comp = pl.read_parquet(comp_path)
        assert set(comp.columns) == set(orig.columns)

    @pytest.mark.parametrize("mod", MODULES)
    def test_studies_columns_match(
        self, hf_cache: Path, compiled_modules: Path, mod: str
    ) -> None:
        orig_path = hf_cache / mod / "studies.parquet"
        comp_path = compiled_modules / mod / "studies.parquet"
        if not orig_path.exists():
            pytest.skip(f"{mod} has no studies")
        if not comp_path.exists():
            pytest.fail(f"{mod} compiled output missing studies.parquet")

        orig = pl.read_parquet(orig_path)
        comp = pl.read_parquet(comp_path)
        assert set(comp.columns) == set(orig.columns)


@pytest.mark.integration
class TestRoundTripContent:
    """Row counts and key values must survive the round-trip."""

    @pytest.mark.parametrize("mod", MODULES)
    def test_weights_row_count(
        self, hf_cache: Path, compiled_modules: Path, mod: str
    ) -> None:
        orig_path = hf_cache / mod / "weights.parquet"
        comp_path = compiled_modules / mod / "weights.parquet"
        if not orig_path.exists():
            pytest.skip(f"{mod} not downloaded")

        orig = pl.read_parquet(orig_path)
        comp = pl.read_parquet(comp_path)
        assert comp.height == orig.height, (
            f"{mod}: weights row count {comp.height} != original {orig.height}"
        )

    @pytest.mark.parametrize("mod", MODULES)
    def test_annotations_row_count(
        self, hf_cache: Path, compiled_modules: Path, mod: str
    ) -> None:
        """Annotations for rsids that appear in weights must be preserved.

        Annotation-only rsids (in annotations.parquet but not weights.parquet)
        cannot survive the round-trip because the DSL ties annotations to
        weight entries.
        """
        orig_ann_path = hf_cache / mod / "annotations.parquet"
        orig_wt_path = hf_cache / mod / "weights.parquet"
        comp_path = compiled_modules / mod / "annotations.parquet"
        if not orig_ann_path.exists():
            pytest.skip(f"{mod} not downloaded")

        orig_ann = pl.read_parquet(orig_ann_path)
        orig_wt = pl.read_parquet(orig_wt_path)
        comp = pl.read_parquet(comp_path)

        weight_rsids = set(orig_wt["rsid"].unique().to_list())
        expected_count = orig_ann.filter(pl.col("rsid").is_in(list(weight_rsids))).height
        assert comp.height == expected_count, (
            f"{mod}: compiled annotations {comp.height} != "
            f"expected {expected_count} (weight-linked from original {orig_ann.height})"
        )

    @pytest.mark.parametrize("mod", MODULES)
    def test_studies_row_count(
        self, hf_cache: Path, compiled_modules: Path, mod: str
    ) -> None:
        """Studies with non-null pmid must be preserved. Null-pmid rows are dropped."""
        orig_path = hf_cache / mod / "studies.parquet"
        comp_path = compiled_modules / mod / "studies.parquet"
        if not orig_path.exists():
            pytest.skip(f"{mod} has no studies")

        orig = pl.read_parquet(orig_path)
        comp = pl.read_parquet(comp_path)
        expected_count = orig.filter(pl.col("pmid").is_not_null()).height
        assert comp.height == expected_count, (
            f"{mod}: compiled studies {comp.height} != "
            f"expected {expected_count} (non-null pmid from original {orig.height})"
        )

    @pytest.mark.parametrize("mod", MODULES)
    def test_rsid_set_preserved(
        self, hf_cache: Path, compiled_modules: Path, mod: str
    ) -> None:
        """The exact set of rsids must survive the round-trip."""
        orig_path = hf_cache / mod / "weights.parquet"
        comp_path = compiled_modules / mod / "weights.parquet"
        if not orig_path.exists():
            pytest.skip(f"{mod} not downloaded")

        orig_rsids = set(pl.read_parquet(orig_path)["rsid"].unique().to_list())
        comp_rsids = set(pl.read_parquet(comp_path)["rsid"].unique().to_list())
        assert comp_rsids == orig_rsids

    @pytest.mark.parametrize("mod", MODULES)
    def test_genotype_set_preserved(
        self, hf_cache: Path, compiled_modules: Path, mod: str
    ) -> None:
        """The set of (rsid, genotype) keys must survive the round-trip."""
        orig_path = hf_cache / mod / "weights.parquet"
        comp_path = compiled_modules / mod / "weights.parquet"
        if not orig_path.exists():
            pytest.skip(f"{mod} not downloaded")

        def extract_keys(path: Path) -> Set[str]:
            df = pl.read_parquet(path)
            keys = set()
            for row in df.select("rsid", "genotype").iter_rows():
                keys.add(f"{row[0]}:{'/'.join(row[1])}")
            return keys

        orig_keys = extract_keys(orig_path)
        comp_keys = extract_keys(comp_path)
        assert comp_keys == orig_keys

    @pytest.mark.parametrize("mod", MODULES)
    def test_weights_values_preserved(
        self, hf_cache: Path, compiled_modules: Path, mod: str
    ) -> None:
        """Weight values must match exactly for each (rsid, genotype) pair."""
        orig_path = hf_cache / mod / "weights.parquet"
        comp_path = compiled_modules / mod / "weights.parquet"
        if not orig_path.exists():
            pytest.skip(f"{mod} not downloaded")

        orig = pl.read_parquet(orig_path)
        comp = pl.read_parquet(comp_path)

        # Build lookup: key -> weight
        def weight_map(df: pl.DataFrame) -> Dict[str, Optional[float]]:
            result: Dict[str, Optional[float]] = {}
            for row in df.select("rsid", "genotype", "weight").iter_rows():
                key = f"{row[0]}:{'/'.join(row[1])}"
                result[key] = row[2]
            return result

        orig_w = weight_map(orig)
        comp_w = weight_map(comp)

        mismatches = []
        for key in orig_w:
            if key not in comp_w:
                mismatches.append(f"  {key}: missing in compiled")
            elif orig_w[key] != comp_w[key] and not (orig_w[key] is None and comp_w[key] is None):
                mismatches.append(f"  {key}: orig={orig_w[key]} vs comp={comp_w[key]}")

        assert len(mismatches) == 0, f"{mod}: weight mismatches:\n" + "\n".join(mismatches[:20])

    @pytest.mark.parametrize("mod", MODULES)
    def test_states_preserved(
        self, hf_cache: Path, compiled_modules: Path, mod: str
    ) -> None:
        """State values must match for each (rsid, genotype)."""
        orig_path = hf_cache / mod / "weights.parquet"
        comp_path = compiled_modules / mod / "weights.parquet"
        if not orig_path.exists():
            pytest.skip(f"{mod} not downloaded")

        def state_map(df: pl.DataFrame) -> Dict[str, str]:
            result: Dict[str, str] = {}
            for row in df.select("rsid", "genotype", "state").iter_rows():
                key = f"{row[0]}:{'/'.join(row[1])}"
                result[key] = row[2]
            return result

        orig_s = state_map(pl.read_parquet(orig_path))
        comp_s = state_map(pl.read_parquet(comp_path))

        mismatches = [
            f"  {k}: orig={orig_s[k]} vs comp={comp_s.get(k, 'MISSING')}"
            for k in orig_s if orig_s[k] != comp_s.get(k)
        ]
        assert len(mismatches) == 0, f"{mod}: state mismatches:\n" + "\n".join(mismatches[:20])

    @pytest.mark.parametrize("mod", MODULES)
    def test_annotations_gene_set_preserved(
        self, hf_cache: Path, compiled_modules: Path, mod: str
    ) -> None:
        """Gene assignments for weight-linked rsids must survive the round-trip."""
        orig_ann_path = hf_cache / mod / "annotations.parquet"
        orig_wt_path = hf_cache / mod / "weights.parquet"
        comp_path = compiled_modules / mod / "annotations.parquet"
        if not orig_ann_path.exists():
            pytest.skip(f"{mod} not downloaded")

        weight_rsids = set(pl.read_parquet(orig_wt_path)["rsid"].unique().to_list())

        def rsid_gene_map(path: Path) -> Dict[str, str]:
            df = pl.read_parquet(path)
            return dict(zip(df["rsid"].to_list(), df["gene"].to_list()))

        orig_g = rsid_gene_map(orig_ann_path)
        comp_g = rsid_gene_map(comp_path)

        mismatches = [
            f"  {k}: orig={orig_g[k]} vs comp={comp_g.get(k, 'MISSING')}"
            for k in orig_g
            if k in weight_rsids and orig_g[k] != comp_g.get(k)
        ]
        assert len(mismatches) == 0, f"{mod}: gene mismatches:\n" + "\n".join(mismatches[:20])

    @pytest.mark.parametrize("mod", MODULES)
    def test_study_pmids_preserved(
        self, hf_cache: Path, compiled_modules: Path, mod: str
    ) -> None:
        """Study (rsid, pmid) pairs with non-null pmid must survive the round-trip."""
        orig_path = hf_cache / mod / "studies.parquet"
        comp_path = compiled_modules / mod / "studies.parquet"
        if not orig_path.exists():
            pytest.skip(f"{mod} has no studies")

        def study_keys(path: Path, filter_null_pmid: bool = False) -> Set[str]:
            df = pl.read_parquet(path)
            if filter_null_pmid:
                df = df.filter(pl.col("pmid").is_not_null())
            return {
                f"{r[0]}:{str(r[1]).strip()}"
                for r in df.select("rsid", "pmid").iter_rows()
            }

        orig_keys = study_keys(orig_path, filter_null_pmid=True)
        comp_keys = study_keys(comp_path)
        assert comp_keys == orig_keys
