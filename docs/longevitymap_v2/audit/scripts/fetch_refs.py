import sys, re, html, json, time, sqlite3, requests, pandas as pd
REPO = "/home/antonkulaga/sources/just-dna-lite"; M = f"{REPO}/data/interim/registered_modules/just_dna_seq__longevitymap"
what = sys.argv[1]
con = sqlite3.connect(f"{REPO}/data/modules/just_longevitymap/longevitymap.sqlite")
sv = pd.read_sql("select id, identifier, quickpubmed from variant", con).astype(str)
tsv = pd.read_csv(f"{REPO}/data/longevity_map.tsv", sep="\t", dtype=str).fillna("")
st = pd.read_csv(f"{M}/studies.csv", dtype=str).fillna("")
v1 = pd.read_csv(f"{M}/variants.csv", dtype=str).fillna("")

if what == "hagr":
    ids = set(tsv.id) | set(sv.merge(st, left_on=["quickpubmed", "identifier"], right_on=["pmid", "rsid"]).id)
    ids = sorted((i for i in ids if i.isdigit()), key=int)
    rows = []
    FIELDS = ["Longevity Association", "Population", "Study Design", "Conclusions", "Identifier", "HGNC symbol", "Cytogenetic Location"]
    for n, i in enumerate(ids):
        try:
            t = requests.get(f"https://genomics.senescence.info/longevity/entry.php?id={i}", timeout=40).text
        except Exception as e:
            rows.append(dict(id=i, error=str(e))); continue
        t = re.sub(r"<script.*?</script>", "", t, flags=re.S)
        parts = [html.unescape(p).strip() for p in re.split(r"<[^>]+>", t)]
        parts = [p for p in parts if p]
        rec = dict(id=i, found="Entry Details" in parts)
        for f in FIELDS:
            if f in parts:
                k = parts.index(f); rec[f] = parts[k + 1] if k + 1 < len(parts) else ""
        m = re.search(r"pubmed[^\"']*?(\d{6,8})", t, flags=re.I)
        rec["pmid_link"] = m.group(1) if m else ""
        rows.append(rec)
        time.sleep(0.4)
        if n % 100 == 0: print(n, len(ids), flush=True)
    pd.DataFrame(rows).to_csv("hagr_web_entries.csv", index=False)
    print("hagr done", len(rows))

if what == "vep":
    rs = sorted(set(v1.rsid) | {x for x in tsv.identifier if re.match(r"^rs\d+$", str(x))} | {x for x in sv.identifier if re.match(r"^rs\d+$", str(x))} & set(st.rsid))
    rs += ["rs61752717", "rs28940578", "rs28940580", "rs3743930", "rs1799889", "rs429358", "rs1800629"]
    rs = sorted(set(rs))
    out = {}
    for k in range(0, len(rs), 150):
        b = rs[k:k + 150]
        for attempt in range(4):
            r = requests.post("https://rest.ensembl.org/vep/human/id", params={"hgvs": 1, "canonical": 1, "content-type": "application/json"},
                              json={"ids": b}, headers={"Content-Type": "application/json", "Accept": "application/json"}, timeout=180)
            if r.status_code == 200: break
            time.sleep(5 * (attempt + 1))
        for rec in r.json() if r.status_code == 200 else []:
            out[rec.get("id")] = rec
        print("vep", k, r.status_code, flush=True)
        time.sleep(1)
    var = {}
    for k in range(0, len(rs), 200):
        b = rs[k:k + 200]
        r = requests.post("https://rest.ensembl.org/variation/homo_sapiens", json={"ids": b}, headers={"Content-Type": "application/json", "Accept": "application/json"}, timeout=180)
        if r.status_code == 200: var.update(r.json())
        print("var", k, r.status_code, flush=True); time.sleep(1)
    json.dump(dict(vep=out, variation=var), open("ensembl_refs.json", "w"))
    print("vep done", len(out), len(var))
