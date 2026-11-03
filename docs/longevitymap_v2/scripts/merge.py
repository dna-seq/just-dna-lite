import pandas as pd, re, numpy as np, json
T={t:pd.read_csv(f"tracks/{t}.csv") for t in "ABDEGH"}
v1=set(pd.read_csv("../current_v1/variants.csv").rsid)
def tierB(s):
    s=str(s); return {"T1":"A","T2":"B","T3":"B","T4":"C"}.get(s[:2])
def tierL(s):
    s=str(s).strip(); m=re.match(r"([ABCDX])",s); return m.group(1) if m else None
rows=[]
for t,d in T.items():
    for _,r in d.iterrows():
        rs=str(r.get("rsid","")).strip()
        if not rs.startswith("rs"): continue
        tier={"B":tierB(r.get("evidence_tier")),"E":tierL(r.get("evidence_tier_proposed")),"G":tierL(r.get("proposed_evidence_tier")),"H":tierL(r.get("evidence_tier"))}.get(t)
        # pro-longevity allele
        pro=None; ea=str(r.get("effect_allele","")).strip(); dirn=str(r.get("direction","")).lower()
        if t=="H":
            la=str(r.get("longevity_allele","")); m=re.match(r"^([ACGT]+)\b",la); pro=m.group(1) if m else None
        elif re.fullmatch(r"[ACGT]+",ea or ""):
            if dirn.startswith("pro"): pro=ea
            elif dirn.startswith("anti"):
                oa=str(r.get("other_allele_if_known","")).strip()
                pro=oa if re.fullmatch(r"[ACGT]+",oa) else f"not-{ea}"
        pos=None; chrom=None; ref=alt=None
        if t=="B" and pd.notna(r.get("pos_grch38")): chrom=str(r["chr_grch38"]).replace(".0",""); pos=int(r["pos_grch38"])
        vid=r.get("ot_variant_id_grch38")
        if isinstance(vid,str) and vid.count("_")>=3:
            c,p,ref,alt=vid.split("_")[:4]; chrom=c; pos=int(p)
        gene=r.get("gene") if pd.notna(r.get("gene",np.nan)) else (r.get("locus_label") if t=="G" else r.get("gene_locus"))
        rows.append(dict(track=t,rsid=rs,gene=str(gene) if pd.notna(gene) else "",tier=tier,pro=pro,chrom=chrom,pos=pos,ref=ref,alt=alt,
            pmid=str(r.get("pmid","")).replace(".0","") if pd.notna(r.get("pmid",np.nan)) else "",
            phenotype=str(r.get("phenotype","")) if pd.notna(r.get("phenotype",np.nan)) else "",
            ancestry=str(r.get("ancestry","")) if pd.notna(r.get("ancestry",np.nan)) else "",
            subpanel=r.get("subpanel") if t=="D" else None,
            pleio=r.get("pleiotropy_labels") if t=="H" else None, through=r.get("acts_mainly_through") if t=="H" else None,
            net=r.get("net_lifespan_direction") if t=="H" else None,
            pip=r.get("max_pip_longevity_traits") if t=="G" else None, l2g=r.get("l2g_top") if t=="G" else None,
            action=r.get("proposed_actionability_tier") if t=="G" else None, mediator=r.get("modifiable_mediator") if t=="G" else None))
L=pd.DataFrame(rows); L.to_csv("merged_long.csv",index=False)
def agg(g):
    tiers=[x for x in g.tier if isinstance(x,str)]; pros=sorted({x for x in g.pro if isinstance(x,str)})
    concrete={p for p in pros if not p.startswith("not-")}; nots={p[4:] for p in pros if p.startswith("not-")}
    conflict= len(concrete)>1 or bool(concrete & nots)
    order="ABCDX"
    if tiers:
        cnt=pd.Series(tiers).value_counts(); top=cnt[cnt==cnt.max()].index.tolist(); seed=sorted(top,key=order.index)[-1]  # conservative on ties
        if seed!="A" and tiers.count("A")>=2: seed="A"
    else: seed=None
    first=lambda s: next((x for x in s if isinstance(x,str) and x and x!="nan"),None)
    return pd.Series(dict(genes="; ".join(sorted({x for x in g.gene if x and x!='nan'}))[:80],
        tracks="".join(sorted(set(g.track))), n_tracks=g.track.nunique(),
        chrom=first(g.chrom), pos=next((int(x) for x in g.pos if pd.notna(x)),None), ref=first(g.ref), alt=first(g.alt),
        tier_votes="".join(tiers), seed_tier=seed, pro_longevity_allele="/".join(pros), allele_conflict=conflict,
        pmids=";".join(sorted({x for x in g.pmid if x and x!='nan'})), phenotypes="; ".join(sorted({x[:40] for x in g.phenotype if x}))[:160],
        ancestry="; ".join(sorted({x[:25] for x in g.ancestry if x}))[:80], subpanel=first(g.subpanel),
        pleiotropy_labels=first(g.pleio), acts_mainly_through=first(g.through), net_lifespan_direction=first(g.net),
        max_pip_longevity=next((x for x in g.pip if pd.notna(x)),None), l2g_top=first(g.l2g), actionability_proposed=first(g.action), modifiable_mediator=first(g.mediator),
        in_v1=g.name in v1))
S=L.groupby("rsid").apply(agg).reset_index()
# locus clustering by position (1 Mb), HLA region collapsed
S["chrom_n"]=S.chrom.map(lambda c: {"X":23}.get(str(c), int(c) if str(c).isdigit() else 99))
S=S.sort_values(["chrom_n","pos"]); lid=0; prev=(None,None); ids=[]
for _,r in S.iterrows():
    if pd.isna(r.pos): lid+=1; ids.append(lid); continue
    if prev[0]==r.chrom and prev[1] is not None and r.pos-prev[1]<1_000_000: ids.append(lid)
    else: lid+=1; ids.append(lid)
    prev=(r.chrom,r.pos)
S["locus_id"]=ids
gname=S.groupby("locus_id").genes.agg(lambda x: pd.Series([g.split(";")[0].split(",")[0].strip() for g in x if g]).mode().iloc[0] if any(x) else "")
S["locus_name"]=S.locus_id.map(gname)
rank={"A":0,"B":1,"C":2,"D":3,"X":4,None:5}
S["_r"]=S.seed_tier.map(lambda x: rank.get(x,5)); S["_p"]=S.max_pip_longevity.fillna(-1)
lead=S.sort_values(["locus_id","_r","n_tracks","_p"],ascending=[True,True,False,False]).groupby("locus_id").head(1).rsid
S["is_locus_lead"]=S.rsid.isin(set(lead))
S=S.drop(columns=["_r","_p","chrom_n"])
S.to_csv("longevitymap_v2_seed_variants.csv",index=False)
Ld=S[S.is_locus_lead]
print("rsids",len(S),"loci",S.locus_id.nunique(),"no-position rsids",S.pos.isna().sum())
print("lead tier counts", Ld.seed_tier.value_counts(dropna=False).to_dict())
print("allele conflicts", int(S.allele_conflict.sum()), S[S.allele_conflict][["rsid","genes","pro_longevity_allele","tracks"]].to_string(index=False))
print("in v1 among all rsids:", int(S.in_v1.sum()))
print(Ld[Ld.seed_tier.isin(["A","B"])][["locus_name","rsid","chrom","pos","seed_tier","tier_votes","tracks","pro_longevity_allele","in_v1"]].to_string(index=False))
