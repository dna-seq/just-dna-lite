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
| C2a | Abstract | Described the ecosystem in general terms; no number; no user groups | Four features with their numbers (6,117 scores for 778 traits with ancestry-matched percentiles and 860 broken scores withheld; 24 registry modules from five publishers; whole-genome annotation in 33 to 65 s, 128 to 231 times faster than Generation I; web UI, AI assistants via MCP and skills, Python libraries) and the user groups | A reader of the Abstract alone did not learn what the software does better than alternatives, how large its catalogue is, or who it serves. The v0.5 improvement run had flagged "The Abstract states no measured result" (ST-10) but left it as an open decision |
| C6 | Introduction, last paragraph | Ended on MCP access | Adds that users enter the workflow at different points and points to the feature list and Box 1 | Lead-in to the two new items below |
| F1 | Introduction, new "Key features" list | Not present | Six features: cleaned PGS Catalog; app store for modules; speed; three ways in; evidence a reader can follow; local processing. Each points to the section with the evidence | A platform paper needs a feature summary a reader can find in one place |
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

## 3. Open points for the authors

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
- **Venue length**: the Abstract grew from 195 to 252 words. The venue record
  (`paper1-just-dna-lite.venue-requirements.md`) lists limits from 100 (Genome Biology) to 350 words
  (BMC Bioinformatics); 252 fits BMC Bioinformatics (350) and PLOS Computational Biology (300) but not
  Bioinformatics (150) or Genome Biology (100), so trim when the venue is chosen.
- **Figure 3** still carries the v0.5 AUTHOR TODO (replace the screenshot); unchanged in this round.
