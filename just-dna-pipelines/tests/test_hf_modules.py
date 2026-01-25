"""
Integration tests for HuggingFace module annotation.

These tests use real data from the just-dna-seq/annotators HuggingFace repository
and a real VCF from antonkulaga/personal-health.
"""

import tempfile
from pathlib import Path

import polars as pl
import pytest
from huggingface_hub import hf_hub_download

from just_dna_pipelines.annotation.hf_modules import (
    AnnotatorModule,
    ModuleTable,
    ModuleOutputMapping,
    AnnotationManifest,
    get_module_table_url,
    scan_module_table,
    scan_module_weights,
    HF_REPO_ID,
)
from just_dna_pipelines.annotation.configs import HfModuleAnnotationConfig
from just_dna_pipelines.annotation.hf_logic import (
    prepare_vcf_for_module_annotation,
    annotate_vcf_with_module_weights,
)


# ============================================================================
# TEST VCF FROM HUGGINGFACE
# ============================================================================

TEST_VCF_REPO = "antonkulaga/personal-health"
TEST_VCF_PATH = "genetics/antonkulaga.vcf"


@pytest.fixture(scope="session")
def real_vcf_path() -> Path:
    """
    Download the real VCF from HuggingFace for testing.
    
    This VCF is from antonkulaga/personal-health and contains real genomic data
    with proper FORMAT fields (GT, GQ, DP, AD, VAF, PL).
    """
    vcf_path = hf_hub_download(
        repo_id=TEST_VCF_REPO,
        filename=TEST_VCF_PATH,
        repo_type="dataset",
    )
    return Path(vcf_path)


# ============================================================================
# UNIT TESTS - No network required after initial enum definition
# ============================================================================

class TestAnnotatorModuleEnum:
    """Test the AnnotatorModule enum."""
    
    def test_all_modules_returns_all(self):
        """All modules should be returned."""
        modules = AnnotatorModule.all_modules()
        assert len(modules) == 5
        assert AnnotatorModule.LONGEVITYMAP in modules
        assert AnnotatorModule.LIPIDMETABOLISM in modules
        assert AnnotatorModule.VO2MAX in modules
        assert AnnotatorModule.SUPERHUMAN in modules
        assert AnnotatorModule.CORONARY in modules
    
    def test_from_string_case_insensitive(self):
        """Module parsing should be case-insensitive."""
        assert AnnotatorModule.from_string("longevitymap") == AnnotatorModule.LONGEVITYMAP
        assert AnnotatorModule.from_string("LONGEVITYMAP") == AnnotatorModule.LONGEVITYMAP
        assert AnnotatorModule.from_string("LongevityMap") == AnnotatorModule.LONGEVITYMAP
    
    def test_from_string_invalid_raises(self):
        """Invalid module name should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown module"):
            AnnotatorModule.from_string("invalid_module")
    
    def test_module_value_is_lowercase(self):
        """Module values should be lowercase for HF path compatibility."""
        for module in AnnotatorModule.all_modules():
            assert module.value == module.value.lower()


class TestModuleTableUrl:
    """Test URL generation for HF modules."""
    
    def test_url_format(self):
        """URLs should follow HF datasets format."""
        url = get_module_table_url(AnnotatorModule.LONGEVITYMAP, ModuleTable.WEIGHTS)
        assert url == f"hf://datasets/{HF_REPO_ID}/data/longevitymap/weights.parquet"
    
    def test_all_table_types(self):
        """All table types should generate valid URLs."""
        module = AnnotatorModule.CORONARY
        for table in ModuleTable:
            url = get_module_table_url(module, table)
            assert f"/{module.value}/" in url
            assert f"/{table.value}.parquet" in url


class TestHfModuleAnnotationConfig:
    """Test the HfModuleAnnotationConfig."""
    
    def test_default_modules_is_all(self):
        """Default should include all modules."""
        config = HfModuleAnnotationConfig(vcf_path="/tmp/test.vcf")
        modules = config.get_modules()
        
        assert len(modules) == len(AnnotatorModule.all_modules())
    
    def test_specific_modules_selection(self):
        """Can select specific modules."""
        config = HfModuleAnnotationConfig(
            vcf_path="/tmp/test.vcf",
            modules=["longevitymap", "coronary"]
        )
        modules = config.get_modules()
        
        assert len(modules) == 2
        assert AnnotatorModule.LONGEVITYMAP in modules
        assert AnnotatorModule.CORONARY in modules


class TestAnnotationManifest:
    """Test the AnnotationManifest model."""
    
    def test_manifest_serialization(self):
        """Manifest should serialize to JSON correctly."""
        manifest = AnnotationManifest(
            user_name="test_user",
            sample_name="sample1",
            source_vcf="/path/to/sample.vcf",
            modules=[
                ModuleOutputMapping(
                    module="longevitymap",
                    weights_path="/output/longevitymap_weights.parquet",
                ),
                ModuleOutputMapping(
                    module="coronary",
                    weights_path="/output/coronary_weights.parquet",
                ),
            ],
            total_variants_annotated=150,
        )
        
        json_str = manifest.model_dump_json()
        assert "test_user" in json_str
        assert "longevitymap" in json_str
        assert "coronary" in json_str
        
        # Round-trip
        parsed = AnnotationManifest.model_validate_json(json_str)
        assert parsed.user_name == manifest.user_name
        assert len(parsed.modules) == 2


# ============================================================================
# INTEGRATION TESTS - Require network access to HuggingFace
# ============================================================================

class TestHfModuleLoading:
    """Test loading modules from HuggingFace (integration tests)."""
    
    @pytest.mark.integration
    def test_scan_longevitymap_weights(self):
        """Load longevitymap weights table from HF."""
        lf = scan_module_weights(AnnotatorModule.LONGEVITYMAP)
        schema = lf.collect_schema()
        
        # Required columns per HF_MODULES.md
        assert "rsid" in schema.names()
        assert "genotype" in schema.names()
        assert "module" in schema.names()
        assert "weight" in schema.names()
        assert "state" in schema.names()
        
        # Position columns for position-based joining
        assert "chrom" in schema.names()
        assert "start" in schema.names()
        
        # Genotype should be List[String]
        assert schema["genotype"] == pl.List(pl.String)
    
    @pytest.mark.integration
    def test_scan_all_modules_have_weights(self):
        """All modules should have a weights table with required columns."""
        required_cols = {"rsid", "genotype", "module", "chrom", "start"}
        
        for module in AnnotatorModule.all_modules():
            lf = scan_module_table(module, ModuleTable.WEIGHTS)
            schema = lf.collect_schema()
            
            missing = required_cols - set(schema.names())
            assert not missing, f"Module {module.value} missing columns: {missing}"
    
    @pytest.mark.integration
    def test_genotype_is_sorted_list(self):
        """Genotypes in weights table should be sorted alphabetically."""
        lf = scan_module_weights(AnnotatorModule.LONGEVITYMAP)
        
        # Check first 100 rows
        df = lf.head(100).collect()
        
        for genotype in df["genotype"].to_list():
            assert genotype == sorted(genotype), f"Genotype not sorted: {genotype}"


class TestVcfPreparation:
    """Test VCF preparation with real VCF from HuggingFace."""
    
    @pytest.mark.integration
    def test_prepare_real_vcf(self, real_vcf_path: Path):
        """Prepare the real VCF and verify genotype computation."""
        lf = prepare_vcf_for_module_annotation(real_vcf_path)
        
        # Check schema has required columns
        schema = lf.collect_schema()
        assert "chrom" in schema.names()
        assert "start" in schema.names()
        assert "ref" in schema.names()
        assert "alt" in schema.names()
        assert "genotype" in schema.names()
        
        # Genotype should be List[String]
        assert schema["genotype"] == pl.List(pl.String)
    
    @pytest.mark.integration
    def test_genotype_computation(self, real_vcf_path: Path):
        """Verify genotypes are computed correctly."""
        lf = prepare_vcf_for_module_annotation(real_vcf_path)
        
        # Get first 100 rows
        df = lf.head(100).collect()
        
        # All genotypes should be sorted lists
        for genotype in df["genotype"].drop_nulls().to_list():
            assert isinstance(genotype, list), f"Expected list, got: {type(genotype)}"
            if len(genotype) > 0:
                assert genotype == sorted(genotype), f"Genotype not sorted: {genotype}"
    
    @pytest.mark.integration
    def test_chromosome_normalization(self, real_vcf_path: Path):
        """Verify chromosome names are normalized (no 'chr' prefix)."""
        lf = prepare_vcf_for_module_annotation(real_vcf_path)
        
        # Check first 1000 rows
        df = lf.head(1000).collect()
        
        chroms = df["chrom"].unique().to_list()
        for chrom in chroms:
            assert not chrom.startswith("chr"), f"Chrom should not have 'chr' prefix: {chrom}"


class TestAnnotationWithRealData:
    """Test annotation with real VCF and HF modules."""
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_annotate_with_longevitymap(self, real_vcf_path: Path, tmp_path: Path):
        """Annotate real VCF with longevitymap module."""
        # Prepare VCF
        vcf_lf = prepare_vcf_for_module_annotation(real_vcf_path)
        
        # Annotate with position-based join
        output_path = tmp_path / "longevitymap_weights.parquet"
        result_path, num_rows = annotate_vcf_with_module_weights(
            vcf_lf,
            AnnotatorModule.LONGEVITYMAP,
            output_path,
            join_on="position",
        )
        
        assert result_path.exists()
        
        # Check output
        result_df = pl.read_parquet(result_path)
        assert "chrom" in result_df.columns
        assert "start" in result_df.columns
        assert "genotype" in result_df.columns
        
        # If there are matches, weight columns should be present
        if num_rows > 0 and "weight" in result_df.columns:
            # Check that some rows have weight annotations
            has_weights = result_df.filter(pl.col("weight").is_not_null()).height
            print(f"Rows with weight annotations: {has_weights} / {num_rows}")
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_annotate_with_multiple_modules(self, real_vcf_path: Path, tmp_path: Path):
        """Annotate real VCF with multiple modules."""
        vcf_lf = prepare_vcf_for_module_annotation(real_vcf_path)
        
        modules_to_test = [AnnotatorModule.LONGEVITYMAP, AnnotatorModule.CORONARY]
        
        for module in modules_to_test:
            output_path = tmp_path / f"{module.value}_weights.parquet"
            result_path, num_rows = annotate_vcf_with_module_weights(
                vcf_lf,
                module,
                output_path,
                join_on="position",
            )
            
            assert result_path.exists(), f"Output not created for {module.value}"
            print(f"{module.value}: {num_rows} variants")


class TestModuleWeightsSchema:
    """Verify the schema of HF module weights tables."""
    
    @pytest.mark.integration
    @pytest.mark.parametrize("module", AnnotatorModule.all_modules())
    def test_module_has_position_columns(self, module: AnnotatorModule):
        """Each module should have position columns for joining."""
        lf = scan_module_weights(module)
        schema = lf.collect_schema()
        
        # Position columns
        assert "chrom" in schema.names(), f"{module.value} missing 'chrom'"
        assert "start" in schema.names(), f"{module.value} missing 'start'"
        
        # Genotype column
        assert "genotype" in schema.names(), f"{module.value} missing 'genotype'"
        assert schema["genotype"] == pl.List(pl.String), f"{module.value} genotype is not List[String]"
    
    @pytest.mark.integration
    @pytest.mark.parametrize("module", AnnotatorModule.all_modules())
    def test_module_has_annotation_columns(self, module: AnnotatorModule):
        """Each module should have annotation columns."""
        lf = scan_module_weights(module)
        schema = lf.collect_schema()
        
        # Core annotation columns
        assert "weight" in schema.names(), f"{module.value} missing 'weight'"
        assert "state" in schema.names(), f"{module.value} missing 'state'"
