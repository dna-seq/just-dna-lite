# Manuscript improvement on Paper 1 v0.3, run blind

A full manuscript-improve run on the v0.3 draft of Paper 1, the text Robi Tacutu reviewed, followed by a
comparison with his review and the authors' later fixes. Run on 2026-10-22 with manuscript-skills 0.8.0
and brought up to 0.12.0 the same day; the dashboard was built by manuscript-dashboard (formerly
manuscript-visualize). The 0.10.2 build is kept in the run folder
(`run/.../manuscript-visualize/dashboard-0.10.2/`) for comparison.

## The three files

| File | What it is |
|---|---|
| [manuscript-dashboard.html](manuscript-dashboard.html) | Download it and open it in a browser: one offline file that opens on the Overview. Every problem counted once, by kind, severity, stage, section and skill; the manuscript with each problem highlighted (`manuscript-dashboard.html#manuscript`); the corrected version as track changes (`#revised`); machine-writing patterns by type in each version; the journals with their AI policies as icons and red flags; the edits as diffs; the reviewers' concerns and suggestions (`#reviewers`), the story (`#story`: the direction, the 15 story tests, the edits that keep the direction and the narrative changes only the authors can choose) and the readers' paths by section and subsection (`#readers`); the comparison with the human review; what could not be checked. The questions for the authors are comments beside the corrected version, never text in it. |
| [corrected-manuscript.md](corrected-manuscript.md) | The corrected version: the v0.3 paper with every applied edit and 60 of the 93 proposals, one per contested passage. It has no notes or placeholders: the 71 questions for the authors are comments in the dashboard and the Word file, and the 8 proposals that cannot be written without the authors' facts (the AI-use statement, the ethics statement, the data availability address, the corresponding author) wait for their answers. A proposal; the v0.3 file is unchanged. |
| [manuscript-review.docx](manuscript-review.docx) | The same corrected version as a Word document: every edit a tracked change signed by the stage that made it, to accept or reject one by one, and in the margin each problem on the passage it quotes, the questions for the authors and the reason for each edit. Google Docs opens it with the comments as comments and the changes as suggestions. |

## In brief

114 distinct problems confirmed (37 major) and 12 candidates, from 716 raw signals across ten stages; 38
of them found by two or more stages and counted once. Journal selection by the authors' priorities gave
Genes, Frontiers in Bioinformatics and BioData Mining; none of their AI policies has a red flag, and
Frontiers asks the most (every use declared, prompts encouraged in the paper). The three simulated
reviewers recommended major revision at the first two, and reject (two of them) or major revision at
BioData Mining; their 40 concerns each come with a suggestion, and 33 were upheld.

26 edits that keep the meaning were applied (7 by prose edit, 19 by deslop); the corrected version adds
60 of the 93 proposals, holds 12 (11 for one journal only, until a journal is chosen; one move), leaves
out 12 alternatives, and keeps out one move and 8 proposals that need facts only the authors have.
Machine-writing patterns fall from 9.8 per 1,000 words in v0.3 to 5.7 in the corrected version.

Against the 125 problems people raised in v0.3, the run caught 52 in full and 27 in part, and missed 46,
most of them wording; of the 80 substantive ones it caught 65 at least in part. It also found 53 confirmed
problems the human review did not raise.

## How the run was kept blind

The stages saw only the v0.3 manuscript, the companion paper of that time and a snapshot of this
repository's code at commit `ad0b30a`, with no `docs/manuscript` and no git history. The reference set was
built from the repository's history by a separate agent and sealed until the run's inventory was frozen;
the deslop stage, added later, was frozen and graded the same way. Two stages read pages updated after the
draft; those findings are kept for the authors and do not count as matches.

## Not committed

The run's evidence stays with the authors, outside git (see `.gitignore`): one folder per skill with its
report, findings, checks and failures, the item-by-item comparison with the review, the blind inputs, and
the analysis of what the run taught the skills. It is large and quotes the reviewer's comments item by
item. The skills' side of the analysis is in the manuscript-skills repository
(`evals/results/2026-10-22-improve-v0.3-blind.md`).
