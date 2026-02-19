# CYP Drug Metabolism Panel — Agent Input (Freeform)

Create a pharmacogenomics panel for key Cytochrome P450 (CYP) enzymes that affect drug
metabolism. This is one of the most clinically actionable areas of genetics — CYP enzyme
activity directly determines how a patient metabolizes dozens of common medications.

## Key Genes & Variants

### CYP2C19 (clopidogrel, PPIs, SSRIs)
The most important pharmacogene. Determines clopidogrel (Plavix) activation.

- **rs4244285** — CYP2C19*2, splice defect, loss of function. Most common LOF allele
  globally (~15% in Europeans, ~30% in Asians). Homozygous = poor metabolizer (PM),
  heterozygous = intermediate metabolizer (IM). PMs have dramatically reduced clopidogrel
  efficacy and higher cardiovascular event rates.
- **rs4986893** — CYP2C19*3, premature stop codon, complete loss of function.
  Rare in Europeans (<1%) but ~5% in East Asians. Same clinical impact as *2.
- **rs12248560** — CYP2C19*17, gain-of-function promoter variant. Increases
  transcription ~2-fold. Homozygous = ultra-rapid metabolizer (UM). May cause
  subtherapeutic drug levels (drugs metabolized too fast) or increased activation
  of prodrugs. ~20% frequency in Europeans.

### CYP2D6 (codeine, tamoxifen, many psych meds)
Highly polymorphic. Metabolizes ~25% of all drugs.

- **rs3892097** — CYP2D6*4, splicing defect, non-functional. Most common null allele
  in Europeans (~20%). Homozygous = PM. Critical for codeine (no morphine conversion)
  and tamoxifen (no endoxifen conversion).

### CYP2C9 (warfarin, NSAIDs, phenytoin)
Determines warfarin dose requirements.

- **rs1799853** — CYP2C9*2, reduced function (~12% Europeans). *2/*2 homozygotes
  need ~20% lower warfarin dose.
- **rs1057910** — CYP2C9*3, severely reduced function (~7% Europeans). *3/*3
  homozygotes need ~50% lower warfarin dose. Most clinically significant CYP2C9 variant.

### CYP3A4 (statins, immunosuppressants, calcium channel blockers)
Metabolizes ~50% of all drugs, but fewer actionable common variants.

- **rs35599367** — CYP3A4*22, intron 6 variant reducing expression. ~5% Europeans.
  Associated with lower statin dose requirements and higher tacrolimus levels.

## Weighting Guidelines

- Loss-of-function (PM genotype): weight -1.0 to -1.5 (risk — altered drug response)
- Reduced function (IM genotype): weight -0.3 to -0.8
- Normal function: weight 0.0 (neutral)
- Gain-of-function (UM genotype): weight 0.5 to 1.0 (can be risk or protective depending
  on the drug — mark as "significant" rather than protective)

## Key Studies

- PMID 17622601 — CPIC guideline for CYP2C19 and clopidogrel
- PMID 21270786 — CPIC guideline for CYP2D6 and codeine
- PMID 27441996 — CPIC guideline for CYP2C9/VKORC1 and warfarin
- PMID 22992668 — CYP2C19*17 ultra-rapid metabolism clinical significance
- PMID 24458010 — CYP3A4*22 and statin dosing
