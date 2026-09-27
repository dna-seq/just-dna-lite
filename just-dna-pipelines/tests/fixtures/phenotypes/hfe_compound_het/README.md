# Iron storage gene (HFE)

This module reads two places in your HFE gene and tells you which of the common inherited patterns
behind hereditary haemochromatosis you carry, if any. Hereditary haemochromatosis is a condition in
which the body slowly takes in and stores more iron than it needs. The two changes the module looks
for are the ones lab reports call C282Y and H63D.

You get one result, such as *Two copies of the C282Y change* or *Neither common iron-gene change*,
with a plain explanation of what it means, how common it is, and what a blood test can show. When your DNA
file cannot tell two possible results apart, the report shows both and says why.

## How this works

The HFE gene helps control how much iron the body takes in from food. Two common changes in it, known
on lab reports as C282Y and H63D, are linked with hereditary haemochromatosis, where iron slowly builds
up in the body. You inherit one copy of the gene from each parent, so you can carry none, one or two of
these changes.

What matters is which changes you carry and how they are arranged. Two copies of C282Y is the pattern
behind most cases. One C282Y and one H63D, one on each copy, carries a much smaller risk, and a single
change, or two copies of H63D, carries little or none. Having both changes on the same copy leaves one
normal copy. That arrangement is very rare, but most DNA files do not record which letters you
inherited together from the same parent, so the report says when your file cannot tell the two
arrangements apart.

Most people with any of these patterns never become ill from iron. A blood test of iron levels
(ferritin and transferrin saturation) shows what is actually happening, and that, not the DNA result,
is what a doctor acts on.

## For professionals

### Defining sites

| allele | variant | HGVS | GRCh38 |
|---|---|---|---|
| C282Y | rs1800562 G>A | NM_000410.3:c.845G>A, p.Cys282Tyr | 6:26092913 |
| H63D | rs1799945 C>G | NM_000410.3:c.187C>G, p.His63Asp | 6:26090951 |

Positions are 1-based VCF `POS` on GRCh38.

### Haplotypes and allele pairs

Four haplotypes are defined in `haplotypes.csv`, each written out at both sites:

| haplotype | rs1800562 | rs1799945 |
|---|---|---|
| `wt` | G | C |
| `C282Y` | **A** | C |
| `H63D` | G | **G** |
| `C282Y-H63D` | **A** | **G** |

`diplotypes.csv` pairs them into eight results:

| pair | technical name | result label shown to the reader | direction | clin_sig |
|---|---|---|---|---|
| C282Y / C282Y | C282Y homozygous | Two copies of the C282Y change | risk | pathogenic |
| C282Y / H63D | C282Y/H63D compound heterozygous (trans) | One C282Y and one H63D change, on different copies | risk | risk_factor |
| C282Y-H63D / wt | C282Y and H63D in cis | C282Y and H63D on the same copy | neutral | (blank) |
| C282Y / wt | C282Y heterozygous | One copy of the C282Y change | neutral | (blank) |
| H63D / H63D | H63D homozygous | Two copies of the H63D change | neutral | benign |
| H63D / wt | H63D heterozygous | One copy of the H63D change | neutral | benign |
| C282Y-H63D / C282Y | C282Y/H63D in cis with a second C282Y | Two C282Y changes, plus H63D on one copy | risk | pathogenic |
| wt / wt | no HFE risk allele (wild type) | Neither common iron-gene change | neutral | benign |

The module authors no weights; a combined result is not a sum of its parts. The labels in the
`phenotype` column are plain words for readers; the technical names above are the ones used in the
literature. `direction` and `clin_sig` come from the upstream reference example, which followed
ClinVar's calls for the two variants, except on the two single-C282Y-copy rows (C282Y / wt and
C282Y-H63D / wt). There the reference example said `risk` / `risk_factor`, while every guideline cited
here (EMQN, AASLD) states that a C282Y heterozygote is at no increased risk of HFE haemochromatosis,
and the conclusions say so. Since 1.1.0 those two rows are `neutral` with `clin_sig` left blank, so the
flag and the text agree. ACMG SF v3.2 lists HFE only for p.C282Y homozygotes, so no row here claims
secondary-findings reportability.

### Phase: cis versus trans

A double heterozygote (rs1800562 G/A, rs1799945 C/G) is consistent with two pairs: C282Y / H63D
(trans, the compound heterozygote) and C282Y-H63D / wt (cis, one intact copy). Without phase the two
cannot be told apart, and the compiler flags exactly this one group as indistinguishable. just-dna-lite
reports such a call as ambiguous and shows both results, and resolves it only when both sites carry
phased genotypes in the same phase set (`GT` with `|` and a shared `PS`).

In practice the trans reading is almost always the right one: the EMQN guideline states that the two
variants are always inherited in trans because they arose as independent founder alleles
(PMID 26153218). The cis rows are kept so that a phased cis call has a correct description, and their
conclusions say how rare the arrangement is.

### Sources

Every frequency and risk figure in the conclusions comes from one of these papers. Each was found with
`literature_search` in the session that wrote this version, and its title was checked against the
PMID. `studies.csv` gives the population, design and a short summary for each, with a verbatim passage
where one was located.

| PMID | Paper | Used for |
|---|---|---|
| 18199861 | Allen KJ et al. Iron-overload-related disease in HFE hereditary hemochromatosis. *N Engl J Med* 2008 | C282Y homozygotes: iron-overload-related disease in 28.4% of men and 1.2% of women |
| 19554541 | Gurrin LC et al. HFE C282Y/H63D compound heterozygotes are at low risk of hemochromatosis-related morbidity. *Hepatology* 2009 | compound heterozygotes: about 2% of northern Europeans, C282Y homozygotes 1 in 200; disease in 1 of 82 men and 0 of 95 women |
| 9138148 | Merryweather-Clarke AT et al. Global prevalence of putative haemochromatosis mutations. *J Med Genet* 1997 | C282Y concentrated in northern Europe; over 90% of UK patients are C282Y homozygotes; H63D more widespread |
| 11325323 | Steinberg KK et al. Prevalence of C282Y and H63D mutations in the hemochromatosis (HFE) gene in the United States. *JAMA* 2001 | C282Y carriers 9.54% of non-Hispanic whites; H63D homozygotes 1.89%, compound heterozygotes 1.97% |
| 15858186 | Adams PC et al. Hemochromatosis and iron-overload screening in a racially diverse population. *N Engl J Med* 2005 | C282Y homozygotes 0.44% of non-Hispanic whites; most have raised ferritin |
| 20008199 | McLaren GD, Gordeuk VR. Hereditary hemochromatosis: insights from the Hemochromatosis and Iron Overload Screening (HEIRS) Study. *Hematology Am Soc Hematol Educ Program* 2009 | genotype frequencies in 44,082 white participants: C282Y/H63D 2.0%, H63D/H63D 2.4%, C282Y carriers 10%, H63D carriers 24%, neither change 61% |
| 20471131 | European Association for the Study of the Liver. EASL clinical practice guidelines for HFE hemochromatosis. *J Hepatol* 2010 | most patients with HFE haemochromatosis are C282Y homozygotes; low penetrance |
| 21452290 | Bacon BR et al. Diagnosis and management of hemochromatosis: 2011 practice guideline by the American Association for the Study of Liver Diseases. *Hepatology* 2011 | 85-90% of inherited iron overload is C282Y homozygosity; C282Y and H63D heterozygotes and H63D homozygotes are generally not at risk of progressive iron overload |
| 26153218 | Porto G et al. EMQN best practice guidelines for the molecular genetic diagnosis of hereditary hemochromatosis (HH). *Eur J Hum Genet* 2016 | C282Y homozygosity 1 in 200-300 in people of European descent, 75-85% never develop disease; severe morbidity such as cirrhosis in about 4% of C282Y homozygotes (5.6% of men, 1.9% of women); about 25% of siblings of a C282Y homozygote are homozygous too; the two variants are always in trans; compound heterozygotes and H63D homozygotes (about 3% of Europeans) not classified as HFE haemochromatosis, overload usually needs co-factors |

Frequencies are for people of European ancestry, mostly measured in northern European or white North
American cohorts. C282Y is rare outside populations of European descent and was absent from the
African, Asian and Australasian chromosomes tested by Merryweather-Clarke et al., so the natural
frequencies in the conclusions do not carry over to other ancestries.

Quotes in `studies.csv` were located by an AI agent (named in `curator` and `authorship`) in text
returned by `fetch_fulltext`, so the literature pass's `quotes_found` for those rows is a
citation-pairing check rather than independent evidence. Several of those texts are abstracts only.
The two Gurrin 2009 passages and the HEIRS table row were located in the PMC author manuscripts,
which the literature pass does not read (it saw only the abstracts), so those three quotes come back
unchecked rather than confirmed.
The EMQN guideline is published under CC BY-NC-ND, so it is cited without a quote. The grain is one
row per paper and variant, where the passage concerns a genotype that contains that variant.

### What this module cannot tell

- **Rarer HFE variants.** Only C282Y and H63D are read. S65C and the rare private HFE variants and
  deletions found in some severe cases are not, so *Neither common iron-gene change* does not exclude
  them.
- **Non-HFE iron overload.** Hereditary haemochromatosis caused by *HJV*, *HAMP*, *TFR2* or
  *SLC40A1* (ferroportin), and acquired iron overload (alcohol, fatty liver disease, repeated
  transfusion), are outside this module.
- **Not a diagnosis.** Penetrance is incomplete and strongly modified by sex, age, alcohol and blood
  loss. Iron status is measured by ferritin and transferrin saturation, not by genotype.
- **Phase.** An unphased double heterozygote is reported as ambiguous rather than guessed, even though
  trans is far more likely.
- **Coverage.** A site the DNA file does not cover is not called. A position a variant-only file does
  not report may be inferred as reference and is labelled as such in the report.

### How it was made

The haplotypes and allele pairs come unchanged from the `hfe_compound_het` reference example in
[just-dna-compiler](https://github.com/dna-seq/just-dna-compiler) (MIT). Version 1.0.0 carried
conclusions rewritten into plain language without citations. Version 1.1.0 (2026-09-27) checked every
factual claim in those conclusions against the papers above, changed the conclusions where a source
disagreed, and added `studies.csv` and `licensing.csv`. The work was done by Claude (an AI agent,
through just-module-creator) with Anton Kulaga as the responsible human author, and every hand edit is
logged in `logs/authoring.log`. The upstream phenotype labels, `direction` and `clin_sig` were kept in
that pass.

Review record, 2026-09-27: two independent AI reviewers, a lay reader given only the plain text and a
scientific reviewer given the sources, read the rendered report for version 1.1.0 before it was
published. Changes made from their findings: the result labels were replaced with plain words (the
technical names are kept in the table above); the two single-C282Y-copy rows, whose conclusions say
there is no increased risk, were changed from `risk` / `risk_factor` to `neutral` with blank
`clin_sig`; the compound-heterozygote conclusion now says in plain words that one copy carries C282Y,
which stops the protein working, and the other H63D, which changes it only slightly, and no longer
ends by contrasting itself with the cis result; the cis conclusions state the rarity of the
arrangement without doubting the reader's call; the C282Y homozygote conclusion now says that the
Allen 2008 figures count raised liver enzymes, that serious damage such as cirrhosis is about 4 in
100 (EMQN), that brothers and sisters have about a 1 in 4 chance of the same result, and that the
usual treatment for high iron is simple and prevents damage, with a doctor deciding; "copy of the
gene" is used throughout; and blood tests are named as "a blood test of iron levels (ferritin and
transferrin saturation)".

## About this copy

This spec is vendored in just-dna-lite as a test fixture and is also the spec of the published module
`antonkulaga/hfe_compound_het`. Its haplotypes and allele-pair rules are those of the just-dna-format reference example,
unchanged; the labels and two rows' `direction` / `clin_sig` were changed for 1.1.0 as recorded above. The conclusions were rewritten in just-dna-lite's report voice (`docs/REPORT_VOICE.md`) and,
for version 1.1.0, checked against and sourced from the literature listed above.
