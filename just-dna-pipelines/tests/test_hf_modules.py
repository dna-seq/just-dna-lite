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
    ModuleInfo,
    ModuleTable,
    ModuleOutputMapping,
    AnnotationManifest,
    get_module_table_url,
    scan_module_table,
    scan_module_weights,
    HF_REPO_ID,
    DISCOVERED_MODULES,
    MODULE_INFOS,
    get_all_modules,
    validate_module,
    validate_modules,
)
from just_dna_pipelines.annotation.configs import HfModuleAnnotationConfig
from just_dna_pipelines.annotation.hf_logic import (
    annotate_vcf_with_module_weights,
    prepare_vcf_for_module_annotation,
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

@pytest.mark.integration
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
    """Test URL generation for HF modules (offline — uses synthetic ModuleInfo)."""

    @pytest.fixture()
    def sample_module_info(self) -> ModuleInfo:
        base = f"datasets/{HF_REPO_ID}/data/longevitymap"
        return ModuleInfo(
            name="longevitymap",
            repo_id=HF_REPO_ID,
            path=base,
            weights_url=f"hf://{base}/weights.parquet",
            annotations_url=f"hf://{base}/annotations.parquet",
            studies_url=f"hf://{base}/studies.parquet",
        )

    def test_url_format(self, sample_module_info):
        """URLs should follow HF datasets format."""
        url = get_module_table_url("longevitymap", ModuleTable.WEIGHTS, module_info=sample_module_info)
        assert url == f"hf://datasets/{HF_REPO_ID}/data/longevitymap/weights.parquet"

    def test_url_format_with_string_table(self, sample_module_info):
        """URLs should work with string table names too."""
        url = get_module_table_url("longevitymap", "weights", module_info=sample_module_info)
        assert url == f"hf://datasets/{HF_REPO_ID}/data/longevitymap/weights.parquet"

    def test_all_table_types(self):
        """All table types should generate valid URLs for a synthetic module."""
        module_name = "coronary"
        base = f"datasets/{HF_REPO_ID}/data/{module_name}"
        info = ModuleInfo(
            name=module_name,
            repo_id=HF_REPO_ID,
            path=base,
            weights_url=f"hf://{base}/weights.parquet",
            annotations_url=f"hf://{base}/annotations.parquet",
            studies_url=f"hf://{base}/studies.parquet",
        )
        for table in ModuleTable:
            url = get_module_table_url(module_name, table, module_info=info)
            assert f"/{module_name}/" in url
            # LEAD is an alias for whichever family carries the module's rows, not a file name of
            # its own — for this weights-led module it resolves to weights.parquet.
            expected = "weights" if table is ModuleTable.LEAD else table.value
            assert f"/{expected}.parquet" in url


@pytest.mark.integration
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
    def test_scan_all_modules_have_a_joinable_lead_table(self):
        """Every module's lead table must carry what a VCF join needs.

        `rsid`, `genotype` and `module` are the universal floor: a weights-led module is joined by
        position and a 0.4-led one by rsid, but both need an rsid and a genotype to match on. The
        position columns are asserted separately, against the weights-led modules that must have
        them — this used to demand them of every module, which only passed because no module led by
        a 0.4 table had been published yet.
        """
        required_cols = {"rsid", "genotype", "module"}

        for module_name in DISCOVERED_MODULES:
            lf = scan_module_table(module_name, ModuleTable.LEAD)
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


# The weights contract applies to the modules that actually have weights. Splitting the parameter
# list rather than skipping inside the test keeps a 0.4-led module from reporting as "passed" for a
# contract it was never asked to meet.
WEIGHTS_LED_MODULES = [n for n, i in MODULE_INFOS.items() if i.lead_table == "weights"]
TABLE_LED_MODULES = [n for n, i in MODULE_INFOS.items() if i.lead_table != "weights"]


class TestModuleWeightsSchema:
    """Verify the schema of HF module weights tables."""

    @pytest.mark.integration
    @pytest.mark.parametrize("module_name", WEIGHTS_LED_MODULES)
    def test_module_has_position_columns(self, module_name: str):
        """Each weights-led module should have position columns for joining."""
        lf = scan_module_weights(module_name)
        schema = lf.collect_schema()

        # Position columns
        assert "chrom" in schema.names(), f"{module_name} missing 'chrom'"
        assert "start" in schema.names(), f"{module_name} missing 'start'"

        # Genotype column
        assert "genotype" in schema.names(), f"{module_name} missing 'genotype'"
        assert schema["genotype"] == pl.List(pl.String), f"{module_name} genotype is not List[String]"

    @pytest.mark.integration
    @pytest.mark.parametrize("module_name", WEIGHTS_LED_MODULES)
    def test_module_has_annotation_columns(self, module_name: str):
        """Each weights-led module should have annotation columns."""
        lf = scan_module_weights(module_name)
        schema = lf.collect_schema()

        # Core annotation columns
        assert "weight" in schema.names(), f"{module_name} missing 'weight'"
        assert "state" in schema.names(), f"{module_name} missing 'state'"

    @pytest.mark.integration
    @pytest.mark.parametrize("module_name", TABLE_LED_MODULES)
    def test_table_led_module_is_rsid_joinable(self, module_name: str):
        """A published 0.4-led module must be joinable the one way it can be: rsid + genotype.

        It has no weights, and asking for that table is an error rather than an empty result. Its
        genotype is the authored string, not the list a weights row carries — the report helpers
        accept both for exactly this reason.
        """
        with pytest.raises(ValueError, match="no weights table"):
            scan_module_weights(module_name)

        lf = scan_module_table(module_name, ModuleTable.LEAD)
        schema = lf.collect_schema()
        assert "rsid" in schema.names(), f"{module_name} missing 'rsid'"
        assert schema["genotype"] == pl.String, f"{module_name} genotype is not String"
        # every row must actually carry an rsid, or the only available join matches nothing
        unmatched = lf.select(pl.col("rsid").is_null().sum()).collect().item()
        assert unmatched == 0, f"{module_name} has {unmatched} row(s) with no rsid to join on"


class TestLeadTableDiscovery:
    """Discovery must recognise a module led by a 0.4 table family, not weights alone.

    Ground truth is the real compiled modules under data/interim/v1_port when they are present:
    `coronary` is weights-led, `pharmgkb` is pharm_variants-led with no weights.parquet at all.
    """

    PORT_ROOT = Path("data/interim/v1_port")

    def _probe(self, module: str):
        import fsspec
        from just_dna_pipelines.annotation.hf_modules import _probe_module_at_path

        base = (self.PORT_ROOT / module).resolve()
        if not base.is_dir():
            pytest.skip(f"{base} not built")
        return _probe_module_at_path(
            fsspec.filesystem("file"), str(base), "file", module, str(base), str(base)
        )

    def test_weights_led_module_is_unchanged(self):
        info = self._probe("coronary")
        assert info is not None
        assert info.lead_table == "weights"
        # a weights-led module still answers to weights_url, and lead_url agrees with it
        assert info.weights_url is not None
        assert info.lead_url == info.weights_url

    def test_pharm_variants_led_module_is_discovered(self):
        info = self._probe("pharmgkb")
        assert info is not None, "a pharm_variants-led module must be discoverable"
        assert info.lead_table == "pharm_variants"
        assert info.lead_url.endswith("pharm_variants.parquet")
        # it genuinely has no weights table — that is the point
        assert info.weights_url is None

    def test_a_directory_with_no_lead_table_is_not_a_module(self, tmp_path):
        import fsspec
        from just_dna_pipelines.annotation.hf_modules import _probe_module_at_path

        (tmp_path / "sources.parquet").touch()   # a side table alone is not a module
        info = _probe_module_at_path(
            fsspec.filesystem("file"), str(tmp_path), "file", "x", str(tmp_path), str(tmp_path)
        )
        assert info is None

    def test_lead_url_defaults_to_weights_for_a_hand_built_info(self):
        """Callers predating the lead table build ModuleInfo directly and must keep working."""
        info = ModuleInfo(
            name="coronary", repo_id="org/repo", path="p", weights_url="hf://p/weights.parquet"
        )
        assert info.lead_url == "hf://p/weights.parquet"
        assert get_module_table_url("coronary", ModuleTable.LEAD, module_info=info).endswith(
            "weights.parquet"
        )

    def test_asking_for_weights_on_a_pharm_module_says_what_to_use(self):
        info = ModuleInfo(
            name="pharmgkb", repo_id="org/repo", path="p",
            lead_table="pharm_variants", lead_url="hf://p/pharm_variants.parquet",
        )
        with pytest.raises(ValueError, match="pharm_variants"):
            get_module_table_url("pharmgkb", ModuleTable.WEIGHTS, module_info=info)


def _module_genotypes_as_vcf(genotypes: list[str] | list[list[str]]) -> list[list[str]]:
    """Put a module's authored genotypes into the VCF's representation.

    A real VCF's ``genotype`` is always ``List(String)`` — ``io._compute_genotype_expr`` gathers
    alleles by GT index and sorts them. A ``pharm_variants`` table stores the authored string
    (``"G/G"``). A fixture that hands the engine the *module's* representation on the VCF side is
    testing a join that cannot happen in production, which is how the dtype mismatch shipped.
    """
    return [
        sorted(a for a in g.replace("|", "/").split("/") if a) if isinstance(g, str) else list(g)
        for g in genotypes
    ]


class TestLeadJoinStrategy:
    """How a lead table is classified — by the schema it has, not by its family name."""

    def test_weights_shape_joins_on_position(self):
        from just_dna_pipelines.annotation.hf_logic import _lead_join_strategy

        lf = pl.LazyFrame({"chrom": ["1"], "start": [100], "rsid": ["rs1"], "genotype": [["A", "G"]]})
        assert _lead_join_strategy(lf)[0] == "position"

    def test_coordinates_null_throughout_downgrade_to_rsid(self):
        """An rsid-authored 0.4 table is typed with coordinates but carries none."""
        from just_dna_pipelines.annotation.hf_logic import _lead_join_strategy

        lf = pl.LazyFrame(
            {"chrom": [None], "start": [None], "rsid": ["rs1"], "genotype": ["A/G"]},
            schema={"chrom": pl.String, "start": pl.Int64, "rsid": pl.String, "genotype": pl.String},
        )
        assert _lead_join_strategy(lf)[0] == "rsid"

    def test_a_table_with_no_variant_key_is_unsupported(self):
        """diplotypes / pgs / allele_function carry neither coordinates nor rsid + genotype."""
        from just_dna_pipelines.annotation.hf_logic import _lead_join_strategy

        diplotypes = pl.LazyFrame({
            "module": ["m"], "gene": ["CYP2D6"],
            "haplotype_a": ["*1"], "haplotype_b": ["*4"], "conclusion": ["poor metabolizer"],
        })
        strategy, reason = _lead_join_strategy(diplotypes)
        assert strategy == "unsupported"
        # the reason must name what was missing, or a skipped module is unexplainable
        assert "rsid" in reason and "genotype" in reason


class TestLeadGenotypeNormalization:
    """The 0.4 families store the authored genotype string; the VCF side is always a sorted list."""

    @pytest.mark.parametrize(
        "authored,expected",
        [
            ("C/C", ["C", "C"]),
            ("A/G", ["A", "G"]),          # unphased: the grammar already requires sorted alleles
            ("G|A", ["G", "A"]),          # phased: homolog order, NOT sorted — see below
            ("T", ["T"]),                 # hemizygous / haploid contig
            ("G/", ["G"]),                # a trailing separator is not a third allele
        ],
    )
    def test_string_genotypes_become_lists_in_the_compilers_own_order(self, authored, expected):
        from just_dna_pipelines.annotation.hf_logic import _normalize_lead_genotype

        out = _normalize_lead_genotype(pl.LazyFrame({"genotype": [authored]})).collect()
        assert out["genotype"].to_list() == [expected]

    def test_a_phased_genotype_keeps_homolog_order(self):
        """`A|G` and `G|A` are different rows: phase says which allele sits on which homolog.

        Sorting here would fold them into one join key and manufacture a match the module never
        stated. `weights.parquet` keeps the authored order (the compiler's `_split_genotype` does
        not sort, and carries phase in its own column), so a 0.4 table must too.
        """
        from just_dna_pipelines.annotation.hf_logic import _normalize_lead_genotype

        out = _normalize_lead_genotype(pl.LazyFrame({"genotype": ["A|G", "G|A"]})).collect()
        assert out["genotype"].to_list() == [["A", "G"], ["G", "A"]]

    def test_it_agrees_with_the_compiler_that_materializes_weights(self):
        """Ground truth: our expression must equal `just_dna_compiler`'s own splitter."""
        from just_dna_compiler.compiler import _split_genotype

        from just_dna_pipelines.annotation.hf_logic import _normalize_lead_genotype

        authored = ["A/G", "C/C", "G|A", "A|G", "T", "AT/AT", "C/CT"]
        ours = _normalize_lead_genotype(
            pl.LazyFrame({"genotype": authored})
        ).collect()["genotype"].to_list()
        assert ours == [_split_genotype(g) for g in authored]

    def test_null_survives_and_a_list_column_is_untouched(self):
        from just_dna_pipelines.annotation.hf_logic import _normalize_lead_genotype

        assert _normalize_lead_genotype(
            pl.LazyFrame({"genotype": [None]}, schema={"genotype": pl.String})
        ).collect()["genotype"].to_list() == [None]

        already = pl.LazyFrame({"genotype": [["A", "G"]]})
        assert _normalize_lead_genotype(already).collect()["genotype"].to_list() == [["A", "G"]]

    def test_the_unnormalized_join_is_a_schema_error(self):
        """The premise this function exists for: polars refuses List[str] against String.

        This is the crash `user_hf_module_annotations` hit on every live pharmgkb run — worth
        pinning, because if a future polars silently coerced instead, normalization would look
        redundant while quietly changing which rows match.
        """
        vcf = pl.LazyFrame({"rsid": ["rs1"], "genotype": [["A", "G"]]})
        module = pl.LazyFrame({"rsid": ["rs1"], "genotype": ["A/G"], "drug": ["atorvastatin"]})
        with pytest.raises(pl.exceptions.SchemaError, match="genotype"):
            vcf.join(module, on=["rsid", "genotype"], how="left").collect()

    def test_normalizing_the_module_side_makes_that_join_succeed(self):
        """The other half: after normalization the same join matches, and stays a list.

        Only the module side is normalized — the VCF is already `List(Utf8)` — so the join key
        keeps the artifact's own representation rather than being folded back to a slash string.
        """
        from just_dna_pipelines.annotation.hf_logic import _normalize_lead_genotype

        vcf = pl.LazyFrame({"rsid": ["rs1", "rs2"], "genotype": [["A", "G"], ["C", "C"]]})
        module = pl.LazyFrame({
            "rsid": ["rs1", "rs2"],
            "genotype": ["A/G", "C/C"],
            "drug": ["atorvastatin", "warfarin"],
        })
        joined = vcf.join(
            _normalize_lead_genotype(module), on=["rsid", "genotype"], how="left"
        ).collect()
        assert joined["drug"].to_list() == ["atorvastatin", "warfarin"]
        assert joined.schema["genotype"] == pl.List(pl.String)
        assert joined["genotype"].to_list() == [["A", "G"], ["C", "C"]]


class TestVcfSpellingsTheEngineMustFold:
    """VCF-legal spellings a module never writes. Both were silent losses (format RM60 / RM64)."""

    @pytest.mark.parametrize(
        "vcf_contig,expected",
        [
            ("chrM", "MT"),   # hs38DH: the strip alone made this `M`, which no module has
            ("M", "MT"),
            ("MT", "MT"),
            ("chr1", "1"),
            ("1", "1"),
            ("X", "X"),
        ],
    )
    def test_mitochondrial_contigs_fold_onto_the_module_spelling(self, vcf_contig, expected):
        from just_dna_pipelines.annotation.hf_logic import _normalize_vcf_contigs

        out = _normalize_vcf_contigs(pl.LazyFrame({"chrom": [vcf_contig]})).collect()
        assert out["chrom"].to_list() == [expected]

    def test_an_unrecognized_contig_is_left_alone_rather_than_dropped(self):
        """A scaffold matches no module, but it must survive as a row."""
        from just_dna_pipelines.annotation.hf_logic import _normalize_vcf_contigs

        out = _normalize_vcf_contigs(
            pl.LazyFrame({"chrom": ["chrUn_KI270742v1", "HLA-A*01:01:01:01"]})
        ).collect()
        assert out.height == 2
        assert "HLA-A*01:01:01:01" in out["chrom"].to_list()

    def test_a_multi_id_record_matches_on_every_identifier_it_carries(self, tmp_path):
        """VCF §1.6.1.3: ID is a semicolon-separated list; the authored side names one variant."""
        from just_dna_pipelines.annotation.hf_logic import annotate_vcf_with_module_weights

        lead = tmp_path / "pharm_variants.parquet"
        pl.DataFrame({
            "module": ["pgx"], "rsid": ["rs456"], "chrom": [None], "start": [None],
            "genotype": ["A/G"], "drug": ["warfarin"], "conclusion": ["reduced dose"],
        }, schema_overrides={"chrom": pl.String, "start": pl.Int64}).write_parquet(lead)
        info = ModuleInfo(
            name="pgx", repo_id="org/repo", path=str(tmp_path),
            lead_table="pharm_variants", lead_url=str(lead),
        )
        # the module's rsid is the *second* identifier on the record
        vcf = pl.LazyFrame({
            "chrom": ["1"], "start": [100], "rsid": ["rs123;rs456"], "genotype": [["A", "G"]]
        })

        out, n = annotate_vcf_with_module_weights(
            vcf, "pgx", tmp_path / "out.parquet", module_info=info
        )
        assert n == 1, "a record's second ID must be matchable"
        result = pl.read_parquet(out)
        assert result["drug"].to_list() == ["warfarin"]
        # the record keeps its ID verbatim; the join key is not leaked into the output
        assert result["rsid"].to_list() == ["rs123;rs456"]
        assert not [c for c in result.columns if c.startswith("_rsid")]


class TestPharmVariantsAnnotation:
    """A pharm_variants-led module has no coordinates, so it must join on rsid and still annotate."""

    PORT_ROOT = Path("data/interim/v1_port")

    def test_join_downgrades_to_rsid_and_matches_real_rows(self, tmp_path):
        import fsspec
        from just_dna_pipelines.annotation.hf_modules import _probe_module_at_path
        from just_dna_pipelines.annotation.hf_logic import (
            _lead_join_strategy,
            _normalize_lead_genotype,
            annotate_vcf_with_module_weights,
        )

        base = (self.PORT_ROOT / "pharmgkb").resolve()
        if not base.is_dir():
            pytest.skip(f"{base} not built")
        info = _probe_module_at_path(
            fsspec.filesystem("file"), str(base), "file", "pharmgkb", str(base), str(base)
        )

        table = pl.read_parquet(base / "pharm_variants.parquet")
        # the compiler materialises 0.4 tables verbatim from CSV, so an rsid-authored one has no
        # coordinates — a position join would match nothing
        lead = _normalize_lead_genotype(pl.scan_parquet(base / "pharm_variants.parquet"))
        assert _lead_join_strategy(lead)[0] == "rsid"

        picks = table.select("rsid", "genotype").unique().head(3)
        # A real VCF / normalized parquet stores genotype as List[str], not the authored
        # slash-string the 0.4 table carries. Planting strings here used to hide the
        # SchemaError that annotation hits on every live pharmgkb run.
        vcf = pl.DataFrame({
            "chrom": ["1"] * 3 + ["2"],
            "start": [100, 200, 300, 400],
            "rsid": picks["rsid"].to_list() + ["rs_absent_from_module"],
            # the VCF side is List(String), never the module's authored string — joining the two
            # straight is a SchemaError, which is the bug this fixture used to hide
            "genotype": _module_genotypes_as_vcf(picks["genotype"].to_list()) + [["A", "A"]],
        }).lazy()
        assert vcf.collect_schema()["genotype"] == pl.List(pl.String)

        out, n = annotate_vcf_with_module_weights(
            vcf, "pharmgkb", tmp_path / "pgx.parquet", module_info=info
        )
        assert n > 0, "the default position join must downgrade to rsid rather than annotate nothing"

        result = pl.read_parquet(out)
        # every annotated row belongs to one of the three rsids we planted; the absent one is gone
        assert set(result["rsid"].unique()) == set(picks["rsid"].unique())
        # ground truth: the join fans out to exactly the module's rows for those (rsid, genotype)
        expected = table.join(picks, on=["rsid", "genotype"], how="semi").height
        assert n == expected
        # and the pharmacogenomics facts survive the join
        assert {"drug", "evidence_level", "phenotype_category"}.issubset(result.columns)
        assert result["drug"].null_count() == 0

    def test_annotate_joins_vcf_lists_to_authored_strings(self, tmp_path: Path):
        """End-to-end on a synthetic fixture: a pharm_variants-led module annotates a real-shaped VCF.

        The companion above pins the same path against the real pharmgkb module; this one needs no
        network and states the expected rows outright.
        """
        lead = tmp_path / "pharm_variants.parquet"
        pl.DataFrame({
            "rsid": ["rs1", "rs1", "rs2"],
            "genotype": ["A/G", "G/G", "C/C"],
            "drug": ["atorvastatin", "atorvastatin", "warfarin"],
            "evidence_level": ["1A", "1A", "2A"],
            "phenotype_category": ["Dosage", "Dosage", "Metabolism"],
        }).write_parquet(lead)
        info = ModuleInfo(
            name="pgx",
            repo_id="org/repo",
            path=str(tmp_path),
            lead_table="pharm_variants",
            lead_url=str(lead),
        )
        vcf = pl.DataFrame({
            "chrom": ["19", "19", "10"],
            "start": [1, 1, 2],
            "rsid": ["rs1", "rs1", "rs_absent"],
            "genotype": [["A", "G"], ["G", "G"], ["T", "T"]],
        }).lazy()

        out, n = annotate_vcf_with_module_weights(
            vcf, "pgx", tmp_path / "annotated.parquet", module_info=info
        )
        result = pl.read_parquet(out)
        assert n == 2
        assert set(result["rsid"].unique()) == {"rs1"}
        assert set(result["drug"].drop_nulls().to_list()) == {"atorvastatin"}

    def test_a_module_with_no_joinable_key_is_skipped_not_fatal(self, tmp_path):
        """A diplotypes-led module must not take the run down; it used to raise ColumnNotFound."""
        from just_dna_pipelines.annotation.hf_logic import (
            UnsupportedLeadTable,
            annotate_vcf_with_module_weights,
        )

        lead = tmp_path / "diplotypes.parquet"
        pl.DataFrame({
            "module": ["cyp"], "gene": ["CYP2D6"],
            "haplotype_a": ["*1"], "haplotype_b": ["*4"], "conclusion": ["intermediate"],
        }).write_parquet(lead)
        info = ModuleInfo(
            name="cyp", repo_id="org/repo", path=str(tmp_path),
            lead_table="diplotypes", lead_url=str(lead),
        )
        vcf = pl.LazyFrame({"chrom": ["1"], "start": [100], "rsid": ["rs1"], "genotype": [["A", "G"]]})

        with pytest.raises(UnsupportedLeadTable, match="diplotypes|rsid"):
            annotate_vcf_with_module_weights(vcf, "cyp", tmp_path / "out.parquet", module_info=info)


class TestOneBadModuleDoesNotSinkTheRun:
    """An unjoinable module used to abort `user_hf_module_annotations` for every selected module."""

    def test_the_good_module_still_annotates_and_the_bad_one_is_recorded(self, tmp_path, monkeypatch):
        import logging

        from just_dna_pipelines.annotation import hf_logic

        good_table = tmp_path / "weights.parquet"
        pl.DataFrame({
            "module": ["good"], "chrom": ["1"], "start": [100],
            "ref": ["T"], "alts": [["C"]], "genotype": [["C", "T"]], "weight": [1.5],
        }).write_parquet(good_table)
        bad_table = tmp_path / "diplotypes.parquet"
        pl.DataFrame({
            "module": ["bad"], "gene": ["CYP2D6"],
            "haplotype_a": ["*1"], "haplotype_b": ["*4"], "conclusion": ["intermediate"],
        }).write_parquet(bad_table)

        # `config.get_modules()` validates the selection against discovery, so the synthetic pair
        # has to be discoverable before the loop can be reached at all
        from just_dna_pipelines.annotation import hf_modules

        monkeypatch.setattr(hf_modules, "DISCOVERED_MODULES", ["good", "bad"])
        monkeypatch.setattr(hf_logic, "MODULE_INFOS", {
            "good": ModuleInfo(
                name="good", repo_id="org/repo", path=str(tmp_path), weights_url=str(good_table)
            ),
            "bad": ModuleInfo(
                name="bad", repo_id="org/repo", path=str(tmp_path),
                lead_table="diplotypes", lead_url=str(bad_table),
            ),
        })

        vcf = tmp_path / "sample.parquet"
        pl.DataFrame({
            "chrom": ["1"], "start": [100], "ref": ["T"], "alt": ["C"], "genotype": [["C", "T"]],
        }).write_parquet(vcf)

        out_dir = tmp_path / "modules"
        # "bad" first: an exception there must not stop "good" from being reached
        manifest, metadata = hf_logic.annotate_vcf_with_all_modules(
            logging.getLogger(__name__),
            vcf_path=vcf,
            config=HfModuleAnnotationConfig(
                modules=["bad", "good"], output_dir=str(out_dir), user_name="u"
            ),
            user_name="u",
            sample_name="s",
            normalized_parquet_path=vcf,
        )

        assert [m.module for m in manifest.modules] == ["good"]
        assert manifest.total_variants_annotated == 1
        assert "bad" in manifest.skipped_modules
        assert "rsid" in manifest.skipped_modules["bad"]
        assert manifest.failed_modules == {}
        # the directory is stated, not reconstructed from a modules[0] that may not exist
        assert manifest.output_dir == str(out_dir)
        assert "modules_skipped" in metadata
        # and the surviving module's rows really are annotated
        assert pl.read_parquet(out_dir / "good_weights.parquet")["weight"].to_list() == [1.5]


class TestPositionJoinRequiresRefAgreement:
    """Genotype lists hold allele strings, so a shared ALT alone can collide two variants."""

    def test_a_different_ref_at_the_same_locus_does_not_annotate(self, tmp_path):
        from just_dna_pipelines.annotation.hf_logic import annotate_vcf_with_module_weights

        lead = tmp_path / "weights.parquet"
        pl.DataFrame({
            "module": ["panel", "panel"],
            "chrom": ["10", "1"],
            "start": [102837224, 206773552],
            # first row: a 6bp deletion whose ALT happens to equal the sample's SNV alt
            "ref": ["GTGTCT", "T"],
            "alts": [["A"], ["C"]],
            "genotype": [["A", "A"], ["C", "T"]],
            "clin_sig": ["likely_pathogenic", "pathogenic"],
        }).write_parquet(lead)
        info = ModuleInfo(
            name="panel", repo_id="org/repo", path=str(tmp_path), weights_url=str(lead)
        )
        vcf = pl.LazyFrame({
            "chrom": ["10", "1"],
            "start": [102837224, 206773552],
            "ref": ["G", "T"],          # G>A is not GTGTCT>A, however the genotypes line up
            "alt": ["A", "C"],
            "genotype": [["A", "A"], ["C", "T"]],
        })

        out, _ = annotate_vcf_with_module_weights(
            vcf, "panel", tmp_path / "out.parquet", module_info=info
        )
        result = pl.read_parquet(out).filter(pl.col("module").is_not_null())
        # only the locus whose ref agrees survives; the collision is not reported as pathogenic
        assert result["start"].to_list() == [206773552]
        assert result["clin_sig"].to_list() == ["pathogenic"]

    @pytest.mark.parametrize(
        "vcf_ref,vcf_alt,mod_ref,mod_alt,ref_agrees",
        [
            # every real discard measured against `pathogenic` on a live sample...
            ("G", "A", "GTGTCT", "A", False),
            ("T", "C", "TT", "C", False),
            ("G", "T", "GC", "T", False),
            ("CGGCCCCCCA", "C", "CGG", "C", False),
            ("T", "C", "TG", "C", False),
            ("T", "C", "TAG", "C", False),
            # ...and the two it kept
            ("T", "C", "T", "C", True),
            ("AC", "A", "AC", "A", True),
        ],
    )
    def test_ref_equality_agrees_with_the_formats_allele_algebra(
        self, vcf_ref, vcf_alt, mod_ref, mod_alt, ref_agrees
    ):
        """Cheap `ref` equality must not disagree with `just_dna_format.alleles` on what it sees.

        One indel has several valid spellings, so comparing allele strings is the wrong test in
        general. It is the right test on the set this filter reaches — the genotype already
        matched, so a differing `ref` means the two records delete different numbers of bases,
        which `event_profile` calls a positive contradiction rather than a spelling difference.
        If that ever stops holding, this fails and the filter needs the real algebra.
        """
        from just_dna_format.alleles import event_profile, parsimony_reduce

        same_event = parsimony_reduce([vcf_ref, vcf_alt]) == parsimony_reduce([mod_ref, mod_alt])
        assert same_event is ref_agrees

        if not ref_agrees:
            vcf_profile = event_profile([vcf_ref, vcf_alt])
            mod_profile = event_profile([mod_ref, mod_alt])
            # a confident contradiction, never the "unknown" residual a reference would settle
            assert vcf_profile is not None and mod_profile is not None
            assert vcf_profile != mod_profile
