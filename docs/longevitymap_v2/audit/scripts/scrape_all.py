import re, html, time, requests, pandas as pd
from concurrent.futures import ThreadPoolExecutor
done = set(pd.read_csv("hagr_web_entries.csv", dtype=str).id)
ids = [str(i) for i in range(1, 3501) if str(i) not in done]
FIELDS = ["Longevity Association", "Population", "Study Design", "Conclusions", "Identifier", "HGNC symbol", "Cytogenetic Location"]
def get(i):
    for a in range(3):
        try:
            t = requests.get(f"https://genomics.senescence.info/longevity/entry.php?id={i}", timeout=40).text; break
        except Exception: time.sleep(3)
    else: return dict(id=i, error="fetch")
    t = re.sub(r"<script.*?</script>", "", t, flags=re.S)
    parts = [p for p in (html.unescape(x).strip() for x in re.split(r"<[^>]+>", t)) if p]
    rec = dict(id=i, found="Entry Details" in parts)
    for f in FIELDS:
        if f in parts:
            k = parts.index(f); rec[f] = parts[k + 1] if k + 1 < len(parts) else ""
    time.sleep(0.3); return rec
with ThreadPoolExecutor(3) as ex: rows = list(ex.map(get, ids))
pd.concat([pd.read_csv("hagr_web_entries.csv", dtype=str), pd.DataFrame(rows).astype(str)]).to_csv("hagr_web_all.csv", index=False)
print("scraped", len(rows), "found", sum(r.get("found") is True for r in rows))
