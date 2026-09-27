# Secretor status (FUT2)

Most people's saliva and other body fluids carry their blood group sugars — the same tags that decide
the ABO blood group. People whose fluids carry them are called secretors. The FUT2 gene makes those
sugars in the cells lining the mouth, gut and other moist surfaces, so it decides whether they appear
in body fluids; the sugars on red blood cells are put there by a different gene, FUT1, whatever a
person's secretor status is. This module reads FUT2 from your DNA file and reports one of three
results: **Secretor**, **Weak secretor** or **Non-secretor**. If your file does not cover the gene
well enough, it says so instead of guessing.

Secretor status is not a disease and nothing about it needs treating. It does change which gut
viruses can get a grip: non-secretors are largely protected against the most common noroviruses, the
winter vomiting bug, and secretors are not.

## How this works

Whether your body fluids carry your blood group sugars depends on the FUT2 gene, which makes those
sugars in the cells lining the mouth, gut and other moist surfaces. Each of your two copies of the
gene is a working version, a partly working version, or one that does not work at all, and one
working copy is enough to make you a secretor.

To decide between the three results, each of your two copies gets a score: 1 for a working version, 0
for a non-working one, and a quarter for the partly working one. The two scores are added together. A
total of 0 means neither copy works, so the result is non-secretor; a total of a quarter or a half
means the only working copies you have are partly working ones, so the result is weak secretor; and a
total of 1 or more means at least one copy works properly, so the result is secretor. The quarter is a
round figure rather than an exact measurement: when the partly working version was put into cells and
measured, it did about a fifth as much of the gene's work as the working version.

## For professionals

### Defining sites and alleles

Two sites on chromosome 19 (GRCh38), read from `haplotypes.csv`. The coding-level spellings are given
against RefSeq NM_000511.6 and confirmed against the ClinGen Allele Registry (CA122797, CA122800); the
`c.428G>A` / `c.385A>T` numbering that the older literature uses is legacy, not HGVS against that
transcript:

| Allele | rs601338 (48,703,417) | rs1047781 (48,703,374) | Activity value | Function |
|---|---|---|---|---|
| `Se`    | G | A | 1.0  | normal function |
| `se428` | A | A | 0.0  | no function — NM_000511.6:c.461G>A, p.Trp154Ter (legacy 428G>A, W143X) |
| `se385` | G | T | 0.25 | decreased function — NM_000511.6:c.418A>T, p.Ile140Phe (legacy 385A>T, I129F; the weak-secretor *Se^w* allele) |

### The activity scale and the bins

`allele_function.csv` gives each allele an activity value; the caller sums the pair and
`activity_phenotype.csv` bins the total:

| Bin | Total | Pairs that reach it | Grounding on the bin row |
|---|---|---|---|
| Non-secretor  | 0        | `se428/se428` | PMID 7876235 |
| Weak secretor | 0.25–0.5 | `se385/se428`, `se385/se385` | PMID 8981090 |
| Secretor      | 1–2      | any pair containing `Se` | PMID 30345375 |

**Why one working copy reaches Secretor.** Non-secretor status is recessive, and this is measured
rather than assumed: in ALSPAC the increased mumps and kidney-disease risks appear only in `A/A`
homozygotes and heterozygotes behave like secretors (PMID 30345375); the type 1 diabetes association
fits a recessive model (PMID 22025780); and intestinal organoids from a heterozygous donor were as
susceptible to norovirus and rotavirus as wild-type organoids (PMID 41132048). Giving `Se` a value of
1 and making the secretor bin start at 1 encodes exactly that.

**The 0.25 is a measurement, the scale around it is a modelling choice** (this is where PMID 8981090,
the measurement behind the quarter, belongs; the plain-language section above states the figure without
the citation). Henry *et al.* expressed the
385A>T allele in COS-7 cells and found unchanged Km but Vmax 230 against 1030 pmol h⁻¹ mg⁻¹ for wild
type, about a fifth (PMID 8981090). The values are then chosen so every pair containing `Se` sums to
at least 1, `se385/se385` and `se385/se428` land in 0.25–0.5, and `se428/se428` is 0. The phenotype
caller's tests enumerate every pair and require exactly that.

**The Weak secretor bin is this module's reading, and studies differ.** Several East Asian surveys
class `se385` homozygotes with non-secretors rather than as a separate partial phenotype — Guo *et al.*
report `se385` as the allele behind 97% of the non-secretor phenotypes they observed in 316 Chinese
participants (PMID 29123975) — while the expression and family work the bin rests on describe a partial
secretor phenotype (PMID 8981090, PMID 8645240). A reader classed here as a weak secretor would be
called a non-secretor by those studies' convention.

### Sources

| PMID | Paper | What it grounds here |
|---|---|---|
| 7876235  | Kelly RJ *et al.*, J Biol Chem 1995 — sequence and expression of the FUT2 candidate; homozygosity for an enzyme-inactivating nonsense mutation correlates with non-secretor | `se428` = 0; ~20% non-secretors |
| 8645240  | Henry S *et al.*, BBRC 1996 — homozygous 385 missense associates with Le(a+b+) partial secretor in an Indonesian family | `se385` gives a partial, not absent, phenotype |
| 8981090  | Henry S *et al.*, Glycoconj J 1996 — the 385 A→T allele expressed, with reduced α(1,2)fucosyltransferase activity | the 0.25 activity value; the weak bin |
| 16306606 | Thorven M *et al.*, J Virol 2005 — homozygous 428G→A gives resistance to symptomatic norovirus (GGII) | non-secretor protection; 20% of Swedish donors |
| 19440360 | Carlsson B *et al.*, PLoS ONE 2009 — the 428 nonsense mutation gives strong but not absolute protection against GII.4 | the hedge on "largely protected" |
| 22025780 | Smyth DJ *et al.*, Diabetes 2011 — FUT2 non-secretor status links type 1 diabetes susceptibility and resistance to infection | recessive inheritance; type 1 diabetes ~1.3×; which null allele belongs to which population |
| 30345375 | Azad MB *et al.*, Wellcome Open Res 2018 — FUT2 secretor genotype and susceptibility in the ALSPAC cohort | 25% non-secretors in a British cohort; mumps 68% vs 48%; heterozygotes are secretors |
| 41132048 | Nordgren J *et al.*, Mol Biol Evol 2025 — natural selection of a virus-protective FUT2 variant after the transition to agriculture | protection only in homozygotes; the Neolithic rise; rs1047781 is East Asia-specific, ~40% there |
| 15809881 | Park KU *et al.*, Ann Hematol 2005 — FUT2 fusion allele and a new se385 allele in a Korean population | se385 in ~7% of Korean donors |
| 29123975 | Guo M *et al.*, FEBS Open Bio 2017 — distribution of Lewis and Secretor polymorphisms in a Chinese population | se385 at 40.19%, se385/se385 in 16.2% and Se/se385 in 18.6% of 316 participants; se385 homozygotes classed as non-secretors |
| 11606829 | Yu LC *et al.*, Transfusion 2001 — polymorphism and distribution of the Secretor gene in Taiwanese populations | se385 (Se^w) circulating in East Asian populations |

Each `studies.csv` row but one carries a passage located by hand in that article's retrieved text.
Those passages were located in the same Europe PMC text the literature pass checks them against, so
`quotes_found` on these rows is a citation-pairing check, not independent evidence that the claim is in
the literature. Three points on terms, all recorded in `licensing.csv`:

- The module's own text is MIT. The quoted passages come from CC-BY articles and are carried with
  attribution, which that licence permits; the compiler reports the mixed declaration as a warning
  because only a person can judge whether such a pair is compatible.
- Smyth 2011 is CC-BY-NC-ND. A supporting passage was located and deliberately **not** carried, since
  a non-commercial, no-derivatives term would bind the whole artifact. That row's empty
  `provenance_quote` is a decision, not a failed search; only the paper's findings, restated, are used.
- Five of the eleven articles are closed or free-to-read with no licence recorded. Their terms are left
  blank — unknown, never false — which is why the module's own commercial-use and redistribution
  answers come back unknown on the published card.

### What this module cannot tell you

- **Only two sites are read.** Other non-working FUT2 alleles exist and are not modelled: the
  `sefus` fusion allele (common in Japanese and Korean populations), `se302`, `se571`, `se685`,
  `se849`, `sedel` and others. A person carrying one of those is reported on the two sites this
  module reads, so a true non-secretor can be reported as a secretor or a weak secretor.
- **Lewis phenotype is not reported.** It is a combination of FUT3 and FUT2, and the format cannot
  yet express a cross-gene combination.
- **It is not a diagnosis.** A laboratory reads secretor status from saliva directly; this is an
  inference from two positions in a DNA file.
- **The frequencies quoted are the ones the cited studies measured**, in the populations they
  measured them in, and do not transfer everywhere.

### How it was made

Authored by hand as a score-and-bin phenotype module (`haplotypes.csv` + `allele_function.csv` +
`activity_phenotype.csv`), compiled with just-dna-compiler. Every factual claim in the three bin
conclusions was checked in this pass against a paper found by literature search and read; the version
1.1.0 changes are listed below. No weights are authored — a phenotype result is not a sum of risks.

## About this copy

Our own pilot module, and the module just-dna-lite's phenotype-caller tests run against. Version
1.1.0 (2026-09-27) sourced every claim in the conclusions and grounded the bins:

- the conclusions were rewritten so each one names the evidence it rests on, with frequencies from
  the studies that measured them, and the norovirus protection hedged to "strong rather than
  absolute" after PMID 19440360;
- `studies.csv` (12 rows, 11 papers) and `licensing.csv` were added;
- each bin row now carries the PMID of the paper behind its boundary;
- the allele values (1.0 / 0.25 / 0.0) were left unchanged — the measurement in PMID 8981090 agrees
  with 0.25 — and so were the labels, alleles and defining sites.

**Review record.** On 2026-09-27 two independent AI reviewers — a lay reader given only the plain text
of the rendered report, and a scientific reviewer given the sources — read the rendered report for this
module, following the procedure in `docs/REPORT_VOICE.md`. What changed as a result, all in version
1.1.0 and none of it touching the labels, alleles, activity values, `haplotypes.csv` or
`resolution.csv`:

- the mechanism sentence in all three conclusions and in *How this works* was corrected: FUT2 does not
  "release" sugars, it makes them in the cells lining the mouth, gut and other moist surfaces, and the
  sugars on red blood cells come from a different gene whatever the secretor status;
- the secretor conclusion no longer says heterozygotes "behave exactly like" people with two working
  copies: one working copy is enough for norovirus, rotavirus and the conditions studied most closely,
  while a few studies see small in-between effects (PMID 30345375);
- the weak-secretor frequency was corrected: the partly working version is common in East Asia, about
  4 in 10 gene copies, with about 1 in 6 of 316 Chinese participants carrying two copies (PMID
  41132048, PMID 29123975); the Korean 7-in-100 figure moved out of the conclusion into the sources;
- the evolutionary sentence now says the non-working version was almost absent among Europe's early
  hunter-gatherers and arrived with the first farmers from Anatolia about 8,000 years ago (PMID
  41132048);
- the rotavirus claim is now attributed as well established for norovirus and supported by recent work
  for the common rotavirus strains;
- the secretor conclusion ends with the limit that only two non-working versions are read, so the
  result is less certain for people whose ancestry carries the others (PMID 15809881, PMID 11606829);
- the professional section notes that some East Asian studies class `se385` homozygotes with
  non-secretors, and the allele spellings are now given as HGVS against NM_000511.6 with the legacy
  numbering beside them;
- the plain-language scoring paragraph was rewritten, the "a quarter" / "a fifth" mismatch explained,
  and the PMID moved out of it into the professional section;
- `studies.csv` and `licensing.csv` gained Guo *et al.* 2017 (PMID 29123975).

Not reviewed by a domain expert.
