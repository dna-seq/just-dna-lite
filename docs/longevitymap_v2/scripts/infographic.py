import matplotlib as mpl, matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import sys
OUT = sys.argv[1] if len(sys.argv) > 1 else "longevitymap_v2_infographic"
S_BASE, S_ANN, S_TICK = 12, 10.5, 9.5          # role ladder (titles/labels, annotations, ticks)
mpl.rcParams.update({"font.family": "DejaVu Sans", "font.size": S_BASE, "axes.titlesize": S_BASE,
    "axes.labelsize": S_BASE, "xtick.labelsize": S_TICK, "ytick.labelsize": S_TICK, "svg.fonttype": "none"})
# Okabe-Ito (CVD-safe); no red/green opposition anywhere
BLUE, ORANGE, SKY, BGREEN, VERM, PURP, YEL, GREY, DARK = "#0072B2", "#E69F00", "#56B4E9", "#009E73", "#D55E00", "#CC79A7", "#F0E442", "#BBBBBB", "#222222"
fig = plt.figure(figsize=(17, 12.2), dpi=150)
gs = fig.add_gridspec(3, 3, height_ratios=[1.0, 1.08, 0.50], width_ratios=[1.12, 1.0, 1.0],
                      left=0.035, right=0.985, top=0.865, bottom=0.03, hspace=0.36, wspace=0.17)
fig.text(0.035, 0.968, "longevitymap v2: from a frozen candidate-gene list to evidence-tiered, mechanism-first longevity genetics",
         fontsize=15, fontweight="bold", color=DARK, va="center")
fig.text(0.035, 0.937, "Requirements summary, 2026-11-03. Numbers come from the v1 audit and the literature tracks; GWAS-coverage and tier counts are provisional until curation.",
         fontsize=S_ANN, color="#444444", va="center")
def letter(ax, l):
    ax.text(-0.02, 1.06, l, transform=ax.transAxes, fontsize=14, fontweight="bold", va="bottom", ha="right")
def box(ax, x, y, w, h, fc, ec="none", lw=0, r=0.012):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=lw, transform=ax.transAxes, clip_on=False))

# ---- a: v1 audit as part-of-whole bars
ax = fig.add_subplot(gs[0, 0]); letter(ax, "a")
items = [("rsIDs resting on one 2012 classifier (retracted lineage)", 280, 516, VERM),
         ("genotype rows labelled 'protective'", 975, 1022, VERM),
         ("rsIDs with ≥2 independent significant studies", 35, 528, BLUE),
         ("genome-wide longevity rsIDs already in v1 (provisional)", 7, 150, BLUE),
         ("distinct conclusion texts across all rows", 79, 1022, BLUE)]
ax.set_xlim(0, 1); ax.set_ylim(-0.75, len(items) - 0.4); ax.invert_yaxis(); ax.axis("off")
for i, (lab, k, n, c) in enumerate(items):
    ax.text(0, i - 0.30, lab, fontsize=S_ANN, va="bottom", ha="left", color=DARK)
    ax.barh(i + 0.05, 1.0, height=0.26, color="#E8E8E8", left=0)
    ax.barh(i + 0.05, k / n, height=0.26, color=c, left=0)
    ax.text(1.0, i - 0.30, f"{k:,} of {n:,}", fontsize=S_ANN, va="bottom", ha="right", color=DARK, fontweight="bold")
ax.set_title("v1 rests on one overfit study and misses modern loci", loc="left", fontweight="bold", pad=14)

# ---- b: evidence tier ladder
ax = fig.add_subplot(gs[0, 1]); letter(ax, "b"); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
ax.set_title("One tier gates scoring and default visibility", loc="left", fontweight="bold", pad=14)
tiers = [("A", "Well established", "genome-wide in ≥100k lives or ≥3k cases\nabove the 90th percentile; replicated", "11 lead loci", BLUE, "white"),
         ("B", "Likely", "genome-wide locus, but one study, a tag SNP,\nor ancestry-specific replication only", "82, to prune", SKY, DARK),
         ("C", "Early evidence", "suggestive, small replication or preprint;\nresearch view only", "39", "#D9D9D9", DARK),
         ("D", "Not supported", "candidate-only, contradicted, meta-null,\nretracted or overfit source (v1 legacy)", "1 + v1 legacy", "#F2F2F2", DARK)]
y = 0.98
for t, word, crit, cnt, fc, tc in tiers:
    h = 0.205; y -= h + 0.014
    box(ax, 0.0, y, 1.0, h, fc)
    ax.text(0.03, y + h / 2, t, fontsize=20, fontweight="bold", color=tc, va="center", transform=ax.transAxes)
    ax.text(0.13, y + h - 0.028, word, fontsize=S_BASE, fontweight="bold", color=tc, va="top", transform=ax.transAxes)
    ax.text(0.13, y + 0.014, crit, fontsize=S_TICK, color=tc, va="bottom", transform=ax.transAxes, linespacing=1.15)
    ax.text(0.97, y + h - 0.028, cnt, fontsize=S_ANN, color=tc, va="top", ha="right", transform=ax.transAxes, fontweight="bold")
ax.text(0.0, -0.07, "Reported separately, never folded into the tier: mechanism,\npleiotropy, age of action, outcome (healthspan / lifespan / very old\nage), actionability, context, causal confidence, animal support.",
        fontsize=S_TICK, color="#444444", va="bottom", transform=ax.transAxes, linespacing=1.2)

# ---- c: genetics vs lifestyle, heritability
gc = gs[0, 2].subgridspec(3, 1, height_ratios=[1, 1, 1.1], hspace=1.05)
ax1 = fig.add_subplot(gc[0]); letter(ax1, "c")
ax1.set_title("Lifestyle outweighs inherited polygenic risk", loc="left", fontweight="bold", pad=10)
for yy, lab, v, c in [(1, "unfavourable vs favourable lifestyle", 1.78, ORANGE), (0, "short- vs long-lifespan polygenic score", 1.21, BLUE)]:
    ax1.plot([1, v], [yy, yy], color=c, lw=2.5); ax1.plot(v, yy, "o", color=c, ms=9)
    ax1.text(v + 0.04, yy, f"HR {v}", va="center", fontsize=S_ANN, fontweight="bold", color=c)
    ax1.text(1.0, yy + 0.32, lab, va="bottom", fontsize=S_TICK, color=DARK)
ax1.axvline(1, color="#888888", lw=1); ax1.set_xlim(0.95, 2.15); ax1.set_ylim(-0.4, 1.75); ax1.set_yticks([])
ax1.set_xlabel("mortality hazard ratio (UK Biobank, Bian 2024)", fontsize=S_TICK)
for s in ("top", "right", "left"): ax1.spines[s].set_visible(False)
ax2 = fig.add_subplot(gc[1])
for yy, lab, v, txt, c in [(1.4, "exposome (25 factors)", 17, "+17 pp", ORANGE), (0, "polygenic scores for 22 diseases", 2, "<2 pp", BLUE)]:
    ax2.barh(yy, v, height=0.42, color=c); ax2.text(v + 0.4, yy, txt, va="center", fontsize=S_ANN, fontweight="bold", color=c)
    ax2.text(0, yy + 0.30, lab, va="bottom", fontsize=S_TICK, color=DARK)
ax2.set_xlim(0, 21); ax2.set_ylim(-0.45, 2.15); ax2.set_yticks([])
ax2.set_xlabel("extra mortality variance explained (Argentieri 2025)", fontsize=S_TICK)
for s in ("top", "right", "left"): ax2.spines[s].set_visible(False)
ax3 = fig.add_subplot(gc[2])
ax3.set_title("Lifespan heritability depends on the estimand", loc="left", fontsize=S_ANN, fontweight="bold", pad=6)
H = [(2, "pedigrees, mating corrected", 0, 10, "<10%", BLUE, False),
     (1, "large family trees", 12, 16, "12–16%", BLUE, False),
     (0, "intrinsic (contested)", 45, 55, "~50%", PURP, True)]
for yy, lab, lo, hi, txt, c, hatch in H:
    ax3.barh(yy, hi - lo, left=lo, height=0.5, color=c, alpha=0.85 if not hatch else 0.45, hatch="//" if hatch else None, edgecolor=c)
    if hatch:
        ax3.text(lo - 1.5, yy, f"{lab} · {txt}", va="center", ha="right", fontsize=S_TICK, color=DARK)
    else:
        ax3.text(hi + 1.5, yy, f"{txt} · {lab}", va="center", fontsize=S_TICK, color=DARK)
ax3.set_xlim(0, 100); ax3.set_ylim(-0.6, 2.6); ax3.set_yticks([]); ax3.set_xticks([0, 25, 50, 75, 100]); ax3.set_xticklabels(["0", "25", "50", "75", "100%"])
for s in ("top", "right", "left"): ax3.spines[s].set_visible(False)

# ---- d: mechanism-first map
ax = fig.add_subplot(gs[1, 0:2]); letter(ax, "d"); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
ax.set_title("Variants are grouped by how they act, because most lifespan signal runs through a disease or behaviour", loc="left", fontweight="bold", pad=14)
tiles = [("Heart and vessels", "LPA · LDLR · 9p21 region\nCELSR2/SORT1 · PCSK9", "preventable: a doctor can\nmeasure Lp(a), LDL-C, BP", BLUE),
         ("Brain and memory", "APOE ε2 / ε3 / ε4 ★\nscored once, as a pair", "descriptive; opt-in, Alzheimer's\nimplication stated plainly", PURP),
         ("Smoking and lungs", "CHRNA3/5\n(nicotine receptor genes)", "modifiable: the behaviour,\nnot the variant, can change", ORANGE),
         ("Immune system", "HLA-DQA1/DRB1 · SH2B3 ⇄\nIL6R · IL6 (Chinese cohorts)", "trade-offs: less autoimmunity\nand CVD, more cancer/infection", BGREEN),
         ("Blood sugar and weight", "TCF7L2\nFTO / MC4R (via BMI)", "modifiable: weight and glucose\nare measurable, changeable", YEL),
         ("Skin and sun", "IRF4 · TYR · DEF8\n(pigmentation; healthspan)", "modifiable: acts through skin\ncancer; sun protection", SKY),
         ("Ageing in general", "FOXO3 · ZW10/USP28\nFGD6 ★ · HTT ★", "descriptive: no single disease\nroute (FURIN, KCNK3 pending)", "#777777"),
         ("Ageing markers", "TERT ★ / TERC · clocks\nloss of Y · mtDNA copies", "not scored: a marker tendency,\nnot a longer-life allele", "#AAAAAA")]
cols, rows = 4, 2; W, Hh, gx, gy = 0.235, 0.40, 0.02, 0.06
for k, (head, loci, note, c) in enumerate(tiles):
    r, cc = divmod(k, cols); x = cc * (W + gx); y0 = 0.93 - (r + 1) * Hh - r * gy
    box(ax, x, y0, W, Hh, "#FAFAFA", ec=c, lw=2.2)
    box(ax, x, y0 + Hh - 0.075, W, 0.075, c)
    tc = "white" if c in (BLUE, PURP, BGREEN, "#777777") else DARK
    ax.text(x + 0.012, y0 + Hh - 0.0375, head, fontsize=S_ANN, fontweight="bold", color=tc, va="center", transform=ax.transAxes)
    ax.text(x + 0.012, y0 + Hh - 0.10, loci, fontsize=S_ANN, color=DARK, va="top", transform=ax.transAxes, linespacing=1.3)
    ax.text(x + 0.012, y0 + 0.025, note, fontsize=S_TICK, color="#333333", va="bottom", transform=ax.transAxes, linespacing=1.25)
ax.text(0.0, -0.02, "★ also supported in animal studies (context only; never raises a tier)    ⇄ trade-off: shown as 'may lower / may raise', never as a good/bad colour    Examples are seed leads",
        fontsize=S_TICK, color="#444444", va="bottom", transform=ax.transAxes)

# ---- e: three readers
ax = fig.add_subplot(gs[1, 2]); letter(ax, "e"); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
ax.set_title("One report, three layers of detail", loc="left", fontweight="bold", pad=14)
layers = [("Citizen scientist (default view)", "• the result in plain words, about you\n• copies of the longer-life version (0, 1, 2)\n• certainty word, what it acts through\n• 'may lower / may raise' for trade-offs\n• what a doctor can measure instead\n• ancestry caveat when it applies", ORANGE),
          ("Geneticist (More details fold)", "• rsID, GRCh38 position, ref/alt, zygosity\n• effect allele, effect size + unit, CI, p\n• phenotype class, cohort N and ancestry\n• fine-mapping and effector-gene confidence", BLUE),
          ("Ageing researcher (research view)", "• tiers C/D, negative and contradicted evidence\n• legacy LongevityMap rows (frozen 2017)\n• full pleiotropy list, hallmark tags\n• animal-model support", PURP)]
y = 1.0
for head, body, c in layers:
    n = body.count("\n") + 1; h = 0.08 + n * 0.051; y -= h + 0.02
    box(ax, 0, y, 1, h, "#FAFAFA", ec=c, lw=2.2)
    ax.text(0.03, y + h - 0.02, head, fontsize=S_ANN, fontweight="bold", color=c, va="top", transform=ax.transAxes)
    ax.text(0.03, y + h - 0.068, body, fontsize=S_TICK, color=DARK, va="top", transform=ax.transAxes, linespacing=1.32)

# ---- f: principles and never-do
ax = fig.add_subplot(gs[2, :]); letter(ax, "f"); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
ax.set_title("Key principles", loc="left", fontweight="bold", pad=8)
P = ["1  Evidence first: only genome-wide, replicated signals are scored; everything else is research view.",
     "2  One lead variant per locus; LD proxies and APOE-region tags are never counted twice.",
     "3  A lead SNP 'marks a region' unless fine-mapping makes it likely causal; name the gene only when confident.",
     "4  Say what it acts through, at what age, and on healthy years or length of life; state trade-offs both ways.",
     "5  Every genotype gets a row; the most common genotype is the neutral reference.",
     "6  Ancestry, sex and age limits travel with the finding; no transfer of European effects to other ancestries.",
     "7  Every claim has a receipt: PMID, effect allele, effect size with unit, and a located quote."]
N = ["No summed 'longevity score' or net weight from single SNPs",
     "No predicted lifespan or genotype-based 'biological age'",
     "No red/green good-bad colouring, least of all on trade-offs",
     "No odds ratios for citizens without plain-language context",
     "No 'gene that controls ageing' wording",
     "No animal result raising a human tier or weight"]
for i, p in enumerate(P):
    ax.text(0.0, 0.88 - i * 0.135, p, fontsize=S_TICK, color=DARK, va="top", transform=ax.transAxes)
box(ax, 0.645, 0.0, 0.355, 0.95, "#F4F4F4", ec=VERM, lw=1.8)
ax.text(0.66, 0.89, "Never", fontsize=S_ANN, fontweight="bold", color=VERM, va="top", transform=ax.transAxes)
for i, t in enumerate(N):
    ax.text(0.66, 0.75 - i * 0.12, "✕  " + t, fontsize=S_TICK, color=DARK, va="top", transform=ax.transAxes)

fig.savefig(OUT + ".png", dpi=150); fig.savefig(OUT + ".pdf")
# §9.1 bbox check
r = fig.canvas.get_renderer()
texts = [(t, t.get_window_extent(r)) for t in fig.findobj(mpl.text.Text) if t.get_text().strip() and t.get_visible()]
fb = fig.bbox
over = [(a.get_text()[:40], b.get_text()[:40]) for i, (a, ba) in enumerate(texts) for b, bb in texts[i + 1:] if ba.overlaps(bb)]
outside = [t.get_text()[:40] for t, bt in texts if bt.x0 < fb.x0 - 1 or bt.x1 > fb.x1 + 1 or bt.y0 < fb.y0 - 1 or bt.y1 > fb.y1 + 1]
print("overlaps:", over); print("outside:", outside)
