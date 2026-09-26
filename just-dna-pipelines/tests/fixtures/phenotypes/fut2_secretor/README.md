# fut2_secretor (pilot, unpublished)

A score-and-bin phenotype module: three FUT2 alleles over two sites, each given an
`activity_value` in `allele_function.csv`, summed over the pair and binned by
`activity_phenotype.csv`.

- `Se` — functional (reference at both sites).
- `se428` — rs601338 A (c.461G>A, p.Trp154Ter, also written W143X; the common European/African null allele).
- `se385` — rs1047781 T (I129F, the East Asian reduced-activity Se-w allele).

**The activity scale is a modelling choice, not a published number.** Secretor status is
dominant, so the values are chosen so every pair containing `Se` sums to at least 1
(secretor), `se385/se385` and `se385/se428` land in the weak bin (0.25–0.5), and
`se428/se428` is 0 (non-secretor). The caller tests enumerate every pair and require
exactly that.

Out of scope: rarer null alleles (sedel, se302 and others), and Lewis phenotype (FUT3 × FUT2),
which is a cross-gene combination the format cannot yet express.

Authored for just-dna-lite's phenotype-caller tests (docs/PHENOTYPE_CALLS.md). Not reviewed
by a domain expert; do not publish as is.

## How this works

Most people release their blood group sugars into saliva and other body fluids, not only onto their red
blood cells. Whether you do depends on the FUT2 gene. Each of your two copies is a working, a partly
working or a non-working version, and one working copy is enough to make you a secretor.

The report gives each version a value (1 for working, less for partly working, 0 for non-working), adds
your two values, and the total decides the result: 0 is a non-secretor, a small total is a weak secretor,
and 1 or more is a secretor.

## About this copy

The conclusions in this copy were rewritten in just-dna-lite's report voice (`docs/REPORT_VOICE.md`) on 2026-09-27; the rows, labels and rules are unchanged from the upstream reference example.
