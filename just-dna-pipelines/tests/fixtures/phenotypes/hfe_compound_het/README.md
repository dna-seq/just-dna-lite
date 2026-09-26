# HFE C282Y/H63D — cis, trans, and the one thing a table cannot say

The companion to [`apoe_epsilon`](../apoe_epsilon/), probing the half of RM28 that APOE left open.
APOE showed a two-SNP haplotype needs no predicate. This asks the harder question: **compound
heterozygosity — where the same two alleles mean opposite things depending on which chromosome they
sit on — was the case that most justified a predicate language. Does it need one?**

It does not. And building it surfaced the thing that *is* actually missing, which turned out to be a
compiler check rather than a schema feature.

## The biology, briefly

HFE haemochromatosis is recessive. Two alleles matter in practice:

| allele | variant | GRCh38 |
|---|---|---|
| C282Y | rs1800562 G>A | 6:26092913 |
| H63D | rs1799945 C>G | 6:26090951 |

C282Y homozygosity accounts for most clinically diagnosed cases. **C282Y/H63D compound
heterozygosity** — one variant on each chromosome — is a recognised at-risk genotype: no wild-type
HFE protein is made from either copy, and a minority develop raised iron indices. Carrying *both*
variants **on the same chromosome** is a different situation entirely: the other chromosome still
carries an intact HFE, so the expectation is that of a simple C282Y carrier.

Same two variants. Same two heterozygous calls. Opposite finding.

## Why no predicate is needed

A **diplotype is already a statement about two homologs.** `haplotypes.csv` says which alleles ride
together on one chromosome (same-strand conjunction, as APOE showed), and `diplotypes.csv` pairs two
of them — which is exactly what "in trans" means. So cis and trans are two rows:

| haplotype | rs1800562 | rs1799945 |
|---|---|---|
| `wt` | G | C |
| `C282Y` | **A** | C |
| `H63D` | G | **G** |
| `C282Y-H63D` | **A** | **G** |

- `C282Y` / `H63D` → **trans**: compound heterozygote, at-risk.
- `C282Y-H63D` / `wt` → **cis**: both variants on one chromosome, one intact copy, a carrier.

Both compile today with bricks that shipped in 0.4. The predicate grammar RM28 sketched would have
restated this less legibly, and the cis/trans relation it was going to introduce is what a diplotype
pair *is*.

Note `wt` is written out with its reference alleles at both positions, the same choice ε3 makes in
the APOE example — unlike a star-allele `*1`, which is defined by carrying no variants at all.

## What building it *did* surface

Nothing in the module says that a consumer **cannot tell those two rows apart**. Discard phase and
both present the identical genotype — rs1800562 G/A and rs1799945 C/G — with opposite conclusions.
Almost all consumer genotype data is unphased. Silently reporting the first would manufacture an
at-risk finding; silently reporting the second would suppress one.

That is real, and it is **derivable**: the compiler already holds both tables, and the computation is
pure and offline. So it became a check rather than a column —
`compiler._cross_validate_phase_ambiguity`, a warning that never blocks:

```
warning: HFE: diplotype rows C282Y-H63D/wt, C282Y/H63D are indistinguishable without phase —
they present the same unphased genotype but state different conclusions. A consumer with unphased
calls must withhold rather than pick one; a phased consumer resolves it.
```

A `requires_phase` column would have made an author restate what the data already determines, and it
would go stale the moment a haplotype is edited. Compiling this module emits exactly one such warning
and nothing else; the other six diplotype rows are unambiguous.

## What it still does not settle

The check is **closed-world**: it compares the rows a module states, never the rows it omits. APOE is
the illustration — ε2/ε4 and ε1/ε3 are the textbook unphased collision, and because that module
carries no ε1, nothing fires. That is correct (the module makes no claim about ε1), and the
neighbouring "star allele used but not defined" warning is what covers an allele a caller might emit
that the module never describes.

And the two gaps [`apoe_epsilon`](../apoe_epsilon/) named are untouched by this:

1. **Pairing across subjects** — a conclusion combining an HFE diplotype with, say, a *HAMP* or
   *TFR2* variant has no carrier; every table keys on one subject.
2. **Economy.** Four haplotypes give ten diplotypes and that is comfortable. A gene with 300
   pathogenic variants where "any two in trans" is the finding gives ~45,000 pairs — expressible,
   unwritable, and no longer saying *why* once enumerated.

Neither is an operator problem, which is the point [ROADMAP RM28](../../docs/ROADMAP.md) keeps
making: rows are a disjunction and columns are a conjunction, so the tables already span any finite
boolean function over an enumerable set of genotypes. What is missing is economy and open-world
negation, and no predicate token fixes the second.

## Provenance and honesty

`clin_sig` follows ClinVar's own calls for the two variants, and the conclusions are deliberately
hedged: HFE penetrance is incomplete and strongly modified by sex, age, alcohol and blood loss, so
every row reads as a susceptibility statement rather than a diagnosis. ACMG SF v3.2 lists HFE, and
scopes it to **"c.845G>A; p.C282Y homozygotes only"** — narrower than the gene, and narrower than
this module, which is why no row here claims secondary-findings reportability.

## Reproduce

```bash
just-dna-enricher enrich reference_examples/hfe_compound_het
just-dna-compiler compile reference_examples/hfe_compound_het out/hfe_compound_het
```
