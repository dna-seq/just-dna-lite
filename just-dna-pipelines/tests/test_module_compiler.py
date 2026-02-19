"""
Tests for the module compiler with real Ensembl resolution.

Uses eval spec directories (mthfr_nad, cyp_panel) as real inputs.
Downloads the Ensembl cache once per session and uses it for
rsid<->position resolution tests.
"""

from pathlib import Path
from typing import Dict, List, Optional

import duckdb
import polars as pl
import pytest
import yaml

from just_dna_pipelines.module_compiler.compiler import compile_module, validate_spec
from just_dna_pipelines.module_compiler.models import (
    CompilationResult,
    Defaults,
    ModuleInfo,
    ModuleSpecConfig,
    StudyRow,
    ValidationResult,
    VariantRow,
)
from just_dna_pipelines.module_compiler.resolver import (
    ensure_resolver_db,
    resolve_variants,
)
from just_dna_pipelines.runtime import load_env

# ── Fixtures ───────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EVALS_DIR = REPO_ROOT / "data" / "module_specs" / "evals"

MTHFR_DIR = EVALS_DIR / "mthfr_nad"
CYP_DIR = EVALS_DIR / "cyp_panel"

# Known CYP panel ground-truth: rsid -> (chrom, start, ref)
# Taken directly from cyp_panel/variants.csv
CYP_GROUND_TRUTH: Dict[str, Dict] = {
    "rs4244285": {"chrom": "10", "start": 94781859, "ref": "G"},
    "rs4986893": {"chrom": "10", "start": 94780653, "ref": "G"},
    "rs12248560": {"chrom": "10", "start": 94761900, "ref": "C"},
    "rs3892097": {"chrom": "22", "start": 42128945, "ref": "C"},
    "rs1799853": {"chrom": "10", "start": 94942290, "ref": "C"},
    "rs1057910": {"chrom": "10", "start": 94981296, "ref": "A"},
    "rs35599367": {"chrom": "7", "start": 99768693, "ref": "G"},
}


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    return tmp_path / "compiled"


@pytest.fixture(scope="session")
def ensembl_db_path() -> Path:
    """Load .env for cache paths, then ensure the Ensembl DuckDB is ready."""
    load_env()
    return ensure_resolver_db()


# ── Pydantic model unit tests ─────────────────────────────────────────────────


class TestModuleSpecConfig:
    def test_load_mthfr_yaml(self) -> None:
        raw = yaml.safe_load((MTHFR_DIR / "module_spec.yaml").read_text())
        config = ModuleSpecConfig.model_validate(raw)
        assert config.module.name == "mthfr_nad"
        assert config.schema_version == "1.0"
        assert config.genome_build == "GRCh38"
        assert config.defaults.curator == "ai-module-creator"

    def test_load_cyp_yaml(self) -> None:
        raw = yaml.safe_load((CYP_DIR / "module_spec.yaml").read_text())
        config = ModuleSpecConfig.model_validate(raw)
        assert config.module.name == "cyp_panel"
        assert config.module.icon == "pill"
        assert config.defaults.priority == "high"

    def test_invalid_module_name(self) -> None:
        with pytest.raises(Exception):
            ModuleInfo(
                name="Bad Name!",
                title="T",
                description="D",
                report_title="R",
            )

    def test_invalid_schema_version(self) -> None:
        with pytest.raises(Exception):
            ModuleSpecConfig(
                schema_version="2.0",
                module=ModuleInfo(
                    name="test", title="T", description="D", report_title="R"
                ),
            )


class TestVariantRow:
    def test_valid_row_with_both(self) -> None:
        row = VariantRow(
            rsid="rs1801133",
            chrom="1",
            start=11796321,
            ref="G",
            alts="A",
            genotype="A/G",
            weight=-0.5,
            state="risk",
            conclusion="Heterozygous",
            gene="MTHFR",
            phenotype="Reduced methylation",
            category="methylation",
        )
        assert row.rsid == "rs1801133"
        assert row.variant_key == "rs1801133"

    def test_rsid_only_valid(self) -> None:
        row = VariantRow(
            rsid="rs123",
            genotype="A/T",
            weight=0.0,
            state="neutral",
            conclusion="Test",
        )
        assert row.chrom is None
        assert row.variant_key == "rs123"

    def test_position_only_valid(self) -> None:
        row = VariantRow(
            chrom="10",
            start=94781859,
            ref="G",
            alts="A",
            genotype="A/G",
            weight=-0.5,
            state="risk",
            conclusion="Position-only",
        )
        assert row.rsid is None
        assert row.variant_key == "10:94781859:G"

    def test_neither_rsid_nor_position_rejected(self) -> None:
        with pytest.raises(Exception, match="At least one identifier"):
            VariantRow(
                genotype="A/G",
                weight=0.0,
                state="neutral",
                conclusion="Test",
            )

    def test_invalid_rsid(self) -> None:
        with pytest.raises(Exception, match="rsid"):
            VariantRow(
                rsid="notAnRsid",
                genotype="A/G",
                weight=0.0,
                state="neutral",
                conclusion="Test",
            )

    def test_unsorted_genotype_rejected(self) -> None:
        with pytest.raises(Exception, match="alphabetically sorted"):
            VariantRow(
                rsid="rs123",
                genotype="G/A",
                weight=0.0,
                state="neutral",
                conclusion="Test",
            )

    def test_invalid_state(self) -> None:
        with pytest.raises(Exception, match="state"):
            VariantRow(
                rsid="rs123",
                genotype="A/G",
                weight=0.0,
                state="bad_state",
                conclusion="Test",
            )

    def test_chrom_normalization(self) -> None:
        row = VariantRow(
            rsid="rs123",
            chrom="chr1",
            start=100,
            genotype="A/G",
            weight=0.0,
            state="neutral",
            conclusion="Test",
        )
        assert row.chrom == "1"

    def test_partial_position_rejected(self) -> None:
        with pytest.raises(Exception, match="chrom and start are required"):
            VariantRow(
                rsid="rs123",
                chrom="1",
                start=None,
                genotype="A/G",
                weight=0.0,
                state="neutral",
                conclusion="Test",
            )

    def test_ref_without_position_rejected(self) -> None:
        with pytest.raises(Exception, match="ref/alts require chrom and start"):
            VariantRow(
                rsid="rs123",
                ref="A",
                genotype="A/G",
                weight=0.0,
                state="neutral",
                conclusion="Test",
            )


class TestStudyRow:
    def test_valid_study_with_rsid(self) -> None:
        row = StudyRow(rsid="rs1801133", pmid="9545397", conclusion="Test")
        assert row.variant_key == "rs1801133"

    def test_valid_study_with_position(self) -> None:
        row = StudyRow(chrom="10", start=94781859, ref="G", pmid="12345", conclusion="Test")
        assert row.variant_key == "10:94781859:G"

    def test_study_no_id_rejected(self) -> None:
        with pytest.raises(Exception, match="At least one identifier"):
            StudyRow(pmid="12345", conclusion="Test")

    def test_empty_pmid_rejected(self) -> None:
        with pytest.raises(Exception, match="pmid"):
            StudyRow(rsid="rs123", pmid="", conclusion="Test")

    def test_freeform_pmid_accepted(self) -> None:
        row = StudyRow(
            rsid="rs123",
            pmid="PMID 17478681; PMID 21378990;",
            conclusion="Test",
        )
        assert row.pmid == "PMID 17478681; PMID 21378990;"


# ── Validation tests ──────────────────────────────────────────────────────────


class TestValidation:
    def test_mthfr_valid(self) -> None:
        result = validate_spec(MTHFR_DIR)
        assert result.valid, f"Validation errors: {result.errors}"
        assert result.stats["unique_rsids"] == 8
        assert result.stats["unique_genes"] == 7
        assert "methylation" in result.stats["categories"]
        assert result.stats["study_rows"] > 0

    def test_cyp_valid(self) -> None:
        result = validate_spec(CYP_DIR)
        assert result.valid, f"Validation errors: {result.errors}"
        assert result.stats["unique_rsids"] == 7
        assert result.stats["module_name"] == "cyp_panel"
        assert result.stats["study_rows"] > 0

    def test_nonexistent_dir(self) -> None:
        result = validate_spec(Path("/nonexistent/path"))
        assert not result.valid
        assert any("does not exist" in e for e in result.errors)

    def test_empty_dir(self, tmp_path: Path) -> None:
        result = validate_spec(tmp_path)
        assert not result.valid
        assert any("module_spec.yaml not found" in e for e in result.errors)

    def test_missing_variants(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "module_spec.yaml"
        yaml_path.write_text(
            yaml.dump({
                "schema_version": "1.0",
                "module": {"name": "test_mod", "title": "Test", "description": "D", "report_title": "R"},
            })
        )
        result = validate_spec(tmp_path)
        assert not result.valid
        assert any("variants.csv not found" in e for e in result.errors)

    def test_malformed_csv_row(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "module_spec.yaml"
        yaml_path.write_text(
            yaml.dump({
                "schema_version": "1.0",
                "module": {"name": "test_mod", "title": "Test", "description": "D", "report_title": "R"},
            })
        )
        (tmp_path / "variants.csv").write_text(
            "rsid,genotype,weight,state,conclusion\n"
            "rs123,A/G,0.5,invalid_state,Conclusion\n"
        )
        result = validate_spec(tmp_path)
        assert not result.valid
        assert any("state" in e for e in result.errors)

    def test_duplicate_genotype_detected(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "module_spec.yaml"
        yaml_path.write_text(
            yaml.dump({
                "schema_version": "1.0",
                "module": {"name": "test_mod", "title": "Test", "description": "D", "report_title": "R"},
            })
        )
        (tmp_path / "variants.csv").write_text(
            "rsid,genotype,weight,state,conclusion\n"
            "rs123,A/G,0.5,risk,Conclusion\n"
            "rs123,A/G,-0.3,protective,Other\n"
        )
        result = validate_spec(tmp_path)
        assert not result.valid
        assert any("Duplicate" in e for e in result.errors)

    def test_weight_direction_warning(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "module_spec.yaml"
        yaml_path.write_text(
            yaml.dump({
                "schema_version": "1.0",
                "module": {"name": "test_mod", "title": "Test", "description": "D", "report_title": "R"},
            })
        )
        (tmp_path / "variants.csv").write_text(
            "rsid,genotype,weight,state,conclusion\n"
            "rs123,A/G,0.5,risk,Conclusion\n"
        )
        result = validate_spec(tmp_path)
        assert result.valid
        assert any("risk" in w and "weight=0.5" in w for w in result.warnings)


# ── Resolver tests (real Ensembl cache) ──────────────────────────────────────


class TestResolver:
    """Test rsid <-> position resolution against real Ensembl data."""

    def test_ensembl_db_exists(self, ensembl_db_path: Path) -> None:
        assert ensembl_db_path.exists()
        con = duckdb.connect(str(ensembl_db_path), read_only=True)
        tables = [row[0] for row in con.execute("SHOW TABLES").fetchall()]
        con.close()
        assert "ensembl_variations" in tables

    def test_rsid_to_position(self, ensembl_db_path: Path) -> None:
        """Known CYP rsids must resolve to their known positions."""
        variants = [
            VariantRow(rsid=rsid, genotype="A/G", weight=0.0, state="neutral", conclusion="Test")
            for rsid in ["rs4244285", "rs3892097", "rs1057910"]
        ]
        patched, warnings = resolve_variants(variants)

        for v in patched:
            gt = CYP_GROUND_TRUTH[v.rsid]
            assert v.chrom == gt["chrom"], f"{v.rsid}: chrom {v.chrom} != {gt['chrom']}"
            assert v.start == gt["start"], f"{v.rsid}: start {v.start} != {gt['start']}"
            assert v.ref == gt["ref"], f"{v.rsid}: ref {v.ref} != {gt['ref']}"

    def test_position_to_rsid(self, ensembl_db_path: Path) -> None:
        """Known CYP positions must resolve back to their rsids."""
        variants = [
            VariantRow(
                chrom=gt["chrom"],
                start=gt["start"],
                ref=gt["ref"],
                genotype="A/G",
                weight=0.0,
                state="neutral",
                conclusion="Test",
            )
            for gt in [CYP_GROUND_TRUTH["rs4244285"], CYP_GROUND_TRUTH["rs3892097"]]
        ]
        patched, warnings = resolve_variants(variants)

        resolved_rsids = {v.rsid for v in patched if v.rsid is not None}
        assert "rs4244285" in resolved_rsids
        assert "rs3892097" in resolved_rsids

    def test_already_complete_untouched(self, ensembl_db_path: Path) -> None:
        """Variants with both rsid and position should not be modified."""
        variants = [
            VariantRow(
                rsid="rs4244285",
                chrom="10",
                start=94781859,
                ref="G",
                alts="A",
                genotype="A/G",
                weight=-0.8,
                state="risk",
                conclusion="Complete",
            )
        ]
        patched, warnings = resolve_variants(variants)
        assert len(patched) == 1
        assert patched[0].rsid == "rs4244285"
        assert patched[0].chrom == "10"
        assert patched[0].start == 94781859
        assert len(warnings) == 0

    @pytest.mark.parametrize("rsid", list(CYP_GROUND_TRUTH.keys()))
    def test_all_cyp_rsids_resolve(self, ensembl_db_path: Path, rsid: str) -> None:
        """Every CYP panel rsid must resolve to its ground-truth position."""
        variants = [
            VariantRow(rsid=rsid, genotype="A/G", weight=0.0, state="neutral", conclusion="Test")
        ]
        patched, warnings = resolve_variants(variants)
        v = patched[0]
        gt = CYP_GROUND_TRUTH[rsid]
        assert v.chrom == gt["chrom"], f"{rsid}: chrom mismatch"
        assert v.start == gt["start"], f"{rsid}: start mismatch"
        assert v.ref == gt["ref"], f"{rsid}: ref mismatch"

    def test_nonexistent_rsid_warns(self, ensembl_db_path: Path) -> None:
        fake_rsid = "rs99999999999999"
        variants = [
            VariantRow(rsid=fake_rsid, genotype="A/G", weight=0.0, state="neutral", conclusion="Test")
        ]
        patched, warnings = resolve_variants(variants)
        assert patched[0].chrom is None
        assert any(fake_rsid in w for w in warnings)

    def test_nonexistent_position_warns(self, ensembl_db_path: Path) -> None:
        variants = [
            VariantRow(chrom="1", start=1, ref="A", genotype="A/G", weight=0.0, state="neutral", conclusion="Test")
        ]
        patched, warnings = resolve_variants(variants)
        assert patched[0].rsid is None
        assert any("1:1:A" in w for w in warnings)


# ── Compilation tests (with real resolution) ──────────────────────────────────


def _make_spec_dir(
    tmp_path: Path,
    module_name: str,
    variants_csv: str,
    studies_csv: Optional[str] = None,
) -> Path:
    """Helper to write a spec directory."""
    spec_dir = tmp_path / module_name
    spec_dir.mkdir()
    (spec_dir / "module_spec.yaml").write_text(
        yaml.dump({
            "schema_version": "1.0",
            "module": {
                "name": module_name,
                "title": module_name.replace("_", " ").title(),
                "description": f"Test module: {module_name}",
                "report_title": module_name.replace("_", " ").title(),
            },
        })
    )
    (spec_dir / "variants.csv").write_text(variants_csv)
    if studies_csv is not None:
        (spec_dir / "studies.csv").write_text(studies_csv)
    return spec_dir


class TestCompilation:
    """Compilation of eval specs. These specs have both rsid and positions,
    so resolution is a no-op and tests validate the core pipeline."""

    def test_compile_mthfr(self, output_dir: Path, ensembl_db_path: Path) -> None:
        result = compile_module(MTHFR_DIR, output_dir)
        assert result.success, f"Compilation errors: {result.errors}"
        assert result.output_dir == output_dir
        assert (output_dir / "weights.parquet").exists()
        assert (output_dir / "annotations.parquet").exists()
        assert (output_dir / "studies.parquet").exists()

    def test_compile_cyp(self, output_dir: Path, ensembl_db_path: Path) -> None:
        result = compile_module(CYP_DIR, output_dir)
        assert result.success, f"Compilation errors: {result.errors}"
        assert (output_dir / "weights.parquet").exists()
        assert (output_dir / "annotations.parquet").exists()
        assert (output_dir / "studies.parquet").exists()

    def test_mthfr_weights_schema(self, output_dir: Path, ensembl_db_path: Path) -> None:
        compile_module(MTHFR_DIR, output_dir)
        df = pl.read_parquet(output_dir / "weights.parquet")

        required_columns = {
            "rsid", "genotype", "weight", "state", "conclusion",
            "priority", "module", "curator", "method",
            "clinvar", "pathogenic", "benign",
            "likely_pathogenic", "likely_benign",
        }
        assert required_columns.issubset(set(df.columns))
        assert df.schema["genotype"] == pl.List(pl.Utf8)
        assert df.schema["weight"] == pl.Float64
        assert df.schema["clinvar"] == pl.Boolean

    def test_mthfr_weights_content(self, output_dir: Path, ensembl_db_path: Path) -> None:
        compile_module(MTHFR_DIR, output_dir)
        df = pl.read_parquet(output_dir / "weights.parquet")

        assert df.height == 24
        assert df["module"].unique().to_list() == ["mthfr_nad"]

        genotypes = df.filter(pl.col("rsid") == "rs1801133")["genotype"].to_list()
        assert ["A", "A"] in genotypes
        assert ["A", "G"] in genotypes
        assert ["G", "G"] in genotypes

        assert all(c == "ai-module-creator" for c in df["curator"].to_list())
        assert all(m == "literature-review" for m in df["method"].to_list())

    def test_mthfr_annotations_content(self, output_dir: Path, ensembl_db_path: Path) -> None:
        compile_module(MTHFR_DIR, output_dir)
        df = pl.read_parquet(output_dir / "annotations.parquet")

        assert df.height == df["rsid"].n_unique()
        rsids = set(df["rsid"].to_list())
        assert "rs1801133" in rsids
        assert "rs4680" in rsids
        genes = set(df["gene"].to_list())
        assert "MTHFR" in genes
        assert "COMT" in genes
        assert "SIRT1" in genes

    def test_mthfr_studies_content(self, output_dir: Path, ensembl_db_path: Path) -> None:
        compile_module(MTHFR_DIR, output_dir)
        df = pl.read_parquet(output_dir / "studies.parquet")

        assert df.height > 0
        assert {"rsid", "pmid", "conclusion"}.issubset(set(df.columns))
        pmids = set(df["pmid"].to_list())
        assert "9545397" in pmids
        assert "21732829" in pmids

    def test_cyp_weights_content(self, output_dir: Path, ensembl_db_path: Path) -> None:
        compile_module(CYP_DIR, output_dir)
        df = pl.read_parquet(output_dir / "weights.parquet")

        assert df.height == 21
        assert df["module"].unique().to_list() == ["cyp_panel"]

        states = set(df["state"].to_list())
        assert "significant" in states
        assert "risk" in states
        assert "neutral" in states

    def test_cyp_annotations_deduplication(self, output_dir: Path, ensembl_db_path: Path) -> None:
        compile_module(CYP_DIR, output_dir)
        df = pl.read_parquet(output_dir / "annotations.parquet")

        rsid_count = df["rsid"].n_unique()
        assert df.height == rsid_count
        categories = set(df["category"].to_list())
        assert categories == {"cyp2c19", "cyp2d6", "cyp2c9", "cyp3a4"}

    def test_cyp_studies_content(self, output_dir: Path, ensembl_db_path: Path) -> None:
        compile_module(CYP_DIR, output_dir)
        df = pl.read_parquet(output_dir / "studies.parquet")

        study_rsids = set(df["rsid"].to_list())
        weights_df = pl.read_parquet(output_dir / "weights.parquet")
        weight_rsids = set(weights_df["rsid"].to_list())
        assert study_rsids.issubset(weight_rsids)

    def test_alts_as_list(self, output_dir: Path, ensembl_db_path: Path) -> None:
        compile_module(CYP_DIR, output_dir)
        df = pl.read_parquet(output_dir / "weights.parquet")

        assert df.schema["alts"] == pl.List(pl.Utf8)
        alts_sample = df.filter(pl.col("rsid") == "rs4244285")["alts"].to_list()
        assert all(isinstance(a, list) for a in alts_sample)

    def test_positions_preserved(self, output_dir: Path, ensembl_db_path: Path) -> None:
        compile_module(MTHFR_DIR, output_dir)
        df = pl.read_parquet(output_dir / "weights.parquet")

        rs1801133 = df.filter(pl.col("rsid") == "rs1801133")
        assert rs1801133["chrom"].unique().to_list() == ["1"]
        assert rs1801133["start"].unique().to_list() == [11796321]

    def test_compile_nonexistent_dir(self, output_dir: Path) -> None:
        result = compile_module(Path("/nonexistent"), output_dir)
        assert not result.success
        assert len(result.errors) > 0

    def test_no_studies_ok(self, tmp_path: Path, output_dir: Path, ensembl_db_path: Path) -> None:
        spec_dir = _make_spec_dir(
            tmp_path,
            "no_studies",
            "rsid,chrom,start,ref,alts,genotype,weight,state,conclusion\n"
            "rs4244285,10,94781859,G,A,A/G,0.5,protective,Good variant\n",
        )
        result = compile_module(spec_dir, output_dir)
        assert result.success
        assert (output_dir / "weights.parquet").exists()
        assert (output_dir / "annotations.parquet").exists()
        assert not (output_dir / "studies.parquet").exists()
        assert result.stats["studies_rows"] == 0


# ── Compilation with resolution tests ─────────────────────────────────────────


class TestCompileWithResolution:
    """Compilation using real Ensembl resolution — rsid-only and position-only specs."""

    def test_rsid_only_spec_resolves_positions(
        self, tmp_path: Path, output_dir: Path, ensembl_db_path: Path
    ) -> None:
        """A spec with rsids but no positions should compile with positions filled in."""
        spec_dir = _make_spec_dir(
            tmp_path,
            "rsid_only",
            "rsid,genotype,weight,state,conclusion,gene,phenotype,category\n"
            "rs4244285,A/G,-0.8,risk,CYP2C19*2 het,CYP2C19,Drug metabolism,cyp2c19\n"
            "rs4244285,A/A,-1.5,risk,CYP2C19*2 hom,CYP2C19,Drug metabolism,cyp2c19\n"
            "rs4244285,G/G,0.0,neutral,CYP2C19 normal,CYP2C19,Drug metabolism,cyp2c19\n"
            "rs3892097,C/T,-0.7,risk,CYP2D6*4 het,CYP2D6,Drug metabolism,cyp2d6\n"
            "rs3892097,C/C,0.0,neutral,CYP2D6 normal,CYP2D6,Drug metabolism,cyp2d6\n"
            "rs3892097,T/T,-1.5,risk,CYP2D6*4 hom,CYP2D6,Drug metabolism,cyp2d6\n",
        )
        result = compile_module(spec_dir, output_dir, resolve_with_ensembl=True)
        assert result.success, f"Errors: {result.errors}"

        df = pl.read_parquet(output_dir / "weights.parquet")
        assert df.height == 6

        for row in df.iter_rows(named=True):
            rsid = row["rsid"]
            gt = CYP_GROUND_TRUTH[rsid]
            assert row["chrom"] == gt["chrom"], f"{rsid}: chrom mismatch"
            assert row["start"] == gt["start"], f"{rsid}: start mismatch"
            assert row["ref"] == gt["ref"], f"{rsid}: ref mismatch"

    def test_position_only_spec_resolves_rsids(
        self, tmp_path: Path, output_dir: Path, ensembl_db_path: Path
    ) -> None:
        """A spec with positions but no rsids should compile with rsids filled in."""
        spec_dir = _make_spec_dir(
            tmp_path,
            "pos_only",
            "chrom,start,ref,alts,genotype,weight,state,conclusion,gene,phenotype,category\n"
            "10,94781859,G,A,A/G,-0.8,risk,CYP2C19*2 het,CYP2C19,Drug metabolism,cyp2c19\n"
            "10,94781859,G,A,G/G,0.0,neutral,CYP2C19 normal,CYP2C19,Drug metabolism,cyp2c19\n"
            "22,42128945,C,T,C/T,-0.7,risk,CYP2D6*4 het,CYP2D6,Drug metabolism,cyp2d6\n"
            "22,42128945,C,T,C/C,0.0,neutral,CYP2D6 normal,CYP2D6,Drug metabolism,cyp2d6\n",
        )
        result = compile_module(spec_dir, output_dir, resolve_with_ensembl=True)
        assert result.success, f"Errors: {result.errors}"

        df = pl.read_parquet(output_dir / "weights.parquet")
        assert df.height == 4

        resolved_rsids = set(df["rsid"].drop_nulls().to_list())
        assert "rs4244285" in resolved_rsids
        assert "rs3892097" in resolved_rsids

    def test_mixed_spec_resolves_both_directions(
        self, tmp_path: Path, output_dir: Path, ensembl_db_path: Path
    ) -> None:
        """A spec mixing rsid-only and position-only rows resolves both."""
        spec_dir = _make_spec_dir(
            tmp_path,
            "mixed_ids",
            "rsid,chrom,start,ref,alts,genotype,weight,state,conclusion,gene,phenotype,category\n"
            "rs4244285,,,,,A/G,-0.8,risk,rsid-only row,CYP2C19,Drug metabolism,cyp2c19\n"
            ",10,94780653,G,A,A/G,-0.8,risk,position-only row,CYP2C19,Drug metabolism,cyp2c19\n"
            "rs3892097,22,42128945,C,T,C/T,-0.7,risk,complete row,CYP2D6,Drug metabolism,cyp2d6\n",
        )
        result = compile_module(spec_dir, output_dir, resolve_with_ensembl=True)
        assert result.success, f"Errors: {result.errors}"

        df = pl.read_parquet(output_dir / "weights.parquet")
        assert df.height == 3

        row_4244285 = df.filter(pl.col("rsid") == "rs4244285")
        assert row_4244285.height == 1
        assert row_4244285["chrom"][0] == "10"
        assert row_4244285["start"][0] == 94781859

        row_4986893 = df.filter(pl.col("rsid") == "rs4986893")
        assert row_4986893.height == 1
        assert row_4986893["chrom"][0] == "10"
        assert row_4986893["start"][0] == 94780653

        row_3892097 = df.filter(pl.col("rsid") == "rs3892097")
        assert row_3892097.height == 1
        assert row_3892097["chrom"][0] == "22"
        assert row_3892097["start"][0] == 42128945

    def test_no_resolve_flag_skips_resolution(
        self, tmp_path: Path, output_dir: Path
    ) -> None:
        """With resolve_with_ensembl=False, rsid-only rows keep no positions."""
        spec_dir = _make_spec_dir(
            tmp_path,
            "no_resolve",
            "rsid,genotype,weight,state,conclusion\n"
            "rs4244285,A/G,0.0,neutral,Test\n",
        )
        result = compile_module(spec_dir, output_dir, resolve_with_ensembl=False)
        assert result.success

        df = pl.read_parquet(output_dir / "weights.parquet")
        assert df["chrom"][0] is None
        assert df["start"][0] is None

    def test_rsid_only_annotations_have_rsid(
        self, tmp_path: Path, output_dir: Path, ensembl_db_path: Path
    ) -> None:
        """After resolution, annotations.parquet should have rsids filled in."""
        spec_dir = _make_spec_dir(
            tmp_path,
            "rsid_ann",
            "rsid,genotype,weight,state,conclusion,gene,phenotype,category\n"
            "rs4244285,A/G,-0.8,risk,CYP2C19*2 het,CYP2C19,Drug metabolism,cyp2c19\n"
            "rs4244285,G/G,0.0,neutral,Normal,CYP2C19,Drug metabolism,cyp2c19\n"
            "rs1057910,A/C,-0.6,risk,CYP2C9*3 het,CYP2C9,Warfarin,cyp2c9\n",
        )
        result = compile_module(spec_dir, output_dir, resolve_with_ensembl=True)
        assert result.success

        ann_df = pl.read_parquet(output_dir / "annotations.parquet")
        assert ann_df.height == 2
        rsids = set(ann_df["rsid"].to_list())
        assert rsids == {"rs4244285", "rs1057910"}

    def test_position_only_annotations_get_resolved_rsid(
        self, tmp_path: Path, output_dir: Path, ensembl_db_path: Path
    ) -> None:
        """Position-only variants should get rsids in annotations after resolution."""
        spec_dir = _make_spec_dir(
            tmp_path,
            "pos_ann",
            "chrom,start,ref,alts,genotype,weight,state,conclusion,gene,phenotype,category\n"
            "10,94781859,G,A,A/G,-0.8,risk,CYP2C19*2 het,CYP2C19,Drug metabolism,cyp2c19\n"
            "10,94781859,G,A,G/G,0.0,neutral,Normal,CYP2C19,Drug metabolism,cyp2c19\n",
        )
        result = compile_module(spec_dir, output_dir, resolve_with_ensembl=True)
        assert result.success

        ann_df = pl.read_parquet(output_dir / "annotations.parquet")
        assert ann_df.height == 1
        assert ann_df["rsid"][0] == "rs4244285"


# ── Round-trip consistency tests ───────────────────────────────────────────────


class TestRoundTrip:
    """Verify that compiling twice from the same spec produces identical output."""

    @pytest.mark.parametrize("spec_dir", [MTHFR_DIR, CYP_DIR], ids=["mthfr_nad", "cyp_panel"])
    def test_deterministic_compilation(
        self, spec_dir: Path, tmp_path: Path, ensembl_db_path: Path
    ) -> None:
        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"

        r1 = compile_module(spec_dir, out1)
        r2 = compile_module(spec_dir, out2)

        assert r1.success and r2.success

        for fname in ["weights.parquet", "annotations.parquet"]:
            df1 = pl.read_parquet(out1 / fname)
            df2 = pl.read_parquet(out2 / fname)
            assert df1.equals(df2), f"{fname} differs between runs"

        if (out1 / "studies.parquet").exists():
            s1 = pl.read_parquet(out1 / "studies.parquet")
            s2 = pl.read_parquet(out2 / "studies.parquet")
            assert s1.equals(s2), "studies.parquet differs between runs"
