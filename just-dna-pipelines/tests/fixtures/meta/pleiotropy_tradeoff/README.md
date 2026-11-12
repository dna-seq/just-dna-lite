# Pleiotropy: per-trait judgements and the computed trade-off

Candidate 4 of `docs/probes/LONGEVITYMAP_V2_SHAPE_AUDIT.md` (Appendix 2): one allele judged per trait on
`meta.csv`, and `tradeoff` computed from those judgements rather than authored. Three loci, one per
outcome of the Kleene verdict. The values below are asserted by
`compiler/tests/test_reference_examples_meta.py`.

## How it was built

```bash
# variants.csv, studies.csv, meta.csv by hand
just-dna-enricher enrich reference_examples/pleiotropy_tradeoff --strict
just-dna-compiler close reference_examples/pleiotropy_tradeoff
just-dna-compiler compile reference_examples/pleiotropy_tradeoff out/ --strict
```

## What it exercises

**A bare locus member bears an allele when its rows agree on one.** Each per-trait row is
`variants[variant_key=…]` with a trait and a direction, one row per trait (not one per genotype). The
rule from the second measuring run: a locus whose `variants.csv` rows all state the same
`effect_allele` is allele-bearing, and `direction` is about that allele.

| locus | `effect_allele` | per-trait rows | `tradeoff` on every genotype row |
|---|---|---|---|
| SH2B3 rs3184504 | T (every row) | celiac disease `risk`, bacterial infectious disease `protective` | **true** |
| LPA rs10455872 | A (every row) | lipoprotein(a) `protective` (`trait_role=mediator`), coronary artery disorder `protective` | **null** |
| CETP rs5882 | none stated | exceptional longevity `protective` | **null**, direction withheld |

- **SH2B3** is the textbook trade-off. Zhernakova et al. 2010 (PMID 20560212) found the celiac risk
  allele of rs3184504 under positive selection and showed its carriers mount a stronger NOD2 response to
  bacterial components. One allele, a harm on one trait and a benefit on another: `tradeoff` is true.
- **LPA** has only protective judgements for its A allele (lower Lp(a), the mediator; less coronary
  disease, the outcome; Clarke et al. 2009, PMID 20032323). `tradeoff` is null, never false: the false
  arm needs every trait's judgement stated, and a module states no closed list of the traits an allele
  touches. A `mediator` row still counts, since its direction is still a benefit or a harm.
- **CETP rs5882** is one of the four loci v2 marks "allele not determined". Its rows state no
  `effect_allele`, so the locus fixes no allele and a direction on it says nothing. **This row is here on
  purpose**, to show what happens: the compile draws `meta_member_allele_ambiguous` once, `meta.parquet`
  lists `direction` in that row's `withheld`, the authored cell is kept for `reverse`, and the locus takes
  no part in a trade-off. v2 itself writes no per-trait row for such a locus, which is the advice; the
  warning is how an author who writes one finds out. The study cited is Barzilai et al. 2003
  (PMID 14559957).

Trait ids were checked against OLS on 2026-11-04: `MONDO:0005130` celiac disease, `MONDO:0005113`
bacterial infectious disease, `EFO:0006925` lipoprotein A measurement, `MONDO:0005010` coronary artery
disorder (EFO_0001645 is obsolete and points there), `OBA:VT0005372` life span trait (EFO_0004300
"longevity" is obsolete and points there).

## What building it broke

Nothing. Two things worth knowing:

- The warning fires under `--strict` and does not refuse: it is a withheld reading, not an invalid row.
  So `--strict` is green with one warning, and that warning is the example's point.
- LPA's genotype rows follow v2's own convention (the audit's case 1): `state` is per genotype against
  the common genotype (A/A neutral, a G carrier at risk), and `effect_allele` is A, the allele the
  per-trait `direction` is about (protective). Read together, "A is protective" and "carrying G is a
  risk" are one claim from two sides, not a contradiction; a module that wants the genotype rows to
  read the other way round states `effect_allele=G` and `risk` per trait, and the trade-off verdict is
  the same null.
- `effect_allele` on `variants.csv` now does double duty: it says which allele a row's effect is about,
  and, uniform across a locus, it is what lets a one-row-per-trait meta row be about an allele. A module
  that leaves it empty on a locus gets the warning above for every per-trait row on it.
