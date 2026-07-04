# Instructions for Ethics Review — Just-DNA-Lite / just-prs Manuscript

**To:** Ethics Committee, Institute of Biochemistry of the Romanian Academy
**From:** The Just-DNA-Lite authorship team (corresponding: Anton Kulaga; supervising: Robi Tacutu)
**Re:** Request for an ethics statement to accompany the manuscript
*"Just-DNA-Lite: an AI-Powered Open-Source Platform for Personal Genome Analysis"*
**Date:** _[to be filled by committee]_

---

## 1. Purpose of this document

This is a scoping brief that tells the committee **exactly what to assess** and **what kind of statement we are asking for**, so that the review can be completed quickly and the resulting statement maps precisely onto what the study actually did.

We are submitting a **software / methods paper**. It describes an open-source bioinformatics tool and benchmarks its performance. It is **not** a study that recruits human participants, collects new biological samples, or performs any clinical intervention. We nevertheless want a formal ethics statement on institutional letterhead because (a) the work processes human genomic data, and (b) reviewers of genomics journals increasingly expect an explicit ethics declaration regardless of study type.

Please read Sections 2–4 (what the work is and what data it touches), then act on the **explicit instructions in Section 5**. Sections 6–8 give you ready-to-adapt statement text so that minimal drafting is required on your side.

---

## 2. Plain-language description of the work

Just-DNA-Lite is an open-source program that runs **entirely on the user's own computer**. A user provides a genome file (a standard VCF produced by DNA sequencing) and the program annotates the variants in that file against **openly available scientific data sources** — for example the LongevityMap database, the PGS Catalog of polygenic scores, and Ensembl variation data. These sources include peer-reviewed databases, public repositories, and published literature (not exclusively peer-reviewed papers). It then produces a report, which can include risk-associated polygenic scores and, optionally, a plain-language AI explanation requested by the user.

Key facts relevant to ethics:

- **No data leaves the user's machine.** There is no central server, no upload, and no transmission of genomic data to the authors or any third party during normal use. The software is local-first and GDPR-friendly by design (the data controller is the user).
- **The software annotates the user's variants against openly available data sources.** These include peer-reviewed scientific literature, public biological databases (e.g. the PGS Catalog, LongevityMap, Ensembl), and open data/code repositories. We do **not** claim that every underlying data point originates from a peer-reviewed publication — some annotations are drawn from public databases or open repositories rather than journal papers — and each module records its own provenance. The software joins these existing data to the user's variants; it does not itself discover new gene–disease relationships.
- **The software does compute research-grade, risk-associated scores and offers optional AI interpretation — but it is not a medical device.** Polygenic risk scores estimate where a user falls, relative to a reference population, for disease- and trait-associated risk; and the user may optionally send a result to a large language model *of their own choice* to obtain a plain-language explanation. That AI explanation can include general, non-prescriptive suggestions — for example, confirming a finding with a clinical-grade test, consulting a physician or genetic counselor, or general lifestyle and exercise information. The software does **not** prescribe medications, dosages, or specific medical treatments; it does **not** perform clinical diagnosis; and the developers do **not** author or control the third-party LLM output. By design, the interpretive layer is oriented toward directing users *to* professional medical validation, not toward replacing it (see Section 7).
- **`just-prs`** is the polygenic-risk-score component of the platform, also released as a standalone toolbox usable from the command line, from Python, and from AI assistants (via a Model Context Protocol server and an agent skill). It uses the same public PGS Catalog data and produces the same kind of research-grade, risk-associated output with the same optional AI interpretation.

---

## 3. Human genomic data used in the manuscript

The manuscript reports benchmarks. To run those benchmarks the authors used **two** human whole-genome files, and **no others**:

1. **An author's own genome.** One of the authors (Anton Kulaga) used his **own** whole-genome sequence. As the data subject and an author, he consents to its use and has additionally made this genome publicly available on Zenodo ([https://zenodo.org/records/18370498](https://zenodo.org/records/18370498)) for reproducibility. There is no third-party data subject involved.

2. **A second author's own genome.** Livia Zaharia, a co-author of the manuscript, provided her own whole-genome sequence for testing the software and consented to its use; she has additionally made it publicly available on Zenodo ([https://zenodo.org/records/19487816](https://zenodo.org/records/19487816)) under an open licence. As with the first genome, the data subject is an author using her own data — there is no third-party or recruited participant involved.

In other words, **both genomes used belong to authors of this paper, who consented to the use of their own data and have publicly released it.** All other inputs are **openly available reference data** (the 1000 Genomes Project phase 3 reference panel, the PGS Catalog, LongevityMap, Ensembl), distributed publicly for research use. These sources are a mix of peer-reviewed databases, public repositories, and published literature; not all are peer-reviewed journal publications.

**What is NOT in this manuscript (please note explicitly):**

- There is **no patient cohort** and **no recruitment** of human subjects.
- There is **no collection of new biological samples**.
- There is **no processing of third-party identifiable health records**.
- The **ROGEN Romanian genomic cohort is NOT part of this work.** It is mentioned in the manuscript only as planned *future* work; the cohort does not yet exist (it is expected in roughly 1–2 years) and, when it does, it will carry its **own separate consent, governance, and ethics approval**, independent of anything in this paper. The committee is **not** being asked to assess the future cohort here.

---

## 4. Why we believe this is not human-subjects research (the case for exemption)

We respectfully submit the following reasoning for the committee's consideration:

- The unit of study is **software performance**, not human beings. The "results" are runtimes, memory usage, and numerical concordance between scoring engines — not findings about people.
- The only human genomes used belong to **two of the authors**, each consenting to the use of their own genome, both of which are publicly released on Zenodo under open licences.
- No participants were recruited, no samples were newly collected, and no identifiable third-party data were processed.

On this basis the work would, in most frameworks, qualify as **not constituting human-subjects research**, or as **exempt** from full ethics review. We submit this as our reasoning and ask the committee to reach its own determination — confirming exemption if it agrees, or, if its procedures prefer it, issuing a formal approval instead (see Section 5).

---

## 5. What we are asking the committee to do — explicit instructions

Please review the description above and then issue **one** signed statement on institutional letterhead. We have deliberately framed this so the committee can choose whichever instrument fits its own procedures:

> **Option A — Exemption / "not human-subjects research" determination.**
> Confirm that, based on the description provided by the authors in Sections 2–4, the work described in the manuscript does not constitute human-subjects research and is therefore exempt from formal ethics approval, noting that the only genomes used belong to consenting authors and are publicly released.

> **Option B — Formal ethics approval.**
> If the committee's procedures require treating this as a reviewable study, issue a formal approval (with a reference number and date) covering the use of the two authors' own genomes for software benchmarking, on the understanding that no other human subjects or samples are involved.

**Either option is acceptable to us.** Template wording for both is provided in Section 6 so that the committee only needs to confirm, edit, and sign.

In addition to A or B, we ask that the statement **also note the points in Section 7** (Research-Use-Only communication). We are asking the committee to record that the disclaimers are present and prominent — not to certify that they are sufficient to prevent misuse, which is not something we are asking the committee to vouch for.

### Checklist — items the committee may note in its statement

1. [ ] The work is software development and benchmarking, not human-subjects research **(or)** is approved as a study (state which).
2. [ ] The only human genomes used belong to two of the authors, each consenting to the use of their own (publicly released) genome.
3. [ ] No participant recruitment, no new sample collection, and no third-party identifiable health data are involved.
4. [ ] All other data are openly available reference sources (public databases, open repositories, and published literature — not necessarily all peer-reviewed papers).
5. [ ] As described by the authors, the software processes data locally and, in normal use, transmits no genomic data to the authors or third parties. (We are not asking the committee to make a legal determination of GDPR compliance.)
6. [ ] The software is designated **Research-Use-Only** and displays disclaimers to that effect in the materials reviewed — noting their presence and prominence, without certifying their sufficiency (see Section 7).
7. [ ] The ROGEN cohort and any future clinical application are **out of scope** for this statement and will be governed separately.

---

## 6. Ready-to-sign statement templates

The committee may copy, edit, and sign whichever applies.

### 6A. Exemption / non-applicability statement (template)

> Based on the manuscript *"Just-DNA-Lite: an AI-Powered Open-Source Platform for Personal Genome Analysis"* and the description of its methods and data provided by the authors, the Ethics Committee of the Institute of Biochemistry of the Romanian Academy finds that the work constitutes the development and computational benchmarking of open-source bioinformatics software and does **not** constitute human-subjects research, as it involves no participant recruitment, no collection of new biological samples, and no processing of third-party identifiable data. The only human genomic data used are the personal genomes of two of the authors, each used with their consent and publicly released under open licences. The Committee therefore considers the study **exempt from formal ethics approval**. The Committee further notes that, as described by the authors, the software runs locally and is designated by the authors for research and educational use only, not for clinical or diagnostic purposes.
>
> _Signature, name, title, date, reference number_

### 6B. Formal approval statement (template)

> The Ethics Committee of the Institute of Biochemistry of the Romanian Academy has reviewed and **approves** the use of human genomic data described in the manuscript *"Just-DNA-Lite: …"* for the purpose of software development and benchmarking. The data comprise the personal genomes of two of the authors, each used with their consent and publicly released under open licences. No other human subjects, samples, or identifiable data are involved. Approval reference: _[number]_, dated _[date]_.
>
> _Signature, name, title, date_

---

## 7. Research-Use-Only communication — for the committee to note

This is the ethical core of the tool. We ask the committee to **note** how it is handled — specifically, to record that the Research-Use-Only designation and the disclaimers below are present and prominent in the materials reviewed. We are **not** asking the committee to certify that these safeguards are sufficient to prevent all misuse; that is not a judgment we are asking it to vouch for. The platform's guiding principle is *transparency with honesty about limitations*: it shows the user everything, including research-grade risk scores, **while making clear that these must never be used for medical decisions on their own.**

The software communicates the following in the materials provided (the user interface, the README liability notice, and a dedicated "science literacy" page). We ask the committee only to record that these disclaimers are present and prominent.

**An honest note on what the tool does produce.** We want the committee to assess the tool as it actually behaves, not an idealized version. The platform *does* compute disease- and trait-associated risk scores, and it lets the user optionally pass a result to a large language model of their choice for a plain-language explanation. That AI explanation can include general, non-prescriptive suggestions — most often a recommendation to confirm a finding with a clinical-grade test or to consult a physician or genetic counselor, and sometimes general lifestyle or exercise information. It does not prescribe drugs, dosages, or specific medical treatments, and the explanatory prompts are deliberately written to foreground uncertainty and to push the user toward professional validation. We consider this orientation — *"this is research-grade information; go confirm it clinically"* — to be the responsible way to surface risk information, and we ask the committee to evaluate it on that basis rather than on a claim that the tool says nothing at all.

**The single most important message we communicate to users:**

> Results from this software are **research-grade, not clinical-grade**. They describe statistical patterns in study populations, not your individual fate. **Never make a medical, health, or treatment decision based only on this tool.** If a result concerns you — especially if it aligns with your family history — the correct next step is to consult a physician or certified genetic counselor and, where appropriate, obtain an orthogonal **clinical-grade** test from a certified laboratory.

### Concrete examples of how relying on this software alone can cause harm

We provide these so the committee can see that the warnings are specific and substantive, not boilerplate. We recommend the committee confirm that examples of this kind are conveyed to users.

1. **Sequencing false positives.** Raw VCF files contain false-positive variant calls. A single exploratory sequencing run is **never** trusted clinically without orthogonal validation. A user who sees a "pathogenic" variant in this tool and concludes they have a disease may be reacting to a sequencing artifact that a confirmatory Sanger or qPCR test from a certified lab would not reproduce.

2. **"Pathogenic" labels are often false alarms.** Studies of healthy people show the average person carries dozens to hundreds of variants flagged "pathogenic" in research databases. Many are later reclassified, or have very low penetrance (they cause disease in only a tiny fraction of carriers). Treating such a flag as a diagnosis can cause unnecessary fear, unnecessary procedures, or harmful self-directed changes to medication or lifestyle.

3. **A polygenic risk percentile is a rank, not a probability or a diagnosis.** Being in the "90th percentile" for a trait means you rank above 90% of a *reference population* on a linear statistical score — it does not mean a 90% chance of developing the condition. Real biology involves gene–gene and gene–environment interactions that a weighted sum cannot capture. Acting as though a percentile were a personal probability is a serious misinterpretation.

4. **Ancestry mismatch breaks the numbers.** Most polygenic scores were derived from predominantly European cohorts. For a user of different ancestry, the percentile can be badly miscalibrated, so a "high" or "low" result may be an artifact of population mismatch rather than a real signal.

5. **Pharmacogenomics is the highest-stakes case.** Some variants (e.g. *CYP2C19* affecting clopidogrel activation, or *HLA-B\*57:01* predicting abacavir hypersensitivity) have genuine clinical implications. A user must **never** start, stop, or change a medication based on this tool. Such findings must be interpreted by a clinician with a clinical-grade test; acting on a research-grade hit could directly endanger the user.

6. **AI-generated annotation modules are first drafts.** Some modules are generated by AI agents reading the literature. They are explicitly labeled as such and **will contain mistakes**; cross-model consensus reduces but does not eliminate errors. They should be treated as lower-confidence starting points, not authoritative sources.

**The takeaway we want reflected in the statement:** *the danger is not in looking at one's own genome — people have the right to do that — the danger is in acting on research-grade results without clinical validation.* We ask the committee to note that the software discloses this distinction prominently in the materials reviewed (again, recording that the disclaimers are present, not certifying their sufficiency).

### Suggested committee wording on Research-Use-Only

> The Committee has reviewed the software's user-facing disclaimers and notes that the platform is clearly and prominently designated as a research and educational tool that is **not** a medical device and is **not** intended for clinical or diagnostic use. The Committee notes that the software computes risk-associated polygenic scores and offers optional, user-initiated AI-generated plain-language interpretation; any suggestions surfaced through that interpretation (such as recommending clinical confirmation, consultation with a physician or genetic counselor, or general lifestyle information) are general and non-prescriptive, do not constitute medical advice or a prescription, and are accompanied by explicit statements of the outputs' research-grade nature. The software explicitly warns users that its outputs are research-grade rather than clinical-grade, that polygenic scores are population-relative statistics and not individual diagnoses or probabilities, and that no medical decision should be made on the basis of its output without consultation of a qualified clinician or genetic counselor and orthogonal clinical-grade testing. The Committee notes that these statements of intended use and limitations are present and prominent in the materials reviewed.

---

## 8. Supporting documentation we can provide on request

- Written confirmation of consent from both genome contributors — both are co-authors who agreed to the use of, and have publicly released, their own genomes.
- The authors' public releases of their own genomes on Zenodo ([18370498](https://zenodo.org/records/18370498); [19487816](https://zenodo.org/records/19487816)).
- The full manuscript and its "Scope," "Limitations," and "Data Privacy" sections.
- Screenshots / text of the in-application Research-Use-Only notices and the "science literacy" page.
- The open-source code repositories for independent audit (the software is AGPL v3).

---

## 9. One-paragraph summary for the manuscript's Ethics section (to finalize once the statement is issued)

> **Ethics statement.** This work describes the development and computational benchmarking of open-source bioinformatics software. It involved no recruitment of human participants and no collection of new biological samples. Benchmarks used the personal genomes of two of the authors, each used with their consent and publicly released on Zenodo under open licences ([18370498](https://zenodo.org/records/18370498); [19487816](https://zenodo.org/records/19487816)); all other data are public reference databases. The Ethics Committee of the Institute of Biochemistry of the Romanian Academy reviewed the study and determined that it _[does not constitute human-subjects research and is exempt from formal approval / was approved under reference no. XXX]_. The software processes all data locally, transmits no genomic data to the authors or third parties, and is designated for research and educational use only; it is not a medical device and is not intended for clinical or diagnostic use.

---

*Prepared to give the committee a precise, low-effort path to a statement that accurately reflects the study. Please contact the corresponding author with any questions or requests for additional documentation.*
