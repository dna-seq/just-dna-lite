# A draft section for the just-dna-lite manuscript: the Longevity Map, re-curated

Drafted 2026-11-18 by longevity-loci's lead, on Anton's ask ("make it not as just example but as a key module of the
whole system and we can talk about longevity and genomics"), for just-dna-lite's reviser to adapt or decline. Every number is from dna-seq/longevity-loci at 6cc9de0; the sources are `rows/`, `module/` (the 2.0.0
build) and `docs/DECISIONS.md` there, and the v1 audit in the manuscript's own Table S14. The module is on the registry's test
instance only; if the paper goes out before it is in production, say so. Its findings count the 169 loci curated by
that date (A 15, B 75, C 43, D 36); the 2.0.0 build in this pull request holds the first 164 (A 15, B 73, C 41, D 35), and
the paper should state whichever it describes.

---

### 3.x The Longevity Map, rebuilt from the evidence

The default Longevity Map module began as a port of HAGR's LongevityMap (build 3, frozen in June 2017). Our audit of
that port (Table S14) found at least one error in 462 of its 528 rsIDs: weights given to results that were not
significant (222 rsIDs), a direction inverted against a cited study (124), a sex- or subgroup-only effect applied to
everyone (51). Most inverted directions entered in the hand weighting, not in HAGR itself, and 281 rows rested on a
single 2012 study. The module also missed most of what genome-wide studies have since found: about 7 of ~150
genome-wide longevity rsIDs were present.

We therefore rebuilt it. Each of 161 candidate loci, drawn mostly from genome-wide studies of 2014–2026 (extreme-survival
meta-analyses, about a million parental lifespans, multivariate healthspan, East Asian cohorts), was re-read against its
sources and written as one row per locus. A locus is graded on its own lead variant's evidence: tier A needs
P < 5×10⁻⁸ in a study of at least 100,000 people, an independent replication and no heterogeneity red flag; tier B
falls short on one of these; C is suggestive; D is contradicted, for example by a well-powered test in the same
ancestry. Six further axes are reported beside the tier and never summed into a score: the system a locus acts
through, pleiotropy, age of action, outcome profile (healthspan, lifespan, exceptional survival), actionability, and
ancestry and sex. Every genotype of a scored locus has a row, the common genotype being the neutral reference. APOE
is scored once, as its ε2/ε3/ε4 pair, rather than through its proxies counted as separate findings.

The curation was done by a team of AI agents with standing roles (a scout searching the literature, a curator
writing rows, a lead running checks and reviews, a module builder), steered by the maintainers through chat and a
question queue. Every claim cites a passage quoted verbatim from its source, and each quote (6,765) is located in the
cached text by machine. Each batch of about ten rows was read by three independent adversarial reviewers, every
finding settled as a recorded decision with the alternative it rejected. A sweep of the literature from 2015 to
October 2026 (22,759 records screened) added papers to 18 rows and five new loci.

**What the evidence says about the genetics of human longevity.**

1. *Few loci meet a strict bar.* Of 169 loci, 15 reach tier A, 75 tier B, 43 tier C and 36 tier D. Most genome-wide
   longevity loci rest on one study with no independent replication.
2. *Much apparent consensus is one cohort counted several times.* The loci the field treats as established
   reach genome-wide significance in several publications, but nearly all of those draw on UK Biobank; counted as
   independent groups of people, every such locus except APOE was found in one.
3. *Strong seed grades did not always hold.* ZW10/TTC12 fell from A to B on heterogeneity between samples;
   CELSR2/SORT1 and CHRNA3/5 fell from A when an independent sample did not confirm them. FOXO3, a classic longevity
   gene, is tier B: real and replicated, but genome-wide only in a multivariate test, never in a single scan.
4. *The candidate-gene era left little behind.* Of v1's 528 rsIDs, five lead or tag a locus of the new module (two
   at APOE, and FOXO3, KL and the EBF1 region).
5. *Most loci act through no system the evidence names.* 111 of 169 are general ageing; the named ones are mostly
   heart and vessels (17) and metabolism (9), then smoking and lungs, immune and inflammation, and skin. A further 19
   loci of biological-ageing markers (telomere length, epigenetic clocks, loss of Y) are shown and scored by nothing,
   since a marker is not lifespan.
6. *When a variant acts is mostly unknown* (157 of 169 loci), and the evidence is mostly European.

The module contrasts with v1 at the level a reader sees (Table x): 528 against 163 rsIDs, 1,022 against 489
genotype rows, 975 protective, 47 risk and no neutral rows against 113, 99 and 277, a summed "net weight" against none,
and 0 against 6,765 located quotes. The fewer rows reflect one lead per signal and the evidence actually carried, not
narrower coverage: the genome-wide loci v1 lacked are all present.

**Limits.** Agents did the reading. Quotes are checked mechanically, but whether a result replicates another is a
judgement, and the reviews will not have caught every mistake; the v2 rows have not yet had an independent audit by the
method of Table S14, whose own verdicts were read by AI agents and are provisional. A tier grades the evidence for an
association; it is not an effect size and not a prediction for one person.

*Source: github.com/dna-seq/longevity-loci (rows, decisions, module build); the 2.0.0 build figures: 164 loci, 163
rsIDs, 489 genotype rows, 679 study rows citing 51 papers.*
