"""
Tests for the Generation-I module port (`just_dna_pipelines.v1_port`).

Ground truth is derived at runtime from each module's own SQLite (fetched from the dna-seq org),
never hardcoded: the key assertion is that curated weights are carried through **verbatim** and that
every emitted PMID is digit-only (ROADMAP 0.2). Network-dependent tests skip cleanly when the source
repos can't be reached.
"""

import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from just_dna_pipelines.v1_port.adapters import (
    _longevitymap_genotype,
    adapt_coronary,
    adapt_longevitymap,
    adapt_three_table,
)
from just_dna_pipelines.v1_port.genotype import state_from_weight, to_slash_genotype
from just_dna_pipelines.v1_port.pmid import normalize_pmids
from just_dna_pipelines.v1_port.runner import DEFAULT_ENSEMBL_CACHE
from just_dna_pipelines.v1_port.sources import REGISTRY, fetch_data_file

_DIGITS = re.compile(r"^\d+$")


# ------------------------------------------------------------------ pure-function unit tests

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("PMID 17478681; PMID: 30278588;", ["17478681", "30278588"]),
        ("[PMID 28373160];  [PMID 23900608];", ["28373160", "23900608"]),
        (34707639, ["34707639"]),  # clean integer pubmed_id
        ("8018664", ["8018664"]),  # bare quickpubmed number
        ("https://www.ncbi.nlm.nih.gov/snp/rs1007211", []),  # URL, not a PMID
        ("", []),
        (None, []),
        ("PMID 123; PMID 123", ["123"]),  # dedup
    ],
)
def test_normalize_pmids(raw, expected):
    assert normalize_pmids(raw) == expected


def test_state_from_weight_reproduces_sign_semantics():
    assert state_from_weight(-1.54) == "risk"
    assert state_from_weight(0.5) == "protective"
    assert state_from_weight(0.0) == "neutral"
    assert state_from_weight(None) == "neutral"


@pytest.mark.parametrize(
    "raw, expected",
    [("AG", "A/G"), ("GA", "A/G"), ("gg", "G/G"), ("A/G", "A/G"), ("N", None), ("AGT", None)],
)
def test_to_slash_genotype(raw, expected):
    assert to_slash_genotype(raw) == expected


@pytest.mark.parametrize(
    "row, ref_alt, expected",
    [
        # hom → two copies of the curated effect allele (Ensembl ref/alt irrelevant)
        ({"allele": "T", "state": "alt", "zygosity": "hom"}, ("C", "T"), "T/T"),
        # het, effect is an alt: pair with the Ensembl reference — NOT the multiallelic alt list
        ({"allele": "G", "state": "alt", "zygosity": "het"}, ("T", "A|G"), "G/T"),
        # het, effect equals the reference: pair with a single-base alt from the list
        ({"allele": "C", "state": "ref", "zygosity": "het"}, ("C", "T"), "C/T"),
        # spec-state het spells the genotype out directly in a two-base allele
        ({"allele": "CT", "state": "spec", "zygosity": "het"}, ("C", "G|T"), "C/T"),
        ({"allele": "AG", "state": "spec", "zygosity": "het"}, ("C", "A|G|T"), "A/G"),
        # unusable: no single complement resolvable and not a clean two-base pair
        ({"allele": "N", "state": "alt", "zygosity": "het"}, ("A", "G"), None),
    ],
)
def test_longevitymap_genotype_reconstruction(row, ref_alt, expected):
    """Het genotypes come from the curated effect allele, never Ensembl's multiallelic alt list."""
    assert _longevitymap_genotype(row, ref_alt) == expected


# ------------------------------------------------------------------ adapter tests (need source data)

@pytest.fixture(scope="module")
def sources_cache():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


def _fetch(name: str, cache: Path) -> Path:
    try:
        return fetch_data_file(REGISTRY[name], cache)
    except Exception as exc:  # network/DNS/etc. — don't fail the suite offline
        pytest.skip(f"could not fetch {name} source: {exc}")


def test_coronary_weights_are_verbatim(sources_cache):
    """Every ported (rsid, genotype) weight must equal the curated value in the source SQLite."""
    db = _fetch("coronary", sources_cache)

    truth: dict[tuple[str, str], float] = {}
    con = sqlite3.connect(db)
    try:
        con.row_factory = sqlite3.Row
        for r in con.execute("SELECT rsID, Genotype, Weight FROM coronary_disease"):
            gt = to_slash_genotype(r["Genotype"])
            rsid = str(r["rsID"] or "").strip()
            w = r["Weight"]
            if gt is None or not rsid.startswith("rs") or w in (None, ""):
                continue
            truth[(rsid, gt)] = float(str(w).strip())
    finally:
        con.close()

    _, variants, _, _ = adapt_coronary(REGISTRY["coronary"], db)
    ported = {(v.rsid, v.genotype): v.weight for v in variants}

    assert truth, "expected curated coronary weights in source"
    checked = 0
    for key, weight in truth.items():
        if key in ported:  # adapter keeps the first of any duplicate (rsid, genotype)
            assert ported[key] == weight, f"weight drift for {key}: {ported[key]} != {weight}"
            checked += 1
    assert checked > 0.9 * len(truth), "most curated weights should survive verbatim"


@pytest.mark.parametrize("name", ["coronary", "thrombophilia", "lipidmetabolism", "vo2max"])
def test_all_study_pmids_are_digit_only(name, sources_cache):
    """ROADMAP 0.2: every emitted study pmid must be a bare number."""
    db = _fetch(name, sources_cache)
    module = REGISTRY[name]
    adapter = adapt_coronary if name == "coronary" else adapt_three_table
    _, _, studies, _ = adapter(module, db)
    assert studies, f"{name} should produce grounded studies"
    for s in studies:
        assert _DIGITS.match(s.pmid), f"{name} pmid not digit-only: {s.pmid!r}"


def test_longevitymap_reconstructs_every_source_rsid(sources_cache):
    """With the Ensembl cache present, every distinct rsid in allele_weights must be reproduced."""
    if not DEFAULT_ENSEMBL_CACHE.exists():
        pytest.skip(f"Ensembl cache not present at {DEFAULT_ENSEMBL_CACHE}")
    db = _fetch("longevitymap", sources_cache)

    con = sqlite3.connect(db)
    try:
        rows = con.execute("SELECT DISTINCT rsid FROM allele_weights WHERE rsid LIKE 'rs%'").fetchall()
    finally:
        con.close()
    source_rsids = {str(r[0]).strip() for r in rows}

    _, variants, _, warnings = adapt_longevitymap(
        REGISTRY["longevitymap"], db, DEFAULT_ENSEMBL_CACHE
    )
    ported_rsids = {v.rsid for v in variants}

    assert source_rsids, "expected curated longevitymap rsids in source"
    missing = source_rsids - ported_rsids
    assert not missing, f"rsids dropped during port: {sorted(missing)}"
    assert not warnings, f"expected a clean port with no skipped rows, got: {warnings}"


def test_thrombophilia_studies_cover_source_pubmed_ids(sources_cache):
    """Ported studies should reflect the distinct (rsid, pubmed_id) links in the source table."""
    db = _fetch("thrombophilia", sources_cache)

    con = sqlite3.connect(db)
    try:
        rows = con.execute(
            "SELECT DISTINCT rsid, pubmed_id FROM studies WHERE rsid LIKE 'rs%' AND pubmed_id IS NOT NULL"
        ).fetchall()
    finally:
        con.close()
    source_links = {(str(r[0]).strip(), str(r[1]).strip()) for r in rows}

    _, _, studies, _ = adapt_three_table(REGISTRY["thrombophilia"], db)
    ported_links = {(s.rsid, s.pmid) for s in studies}

    assert source_links, "expected curated thrombophilia study links"
    # Every source (rsid, pubmed_id) with a valid rsid should appear among the ported studies.
    missing = source_links - ported_links
    assert not missing, f"ported studies missing source links: {sorted(missing)[:5]}"
