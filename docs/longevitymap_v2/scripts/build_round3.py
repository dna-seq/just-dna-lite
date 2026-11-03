"""Turn round-3 sub-agent outputs into round3/notes.json (HTML fragments) and the age-of-action chart."""
import base64, html, io, json
import pandas as pd
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
H = html.escape
BLUE, ORANGE, SKY, BGREEN, VERM, PURP, GREY = "#0072B2", "#E69F00", "#56B4E9", "#009E73", "#D55E00", "#CC79A7", "#888888"
mpl.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "xtick.labelsize": 9.5, "ytick.labelsize": 9.5})

LB, RB, KW = "{" * 2, "}" * 2, "artifact"
def art(vid, label): return f'<a href="{LB}{KW}:{vid}{RB}">{H(label)}</a>'
def tbl(df, maxlen=260):
    th = "".join(f"<th>{H(str(c))}</th>" for c in df.columns)
    tr = "".join("<tr>" + "".join(f"<td>{H(str(v))[:maxlen] if pd.notna(v) else ''}</td>" for v in r) + "</tr>" for r in df.itertuples(index=False))
    return f'<div class="tw"><table class="tbl"><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div>'

age = pd.read_csv("round3/age_of_action.csv")
bands = pd.read_csv("round3/age_bands.csv")
mo = pd.read_csv("round3/model_evidence.csv")
rare = pd.read_csv("round3/rare_candidates.csv")

# ---- age-band chart (Timmers 2019 fig 5 source data, IVW-pooled father/mother by the age track)
pick = [("APOE", PURP, "late: grows with age"), ("CHRNA3/5", ORANGE, "mid-life: fades"), ("CDKN2B-AS1", BLUE, "mid-life: fades"),
        ("LPA", SKY, "mid-life: fades"), ("ATXN2/BRAP", BGREEN, "lifelong: flat"), ("HLA-DQA1", GREY, "lifelong: flat")]
x = [0, 1, 2]; labs = ["40–60", "60–80", "80+"]
fig, ax = plt.subplots(figsize=(7.8, 4.4))
ends = []
for k, (loc, c, cls) in enumerate(pick):
    r = bands[bands.locus == loc].iloc[0]
    y = [r["b40-60"], r["b60-80"], r["b80+"]]; e = [1.96 * r["se40-60"], 1.96 * r["se60-80"], 1.96 * r["se80+"]]
    dx = (k - 2.5) * 0.035
    ax.errorbar([v + dx for v in x], y, yerr=e, color=c, marker="o", ms=6, lw=2, capsize=3)
    ends.append([y[2], 2 + dx, loc, c, cls])
ends.sort(key=lambda t: t[0])
gap = 0.0125
for i in range(1, len(ends)):                      # push labels apart, bottom-up
    if ends[i][0] - ends[i - 1][0] < gap: ends[i][0] = ends[i - 1][0] + gap
for ly, ex, loc, c, cls in ends:
    true_y = bands[bands.locus == loc].iloc[0]["b80+"]
    ax.annotate(f"{loc} ({cls})", xy=(ex, true_y), xytext=(2.25, ly), color=c, va="center", fontsize=9.5,
                arrowprops=dict(arrowstyle="-", color=c, lw=0.8))
ax.axhline(0, color="#999999", lw=0.8)
ax.set_xticks(x); ax.set_xticklabels(labs); ax.set_xlim(-0.2, 3.55)
ax.set_xlabel("parent's age band at death or censoring")
ax.set_ylabel("per-allele log protection ratio\n(lifespan-increasing allele)")
ax.set_title("APOE's effect grows with age; heart and smoking loci fade", loc="left", fontweight="bold")
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.text(0.01, -0.09, "Timmers 2019 (PMID 30642433) Fig. 5 source data, father/mother estimates pooled by inverse variance; bars 95% CI. "
         "Age-moderation P: APOE 2.2e-14; CHRNA3/5 2.1e-4; CDKN2B-AS1 5.2e-4; LPA 0.04; ATXN2/BRAP 0.91; HLA-DQA1 0.82.", fontsize=8.5, color="#444444", wrap=True)
fig.savefig("age_of_action_bands.png", dpi=150, bbox_inches="tight")
buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=150, bbox_inches="tight"); plt.close(fig)
chart = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

cls = age.age_of_action.value_counts().to_dict(); conf = age.confidence.value_counts().to_dict()
cls_txt = " · ".join(f"{k}: {v}" for k, v in cls.items()); conf_txt = " · ".join(f"{k}: {v}" for k, v in conf.items())
age_html = f"""<h3>Age of action</h3>
<p>Classes (40 loci, provisional): <b>{H(cls_txt)}</b>. Confidence: {H(conf_txt)}. No locus met AGE_INVERTING or EARLY_LIFE criteria.
Source: age track ({art('f059ef08-9bf4-4d89-ac2d-007db23ceabd','age_of_action.csv')}, {art('1a0dbf65-d864-49d6-a366-453a6f8bfea8','synthesis')}).
Parental-lifespan data censor late effects, so “mid-life” partly reflects that parents had to die for the effect to be seen.</p>
<img src="{chart}" alt="age bands">
<p class="note">Caveats from the track: allele labels in the source sheet do not always match the seed's pro-longevity allele (magnitudes shown in the lifespan-increasing direction; CDKN2B-AS1 orientation to be re-checked); three loci used unverified LD proxies; seven tier-B loci (TERT, IL6, IL6R, PCSK9, TCF7L2, IRF4, TYR) have no age-stratified lifespan data and are classed INFERRED or UNKNOWN.</p>
{tbl(age[['locus','rsid','seed_tier','age_of_action','confidence','report_phrase','evidence','pmid']], 300)}"""

mo_key = mo[mo.model_type.astype(str).str.contains("knock-in|humanised|humanized|QTL|allele", case=False, regex=True) | mo.matches_human_direction.astype(str).str.contains("no|discord", case=False)]
animal_html = f"""<h3>Allele-level and direction checks (model-organism re-run)</h3>
<ul>
<li><b>Almost no human longevity allele has been tested allele-specifically in mice with a lifespan endpoint.</b> The only knock-in found with lifespan data is PPARG Pro12Ala (Ala/Ala longer-lived on chow; benefit lost on a high-fat diet; PMID 19117549, title-verified by the track). Humanised Klotho variant knock-ins exist only as conference abstracts; no FOXO3 rs2802292, SIRT6 N308K/A313S or IGF1R A37T/R407H knock-in lifespan study was found.</li>
<li><b>Direction can disagree across species:</b> Igf1r+/- mice (female +33%) are concordant with reduced-function IGF1R alleles in female centenarians; GHR knockout extends mouse life, while human d3-GHR raises GH sensitivity and is male-specific (discordant); KL-VS is non-monotone in humans (heterozygote advantage) but monotone in mice.</li>
<li><b>Corrected count:</b> with NCBI orthologues, 22 of 272 v1 genes (45 rsIDs) have GenAge mouse lifespan entries (symbol matching gave 20); Open Genes adds to a union of 26 genes (51 rsIDs).</li>
<li><b>v1's KL rs1207362, IGF1R rs2229765 and SIRT6 rs107251 are not the functionally characterised alleles.</b> Candidates instead: KL-VS (rs9536314 + rs9527025, as a haplotype), d3-GHR tag rs6873545, BPIFB4 rs2070325 — identities to be verified at curation.</li>
<li>The SIRT6 centenarian-allele paper (Simon 2022) is in EMBO J (PMID 36215696), not Cell Reports as the brief said.</li></ul>
<p>Full table: {art('47ea52d0-e592-42af-93cc-084aaf013f21','model_evidence.csv (77 rows)')} · {art('5fad2890-4ac4-4e57-8488-434eb1a04397','synthesis')}</p>
{tbl(mo_key[['human_gene','human_rsid_if_any','model_organism','model_type','lifespan_effect','matches_human_direction','pmid']], 220)}"""

rc = rare[['rsid','gene','evidence_tier','mechanism','effect_measure','effect_size','phenotype','ancestry','pmid','genotypable_short_read_vcf','recommended_table_kind']].copy()
gene_level = rc.rsid.isna() & rc.evidence_tier.astype(str).str.startswith("A")
rc.loc[gene_level, "evidence_tier"] = "A* (gene-level burden: shortened survival; cross-reference only, not a pro-longevity tier)"
rc.loc[rc.gene.eq("TET2") & gene_level, "evidence_tier"] += "; likely somatic clonal haematopoiesis"
rare_html = f"""<ul>
<li><b>Centenarian sequencing is small and largely negative at variant level:</b> WES of 100 centenarians found no rare-variant or gene burden (PMID 29750252); WGS 81 vs 36 gave STK17A/COA1 plus a DNA-repair signal (PMID 33941312); ClinVar/HGMD pathogenic burden did not differ among 1,879 Ashkenazi centenarians, offspring and controls (PMID 32860726).</li>
<li><b>APOE is the only replicated direct-lifespan locus at this level</b> (28,297 participants, 7 studies; PMID 30060062). FOXO3 rs2802292 is meta-analytically significant in men but null in Japanese and Italian samples; d3-GHR rises with age in 3 of 4 cohorts (men); CLEC3B rs13963 is East Asian-only; KL-VS acts as an Alzheimer's-risk modifier in APOE4 carriers.</li>
<li><b>Lipid loss-of-function (PCSK9, APOC3, ANGPTL3, ASGR1)</b> protects against coronary disease (e.g. ANGPTL3 OR 0.59; APOC3 LoF −41% ischaemic vascular disease), but lifespan evidence is Mendelian randomisation only (PMID 38082436). APOE3-Christchurch and RELN-COLBOS delay Alzheimer's onset in single kindreds.</li>
<li><b>Pathogenic carriage shortens life:</b> UK Biobank ACMG SF v3.2 P/LP carriers (3.4%) have all-cause mortality HR 1.42 (women) / 1.31 (men); PTV burden HR BRCA2 2.57, BRCA1 2.36, TET2 1.76, ATM 1.65. No “years lost” figure was found.</li>
<li><b>Germline clonal-haematopoiesis loci</b> (TERT, TCL1A) act indirectly; CHIP itself carries all-cause mortality HR 1.34 (meta-analysis) and is not callable from a germline VCF. mtDNA haplogroup evidence is weak and unreplicated.</li>
<li>ADARB1/2 (18 v1 rsIDs) have no replication since 2015 → tier C.</li></ul>
<p class="note">In the table below, the track's tier A for gene-level BRCA1/BRCA2/ATM/TET2 rows is shown as A*: robust evidence that rare damaging variants <i>shorten</i> survival (UK Biobank burden), routed to the clinical modules; APOE remains the only tier-A pro-longevity locus here. Effect sizes from abstracts or open-access text; several rsIDs taken from dbSNP after verifying gene and protein change; counts provisional. {art('278dc19f-acf4-4210-becb-c466ff17356b','synthesis')} · {art('dd7e170f-8a1e-4d98-a445-c73fb016b1c4','evidence')} · {art('5fd939f7-d648-4f49-b739-0c49953fd671','candidates (50)')}</p>
{tbl(rc, 200)}"""

limits_html = ("<li>Rare-variant and mouse tracks were stopped by a content-safety filter on the first model and completed on a re-run with Sonnet 5.5, with the original briefs unchanged.</li>"
               "<li>Age of action: no genome-wide age-varying-hazard lifespan GWAS exists; classes rest on Timmers 2019/2020 age bands and inference from mediating disease; provisional.</li>"
               "<li>Mouse: GenAge-only rows lack paper-verified PMIDs; worm/fly matches symbol-only; positional synteny of mouse QTL with human loci not done.</li>")
tracks = [("C: rare and protective variants (Sonnet 5.5 re-run)", "278dc19f-acf4-4210-becb-c466ff17356b", "dd7e170f-8a1e-4d98-a445-c73fb016b1c4", "5fd939f7-d648-4f49-b739-0c49953fd671"),
          ("J: mouse and model-organism validation (Sonnet 5.5 re-run)", "5fad2890-4ac4-4e57-8488-434eb1a04397", "0a13dbe0-35a1-4fad-8038-9a2c36cd8913", "47ea52d0-e592-42af-93cc-084aaf013f21"),
          ("K: definitions of pro-longevity and age of action", "1a0dbf65-d864-49d6-a366-453a6f8bfea8", "4ab4848c-3c43-48d0-b634-4bf05cc61510", "f059ef08-9bf4-4d89-ac2d-007db23ceabd")]
json.dump(dict(age_summary_html=age_html, animal_html=animal_html, rare_html=rare_html, limits_html=limits_html, tracks=tracks), open("round3/notes.json", "w"))
print("classes", cls, "| confidence", conf)
