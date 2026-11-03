import pandas as pd, re, json
m=pd.read_csv("genage/genage_models.csv"); h=pd.read_csv("genage/genage_human.csv")
print(m.organism.value_counts().head(6).to_string())
mm=m[m.organism=="Mus musculus"].copy(); mm["human_symbol"]=mm.symbol.str.upper()
v1=pd.read_csv("../current_v1/variants.csv"); v1g=set(v1.gene.dropna().str.upper())
def genes(df):
    s=set()
    for g in df.gene.dropna(): s|={x.strip().upper() for x in re.split(r"[,/;]",g) if x.strip()}
    return s
cand=genes(pd.read_csv("trackA_candidates.csv"))|genes(pd.read_csv("trackD_candidates.csv"))
# CDKN2A/B split
cand|={"CDKN2A","CDKN2B"}
def summarise(gs,label):
    hit=mm[mm.human_symbol.isin(gs)]
    print(f"\n{label}: {len(gs)} genes; with mouse GenAge entry: {hit.human_symbol.nunique()}; in GenAge human: {len(gs & set(h.symbol.str.upper()))}")
    return hit
a=summarise(v1g,"v1 genes"); b=summarise(cand,"new GWAS-era candidate genes")
cols=["human_symbol","symbol","lifespan effect","longevity influence","avg lifespan change (max obsv)"]
print(b[cols].drop_duplicates().to_string(index=False))
out=pd.concat([a.assign(gene_set="v1"),b.assign(gene_set="gwas_candidate")])[cols+["gene_set","GenAge ID","entrez gene id"]]
out.to_csv("genage_mouse_xref.csv",index=False)
print("\nv1 mouse-supported genes:", ", ".join(sorted(a.human_symbol.unique())))
print("\nlongevity influence among v1 hits:", a["longevity influence"].value_counts().to_dict())
