import sqlite3, pandas as pd, re
pd.set_option("display.width",250); pd.set_option("display.max_colwidth",80); pd.set_option("display.max_rows",120)
REPO="/home/antonkulaga/sources/just-dna-lite"
h=pd.read_csv("hagr_web_entries.csv",dtype=str).fillna("")
print("found:",h.found.value_counts().to_dict(), "errors:", (h.get("error","")!="").sum() if "error" in h else 0)
con=sqlite3.connect(f"{REPO}/data/modules/just_longevitymap/longevitymap.sqlite")
sv=pd.read_sql("select v.*, g.symbol sq_gene, p.name sq_pop from variant v left join gene g on g.id=v.gene_id left join population p on p.id=v.population_id",con).fillna("").astype(str)
x=h.merge(sv,on="id",how="left").fillna("")
n=lambda s: re.sub(r"\s+"," ",str(s)).strip().lower()
x["d_ident"]=[n(a)!=n(b) for a,b in zip(x.Identifier,x.identifier)]
x["d_assoc"]=[n(a)!=n(b) for a,b in zip(x["Longevity Association"],x.association)]
x["d_concl"]=[n(a)!=n(b) for a,b in zip(x.Conclusions,x.conclusions)]
x["d_gene"]=[n(a)!=n(b) for a,b in zip(x["HGNC symbol"],x.sq_gene)]
x["d_pop"]=[n(a)!=n(b) for a,b in zip(x.Population,x.sq_pop)]
f=x[x.found=="True"]
print("of",len(f),"found: identifier diff",f.d_ident.sum(),"assoc diff",f.d_assoc.sum(),"concl diff",f.d_concl.sum(),"gene diff",f.d_gene.sum(),"pop diff",f.d_pop.sum())
d=f[f.d_ident].copy()
print("identifier changes HAGR->sqlite (kinds):"); 
d["kind"]=["hagr_rs_changed" if re.match(r"^rs\d+$",a) else ("named->rs" if re.match(r"^rs\d+$",b) else "other") for a,b in zip(d.Identifier,d.identifier)]
print(d.kind.value_counts().to_dict())
print(d[["id","Identifier","identifier","HGNC symbol","quickpubmed","kind"]].to_string())
print("assoc diffs:"); print(f[f.d_assoc][["id","Identifier","Longevity Association","association","quickpubmed"]].to_string())
print("gene diffs:"); print(f[f.d_gene][["id","Identifier","HGNC symbol","sq_gene"]].head(30).to_string())
c=f[f.d_concl]; print("concl diffs",len(c)); 
for _,r in c.head(5).iterrows(): print(r.id,"|HAGR:",r.Conclusions[:110],"|SQ:",r.conclusions[:110])
x.to_csv("hagr_vs_sqlite.csv",index=False)
