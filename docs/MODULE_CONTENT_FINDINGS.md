# What the ten v1-port modules actually say, and where it is wrong

**Audit date 2026-08-21/22.** A content review of every module in `data/interim/v1_port/` — the
claims themselves, not the tooling. Findings carry `C#` ids and are grouped by **what has to happen
to them**: fix, improve, recheck, misc.

This is the companion to [MODULE_DOGFOODING.md](MODULE_DOGFOODING.md), which asked whether the
authoring tooling can *find* problems like these. It mostly cannot — every module below passes
`validate_module(strict=true)` with zero errors, and nothing here was surfaced by any automated gate.

**Nothing has been changed.** Authored cells — `genotype`, `weight`, `state`, `conclusion` — are the
maintainer's call, and the corpus is deliberately held at its 0.5-era state.

## Severity

- **FIX** — wrong on the module's own terms. A reader is shown a false statement about themselves.
- **IMPROVE** — not false, but the module is not doing the job it claims.
- **RECHECK** — cannot be settled from inside the repo; needs a source consulted.
- **MISC** — structural or cosmetic.

## Scope

| module | rows | rsIDs | states | weights |
|---|---|---|---|---|
| coronary | 81 | 27 | 41 risk / 27 neutral / 13 protective | 41 neg, 27 zero, 13 pos |
| lipidmetabolism | 45 | 15 | 27 / 10 / 8 | 27 neg, 10 zero, 8 pos |
| longevitymap | 1039 | 528 | 47 risk / **0 neutral** / 992 protective | 47 neg, 0 zero, 992 pos |
| superhuman | 190 | 101 | **190 protective, 0 anything else** | **all empty** |
| thrombophilia | 24 | 8 | 17 / 7 / 0 | 17 neg, 7 zero |
| vo2max | 39 | 13 | 10 / 22 / 7 | 10 neg, 22 zero, 7 pos |
| pharmgkb | 1482 | — | (PGx, no state axis) | — |
| cardio / cancer / pathogenic | 57k / 70k / 309k | — | ClinVar-drafted | — |

---

# FIX

## C1 — `vo2max` inverts the APOE result it cites, on both SNPs

**The single most serious finding in this audit.** The module's own `studies.csv` grounds both APOE
rows in **PMID 24571688** (Yu et al. 2014, *Lipids Health Dis*, 360 Chinese young adults). The paper's
results tables and the module disagree in direction.

APOE haplotypes are defined by the rs429358/rs7412 pair: ε2 = `T`+`T`, ε3 = `T`+`C`, ε4 = `C`+`C`.
So `rs429358 C/C` is ε4/ε4, and `rs7412 T/T` is ε2/ε2.

What the paper found (male cohort; the female cohort is the same pattern):

| genotype | P | result |
|---|---|---|
| E2/E2 | 0.63 | not significant |
| **E2/E3** | **0.04** | **significantly higher VO2max gain** |
| E2/E4 | 0.58 | not significant |
| E3/E3 | 0.19 | not significant |
| **E3/E4** | **0.02** | **significantly higher VO2max gain** |
| E4/E4 | 0.67 | not significant |

What the module says:

| row | module state / weight | module conclusion | the paper |
|---|---|---|---|
| `rs429358 C/C` (= ε4/ε4) | **protective +1.0** | "High VO2max training response" | **ns, P=0.67** |
| `rs429358 T/T` (= ε2/ε2, ε2/ε3 or ε3/ε3) | **risk −0.5** | "Low VO2max training response" | contains **ε2/ε3, P=0.04, higher** |
| `rs7412 T/T` (= ε2/ε2) | **protective +1.0** | "High VO2max training response" | **ns, P=0.65** |
| `rs7412 C/C` | risk −0.5 | "Low VO2max training response" | contains ε3/ε4, P=0.02, **higher** |

Three separate errors compounded:

1. **The two genotypes the paper found significant (ε2/ε3 and ε3/ε4) are both heterozygous
   combinations that the module scores as neutral or risk.** The two it scores most extreme —
   ε4/ε4 and ε2/ε2 — are the two the paper explicitly reports as non-significant.
2. **A haplotype effect is being scored per SNP.** ε2/ε3 and ε3/ε4 cannot be read off either SNP
   alone; you need both. The module carries both rsIDs and scores them independently and additively,
   which cannot reconstruct the finding it cites even in principle.
3. **The direction is inverted on rs429358.** Whatever the intended reading, calling ε4/ε4 the best
   training responder is not in the cited paper.

**What a reader is told today:** an ε4/ε4 homozygote — the highest-risk APOE genotype for Alzheimer's
disease and the one `lipidmetabolism` scores **risk −3.0** — is shown "High VO2max training response,
protective" by `vo2max` in the same report.

**Additional caution for whoever fixes this:** the paper is n=360, single-centre, single-ethnicity,
self-controlled with no control group, and its own limitations section says so. Its ORs are reported
with CIs that cross or nearly touch zero. It is thin support for any per-genotype claim, in either
direction. The honest repair may be to drop both APOE rows from `vo2max` rather than re-sign them.

## C2 — `superhuman` labels 190 of 190 rows `protective`, including sickle-cell disease and CIPA

Every row in the module carries `state: protective`. There is no `risk` and no `neutral` row, and
**every `weight` is empty**. 117 of the 190 rows name a real adverse effect in their own conclusion
text, and 90 name one that is serious.

The module's framing — a beneficial variant with a noted downside — is coherent for `rs1815739`
(ACTN3) or `rs1800795` (IL6). It is not coherent for these:

| rsID | gene | genotype | conclusion, verbatim |
|---|---|---|---|
| `rs334` | HBB | `A/T` | "Malaria resistance · Adverse effects: **Exertional rhabdomyolysis**" |
| `rs1799770` | NTRK1 | `C/C` | "Pain insensitive, no sweat (anhydrosis) · Adverse: Unnoticed harm, hyperthermia" |
| 20+ more NTRK1 | NTRK1 | various | same text |
| 8 `SCN9A` | SCN9A | various | "Loss of the sense of smell" / "may cause hypersensitivity" |
| 8 `RIMS1` | RIMS1 | various | "**Late onset visual loss (Cone-rod dystrophy)**" |
| 8 `GHR` | GHR | various | "Short stature" |

`rs334` is the sickle-cell mutation (HbS, p.Glu7Val). Heterozygous carriage does confer malaria
resistance and the trait framing is defensible — though "exertional rhabdomyolysis" considerably
understates sickle cell trait, and ClinVar carries this variant as **Pathogenic** for HEMOGLOBIN S.

The NTRK1 cluster is the sharper case. Biallelic NTRK1 loss of function causes **CIPA** (congenital
insensitivity to pain with anhidrosis) — a severe recessive disorder with childhood mortality from
hyperthermia. Twenty-plus rows present it as a `protective` superpower with an "adverse effect".

**And the state axis is doing no work at all.** With 190/190 `protective` and no weights, the column
carries zero information — a consumer colouring by `state` renders the entire module green, sickle
cell and CIPA included. See also **C6**.

## C3 — `superhuman` rs333: the CCR5-Δ32 heterozygote is labelled "HIV resistance"

Resolved alleles: `ref = ACAGTCAGTATCAATTCTGGAAGAATTTCCAGA` (intact, 33 bp),
`alt = A` (the Δ32 deletion).

| row genotype | what it is | module says |
|---|---|---|
| `A/A` | **Δ32 homozygote** | "HIV resistance", protective — **correct** |
| `A/ACAGTCAGTATCAATTCTGGAAGAATTTCCAGA` | **heterozygote, one Δ32 copy** | "HIV resistance", protective — **wrong** |

The two rows carry byte-identical conclusion text. One Δ32 copy does not confer resistance to
HIV-1 infection; it is associated with slower progression to AIDS once infected. Roughly 10% of
people of European ancestry are Δ32 heterozygotes, so this row will fire often, and it tells them
they are resistant to HIV.

## C4 — `coronary` rs17514846: the `C/C` and `A/A` conclusions are swapped

| genotype | state | weight | conclusion |
|---|---|---|---|
| `C/C` | neutral | 0.0 | "…**AA** genotype **is** associated with an increased risk of CAD." |
| `A/C` | neutral | 0.0 | (shared FURIN text) |
| `A/A` | neutral | 0.0 | "…**CC** genotype is **NOT** associated with an increased risk of CAD." |

Each homozygote is shown the other's sentence. All three rows are scored `neutral 0.0`, so the
`weight` does not disagree with anything — but the prose is what the reader reads, and it is exactly
backwards. `rs17514846` A is the CAD risk allele (FURIN locus, 15q26.1), which the shared preamble on
each row states correctly before contradicting itself.

## C5 — `coronary` rs11591147: `T/T` scored `protective +1.2` under text saying `GG` is protective

`rs11591147` is PCSK9 R46L. The `T` (minor) allele is the loss-of-function allele associated with
lower LDL and lower CAD risk, so `T/T` **being** protective is right. The conclusion text is what is
wrong:

> "…rs11591147(T) allele w[as associated with]… **GG genotype is protective** and is associated with
> 2-3 fold lower risk o[f]…"

`G/G` is the common non-carrier genotype and is scored `neutral 0.0` on its own row. The sentence
appears on all three rows, so the `G/G` row tells a non-carrier they are protected and the `T/T` row
credits the wrong genotype for its own +1.2.

## C6 — `superhuman` authors no weights at all

190 rows, `weight` empty on every one, and no `weighting:` block in `module_spec.yaml`. This repo's
report sums `weight` per module into `total_weight`, so the module renders **0.0 for every category
while displaying up to 190 findings**.

Also carried as **D5** in the dogfooding doc, because no tool remarks on it. It is here too because
it is a content decision, not a tooling gap: either the weights should be authored, or
`weighting:` should declare that the module authors none deliberately.

---

# IMPROVE

## C7 — `longevitymap`'s conclusions are study abstracts, not statements about the reader

1,039 rows share **79 distinct conclusions**. The top 12 cover **79%** of all rows, and the single
most common one — used on **551 rows, 53% of the module** — is in full:

> "281 SNPs were found to discriminate between cases and controls"

**70% of rows** have a conclusion matching study prose (`SNPs were`, `cohort`, `meta-analysis`,
`p =`, `HR (`), **0 rows** address the reader in the second person, and only 128 of 1,039 mention
their own rsID. Twenty rows have the conclusion "Longevity-associated variant" and nothing else.

Compare `lipidmetabolism`, which does this properly: *"You are a carrier of one rs7412(T) allele,
also known as Arg176Cys. That generally indicates…"*

A reader with a hit in this module currently sees a sentence about a study population they are not
part of, repeated identically for up to 551 findings. This is the largest single readability problem
in the corpus and it affects the module most likely to produce many hits.

## C8 — `longevitymap`'s weights are a mechanical allele-dose formula, not curated values

Of 464 rsIDs with exactly two weighted rows, **461 (99%) have `|w_homozygote| = 2 × |w_heterozygote|`
exactly**. Weight and `state` are perfectly collinear — all 992 `protective` rows are positive, all
47 `risk` rows are negative, and there are **no zero weights and no `neutral` rows anywhere**.

That is an additive dose model applied uniformly, which is a reasonable default and should simply be
**declared**. Right now a consumer cannot tell a per-variant curated weight from a formula output,
and `weighting:` is the field that would say so. Note also that 11 conclusions are shared across rows
with *opposite* `state` — one text spans 20 rows covering both `protective` and `risk`.

## C9 — 45 `longevitymap` rsIDs have only one genotype row

A reader who is a non-carrier at those sites matches nothing and is told nothing. Because every row
in the module is a positive weight in one direction, a partial genotype set means the score is
computed over whatever happens to be present. `superhuman` has the same shape more severely — the
compiler reports 46 reference-homozygote, 31 homozygous-alternate and 8 heterozygous genotypes with
no row.

The compiler *does* warn about this (it is the "N genotype(s) at M site(s) have no row" warning), so
unlike most of this document it is not invisible — it is just buried under 80 VRS warnings.

## C10 — `superhuman` genotypes spelled as long allele strings will rarely match

Ten rows carry an allele longer than 4 bp inside the `genotype` cell, e.g.
`rs11369980 AATTTATTTTGACATAAAGTTGATAAAGATA/AATTTATTTTGACATAAA` and
`rs333 A/ACAGTCAGTATCAATTCTGGAAGAATTTCCAGA`.

The join is string equality on allele spellings, and one indel has several valid representations. A
caller that left-aligns or parsimony-reduces differently produces a different string for the same
biological event, and the row silently does not match. `rs333` is the one that matters most, since
Δ32 is common and the module's claim about it is prominent.

## C11 — `rs334` is scored identically for three different variants

The module has `A/T`, `C/T` and `G/T` rows, all reading "Malaria resistance". Resolution gives
`ref=T, alts=A,C,G` — three distinct substitutions at the same codon:

- `T>A` = **HbS** (p.Glu7Val) — sickle cell, the malaria-protective one
- `T>C` = **Hb G-Makassar** (p.Glu7Gly) — clinically benign, **no malaria protection reported**
- `T>G` = p.Glu7Ala — a third variant

Two of the three rows claim a benefit belonging to the first. And `A/A` — HbSS, sickle cell
**disease** — has no row at all, so the one genotype with major clinical consequence is the one the
module is silent about.

---

# RECHECK

## C12 — no module grounds any claim in a located quote

`provenance_quote` is filled on **0 of 979** `studies.csv` rows across all six curated modules, and
`quotes_authored` is `0` on **all 326** `literature.csv` rows.

| module | studies rows | with quote | literature rows | with quote | open access |
|---|---|---|---|---|---|
| coronary | 118 | 0 | 59 | 0 | 19 |
| lipidmetabolism | 41 | 0 | 36 | 0 | 19 |
| longevitymap | 671 | 0 | 162 | 0 | 16 |
| superhuman | 103 | 0 | 37 | 0 | 8 |
| thrombophilia | 27 | 0 | 25 | 0 | 3 |
| vo2max | 19 | 0 | 7 | 0 | 3 |

Every PMID resolves (`exists: true` on all 326, no dead citations — that part is clean). But nothing
records that anyone read any of them, which is exactly how **C1** survived: `vo2max` cites a real,
open-access paper whose results table contradicts the module, and nothing in the module ever had to
quote it.

68 of the 326 citations are open access and could be quoted today with the tooling that exists.

## C13 — 20 conclusions describe a genotype other than their own row's

Measured across the six curated modules (1,418 rows) by testing whether a conclusion names a
two-letter genotype token built from alleles **at that rsID's own locus** that is not the row's
genotype. **20 hits; roughly 12 are real** on hand inspection, the rest legitimate comparative or
quoted prose (`longevitymap` abstracts contain strings like `HR (MnSOD(CC/CT)) = 0.91`).

**C4** and **C5** are the two worst. The others, needing a look:

| module | rsID | row | names |
|---|---|---|---|
| coronary | rs4977574 | `A/A` | GG |
| coronary | rs17228212 | `C/C` | TT |
| lipidmetabolism | rs676210 | `A/G`, `G/G` | GG / AG |
| thrombophilia | rs6025 | `T/T` | CC, AA |
| thrombophilia | rs1799963 | `A/A` | GA |
| thrombophilia | rs1800790 | `A/A` | GA |
| thrombophilia | rs2519093 | `C/T` | TT |

`thrombophilia` rs6025 is worth separating: its `C/T` row reads *"**CA** carriers have 3.5-4.4x
risk"*. F5 Leiden is `1691G>A` in the legacy orientation and `C>T` in dbSNP's, so this is a genuine
orientation mismatch between the `genotype` column and the prose rather than a typo — but the reader
still sees `C/T` in one cell and "CA carriers" in the next.

## C14 — `thrombophilia` rs1799889 `G/G` is `state: risk` with a conclusion saying it is not

> `G/G`, `state: risk`, `weight: -0.3` — "GG variant may increase the risk of abdominal aortic
> aneurysm (AAA). The risk of blod clotting and coronary arthery disease **is not increased**."

The module is about thrombophilia. If the AAA association is the reason for the `risk` label, the
module should say so; if not, `G/G` (the 5G/5G PAI-1 genotype) is the common non-risk genotype and
`neutral 0.0` is the honest scoring. Needs a source consulted either way. (Two spelling errors in
that sentence, "blod" and "arthery" — see **C17**.)

## C15 — cross-module APOE contradiction

`rs7412` appears in four modules and `rs429358` in three, scored independently and inconsistently:

| rsID / genotype | lipidmetabolism | longevitymap | vo2max | superhuman |
|---|---|---|---|---|
| rs429358 `C/C` (ε4/ε4) | **risk −3.0** | risk −1.0 | **protective +1.0** | — |
| rs429358 `T/T` | neutral 0.0 | — | **risk −0.5** | — |
| rs7412 `T/T` (ε2/ε2) | protective +3.0 | protective +1.0 | protective +1.0 | protective (no weight) |
| rs7412 `C/C` | neutral 0.0 | — | **risk −0.5** | — |

The `rs429358 C/C` row is a flat contradiction: −3.0 in one module and +1.0 in another, in the same
report. Some of this is legitimate — APOE is genuinely pleiotropic and a variant can be bad for
lipids and neutral for fitness — but `vo2max`'s side of it is **C1**, which is wrong on its own
terms. Once **C1** is settled the remaining disagreement is defensible, provided the reader can see
that the modules are answering different questions.

`rs1801133` (MTHFR C677T) is carried by `thrombophilia` without `rs1801131` (A1298C), so the
compound-heterozygote state cannot be reconstructed. Same class of problem as **C1**'s point 2,
lower stakes.

---

# MISC

## C16 — `pharmgkb` makes 1,482 clinical claims with no citations

No `studies.csv`, `study_count: 0`, and `pharm_variants.csv` has no PMID column to put one in. Every
row is a drug-response statement ("*may have an increased risk of myopathy when treated with
atorvastatin*"). `evidence_level` (1A/1B/2A/2B) and `annotation_id` point at ClinPGx's own grading,
which is a pointer to somebody else's evidence rather than a citation.

Whether that is sufficient provenance for a drafted PGx module is genuinely undecided — carried as
**D8** in the dogfooding doc and raised upstream. Not a defect in the module as authored.

## C17 — spelling and grammar errors in reader-facing conclusions

Found while reading; not systematically swept. `thrombophilia`: "increse", "blod clotting",
"coronary arthery", "thromboembolia". `lipidmetabolism`: "ia a part of" (twice, on the two rs429358
carrier rows). These are in the exact sentences a person reads about their own genome.

## C18 — `category` is empty on five of six curated modules

| module | rows | with `category` |
|---|---|---|
| longevitymap | 1039 | 1039 (`other` 483, `inflammation` 117, `genome_maintenance` 109, `insulin` 101, …) |
| coronary, lipidmetabolism, superhuman, thrombophilia, vo2max | 379 | **0** |

`category` is what the report groups sections by, so those five collapse to a single unnamed block.
`longevitymap` fills it — and 46% of its values are `other`.

`direction`, `stat_significance`, `trait_efo_id`, `effect_size` and `effect_measure` are empty
**corpus-wide**. That is expected for Gen-I ports authored against 0.2, and `direction` is derived at
read time from `state`, so nothing is broken — but it means the 0.5/0.6 axes carry no information
anywhere in the corpus.

## C19 — `superhuman` rs56185968 is a 23-allele repeat authored as one variant row

Authored as a single `variants.csv` row with no coordinates and genotype `G/G`; resolution expanded
it to a GT-repeat ladder from `G` to a 45-base allele. Belongs in `repeat_alleles.csv`. Carried as
**D13**; repeated here because the row also carries an NTRK1/CIPA conclusion, so it is part of **C2**.

## C20 — one near-empty conclusion

`superhuman` `rs6265` (BDNF Val66Met): the entire conclusion is **"Learning (BDNF M66V)."** — a
label, not a statement. Also note the module writes `M66V`; the standard designation is `V66M`
(Val66Met), so the substitution is written backwards.

---

# Suggested order

| # | finding | why |
|---|---|---|
| 1 | **C1** `vo2max` APOE inverted vs its own cited paper | a false, source-contradicted claim on a common genotype |
| 2 | **C3** rs333 heterozygote told they are HIV resistant | ~10% of European-ancestry readers hit this row |
| 3 | **C2** `superhuman` 190/190 protective, incl. sickle cell + CIPA | severe recessive disease presented as a superpower |
| 4 | **C4 / C5** `coronary` swapped and mismatched conclusions | reader shown another genotype's sentence |
| 5 | **C11** rs334 three variants scored as one; HbSS absent | benign G-Makassar told it resists malaria |
| 6 | **C7** `longevitymap` conclusions are abstracts | 53% of rows share one meaningless sentence |
| 7 | **C13 / C14 / C17** remaining prose defects | ~10 rows, one sweep |
| 8 | **C6 / C8** declare `weighting:`, or author weights | makes two modules' numbers interpretable |
| 9 | **C12** ground claims in located quotes | the control that would have caught C1 |
| 10 | **C9 / C10 / C15 / C18 / C19 / C20** | structural, lower stakes |

**On method.** C1, C3 and C11 were checked against external sources (the cited paper's own results
tables via PubMed, ClinVar via `variant_getter`, and the modules' own `resolution.csv`). C4, C5, C13,
C14 and C17 are internal contradictions provable from the rows alone. C7, C8, C9, C10 and C18 are
measurements over the CSVs. Nothing here was taken from the modules' own summaries of themselves.
