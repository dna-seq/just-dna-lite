"""Merge paper-level verdicts with mechanical lineage checks into one errata register (S14 schema + layer)."""
import re, json, collections, pandas as pd
REPO = "/home/antonkulaga/sources/just-dna-lite"; M = f"{REPO}/data/interim/registered_modules/just_dna_seq__longevitymap"
V = pd.read_csv("verif_all.csv", dtype=str).fillna("")
tsv = pd.read_csv(f"{REPO}/data/longevity_map.tsv", sep="\t", dtype=str).fillna("")
v1 = pd.read_csv(f"{M}/variants.csv", dtype=str).fillna("")
st = pd.read_csv(f"{M}/studies.csv", dtype=str).fillna("")
log = open(f"{M}/v1_port.log").read()
port_rs = set(re.findall(r"(rs\d+) [ACGT]/[ACGT]: (?:dropped|genotype)", log)) | set(re.findall(r"(rs\d+) [ACGT]/[ACGT] \(locus has", log))
RC = str.maketrans("ACGT", "TGCA")
key = lambda g: "".join(sorted(g.replace("/", "")))

def tsv_map(tid):
    r = tsv[tsv.id == tid]
    if r.empty: return {}
    r = r.iloc[0]; gts = [g.strip() for g in r.genotypes.split(";") if g.strip()]
    ws = [w.strip().replace(",", ".") for w in r["Genotype longevity weight"].split(";") if w.strip()]
    out = {}
    for g, w in zip(gts, ws):
        try: out[key(g)] = float(w)
        except ValueError: pass
    return out
v1pos = v1[v1.weight.astype(float) > 0].groupby("rsid").genotype.apply(lambda s: [key(g) for g in s]).to_dict()
v1neg = v1[v1.weight.astype(float) < 0].groupby("rsid").genotype.apply(lambda s: [key(g) for g in s]).to_dict()

def study_agrees_with_v1(r):
    """Does this study's own TSV curation give the v1-favoured genotypes a positive weight?"""
    m = tsv_map(r.tsv_id)
    if not m or r.rsid not in v1pos: return None
    vals = [m.get(g, m.get(key(g.translate(RC)))) for g in v1pos[r.rsid]]
    vals = [x for x in vals if x is not None]
    if not vals: return None
    return any(x > 0 for x in vals)

CAT = {"direction_reversed": "E1 risk direction inverted (weight sign)", "hagr_misreport": "E4 citation or transcription error",
       "not_significant_but_weighted": "E6 weight inconsistent with the cited evidence", "subgroup_generalised": "E7 sex- or subgroup-only effect applied to everyone",
       "model_mismatch": "E8 genetic model differs from the cited study", "strand_unresolvable": "N6 strand-ambiguous (A/T, C/G) SNP, direction unresolvable"}
reg = []
for _, r in V.iterrows():
    vd = r.verdict.lower()
    if vd in ("ok", "cannot_verify"): continue
    if vd == "wrong_variant":
        cat = "E9 rsID is not the variant studied" if r.variant_match.lower() == "no" else "E5 genotype not representable (allele not assayed or not at the locus)"
    else: cat = CAT[vd]
    lay = r.error_layer.lower()
    # mechanical re-attribution
    if lay == "l3_port" and r.rsid not in port_rs: lay = "l2_curation"
    if lay == "l2_curation":
        if r.rsid == "rs7412" and vd == "wrong_variant": lay = "l2_import"
        elif vd == "direction_reversed" and study_agrees_with_v1(r) is False: lay = "l2_curation"  # study itself curated the v1 direction? no -> see below
        a = study_agrees_with_v1(r)
        if vd == "direction_reversed" and a is False: lay = "l2_aggregation"
    if r.rsid in ("rs28940579",) and r.pmid == "17048073": lay = "l1_hagr+l2_import"
    if r.tsv_id in ("3477", "3478", "3479", "3480", "3481") and lay.startswith("l1"): lay = "l2_curation"; cat = "E6 weight inconsistent with the cited evidence" if vd == "hagr_misreport" else cat
    stage = "still in v1.2.0" if r.rsid in set(v1.rsid) else "not in v1.2.0 (skipped or dropped)"
    reg.append(dict(module="longevitymap", rsid=r.rsid, gene=r.gene, pmid=r.pmid, tsv_id=r.tsv_id, genotype="", cls="error" if cat.startswith("E") else "note",
                    category=cat, layer=lay, stage=stage, detail=r.note[:600], evidence=r.quote[:400], source_read=r.source_read,
                    secondary=r.other_codes, provisional=("yes" if (r.source_read == "abstract" or "provisional" in r.note.lower() or "probable" in r.other_codes.lower() or "inferred" in r.note.lower()) else "no"),
                    origin="paper verification"))
R = pd.DataFrame(reg)

# ---- mechanical findings ----
mech = []
def add(**k): mech.append({**dict(module="longevitymap", genotype="", pmid="", tsv_id="", source_read="", secondary="", provisional="no", origin="mechanical check"), **k})
for rs in ["rs10819510", "rs1205035", "rs13008689", "rs1333049", "rs3120819", "rs9616906"]:
    add(rsid=rs, gene="TP53", cls="error", category="E10 gene label wrong", layer="l1_hagr", stage="still in v1.2.0",
        detail="HAGR labels this rsID TP53 (Yashin 2012, PMID 22533364 p53-pathway study, or 9p21 entries); Ensembl places it outside TP53 on another chromosome",
        evidence="Ensembl VEP 2026-11-03: not within 5 kb of TP53 (chr17)")
add(rsid="rs7959761", gene="BHLHE41", cls="note", category="N2 gene symbol not the overlapping gene", layer="l1_hagr", stage="still in v1.2.0",
    detail="v1 keeps HAGR's BHLHE41; the variant is intronic in SSPN (the Generation I curation file had SSPN)", evidence="Ensembl VEP: intron_variant SSPN")
add(rsid="rs28940479", gene="MEFV", cls="error", category="E4 citation or transcription error", layer="l1_hagr", stage="corrected at Generation I import",
    detail="HAGR entry 1887 gives rs28940479; the Generation I import used rs28940579", evidence="HAGR entry.php?id=1887 Identifier field")
add(rsid="rs28940579", gene="SERPINE1", cls="error", category="E9 rsID is not the variant studied", layer="l1_hagr+l2_import", stage="still in v1.2.0",
    detail="HAGR entry 226 (PMID 17048073) has identifier 'SERPINE1' for a study of the alpha-1-antitrypsin (SERPINA1) Z allele; the Generation I import attached MEFV V726A rsID rs28940579 and the curation file relabelled the gene MEFV",
    evidence="HAGR entry.php?id=226; Ensembl VEP rs28940579 = MEFV p.Val726Ala")
add(rsid="rs28940577", gene="MEFV", cls="error", category="E9 rsID is not the variant studied", layer="l2_curation+l3_port", stage="still in v1.2.0",
    detail="Generation I curation mapped MEFV M694V (HAGR identifier) to rs28940577, which Ensembl annotates as p.Met693Val; M694V is rs61752717. The v1.2.0 port then strand-corrected the row citing 'p.Met694Val'",
    evidence="Ensembl VEP canonical HGVSp: rs28940577 M693V; rs61752717 M694V/M694L; v1_port.log")
add(rsid="rs7412", gene="APOE", cls="error", category="E9 rsID is not the variant studied", layer="l2_import", stage="still in v1.2.0",
    detail="Generation I import mapped every HAGR 'E2/E3/E4' record (21 study rows in v1) to rs7412 alone; 16 of these conclusions concern the e4 allele (rs429358), which is therefore credited or penalised through the e2-defining SNP",
    evidence="HAGR entry pages give identifier 'E2/E3/E4'; v1 studies.csv rs7412 = 21 rows, 16 mention E4")
dual = tsv[(tsv.Skip != "1") & tsv.genotypes.str.split(";").apply(lambda g: len(set("".join(x.strip() for x in g)) & set("ACGT")) > 2)]
for rs in sorted(set(dual.identifier)):
    add(rsid=rs, gene=dual[dual.identifier == rs].gene_symbol.iloc[0], cls="error", category="E5 genotype not representable (allele not assayed or not at the locus)",
        layer="l2_curation", stage="corrected at port (v1.2.0)" if rs in port_rs else "still in v1.2.0 (inert rows)",
        detail="Generation I genotype list mixes both strands (more than two bases for a biallelic SNP), e.g. '" + dual[dual.identifier == rs].genotypes.iloc[0] + "'", evidence="data/longevity_map.tsv; Ensembl alleles; v1_port.log")
add(rsid="rs2758331", gene="SOD2", cls="note", category="N7 transcription defect without effect", layer="l2_curation", stage="removed at port (weight 0)",
    detail="Genotype written with Cyrillic letters 'СС' (weight 0)", evidence="data/longevity_map.tsv tsv_id 1472")
for tid in ["3477", "3479", "3480", "3481"]:
    r = tsv[tsv.id == tid].iloc[0]
    add(rsid=r.identifier, gene=r.gene_symbol, cls="note", category="N8 record added by Generation I curation (not in HAGR)", layer="l2_curation", stage="still in v1.2.0",
        detail=f"Row id {tid} (PMID {r.quickpubmed}) has no HAGR entry (HAGR ids above 3476 are empty templates); see paper verification for its significance",
        evidence="HAGR entry.php?id=" + tid)
conf = pd.read_csv("conflicting_curations.csv")
for _, r in conf.iterrows():
    add(rsid=r.rsid, gene="", cls="note", category="N9 conflicting study-level curations collapsed into one direction without a flag", layer="l2_aggregation", stage="still in v1.2.0",
        detail=f"{r.n_rows} curated studies (PMIDs {r.pmids}) give different genotype maps: {r.maps[:300]}", evidence="data/longevity_map.tsv vs allele_weights")
lost = pd.read_csv("lost_study_links.csv", dtype=str)
for _, r in lost.iterrows():
    add(rsid=r.identifier, gene=r.gene_symbol, cls="error", category="E11 cited evidence lost at port", layer="l3_port", stage="still in v1.2.0",
        detail=f"Curated study PMID {r.quickpubmed} (TSV id {r.id}), from which the weight was curated, is absent from v1 studies.csv because its HAGR record carried a named identifier, not an rsID", evidence="studies.csv join on (pmid, rsid)")
    mech[-1]["pmid"] = r.quickpubmed
ph = v1[v1.conclusion == "Longevity-associated variant"]
for rs, g in ph.groupby("rsid"):
    add(rsid=rs, gene=g.gene.iloc[0], cls="note", category="N5 conclusions are bare labels", layer="l3_port", stage="still in v1.2.0",
        detail=f"{len(g)} genotype row(s) carry the placeholder conclusion 'Longevity-associated variant'", evidence="variants.csv")
M2 = pd.DataFrame(mech)
REG = pd.concat([R, M2], ignore_index=True)
REG["layer_label"] = REG.layer.map({"l1_hagr": "LongevityMap (HAGR)", "l2_import": "Generation I import", "l2_curation": "Generation I curation",
    "l2_aggregation": "Generation I aggregation", "l3_port": "v1.2.0 port", "l0_paper": "source paper", "l1_hagr+l2_import": "LongevityMap (HAGR) + Generation I import",
    "l2_curation+l3_port": "Generation I curation + v1.2.0 port"}).fillna(REG.layer)
REG.to_csv("S14_longevitymap_register.csv", index=False)

# ---- summaries ----
S = {}
S["paper_rows"] = len(V); S["paper_rows_by_batch"] = V.batch.value_counts().to_dict()
S["paper_source_read"] = V.source_read.value_counts().to_dict()
S["paper_verdicts"] = V.verdict.str.lower().value_counts().to_dict()
S["register_rows"] = len(REG)
S["by_layer_category"] = REG.groupby(["layer_label", "category"]).size().reset_index().values.tolist()
S["by_layer"] = REG.layer_label.value_counts().to_dict()
E1 = R[R.category.str.startswith("E1")]
S["E1_rows"] = len(E1); S["E1_rsids"] = E1.rsid.nunique(); S["E1_rows_sebastiani"] = int((E1.pmid == "22279548").sum())
S["E1_layer"] = E1.layer.value_counts().to_dict(); S["E1_provisional"] = int((E1.provisional == "yes").sum())
# per v1 rsID impact
err = REG[REG.cls == "error"]
v1rs = set(v1.rsid)
S["v1_rsids"] = len(v1rs)
S["v1_rsids_with_any_error"] = len(set(err.rsid) & v1rs)
S["v1_rsids_with_E1"] = len(set(E1.rsid) & v1rs)
ok_rs = set(V[V.verdict.str.lower() == "ok"].rsid)
S["v1_rsids_E1_and_also_some_OK_study"] = len(set(E1.rsid) & ok_rs & v1rs)
S["v1_rsids_unverified"] = len(v1rs - set(V[V.verdict.str.lower() != "cannot_verify"].rsid))
S["v1_rsids_all_studies_ok"] = len({rs for rs, g in V[V.rsid.isin(v1rs)].groupby("rsid") if (g.verdict.str.lower() == "ok").all()})
S["v1_rows_on_E1_rsids"] = int(v1.rsid.isin(set(E1.rsid)).sum())
S["port_rsids"] = len(port_rs)
g = pd.read_csv(f"{REPO}/docs/longevitymap_v2/evidence/B_gwascatalog_gw_leads.csv", dtype=str)
gw = set(g.rsid.str.extract(r"(rs\d+)")[0].dropna()); S["gws_longevity_rsids"] = len(gw); S["gws_in_v1"] = sorted(gw & v1rs)
S["E1_by_batch_rows"] = E1.merge(V[["tsv_id","batch"]], on="tsv_id", how="left").batch.value_counts().to_dict()
S["hagr_E4_rows"] = REG[(REG.layer_label=="LongevityMap (HAGR)") & REG.category.str.startswith("E4")][["rsid","pmid","tsv_id"]].values.tolist()
S["stage_counts"] = REG.groupby(["cls","stage"]).size().reset_index().values.tolist()
S["seb_verdicts"] = V[V.batch=="sebastiani"].verdict.value_counts().to_dict()
S["nonseb_verdicts"] = V[V.batch!="sebastiani"].verdict.value_counts().to_dict()
S["nonseb_source_read"] = V[V.batch!="sebastiani"].source_read.value_counts().to_dict()
S["nonseb_pmids"] = V[V.batch!="sebastiani"].pmid.nunique()
S["v1_rsids_E1_nonseb"] = len(set(E1[E1.pmid!="22279548"].rsid) & v1rs); S["v1_rsids_E1_seb"] = len(set(E1[E1.pmid=="22279548"].rsid) & v1rs)
E1p = E1[E1.provisional=="no"]; S["E1_rows_firm"] = len(E1p); S["E1_rsids_firm"] = E1p.rsid.nunique()
json.dump(S, open("S14_longevitymap_summary.json", "w"), indent=1, default=str)
for k, v in S.items(): print(k, "=", v)
