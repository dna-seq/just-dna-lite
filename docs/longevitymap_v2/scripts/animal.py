import pandas as pd, re
S=pd.read_csv("longevitymap_v2_seed_variants.csv")
m=pd.read_csv("genage/genage_models.csv"); mm=m[m.organism=="Mus musculus"].copy(); mm["H"]=mm.symbol.str.upper()
gen={r.H: f"GenAge mouse {r.symbol}: lifespan {str(r['lifespan effect']).lower()}, {str(r['longevity influence']).lower()} (GenAge ID {r['GenAge ID']})" for _,r in mm.iterrows()}
qtl={"FGD6":"UM-HET3 late-male lifespan QTL candidate; worm ortholog tag-77 RNAi shortened lifespan ~14% (Bou Sleiman 2022, PMID 36173858)"}
def sup(g):
    toks={t.strip().upper() for t in re.split(r"[;,/ ()]+",str(g)) if t.strip()}
    out=[gen[t] for t in toks if t in gen]+[qtl[t] for t in toks if t in qtl]
    return " | ".join(out)
S["animal_support"]=S.genes.map(sup)
S.to_csv("longevitymap_v2_seed_variants.csv",index=False)
print(S[S.animal_support!=""][["locus_name","rsid","seed_tier","animal_support"]].to_string(index=False,max_colwidth=110))
# model-organism evidence table
v1=pd.read_csv("../current_v1/variants.csv"); v1g=set(v1.gene.dropna().str.upper())
rows=[]
for _,r in mm[mm.H.isin(v1g|{"FGD6","TERT","APOE","HTT"})].iterrows():
    rows.append(dict(human_gene=r.H,model_organism="Mus musculus",evidence_type="GenAge curated gene manipulation",lifespan_effect=r["lifespan effect"],longevity_influence=r["longevity influence"],source=f"GenAge models build (2023-10), GenAge ID {r['GenAge ID']}",in_v1=r.H in v1g,in_gwas_seed=r.H in {"TERT","APOE","HTT"}))
rows+= [dict(human_gene="FGD6",model_organism="Mus musculus UM-HET3 + C. elegans",evidence_type="unbiased lifespan QTL + RNAi validation",lifespan_effect="tag-77 RNAi shortened lifespan (~14%)",longevity_influence="Pro-Longevity (gene activity)",source="Bou Sleiman 2022 Science PMID 36173858",in_v1=False,in_gwas_seed=True),
 dict(human_gene="(mouse chr12 locus; candidate Susd6/DRAGO)",model_organism="Mus musculus DO, UM-HET3, BXD",evidence_type="unbiased lifespan QTL replicated across populations",lifespan_effect="CAST allele +106 days (DRiDO)",longevity_influence="locus-level",source="Mullis 2025 Genetics PMID 40326784; Bou Sleiman 2022 PMID 36173858",in_v1=False,in_gwas_seed=False),
 dict(human_gene="(mouse chr18 locus; candidate Garem1)",model_organism="Mus musculus DO",evidence_type="unbiased lifespan QTL",lifespan_effect="CAST allele -175 days (DRiDO)",longevity_influence="locus-level",source="Mullis 2025 Genetics PMID 40326784",in_v1=False,in_gwas_seed=False)]
pd.DataFrame(rows).to_csv("longevitymap_v2_model_organism_evidence.csv",index=False); print(len(rows),"model-organism rows")
