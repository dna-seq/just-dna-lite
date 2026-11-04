"""Layer-by-layer lineage of longevitymap v1.2.0 rows.
L1 = HAGR LongevityMap Build 3 (longevity.csv) and its import into the OakVar sqlite `variant` table
L2 = just-dna-seq curation: data/longevity_map.tsv -> sqlite `allele_weights`
L3 = 2026 port: registered module variants.csv / studies.csv
"""
import csv, re, sqlite3, json, collections
import pandas as pd

REPO = "/home/antonkulaga/sources/just-dna-lite"
M = f"{REPO}/data/interim/registered_modules/just_dna_seq__longevitymap"
out = {}

# ---------- L1: Build 3 ----------
b3 = pd.read_csv("longevity.csv", dtype=str).fillna("")
b3 = b3.loc[:, ~b3.columns.str.startswith("Unnamed")]
b3x = []
for _, r in b3.iterrows():
    for tok in re.split(r"[,;]\s*", r["Variant(s)"]):
        tok = tok.strip()
        if tok:
            b3x.append(dict(b3_id=r["id"], assoc=r["Association"], pop=r["Population"], variant=tok, genes=r["Gene(s)"], pmid=r["PubMed"].strip()))
b3x = pd.DataFrame(b3x)
b3rs = b3x[b3x.variant.str.match(r"^rs\d+$")]

con = sqlite3.connect(f"{REPO}/data/modules/just_longevitymap/longevitymap.sqlite")
sv = pd.read_sql("select * from variant", con).fillna("")
gene = pd.read_sql("select id, symbol from gene", con)
pop = pd.read_sql("select id, name as population from population", con)
sv = sv.merge(gene.rename(columns={"id": "gene_id", "symbol": "sq_gene"}), on="gene_id", how="left").merge(pop.rename(columns={"id": "population_id"}), on="population_id", how="left")
sv["quickpubmed"] = sv.quickpubmed.astype(str).str.strip()
aw = pd.read_sql("select * from allele_weights", con)

# sqlite variant vs Build 3 (rsID rows only)
svrs = sv[sv.identifier.str.match(r"^rs\d+$")]
k_b3 = set(zip(b3rs.pmid, b3rs.variant)); k_sv = set(zip(svrs.quickpubmed, svrs.identifier))
m = svrs.merge(b3rs, left_on=["quickpubmed", "identifier"], right_on=["pmid", "variant"], how="left", indicator=True)
out["L1_sqlite_rs_rows"] = len(svrs); out["L1_b3_rs_pairs"] = len(k_b3)
out["L1_sqlite_pairs_not_in_b3"] = len(k_sv - k_b3); out["L1_b3_pairs_not_in_sqlite"] = len(k_b3 - k_sv)
mm = m[m._merge == "both"]
out["L1_assoc_mismatch"] = int((mm.association != mm.assoc).sum())
gm = mm[[s not in [g.strip() for g in re.split(r"[,;]", gs)] for s, gs in zip(mm.sq_gene.fillna(""), mm.genes)]]
out["L1_gene_mismatch"] = len(gm)
out["L1_pop_mismatch"] = int((mm.population.fillna("") != mm["pop"]).sum())

# ---------- L2: curation TSV ----------
tsv = pd.read_csv(f"{REPO}/data/longevity_map.tsv", sep="\t", dtype=str).fillna("")
tsv["quickpubmed"] = tsv.quickpubmed.str.strip()
j = tsv.merge(sv, left_on="id", right_on=sv.id.astype(str), how="left", suffixes=("", "_sq"), indicator=True)
out["L2_tsv_rows"] = len(tsv); out["L2_tsv_id_not_in_sqlite"] = int((j._merge != "both").sum())
jj = j[j._merge == "both"]
for f, g in [("identifier", "identifier_sq"), ("quickpubmed", "quickpubmed_sq"), ("association", "association_sq"), ("conclusions", "conclusions_sq")]:
    out[f"L2_tsv_vs_hagr_{f}_mismatch"] = int((jj[f].str.strip() != jj[g].astype(str).str.strip()).sum())
out["L2_tsv_vs_hagr_gene_mismatch"] = int((jj.gene_symbol.str.strip() != jj.sq_gene.fillna("").str.strip()).sum())
# Was the TSV restricted to significant HAGR rows and is every significant rsID HAGR row curated?
sig = svrs[svrs.association == "significant"]
cur_ids = set(tsv.id)
out["L2_hagr_sig_rs_rows"] = len(sig); out["L2_hagr_sig_rs_rows_not_curated"] = int((~sig.id.astype(str).isin(cur_ids)).sum())

# parse genotype/weight strings
BASES = set("ACGT")
parse = []
for _, r in tsv.iterrows():
    gts = [g.strip() for g in r.genotypes.split(";") if g.strip()]
    ws = [w.strip().replace(",", ".") for w in r["Genotype longevity weight"].split(";") if w.strip()]
    issue = []
    if len(gts) != len(ws): issue.append("n_genotypes!=n_weights")
    for g in gts:
        if len(g) != 2 or not set(g) <= BASES: issue.append(f"nonstandard_genotype:{g}")
    try: wf = [float(w) for w in ws]
    except ValueError: wf = []; issue.append("unparseable_weight")
    alle = set("".join(gts)) & BASES
    if len(alle) > 2: issue.append("more_than_2_alleles")
    parse.append(dict(tsv_id=r.id, rsid=r.identifier, pmid=r.quickpubmed, gene=r.gene_symbol, skip=r.Skip, genotypes=r.genotypes,
                      weights=r["Genotype longevity weight"], prio=r["Gene prioritization"], n_gt=len(gts), issues=";".join(issue),
                      gt_w=dict(zip(gts, wf)) if len(gts) == len(wf) else {}))
P = pd.DataFrame(parse)
out["L2_tsv_parse_issue_rows"] = int((P.issues != "").sum())
out["L2_tsv_issue_kinds"] = collections.Counter(i.split(":")[0] for s in P.issues for i in s.split(";") if i).most_common()
# Same rsID, different curated genotype->weight maps across rows (conflicting curation)
conf = []
for rs, g in P[P.skip != "1"].groupby("rsid"):
    maps = {json.dumps({k: v for k, v in sorted(d.items())}) for d in g.gt_w if d}
    if len(maps) > 1: conf.append(dict(rsid=rs, n_rows=len(g), maps=" | ".join(sorted(maps)), pmids=",".join(sorted(set(g.pmid)))))
out["L2_rsids_with_conflicting_curations"] = len(conf)
# sign conflicts: an allele weighted + in one row and - in another
signc = []
for rs, g in P[P.skip != "1"].groupby("rsid"):
    s = collections.defaultdict(set)
    for d in g.gt_w:
        for gt, w in d.items():
            if w: s[gt].add(w > 0)
    if any(len(v) > 1 for v in s.values()): signc.append(rs)
out["L2_rsids_with_sign_conflict"] = len(signc)

# ---------- L2b: TSV -> allele_weights ----------
res = pd.read_csv(f"{M}/resolution.csv", dtype=str).fillna("")
res1 = res.drop_duplicates("rsid").set_index("rsid")
awr = aw.copy()
awr["ref"] = awr.rsid.map(res1.ref); awr["alts"] = awr.rsid.map(res1.alts)
def ref_alt_ok(r):
    if not r.ref: return "unresolved"
    alts = r.alts.split(",")
    if r.state == "ref": return "ok" if r.allele == r.ref else ("allele_is_alt" if r.allele in alts else "allele_not_at_locus")
    if r.state == "alt": return "ok" if r.allele in alts else ("allele_is_ref" if r.allele == r.ref else "allele_not_at_locus")
    return "spec"
awr["refalt_check"] = awr.apply(ref_alt_ok, axis=1)
out["L2b_allele_weights_rows"] = len(aw)
out["L2b_refalt_check"] = awr.refalt_check.value_counts().to_dict()
# reconstruct genotype per allele_weights row, compare with TSV maps
def aw_gt(r):
    if r.zygosity == "hom": return r.allele * 2
    if r.zygosity == "het" and r.ref: return "".join(sorted(r.allele + (r.ref if r.state == "alt" else r.alts.split(",")[0])))
    return None
awr["gtx"] = awr.apply(aw_gt, axis=1)
tsvmap = collections.defaultdict(dict)
for _, r in P[P.skip != "1"].iterrows():
    for gt, w in r.gt_w.items():
        tsvmap[r.rsid].setdefault("".join(sorted(gt)), set()).add(round(w, 4))
def in_tsv(r):
    t = tsvmap.get(r.rsid)
    if t is None: return "rsid_not_in_curation"
    if r.gtx is None: return "gt_unreconstructable"
    if r.gtx in t: return "match" if round(r.weight, 4) in t[r.gtx] else "weight_differs"
    rc = "".join(sorted(r.gtx.translate(str.maketrans("ACGT", "TGCA"))))
    if rc in t: return "match_revcomp" if round(r.weight, 4) in t[rc] else "revcomp_weight_differs"
    return "gt_not_in_curation"
awr["vs_tsv"] = awr.apply(in_tsv, axis=1)
out["L2b_vs_tsv"] = awr.vs_tsv.value_counts().to_dict()
# TSV non-zero genotypes with no allele_weights row
awkeys = set(zip(awr.rsid, awr.gtx.fillna("")))
miss = []
for rs, t in tsvmap.items():
    for gt, ws in t.items():
        if any(w != 0 for w in ws) and (rs, gt) not in awkeys:
            rc = "".join(sorted(gt.translate(str.maketrans("ACGT", "TGCA"))))
            miss.append(dict(rsid=rs, gt=gt, weights=sorted(ws), revcomp_present=(rs, rc) in awkeys))
out["L2b_tsv_nonzero_gt_missing_in_allele_weights"] = len(miss)
out["L2b_of_which_revcomp_present"] = sum(x["revcomp_present"] for x in miss)

# ---------- L3: port ----------
v1 = pd.read_csv(f"{M}/variants.csv", dtype=str).fillna("")
v1["gtk"] = v1.genotype.str.replace("/", "").apply(lambda s: "".join(sorted(s)))
v1["w"] = v1.weight.astype(float)
awr["gtk"] = awr.gtx.fillna("")
pm = v1.merge(awr[["rsid", "gtk", "weight", "state", "zygosity", "allele", "refalt_check", "vs_tsv"]].rename(columns={"state": "aw_state", "weight": "aw_weight"}), on=["rsid", "gtk"], how="left", indicator=True)
out["L3_v1_rows"] = len(v1); out["L3_v1_rows_without_aw_match"] = int((pm._merge != "both").sum())
both = pm[pm._merge == "both"]
out["L3_weight_changed"] = int((abs(both.w - both.aw_weight) > 1e-9).sum())
out["L3_state_sign_inconsistent"] = int((((both.w > 0) & (both.state == "risk")) | ((both.w < 0) & (both.state == "protective"))).sum())
v1["ref_r"] = v1.rsid.map(res1.ref); v1["alts_r"] = v1.rsid.map(res1.alts); v1["rsid_status"] = v1.rsid.map(res1.rsid_status); v1["rsid_current"] = v1.rsid.map(res1.rsid_current)
def gt_at_locus(r):
    if not r.ref_r: return "unresolved"
    al = {r.ref_r, *r.alts_r.split(",")}
    return "ok" if set(r.genotype.split("/")) <= al else "allele_not_at_locus"
v1["locus_check"] = v1.apply(gt_at_locus, axis=1)
out["L3_locus_check"] = v1.locus_check.value_counts().to_dict()
pal = lambda r: r.ref_r and len(r.ref_r) == 1 and all(len(a) == 1 for a in r.alts_r.split(",")) and {r.ref_r, *r.alts_r.split(",")} in ({"A", "T"}, {"C", "G"})
v1["palindromic"] = v1.apply(pal, axis=1)
out["L3_palindromic_rsids"] = int(v1[v1.palindromic].rsid.nunique())
out["L3_rsid_status"] = res1.rsid_status.value_counts().to_dict()
out["L3_multiallelic_rsids"] = int(res1.alts.str.contains(",").sum())
# a genotype present for the 'longevity' allele but missing the other zygosity, and reference-homozygote coverage
out["L3_rsids_with_only_het"] = int(v1.groupby("rsid").apply(lambda g: (g.genotype.str[0] != g.genotype.str[2]).all()).sum())

# conclusion attribution in port: is v1 row conclusion text a study conclusion for that rsID?
st = pd.read_csv(f"{M}/studies.csv", dtype=str).fillna("")
stc = st.groupby("rsid").conclusion.apply(set)
v1["concl_from_own_study"] = [c in stc.get(rs, set()) for rs, c in zip(v1.rsid, v1.conclusion)]
out["L3_v1_rows_conclusion_not_matching_any_own_study"] = int((~v1.concl_from_own_study).sum())
# studies.csv vs HAGR rows
stk = set(zip(st.pmid, st.rsid))
out["L3_study_pairs"] = len(stk); out["L3_study_pairs_not_in_hagr_sqlite"] = len(stk - k_sv); out["L3_study_pairs_not_in_b3"] = len(stk - k_b3)
st2 = st.merge(svrs[["quickpubmed", "identifier", "association"]].drop_duplicates(["quickpubmed", "identifier"]), left_on=["pmid", "rsid"], right_on=["quickpubmed", "identifier"], how="left")
out["L3_study_signif_mismatch_vs_hagr"] = int((st2.association.notna() & (st2.stat_significance != st2.association)).sum())
# genes: v1 gene vs HAGR gene for the rsID
hg = svrs.groupby("identifier").sq_gene.apply(lambda s: set(s.dropna()))
v1["hagr_genes"] = v1.rsid.map(lambda r: ",".join(sorted(hg.get(r, set()))))
out["L3_gene_differs_from_hagr"] = int(((v1.gene != "") & v1.apply(lambda r: r.gene not in r.hagr_genes.split(","), axis=1)).sum())

for k, v in out.items(): print(k, "=", v)
P.drop(columns="gt_w").to_csv("tsv_parsed.csv", index=False)
pd.DataFrame(conf).to_csv("conflicting_curations.csv", index=False)
pd.DataFrame(miss).to_csv("tsv_gt_missing_in_aw.csv", index=False)
awr.to_csv("allele_weights_checked.csv", index=False)
v1.to_csv("v1_checked.csv", index=False)
gm.to_csv("L1_gene_mismatch.csv", index=False)
m[m._merge != "both"].to_csv("L1_sqlite_not_in_b3.csv", index=False)
json.dump({k: v for k, v in out.items()}, open("lineage_summary.json", "w"), indent=1, default=str)
