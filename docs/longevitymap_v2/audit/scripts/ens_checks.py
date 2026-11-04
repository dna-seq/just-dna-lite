import json, re, collections, pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 70); pd.set_option("display.max_rows", 200)
REPO = "/home/antonkulaga/sources/just-dna-lite"; M = f"{REPO}/data/interim/registered_modules/just_dna_seq__longevitymap"
E = json.load(open("ensembl_refs.json")); vep, var = E["vep"], E["variation"]
ALIAS = {"FOXO3A": "FOXO3", "UCP4": "SLC25A27", "SLC9A3R2": "NHERF2", "C9orf3": "AOPEP", "MKL1": "MRTFA", "H2AFX": "H2AX", "CARS": "CARS1", "PAPD5": "TENT4B",
         "FAM19A5": "TAFA5", "TMEM2": "CEMIP2", "IL8": "CXCL8", "C20orf194": "DNAAF9", "C7orf50": "CHLSN"}

def genes(rs):
    rec = vep.get(rs)
    if not rec: return None
    ov, near = set(), {}
    for tc in rec.get("transcript_consequences", []):
        s = tc.get("gene_symbol")
        if not s: continue
        terms = tc.get("consequence_terms", [])
        if any(t in ("upstream_gene_variant", "downstream_gene_variant") for t in terms):
            near[s] = min(near.get(s, 1e9), tc.get("distance", 0) or 0)
        else: ov.add(s)
    return ov, near, rec.get("most_severe_consequence"), rec.get("seq_region_name"), rec.get("start")

def hgvsp(rs):
    rec = vep.get(rs) or {}
    return sorted({tc["hgvsp"].split(":")[-1] for tc in rec.get("transcript_consequences", []) if tc.get("hgvsp") and tc.get("canonical")})

# 1. gene label check (v1 rows, one per rsID)
v1 = pd.read_csv(f"{M}/variants.csv", dtype=str).fillna("")
g1 = v1.groupby("rsid").agg(gene=("gene", "first")).reset_index()
rows = []
for _, r in g1.iterrows():
    G = genes(r.rsid)
    if G is None: rows.append(dict(rsid=r.rsid, gene=r.gene, gene_check="no_vep")); continue
    ov, near, csq, chrom, pos = G
    lab = ALIAS.get(r.gene, r.gene)
    if not r.gene or r.gene in ("-",): c = "no_label"
    elif lab in ov or r.gene in ov: c = "overlaps"
    elif lab in near or r.gene in near: c = "within_5kb"
    elif r.gene.startswith("LOC"): c = "LOC_unverifiable"
    else: c = "not_within_5kb"
    rows.append(dict(rsid=r.rsid, gene=r.gene, gene_check=c, overlapping=",".join(sorted(ov)), near=",".join(f"{k}:{v}" for k, v in sorted(near.items())), csq=csq, chrom=chrom, pos=pos))
G1 = pd.DataFrame(rows)
print("gene check:", G1.gene_check.value_counts().to_dict())
print(G1[G1.gene_check == "not_within_5kb"][["rsid", "gene", "overlapping", "near", "csq", "chrom", "pos"]].to_string())
G1.to_csv("gene_check.csv", index=False)

# 2. merged / renamed rsIDs
mer = [(q, d.get("name"), d.get("synonyms", [])[:3]) for q, d in var.items() if d.get("name") and d["name"] != q]
print("rsIDs returned under another name (merged):", mer[:20], len(mer))
missing = sorted(set(v1.rsid) - set(var))
print("v1 rsIDs absent from Ensembl variation:", missing)

# 3. named-variant translations made by the curator / importer (HAGR identifier was not an rsID)
named = {  # HAGR identifier -> (rsID used, expected protein/notation token)
 "rs5882": "I405V", "rs9536314": "F352V", "rs9527025": "C370S", "rs1801282": "P12A", "rs1800562": "C282Y", "rs4986790": "D299G",
 "rs1805097": "G1057D", "rs28940577": "M694V", "rs1056836": "V432L", "rs13181": "K751Q", "rs699": "M235T", "rs73598374": "D8N",
 "rs1800471": "R25P", "rs2229765": "", "rs1043618": "", "rs2227956": "T493M", "rs1061581": "", "rs1008438": "", "rs1800592": "",
 "rs2854116": "", "rs1800624": "", "rs647126": "", "rs1042031": "E4181K", "rs5128": "", "rs28940579": "V726A", "rs1799889": ""}
AA = dict(Ala="A", Arg="R", Asn="N", Asp="D", Cys="C", Gln="Q", Glu="E", Gly="G", His="H", Ile="I", Leu="L", Lys="K", Met="M", Phe="F", Pro="P", Ser="S", Thr="T", Trp="W", Tyr="Y", Val="V")
def short(p):
    m = re.match(r"p\.([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2})", p)
    return f"{AA.get(m.group(1), '?')}{m.group(2)}{AA.get(m.group(3), '?')}" if m else p
out = []
for rs, exp in named.items():
    hp = [short(p) for p in hgvsp(rs)]
    out.append(dict(rsid=rs, expected=exp, canonical_hgvsp=",".join(hp), csq=(vep.get(rs) or {}).get("most_severe_consequence"),
                    match=(exp in hp) if exp else None))
N = pd.DataFrame(out); print(N.to_string()); N.to_csv("named_variant_check.csv", index=False)
for rs in ["rs61752717", "rs28940578", "rs28940580", "rs3743930", "rs1799889"]:
    print(rs, [short(p) for p in hgvsp(rs)], (vep.get(rs) or {}).get("most_severe_consequence"))
