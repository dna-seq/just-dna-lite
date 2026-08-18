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
    _superhuman_genotypes,
    _longevitymap_genotype,
    adapt_coronary,
    adapt_longevitymap,
    adapt_superhuman,
    adapt_three_table,
)
from just_dna_pipelines.v1_port.genotype import state_from_weight, to_slash_genotype
from just_dna_pipelines.v1_port.pmid import normalize_pmids
from just_dna_pipelines.v1_port.publish import plan_publish, resolve_module_dir
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
        "rs4570625": ("TPH2", {"T/T"}),          # -703 minor-allele homozygous
        "rs4680": ("COMT", {"G/G"}),             # Val158 (G)
        "rs6265": ("BDNF", {"C/C"}),             # Val66 (C)
        "rs5882": ("CETP", {"G/G"}),             # Val405 (G)
        "rs121918393": ("APOE", {"A/C"}),        # Christchurch R136S carrier
        "rs11591147": ("PCSK9", {"G/T", "T/T"}), # R46L, protective in het + hom Leu carriers
    }
    assert set(cur.added) == set(expected), f"added rsids drifted: {sorted(cur.added)}"
    for rsid, (gene, gts) in expected.items():
        entry = cur.added[rsid]
        assert entry["gene"] == gene and set(entry["genotypes"]) == gts
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


def test_superhuman_multiallelic_locus_with_no_source_allele_emits_nothing():
    """A source row naming no allele at a multi-allelic locus yields NO genotype.

    This inverts an earlier regression test, and the reason it was written is real, so it is worth
    stating rather than deleting. That test fixed a *0-results* bug (2026-07): a carrier whose real
    allele was a later Ensembl alt matched nothing, so the adapter began emitting het+hom for every
    single-base alt. The cure was worse. Ensembl lists every observed alt at a position, so fanning
    out asserts the module's protective conclusion once per alt, and the module names only one of
    them. Measured on the shipped artifact: 31 rsIDs produced 95 of 190 rows, **54 of which name an
    allele nothing in the provenance chain ever stated**.

    `HBB rs334` is the case that settles the trade. Fanned out, the module asserted `A/T`, `C/T` and
    `G/T` all as "Malaria resistance". Only `T>A` is HbS. `T>C` is HbC, which the module's own
    citation (PMID 35811813) reports as **not** protective in that cohort (p=0.26), and `T>G` is
    Hb-Makassar, a benign non-sickling variant. A missed carrier is a report that says nothing; a
    fabricated one is a report that tells a person something false about their malaria risk.

    So the miss is accepted and reported by name, and the durable fix is curation — naming the
    protective allele for those rsIDs, the way the `added` entries already do.
    """
    row = {"rsid": "rs1168015", "genotype": None, "ref_allele": None,
           "alt_allele": None, "zygosity": "both"}
    assert _superhuman_genotypes(row, ("C", "A|G|T")) == []


def test_superhuman_single_alt_locus_is_still_reconstructed():
    """One alt at the locus is unambiguous, so reconstruction is safe and must still happen.

    The withholding above is scoped to genuine ambiguity. Where Ensembl names a single alt there is
    nothing to guess, and dropping these too would discard the reconstruction the adapter exists for.
    """
    row = {"rsid": "rsX", "genotype": None, "ref_allele": None,
           "alt_allele": None, "zygosity": "both"}
    assert sorted(_superhuman_genotypes(row, ("C", "T"))) == ["C/T", "T/T"]


def test_superhuman_genotypes_hom_only_and_source_alleles():
    """hom zygosity emits only the homozygous genotype; an explicit source alt is used verbatim."""
    # recessive (hom) phenotype: only alt/alt, no het
    hom = _superhuman_genotypes(
        {"rsid": "rs1", "genotype": None, "ref_allele": None, "alt_allele": None, "zygosity": "hom"},
        ("C", "T"),
    )
    assert hom == ["T/T"], hom
    # source spelled out ref/alt for this row -> use that alt, not the Ensembl list
    src = _superhuman_genotypes(
        {"rsid": "rs2", "genotype": None, "ref_allele": "G", "alt_allele": "C", "zygosity": "both"},
        ("G", "A|C|T"),
    )
    assert set(src) == {"C/G", "C/C"}, src


# ------------------------------------------------------------------ HF publish route

def test_publish_accepts_a_directory_or_a_name_identically(tmp_path):
    """A path and the equivalent bare name resolve to the same module.

    Before, the argument was always joined onto the output root, so passing the path you were
    looking at produced `<root>/<root>/<name>` and an error about the wrong directory.
    """
    root = tmp_path / "v1_port"
    module_dir = root / "coronary"
    module_dir.mkdir(parents=True)

    by_name = resolve_module_dir("coronary", root)
    by_path = resolve_module_dir(str(module_dir), root)
    assert by_name == by_path == (module_dir, "coronary")


def test_publish_rejects_a_mistyped_path_as_a_path(tmp_path):
    """A path-shaped argument that does not exist is not retried as a name under the output root."""
    with pytest.raises(FileNotFoundError) as excinfo:
        resolve_module_dir(str(tmp_path / "v1_port" / "coronaryy"), tmp_path / "v1_port")
    # the message names what was actually asked for, not some other absent directory
    assert "coronaryy" in str(excinfo.value)
    assert "v1_port/v1_port" not in str(excinfo.value)


def test_publish_remedy_for_an_uncompiled_spec_is_a_runnable_command(tmp_path):
    """The missing-artifact error must suggest a command that exists and lands where publish reads.

    It used to suggest `v1-port port --module <arg>`, which cannot rebuild a module that was never
    a Generation-I port, and which took a name where a path had been given.
    """
    spec = tmp_path / "my_module"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text("name: my_module\n")

    with pytest.raises(FileNotFoundError) as excinfo:
        plan_publish(spec, "my_module")
    message = str(excinfo.value)
    assert "weights.parquet" in message
    # compiling in place is what makes the artifacts visible to this uploader
    assert f"pipelines module compile {spec} --output {spec}" in message


def test_publish_accepts_a_module_led_by_a_04_table(tmp_path):
    """A pharm_variants-led module publishes to HF like any other — no weights.parquet needed.

    Discovery probes every family in LEAD_TABLES, so the old refusal (which sent these to the
    registry) described a limitation that no longer exists.
    """
    module_dir = tmp_path / "pharmgkb"
    module_dir.mkdir()
    for table in ("pharm_variants.parquet", "sources.parquet", "manifest.json"):
        (module_dir / table).touch()

    plan = plan_publish(module_dir, "pharmgkb")
    assert plan.path_in_repo == "data/pharmgkb"
    assert "pharm_variants.parquet" in plan.files
    # side tables a pharm module does not have must not be demanded of it
    assert "annotations.parquet" not in plan.files


def test_publish_still_rejects_a_directory_with_no_lead_table(tmp_path):
    """Accepting the 0.4 families must not degrade into accepting anything at all."""
    module_dir = tmp_path / "not_a_module"
    module_dir.mkdir()
    (module_dir / "sources.parquet").touch()      # a side table alone does not make a module
    (module_dir / "manifest.json").touch()

    with pytest.raises(FileNotFoundError) as excinfo:
        plan_publish(module_dir, "not_a_module")
    assert "no compiled table" in str(excinfo.value)


def test_publish_still_catches_a_partial_weights_compile(tmp_path):
    """A weights-led module missing its side tables is a partial compile, not a new shape."""
    module_dir = tmp_path / "coronary"
    module_dir.mkdir()
    (module_dir / "weights.parquet").touch()

    with pytest.raises(FileNotFoundError) as excinfo:
        plan_publish(module_dir, "coronary")
    message = str(excinfo.value)
    assert "annotations.parquet" in message and "studies.parquet" in message
