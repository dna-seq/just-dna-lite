"""Build the tabbed, self-contained HTML research report for longevitymap v2.
Run: uv run python build_report.py  (reads files in this directory; optional round-3 inputs in ./round3/)"""
import base64, html, io, json, os, re
import pandas as pd
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt

H = html.escape
OUT = "../deliverables/longevitymap_v2_research_report.html"
BLUE, ORANGE, SKY, BGREEN, VERM, PURP, YEL, GREY = "#0072B2", "#E69F00", "#56B4E9", "#009E73", "#D55E00", "#CC79A7", "#F0E442", "#BBBBBB"
mpl.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.titlesize": 11, "axes.labelsize": 11,
                     "xtick.labelsize": 9.5, "ytick.labelsize": 9.5})

LB, RB, KW = "{" * 2, "}" * 2, "artifact"
def art(vid, label):  # artifact link marker, resolved by the app
    return f'<a href="{LB}{KW}:{vid}{RB}">{H(label)}</a>'

def img_b64(path):
    return "data:image/png;base64," + base64.b64encode(open(path, "rb").read()).decode()

def fig_b64(fig):
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=150, bbox_inches="tight"); plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

def table(df, cols=None, cls="tbl", maxlen=400, ids=None):
    cols = cols or list(df.columns)
    th = "".join(f"<th>{H(str(c))}</th>" for c in cols)
    rows = []
    for _, r in df.iterrows():
        tds = "".join(f"<td>{H(str(r[c]) if pd.notna(r[c]) else '')[:maxlen]}</td>" for c in cols)
        rows.append(f"<tr>{tds}</tr>")
    idattr = f' id="{ids}"' if ids else ""
    return f'<div class="tw"><table class="{cls}"{idattr}><thead><tr>{th}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'

# ---------------- data
seed = pd.read_csv("longevitymap_v2_seed_variants.csv")
prof = json.load(open("v1_profile.json"))
H8 = pd.read_csv("tracks/H.csv")
appr = pd.read_csv("tracks/I_approaches.csv")
mo = pd.read_csv("longevitymap_v2_model_organism_evidence.csv")
cites = json.load(open("cites.json"))
R3 = "round3"
age = pd.read_csv(f"{R3}/age_of_action.csv") if os.path.exists(f"{R3}/age_of_action.csv") else None
defs = pd.read_csv(f"{R3}/definitions.csv") if os.path.exists(f"{R3}/definitions.csv") else None
r3notes = json.load(open(f"{R3}/notes.json")) if os.path.exists(f"{R3}/notes.json") else {}

# ---------------- charts
info_png = img_b64("longevitymap_v2_infographic.png")
# v1 categories
cat = pd.Series(prof["category"]).sort_values()
fig, ax = plt.subplots(figsize=(6.2, 3.6))
ax.barh(cat.index, cat.values, color=[VERM if k == "other" else BLUE for k in cat.index])
for i, v in enumerate(cat.values): ax.text(v + 6, i, f"{v}", va="center", fontsize=9.5)
ax.set_xlabel("genotype rows in v1.2.0 (n = 1,022)"); ax.set_title("47% of v1 rows sit in the 'other' category", loc="left", fontweight="bold")
for s in ("top", "right"): ax.spines[s].set_visible(False)
ax.margins(x=0.12)
cat_png = fig_b64(fig)
# v1 study concentration
top = prof["top_pmids_by_rsids"]
fig, ax = plt.subplots(figsize=(6.2, 3.0))
labs = [f"PMID {k}" for k in top]; vals = list(top.values())
ax.barh(labs[::-1], vals[::-1], color=[VERM if k == "22279548" else BLUE for k in list(top)[::-1]])
for i, v in enumerate(vals[::-1]): ax.text(v + 4, i, str(v), va="center", fontsize=9.5)
ax.set_xlabel(f"rsIDs supported (of {prof['study_rsids']} study-cited rsIDs)")
ax.set_title("One 2012 classifier supports 280 rsIDs", loc="left", fontweight="bold")
for s in ("top", "right"): ax.spines[s].set_visible(False)
ax.margins(x=0.12)
conc_png = fig_b64(fig)
# seed lead tiers
lead = seed[seed.is_locus_lead]
tc = lead.seed_tier.fillna("ungraded").value_counts().reindex(["A", "B", "C", "D", "X", "ungraded"]).fillna(0).astype(int)
fig, ax = plt.subplots(figsize=(6.2, 2.8))
cols = [BLUE, SKY, "#9E9E9E", "#CFCFCF", "#E0E0E0", "#EEEEEE"]
ax.bar(["A", "B", "C", "D", "excluded", "ungraded"], tc.values, color=cols, edgecolor="#777777", linewidth=0.5)
for i, v in enumerate(tc.values): ax.text(i, v + 1.5, str(v), ha="center", fontsize=9.5)
ax.set_ylabel("lead loci"); ax.set_title(f"Seed: {len(lead)} lead loci by provisional tier", loc="left", fontweight="bold")
for s in ("top", "right"): ax.spines[s].set_visible(False)
ax.margins(y=0.15)
tier_png = fig_b64(fig)
# genetics vs lifestyle
fig, axs = plt.subplots(1, 2, figsize=(7.6, 2.6))
axs[0].barh(["polygenic score\n(short vs long)", "lifestyle\n(unfavourable vs favourable)"], [0.21, 0.78], color=[BLUE, ORANGE])
axs[0].set_xlabel("extra mortality hazard (HR − 1)"); axs[0].set_title("Bian 2024, UK Biobank", loc="left", fontsize=10)
for i, v in enumerate([1.21, 1.78]): axs[0].text([0.21, 0.78][i] + 0.02, i, f"HR {v}", va="center", fontsize=9.5)
axs[1].barh(["22 disease\npolygenic scores", "exposome\n(25 factors)"], [2, 17], color=[BLUE, ORANGE])
axs[1].set_xlabel("extra mortality variance (pp)"); axs[1].set_title("Argentieri 2025, n = 492,567", loc="left", fontsize=10)
for i, (v, t) in enumerate([(2, "<2 pp"), (17, "+17 pp")]): axs[1].text(v + 0.4, i, t, va="center", fontsize=9.5)
for a in axs:
    a.margins(x=0.25)
    for s in ("top", "right"): a.spines[s].set_visible(False)
fig.tight_layout()
gl_png = fig_b64(fig)

# ---------------- tab content
ART = {  # artifact ids from this session
 "req": "a8f18069-2841-4af9-9025-ee585e36d1ee", "seed": "bfd36b8d-a43d-4249-ba31-19686d91f521",
 "cmp": "427d12d6-5573-439c-ac0f-4fbe605a9ec3", "info_png": "f4f09911-51ad-4380-9c54-719bbd5d018a",
 "info_pdf": "8bbd2576-abba-4dc4-991d-98889119514e", "age_png": "5ceba108-0afa-472a-944d-73246ff89b04",
 "mo": "9d07043d-0053-4457-b477-32906a172825", "audit": "0a8e1c5c-e7a0-4447-8311-0f1e454c3020",
}
TRACKS = [
 ("A: LongevityMap & HAGR, v1 audit", "5886f1a8-7682-441a-bac8-68715aa67e39", "4022b06f-7d90-451d-9fd6-34b4cfe42acd", "a10da825-c259-4c7f-bd5f-4d5c716257f3"),
 ("B: common-variant GWAS", "5096fbec-f21e-4184-8a3f-e2e98c8a168b", "58469df8-058f-4ebb-bd6b-a15c40011b00", "edd94f82-f452-4846-8e0b-5418ce424536"),
 ("D: healthspan, biological age, heritability", "c6486a63-18c8-407c-9aa4-6d2d1dd63045", "37bbdfb9-3320-4f50-97a1-681f3ef945b0", "9253f9f6-d334-491c-9def-066ded8b1d0e"),
 ("E: 2025–2026 preprints and papers", "614439c6-ffd6-40fb-b160-b926cc8a151f", "a855e764-002a-4be8-86b7-72e68b361194", "34dc5447-f162-477c-9be2-90aa4a3b5a5b"),
 ("F: reporting to three audiences", "ddd14c9d-7295-43e3-bef5-67284c87e17f", "b383d002-13be-4749-ae08-c9f879a0cf85", None),
 ("G: SNP evaluation methodology", "a6950555-ff10-4a53-8c41-c34eb1989a28", "dc38d981-fc62-4740-928b-585c12eafffc", "0587a5ac-f812-42bc-9ca2-9d2f3086bdab"),
 ("H: pleiotropy", "97c7a276-700e-4329-acb9-b181b14def0a", "d8872a01-604f-4128-85d2-78c2df9982e9", "8cef5082-bf79-4fe3-ae73-43dadd748591"),
 ("I: conceptual and meta-reviews", "95b180fd-7121-4e36-8bfe-92feb4029363", "e209e94f-7a0a-4b75-afea-15d25c9784e8", "18213213-d029-4b11-89a5-08809d0e4abf"),
] + r3notes.get("tracks", [])

def cite(pmid):
    c = cites.get(str(pmid))
    lab = f"{c['first'].split()[0]} {c['year']}" if c else f"PMID {pmid}"
    return f'<a class="pm" href="https://pubmed.ncbi.nlm.nih.gov/{pmid}/" title="{H(c["title"]) if c else ""}">{H(lab)}</a>'

tabs = []
def tab(key, title, body): tabs.append((key, title, body))

tab("overview", "Overview", f"""
<p class="lead">v2 rebuilds the module around <b>genome-wide, replicated evidence</b>, organised by <b>how each variant acts</b>,
with seven per-locus axes reported separately and <b>no summed per-SNP score</b>. Full specification: {art(ART['req'], 'longevitymap_v2_requirements.md')}.</p>
<img class="wide" src="{info_png}" alt="longevitymap v2 infographic">
<div class="grid2">
<div class="card"><h3>Key principles</h3><ol>
<li>Evidence first: only genome-wide, replicated signals are scored; everything else is research view.</li>
<li>One lead variant per locus; LD proxies and APOE-region tags are never counted twice.</li>
<li>A lead SNP “marks a region” unless fine-mapping makes it likely causal; name the gene only when confident.</li>
<li>Say what it acts through, at what age, on healthy years or on length of life, and state trade-offs both ways.</li>
<li>Every genotype gets a row; the most common genotype is the neutral reference.</li>
<li>Ancestry, sex and age limits travel with the finding.</li>
<li>Every claim has a receipt: PMID, effect allele, effect size with unit, located quote.</li></ol></div>
<div class="card never"><h3>Never</h3><ul>
<li>A summed “longevity score” or net weight from single SNPs</li><li>A predicted lifespan or genotype-based “biological age”</li>
<li>Red/green good–bad colouring, least of all on trade-offs</li><li>Odds ratios for citizens without plain-language context</li>
<li>“Gene that controls ageing” wording</li><li>An animal result raising a human tier or weight</li></ul></div></div>""")

tab("why", "Why v2", f"""
<p>v1.2.0 is a faithful port of HAGR LongevityMap, frozen at Build 3 (2017-06-24; {cite(29121237)}, {cite(37933854)}). Out of date is not broken:
it met LongevityMap's contract, an inclusive literature index. Measured on 2026-11-03 ({art(ART['audit'], 'audit profile')}):</p>
<div class="kpis">
<div class="kpi"><b>280 / 516</b><span>study-cited rsIDs rest on one 2012 classifier ({cite(22279548)}); its 2010 predecessor is retracted ({cite(20595579)})</span></div>
<div class="kpi"><b>975 / 1,022</b><span>genotype rows labelled “protective”; 47 risk; 0 neutral</span></div>
<div class="kpi"><b>35 / 528</b><span>rsIDs with ≥2 independent significant studies</span></div>
<div class="kpi"><b>79</b><span>distinct conclusion texts for 1,022 rows; none addresses the reader</span></div>
<div class="kpi"><b>0 / 671</b><span>study rows with effect allele, effect size or p-value</span></div>
<div class="kpi"><b>~7 / ~150</b><span>genome-wide longevity rsIDs in v1 (provisional; trait-set dependent)</span></div></div>
<div class="grid2"><img src="{conc_png}" alt="study concentration"><img src="{cat_png}" alt="v1 categories"></div>
<p>Missing entirely: LPA, CHRNA3/5, 9p21 (CDKN2B-AS1), SH2B3/ATXN2, HLA-DQA1/DRB1, LDLR, FURIN, ZW10 — the best-replicated modern loci
({cite(30642433)}, {cite(31413261)}, {cite(32678081)}, {cite(29030599)}).</p>""")

cmp_md = open("../deliverables/longevitymap_v1_vs_v2.md").read()
rows = [l for l in cmp_md.splitlines() if l.startswith("| **")]
cmp_html = "".join("<tr>" + "".join(f"<td>{re.sub(r'\\*\\*(.+?)\\*\\*', r'<b>\\1</b>', H(c.strip()))}</td>" for c in l.strip('|').split(' | ')) + "</tr>" for l in rows)
tab("compare", "v1 vs v2", f"""<div class="tw"><table class="tbl cmp"><thead><tr><th>Aspect</th><th>v1.2.0 (published)</th><th>v2 (designed)</th></tr></thead><tbody>{cmp_html}</tbody></table></div>""")

tab("tiers", "Evidence tiers", f"""
<p>Merged rubric from the methodology, GWAS, preprint and reporting tracks; labels follow ClinGen risk-allele language ({cite(38054408)}) and Venice credibility grading ({cite(17898028)}).</p>
<div class="ladder">
<div class="rung a"><b>A · Well established</b><span>p &lt; 5×10⁻⁸ for longevity / lifespan / parental lifespan / healthspan in ≥100k lives or ≥3k cases above the 90th percentile; independent replication, same allele and direction; no red-flag heterogeneity. Shown first.</span></div>
<div class="rung b"><b>B · Likely</b><span>genome-wide locus but one study, a tag SNP outside the credible set, a much smaller replicated effect, or ancestry-specific replication only. Shown.</span></div>
<div class="rung c"><b>C · Early evidence</b><span>suggestive (p &lt; 10⁻⁵), small or same-group replication, preprint only. Research view.</span></div>
<div class="rung d"><b>D · Not supported</b><span>candidate-only without adequate replication, contradicted (e.g. IL6, USP42, TMTC2 in {cite(30642433)}), meta-null, retracted or overfit source. Research view, as negative evidence.</span></div></div>
<p class="note">Hard rules: rows supported only by PMID 22279548 → D; unreplicated centenarian-vs-young designs capped at C; European tiers not transferred to other ancestries; MR-only, sub-genome-wide and n = 1 genomes never A/B.</p>
<img src="{tier_png}" alt="seed tiers"><p class="note">Seed tiers are a mechanical consensus of track proposals; curation will prune tier B (many single-study GWAS Catalog hits).</p>""")

axes_rows = [
 ("Evidence tier", "A / B / C / D", "gates scoring and default visibility", "flags tier:X + priority (format request: evidence_tier)"),
 ("Mechanism", "heart_vessels, brain_memory, smoking_lungs, immune_inflammation, metabolism, skin_sun, general_ageing, ageing_markers", "what the locus acts through; report grouping", "category; mediator EFO in flags"),
 ("Pleiotropy", "mech:&lt;area&gt;, broad, tradeoff, context:&lt;x&gt;, nonadditive, ap:&lt;strength&gt;, mr:drug_target_proxy", "trade-offs both ways", "flags (+ reserved pleiotropic); negatives prose; direction=contested"),
 ("Age of action", "lifelong / midlife / late / age_inverting / early_life / unknown", "when in life the effect operates", "flags age:&lt;class&gt;; evidence in studies.csv"),
 ("Outcome profile", "healthspan · lifespan · exceptional survival: raises / none / lowers / untested", "healthy years vs length of life vs reaching very old age", "flags outcome:&lt;dim&gt;&lt;sign&gt;; phenotype class per study row"),
 ("Actionability", "preventable / modifiable / descriptive + what (test, screening, behaviour) + who (you / doctor)", "is there something to measure or change", "actionability (closed vocab) + flags act_test:/act_behaviour:"),
 ("Context", "eur_only_evidence, ancestry_specific:&lt;pop&gt;, sex_specific:&lt;m|f&gt;", "who the evidence applies to", "flags; population on studies.csv"),
 ("Causal / effector confidence", "C1–C4 (fine-mapping PIP) · E1–E4 (L2G, coloc)", "is this SNP causal; which gene", "flags causal:/effector:; gene = effector call"),
 ("Animal support", "genage_mouse, mouse_qtl, worm_rnai", "cross-species context only", "flags animal:; studies.csv model_organism"),
]
axes_html = "".join(f"<tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td><td><code>{d}</code></td></tr>" for a, b, c, d in axes_rows)
tab("axes", "Classification axes", f"""
<p>Each scored locus carries these axes, <b>reported separately and never merged into one score</b>.</p>
<div class="tw"><table class="tbl"><thead><tr><th>Axis</th><th>Values</th><th>Answers</th><th>Home in format 0.7.1</th></tr></thead><tbody>{axes_html}</tbody></table></div>
<h3>Worked example: LPA rs10455872</h3>
<div class="example">
<div><b>Tier</b> A — genome-wide in parental lifespan ({cite(30642433)}; +0.76 years per A allele) and the multivariate scan ({cite(32678081)})</div>
<div><b>Mechanism</b> heart_vessels — Lp(a)-driven coronary disease and aortic stenosis</div>
<div><b>Pleiotropy</b> mech:cvd; very low Lp(a) linked to type 2 diabetes (trade-off at the extreme)</div>
<div><b>Age of action</b> MIDLIFE (confidence DIRECT_WEAK): per-allele log protection ratio 0.109 → 0.078 → 0.053 across parental ages 40–60 / 60–80 / 80+ (age moderation P = 0.04, FDR q = 0.76). Report phrase: “Mainly lowers the chance of dying before about 80, through less Lp(a)-driven heart and valve disease; the benefit shrinks but does not disappear at older ages.”</div>
<div><b>Outcome profile</b> lifespan ✓ · healthspan ✓ (multivariate scan) · exceptional survival: to be checked against 90th/99th-percentile data at curation</div>
<div><b>Protection type</b> PROTECT:ABSENCE_OF_RISK — the common allele does not raise Lp(a)</div>
<div><b>Actionability</b> preventable — an Lp(a) blood test, once in life, ordered by a doctor; the measured level matters more than the genotype</div>
<div><b>Context</b> eur_only_evidence — risk allele G ≈ 7% in non-Finnish Europeans, ≈ 0.1% in East Asians (gnomAD via Open Targets)</div>
<div><b>Causal / effector</b> C2 (PIP 0.38; second signal rs186696265 PIP 0.93) · E1/E2 (L2G LPA 0.56–0.76)</div></div>""")

MECH = [
 ("Heart and vessels", BLUE, "LPA rs10455872 (A) · LDLR rs142158911 (A) · CDKN2B-AS1 rs1556516 (A) · CELSR2/SORT1 rs646776 (A) · PCSK9 R46L rs11591147 (B)", "preventable: Lp(a), LDL-C, blood pressure"),
 ("Brain and memory", PURP, "APOE ε2/ε3/ε4 (A; scored once as a diplotype) ★", "descriptive; opt-in; Alzheimer's implication stated"),
 ("Smoking and lungs", ORANGE, "CHRNA3/5 rs8042849 (A)", "modifiable: smoking"),
 ("Immune system", BGREEN, "HLA-DQA1/DRB1 rs34967069 (A) · SH2B3/ATXN2 rs11065979 (A) ⇄ · MAGI3/PTPN22 rs1230666 (B) · IL6R rs2228145 (B) ⇄ · IL6 rs2069837 (B, Chinese)", "trade-offs: autoimmunity/CVD vs cancer/infection"),
 ("Blood sugar and weight", YEL, "TCF7L2 rs35198068 (B) · FTO / MC4R (C, via BMI)", "modifiable: weight, glucose"),
 ("Skin and sun", SKY, "IRF4 rs12203592 (B) · TYR rs1126809 (B) · DEF8 rs4268748 (B)", "modifiable: sun protection; healthspan via skin cancer"),
 ("Ageing in general", "#777777", "FOXO3 rs1159806 (B) · ZW10/USP28 rs61905747 (A) · FGD6 rs12830425 (B) ★ · HTT rs61348208 (B) ★ · pending: FES/FURIN rs6224 (A), KCNK3 rs1275922 (B)", "descriptive"),
 ("Ageing markers (not scored)", "#AAAAAA", "TERT rs2736100 ★ · TERC rs10936599 · epigenetic clocks · loss of Y · mtDNA copy number", "marker tendency, not a longer-life allele"),
]
mech_html = "".join(f'<div class="mcard" style="border-color:{c}"><div class="mh" style="background:{c}">{H(t)}</div><p>{H(l)}</p><p class="note">{H(n)}</p></div>' for t, c, l, n in MECH)
tab("mech", "Mechanism map", f"""<p>Most lifespan signal runs through specific diseases: in {cite(30642433)} the top disease SNPs explain 0.43 y² of lifespan variance via CVD, 0.15 y² via smoking/lung cancer and 0.11 y² via other cancers; APOE alone 0.23 y².
Tiers are seed consensus (provisional). ★ animal support · ⇄ trade-off.</p><div class="mgrid">{mech_html}</div>""")

pcols = ["rsid", "gene_locus", "longevity_allele", "pleiotropy_labels", "acts_mainly_through", "beneficial_associations_of_longevity_allele", "harmful_associations_or_tradeoffs_of_longevity_allele", "context_modifiers", "net_lifespan_direction", "evidence_tier"]
P = H8[pcols].copy()
if age is not None:
    ac = [c for c in age.columns if c.lower() in ("rsid", "age_of_action", "confidence", "report_phrase")]
    P = P.merge(age[ac], on="rsid", how="left")
age_block = ("" if age is not None else '<p class="pending">Age-of-action classes are being collected by a running sub-agent; this table gains them on the next build.</p>')
tab("pleio", "Pleiotropy & age", f"""
<p>From the pleiotropy track (Open Targets credible-set PheWAS + literature; {art('8cef5082-bf79-4fe3-ae73-43dadd748591','locus table')}).
Timmers 2020 ({cite(32678081)}): the protective effects of the 9 non-APOE loci shrink ~24% per decade of parental age while the APOE ε4 effect grows ~32% per decade — most loci act on mid- and late-life mortality, not on reaching extreme ages.</p>
{age_block}{r3notes.get('age_summary_html','')}
{table(P, maxlen=260)}""")

dcols = ["approach", "description", "representative_papers_pmids", "strengths", "blind_spots", "implication_for_module"]
NEW2526 = pd.DataFrame([
 ("Age-stratified / ancestry-specific survival GWAS", "alleles whose association changes with the age band reached", "41949656; 42176242; Sasaki 2025 (preprint)", "small, suggestive; 3 of 14 replicated SNPs flipped direction (Taiwan)", "score only if tier rules met; ancestry-restricted"),
 ("Own-survival GWAS + rare-variant burden (UKB)", "genes where rare damaging variants change one's own survival", "40021682", "many cancer genes; TET2/ASXL1 likely somatic clonal haematopoiesis", "cross-reference to cancer modules; CH flag"),
 ("Rare protective alleles / LoF depletion in the long-lived", "genes intolerant to damage in centenarians", "40232348; 39424787", "CH confound; private variants rarely replicate", "annotation only"),
 ("Allele-level HLA immunogenetics", "specific HLA alleles/haplotypes", "41116190; 41135092", "needs HLA typing/imputation", "hook; tag SNPs flagged"),
 ("Absence of risk: low polygenic disease burden", "long-lived carry less CAD/AD polygenic risk", "38634500; 40615639; 42065824", "longevity as disease avoidance, not 'longevity genes'", "context sentences"),
 ("Evolutionary trade-off definitions", "alleles that raise fertility/early fitness but shorten life", "Brigos-Barril 2026 Nat Ecol Evol; 39751714", "population-level, hard per individual", "trade-off labels"),
 ("Causal / drug-target (MR + coloc + experiments)", "genes whose genetically lower/higher activity extends life or healthspan", "41004220; Leung 2026", "MR assumptions; target ≠ 'good genotype'", "mr:drug_target_proxy flag"),
 ("Biomarker-anchored (proteomic / organ clocks)", "alleles that slow a measured clock", "Argentieri 2025 (preprint); Zhu 2025", "clock loci mostly pQTLs", "unscored ageing-markers section"),
 ("Long-read structural variation", "structural haplotypes invisible to short reads", "41282933 (preprint); TMEM106B (preprint)", "not callable from typical VCFs", "callability hooks"),
 ("Reframing heritability (intrinsic vs extrinsic)", "separates age-related from external mortality", "41610249", "disputed (two 2026 preprints)", "context card"),
], columns=["approach", "what it defines as pro-longevity", "representative work (PMID)", "main caveat", "use in v2"])
defs_block = table(defs, maxlen=320) if defs is not None else '<p class="pending">The systematic definitions comparison (including viability selection) is being produced by a running sub-agent.</p>'
tab("defs", "Defining pro-longevity", f"""
<h3>Newer approaches, 2025–2026</h3><p class="note">Preprints flagged; most read at abstract level; PMIDs title-verified by the tracks.</p>
{table(NEW2526, maxlen=300)}
<h3>Approaches across the field (conceptual-reviews track)</h3>{table(appr[dcols], maxlen=300)}
<h3>Systematic comparison of definitions</h3>{defs_block}""")

mo_tbl = table(mo, maxlen=200)
tab("animal", "Rare variants & animals", f"""
<h3>Animal evidence</h3>
<p>GenAge mouse lifespan genes overlap <b>22 of 272</b> v1 genes by NCBI orthologues (20 by symbol; 26 with Open Genes) but only <b>3 of 71</b> genes at GWAS-era loci (TERT, APOE, HTT): knockout-style animal evidence and human genome-wide evidence barely overlap.
Unbiased mouse population genetics is the bridge: UM-HET3 (3,276 genotyped ITP mice; {cite(36173858)}), Diversity Outbred ({cite(40326784)}, {cite(41758904)}, {cite(39385029)}) and BXD ({cite(34552269)}).
<b>FGD6</b> is the cleanest cross-species case: human multivariate healthspan/lifespan locus rs12830425 ({cite(32678081)}) and a late-life mouse lifespan QTL candidate whose worm orthologue shortens lifespan when knocked down.</p>
{mo_tbl}
{r3notes.get('animal_html','<p class="pending">Humanised knock-in studies (APOE-TR, SIRT6, BPIFB4, KL-VS) are being reviewed by a running sub-agent.</p>')}
<h3>Rare and protective variants</h3>
{r3notes.get('rare_html','<p class="pending">The rare/protective-variant review is running; until it lands, coverage comes from Ying 2024, Park 2025, Kolbe 2025 and Lin 2021.</p>')}""")

tab("report", "Report design", f"""
<div class="grid3">
<div class="card" style="border-color:{ORANGE}"><h3 style="color:{ORANGE}">Citizen scientist (default)</h3><ul><li>the result in plain words, about you</li><li>copies of the longer-life version (0, 1, 2)</li><li>certainty word; what it acts through; at what age</li><li>healthy years vs length of life</li><li>“may lower / may raise” for trade-offs</li><li>what a doctor can measure instead</li><li>ancestry caveat when it applies</li></ul></div>
<div class="card" style="border-color:{BLUE}"><h3 style="color:{BLUE}">Geneticist (More details)</h3><ul><li>rsID, GRCh38 position, ref/alt, zygosity</li><li>effect allele, effect size with unit, CI, p</li><li>phenotype class, cohort N and ancestry</li><li>fine-mapping and effector-gene confidence</li><li>located quotes and PMIDs</li></ul></div>
<div class="card" style="border-color:{PURP}"><h3 style="color:{PURP}">Ageing researcher (research view)</h3><ul><li>tiers C/D, negative and contradicted evidence</li><li>legacy LongevityMap rows (frozen 2017)</li><li>full pleiotropy list, hallmark tags</li><li>animal-model support</li></ul></div></div>
<h3>Context card (always shown)</h3><img src="{gl_png}" alt="genetics vs lifestyle">
<ul><li>“Most of how long people live is not explained by known DNA variants.” ({cite(38684374)}, {cite(39972219)})</li>
<li>Heritability depends on the estimand: &lt;10% after correcting for assortative mating ({cite(30401766)}); 12–16% in large family trees ({cite(29496957)}); ~50% for “intrinsic” lifespan, contested ({cite(41610249)}).</li>
<li>“Long-lived people carry many disease-risk variants too.” ({cite(20921414)})</li><li>“Nothing here predicts your lifespan.”</li></ul>
<h3>Wording rules</h3><ul><li>Open with the reader's result; association wording; size in words; certainty ladder = tier.</li>
<li>No rsID, p-value, OR or coordinate in labels or conclusions.</li><li>Preventable rows name who decides; never advise starting or stopping a medicine, supplement or diet.</li>
<li>Trade-offs get a two-sided sentence and no good/bad colour.</li></ul>""")

scols = ["locus_name", "rsid", "seed_tier", "tier_votes", "is_locus_lead", "chrom", "pos", "pro_longevity_allele", "genes", "pleiotropy_labels", "acts_mainly_through", "max_pip_longevity", "l2g_top", "actionability_proposed", "animal_support", "in_v1", "tracks", "pmids"]
S = seed[scols].copy(); S["pos"] = S.pos.map(lambda x: "" if pd.isna(x) else str(int(x)))
tab("seed", "Seed variants", f"""
<p>228 rsIDs in 161 loci merged from seven tracks ({art(ART['seed'], 'CSV')}). Filter by any text (gene, rsID, tier, label):</p>
<input id="flt" placeholder="filter, e.g. APOE, tier A, tradeoff, smoking" oninput="filt()">
<label><input type="checkbox" id="leads" onchange="filt()"> lead variants only</label>
{table(S, ids='seedtbl', maxlen=160)}""")

tab("plan", "Build plan & decisions", """
<ol class="steps"><li><b>Scaffold</b> spec (name longevitymap, 2.0.0, GRCh38; weighting, licence, defaults)</li>
<li><b>Curate</b> lead loci from the seed: confirm tiers, one lead per locus, harmonise the lifespan-increasing allele (target ~25–40 scored loci)</li>
<li><b>Evidence</b>: effect numbers from paper tables/supplements, verbatim quotes, sign conventions resolved (Timmers years +, Pilling Martingale +=shorter, Zenin hazard +=worse)</li>
<li><b>Enrich</b> coordinates and ref checks (strand errors were v1's dominant repair)</li>
<li><b>GWAS effects + fine-mapping</b> (enrich_gwas_effects; Open Targets PIP/L2G as flags)</li>
<li><b>Cross-check → compile --strict → verify</b></li><li><b>Reviews</b>: lay reader + scientific reviewer on the rendered report</li>
<li><b>Trial install</b> on the two public genomes (on request) → <b>polygon rehearsal</b> → publish on explicit yes</li></ol>
<h3>Decisions for the author</h3><div class="tw"><table class="tbl"><thead><tr><th>#</th><th>Decision</th><th>Recommended</th></tr></thead><tbody>
<tr><td>D1</td><td>Weights</td><td>none (scale: none); order by tier priority</td></tr>
<tr><td>D2</td><td>APOE ownership</td><td>ε diplotype inside v2, cross-linked to apoe_epsilon, after a render check</td></tr>
<tr><td>D3</td><td>Name/version</td><td>keep longevitymap at 2.0.0; title “Longevity genetics”</td></tr>
<tr><td>D4</td><td>Biological-ageing markers</td><td>unscored closed section (or a separate module later)</td></tr>
<tr><td>D5</td><td>Mortality PGS (PGS000318/319)</td><td>exclude</td></tr>
<tr><td>D6</td><td>Legacy depth</td><td>v1's 528 rsIDs in research view; not the further 2,339 non-significant Build 3 entries</td></tr>
<tr><td>D7</td><td>Ancestry-specific loci without ancestry inference</td><td>research view only</td></tr></tbody></table></div>
<h3>Consumer (just-dna-lite) and format requests</h3><ul>
<li>Category prose from the module or a report: block, replacing hardcoded LONGEVITY_CATEGORIES; hide Net weight; render negatives and flag chips; research-view toggle; “not screened” state; ancestry banner; link to PRS tab.</li>
<li>Format: evidence_tier column; associations/pleiotropy table; effect_modifiers table; second (mediator) EFO; fine-mapping fields on gwas_effects; allele-level HLA.</li></ul>""")

trows = "".join(f"<tr><td>{H(n)}</td><td>{art(s,'synthesis')}</td><td>{art(e,'evidence')}</td><td>{art(v,'table') if v else '—'}</td></tr>" for n, s, e, v in TRACKS)
crow = "".join(f"<tr><td>{cite(k)}</td><td>{H(v['journal'])}</td><td>{H(v['title'])}</td></tr>" for k, v in sorted(cites.items(), key=lambda x: x[1]['year']))
tab("sources", "Sources & limits", f"""
<h3>Track deliverables</h3><div class="tw"><table class="tbl"><thead><tr><th>Track</th><th>Synthesis</th><th>Evidence</th><th>Variant/locus table</th></tr></thead><tbody>{trows}</tbody></table></div>
<p>Also: {art(ART['req'],'requirements')} · {art(ART['cmp'],'v1 vs v2 comparison')} · {art(ART['seed'],'seed variants')} · {art(ART['mo'],'model-organism evidence')} · {art(ART['audit'],'v1 audit')} · {art(ART['info_png'],'infographic PNG')} · {art(ART['info_pdf'],'infographic PDF')} · {art(ART['age_png'],'age-of-action chart')}</p>
<h3>Limits</h3><ul>{r3notes.get('limits_html','')}
<li>Most per-study facts come from abstracts plus GWAS Catalog records; full texts read for Deelen 2019, Timmers 2019/2020, Joshi 2017 and the mouse papers. Budovsky 2013 full text not accessible.</li>
<li>GWAS Catalog queried for 6–8 trait IDs without child-term expansion; the ~150 genome-wide-rsID figure is provisional.</li>
<li>bioRxiv listing partial (49,792 of 130,451 records); medRxiv complete.</li>
<li>Open Genes and HALL data licences unverified (sites blocked in the sandbox).</li>
<li>Seed tiers are a mechanical consensus; single-track A calls need curator confirmation.</li></ul>
<h3>Key PMIDs (title-verified 2026-11-03)</h3><div class="tw"><table class="tbl"><thead><tr><th>Paper</th><th>Journal</th><th>Title</th></tr></thead><tbody>{crow}</tbody></table></div>""")

# ---------------- page
nav = "".join(f'<button class="tb{" on" if i == 0 else ""}" onclick="show(\'{k}\',this)">{H(t)}</button>' for i, (k, t, _) in enumerate(tabs))
secs = "".join(f'<section id="{k}" class="tab{" on" if i == 0 else ""}"><h2>{H(t)}</h2>{b}</section>' for i, (k, t, b) in enumerate(tabs))
CSS = """
body{font-family:'DejaVu Sans',Helvetica,Arial,sans-serif;margin:0;color:#222;background:#fafafa}
header{background:#0b3d5c;color:#fff;padding:18px 28px}header h1{margin:0;font-size:22px}header p{margin:6px 0 0;font-size:13px;opacity:.85}
nav{display:flex;flex-wrap:wrap;gap:4px;padding:10px 28px;background:#e9eef2;position:sticky;top:0;z-index:5}
.tb{border:1px solid #b8c6d0;background:#fff;padding:7px 12px;border-radius:6px;cursor:pointer;font-size:13px}.tb.on{background:#0072B2;color:#fff;border-color:#0072B2}
main{padding:18px 28px;max-width:1500px}.tab{display:none}.tab.on{display:block}h2{margin-top:0;color:#0b3d5c}h3{color:#0b3d5c;margin:18px 0 8px}
.lead{font-size:15px}img{max-width:100%;border:1px solid #ddd;border-radius:6px;background:#fff}img.wide{width:100%}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:14px 0}.grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}
.card{background:#fff;border:2px solid #ddd;border-radius:8px;padding:10px 16px}.card.never{border-color:#D55E00}.card.never h3{color:#D55E00}
.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:12px 0}.kpi{background:#fff;border-left:5px solid #D55E00;padding:10px 14px;border-radius:4px}
.kpi b{display:block;font-size:22px;color:#222}.kpi span{font-size:13px;color:#444}
.tw{overflow-x:auto;margin:10px 0}.tbl{border-collapse:collapse;font-size:12.5px;background:#fff;width:100%}.tbl th{background:#e9eef2;text-align:left;position:sticky;top:0}
.tbl td,.tbl th{border:1px solid #dde3e8;padding:5px 7px;vertical-align:top}.cmp td:first-child{width:14%}.cmp td{width:43%}
.ladder .rung{padding:10px 14px;margin:6px 0;border-radius:6px}.rung b{display:block;font-size:15px}.rung span{font-size:13px}
.rung.a{background:#0072B2;color:#fff}.rung.b{background:#56B4E9}.rung.c{background:#d9d9d9}.rung.d{background:#f0f0f0;border:1px solid #ccc}
.note{font-size:12.5px;color:#555}.pending{background:#fff7e0;border-left:4px solid #E69F00;padding:8px 12px;font-size:13px}
.mgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.mcard{background:#fff;border:2px solid;border-radius:8px;overflow:hidden}
.mh{color:#fff;font-weight:bold;padding:6px 10px;font-size:13.5px}.mcard p{margin:8px 10px;font-size:13px}
.example{background:#fff;border:1px solid #ccc;border-radius:8px;padding:10px 16px;font-size:13.5px}.example div{margin:4px 0}
code{font-size:11.5px;background:#f2f2f2;padding:1px 3px}a.pm{color:#0072B2;text-decoration:none;border-bottom:1px dotted}
#flt{width:420px;padding:6px;margin:6px 10px 6px 0}.steps li{margin:5px 0}
"""
JS = """
function show(k,b){document.querySelectorAll('.tab').forEach(s=>s.classList.remove('on'));document.getElementById(k).classList.add('on');
document.querySelectorAll('.tb').forEach(x=>x.classList.remove('on'));b.classList.add('on');window.scrollTo(0,0);}
function filt(){const q=document.getElementById('flt').value.toLowerCase().replace('tier ','');const lo=document.getElementById('leads').checked;
document.querySelectorAll('#seedtbl tbody tr').forEach(r=>{const t=r.innerText.toLowerCase();const c=r.children;
const lead=c[4].innerText.trim()==='True';const tierHit=q.length===1&&c[2].innerText.trim().toLowerCase()===q;
r.style.display=((q===''||t.includes(q)||tierHit)&&(!lo||lead))?'':'none';});}
"""
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>longevitymap v2 research report</title><style>{CSS}</style></head><body>
<header><h1>longevitymap v2 — research report</h1><p>Evidence-tiered, mechanism-first longevity genetics for just-dna-lite · built 2026-11-03 · numbers from this session's audit and literature tracks; tier counts provisional until curation</p></header>
<nav>{nav}</nav><main>{secs}</main><script>{JS}</script></body></html>"""
open(OUT, "w").write(page)
print("wrote", OUT, round(len(page) / 1e6, 2), "MB;", len(tabs), "tabs; age:", age is not None, "defs:", defs is not None, "r3:", bool(r3notes))
