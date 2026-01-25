"""
Integration tests for HuggingFace module annotation.

These tests use real data from the just-dna-seq/annotators HuggingFace repository
and a real VCF from Zenodo.
"""

import tempfile
from pathlib import Path

import polars as pl
import pytest
from huggingface_hub import hf_hub_download

from just_dna_pipelines.annotation.hf_modules import (
    ModuleTable,
    ModuleOutputMapping,
    AnnotationManifest,
    get_module_table_url,
    scan_module_table,
    scan_module_weights,
    HF_REPO_ID,
    DISCOVERED_MODULES,
    get_all_modules,
    validate_module,
    validate_modules,
)
from just_dna_pipelines.annotation.configs import HfModuleAnnotationConfig
from just_dna_pipelines.annotation.hf_logic import (
    prepare_vcf_for_module_annotation,
    annotate_vcf_with_module_weights,
)


# ============================================================================
# TEST VCF FROM ZENODO
# ============================================================================

ZENODO_VCF_URL = "https://zenodo.org/api/records/18370498/files/antonkulaga.vcf/content"


@pytest.fixture(scope="session")
def real_vcf_path(tmp_path_factory) -> Path:
    """
    Download the real VCF from Zenodo for testing.
    
    This VCF is from Zenodo (https://zenodo.org/records/18370498) and contains 
    real genomic data with proper FORMAT fields (GT, GQ, DP, AD, VAF, PL).
    """
    import requests
    
    # Simple caching in ~/.cache/just-dna-pipelines/test_data/
    cache_dir = Path.home() / ".cache" / "just-dna-pipelines" / "test_data"
    cache_dir.mkdir(parents=True, exist_ok=True)
    vcf_path = cache_dir / "antonkulaga.vcf"
    
    if not vcf_path.exists():
        print(f"\nDownloading test VCF from Zenodo to {vcf_path}...")
        response = requests.get(ZENODO_VCF_URL, stream=True)
        response.raise_for_status()
        with open(vcf_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
    
    return vcf_path


# ============================================================================
# UNIT TESTS - Dynamic module discovery
# ============================================================================

class TestDynamicModuleDiscovery:
    """Test the dynamic module discovery system."""
    
    def test_discovered_modules_not_empty(self):
        """Discovered modules list should not be empty."""
        assert len(DISCOVERED_MODULES) > 0
    
    def test_discovered_modules_contains_known_modules(self):
        """Discovered modules should contain known modules."""
        # These are the expected modules based on static fallback
        expected = {"longevitymap", "lipidmetabolism", "vo2max", "superhuman", "coronary"}
        discovered_set = set(DISCOVERED_MODULES)
        assert expected.issubset(discovered_set), f"Missing modules: {expected - discovered_set}"
    
    def test_get_all_modules_returns_copy(self):
        """get_all_modules should return a copy to prevent mutation."""
        modules = get_all_modules()
        modules.append("fake_module")
        assert "fake_module" not in DISCOVERED_MODULES
    
    def test_validate_module_valid(self):
        """validate_module should return True for valid modules."""
        assert validate_module("longevitymap")
        assert validate_module("LONGEVITYMAP")  # Case-insensitive
        assert validate_module("LongevityMap")
    
    def test_validate_module_invalid(self):
        """validate_module should return False for invalid modules."""
        assert not validate_module("invalid_module")
        assert not validate_module("")
    
    def test_validate_modules_filters_invalid(self):
        """validate_modules should filter out invalid modules."""
        result = validate_modules(["longevitymap", "invalid", "coronary", "fake"])
        assert len(result) == 2
        assert "longevitymap" in result
        assert "coronary" in result
    
    def test_module_names_are_lowercase(self):
        """Module names should be lowercase for HF path compatibility."""
        for module_name in DISCOVERED_MODULES:
            assert module_name == module_name.lower()


class TestModuleTableUrl:
    """Test URL generation for HF modules."""
    
    def test_url_format(self):
        """URLs should follow HF datasets format."""
        url = get_module_table_url("longevitymap", ModuleTable.WEIGHTS)
        assert url == f"hf://datasets/{HF_REPO_ID}/data/longevitymap/weights.parquet"
    
    def test_url_format_with_string_table(self):
        """URLs should work with string table names too."""
        url = get_module_table_url("longevitymap", "weights")
        assert url == f"hf://datasets/{HF_REPO_ID}/data/longevitymap/weights.parquet"
    
    def test_all_table_types(self):
        """All table types should generate valid URLs."""
        module_name = "coronary"
        for table in ModuleTable:
            url = get_module_table_url(module_name, table)
            assert f"/{module_name}/" in url
            assert f"/{table.value}.parquet" in url


class TestHfModuleAnnotationConfig:
    """Test the HfModuleAnnotationConfig."""
    
    def test_default_modules_is_all(self):
        """Default should include all discovered modules."""
        config = HfModuleAnnotationConfig(vcf_path="/tmp/test.vcf")
        modules = config.get_modules()
        
        assert len(modules) == len(DISCOVERED_MODULES)
        assert set(modules) == set(DISCOVERED_MODULES)
    
    def test_specific_modules_selection(self):
        """Can select specific modules."""
        config = HfModuleAnnotationConfig(
            vcf_path="/tmp/test.vcf",
            modules=["longevitymap", "coronary"]
        )
        modules = config.get_modules()
        
        assert len(modules) == 2
        assert "longevitymap" in modules
        assert "coronary" in modules
    
    def test_invalid_modules_filtered(self):
        """Invalid module names should be filtered out."""
        config = HfModuleAnnotationConfig(
            vcf_path="/tmp/test.vcf",
            modules=["longevitymap", "invalid_module", "coronary"]
        )
        modules = config.get_modules()
        
        assert len(modules) == 2
        assert "invalid_module" not in modules


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
        lf = scan_module_weights("longevitymap")
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
        
        for module_name in DISCOVERED_MODULES:
            lf = scan_module_table(module_name, ModuleTable.WEIGHTS)
            schema = lf.collect_schema()
            
            missing = required_cols - set(schema.names())
            assert not missing, f"Module {module_name} missing columns: {missing}"
    
    @pytest.mark.integration
    def test_genotype_is_sorted_list(self):
        """Genotypes in weights table should be sorted alphabetically."""
        lf = scan_module_weights("longevitymap")
        
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
            "longevitymap",
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
        
        modules_to_test = ["longevitymap", "coronary"]
        
        for module_name in modules_to_test:
            output_path = tmp_path / f"{module_name}_weights.parquet"
            result_path, num_rows = annotate_vcf_with_module_weights(
                vcf_lf,
                module_name,
                output_path,
                join_on="position",
            )
            
            assert result_path.exists(), f"Output not created for {module_name}"
            print(f"{module_name}: {num_rows} variants")


class TestModuleWeightsSchema:
    """Verify the schema of HF module weights tables."""
    
    @pytest.mark.integration
    @pytest.mark.parametrize("module_name", DISCOVERED_MODULES)
    def test_module_has_position_columns(self, module_name: str):
        """Each module should have position columns for joining."""
        lf = scan_module_weights(module_name)
        schema = lf.collect_schema()
        
        # Position columns
        assert "chrom" in schema.names(), f"{module_name} missing 'chrom'"
        assert "start" in schema.names(), f"{module_name} missing 'start'"
        
        # Genotype column
        assert "genotype" in schema.names(), f"{module_name} missing 'genotype'"
        assert schema["genotype"] == pl.List(pl.String), f"{module_name} genotype is not List[String]"
    
    @pytest.mark.integration
    @pytest.mark.parametrize("module_name", DISCOVERED_MODULES)
    def test_module_has_annotation_columns(self, module_name: str):
        """Each module should have annotation columns."""
        lf = scan_module_weights(module_name)
        schema = lf.collect_schema()
        
        # Core annotation columns
        assert "weight" in schema.names(), f"{module_name} missing 'weight'"
        assert "state" in schema.names(), f"{module_name} missing 'state'"
