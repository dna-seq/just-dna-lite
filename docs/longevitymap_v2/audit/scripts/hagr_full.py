import sqlite3, pandas as pd, re, json
REPO="/home/antonkulaga/sources/just-dna-lite"
h=pd.read_csv("hagr_web_all.csv",dtype=str).fillna("").drop_duplicates("id")
h["has"]=h.Identifier.str.len()>0
print("HAGR ids scraped",len(h),"with content",h.has.sum(),"max id with content",h[h.has].id.astype(int).max())
con=sqlite3.connect(f"{REPO}/data/modules/just_longevitymap/longevitymap.sqlite")
sv=pd.read_sql("select v.*, g.symbol sq_gene, p.name sq_pop from variant v left join gene g on g.id=v.gene_id left join population p on p.id=v.population_id",con).fillna("").astype(str)
print("sqlite rows",len(sv),"max id",sv.id.astype(int).max())
x=h[h.has].merge(sv,on="id",how="outer",indicator=True).fillna("")
print("join:",x._merge.value_counts().to_dict())
b=x[x._merge=="both"].copy()
n=lambda s: re.sub(r"\s+"," ",str(s)).strip().lower()
F={"identifier":("Identifier","identifier"),"association":("Longevity Association","association"),"population":("Population","sq_pop"),"gene":("HGNC symbol","sq_gene"),"study_design":("Study Design","study_design"),"conclusions":("Conclusions","conclusions")}
def trunc_eq(a,c): a,c=n(a),n(c); return a==c or a.startswith(c) or c.startswith(a)
res={}
for k,(a,c) in F.items():
    d=[not (trunc_eq(p,q) if k in("conclusions","study_design") else n(p)==n(q)) for p,q in zip(b[a],b[c])]
    b["d_"+k]=d; res[k]=int(sum(d))
b["any_edit"]=b[[c for c in b if c.startswith("d_")]].any(axis=1)
print("records differing (truncation-insensitive) per field:",res,"| any field:",int(b.any_edit.sum()))
only_sql=x[x._merge=="right_only"]; only_h=x[x._merge=="left_only"]
print("sqlite-only ids:",only_sql.id.tolist()[:20]); print("HAGR-only ids:",only_h.id.tolist()[:20])
# identifier edits that are not named->rs
idd=b[b.d_identifier]; print("identifier edits",len(idd),"named->rs",int(sum(bool(re.match(r'^rs\d+$',q)) and not re.match(r'^rs\d+$',p) for p,q in zip(idd.Identifier,idd.identifier))))
print(idd[~idd.identifier.str.match(r'^rs\d+$')][["id","Identifier","identifier"]].head(10).to_string())
for k in ["study_design","conclusions","population","association"]:
    s=b[b["d_"+k]]
    for _,r in s.head(3).iterrows(): print(k,r.id,"|HAGR:",r[F[k][0]][:90],"|SQ:",r[F[k][1]][:90])
b.to_csv("hagr_vs_sqlite_full.csv",index=False)
json.dump(dict(fields=res,any=int(b.any_edit.sum()),both=len(b)),open("hagr_full_summary.json","w"))
