# Understanding What Your Genome Can and Cannot Tell You

> **⚠️ MEDICAL DISCLAIMER:** The information provided in this document and by the just-dna-lite software is for educational, citizen science, and research purposes only. It is **not** medical advice, and the software is **not** a diagnostic tool. Never make health or medical decisions based on the output of this tool. Always consult a qualified healthcare professional or genetic counselor for clinical interpretation of your genomic data.

This tool is a research instrument. It is not a diagnostic device. That distinction matters enormously, and this page exists to make sure you understand *why* — not because of legal caution, but because the biology genuinely demands it.

---

## What "heritability" actually means (and why it misleads almost everyone)

When scientists say a trait is "60% heritable," most people hear "60% determined by your genes." That is wrong in a subtle but important way.

Heritability is a population-level statistic. It measures how much of the *variation* in a trait across a specific population, studied at a specific time, in a specific environment, can be attributed to genetic differences *between individuals in that group*. It says nothing about any single person. It says nothing about how much the environment matters in absolute terms.

A toy example: if everyone in a study ate the exact same diet, then dietary differences contribute zero variance to, say, body weight. Genetic differences now explain a large fraction of the remaining variance — not because diet doesn't matter to body weight (it obviously does), but because diet variance was removed from the equation. Heritability estimates are entirely contingent on the population and environment in which the study was done.

This means a high-heritability trait can still be profoundly environmental and vice versa. Height is about 80% heritable in wealthy countries. In populations experiencing childhood malnutrition, that number drops substantially. The genes didn't change. The environment did.

The practical consequence: a high PRS for a complex trait does not mean "your genes doom you." It means the alleles you carry are statistically associated with higher risk in the populations studied.

One more thing worth knowing: this tool doesn't display heritability estimates alongside most findings. That means when you see a variant flagged as risky, you won't automatically know how heritable the underlying trait is. For anything that concerns you, look it up. A scary-sounding variant tied to a trait with low heritability means genetic factors explain very little of who actually gets it. And carrying a risk variant without the phenotype manifesting is common — many variants have low penetrance, meaning most carriers never develop the condition at all.

---

## What polygenic risk scores are

A polygenic risk score is a weighted sum. You take a list of genetic variants — typically single-nucleotide polymorphisms (SNPs) pulled from genome-wide association studies — assign each one a weight based on its effect size in some study, and add up the values across your genome. The result is a number.

That number is not a probability. It is not a diagnosis. It is a rank: where you fall in a distribution relative to some reference population.

The model is linear. Real biology almost never is. There are gene–gene interactions (epistasis), gene–environment interactions, feedback loops, developmental windows, and compensatory mechanisms that a linear weighted sum cannot capture. The score also assumes that the effect sizes measured in the original study translate cleanly to your genome — which requires that your ancestry, the allele frequencies in your background, and the linkage disequilibrium structure (which SNPs are correlated with which) all match the study population. For most PGS Catalog scores, that population is European. If your ancestry is East African, South Asian, or admixed, the score's predictive power for *you* degrades, sometimes substantially.

The PGS Catalog has over 5,000 scores covering everything from height to Alzheimer's risk to educational attainment. Most of them explain only a few percent of variance in their trait. A few of them — for highly polygenic, well-studied traits in well-matched populations — do meaningfully better. But even the good ones produce wide distributions of outcomes at any given score value. Someone at the 90th percentile for a disease PRS does not have that disease. Many people at the 10th percentile do.

---

## The difference between science-grade and clinical-grade evidence

Clinical-grade evidence requires a different standard than research-grade association.

For a genetic test to be used clinically, someone has to demonstrate — in well-designed prospective studies — that knowing the result changes patient outcomes. It has to work across diverse populations. The measurement has to be reproducible under routine laboratory conditions. The downstream management pathway has to be defined. And the benefits have to outweigh the harms across the population of people who would get the test.

Very little of genomics has cleared that bar. The exceptions are real and important: BRCA1/2 pathogenic variants genuinely predict high lifetime breast and ovarian cancer risk. Pharmacogenomic variants for drug metabolism (CYP2C19, HLA-B*57:01, etc.) have direct clinical applications with strong evidence. Monogenic conditions — Huntington's, cystic fibrosis, familial hypercholesterolemia — are deterministic or near-deterministic. For these, the science and the clinical utility converge.

But that's a short list. Most complex trait polygenic scores — cardiovascular risk, metabolic traits, psychiatric conditions, longevity — are science-grade at best. They tell you something real about population-level distributions. They do not tell you what will happen to you.

The annotation modules in this tool are in the same category. They are built from published research. The variants are real. The effect sizes are from real studies. But most of them were found in a GWAS, which finds statistical associations, not mechanisms. Many GWAS hits are tagging variants — they are statistically correlated with a causal variant nearby but are not themselves causal. If the population you studied had a different LD structure, the "hit" might not replicate at all.

---

## Why acting fast on a scary (or exciting) genetic finding is usually a mistake

Say you compute a PRS for cardiovascular disease and you're in the 92nd percentile. Or you find a variant that some annotation module flags as associated with a longevity phenotype. What should you do?

The honest answer: probably nothing immediately, and certainly nothing drastic.

Here is why the "scary finding" case deserves more scrutiny than it gets:

**The base rate problem.** If a PRS flags the top 10% of the population as "high risk," that's tens of millions of people. Most of them will not develop the condition. The positive predictive value of a high score depends heavily on how common the condition is in the first place. For a disease with 5% lifetime prevalence, even a very good risk stratification model will produce many false positives.

**Publication bias bakes in overestimation.** Effect sizes from GWAS consistently shrink when replicated in independent cohorts. This "winner's curse" means the weights in PRS models tend to be inflated. Scores computed from those weights overestimate the true genetic contribution.

**Your specific variant context matters.** Two people can have the same PRS but very different variant architectures: one person has many small-effect common variants, another has one large-effect rare variant plus a protective background. The linear sum is the same; the biology is different.

**Modifiable factors swamp genetics for most traits.** For the top causes of premature mortality — cardiovascular disease, type 2 diabetes, some cancers — the effect sizes for smoking, physical activity, diet, and sleep dwarf the effect sizes of any common genetic variant. Knowing your PRS for cardiovascular disease while ignoring whether you smoke is like fine-tuning an antenna while your house is on fire.

The "exciting finding" case has its own trap. If you find a variant associated with longevity or above-average VO2 max capacity, it is tempting to treat that as permission to relax on the lifestyle side. That is also backwards. Most longevity-associated variants have effect sizes in the single-digit percentage range. They shift distributions. They do not guarantee outcomes.

---

## What actually is deterministic (a short and honest list)

A small number of genetic findings are genuinely high-confidence and actionable:

- **Monogenic diseases with Mendelian inheritance.** One broken copy (dominant) or two broken copies (recessive) of a gene causes a specific disease with very high penetrance. Examples: Huntington's disease (HTT repeat expansion), familial hypercholesterolemia (LDLR, APOB, PCSK9 pathogenic variants), hereditary BRCA1/2 breast/ovarian cancer, Lynch syndrome (mismatch repair genes). These are genuinely deterministic or near-deterministic. They are also rare.

- **Pharmacogenomics with established clinical variants.** CYP2C19 loss-of-function affects clopidogrel activation. HLA-B*57:01 predicts abacavir hypersensitivity with near-100% negative predictive value. These have direct clinical implications and should ideally be handled in context with a physician who knows what to do with the result.

- **High-penetrance rare variants in well-characterized genes.** There is a growing list of rare pathogenic variants in genes like APOE (ε4ε4 for Alzheimer's), TTR (hereditary amyloidosis), and others where the biology is well understood even if the penetrance is not 100%.

Everything outside this category — the vast majority of what a genomic tool like this will surface — is associative, probabilistic, population-level, and heavily context-dependent.

---

## How to actually use this tool

Browse your genome. Notice patterns. Follow up on specific findings in the primary literature. Cross-reference with Ensembl ClinVar annotations to see whether a variant has clinical evidence. Understand that a "pathogenic" label in ClinVar is assigned by submitters and has its own quality tiers — a single submitter with no review is not the same as a reviewed expert panel classification.

Use the PRS results to understand your relative position in a distribution, not to predict your future. If you are at the 85th percentile for a disease risk score, that is interesting population-level information. It is not a sentence.

Dig into the modules that interest you. Look at the original papers. Check the GWAS catalog. Check whether the findings replicated. Check how much variance the score explains. Ask whether the study population matches your ancestry.

This is what research-level genomics looks like: iterative, uncertain, dependent on context, and genuinely informative if you take the time to understand what the numbers actually mean.

The reason to use this tool is not to get answers. It is to ask better questions.
