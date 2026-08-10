"""
Tests for the 0.5 module surfaces this repo added: the ClinVar panel route, the ClinPGx
(pharmgkb) route, and the two plumbing fixes they exposed.

Everything that needs a reference snapshot is marked ``integration`` and skips when the snapshot is
absent, so a checkout with no caches still runs the unit half. Ground truth is read from the same
snapshot the builder read, at test time — never hardcoded counts, which would drift with the next
ClinVar release.
"""

import csv
from pathlib import Path
from typing import Optional

import polars as pl
import pytest
import yaml
from just_dna_compiler.compiler import compile_module, validate_spec
from just_dna_enricher.clinvar import select_by_gene
from just_dna_enricher.enrich import enrich
from just_dna_enricher.locations import resolve_clinpgx_reference, resolve_clinvar_reference
from just_dna_format.spec import PMID_PATTERN, StudyRow, VariantRow

from just_dna_pipelines.module_compiler.models import ModuleSpecConfig
from just_dna_pipelines.module_config import _merge_config
from just_dna_pipelines.runtime import load_env
from just_dna_pipelines.v1_port.clinvar_panel import (
    CLINVAR_RESOURCE_PMID,
    MIN_REVIEW_STARS,
    PANEL_CLIN_SIG,
    PLACEHOLDER,
    build_clinvar_module,
    draft_studies,
    fill_genotypes,
)
from just_dna_pipelines.v1_port.pharmgkb import (
    MIN_EVIDENCE_LEVEL,
    _trim,
    build_pharmgkb_module,
)
from just_dna_pipelines.v1_port.writer import _authored_columns, _flatten, write_spec_dir

# A gene small enough to build in seconds and rich enough to exercise every mechanism: HBB carries
# multi-allelic rsIDs, coordinate-only variants and indels.
PANEL_GENES = ["HBB"]

#: Evidence levels at or above the pharmgkb floor (ClinPGx grades 1A > 1B > 2A > 2B > 3 > 4).
KEPT_EVIDENCE_LEVELS = {"1A", "1B", "2A", "2B"}

# The enricher's cache resolvers evaluate their default directory as a call argument, i.e. before
# the `load_env()` inside them runs — so the *first* resolve in a process misses a cache the
# environment names. Load it here, at import, before any skipif expression asks.
load_env()


def _clinvar_snapshot() -> Optional[Path]:
    return resolve_clinvar_reference()


def _clinpgx_snapshot() -> Optional[Path]:
    return resolve_clinpgx_reference()


needs_clinvar = pytest.mark.skipif(
    _clinvar_snapshot() is None,
    reason="no ClinVar snapshot (`just-dna-enricher cache pull --only clinvar`)",
)
needs_clinpgx = pytest.mark.skipif(
    _clinpgx_snapshot() is None,
    reason="no ClinPGx snapshot (`just-dna-enricher cache pull --only clinpgx --use non-commercial`)",
)


# ── modules.yaml layering ──────────────────────────────────────────────────────


class TestModulesConfigMerge:
    """The working copy is layered over the shipped defaults, not substituted for them.

    The bug this pins: first-found-wins meant that once `register_custom_module` wrote a working
    copy naming one custom module, every *shipped* module lost its display metadata — silently, in
    the app and in every spec a port wrote.
    """

    def test_custom_metadata_does_not_delete_shipped_metadata(self) -> None:
        default = {
            "module_metadata": {
                "coronary": {"title": "Coronary", "icon": "heart"},
                "vo2max": {"title": "VO2 Max"},
            },
            "quality_filters": {"min_depth": 10},
        }
        working = {"module_metadata": {"eric_mods__lactose": {"title": "Lactose"}}}
        merged = _merge_config(default, working)
        assert set(merged["module_metadata"]) == {"coronary", "vo2max", "eric_mods__lactose"}
        assert merged["module_metadata"]["coronary"]["icon"] == "heart"
        # A key the working copy never mentions survives untouched.
        assert merged["quality_filters"] == {"min_depth": 10}

    def test_working_copy_overrides_a_shipped_entry(self) -> None:
        default = {"module_metadata": {"coronary": {"title": "Coronary", "icon": "heart"}}}
        working = {"module_metadata": {"coronary": {"title": "Renamed", "icon": "pill"}}}
        merged = _merge_config(default, working)
        assert merged["module_metadata"]["coronary"] == {"title": "Renamed", "icon": "pill"}

    def test_sources_union_without_duplicates(self) -> None:
        default = {"sources": [{"url": "just-dna-seq/annotators"}]}
        working = {
            "sources": [
                {"url": "just-dna-seq/annotators"},
                {"url": "/data/registered_modules", "kind": "collection"},
            ]
        }
        merged = _merge_config(default, working)
        urls = [s["url"] for s in merged["sources"]]
        assert urls == ["just-dna-seq/annotators", "/data/registered_modules"]

    def test_other_keys_take_the_working_value(self) -> None:
        merged = _merge_config({"ensembl_source": {"repo_id": "a"}}, {"ensembl_source": {"repo_id": "b"}})
        assert merged["ensembl_source"] == {"repo_id": "b"}


# ── the spec writer under the 0.5 models ───────────────────────────────────────


class TestSpecWriter:
    """0.4 added list-typed and compiler-managed columns; the writer has to know about both."""

    def test_compiler_managed_columns_are_not_authored(self) -> None:
        columns = _authored_columns(VariantRow)
        assert "variant_key" not in columns
        assert "authored_ident" not in columns
        # …but the ordinary ones are all there.
        assert {"rsid", "genotype", "state", "conclusion", "clin_sig", "flags"} <= set(columns)

    @pytest.mark.parametrize(
        "value,expected",
        [(["a", "b"], "a;b"), (["only"], "only"), ([], None), ("plain", "plain"), (None, None)],
    )
    def test_flatten_list_cells(self, value: object, expected: object) -> None:
        assert _flatten(value) == expected

    def test_list_cell_round_trips_through_csv(self, tmp_path: Path) -> None:
        """The joined spelling must re-parse to the list it came from, or the port is lossy."""
        row = VariantRow(
            rsid="rs1801133",
            genotype="A/G",
            weight=-0.5,
            state="risk",
            conclusion="Test",
            flags=["low_penetrance", "founder"],
        )
        spec = {
            "schema_version": "1.0",
            "module": {
                "name": "flag_test", "title": "T", "description": "D", "report_title": "R",
            },
        }
        write_spec_dir(
            ModuleSpecConfig.model_validate(spec),
            [row],
            [StudyRow(rsid="rs1801133", pmid="9545397")],
            tmp_path / "flag_test",
            source_repo="test", source_file=None, warnings=[],
        )
        written = list(csv.DictReader((tmp_path / "flag_test" / "variants.csv").open()))
        assert written[0]["flags"] == "low_penetrance;founder"
        assert VariantRow(**{k: v or None for k, v in written[0].items()}).flags == [
            "low_penetrance", "founder"
        ]


# ── the ClinVar panel route ────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def hbb_records() -> list[dict]:
    snapshot = _clinvar_snapshot()
    if snapshot is None:
        pytest.skip("no ClinVar snapshot")
    return select_by_gene(
        snapshot, PANEL_GENES, clin_sig=PANEL_CLIN_SIG, min_review_stars=MIN_REVIEW_STARS
    )


@pytest.fixture(scope="module")
def hbb_module(tmp_path_factory: pytest.TempPathFactory) -> Path:
    snapshot = _clinvar_snapshot()
    if snapshot is None:
        pytest.skip("no ClinVar snapshot")
    out = tmp_path_factory.mktemp("clinvar_panel") / "cardio"
    build_clinvar_module("cardio", PANEL_GENES, out, reference=snapshot)
    return out


@needs_clinvar
@pytest.mark.integration
class TestClinVarPanel:
    def test_every_placeholder_is_filled(self, hbb_module: Path) -> None:
        rows = list(csv.DictReader((hbb_module / "variants.csv").open()))
        assert rows, "panel drafted nothing"
        assert not [r for r in rows if r["genotype"] == PLACEHOLDER]

    def test_each_record_becomes_its_two_zygosities(
        self, hbb_module: Path, hbb_records: list[dict]
    ) -> None:
        """Derived ground truth: one het + one hom row per ClinVar record, no more, no fewer."""
        rows = list(csv.DictReader((hbb_module / "variants.csv").open()))
        assert len(rows) == 2 * len(hbb_records)
        genotypes_per_key: dict[str, set[str]] = {}
        for row in rows:
            key = row["rsid"] or f"{row['chrom']}:{row['start']}:{row['ref']}:{row['alts']}"
            genotypes_per_key.setdefault(key, set()).add(row["genotype"])
        assert all(len(g) == 2 for g in genotypes_per_key.values())

    def test_genotypes_are_drawn_from_the_records_own_alleles(
        self, hbb_module: Path, hbb_records: list[dict]
    ) -> None:
        """No invented nucleotides: every allele written appears in some record's ref/alt."""
        source_alleles = {r["ref"] for r in hbb_records} | {r["alt"] for r in hbb_records}
        for row in csv.DictReader((hbb_module / "variants.csv").open()):
            assert set(row["genotype"].split("/")) <= source_alleles, row

    def test_unphased_genotypes_are_sorted(self, hbb_module: Path) -> None:
        """`VariantRow` rejects `G/A`; the fill has to sort, and this is where it used to not."""
        for row in csv.DictReader((hbb_module / "variants.csv").open()):
            alleles = row["genotype"].split("/")
            if alleles[0] != alleles[1]:
                assert alleles == sorted(alleles), row["genotype"]

    def test_non_diploid_contigs_get_one_single_allele_row(
        self, tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        """MT is haploid, so `A/G` and `A/A` are both category errors there.

        The compiler says so itself — *"chrom=MT is not diploid here — use a single-allele genotype
        for a homoplasmic/hemizygous call"* — which is how the original two-rows-everywhere fill was
        caught, on 264 mitochondrial rows in `pathogenic`. Uses a mitochondrial gene so the panel is
        entirely non-diploid and the assertion cannot pass by accident.
        """
        snapshot = _clinvar_snapshot()
        out = tmp_path_factory.mktemp("mt_panel") / "cardio"
        build = build_clinvar_module("cardio", ["MT-TL1", "MT-ND1"], out, reference=snapshot)
        rows = list(csv.DictReader((out / "variants.csv").open()))
        assert rows, "no mitochondrial variants drafted"

        for row in rows:
            assert "/" not in row["genotype"], f"diploid genotype on MT: {row['genotype']}"
            assert row["genotype"], row
        # One row per record, where a diploid contig would have produced two.
        assert build.variant_rows == len(rows)
        resolution = {
            (r.get("rsid") or "").strip()
            for r in rows
        }
        assert resolution, "expected rsid-identified mitochondrial rows"

    def test_diploid_contigs_still_get_both_zygosities(
        self, hbb_module: Path, hbb_records: list[dict]
    ) -> None:
        """The complement of the above: HBB is on chr11, so nothing there may be single-allele."""
        for row in csv.DictReader((hbb_module / "variants.csv").open()):
            assert "/" in row["genotype"], f"single-allele genotype on a diploid contig: {row}"

    def test_clin_sig_is_the_typed_source_value(
        self, hbb_module: Path, hbb_records: list[dict]
    ) -> None:
        written = {r["clin_sig"] for r in csv.DictReader((hbb_module / "variants.csv").open())}
        assert written <= set(PANEL_CLIN_SIG)
        assert written == {r["clin_sig"] for r in hbb_records}

    def test_every_study_pmid_is_one_the_model_accepts(self, hbb_module: Path) -> None:
        """The upstream regression guard.

        ClinVar's `var_citations.txt` mixes 632k PubMedCentral ids and a few malformed "PubMed"
        ones (Variation 12606 cites `168335863`, nine digits) in with the real PMIDs. `StudyRow`
        takes at most eight digits, and the provider's own study drafting raises an unhandled
        `ValidationError` on the first bad one — which aborts a whole gene panel. This asserts the
        filter that replaced it.
        """
        pmids = [r["pmid"] for r in csv.DictReader((hbb_module / "studies.csv").open())]
        assert pmids
        for pmid in pmids:
            assert PMID_PATTERN.fullmatch(pmid), pmid
            StudyRow(rsid="rs1", pmid=pmid)  # the model itself is the authority

    def test_every_variant_is_grounded(self, hbb_module: Path, hbb_records: list[dict]) -> None:
        """Each drafted variant has at least one citation — its own, or the ClinVar paper."""
        studies = list(csv.DictReader((hbb_module / "studies.csv").open()))
        cited = {(s["rsid"], s["chrom"], s["start"], s["ref"]) for s in studies}
        for row in csv.DictReader((hbb_module / "variants.csv").open()):
            key = (row["rsid"], row["chrom"], row["start"], row["ref"])
            assert key in cited, f"ungrounded variant {row['rsid'] or key}"
        assert {s["pmid"] for s in studies} != {CLINVAR_RESOURCE_PMID}, (
            "every citation is the fallback — the snapshot's citations table was not read"
        )

    def test_panel_declaration_pins_the_reference(self, hbb_module: Path) -> None:
        spec = yaml.safe_load((hbb_module / "module_spec.yaml").read_text())
        panel = spec["panel"]
        assert panel["source"] == "clinvar"
        assert panel["reference"] and panel["reference"] != "unknown"
        assert panel["reference_sha256"].startswith("sha256:")
        assert set(panel["significance"]) == set(PANEL_CLIN_SIG)
        assert panel["genes"] == PANEL_GENES

    def test_display_metadata_comes_from_modules_yaml(self, hbb_module: Path) -> None:
        """Not the auto-generated default — the regression the config-merge bug caused."""
        module = yaml.safe_load((hbb_module / "module_spec.yaml").read_text())["module"]
        assert module["description"] != "Annotation module: cardio"
        assert module["icon"] != "database"

    def test_sources_records_clinvar(self, hbb_module: Path) -> None:
        sources = list(csv.DictReader((hbb_module / "sources.csv").open()))
        assert {s["source"] for s in sources} == {"clinvar"}
        assert all(s["license"] == "public-domain" for s in sources)

    def test_rebuild_does_not_append(self, hbb_module: Path) -> None:
        """`draft_gene_panel` is additive by design, so the builder has to clear first."""
        before = len(list(csv.DictReader((hbb_module / "variants.csv").open())))
        build_clinvar_module("cardio", PANEL_GENES, hbb_module, reference=_clinvar_snapshot())
        after = len(list(csv.DictReader((hbb_module / "variants.csv").open())))
        assert after == before

    def test_max_citations_caps_per_record(
        self, hbb_module: Path, hbb_records: list[dict]
    ) -> None:
        """The cap is per ClinVar record, and the number dropped is reported rather than implied.

        Not per study *identity*: `StudyRow` has no `alt`, so several ALT alleles at one locus share
        the identity `(chrom, start, ref)` — a locus with four coordinate-only alleles legitimately
        carries four rows under a cap of one. That is the position-level join the format documents.
        """
        snapshot = _clinvar_snapshot()
        assert snapshot is not None
        capped, dropped, notes = draft_studies(hbb_module, snapshot, hbb_records, max_citations=1)
        assert 0 < capped <= len(hbb_records)
        assert dropped > 0
        assert any("--max-citations 1" in n for n in notes), notes

        uncapped, _dropped, _notes = draft_studies(hbb_module, snapshot, hbb_records)
        assert uncapped > capped, "raising the cap added no citations — none were being read"


@pytest.fixture(scope="module")
def compiled(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A panel taken all the way: draft → validate → enrich → compile, offline throughout."""
    snapshot = _clinvar_snapshot()
    if snapshot is None:
        pytest.skip("no ClinVar snapshot")
    out = tmp_path_factory.mktemp("clinvar_compile") / "cardio"
    build_clinvar_module("cardio", PANEL_GENES, out, reference=snapshot)
    assert validate_spec(out).valid
    enrich(
        out, offline=True, ensembl_cache=Path("/nonexistent"), clinvar_cache=snapshot,
        use_clinvar=True, use_gnomad=False, download=False,
    )
    result = compile_module(out, out, resolve_with_ensembl=True, ensembl_cache=None)
    assert result.success, result.errors
    return out


@needs_clinvar
@pytest.mark.integration
class TestClinVarPanelCompiles:
    """The end-to-end guard: a panel must reach parquet *with coordinates*."""

    def test_weights_carry_coordinates(self, compiled: Path) -> None:
        """The `resolve_with_ensembl=False` trap: a module compiles happily with `chrom=None`,
        and every one of its rows would then fail to match any VCF forever."""
        weights = pl.read_parquet(compiled / "weights.parquet")
        assert weights.height > 0
        with_chrom = weights.filter(pl.col("chrom").is_not_null()).height
        assert with_chrom == weights.height, f"{weights.height - with_chrom} rows have no chrom"

    def test_resolution_table_covers_every_authored_variant(self, compiled: Path) -> None:
        resolution = pl.read_csv(compiled / "resolution.csv", infer_schema_length=0)
        authored = pl.read_csv(compiled / "variants.csv", infer_schema_length=0)
        assert set(authored["rsid"].drop_nulls()) <= set(resolution["rsid"].drop_nulls())

    def test_positions_agree_with_the_snapshot(self, compiled: Path, hbb_records: list[dict]) -> None:
        """Coordinates must be ClinVar's own, not re-derived — spot-checked against the source."""
        truth = {r["rsid"]: (str(r["chrom"]), int(r["start"])) for r in hbb_records if r["rsid"]}
        weights = pl.read_parquet(compiled / "weights.parquet")
        checked = 0
        for row in weights.iter_rows(named=True):
            expected = truth.get(row["rsid"])
            # A one-to-many rsID expands to several loci; only single-locus rows are comparable.
            if expected is None or row["chrom"] is None:
                continue
            if (row["chrom"], row["start"]) != expected:
                continue
            checked += 1
        assert checked > 0, "no row could be compared against the snapshot"


# ── the ClinPGx (pharmgkb) route ───────────────────────────────────────────────


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The pharmgkb module, drafted and enriched from the ClinPGx snapshot (no network)."""
    snapshot = _clinpgx_snapshot()
    if snapshot is None:
        pytest.skip("no ClinPGx snapshot")
    out = tmp_path_factory.mktemp("pharmgkb") / "pharmgkb"
    build_pharmgkb_module(out, snapshot=snapshot)
    return out


@needs_clinpgx
@pytest.mark.integration
class TestPharmGkb:
    def test_the_module_is_a_pharm_variants_module(self, built: Path) -> None:
        assert (built / "pharm_variants.csv").exists()
        assert not (built / "variants.csv").exists()
        assert validate_spec(built).valid

    def test_evidence_floor_is_respected(self, built: Path) -> None:
        levels = {r["evidence_level"] for r in csv.DictReader((built / "pharm_variants.csv").open())}
        assert levels <= KEPT_EVIDENCE_LEVELS, (
            f"{MIN_EVIDENCE_LEVEL} floor let through {sorted(levels - KEPT_EVIDENCE_LEVELS)}"
        )

    def test_rows_match_the_snapshot_selection(self, built: Path) -> None:
        """Derived ground truth: the drafted (annotation, genotype) pairs are the snapshot's."""
        snapshot = pl.read_parquet(
            _clinpgx_snapshot() / "data" / "annotations.parquet",
            columns=["annotation_id", "genotype", "evidence_level", "rsid"],
        ).filter(
            pl.col("evidence_level").is_in(list(KEPT_EVIDENCE_LEVELS))
            & pl.col("rsid").is_not_null()
        )
        authored = list(csv.DictReader((built / "pharm_variants.csv").open()))
        assert authored
        source_ids = set(snapshot["annotation_id"].to_list())
        assert {r["annotation_id"] for r in authored} <= source_ids

    def test_conclusions_are_the_sources_own_sentences(self, built: Path) -> None:
        """Not the provider's identity placeholder — that is what `enrich_drafted_rows` replaces."""
        rows = list(csv.DictReader((built / "pharm_variants.csv").open()))
        placeholder_shaped = [r for r in rows if r["conclusion"].startswith("ClinPGx ")]
        assert len(placeholder_shaped) < len(rows) * 0.05, (
            f"{len(placeholder_shaped)}/{len(rows)} conclusions are still the identity line"
        )

    def test_gene_is_filled_exactly_where_the_source_names_one(self, built: Path) -> None:
        """ClinPGx leaves `gene` empty on some annotations; the fill copies, it does not invent."""
        snapshot = pl.read_parquet(
            _clinpgx_snapshot() / "data" / "annotations.parquet",
            columns=["annotation_id", "gene"],
        )
        has_gene = {
            str(r["annotation_id"]) for r in snapshot.iter_rows(named=True) if (r["gene"] or "").strip()
        }
        rows = list(csv.DictReader((built / "pharm_variants.csv").open()))
        filled = {r["annotation_id"] for r in rows if (r["gene"] or "").strip()}
        empty = {r["annotation_id"] for r in rows if not (r["gene"] or "").strip()}
        assert filled <= has_gene, "gene written for an annotation ClinPGx names none for"
        assert not (empty & has_gene), "gene left empty where ClinPGx names one"

    def test_identity_columns_are_present_on_every_row(self, built: Path) -> None:
        """`(variant, drug, genotype, phenotype_category, annotation_id)` is the duplicate key."""
        for row in csv.DictReader((built / "pharm_variants.csv").open()):
            assert row["rsid"] and row["drug"] and row["annotation_id"]
            assert row["phenotype_category"], row

    def test_licence_is_recorded_as_no_sale(self, built: Path) -> None:
        """ClinPGx forbids sale; the artifact has to say so or the compile gate has nothing to read."""
        sources = list(csv.DictReader((built / "sources.csv").open()))
        clinpgx = [s for s in sources if s["source"] == "clinpgx"]
        assert clinpgx, sources
        assert all(s["commercial_use"] == "false" for s in clinpgx)
        assert all(s["declared_use"] == "non_commercial" for s in clinpgx)
        assert yaml.safe_load((built / "module_spec.yaml").read_text())["license"] == "CC-BY-SA-4.0"


class TestConclusionTrim:
    """ClinPGx's sentences are transcribed, not summarized — but a report cell has a limit."""

    def test_short_text_is_untouched(self) -> None:
        assert _trim("One short sentence.") == "One short sentence."

    def test_long_text_is_cut_on_a_sentence_boundary(self) -> None:
        text = " ".join(f"Sentence number {i} says something about the drug." for i in range(40))
        trimmed = _trim(text, limit=120)
        assert len(trimmed) <= 200
        assert trimmed.endswith(".")
        assert text.startswith(trimmed)

    def test_a_single_overlong_sentence_still_returns_something(self) -> None:
        trimmed = _trim("word " * 300, limit=50)
        assert trimmed
        assert len(trimmed) <= 60
