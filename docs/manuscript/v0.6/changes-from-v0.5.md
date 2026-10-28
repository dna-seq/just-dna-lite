# Paper 1: changes from v0.5 to v0.6

Round opened on 26 October 2026 from the v0.5 master (commit `966c29f`). Each entry says what the text was,
what it is now and why. The id is the revision-ledger segment in `paper1-just-dna-lite.md`
(`<!-- @rev ID … -->`), so `uv run manuscript ledger report` finds the passage. For the full wording of
both versions, compare the two files:
`git diff --no-index --word-diff docs/manuscript/v0.5/paper1-just-dna-lite.md docs/manuscript/v0.6/paper1-just-dna-lite.md`.

The Supplementary Data, Tables S4 and S5, the figures and the venue files are unchanged copies of v0.5.

## 1. Authors, affiliations and acknowledgements

Requested by Anton Kulaga on 26 October 2026.

| Id | Where | Was | Now | Why |
|---|---|---|---|---|
| AU1 | Author line | Twelve authors, including Ryangguk Kim, Alina Fedorova and Sergey Evfratov | Nine authors; those three moved to the Acknowledgments | Their contributions (OakVar; utilities and literature exploration; the Generation I drug module) fit an acknowledgement better than authorship of this paper |
| AU1 | Kulaga Anton | Affiliations 1, 2, 4 (IBIMA, IBAR, SecvADN) | 1, 2 (IBIMA, IBAR) | Anton's affiliations are IBAR and IBIMA |
| AU1 | Tacutu Robi | 2, 9 (IBAR, Romanian Bioinformatics Cluster) | 2 (IBAR) | Robi is now affiliated with IBAR only |
| AU1 | Zaharia Livia | 3 (HEALES) | 1 (IBIMA) | Livia belongs under IBIMA |
| AU1 | Karmazin Alexey | 4 (SecvADN) | 3, 4 (HEALES, SecvADN) | Alexey Karmazin is at HEALES; SecvADN kept because he co-founded it (see Competing Interests) |
| AU2 | Affiliation list | Nine entries | Four: IBIMA, IBAR, HEALES, SecvADN | Dropped the Bioinformatics Cluster and CellFabrik (requested), the Glushkov Institute (the Ukrainian affiliation, requested), Oak Bioinformatics (its only author moved to the Acknowledgments) and MitoSpace (no author had it, in v0.5 either) |
| AU3 | Acknowledgments | Volodymir Semenuik only | Ryangguk Kim (Oak Bioinformatics), Alina Fedorova, Sergey Evfratov and Volodymir Semenuik, each with what they did | Moved from the author list |
| P7 | Contribution Statements | Entries for the three moved authors | Entries removed | They are no longer authors |
| (none) | Competing Interests | "Ryangguk Kim is a co-founder of OakVar Inc." | Removed | Competing interests are declared for authors |
| (none) | Header | "Draft v0.5" | "Draft v0.6" | New round |

## 2. Putting the features and the users first

v0.5 described the platform mostly through its mechanics and its limits; its strongest results sat in
Sections 3 and 4, and several features (the cleaned PGS Catalog, the registry's actual size, the plugin
skills, the PyPI libraries, compound results such as blood group or APOE type) were missing or only
implied. The paper did not say who the tool is for. These changes bring measured, verifiable facts
forward. No limitation or caveat was removed.

| Id | Where | Was | Now | Why |
|---|---|---|---|---|
| C2a | Abstract | Described the ecosystem in general terms; no user groups | One paragraph on the ecosystem (the platform, no-code modules, just-dna-registry as an app store, just-module-creator, just-prs alone or inside the platform), evidence linked to each variant's sources, MCP access and the public demonstration; no result numbers, headings or disclaimers (198 words, the "Alternative A" text, committed by the abstract-revision session in 8656195) | Author's request: the Abstract should make readers want the features, not retell the paper. An interim v0.6 version that listed four features with their numbers was replaced; the numbers stay in the Key features list (F1) and the body |
| C6 | Introduction, last paragraph | Ended on MCP access | Adds that users enter the workflow at different points and points to the feature list and Box 1 | Lead-in to the two new items below |
| F1 | Introduction, new "Key features" list | Not present | Six features (the evidence item says each variant leads to "its sources": the pharmacogenomics module cites ClinPGx annotations, not study rows): cleaned PGS Catalog; app store for modules; speed; three ways in; evidence a reader can follow; local processing. Each points to the section with the evidence | A platform paper needs a feature summary a reader can find in one place |
| F2 | Introduction, new Box 1 | Not present | Five user groups (people with their own genome; researchers; bioinformaticians and developers; AI-assistant users; educators and students), what each can do, where each starts | v0.5 never said who the tool is for. A box, not a table, so Tables 1 to 4 keep their numbers |
| F3 | Section 3.2, new paragraph "A catalogue that works out of the box" | The cleaned catalogue was not described; only the scoring-file compatibility audit (Table S5) | How the metadata are cleaned; the 2 September 2026 audit of reference distributions (6,117 of 6,977 pass, 860 withheld and why); 778 EFO traits; the rules behind the High, Moderate, Low and Very low quality labels; direction-of-effect annotation for 2,282 scores, AI-assisted and pending expert review | The quality control that makes the catalogue usable out of the box is real work that the paper did not mention |
| F4 | Section 3.4, new paragraph | The registry was described as a service, with no size or examples | How publishing and installing work; the registry on 26 October 2026 (24 modules, five accounts, examples beyond Table 1); modules that combine several variants into one result (blood group, APOE type) | Shows that the ecosystem already grows beyond the authors' own modules |
| P5 | Section 3.2.1 | just-prs reachable through API, CLI, web UI, MCP | Adds the `/prs` skill of the just-prs Claude Code plugin | It exists and was not mentioned |
| J11 | Section 3.2.1 | MCP servers described without clients | Names Claude Code, Codex and Cursor, and the just-module-creator authoring skills for Claude Code and Codex | Readers want to know whether it works with the assistant they use |
| F5 (inside T6) | Discussion, opening | Connection of genome to evidence | Adds one sentence: the same operations from a web UI, an assistant or a library serve several groups at once (Box 1) | Ties the Discussion to the user groups |
| R24, A3c | Conclusion | Opened on architecture ("integrates local variant annotation … with a portable annotation-module contract"); said "faster annotation … albeit on four call sets" | Opens on what users get (catalogue, registry, speed, three ways in); states the 128 to 231 times speedup; keeps the scope (four call sets from three people, one for scoring) and every later caveat | The Conclusion should restate the value, then the limits |

### Where the new numbers come from

| Number | Source (checked 26 October 2026) |
|---|---|
| 6,117 scores with 1000 Genomes distributions; 6,977 audited; 860 withheld; 847 for collapsed percentiles | `just-dna-seq/prs-percentiles`, `data/1000g_distribution_audit_summary.json` (generated 2026-09-02) and `data/1000g_distributions.parquet`; `just-dna-seq/pgs-catalog`, `data/metadata/catalog_scoring_flags.parquet` |
| 778 traits | Distinct EFO ids among the 6,117 published scores (807 distinct trait strings, 1,931 reported-trait labels) |
| Reference panel of 3,202 people | `n` summed over the five superpopulations is 3,202 for every published score, matching Section 3.2 |
| Quality-label rules | `just_prs.quality.classify_model_quality` (thresholds 0.20 and 0.50 weight coverage, AUROC 0.7 and 0.6, 0.05 cross-build penalty) |
| 2,282 direction annotations | `just-dna-seq/pgs-catalog`, `data/metadata/curation_manifest.json` (built 2026-09-27; 0 marked verified, 242 in review) |
| 24 modules from five accounts | `GET https://module-registry.just-dna.life/api/v1/modules` |
| 33 to 65 s, 128 to 231 times, 16 to 20 s warm | Table 2 (unchanged) |
| 0.08 s per score, about seven times PLINK2 | Table 3 and the 0.10.2 rerun in Section 4.2 (unchanged) |
| PyPI libraries | PyPI: just-prs 0.10.5, prs-ui 0.3.18, just-prs-mcp 0.5.0, just-dna-format 0.7.1, just-dna-compiler 0.7.2, just-dna-registry 0.27.0. The annotation pipeline itself is not on PyPI, so the paper does not claim it is |
| Codex support | just-module-creator ships `.codex-plugin`; the MCP servers document Codex setup |

## 3. New Figures 1 and 3 from the public demonstration

Requested by Anton Kulaga on 26 October 2026, after the v0.5 review showed that the simulated referees
judged the screenshots only for errors and that the paper never showed the interface at its best. Both
figures were captured at https://lite.just-dna.life/ on 26 October 2026; `figures/README.md` records how.

| Id | Where | Was | Now | Why |
|---|---|---|---|---|
| N8 | Figure 1 and caption | Screenshot of the Input tab (sample list, quality-filter counts, raw variant grid). Its sample list showed nine uploads labelled with other people's names and family roles | (a) The Module Catalog with Longevity Map selected: publishing accounts, versions, variant counts, downloads, install button. (b) The Longevity Variants section of a report on Anton Kulaga's public genome: summary counts, an inferred genotype row, the AI-explain buttons, and the FOXO3 rs2802292 row opened to its conclusion and linked studies | Shows the two features readers asked to see (a finished report; the app store), and removes the names that two referees, the figures check and the policy check all flagged in v0.5 |
| N10 | Figure 3 and caption | Screenshot of an earlier PRS view showing an absolute-risk value for intelligence and inconsistent quality labels; the caption said it had to be replaced; an AUTHOR TODO asked for a new one | The current trait report for LDL cholesterol with all 101 models scored: summary across the 94 rated High or Moderate, the distribution chart with each model's position, and the per-model table with percentile, matched variants and quality label | The old image was a placeholder by its own caption. LDL cholesterol has many models and published discrimination data, so the view shows the quality labels at work and links to the Lipid Metabolism module |
| (none) | AUTHOR TODO after Figure 3 | Present | Removed | Done |
| R10 | Section 2.3 | Cited Figure 1 for "self-exploration" | Names the Module Catalog (Figure 1a) and says what a report section shows (Figure 1b) | The text now matches the figure |
| T4 | Section 3.2, first paragraph | Models shown "with their coverage and reference population" | Adds each model's percentile and quality label and the summary across models | Matches the new Figure 3 |
| T3 | Section 3.1, "A report in use" | Pointed to Supplementary S13 only | Also points to Figure 1b, where the same row is shown as the report renders it | Links the reconstruction (Figure 2) to the real interface |
| F1, F4 | Key features; Section 3.4 | No figure for the catalogue | Cite Figure 1a; the "evidence" feature cites Figures 1b, 2 and 3 | |

## 4. Why longevity: a bridge in the Introduction

Requested by Anton Kulaga on 28 October 2026. The Introduction argued for personal-genome annotation in
general for three paragraphs, then opened the fourth with "Recent progress in the genetics of longevity
illustrates the need for such extensible annotation tools", without saying why longevity. The reason
(Generation I was built around longevity) appeared only in Section 3. Since v0.5 the paragraph before had
ended on the Table S7 comparison rather than on "extensibility", so "such extensible annotation tools" had
lost its referent. No manuscript-skills stage flagged it.

| Id | Where | Was | Now | Why |
|---|---|---|---|---|
| N11a | Introduction, fourth paragraph (inside R4) | Opened directly on "Recent progress in the genetics of longevity" | One sentence first: the authors' starting point was longevity research, Generation I was built to read a genome against longevity studies (Kulaga et al., 2024), and longevity remains the most extensive expert-curated module (Section 3.1, Table 1: 528 variants, against at most 74 in the other expert modules) | Gives the reader the reason for the turn to longevity, in the place the turn happens |
| N11b | Section 1.2, first paragraph (inside C5) | "whose first generation (Generation I) was a set of annotation and report modules for OakVar" | Adds "built for longevity research" | Connects the platform's history to the motivation; Section 3's sentence on the default modules now recalls it rather than introducing it |

## 5. Open points for the authors

- **Anton's SecvADN affiliation** was dropped on the reading that "Anton has IBAR and IBIMA" means only
  those two. He is still listed as a SecvADN co-founder under Competing Interests.
- **Karmazin** keeps SecvADN beside HEALES. Drop SecvADN if HEALES should be his only affiliation.
- **Spelling**: the paper keeps "Alina Fedorova", as in every earlier version (the request wrote
  "Fyodorova").
- **Trait count**: the request remembered about 600 traits; the published data give 778 EFO traits among
  the 6,117 scores. The paper uses 778.
- **Direction annotations** (F3) are AI-assisted and none is yet marked as reviewed by a person; the
  sentence says so. Remove it if that caveat weakens the paragraph more than the feature helps.
- **Module examples** (F4) leave out the personality, cognition and aggression modules in the registry,
  to avoid a reviewer reading the paper as endorsing genetic prediction of behaviour.
- **Venue length**: the Abstract is 198 words. The venue record
  (`paper1-just-dna-lite.venue-requirements.md`) lists limits from 100 (Genome Biology) to 350 words
  (BMC Bioinformatics); 198 fits BMC Bioinformatics (350) and PLOS Computational Biology (300) but not
  Bioinformatics (150) or Genome Biology (100), so trim when the venue is chosen.
- **The public demonstration accepts uploads.** On 26 October 2026 https://lite.just-dna.life/ showed an
  "Add Sample / Select VCF" form and six samples: the two public genomes and four other uploads from 27 and
  29 September (file names such as `NG13RC2LEB.mm2.sortdup.bqsr.hc` and `LB2BBH2510.GRCh38.deepvariant.norm`;
  who uploaded them was not checked), visible to every visitor; its user id is `anonymous`, not the `public` of immutable mode. Section 2.3 says
  uploads are disabled there, and the landing page says "Nothing is sent to a server". Turn immutable mode
  on and remove the visitors' files, or change the sentence. The figures crop the sample list out.
- **Catalog cards miscount some modules.** Pharmacogenomics, FUT2 secretor, HFE, APOE type and Blood Groups
  show "0 variants", and the ClinVar panels show more "pathogenic" than variants (Pathogenic: 308,990
  variants, 617,822 pathogenic; Cancer: 70,638 and 141,316). Figure 1a was framed to show cards whose
  counts are right; fix the counts before a referee opens the catalog.
- **The trait report still shows an absolute risk for fluid intelligence.** On Anton Kulaga's genome the
  intelligence report gives "86.8% (pop. avg: 64.0%)" and a 1.36× relative risk, the problem that retired the
  old Figure 3. Absolute risk for a quantitative trait has no meaning; gate it on a binary outcome.
- **Quality labels render in lower case with underscores** in the trait report (`moderate`, `very_low`),
  while Section 3.2 writes them as words (Moderate, Very low).
