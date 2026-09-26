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
