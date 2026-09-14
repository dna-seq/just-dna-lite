# Request for an ethics determination — Just-DNA-Lite manuscript

**Submitted to:** Ethics Committee of the Institute of Biochemistry of the Romanian Academy (IBAR)
**Applicant:** Anton Kulaga (doctoral researcher, IBAR and Rostock University Medical Center)
**Supervisors:** Robi Tacutu (IBAR), Georg Fuellen (Rostock University Medical Center)
**Project:** ROGEN — *Dezvoltarea cercetării genomice în România*, project code 324809
**Manuscript:** *Just-DNA-Lite: a Local-First, Open-Source Platform for Personal Genome Annotation and Polygenic Risk Scoring* (v0.3, Annex A)
**Date:** _[to be completed]_
**Reference number:** _[assigned by the Committee]_

---

## 1. The request, in short

The applicant asks the Committee for a **short written letter, with a reference number, stating
that the work described below does not require ethics approval**, because it is software
development and involves no research participants. Proposed wording is in Section 8; the Committee
need only adopt or amend it.

**Why the letter is needed.** The applicant's doctorate is examined in Germany. German medical
faculties expect a written ethics position on file for any work that touches human genomic data,
even where no approval was required. A letter from the home institution's committee saying so is
what closes the question there. Nothing beyond this letter is asked.

**What the work is.** Open-source software that a person installs on their own computer. It reads
a genomic variant file (VCF) the person already has, looks up each variant in published reference
databases (ClinVar, Ensembl, the Polygenic Score Catalog) and in curated annotation files, and
produces a report listing which published findings mention which of the person's variants. The
manuscript reports how fast the software runs and whether its calculations agree with an established
external tool (PLINK2). No participants were recruited, no samples were taken, no data were
collected from anyone. The only human genomes used are the applicant's own and a co-author's, both
of which the two of them had already published on Zenodo under open licences before this work.

---

## 2. What was done

### 2.1 The software

- A pipeline that looks up the variants in a VCF file against reference databases and against
  *annotation modules*. A module is a curated table of variants together with the published studies
  that report findings about them, distributed as a data file.
- A polygenic-score calculator (`just-prs`) implementing the standard weighted sum over scoring
  files from the Polygenic Score Catalog.
- A file format and compiler for those modules, so that curated content can be versioned and shared.
- A web interface that runs on the user's own machine. Optionally, a user who supplies their own
  API key can let an AI assistant operate the same functions for them (see Section 5).

All code is public under Apache/MIT licences at `https://github.com/dna-seq`.

### 2.2 The measurements reported in the manuscript

| # | What was measured | Human data used |
|---|---|---|
| 1 | Runtime and memory of the annotation pipeline, compared with the previous version of the same tool | One public genome (Zenodo 18370498) |
| 2 | Runtime of two polygenic-score engines over 100 PGS Catalog scoring models, compared with PLINK2 | The same genome |
| 3 | Numerical agreement between those engines and PLINK2 | The same genome |

These are engineering measurements. Their results are seconds, megabytes and agreement statistics.
The manuscript reports no genotype, no polygenic score value, no disease association and no health
statement about either individual.

### 2.3 Where the software runs

On the user's own computer. Reference databases are downloaded *to* the user; nothing is uploaded
*from* the user, and the research team receives no user data.

The team does host one public demonstration website, but it accepts no data from anyone: file
upload is disabled in that deployment, and the only genomes it can show are the two that are
already public (Section 3). A visitor cannot put their own genome into it.

---

## 3. All human data used

Exactly two human genomes were used. Both were already public before this work began, both were
put online by the person they belong to, and both people are authors of the manuscript.

| | Genome A | Genome B |
|---|---|---|
| Person | Anton Kulaga (the applicant) | Livia Zaharia (co-author) |
| Where published | Zenodo record 18370498 | Zenodo record 19487816 |
| Licence chosen by the person | CC0 1.0 (public domain dedication) | CC BY 4.0 (free reuse with attribution) |
| Deposited by | Anton Kulaga, himself | Livia Zaharia, herself |
| Data type | Whole-genome VCF, GRCh38 | Whole-genome VCF, GRCh38 |
| Used for | The three measurements in Section 2.2; demo website | Demo website; software testing |

Why this raises no ethics question:

1. **Nobody outside the author team is involved.** Neither person was recruited, screened or
   approached. Both are authors of the manuscript, using their own data.
2. **The data were already public, by the choice of the people concerned.** Each of them decided
   to publish their own genome, and did so before and independently of this work. Using the files
   here adds nothing to what is already online.
3. **Nothing about either person is reported.** The manuscript gives the number of variants in the
   file and how long the program took to process it, and nothing else.

The two Zenodo pages, which show who deposited each file and under which licence, are Annex B.

---

## 4. What is *not* part of this request

- **The planned ROGEN Romanian cohort (about 5,000 people).** The manuscript says, in its future
  directions, that population-calibrated polygenic scores for a Romanian cohort are planned within
  ROGEN. **That cohort has not been sequenced and no data from it exist.** Nothing was accessed,
  because there is nothing to access. That work will be submitted separately, with its own protocol
  and consent documents, before any sample is taken.
- **Clinical, diagnostic or predictive use.** The software is a research and educational tool. The
  manuscript says in several places that it does not establish clinical validity.
- **Returning results to anyone.** A user who runs the software sees their own output on their own
  computer; the team never sees it.
- **Any genetic testing service.** No sequencing, no samples, no laboratory, no fees, no medical
  advice.
- **Patients, clinical records, biobanks, or any identifiable dataset other than the two above.**
- **Workshops and tutorials.** The manuscript mentions (its Section 6.3) that the project runs
  hands-on workshops. Participants work on their own laptops with the two public genomes or a file
  they already own. Nothing is collected from them and nothing from workshops enters the manuscript.

---

## 5. Personal data (GDPR)

| Question | Answer |
|---|---|
| Are any research participants' personal data processed? | No. There are no participants. |
| Are genetic data processed? | Only the two genomes in Section 3. Each is used by the person it describes, or with that person's agreement as a co-author, and each was already published by that person. |
| Who is legally responsible for the genomic data of people who use the software? | The user. They run the software on their own computer on a file they already hold, for their own purposes. The team has no copy, no access and no way to obtain one. |
| Do any data leave the EU? | No genomic data. Reference databases are downloaded from public sources (Ensembl, PGS Catalog, HuggingFace, Zenodo); that is a download, not a transfer of anyone's personal data. |
| Can the software send data anywhere? | Only if the user deliberately connects an external AI assistant using their own API key. The genome file itself still stays on their computer, but the questions and results they send to that assistant may contain sensitive information. This is switched off unless the user sets it up, and the manuscript (its Section 6.2), the documentation and the interface all say so. |
| Is a data protection impact assessment (DPIA) needed? | In the applicant's view, no: the team processes no personal data of anyone other than the two co-authors, whose data are already public by their own choice. |

---

## 6. Risks considered

**A user misunderstands their own genomic information.** This is the real risk in this field. It
is documented in the literature for direct-to-consumer tests (Tandy-Connor et al., 2018) and for
risk estimates applied across ancestries (Manrai et al., 2016). What the software does about it:

- every reported association names the publication it comes from;
- a polygenic score is never shown as a single authoritative number. Alongside it the user sees
  which score model was used, how many of that model's variants were actually found in their file,
  which reference population the percentile is relative to, and how far different models for the
  same trait disagree with each other;
- the manuscript sets out plainly that heritability is a population statistic rather than an
  individual prediction, that these scores are linear approximations of non-linear biology, and
  that most source cohorts are European (its Sections 6.1 and 6.4);
- the software states that it is not a clinical instrument.

The manuscript is explicit that whether this presentation actually helps lay users has not been
tested and would need a usability study.

**Incidental findings.** The team generates no findings about anyone. The software reports to the
user alone, so no finding can reach the investigators and no duty to inform arises. The two
co-authors published their own genomes knowing what they contain.

---

## 7. Likely questions

**Is this research on human subjects?**
No. Nobody was recruited, nothing was done to anyone, and no data were collected from anyone. The
two genomes were already public, published by their owners, who are the authors.

**A whole genome identifies a person. Does that not change the answer?**
It does not. Both people put their own genomes online themselves, knowing this, and are authors
here. The files were public before this work, remain public, and nothing new about either person
is derived or reported.

**Are polygenic risk scores not health prediction?**
In this manuscript they are a numerical benchmark: the question asked is whether two calculation
engines agree with each other and with PLINK2. No score for any individual is reported.

**Could someone be harmed by using the software?**
The realistic harm is misunderstanding one's own data. Section 6 describes what is done about it.

**Will the ROGEN cohort need approval?**
The cohort does not exist yet: it has not been sequenced. When it goes ahead it will need approval,
and it will be submitted separately, with its own protocol and consent documents, before any sample
is taken.

---

## 8. Proposed wording of the letter

### Requested: determination that no approval is required

> The Ethics Committee of the Institute of Biochemistry of the Romanian Academy, having examined
> the application of Anton Kulaga concerning the manuscript *Just-DNA-Lite: a Local-First,
> Open-Source Platform for Personal Genome Annotation and Polygenic Risk Scoring*, records the
> following. The work is a software and methods development project. It involves no recruitment of
> participants, no intervention, no collection of data from any person, and no access to any
> clinical, cohort or biobank dataset. The only human genomic data used are two whole-genome files
> previously published by the individuals they describe, on their own initiative, under open
> licences (CC0 1.0 and CC BY 4.0); both individuals are authors of the manuscript. No
> individual-level genomic, phenotypic or health-related result is reported. No results are
> returned to any individual. The software runs on the end user's own equipment and the
> investigators receive no user data.
>
> The Committee therefore determines that the work does not constitute research on human subjects
> and **does not require the approval of this Committee**. The Committee has no ethical objection
> to the conduct or publication of the work as described.
>
> This determination covers the work described in the application. The Committee notes that the
> ROGEN cohort mentioned in the manuscript as a future direction has not been sequenced and that no
> data from it exist or were used. This determination does not extend to that future work or to any
> other identifiable dataset, which must be submitted separately.

### Fallback only, if the Committee's rules do not allow the letter above: favourable opinion

> The Ethics Committee of the Institute of Biochemistry of the Romanian Academy has reviewed the
> application of Anton Kulaga concerning the manuscript *Just-DNA-Lite: a Local-First, Open-Source
> Platform for Personal Genome Annotation and Polygenic Risk Scoring*, together with the manuscript
> and annexes. The Committee notes that the work involves no research participants; that the only
> human genomic data used are two whole-genome files self-published under open licences by
> individuals who are authors of the work; that no individual-level result is reported or returned;
> and that the software processes data locally on the end user's equipment without transmission to
> the investigators.
>
> The Committee issues a **favourable opinion** for the conduct and publication of the work as
> described, under reference _[number]_, dated _[date]_.
>
> The Committee notes that the ROGEN cohort mentioned in the manuscript as a future direction has
> not been sequenced and that no data from it exist or were used. This opinion does not extend to
> that future work or to any other identifiable dataset, which must be submitted separately.

---

## 9. Annexes

| | Document |
|---|---|
| A | Manuscript, v0.3 |
| B | Zenodo landing pages for records 18370498 (CC0 1.0) and 19487816 (CC BY 4.0), showing depositor and licence |
| C | Public repository index and software licences (`https://github.com/dna-seq`) |
| D | ROGEN project identification, code 324809 |

---

## Appendix (for the applicant, not part of the submission): ethics statement for the manuscript

To be inserted once the letter is issued.

**If the determination is issued:**

> **Ethics declarations.** This study involved no research participants, no recruitment, no
> intervention and no collection of data from any individual. The only human genomic data used
> were two whole-genome sequences previously published by the individuals they describe, on their
> own initiative, under open licences: Zenodo record 18370498 (CC0 1.0) and Zenodo record
> 19487816 (CC BY 4.0). Both individuals are authors of this manuscript. No individual-level
> genomic, phenotypic or health-related result is reported. The software described executes
> locally on the end user's own equipment; the authors operate no service that receives user
> genomic data and received none. The Ethics Committee of the Institute of Biochemistry of the
> Romanian Academy determined that the work does not constitute research on human subjects and
> does not require ethics approval (reference _[number]_, _[date]_). The ROGEN cohort referred to
> under future directions has not been sequenced and contributed no data to this work; it will be
> subject to separate ethics review.

**If a favourable opinion is issued instead:**

> **Ethics declarations.** This study was reviewed by the Ethics Committee of the Institute of
> Biochemistry of the Romanian Academy, which issued a favourable opinion (reference _[number]_,
> _[date]_). The study involved no research participants, no recruitment and no collection of data
> from any individual. The only human genomic data used were two whole-genome sequences previously
> published by the individuals they describe, on their own initiative, under open licences: Zenodo
> record 18370498 (CC0 1.0) and Zenodo record 19487816 (CC BY 4.0). Both individuals are authors of
> this manuscript. No individual-level genomic, phenotypic or health-related result is reported.
> The software described executes locally on the end user's own equipment; the authors operate no
> service that receives user genomic data and received none. The ROGEN cohort referred to under
> future directions has not been sequenced and contributed no data to this work; it will be subject
> to separate ethics review.
