import pandas as pd, json
REG = pd.read_csv("S14_longevitymap_register.csv", dtype=str).fillna("")
V = pd.read_csv("verif_all.csv", dtype=str).fillna("")
v1 = pd.read_csv("/home/antonkulaga/sources/just-dna-lite/data/interim/registered_modules/just_dna_seq__longevitymap/variants.csv", dtype=str)
v1rs = sorted(set(v1.rsid))
order = ["E9", "E1", "E5", "E6", "E7", "E8", "E10", "E11", "E4"]
lab = {"E9": "wrong variant (rsID is not the variant studied)", "E1": "direction inverted relative to at least one cited study",
       "E5": "weighted genotype cannot be called (allele not assayed / not at the locus)", "E6": "weighted although the cited evidence is not significant",
       "E7": "sex- or subgroup-only effect applied to everyone", "E8": "genetic model differs", "E10": "wrong gene label", "E11": "cited evidence lost at port", "E4": "citation error"}
rows = []
for rs in v1rs:
    e = REG[(REG.rsid == rs) & (REG.cls == "error") & ~REG.stage.str.startswith("corrected")]
    codes = {c.split()[0] for c in e.category}
    worst = next((c for c in order if c in codes), None)
    vv = V[V.rsid == rs]; ok = (vv.verdict == "OK").sum(); cv = (vv.verdict == "CANNOT_VERIFY").sum()
    seb = (vv.pmid == "22279548").any() and (vv.pmid != "22279548").sum() == 0
    if worst is None: worst = "none" if ok > 0 else ("unverified" if len(vv) == 0 or cv == len(vv) else "none")
    rows.append(dict(rsid=rs, gene=v1[v1.rsid == rs].gene.iloc[0], worst=worst, n_studies=len(vv), n_ok=ok, sebastiani_only=seb,
                     provisional_only=bool(len(e)) and (e.provisional == "yes").all()))
P = pd.DataFrame(rows); P.to_csv("per_rsid_worst.csv", index=False)
t = P.groupby(["worst", "sebastiani_only"]).size().unstack(fill_value=0); t["total"] = t.sum(axis=1)
print(t.to_string()); print("total", len(P))
print("E1 rsIDs with only provisional E1 evidence:", int(P[(P.worst == "E1") & P.provisional_only].shape[0]))
print("none:", P[P.worst == "none"].rsid.tolist()[:60])
json.dump({k: int(v) for k, v in P.worst.value_counts().items()}, open("per_rsid_summary.json", "w"))
