# Just-DNA-Lite Manuscript Strategy

> **Venues as of October 2026** are in the last section, [Venues, October 2026](#venues-october-2026). The fit analysis before it still stands.

Assessment of `docs/manuscript/manuscript_draft_v2.md`, focused on weak points, revision ideas, risks, and journals with recent impact factor above 5.

## Executive Verdict

The manuscript has a publishable core: a local-first, open-source genome annotation platform with strong performance claims, PRS computation, and a useful extensibility model. The largest weakness is not lack of content, but lack of discipline: the draft tries to be a software paper, PRS methods paper, AI-agent paper, ethics essay, and platform manifesto at once.

Current best realistic target: **Bioinformatics**.

Scientific potential: **High**  
Submission readiness: **Medium**  
Scope-control risk: **High**

## Main Strategic Choice

Submit as a rigorous bioinformatics software paper, not as a clinical genomics, longevity, or AI manifesto paper. The safer core claim is: fast, transparent, local VCF annotation plus PRS computation with reproducible benchmarking and an extensible module format.

The manuscript already contains two important comparisons:

- **OakVar / Generation I** in Section 5.1, including runtime table and 172-fold speedup.
- **PLINK2** in Section 5.2, including runtime, memory, and concordance tables for PRS computation.

The remaining comparison gap is not absence of OakVar or PLINK2 evidence. It is broader positioning: the paper should make clearer how Just-DNA-Lite differs from VEP, ANNOVAR, OpenCRAVAT/OakVar, Galaxy, PRSice, PGS Catalog workflows, and commercial services in terms of scope, user interface, local privacy, module extensibility, PRS support, and agentic access.

## Weak Points To Fix

| Issue | Severity | Why it matters | Best fix |
| --- | --- | --- | --- |
| Too many centerpieces | High | The draft simultaneously sells local genome annotation, PRS benchmarking, MCP/agentic access, and AI-generated modules. Reviewers may struggle to identify the main scientific contribution. | Choose one lead claim. Best route: local-first extensible genome annotation platform, with PRS and AI module creation as supporting capabilities. |
| AI module validation is too thin | High | The text claims no manual corrections and reduced hallucination, but validation is anecdotal across three scenarios. | Add an evaluation set: papers with known variant tables, expert adjudication, precision/recall, provenance errors, genotype-direction errors, and ablation of solo versus team mode. |
| Clinical/regulatory sensitivity | High | The right-to-read and anti-gatekeeping section is strong rhetorically but can trigger medical-genomics reviewers if it sounds like advocacy over risk control. | Shorten and make it empirical: local processing, transparent uncertainty, no diagnosis, no recommendation, explicit user-facing safeguards. |
| Benchmark breadth | Medium | Annotation speed is compelling but mostly one personal WGS, one hardware profile, and Gen I comparison. PRS validation is stronger but still has unresolved match-rate discussion. | Add public-genome benchmarks if feasible, include warm/cold cache status, and explain the 50-54% PRS match rate. |
| Unresolved TODOs | Medium | Visible TODOs in benchmark interpretation, ancestry estimation, bibliography, funding wording, and figure placeholders signal pre-submission immaturity. | Remove all TODOs before journal submission; convert uncertain claims into limitations or omit them. |
| Default modules look narrow | Medium | Only five expert modules plus one AI-generated module may look small for a platform paper unless framed as examples. | Emphasize module format and ecosystem mechanics; avoid implying comprehensive clinical coverage. |
| Citation and novelty risk | Medium | Some claims depend on current tools, MCP/agent workflows, and 2025-2026 sources; journals may ask what is novel versus integration. | Add a concise landscape table comparing scope and capabilities against established tools and workflows. |

## Highest-Leverage Edits

| Priority | Edit | Concrete action |
| --- | --- | --- |
| 1 | Refocus title and abstract | Replace the AI-powered headline with a methods/software title around local, extensible genome annotation and PRS. |
| 2 | Add a state-of-the-art positioning table | Show exactly where the platform differs from VEP, ANNOVAR, OpenCRAVAT/OakVar, Galaxy, PGS Catalog tooling, PRSice, PLINK2, and commercial services. |
| 3 | Harden AI claims | Turn the AI module creator from a promotional feature into a measured pipeline with error classes and expert review outcomes. |
| 4 | Broaden reproducible benchmarks | If feasible, run at least two public genomes and include scripts, warm/cold cache status, input size, storage, and module selection. |
| 5 | Move philosophy down | Keep the ethical argument, but make it shorter and less confrontational in the main text; preserve detail for Discussion or supplement. |
| 6 | Prepare journal-specific versions | For software journals, lead with benchmarking and usability; for medical genomics journals, lead with privacy, safeguards, and human-genomics utility. |

## Submission Risks

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Desk rejection as insufficiently novel | High | Foreground the no-code module format, fsspec discovery, local-first performance, PRS concordance, and agent-access architecture as a coherent system. |
| Rejection as clinical interpretation | High | Avoid individual-risk language, disease prediction claims, and overconfident PRS interpretation. Keep the "joins VCF against databases" framing. |
| AI hype skepticism | High | Replace claims of trustworthy automation with measured accuracy, provenance, expert review, and clear failure modes. |
| Impact-factor target mismatch | Medium | Some best-fit software venues are below IF 5. If IF >5 is mandatory, Bioinformatics and Genome Biology are the realistic core targets. |
| Maintenance burden | Medium | NAR or Genome Biology reviewers will care that web resources, datasets, and documentation remain live and maintained. |

### Journal-Specific Risks

| Journal | Specific risk | How to reduce it |
| --- | --- | --- |
| Bioinformatics | Reviewers may treat the paper as an ordinary software tool paper and ask whether the algorithms are novel enough beyond integration of Polars, DuckDB, Dagster, PGS Catalog, and existing annotation databases. | Lead with the system-level novelty: no-code modules, fsspec-discoverable annotation ecosystem, local privacy, PRS integration, reproducible benchmarks, and agentic access as one coherent architecture. Keep the AI-module creator as a supporting feature, not the main novelty claim. |
| Genome Biology | High bar for broad utility and state-of-the-art comparison. Reviewers may ask for stronger validation, more public datasets, and clearer evidence that the tool is a major advance beyond existing genomic software. | Submit only after adding a compact landscape comparison and broader reproducibility package. De-emphasize manifesto language. |
| Genome Medicine | Highest risk of being read as clinical interpretation or consumer genetic testing. The personal-genome/right-to-read framing could trigger regulatory and clinical-safety objections. | Use only if the manuscript is rewritten around privacy-preserving research genomics, safeguards, no clinical claims, and strong limitations. Avoid as first submission unless the medical framing is substantially tightened. |
| Nucleic Acids Research | The local app/MCP architecture may not fit the Web Server or Database Issue unless there is a stable public server/resource with clear biological utility. | Consider only for a separate resource/server paper. The current manuscript is not naturally a NAR Web Server paper unless a maintained hosted resource is central. |
| Cell Genomics | Likely desk-rejection risk if the manuscript reads as useful software rather than a field-level genomic technology. | Only submit after stronger adoption evidence, validation, and a clearer genomics-wide advance. |
| Genome Research | May expect new genome biology or a method that enables new biological insight, not mainly a platform for personal annotation. | Use only if adding a biological case study or stronger methodological contribution; otherwise lower priority. |
| Briefings in Bioinformatics | Better suited to reviews and broad methodological syntheses. Reworking into this format would create a long review-style manuscript, and the AI-agent section may age before publication. | Avoid unless the goal changes to a review/perspective. Not ideal for fast publication of a fast-moving AI/software platform. |
| GigaScience | Excellent philosophical fit, but there is editorial-transition risk after the 2025 staff/board crisis. Reviewers may also require very strong FAIR/reproducibility packaging. | Verify current editorial stability before submission. Prepare code, data, workflows, and test datasets exceptionally well. |
| PLOS Computational Biology | Strong open-source fit, but software articles must provide a significant advance and broad adoption potential; reviewers may be tough on novelty. | Frame as open-source infrastructure for reproducible personal-genome analysis, not just a web UI. Provide test data and exact reproducibility commands. |
| BMC Bioinformatics | Safest software-paper fit but lower prestige; reviewers may still ask for conventional tool comparison and validation. | Good fallback if speed and fit matter more than prestige. Keep the manuscript concise and practical. |
| Database | Works only if the module ecosystem and curated resources are the center of the paper. | Submit a resource-focused version, not the full platform/AI/ethics paper. |
| Patterns | Philosophically open to data/software/ethics, but highly selective and broad. It may ask for a more general data-science contribution beyond genomics. | Use only if reframing around local-first data infrastructure, FAIR workflows, and AI-assisted reproducible analysis. |

### Speed And AI-Aging Risk

The AI-agent and MCP parts of the manuscript will age quickly: model names, assistant ecosystems, MCP conventions, and agent frameworks may look outdated within a year. This argues against formats with predictably long review cycles or extensive review-style rewrites.

Practical implications:

- Prefer **software article** formats over review/perspective formats.
- Avoid turning the paper into a long `Briefings in Bioinformatics`-style review unless the AI section is shortened and made historically robust.
- Keep the AI section focused on durable ideas: tool schemas, reproducible operations, provenance, validation, and human review. Avoid over-specific claims about current assistants or model rankings.
- Treat `BMC Bioinformatics`, `Bioinformatics`, `PLOS Computational Biology`, and possibly `GigaScience` as more practical than very selective venues if fast publication is important.
- If submitting to a reach journal, freeze the AI/MCP claims to principles and put volatile implementation details in the software documentation rather than the manuscript.

## Journal Shortlist

| Journal | Recent JIF | Fit | How to position |
| --- | ---: | --- | --- |
| Bioinformatics | 5.4 | Best realistic fit | Strong match for open-source bioinformatics software and benchmarks. The manuscript needs sharper novelty, a shorter scope, and a conventional software-paper structure. |
| Genome Biology | 9.4 | Ambitious but plausible | Good for broad genomics software if it is a clear advance over state of the art. Needs stronger side-by-side comparisons and broader validation. |
| Genome Medicine | 11.2 | High-risk translational route | Only suitable if framed around privacy-preserving human genomics and safeguards, not citizen self-diagnosis. Would likely demand stronger clinical-use boundaries. |
| Nucleic Acids Research | 13.1 | Conditional fit | Possible if positioned as a maintained web/server/resource ecosystem. Local app plus MCP may not fit the Web Server Issue unless the hosted resource is central and robust. |
| Cell Genomics | 9.0 | Reach target | Could work as a Technology/Resource paper only after strong validation and a clear field-level advance. Current draft likely too tool-integration focused. |
| Genome Research | 5.5 | Selective and less natural | Impact threshold is met, but the journal usually wants novel genome biology or methods with broad biological insight. Fit is weaker than Bioinformatics or Genome Biology. |
| Briefings in Bioinformatics | 7.7 | Only if reworked | Better for a review/tutorial-style or perspective-plus-resource article than a straight platform paper. Consider only with a substantial narrative pivot. |

## Recommended Submission Sequence

### Practical Route

First target `Bioinformatics`. If the paper is strengthened substantially with broader validation and a cleaner state-of-the-art comparison, try `Genome Biology` before `Bioinformatics`.

### Reach Route

`Genome Biology` or `Cell Genomics` only after the AI-module validation and benchmarks are much stronger. `Nature Biotechnology` is above the threshold but not a realistic match for the current contribution unless the platform becomes a field-defining, widely adopted technology.

### Avoid Under The IF Constraint

`GigaScience`, `NAR Genomics and Bioinformatics`, `PLOS Computational Biology`, and `Human Genomics` are scientifically relevant but currently below the requested impact-factor threshold.

## Open-Source And Anti-Gatekeeping-Friendly Venues

If the impact-factor requirement is relaxed to **recent IF >3**, several more natural venues become attractive. These journals are generally friendlier to open-source software, open data, reproducibility, article-level merit, and unconventional research outputs than prestige-first medical/genomics journals.

### Best Philosophical Fits Above IF 3

| Journal | Recent JIF | Why it fits Just-DNA-Lite | Main caveat |
| --- | ---: | --- | --- |
| GigaScience | 3.9 | Very strong open-science fit: open access, open data, open peer review, FAIR data/software/workflows, reproducibility and usability as explicit publication criteria. The platform, module ecosystem, HuggingFace datasets, and reproducible benchmarks fit the journal's historical identity well. | Serious editorial-transition risk after the 2025 staff/board crisis; verify current editorial stability before submitting. |
| PLOS Computational Biology | 3.6 | Explicit Software article type for open-source tools of broad utility. Requires OSI-compliant source code, documentation, test data, and reproducibility. Philosophically aligned with article-level metrics and open access. | More selective than its IF suggests; software must be a significant advance with broad adoption potential or new biological insight. |
| BMC Bioinformatics | 3.3 | Very natural software-paper venue. Open access, accepts software articles, encourages open-source licensing, and routinely publishes bioinformatics tools with validation and comparison to existing methods. | Less prestigious than Bioinformatics or Genome Biology, but likely one of the safest fits. |
| Database: The Journal of Biological Databases and Curation | 3.6 | Good fit if the paper emphasizes the annotation module ecosystem, biological data resources, fsspec-discoverable module repositories, Ensembl/ClinVar/PGS-derived resources, and curation workflows. | Less ideal if framed mainly as a local app; it wants databases/database tools and resource availability. |
| Patterns | 7.4 | Open-access Cell Press journal focused on data science, FAIR software/data/workflows, infrastructures, tools, services, ethics, and policy. Could appreciate the agentic + local privacy + reproducibility angle. | Highly selective and broader data-science audience; needs stronger framing as a reusable data-science infrastructure, not only genomics software. |
| Scientific Data | 6.9 | Strong open-data and reuse philosophy. Could fit a companion paper describing the project datasets: annotation modules, Ensembl/ClinVar/PGS Parquet resources, PRS percentile distributions, and technical validation. | Not a good venue for the main software/platform manuscript; better for a Data Descriptor. |
| Computational and Structural Biotechnology Journal | 4.1 | Gold open access, accepts Software/Web Server Articles, has bioinformatics/tool-development scope, and is likely more open to applied computational platforms than elite genomics journals. | Broader computational biotechnology scope; manuscript should emphasize transparent AI-assisted analysis and reproducible bioinformatics workflows. |
| iScience | 4.1 | Cell Press open-access venue with broad scope, systems/computational biology sections, and willingness to consider robust applied work, replications, and negative results. | Fit is broad rather than precise; the manuscript would need a clear field contribution beyond "useful tool". |
| PeerJ Computer Science | 3.8 | Strong open-access and anti-impact-factor culture; evaluates methodological soundness rather than subjective impact. Good fit if reframed for computer science/software engineering, reproducibility, and agentic workflows. | PeerJ itself notes that bioinformatics software may belong in the flagship `PeerJ` journal rather than `PeerJ Computer Science`; check current scope before choosing. |

### Philosophically Excellent But Metric-Problematic

These venues are very aligned with open science and against gatekeeping, but they do not satisfy a conventional **IF >3** requirement now.

| Venue | Metric issue | Why still worth knowing |
| --- | --- | --- |
| eLife | No current JIF after its publishing-model change and indexing dispute. | Probably the strongest anti-gatekeeping philosophy: public reviews, article-level assessment, no traditional accept/reject prestige logic. Excellent ideological fit, but not if formal IF is required. |
| F1000Research | Publishing platform, not a conventional journal; no JIF. | Very friendly to software tool articles, open peer review, rapid publication, versioning, and article-level metrics. Good fallback if the goal becomes open dissemination rather than journal prestige. |
| Wellcome Open Research | Recent impact metrics below 3 and limited to Wellcome-funded authors. | Strong open-research model, software tool articles, transparent peer review, and author-driven publication. Only relevant if author eligibility fits. |
| Open Research Europe | No conventional JIF and eligibility constraints. | Similar platform logic: useful for EU-funded outputs and open peer review, but not for IF-driven publication strategy. |

### Revised Recommendation With IF >3

If the goal is **best match to the manuscript's open-source, local-first, anti-gatekeeping philosophy**, the order changes:

1. **GigaScience**, if the editorial situation is acceptable at submission time.
2. **PLOS Computational Biology**, if the software contribution is sharpened and the open-source/reproducibility package is very strong.
3. **BMC Bioinformatics**, as the safest conventional software-paper venue.
4. **Database**, if reframed around reusable annotation resources and curation infrastructure.
5. **Patterns**, as a more ambitious interdisciplinary open-data/software target.
6. **Bioinformatics**, still strong, but more conventional and less explicitly anti-gatekeeping than the venues above.

For the current draft, the most natural open-source-friendly version would emphasize:

- AGPL open-source code and local execution.
- Reproducible benchmarks with public genomes.
- Test data, containers, and exact commands.
- Open module specification and fsspec-discoverable repositories.
- Public datasets on HuggingFace/Zenodo where possible.
- Explicit uncertainty display rather than curated gatekeeping.
- Article-level usefulness: installability, reproducibility, extensibility, and user control.

## Venues, October 2026

Both papers were entered at EASRP 2026 (a EuroTech Federation student competition with no proceedings) and
neither reached the final. Nothing is published or under review, so there is no anonymity constraint, and
both papers can go to arXiv: Paper 1 first, Paper 2 when its journal version is ready (arXiv allows two
submissions per submitter per month, and rejected ones count).

### Paper 1

A working order, not a final choice, re-evaluated on 2026-10-27 with manuscript-journal-select (manuscript-skills
0.29.0). The files behind it sit beside the paper in `v0.6/`: `paper1-just-dna-lite.record.yaml` (priorities and
every venue fact, with source and date), `paper1-just-dna-lite.journal-ladder.csv` and
`paper1-just-dna-lite.preprint-ladder.csv` (sorted and chosen rungs in fixed columns), and
`paper1-just-dna-lite.venue-requirements.md` (what every venue shares). The authors' priorities: speed to a
decision, reach (impact factor above 3), a light AI-policy burden, and a bioRxiv-friendly journal; a grant can
pay a normal open-access fee. Every figure below was read on the venue's own page on 2026-10-27 or 2026-10-19
unless marked.

**What changed from the 19 October ladder.** That ladder put BMC Bioinformatics, Cell Reports Methods and Genome
Biology on top because it sorted by days to a first decision, a figure that includes desk rejections and so is
shortest at selective journals, and because it scored the AI rules for reworded text rather than for what AI
did here. AI drafted and rewrote passages throughout, Results and Discussion included, and the authors said on
27 October that a rule reserving those sections for them is too tough. Under that use two rules rule a journal
out: ISCB's ban on drafting "from a prompt text" (*Bioinformatics*, *Bioinformatics Advances*) and Springer
Nature's red line on "writing results or discussion independently" (BMC Bioinformatics, Genome Biology). The
simulated referees of the v0.5 run reviewed against the old top three, which is why they came from journals
that are now off the ladder.

**Preprint ladder.** 1. **bioRxiv** (Bioinformatics category), then **arXiv** q-bio.GN as the fallback.
bioRxiv screens out "announcements of tools or services without data" and may send a paper with
health-related content to medRxiv, so the preprint must read as a software paper with results. It transfers
the manuscript directly to iScience, Frontiers in Bioinformatics, PLOS Computational Biology, NAR Genomics and
Bioinformatics and Cell Genomics on this ladder, not to JAMIA Open, Cell Reports Methods or Genomics
([list](https://www.biorxiv.org/submit-a-manuscript)). Every journal below accepts a manuscript already on
bioRxiv. The Cell Press journals (iScience, Cell Reports Methods, Cell Genomics) allow only the original
submitted version on the server: do not post revised versions once the paper is under review there.
The servers' screening rules, read on 28 October 2026, explain the Generation I paper's round trip: bioRxiv
sends clinical papers to medRxiv and keeps an epidemiology paper only if it "contains no health-related
information", and medRxiv's screeners ask whether a paper is "a clinical research manuscript", with
"Announcements of tools or services" out of scope, so a tool paper that reports disease risk can be sent from
one to the other and back. arXiv states no such rule, which is why the regenerated preprint ladder sorts it
first; the order stays bioRxiv first, because both bioRxiv and medRxiv refuse a manuscript already posted on
another server, so arXiv first would close them.

**Journal ladder.**

| Rung | Venue (article type) | Days to first decision (median) | IF | AI rule for this paper | Direct from bioRxiv | Fee for a Rostock author | What decides it |
|---:|---|---:|---:|---|---|---|---|
| 1 | **iScience** (Research Article) | 6, desk decisions included | 4.5 | Elsevier policy: drafting allowed if it does not replace the authors' contribution; one published declaration | yes | US$3,240, 15% off under DEAL; fund up to €2,000, grant the rest | "a significant contribution"; ML methods without benchmarks are out of scope, and the PLINK2 and Generation I benchmarks answer that |
| 2 | **Frontiers in Bioinformatics** (Technology and Code) | not published | 3.6 | declare in Acknowledgements; prompts encouraged, not required | yes | nothing: the library's Frontiers agreement caps it at €2,000 and pays it | new code or software, or a new application of known software; up to 12,000 words |
| 3 | **JAMIA Open** (Application Note) | not published | 4.7 | OUP: declare in the cover letter and Acknowledgements | no | US$3,582 (DOAJ); no OUP agreement | "descriptions of computer software or algorithm implementations" |
| 4 | **Cell Reports Methods** (Article) | 7, desk decisions included | 5.8 | Elsevier policy, as iScience | no | US$4,970, 15% off under DEAL | "a comparison of the method with related methods when appropriate, and validation"; two of three simulated referees said reject |
| 5 | **Genomics** (Elsevier; Research article) | 6; 64 after review | 3.6 | Elsevier policy | no | US$3,460, 20% off under DEAL | personal genomics and bioinformatics tools in scope; accepts about a quarter of submissions |
| 6 | **PLOS Computational Biology** (Software) | 41 | 3.6 (third-party) | declare tools, what they affected and how outputs were checked; may run AI detection | yes | US$3,165; no agreement | "new biological insights" and wide adoption; under 3,500 words |
| 7 | **NAR Genomics and Bioinformatics** (Application Note, Methods) | 44 | 3.0, at the floor | OUP default | yes | US$2,633 (DOAJ); no agreement | benchmarks against "an adequate number of relevant alternative" methods |
| 8 | **Cell Genomics** (Technology) | 5, desk decisions included | 8.4 | Elsevier policy | yes | US$8,900, 15% off under DEAL | "significant improvements over existing methods", a step-by-step protocol; the reach rung |

Every journal's validation rules were read on 27 and 28 October 2026 (Genomics' Guide for Authors in the
authors' own browser), and each condition the paper can settle was checked against the v0.6 text. iScience,
Genomics, PLOS Computational Biology, JAMIA Open and Frontiers in Bioinformatics state no validation rule for a
software paper, and Cell Reports Methods' comparison-and-validation rule is met (Section 4.2 against PLINK2,
Section 4.4 for the ancestry call): all six fit. Two meet their bar only in part, so the sorted order puts
them last: Cell Genomics' Technology bar asks for "significant improvements to existing methods", and the paper
compares annotation only with its own Generation I, not with ANNOVAR or VEP; NAR Genomics and Bioinformatics'
Methods Papers need benchmarks against several state-of-the-art tools and large-scale computing, while an
Application Note would mean cutting to 3,000 words. On the preprint side the paper names its two genome
donors, which bioRxiv's and medRxiv's rules against identifying people do not allow for. Before these rules were read, the
sorted order put Cell Genomics first on its 5-day median; it is last because that figure is mostly desk
decisions and its Technology bar is the highest here. Frontiers in Bioinformatics and JAMIA Open sit above
journals with a published speed because their software article types fit the paper as it is. Elsevier's policy
also advises keeping a record of the AI tools used, which editors may ask to see; it requires none, and nothing
is deposited.

**Left out, and why.** *Bioinformatics* and *Bioinformatics Advances* (ISCB bars LLM drafting); BMC
Bioinformatics and Genome Biology (Springer Nature's red line on AI-written Results and Discussion);
GigaScience (AI outputs deposited in GigaDB); Molecular Systems Biology (AI limited to polishing human text);
eLife and F1000Research (no impact factor); Life Science Alliance (impact factor not on its pages, about 3.1
elsewhere); Genome Research (Resource articles must add "novel biological information or technology",
US$5,200). Worth knowing: from November 2026 the *Nucleic Acids Research* Web Server issue takes stand-alone
applications that run on any operating system from a container needing no installation, with "novelty or a
clear benefit over similar applications (e.g. usability)" (IF 15.0); a proposal comes first. Just-DNA-Lite
would need a published container image.

**Simulated review.** The next manuscript-improve run on v0.6 reviews against the top three rungs: iScience,
Frontiers in Bioinformatics and JAMIA Open.

**AI use.** One factual account from the authors of what the tools did (Claude Code as the main assistant,
Codex as a second model checking its output), not a count of commits or revision markers and not a per-pass
record. Every journal on the ladder accepts it as a declaration.

**Ethics.** The Ethics Committee of the Institute of Biochemistry of the Romanian Academy determined that the
work is not research on human subjects and needs no approval (ethics register no. 17, 23 September 2026).

### Paper 2

Priorities confirmed by the authors on 19 October 2026: **fast publication first, with a journal impact
factor above 3**. The recommended order among the three journals checked is:

| Order | Venue | Why |
|---|---|---|
| 1 | **BMC Bioinformatics** (Software) | IF 4.4; the fastest reported first-decision median among these checked candidates. Evaluation consistency and the fee route must be settled. |
| 2 | **Bioinformatics** (Original Paper) | IF 5.5; fallback, with a longer reported first-decision median and stricter writing-assistance policy. |

The files behind it sit beside Paper 2 in just-module-creator's `docs/manuscript/`: `manuscript.record.yaml`
(priorities and every venue fact, with source and date), `manuscript.journal-ladder.csv` and
`manuscript.venue-requirements.md` (what every venue shares).

Read on each journal's own pages on 2026-10-19. BMC Bioinformatics: median 5 days to first decision, fee
€2,590 ([metrics](https://link.springer.com/journal/12859),
[fees](https://link.springer.com/journal/12859/how-to-publish-with-us)); a Rostock corresponding author may get
the 20% DEAL discount, and the university fund pays at most €2,000 gross, so whether Paper 2 qualifies is
still open. *Bioinformatics*: median 23 days in 2025, US$4,376
([About](https://academic.oup.com/bioinformatics/pages/About)). Both medians include desk decisions, so
they do not measure the time to a decision after external review. *Database* is outside the floor: its
[About page](https://academic.oup.com/database/pages/About) gives a 2025 IF of 2.7, not the 3.6 used
earlier, and a median of 63 days. Its scope (annotation methods, automated and semi-automated curation)
fits the paper closely, so it returns if the authors drop the floor.

**Evaluation to settle before posting.** Paper 2's evaluation table
(`just-module-creator/docs/manuscript/manuscript.tex`, "plugin version fixed") reports three runs with pair
recall 0.67, 1.00 and 1.00. The SIRT6 runs committed in just-module-creator (`a`, `b`, `a2`) score 0.33,
1.00 and 0.33, but they are an earlier preparation round across three plugin builds: commit `fab4db5`
(31 August 2026) replaced them in the table with a round at a fixed version, and `221b95f` filled in that
round's runs 2 and 3. The different scores therefore do not show an error in the table. The later round's
raw modules, prompt, reference and version record are not in the repository; the runbook kept them in the
gitignored `data/interim/repro-bench-2/`, which is not in the current checkout. Recover and archive them,
then reproduce the table. If they cannot be found, report the preparation round with its limits or run a
new, separately identified evaluation. BMC Bioinformatics asks for a "direct comparison with available
related software"; for an authoring tool that means a matched authoring baseline (a raw model or a
scripted draft) on the same task.

Make Paper 1 citable first, then let Paper 2 cite its preprint and proceed when its own evidence is ready.
Paper 2 does not need to wait for Paper 1's journal acceptance; the journals can assess the two distinct
papers in parallel with the overlap disclosed. Update companion citations when preprint or journal
identifiers become available, and preserve each paper's software/evidence versions.

### AI rules of the candidate venues

Read on 2026-10-15 from each venue's own pages; the sources, with verbatim quotes, are in the
[manuscript-skills](https://github.com/dna-seq/manuscript-skills) plugin
(`skills/manuscript-integrity-check/references/`). Impact factors are copied from the June 2026 assessment
above and were not re-checked. These policies changed several times in 2026, so re-read the chosen venue's
live author guidelines before submitting.

| Venue | IF | Writing help | Disclosure cost | Screening | Note for us |
|---|---:|---|---|---|---|
| **Bioinformatics** (OUP/ISCB) | 5.4 | **The only outright ban:** no drafting "from a prompt text"; the only writing aids named are spelling and grammar checkers | Cover letter, Methods or Acknowledgements, and a supplementary note "with sufficient details" | None systematic ("investigate reported instances") | Off Paper 1's ladder since 2026-10-27: AI drafted parts of the paper |
| **Briefings in Bioinformatics** (OUP/ISCB) | 7.7 | Same ISCB ban | Same | None systematic | Same rules as *Bioinformatics* |
| **CSBJ** (left Elsevier on 31 Jan 2026; now an AAAS Science Partner Journal) | 4.1 | Allowed, but even language editing must be disclosed | Cover letter, Acknowledgments, and Methods **with the full prompts** | iThenticate | Heaviest disclosure. Our edits ran over many conversational sessions, so full prompts are impractical. Drop |
| **GigaScience** (OUP/BGI) | 3.9 | Allowed with disclosure; no grammar exemption | The tool cited in the text and in the reference list, a usage summary at the end, and AI outputs deposited in GigaDB | "may use tools to detect undeclared or misuse of AI" | Most burdensome open-science venue. BGI dismissed the editorial team in Sept 2025 and 30 of 49 board members resigned (secondary report); the journal still publishes. Drop for now |
| **Genome Biology**, **Genome Medicine**, **BMC Bioinformatics**, **Scientific Data** (Springer Nature/BMC) | 9.4 / 11.2 / 3.3 / 6.9 | Risk framework: language polish (Green) and "drafting sections based on author input" (Amber) allowed; "writing results or discussion independently" and content "from text prompts" (Red) forbidden | AI Declaration plus Methods (the journal pages still say Methods); even Green use is declared | **Publisher-wide**: nonsense-text detector, irrelevant-reference checker, tortured-phrase tool. Editor guidance calls detectors "far from definitive" | Permissive rules, the most active screening. Fine with clean references and a declaration; Results and Discussion must be ours |
| **PLOS Computational Biology** | 3.6 | Allowed; rephrasing for clarity is exempt | In the article: tools, what they affected, **how the outputs were validated**; AI-written code must be disclosed | "We may use available AI detection tools" | Moderate. The validation statement is extra work but natural for us (tests, benchmark records) |
| **PeerJ / PeerJ CS** (T&F) | 3.8 | Allowed, but even copyediting is declared, and both versions must be kept | Methods or Acknowledgments | None named | Moderate; undisclosed use is listed as misconduct |
| **Patterns**, **Cell Genomics**, **iScience** (Cell Press, Elsevier policy) | 7.4 / 9.0 / 4.1 | Allowed, drafting support included; grammar, spelling and reference tools exempt | A published "Declaration of generative AI…" section; STAR Methods when AI is part of the method | Elsevier's 100+ integrity signals; no AI-text detector named | Low friction on AI; the bar is scientific selectivity |
| **Nucleic Acids Research**, **Database** (OUP default policy) | 13.1 / 3.6 | Language polish exempt; substantial editing allowed with disclosure | Cover letter and Acknowledgements (Methods if integral): tool, version, use, author oversight | iThenticate; no AI detector | Low friction. Fit limits apply (NAR: web server or database issue; Database: resource framing). Database's 2026 page could only be read in part |
| **Genome Research** (CSHL Press) | 5.5 | **Most permissive**: refining, editing and grammar tools exempt; generated content allowed with disclosure | Methods: tool, version, description | Plagiarism and image tools; no AI detector | Least AI friction of the IF > 5 group, but the weakest fit (it wants genome biology) |
| **F1000Research**, **Wellcome Open Research**, **Open Research Europe** | n/a | Allowed; F1000Research bars "text or code generation without rigorous revision" | Methods or Acknowledgments | ImageTwin; no AI detector | Low friction. One F1000Research clause names "computer code" among things AI may not create; ask before relying on it |
| **eLife** | n/a | Allowed | Materials and Methods | None found | Low friction; no JIF |
