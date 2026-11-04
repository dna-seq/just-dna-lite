import pandas as pd, json, re, sqlite3
REPO = "/home/antonkulaga/sources/just-dna-lite"; M = f"{REPO}/data/interim/registered_modules/just_dna_seq__longevitymap"
E = json.load(open("ensembl_refs.json"))
tsv = pd.read_csv(f"{REPO}/data/longevity_map.tsv", sep="\t", dtype=str).fillna("")
h = pd.read_csv("hagr_web_entries.csv", dtype=str).fillna("").set_index("id")
v1 = pd.read_csv(f"{M}/variants.csv", dtype=str).fillna("")
res = pd.read_csv(f"{M}/resolution.csv", dtype=str).fillna("").drop_duplicates("rsid").set_index("rsid")
def strand(rs):
    rec = E["vep"].get(rs) or {}
    for tc in rec.get("transcript_consequences", []):
        if tc.get("canonical"): return f'{tc.get("gene_symbol")}:{"+" if tc.get("strand") == 1 else "-"}'
    return ""
v1map = v1.groupby("rsid").apply(lambda g: "; ".join(f"{a}={w}({s})" for a, w, s in zip(g.genotype, g.weight, g.state))).to_dict()
rows = []
for _, r in tsv.iterrows():
    hw = h.loc[r.id] if r.id in h.index else None
    rows.append(dict(tsv_id=r.id, rsid=r.identifier, gene=r.gene_symbol, pmid=r.quickpubmed, year=r.quickyear, skip=r.Skip,
        hagr_identifier=hw["Identifier"] if hw is not None else "", hagr_association=hw["Longevity Association"] if hw is not None else "",
        hagr_population=hw["Population"] if hw is not None else "", hagr_study_design=hw["Study Design"] if hw is not None else r.study_design,
        hagr_conclusion=hw["Conclusions"] if hw is not None else r.conclusions, curated_genotypes=r.genotypes, curated_weights=r["Genotype longevity weight"],
        grch38_ref=res.ref.get(r.identifier, ""), grch38_alts=res.alts.get(r.identifier, ""), gene_strand=strand(r.identifier),
        v1_final_rows=v1map.get(r.identifier, "NOT IN v1")))
D = pd.DataFrame(rows)
seb = D[D.pmid == "22279548"]; non = D[(D.pmid != "22279548")]
seb.to_csv("verify_sebastiani.csv", index=False)
pm = sorted(non.pmid.unique(), key=lambda p: -len(non[non.pmid == p]))
# balance batches by row count
B = [[], [], [], []]; cnt = [0] * 4
for p in pm:
    k = cnt.index(min(cnt)); B[k].append(p); cnt[k] += len(non[non.pmid == p])
for k in range(4):
    non[non.pmid.isin(B[k])].sort_values(["pmid", "rsid"]).to_csv(f"verify_batch{k+1}.csv", index=False)
print("sebastiani rows", len(seb), "| non-seb rows", len(non), "pmids", len(pm), "| batches rows", cnt, "pmids", [len(b) for b in B])
