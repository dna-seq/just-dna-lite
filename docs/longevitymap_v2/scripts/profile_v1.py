import pandas as pd, json
v=pd.read_csv("../current_v1/variants.csv"); s=pd.read_csv("../current_v1/studies.csv")
out={}
out["rows"]=len(v); out["rsids"]=int(v.rsid.nunique()); out["genes"]=int(v.gene.nunique())
out["category"]=v.category.value_counts(dropna=False).to_dict()
out["state"]=v.state.value_counts().to_dict()
out["weight_min_median_max"]=[float(v.weight.min()),float(v.weight.median()),float(v.weight.max())]
out["distinct_conclusions"]=int(v.conclusion.nunique())
out["study_rows"]=len(s); out["study_pmids"]=int(s.pmid.nunique())
out["stat_significance"]=s.stat_significance.value_counts(dropna=False).to_dict()
c=s.groupby("pmid").rsid.nunique().sort_values(ascending=False)
out["top_pmids_by_rsids"]={str(k):int(x) for k,x in c.head(5).items()}
out["study_rsids"]=int(s.rsid.nunique())
sig=s[s.stat_significance=="significant"].groupby("rsid").pmid.nunique()
out["rsids_ge2_sig_pmids"]=int((sig>=2).sum()); out["rsids_ge3_sig_pmids"]=int((sig>=3).sum())
out["rsids_no_sig_study"]=int((~s.groupby("rsid").stat_significance.apply(lambda x:(x=="significant").any())).sum())
out["top_populations"]=s.population.value_counts().head(5).to_dict()
json.dump(out,open("v1_profile.json","w"),indent=1); print(json.dumps(out))
