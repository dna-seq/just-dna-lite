# abo_phenotype (pilot, unpublished)

An enumerative phenotype module: five ABO alleles (A1, A2, B, O1, O2) over six sites, and the
15 diplotypes they form, each mapped to a serological group (A, B, AB, O). The subgroup (A2) is
in `conclusion`, not `phenotype`, so an unphased callset that cannot tell A1 from A2 still calls
the group.

| Site | cDNA | GRCh38 (VCF, plus strand) | Marks |
|---|---|---|---|
| rs8176719 | c.261delG | 9:133257521 T>TC | the reference genome carries the deletion (**O**), so every non-O allele carries the insertion |
| rs1053878 | c.467C>T | 9:133256264 G>A | A2 |
| rs8176746 | c.796C>A | 9:133255935 G>T | B |
| rs41302905 | c.802G>A | 9:133255929 C>T | O2 (which keeps the 261 G) |
| rs8176747 | c.803G>C | 9:133255928 C>G | B |
| rs56392308 | c.1061delC | 9:133255669 CG>C | A2 |

ABO is on the minus strand; every allele here is the genomic (plus-strand) base, checked
against the GRCh38 reference sequence. Two sites are indels whose spelling differs between
sources, and both are authored as a left-normalized VCF caller writes them:

- **rs8176719**: dbSNP, gnomAD and DRAGEN place it at `133257521 T>TC`. The Ensembl
  variation cache places the rsID at `133257520 G>GC`, a different event (the flanking
  bases are G and T, not C) that gnomAD records at AF ~6e-7. Resolving the rsID through
  Ensembl would therefore match no real sample.
- **rs56392308**: a one-base deletion in a GGG run. Ensembl spells it `133255670 GGG>GG`,
  left normalization gives `133255669 CG>C`. The same event either way.

The caller matches both spellings through its indel window (docs/PHENOTYPE_CALLS.md).

**Not assessed**: RhD (a whole-gene deletion, not callable from an SNV VCF), the >250 rarer
ISBT ABO alleles (weak A/B subgroups, cis-AB, B(A)), and secretor status (see `fut2_secretor`).
A genotype these five alleles cannot explain is reported `no_match`, never forced onto the
nearest allele.

Authored for just-dna-lite's phenotype-caller tests. Not reviewed by a blood-group
specialist; do not publish as is.

## How this works

You inherit one version of the ABO blood group gene from each parent, and your blood group comes from
how the two combine. The A and B versions each put a different sugar tag on your red blood cells, and
the O version puts none. A and B both show when you carry them, and O shows only when both of your
versions are O. So an A version plus an O version gives group A, A plus B gives AB, and only O plus O
gives group O.

This report reads the few DNA positions that tell the versions apart. Blood for a transfusion is always
matched by a lab test, never by a DNA file.

## About this copy

The conclusions in this copy were rewritten in just-dna-lite's report voice (`docs/REPORT_VOICE.md`) on 2026-09-27; the rows, labels and rules are unchanged from the upstream reference example.
