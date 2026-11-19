"""A human genome on any reference but GRCh38 is refused, with the reason, never read as GRCh38.

Before this, the web UI set every sample to GRCh38, so a GRCh37 or T2T file was scored and
position-joined against GRCh38 coordinates with no warning (docs/INVESTIGATE_GRCH37_UI.md; desk #59).
The builds come from the upload's own list (`REFERENCE_GENOMES`) and from the header detector's
outputs, not restated here.
"""

from __future__ import annotations

import pytest

from webui.state import REFERENCE_GENOMES, SUPPORTED_HUMAN_BUILD, unsupported_build_reason

HUMAN = "Homo sapiens"
OTHER_HUMAN_BUILDS = [b for b in REFERENCE_GENOMES[HUMAN] if b != SUPPORTED_HUMAN_BUILD]


def test_the_supported_build_is_one_the_upload_offers() -> None:
    assert SUPPORTED_HUMAN_BUILD in REFERENCE_GENOMES[HUMAN]
    assert OTHER_HUMAN_BUILDS, "the upload offers at least one other human build"


def test_grch38_is_analysed() -> None:
    assert unsupported_build_reason(HUMAN, SUPPORTED_HUMAN_BUILD) == ""


@pytest.mark.parametrize("build", OTHER_HUMAN_BUILDS)
def test_every_other_human_build_is_refused_and_named(build: str) -> None:
    reason = unsupported_build_reason(HUMAN, build)
    assert reason
    assert build in reason
    assert SUPPORTED_HUMAN_BUILD in reason


@pytest.mark.parametrize("build", ["GRCh37", "GRCh38"])
def test_each_build_the_header_detector_names_is_judged(build: str) -> None:
    # just_prs.vcf.detect_genome_build returns "GRCh37", "GRCh38" or None.
    assert bool(unsupported_build_reason(HUMAN, build)) is (build != SUPPORTED_HUMAN_BUILD)


@pytest.mark.parametrize("species, build", [(None, None), (HUMAN, None), (None, ""), (HUMAN, "")])
def test_missing_metadata_reads_as_the_upload_default(species: str | None, build: str | None) -> None:
    assert unsupported_build_reason(species, build) == ""


@pytest.mark.parametrize("species", [s for s in REFERENCE_GENOMES if s != HUMAN])
def test_other_species_are_not_judged_by_the_human_rule(species: str) -> None:
    assert unsupported_build_reason(species, REFERENCE_GENOMES[species][0]) == ""


def test_an_unknown_human_build_is_refused() -> None:
    assert unsupported_build_reason(HUMAN, "custom")
