# Supplementary Table S14 (continued). Audit of the Generation I Longevity Map module and of its LongevityMap source

This part of the audit covers the Longevity Map module (`just-dna-seq/longevitymap@1.2.0`; 528 rsIDs, 1,022 genotype
rows, 671 study rows citing 126 papers) and the LongevityMap records it was built from. LongevityMap is part of the
Human Ageing Genomic Resources (HAGR; Tacutu et al., 2018). Unlike the four modules above, this module passed through
four layers before it reached v1.2.0, and an error can enter at any of them. Each finding is therefore assigned to the
layer that introduced it. Every finding is listed in `S14_generation1_longevitymap_audit.csv`.

| Layer | What it holds | File checked |
|---|---|---|
| Source paper | what the study reported | PubMed, PMC, publisher full text |
| LongevityMap (HAGR) | one record per study and variant: identifier, gene, population, design, conclusion, "Significant"/"Non-significant" | HAGR entry pages (all 3,457 live records, read 2026-11-03) and the Build 3 download (24 June 2017) |
| Generation I import | the HAGR records copied into the OakVar module database; named variants (e.g. "E2/E3/E4", "I/D", "Q192R") replaced by rsIDs | `data/modules/just_longevitymap/longevitymap.sqlite`, table `variant` |
| Generation I curation | for each significant record: the genotypes, a weight for each (0, ±0.5, ±1) and a per-row "gene prioritisation" factor | `data/longevity_map.tsv` (626 rows, 15 marked skip) |
| Generation I aggregation | one weight per genotype and rsID, used for scoring: curated weight × prioritisation factor | `longevitymap.sqlite`, table `allele_weights` (1,043 rows) |
| v1.2.0 port | conversion to the current module format with strand repair | `variants.csv`, `studies.csv`, `v1_port.log` |

## How the content was checked

1. **Lineage.** Every v1.2.0 genotype row was joined back through each layer. The aggregation step was reproduced
   exactly: for all 1,027 `allele_weights` rows that carry an ordinary genotype, the weight equals the curated weight
   times the row's prioritisation factor (the other 16 are heterozygote rows stored as a two-letter allele). The port
   changed no weight and touched alleles only at the 22 rsIDs named in its log, so any other error in v1.2.0
   was already present in Generation I.
2. **HAGR records.** The Generation I database was compared field by field with HAGR's own entry pages.
3. **Reference genome.** Each rsID was checked against Ensembl (REST, release current on 2026-11-03): alleles, merge
   status, the genes it overlaps, and, for the coding variants that the import or the curation translated from a name
   into an rsID, the protein change on the canonical transcript.
4. **Source papers.** Each of the 626 curated rows was read against its paper by AI agents working in parallel. They
   checked whether the rsID is the variant studied, which allele or genotype the paper associates with longevity, in
   which sex or subgroup, whether the result was significant, and whether the v1.2.0 genotype weights agree after strand
   is accounted for. Each verdict carries a quotation from the source. 509 rows
   were read in full text, 116 from the abstract only and 1 from the title.
   For Sebastiani et al. 2012 (PMID 22279548; 281 rows), the direction was taken from the allele and genotype frequencies
   in centenarians and controls in its Table S1, because the paper names no longevity allele per SNP.
5. **Current GWAS.** The v1.2.0 rsIDs were compared with the 145 rsIDs that have genome-wide-significant
   (p < 5×10⁻⁸) associations with longevity, parental lifespan, healthspan or age at death in the GWAS Catalog.

The error, outdated and note classes are defined as in the first part of this table. Five error categories and four
note categories are added because this module raises cases the other four did not: E7 (a sex- or subgroup-only result
applied to everyone), E8 (the cited study used a recessive, dominant or heterozygote model but the module scores
additively, or the reverse), E9 (the rsID is not the variant the study tested), E10 (gene label wrong), E11 (cited
evidence lost at the port), N6 (strand-ambiguous SNP), N7 (transcription defect without effect), N8 (record added by
Generation I, not present in HAGR) and N9 (studies with conflicting results merged into one direction without a flag).

## Summary

**Per rsID.** Each of the 528 v1.2.0 rsIDs is counted once, under its most serious finding still present:

| Most serious finding for the rsID | rsIDs | of which only from Sebastiani et al. 2012 |
|---|---|---|
| E9 rsID is not the variant studied | 4 | 0 |
| E1 Direction inverted relative to at least one cited study | 124 | 82 |
| E5 Weighted genotype cannot be called (allele not assayed or not at the locus) | 32 | 17 |
| E6 Weighted although the cited result is not significant | 222 | 178 |
| E7 Sex- or subgroup-only effect applied to everyone | 51 | 0 |
| E8 Genetic model differs from the cited study | 18 | 0 |
| E10 Gene label wrong | 4 | 0 |
| E11 Cited evidence lost at the port | 6 | 0 |
| E4 Citation error | 1 | 0 |
| No error found | 50 | 0 |
| Could not be verified | 16 | 0 |
| **Total** | **528** | **277** |

**Per row of the source papers** (626 curated rows):

| Verdict | Sebastiani et al. 2012 rows | Other studies' rows |
|---|---|---|
| agrees with the paper | 2 | 107 |
| direction inverted | 82 | 50 |
| wrong variant or allele | 16 | 9 |
| weighted, not significant | 181 | 52 |
| subgroup result applied to all | 0 | 70 |
| genetic model differs | 0 | 24 |
| HAGR record misstates the paper | 0 | 4 |
| strand unresolvable | 0 | 2 |
| could not be verified | 0 | 27 |
| **Total** | **281** | **345** |

**By layer.** Where each finding entered (rows of the CSV; one row per study record or per mechanical finding):

| Category | HAGR | HAGR + G-I import | G-I import | G-I curation | G-I curation + port | G-I aggregation | v1.2.0 port | paper |
|---|---|---|---|---|---|---|---|---|
| E1 risk direction inverted (weight sign) |  |  |  | 127 |  | 4 |  | 1 |
| E4 citation or transcription error | 4 |  |  |  |  |  |  |  |
| E5 genotype not representable (allele not assayed or not at the locus) |  |  |  | 53 |  |  |  |  |
| E6 weight inconsistent with the cited evidence | 182 |  |  | 51 |  |  |  | 1 |
| E7 sex- or subgroup-only effect applied to everyone | 7 |  |  | 63 |  |  |  |  |
| E8 genetic model differs from the cited study | 1 |  |  | 23 |  |  |  |  |
| E9 rsID is not the variant studied | 1 | 1 | 4 |  | 1 |  |  |  |
| E10 gene label wrong | 6 |  |  |  |  |  |  |  |
| E11 cited evidence lost at port |  |  |  |  |  |  | 34 |  |
| N2 gene symbol not the overlapping gene | 1 |  |  |  |  |  |  |  |
| N5 conclusions are bare labels |  |  |  |  |  |  | 12 |  |
| N6 strand-ambiguous (A/T, C/G) SNP, direction unresolvable |  |  |  | 1 |  |  |  | 1 |
| N7 transcription defect without effect |  |  |  | 1 |  |  |  |  |
| N8 record added by Generation I curation (not in HAGR) |  |  |  | 4 |  |  |  |  |
| N9 conflicting study-level curations collapsed into one direction without a flag |  |  |  |  |  | 19 |  |  |

## A. Errors in the LongevityMap records

These are errors in HAGR's own records, inherited unchanged by Generation I. They were assessed only for the records
the module uses; the rest of LongevityMap was not assessed at this depth.

- **"Significant" for SNPs that were not individually significant.** HAGR records each of the 280 SNPs of the
  Sebastiani et al. 2012 genetic signature as a separate "Significant" association. The paper reports one SNP,
  rs2075650 in TOMM40, as genome-wide significant; the other 279 were selected as members of a multi-SNP predictive
  model without individual replication. HAGR's conclusion text describes this correctly at model level, but the per-SNP
  flag is what the module used. These 279 SNPs are 53% of the module's rsIDs. The same happens for AKT1 rs3803304
  (PMID 22929028), a failed replication recorded as "Significant".
- **Records citing the wrong paper.** In four records, the PMID and the study text belong to different papers:
  APOE (HAGR entry 68, PMID 11640949; the text matches PMID 11780357), IFNG +874 (entry 79, PMID 11857058; text matches
  11772518), HFE (entry 81, a duplicate of the HFE record of PMID 11857056 attached to PMID 11857058) and IL6 −174 (entry
  155, PMID 15241482; text matches 15130757). In PMID 22496539, the CETP and ADIPOQ records (entries 1948 and 1952) carry
  the conclusion written for MTP.
- **Wrong gene.** Six rsIDs are labelled TP53 although Ensembl places them on chromosomes 1, 2, 6, 9 and 22
  (rs10819510, rs1205035, rs13008689, rs1333049, rs3120819, rs9616906; five from the p53-pathway study PMID 22533364).
  Entry 226 (PMID 17048073), a study of the α1-antitrypsin Z allele (SERPINA1), is labelled SERPINE1 with no variant
  identifier. rs7959761 is labelled BHLHE41 but lies in an intron of SSPN.
- **Transcription and retired identifiers.** Entry 1887 gives rs28940479 for MEFV, where the variant studied is
  rs28940579, and entry 2086 gives rs37926683 for rs3792683. Twelve further records use rsIDs since merged in dbSNP. The
  Generation I import corrected all fourteen. The IFNG +874 records call +874T the low-producer allele; the source abstract names +874A.
- **Restrictions left out.** Seven FOXO3 records from PMID 20849522 omit that the associations passed correction in men
  only. One record describes a recessive effect as "G allele carriers" (rs2111699, PMID 22576335), and UCP2 rs659366 is
  listed although the paper excluded it from analysis (PMID 21340542).
- **Not updated.** No record cited by the module is newer than 2015, and HAGR has not released a build since 2017.

## B. Errors introduced by Generation I

**Import.** 118 of 3,457 HAGR records have a different identifier in the Generation I
database. 96 replace a named variant with an rsID. 14 replace a HAGR rsID that no longer resolves in Ensembl with a
current one, mostly dbSNP merges (for example IL6R rs8192284 → rs2228145, VDR rs10735810 → rs2228570); two of the old
identifiers, rs28940479 and rs37926683, look like typing errors. 8 rare-variant identifiers were left empty. Of the
named-variant translations made by the import or the curation, the 15 coding ones were checked against Ensembl's protein
annotation: 14 are correct once legacy numbering is allowed for (for example CETP I405V = p.Val422Ile, AGT M235T =
p.Met259Thr) and one, MEFV M694V, is not (below). Two import mappings are wrong. Every HAGR "E2/E3/E4" record was mapped to rs7412 alone: in v1.2.0, rs7412 carries
21 study rows, 16 of whose conclusions concern ε4, which is defined by rs429358. The SERPINE1/SERPINA1 record (entry
226) was given rs28940579, a MEFV variant, which the curation then relabelled MEFV.

**Curation.**
- **Direction.** 132 curated rows at 124 rsIDs favour the allele that the cited study found less
  often in long-lived people or associated with shorter survival (99 firm, 33
  provisional because they rest on an abstract or on an allele identified from population frequencies). 82 of these
  rsIDs come from Sebastiani et al. 2012. For 79 of those 82, the array's A/B allele letters in Table S1 are on the
  strand opposite to the GRCh38 forward strand, which suggests that the letters were transferred without being
  complemented. Examples from other studies: FOXO3 rs3800231, the most significant SNP of Flachsbart et al. 2009 (PMID
  19196970); FOXO3 rs2253310 and rs4946936 (PMIDs 19793722, 20884733); PON1 Q192R (rs662); SIRT1 rs7896005; GHSR rs572169;
  TTR T119M (rs28933981); and six ADARB1/ADARB2 SNPs (PMID 20011587).
- **Wrong variant.** MEFV M694V (HAGR identifier) was mapped to rs28940577, which Ensembl annotates as p.Met693Val;
  M694V is rs61752717. For TP53 Arg72Pro (rs1042522) and FOXO3 rs1268170, the weighted allele is not one of the two
  alleles the study genotyped, so the favoured genotype is never scored.
- **Genotypes that cannot be called.** At 26 rsIDs the curated genotype list mixes both strands (more than two bases for
  a biallelic SNP; for example KL rs9536314 `TT; TG; GG; TA; AA`). Sixteen Sebastiani SNPs are weighted on alleles the
  array did not assay. One genotype is written with Cyrillic letters (SOD2 rs2758331).
- **Evidence weighted beyond what it shows.** 63 rows apply a male-only or female-only result
  to everyone (for example PPARG Pro12Ala, AGT M235T, ADA*2, IFNG +874). 23 rows score a recessive,
  dominant or heterozygote effect additively. 51 rows weight a result that the paper reports as
  nominal only, not significant after correction, or not tested for that SNP (for example APOE rs7412 in PMID 23051975,
  which finds no ε2 effect on mortality).
- **Records added.** Four curated rows (IL6 rs1800795, CCL5 rs2280789, VEGFA rs699947 and rs2010963) have no HAGR record.
  Their verdicts are in the CSV; the VEGFA rows rest on the abstract only.

**Aggregation.** At 19 rsIDs, studies were curated with different genotype maps, but `allele_weights` keeps one
direction and the module gives no sign of the conflict. At four rows the per-study curation agreed with the paper but
the aggregated weight does not. For IL6 −174 (rs1800795), for example, PMIDs 15130757 and 15664628 favour G, yet v1.2.0
scores C/C and C/G as protective. The weights themselves are the curated value (0, ±0.5, ±1) times a prioritisation
factor with 63 distinct values between 0.04 and 1.0, so the homozygote always weighs twice the heterozygote. The factor
is 0.14 for 252 of the 281 Sebastiani rows. The method behind the factor is not recorded in these files.

## C. The v1.2.0 port: what it fixed and what it lost

**Fixed.** The port applied 30 recorded corrections and pruned 4 rows: strand duplicates of the same genotype, cDNA
spellings on minus-strand genes, and genotypes whose alleles do not occur at the locus. All 1,022 v1.2.0 genotypes use
alleles present at their GRCh38 locus. One correction rests on a wrong premise: the MEFV row was strand-corrected with
the justification that rs28940577 is p.Met694Val, which repeats the curation error above.

**Lost.** The port joined study records to variants on (PMID, rsID). The 34 curated study rows at 26 rsIDs whose HAGR
record carried a named identifier rather than an rsID were therefore dropped from `studies.csv`, although their weights
were kept. These include the studies behind CETP I405V, KL-VS, PPARG Pro12Ala, HFE C282Y, AGT M235T, TLR4 Asp299Gly and
IRS2 Gly1057Asp. Twelve rsIDs are left showing only non-significant studies beside a non-zero weight. Twenty genotype
rows at twelve rsIDs carry the placeholder conclusion "Longevity-associated variant", and sixteen rsIDs display a
conclusion taken from a non-significant study.

## Outdated content

Of the 145 rsIDs with genome-wide-significant longevity associations in the GWAS Catalog,
7 are in v1.2.0: rs2075650, rs2149954, rs405509, rs429358, rs4420638, rs7412, rs769449. All but rs2149954 (5q33.3) belong to the APOE–TOMM40–APOC1 cluster.
The other 521 rsIDs come from candidate-gene studies or from the Sebastiani signature, mostly published between 1993
and 2015. The worked example of Supplementary S13, FOXO3 rs2802292, is among the rows whose direction agrees with its
studies; its only finding is that one study's male-only effect is applied to everyone (E7).

## Points for the authors

These statements in the main text (Section 3.1) could not be reproduced from the files audited here:

- "curation and expansion with post-2017 literature, adding 50 new entries and editing 876 existing records". The
  Generation I database and curation file cite no study after 2015. Four curated rows have no HAGR record. The import
  differs from HAGR in 128 records: 118 identifiers, 9 association flags and
  1 study-design text. If the expansion exists elsewhere (for example in HAGR itself after June 2017, or in a later file),
  it did not reach the module.
- "assignment of weighted scores based on study quality, replication across populations and statistical significance".
  The weights are the product described above. Across rsIDs, the weight correlates weakly with the number of
  significant studies (Spearman 0.16). rsIDs with no significant study have a higher mean absolute weight (0.38) than
  rsIDs with one (0.20).

## How v2.0.0 handles them

The redesign of the module (`docs/longevitymap_v2/`) scores only genome-wide-significant, replicated loci. It keeps the
v1.2.0 rows as a legacy research view with their findings attached, so none is deleted silently. Errors still present
in v1.2.0 are listed as curation decisions rather than fixed in place, because each one changes an authored weight.

## Limitations

- The paper reading was done by AI agents and needs confirmation by a human curator before these numbers are
  published. Each verdict is a judgement; the CSV gives the quotation and the reasoning for each.
- 116 rows rest on abstracts, and for several papers the allele was identified
  from 1000 Genomes or gnomAD frequencies because the paper names only a "minor allele". These rows are marked
  `provisional = yes`. The per-SNP alleles of PMID 24462499 (29 rows) are in a supplement that could not be retrieved, and
  27 rows could not be verified at all.
- Direction for the Sebastiani SNPs is inferred from centenarian and control frequencies; the paper itself makes no
  per-SNP direction claim.
- HAGR records not used by the module were checked only for agreement with the Generation I database, not against their
  papers.
- Strand-ambiguous A/T and C/G SNPs on minus-strand genes (for example IFNG +874, RAGE −374, CYP1B1 V432L) were
  resolved by the gene-relative numbering convention; this is marked in the CSV.

## Files

- `S14_generation1_longevitymap_audit.csv`: one row per finding, with the columns of the first part of this table plus
  `layer`, `pmid`, `tsv_id` (the HAGR record id), `source_read`, `provisional`, `origin` and `secondary_codes`.
- `docs/longevitymap_v2/audit/`: the scripts that produced every number above, the per-row paper verdicts with their
  quotations (`evidence/paper_verification_*.csv`), the HAGR entry pages as read (`evidence/hagr_web_all.csv`) and the
  record-by-record comparison with the Generation I database.
