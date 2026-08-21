"""The reads and refusals that came out of the just-module-creator hand-off (2026-08-20/21).

Full triage in `docs/reviews/consumer-handoff-triage.md`. Every test here pins one item from the
tranche we accepted, and each names the failure it prevents rather than restating the fix. All are
network-free; the two that want a real artifact skip when it is absent rather than inventing one.
"""

from pathlib import Path

import polars as pl
import pytest
from just_dna_format.manifest import README_CANDIDATES

from just_dna_pipelines.annotation.hf_logic import (
    _lead_join_strategy,
    _unmatchable_phased_rows,
)
from just_dna_pipelines.annotation.hf_modules import (
    ModuleInfo,
    read_module_provenance,
)
from just_dna_pipelines.annotation.report_logic import _alt_alleles, _alt_str
from just_dna_pipelines.v1_port.publish import _ALLOW_PATTERNS

PHARMGKB = Path("data/interim/v1_port/pharmgkb")


class TestAltsIsNotAlwaysAList:
    """`alts` is `List(Utf8)` on `weights.parquet` and `String` on a 0.4 family."""

    def test_the_old_expression_produces_nonsense_on_the_string_case(self) -> None:
        """The bug, run: `"/".join` over a string iterates characters.

        This is what reached the report as "Module alternate alleles" and went into the
        AI-prefill prompt the reader can send to a third party.
        """
        assert "/".join("A,C") == "A/,/C"

    def test_the_string_case_now_splits_on_the_authored_separator(self) -> None:
        assert _alt_alleles("A,C") == ["A", "C"]
        assert _alt_str("A,C") == "A/C"

    def test_the_list_case_is_unchanged(self) -> None:
        assert _alt_alleles(["A", "C"]) == ["A", "C"]
        assert _alt_str(["A", "C"]) == "A/C"

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, []),
            ("", []),
            ([], []),
            ("A", ["A"]),
            ("G|T", ["G", "T"]),   # polars-bio's multi-allelic ALT separator
            (["A", None, "C"], ["A", "C"]),
        ],
    )
    def test_edges(self, value: list[str] | str | None, expected: list[str]) -> None:
        assert _alt_alleles(value) == expected

    def test_our_shipped_pharm_module_is_the_latent_case(self) -> None:
        """0.5 `pharmgkb` has no `alts` column, which is why nothing caught this.

        Kept as a live check rather than a comment: when this module is recompiled under 0.6 the
        column appears and the bug would be reachable, so the test above stops being hypothetical.
        """
        table = PHARMGKB / "pharm_variants.parquet"
        if not table.is_file():
            pytest.skip("v1_port pharmgkb artifact not built in this checkout")
        columns = pl.scan_parquet(table).collect_schema().names()
        if "alts" not in columns:
            pytest.skip("shipped pharmgkb predates the alts column, as expected for a 0.5 artifact")
        dtype = pl.scan_parquet(table).collect_schema()["alts"]
        # Whatever the compiler emits, the reader must survive it.
        sample = pl.read_parquet(table, columns=["alts"]).get_column("alts").drop_nulls().head(1)
        if len(sample):
            assert "/,/" not in _alt_str(sample[0]), f"alts dtype {dtype} still renders wrong"


class TestJoinStrategyNamesTheColumnsItReads:
    """`position` used to be returned on `{chrom, start}` alone."""

    def test_a_haplotypes_led_table_is_unsupported_not_position(self) -> None:
        """The crash this prevents: `haplotypes` has coordinates and `allele`, not `genotype`.

        Classified `position`, the join then died at collect time on a `ColumnNotFoundError` —
        an unhandled crash where a module we cannot join should get a recorded skip.
        """
        haplotypes = pl.LazyFrame({"chrom": ["19"], "start": [44908684], "allele": ["*2"]})
        strategy, reason = _lead_join_strategy(haplotypes)
        assert strategy == "unsupported"
        assert "genotype" in reason

    def test_a_placed_table_with_a_genotype_still_gets_position(self) -> None:
        placed = pl.LazyFrame(
            {"chrom": ["1"], "start": [100], "genotype": [["A", "G"]], "rsid": ["rs1"]}
        )
        assert _lead_join_strategy(placed)[0] == "position"

    def test_coordinates_typed_but_null_throughout_fall_back_to_rsid(self) -> None:
        """Which is what every pre-0.6 PGx module is, our own `pharmgkb` included."""
        unplaced = pl.LazyFrame(
            {
                "chrom": pl.Series([None, None], dtype=pl.String),
                "start": pl.Series([None, None], dtype=pl.Int64),
                "genotype": [["A", "G"], ["C", "C"]],
                "rsid": ["rs1", "rs2"],
            }
        )
        assert _lead_join_strategy(unplaced)[0] == "rsid"

    def test_the_shipped_pharm_module_is_still_unplaced(self) -> None:
        """Pins the measurement the triage rests on: 0 of 1482 rows placed.

        If a recompile ever changes this, the position branch starts running on this family for the
        first time and that is worth being told about rather than discovering in a report.
        """
        table = PHARMGKB / "pharm_variants.parquet"
        if not table.is_file():
            pytest.skip("v1_port pharmgkb artifact not built in this checkout")
        lf = pl.scan_parquet(table)
        placed = lf.select(pl.col("chrom").is_not_null().sum()).collect().item()
        total = lf.select(pl.len()).collect().item()
        assert total > 0
        assert placed == 0, (
            f"{placed}/{total} rows now carry coordinates — this module has been recompiled "
            "under format 0.6 (RM43). The position join now applies to it; exercise that branch."
        )


class TestPhasedRowsAreRefusedLoudly:
    """The VCF side sorts and the module side must not, so homolog order matches nothing."""

    def test_the_unsorted_phased_row_is_the_one_that_cannot_match(self) -> None:
        lead = pl.LazyFrame({"genotype": ["A|G", "G|A", "A/G", "C/C"]})
        phased, unmatchable = _unmatchable_phased_rows(lead)
        assert phased == 2, "both `|` cells are phased"
        # `A|G` sorts to itself and does match, phase simply ignored. `G|A` cannot.
        assert unmatchable == 1

    def test_a_weights_led_module_states_phase_in_its_own_column(self) -> None:
        lead = pl.LazyFrame(
            {"genotype": [["A", "G"], ["G", "A"], ["G", "A"]], "phased": [True, True, False]}
        )
        assert _unmatchable_phased_rows(lead) == (2, 1)

    def test_must_run_before_normalization_or_there_is_nothing_left_to_see(self) -> None:
        """`_normalize_lead_genotype` folds `|` into `/`; detection has to precede it."""
        from just_dna_pipelines.annotation.hf_logic import _normalize_lead_genotype

        raw = pl.LazyFrame({"genotype": ["G|A"]})
        assert _unmatchable_phased_rows(raw)[1] == 1
        # After normalization the genotype is a list and carries no `phased` column, so the same
        # call reports nothing — which is exactly why the call site sits above it.
        assert _unmatchable_phased_rows(_normalize_lead_genotype(raw)) == (0, 0)

    @pytest.mark.parametrize(
        "frame",
        [
            pl.LazyFrame({"rsid": ["rs1"]}),                        # no genotype at all
            pl.LazyFrame({"genotype": ["A/G", "C/C"]}),             # nothing phased
            pl.LazyFrame({"genotype": [["A", "G"]]}),               # list, no phase column
        ],
    )
    def test_a_module_with_no_phase_information_reports_nothing(self, frame: pl.LazyFrame) -> None:
        assert _unmatchable_phased_rows(frame) == (0, 0)


class TestRemoteProvenanceIsNotDropped:
    """Discovery validated the manifest and kept one field of it."""

    def _info(self, **kw: object) -> ModuleInfo:
        return ModuleInfo(name="m", repo_id="r", path="p", lead_url="u", **kw)  # type: ignore[arg-type]

    def test_a_remotely_stated_manifest_now_reaches_the_report(self) -> None:
        info = self._info(
            manifest_version="2.1.0",
            manifest_digest="sha256:abc",
            manifest_weighting="scale: per-allele log-OR",
        )
        assert read_module_provenance(info) == (
            "2.1.0",
            "sha256:abc",
            "scale: per-allele log-OR",
        )

    def test_a_source_that_states_nothing_still_answers_none(self) -> None:
        """Tri-state: every module on HuggingFace today has no manifest, and `None` is honest.

        `None` must never be repaired into "unversioned", "unverified", or a claim that this
        module's weights are comparable to another's.
        """
        assert read_module_provenance(self._info()) == (None, None, None)
        assert read_module_provenance(None) == (None, None, None)


def test_the_publish_allowlist_carries_the_readme_the_manifest_attests() -> None:
    """`manifest.readme` named a file the upload never sent, and `verify_manifest` passed anyway.

    Set containment against the format's own constant, not a restated spelling — the whole reason
    this broke is that the allowlist was hand-kept.
    """
    assert set(README_CANDIDATES).issubset(set(_ALLOW_PATTERNS))


class TestDiscoveryProbeIsCallableAtImportTime:
    """Discovery runs at import, so anything it calls must be bound before that line.

    This exists because moving manifest reading into `_probe_module_at_path` introduced a call to
    `_weighting_summary`, which was defined 500 lines further down — after
    `MODULE_INFOS = discover_hf_modules()`. It raised no ImportError, because
    `discover_modules_from_source` catches per-source failures and logs them: every source failed
    with `name '_weighting_summary' is not defined` and discovery silently returned **nothing**.

    Exercising the probe against a real directory on the local filesystem reproduces that without a
    network call, which the tests that did catch it (`test_hf_modules`) all need.
    """

    def _probe(self, path: Path):
        from fsspec.implementations.local import LocalFileSystem

        from just_dna_pipelines.annotation.hf_modules import _probe_module_at_path

        return _probe_module_at_path(
            LocalFileSystem(), str(path), "file", path.name, str(path), str(path)
        )

    def test_probing_a_real_module_directory_does_not_raise(self, tmp_path: Path) -> None:
        if not PHARMGKB.is_dir():
            pytest.skip("v1_port pharmgkb artifact not built in this checkout")
        info = self._probe(PHARMGKB.resolve())
        assert info is not None
        assert info.lead_table == "pharm_variants"

    def test_a_directory_that_is_not_a_module_probes_to_none(self, tmp_path: Path) -> None:
        (tmp_path / "notes.txt").write_text("not a module")
        assert self._probe(tmp_path) is None

    def test_the_probe_keeps_what_the_manifest_states(self) -> None:
        """`manifest.json` beside the parquet must reach `ModuleInfo`, not just its file list."""
        if not (PHARMGKB / "manifest.json").is_file():
            pytest.skip("v1_port pharmgkb artifact not built in this checkout")
        info = self._probe(PHARMGKB.resolve())
        assert info is not None
        # The digest is what the module claims; a manifest that states one must not be dropped.
        assert info.manifest_digest, "manifest.artifact.digest was read and discarded"
