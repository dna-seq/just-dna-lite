# MTHFR & NAD+ Metabolism Panel — Agent Input (Freeform)

Build an annotation module covering methylation cycle and NAD+ biosynthesis genetics.
These pathways are deeply intertwined — folate metabolism feeds one-carbon units into
methylation reactions, while NAD+ is essential for sirtuin-mediated epigenetic regulation
and DNA repair. Both decline with age.

## Methylation / Folate Cycle

### MTHFR — Methylenetetrahydrofolate Reductase
The rate-limiting enzyme in folate metabolism. Converts 5,10-methyleneTHF to 5-methylTHF,
the primary methyl donor for homocysteine → methionine conversion.

- **rs1801133** (C677T): The most studied nutrigenomic variant. T allele reduces enzyme
  thermostability. TT genotype retains only ~30% of normal activity at 37°C. Associated
  with elevated homocysteine (especially with low folate intake), neural tube defect risk,
  and cardiovascular disease. Frequency: T allele ~25-35% in Europeans, up to 50% in
  some Mexican/Italian populations. Protective: responds well to methylfolate supplementation.

- **rs1801131** (A1298C): Second MTHFR variant. C allele reduces activity but less severely
  than C677T. CC homozygotes have ~60% of normal activity. Compound heterozygotes
  (677CT + 1298AC) have clinically similar profiles to 677TT. Less well-studied independently.

### MTR — Methionine Synthase (5-methylTHF → THF + methionine)
- **rs1805087** (A2756G): G allele associated with lower enzyme activity and altered
  methionine/homocysteine balance. GG genotype may increase neural tube defect risk.
  Interacts with MTHFR and B12 status.

### MTRR — Methionine Synthase Reductase (reactivates MTR)
- **rs1801394** (A66G): G allele reduces reductase activity. GG genotype impairs
  MTR regeneration. Combined with MTR and MTHFR variants, compounds methylation deficiency.

### COMT — Catechol-O-Methyltransferase
- **rs4680** (Val158Met): A→G substitution. Met/Met (A/A) = slow COMT, higher
  catecholamine and estrogen levels, better prefrontal cognition but higher anxiety.
  Val/Val (G/G) = fast COMT, lower catecholamines, stress resilience but lower
  working memory. The "worrier vs warrior" gene. Direct SAM consumer — links to
  methylation capacity.

## NAD+ Pathway

NAD+ is a critical coenzyme for sirtuins (SIRT1-7), PARPs, and CD38. Levels decline
~50% between ages 40-60. Genetic variants affecting NAD+ biosynthesis or consumption
influence aging rate.

### NAMPT — Nicotinamide Phosphoribosyltransferase
Rate-limiting enzyme in the NAD+ salvage pathway (the primary NAD+ source in mammals).

- **rs61330082**: Promoter variant affecting NAMPT expression. T allele associated with
  lower circulating visfatin/NAMPT levels and reduced NAD+ salvage capacity.

### SIRT1 — Sirtuin 1
NAD+-dependent deacetylase. Master regulator of aging, inflammation, and metabolism.

- **rs7895833** (A/G in promoter): G allele associated with reduced SIRT1 expression.
  GG genotype linked to increased visceral fat, insulin resistance, and cardiovascular
  risk in multiple cohorts. The A allele is protective.

### NADSYN1 — NAD Synthetase 1
Final step of de novo NAD+ synthesis (from tryptophan pathway).

- **rs3741534**: Variant affecting enzyme efficiency. Associated with circulating NAD+
  levels in GWAS. Minor allele linked to lower NAD+ in blood metabolomics studies.

## Weighting Philosophy

For methylation variants: negative weights for reduced function (higher homocysteine risk),
but note these are highly modifiable by supplementation — conclusions should mention
methylfolate/B12/riboflavin interventions.

For NAD+ variants: negative weights for reduced NAD+ capacity, with conclusions mentioning
NMN/NR supplementation as potential interventions.

COMT is unique — neither allele is strictly "bad." Use weight 0 for both homozygotes
with descriptive conclusions, slight negative for Met/Met (anxiety risk) since this is
a health panel.

## Key References

- PMID 9545397 — Original MTHFR C677T thermolability study (Frosst et al.)
- PMID 21732829 — MTHFR and neural tube defects meta-analysis
- PMID 17913843 — COMT Val158Met and cognition/anxiety meta-analysis
- PMID 22139851 — NAMPT/visfatin genetics and metabolic syndrome
- PMID 23435088 — SIRT1 rs7895833 and cardiovascular risk
- PMID 31467085 — NAD+ decline with aging, review
