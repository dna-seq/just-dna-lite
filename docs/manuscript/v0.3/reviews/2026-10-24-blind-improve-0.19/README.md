# Manuscript improvement on Paper 1 v0.3, run blind again (manuscript-skills 0.19 to 0.24)

A second blind manuscript-improve run on the v0.3 draft of Paper 1, after the fixes that came out of the first run (`../2026-10-22-blind-improve/`, manuscript-skills 0.12.1). It ran on 24 and 25 October 2026. It started on release 0.19.0 and picked up 0.20.0 to 0.24.0 and the fixes it found itself as they were released. The edit setting was `conservative`. Fresh Claude and Codex reviewers then compared its corrected version with the draft and with the first run's.

## The files

| File | What it is |
|---|---|
| [manuscript-dashboard.html](manuscript-dashboard.html) | One offline file: every problem counted once, the manuscript with each problem highlighted, the corrected version as track changes with the questions as comments, the edits as diffs, the figures, the simulated referees and readers, the independent re-check and what could not be checked. |
| [corrected-manuscript.md](corrected-manuscript.md) | The corrected version: the v0.3 paper with 84 applied edits and 12 of the stages' proposals. It holds 90 proposals back. Most were already applied under another number; the rest wait for a fact or decision only the authors have. It carries no notes or placeholders. A proposal; the v0.3 file is unchanged. |
| [manuscript-review.docx](manuscript-review.docx) | The same as a Word document: each edit a tracked change signed by its stage, each problem and question a comment. |
| [quality-comparison.md](quality-comparison.md) | What fresh Claude and Codex reviewers made of this corrected version against the draft and against the first run's, and how many of the 125 problems people found in v0.3 the run caught. |

## In brief

- **Problems:** 99 confirmed (2 blockers, 25 major, 46 minor, 26 optional), 9 candidates and 52 dismissed flags, across eleven stages.
- **Questions for the authors:** 13 decisions and 7 questions, where the first run left 72 questions.
- **Independent re-check:** a fresh agent read every confirmed problem against the corrected version. It judged 36 fully fixed, 24 partly, 31 open and 1 worse, and found 9 problems the edits introduced. Two proposals were held because of it, and two slips were fixed with recorded edits. The corrections whose reversal would bring an error back were kept, and their remaining defects are listed for the authors.
- **Against the draft:** both reviewers prefer the corrected version with high confidence, with the same scores the first run's version got.
- **Damage:** less than the first run. Serious damage fell from 3 to 1 (Claude) and from 8 to 5 (Codex), the share of changes the authors would reject fell, and both reviewers find the authors' voice kept.
- **Against the first run's version:** both reviewers prefer the first run's, with medium confidence, for its substance. It corrected more from the code (the AI module creator's outside services, the warm-run definition, the ancestry method, the comparison with pgsc_calc), where this run left those as questions.
- **Coverage:** this run caught 42 of the 125 known problems in full and 31 in part, against 52 and 24 for the first run. It caught more of the human referee's substantive comments and fewer of the authors' own later fixes.

## How the run was kept blind

The stages saw only the v0.3 manuscript, the companion paper of that time, the images of its four figures and a snapshot of this repository's code at commit `ad0b30a`, with no `docs/manuscript` and no git history. They were told never to open other review folders or the first run's benchmark. Every simulated reader, referee and the re-check ran as a fresh agent that had only its own workspace. The reviewers of the comparison worked in empty folders outside the repository. The coverage grading ran after the inventory was frozen.

## Not committed

The run's evidence stays local (see `.gitignore`): one folder per stage with its report, findings, checks and recorded edits (`run/`), the coordinator's notes and the reviewers' full answers (`benchmark/`), and the blind inputs (`project/`). The skills' side of the analysis is in the manuscript-skills repository (`evals/results/2026-10-25-improve-v0.3-0.24.md`).
