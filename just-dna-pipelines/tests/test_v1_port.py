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
    _SUPERHUMAN_CURATION,
    _load_superhuman_curation,
    _longevitymap_genotype,
    adapt_coronary,
    adapt_longevitymap,
    adapt_superhuman,
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


# ------------------------------------------------------------------ superhuman v2 curation tests

def test_superhuman_curation_csv_is_well_formed():
    """The frozen PMID curation (deterministic, no network) must satisfy the grounding guardrails."""
    import csv as _csv

    rows = list(_csv.DictReader(_SUPERHUMAN_CURATION.open(newline="")))
    assert rows, "curation CSV should not be empty"
    seen: set[tuple[str, str, str]] = set()
    for r in rows:
        gene, rsid, scope, pmid = r["gene"], r["rsid"], r["scope"], r["pmid"]
        assert gene, "every row needs a gene"
        assert _DIGITS.match(pmid), f"non-digit pmid {pmid!r} for {gene}/{rsid}"  # ROADMAP 0.2
        assert r["verified_title"].strip(), f"missing verified_title for {gene}/{rsid} pmid {pmid}"
        assert scope in {"rsid", "gene-indel"}, f"bad scope {scope!r}"
        if scope == "gene-indel":
            assert not rsid, "gene-indel rows carry no rsid"
        else:
            assert rsid.startswith("rs"), f"bad rsid {rsid!r}"
        key = (gene, rsid, pmid)
        assert key not in seen, f"duplicate curation row {key}"
        seen.add(key)


def test_superhuman_added_genes_have_explicit_verified_genotypes():
    """The March-2026 additions are not in the source, so they must carry a hand-verified genotype."""
    cur = _load_superhuman_curation()
    # Allele orientation confirmed against dbSNP/MyVariant (see docs/SUPERHUMAN_REFRESH_PLAN.md).
    expected = {
        "rs4570625": ("TPH2", "T/T"),      # -703 minor-allele homozygous
        "rs4680": ("COMT", "G/G"),         # Val158 (G)
        "rs6265": ("BDNF", "C/C"),         # Val66 (C)
        "rs5882": ("CETP", "G/G"),         # Val405 (G)
        "rs121918393": ("APOE", "A/C"),    # Christchurch R136S carrier
    }
    assert set(cur.added) == set(expected), f"added rsids drifted: {sorted(cur.added)}"
    for rsid, (gene, gt) in expected.items():
        entry = cur.added[rsid]
        assert entry["gene"] == gene and entry["genotype"] == gt
        assert all(_DIGITS.match(p) for p in entry["pmids"]) and entry["pmids"]


def test_superhuman_port_narrows_and_grounds(sources_cache):
    """Every kept variant is a curated protective allele and every one is grounded; the unnamed
    whole-gene dbSNP dumps are dropped."""
    if not DEFAULT_ENSEMBL_CACHE.exists():
        pytest.skip(f"Ensembl cache not present at {DEFAULT_ENSEMBL_CACHE}")
    db = _fetch("superhuman", sources_cache)
    _, variants, studies, _ = adapt_superhuman(REGISTRY["superhuman"], db, DEFAULT_ENSEMBL_CACHE)

    assert studies, "superhuman should produce grounded studies"
    for s in studies:
        assert _DIGITS.match(s.pmid), f"non-digit superhuman pmid: {s.pmid!r}"

    variant_rsids = {v.rsid for v in variants}
    study_rsids = {s.rsid for s in studies}
    # Referential integrity: every study points at a kept variant.
    assert study_rsids <= variant_rsids, f"studies reference absent rsids: {study_rsids - variant_rsids}"
    # Narrowing grounds the whole set: every kept variant has at least one study.
    assert variant_rsids == study_rsids, (
        f"ungrounded kept variants: {sorted(variant_rsids - study_rsids)}"
    )

    # Narrowing dropped the unnamed NTRK1 SNP dump but kept its deletion-class (indel) variants.
    con = sqlite3.connect(db)
    try:
        ntrk1_snv = con.execute(
            "SELECT rsid FROM superhuman WHERE gene='NTRK1' AND length(ref_allele)=1 "
            "AND length(alt_allele)=1 LIMIT 1"
        ).fetchone()
    finally:
        con.close()
    if ntrk1_snv:
        assert ntrk1_snv[0] not in variant_rsids, "an unnamed NTRK1 SNP should have been dropped"

    # The March-2026 additions are present with their verified genotypes.
    by_rsid = {v.rsid: v for v in variants}
    for rsid, gt in [("rs4570625", "T/T"), ("rs6265", "C/C"), ("rs5882", "G/G"),
                     ("rs4680", "G/G"), ("rs121918393", "A/C")]:
        assert rsid in by_rsid, f"missing refresh addition {rsid}"
        assert by_rsid[rsid].genotype == gt, f"{rsid}: {by_rsid[rsid].genotype} != {gt}"


# ---------------------------------------------------- gene-panel symbol reconciliation (pure)

def test_symbol_resolver_maps_aliases_and_flags_typos():
    """Legacy aliases resolve to current symbols; true typos are reported, never guessed."""
    from just_dna_pipelines.v1_port.symbols import SymbolResolver, resolve_panel_genes

    resolver = SymbolResolver(
        official={"MYCL", "PRKN", "TAFAZZIN", "AKT1"},
        synonym_to_official={"MYCL1": "MYCL", "PARK2": "PRKN", "TAZ": "TAFAZZIN"},
    )
    wanted, alias_map, unresolved = resolve_panel_genes(
        {"MYCL1", "PARK2", "TAZ", "AKT1", "ATK1"}, resolver
    )
    assert alias_map == {"MYCL1": "MYCL", "PARK2": "PRKN", "TAZ": "TAFAZZIN"}
    assert unresolved == ["ATK1"]  # not a current symbol nor a known synonym → flagged, not guessed
    assert {"MYCL", "PRKN", "TAFAZZIN", "AKT1"}.issubset(wanted)
    assert "ATK1" in wanted  # kept (so it's visible), even though it will match nothing

    # No resolver (no gene_info cache) → pass-through, nothing flagged.
    passthrough, aliases, missing = resolve_panel_genes({"MYCL1"}, None)
    assert passthrough == {"MYCL1"} and not aliases and not missing
