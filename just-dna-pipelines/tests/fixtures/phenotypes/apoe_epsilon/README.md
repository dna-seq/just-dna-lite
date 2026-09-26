# APOE ε2/ε3/ε4 — the meta-conclusion feasibility probe

This module exists to answer a design question with evidence instead of opinion: **does pairing two
annotations require new machinery?** APOE is the sharpest possible test, because the ε haplotypes are
defined by *two* SNPs together and CONSTITUTION Principle 1's own example of the predicate escape
hatch is literally the ε4 condition:

> a **non-Turing-complete boolean predicate** over genotypes (e.g. `rs429358==C AND rs7412==C`)

**The answer is that it does not.** APOE is expressible with bricks that shipped in 0.4, needs no
predicate, and compiles at 20K.

## Why it works without a predicate

`HaplotypeRow` **is** same-strand co-location. It is a junction table — one row per (haplotype ×
defining variant) — so a haplotype defined by two SNPs is simply two rows:

| haplotype | rs429358 (19:44908684 T>·) | rs7412 (19:44908822 C>·) |
|---|---|---|
| ε2 | T | **T** |
| ε3 | T | C |
| ε4 | **C** | C |

`diplotypes.csv` then pairs them, which is where the conclusion lives. So "two variants on one
strand mean this" was never a missing feature; it is what a haplotype table is for. The predicate
would have restated, less legibly, something the schema already says.

Note ε3 carries the **reference** allele at both positions. Unlike a star-allele `*1`, which is
defined by the *absence* of variants, ε3 is a real named haplotype whose defining alleles happen to
be the reference ones — so it is written out rather than left implicit.

## What this does *not* settle

Two things stay genuinely out of reach, and they are what [RM28](../../docs/ROADMAP.md) is still
about:

1. **Pairing across subjects.** A conclusion combining an APOE diplotype with a separate
   cardiovascular variant and a PGx drug row has no carrier: every table keys on one subject, and no
   column can name a row in another table.
2. **Compound heterozygosity without enumeration.** APOE has three haplotypes and six diplotypes, so
   writing them out is trivial. A gene with hundreds of pathogenic variants would need every
   two-variant combination enumerated to say one thing about "any two in trans" — expressible in
   principle, absurd in practice. That is an economy argument, not an expressiveness one, which makes
   it weaker than it first looked.

So the feasibility signal is positive: the highest-profile meta case needs nothing new, and RM28 stays
parked until a module appears that genuinely cannot be written.

## The defect it did find — since fixed

`AlleleFunctionRow.allele` enforced `STAR_ALLELE_PATTERN` (a leading `*`) while
`HaplotypeRow.haplotype_name` and `DiplotypeRow.haplotype_a`/`haplotype_b` had no rule at all, so
`e4` was legal in two of the three PGx tables and illegal in the third. Worse, the cross-table check
added in 0.5 turned the obvious workaround into a dead end: write `*4` in one table and `e4` in the
other and it reports "used but not defined", with no spelling that satisfies both.

All three tables now share one rule (`validate_haplotype_name`): non-empty, no whitespace, nothing
else — a name is an identity, not a grammar. `STAR_ALLELE_PATTERN` is still what the CPIC provider
checks, so drafting is as strict as it was.

This module still carries no `allele_function.csv`, but that is now a curation choice rather than a
prohibition: an ε allele has no CPIC activity value or function category, and inventing one to fill
a table would be worse than leaving it out.

## Honest limits of the content

The `direction` on ε2/ε4 is `unknown` on purpose — two opposing alleles, and the risk is not the sum
of its parts. Every conclusion here says the association and stops: APOE is a risk modifier with
incomplete, age-dependent penetrance, not a diagnosis, and the module is not entitled to imply one.

Phase matters and the module cannot supply it: unphased `rs429358 T/C` + `rs7412 C/T` is ambiguous
between ε1/ε3 and ε2/ε4. Resolving that is the consumer's caller's job — the module states what each
diplotype means, never which diplotype a sample has.
