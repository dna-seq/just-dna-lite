# Quality comparison: the old run's corrected version, this run's, and the original draft

Fresh reviewers judged the corrected versions of two blind runs on draft v0.3: Claude agents, and Codex (`gpt-5.6-sol`, reasoning effort high). Each worked in an empty folder outside the repository, holding only its brief and the texts.

- **Old run:** release 0.12.1, `corrected-manuscript.md`.
- **This run:** releases 0.19.0 to 0.24.0 and the fixes made during the run, `run/.../manuscript-improve/revision.4/proposed.md` (sha256 c88e33dc…).

The briefs are `benchmark/quality/blind-brief.md` and `faithful-brief.md`, the same files the baseline used. Which file is which version is in `mapping.txt` and `mapping-new.txt`. Each reviewer's full answer is in its own folder (`answer.json`, `answer.md`).

## Blind: corrected version against the original

Scores are interest/clarity/soundness/voice and direction/readiness, out of 10. "Worse passages" counts the passages where that version reads clearly worse than the other.

| Reviewer | Corrected | Original | Preferred | Worse passages (corrected / original) |
|---|---|---|---|---|
| Claude, old run | 7/7/8/7/6 | 6/6/4/6/4 | corrected, high | 3 / 33 |
| Claude, this run | 7/7/8/7/6 | 6/6/5/6/4 | corrected, high | 4 / 40 |
| Codex, old run | 8/8/8/8/6 | 7/7/5/6/4 | corrected, high | 3 / 30 |
| Codex, this run | 8/8/8/8/6 | 7/7/5/7/4 | corrected, high | 1 / 33 |

Both corrected versions beat the original by the same margin. No quality was lost against the draft.

## Faithfulness: did the revision keep the paper?

| Reviewer | Verdict | Direction kept | Voice kept | Would reject or rework | Damage (high/medium/low) | More interesting |
|---|---|---|---|---|---|---|
| Claude, old run | accept with small fixes | yes | yes | 30% | 3 / 12 / 16 | same |
| Claude, this run | accept with small fixes | yes | yes | 20% | 1 / 7 / 10 | original |
| Codex, old run | needs substantial rework | yes | **no** | 35% | 8 / 7 / 2 | revised |
| Codex, this run | needs substantial rework | yes | **yes** | 30% | 5 / 5 / 2 | revised |

This run damaged less. High-severity damage fell from 3 to 1 (Claude) and from 8 to 5 (Codex), and the share of changes the authors would reject fell. Codex now finds the authors' voice kept. The old run's worst damage is gone: the invented consent statement, the blanket competing-interests declaration and the dropped co-author benchmarking credit.

Most of the "high" damage both reviewers still list are corrections made against the code or the deposited data: the join key, the default depth and quality filters, inferred ancestry, the restoration default, the DeepVariant version. A reviewer who sees only the two texts cannot see the evidence, so it reads them as unexplained method changes. The dashboard shows each one with its evidence; the corrected version alone does not.

Claude found the original slightly more interesting to read. Cut or flattened lines account for that: "Yet the gap between sequencing accessibility and variant annotation remains wide", "the larger experiment is social", "a compelling direction" turned into "another direction we are considering". The deslop and prose stages made these changes. Codex found the revision more interesting. The human referee of v0.3 marked "the larger experiment is social" as machine-like phrasing, so the two readings disagree on that line, and the human one counts for more.

## Head to head: the old run's corrected version against this run's

| Reviewer | Order | This run | Old run | Preferred | Worse passages (this / old) |
|---|---|---|---|---|---|
| Claude | old first | 6/6/6/6/5 | 7/7/7/7/5 | old, medium | 29 / 14 |
| Codex | this run first | 7/7/7/7/5 | 8/8/7/8/5 | old, medium | 14 / 16 |

Both reviewers prefer the old run's version with medium confidence, in either order. Their reasons agree. The old version corrected more of the substance, and kept caveats beside the claims of the paper's lead theme:
- the AI module creator sends the prompt and attachments to hosted services;
- the memory measurement samples only step boundaries;
- what the platform's upload accepts, set apart from what the just-prs library does;
- how ancestry is inferred and when it fails;
- what a warm run reuses;
- the PGS Catalog Calculator (pgsc_calc) named as the closest competitor.

Both prefer this run's benchmark reporting, its bibliography and its back matter. Claude also lists inconsistencies this run introduced: "we know of no tool" one paragraph after naming OpenCRAVAT, and "the two genes most consistently associated" with longevity. It also lists faults this run kept from the draft: "(added)" left in Future Directions, and the section heading "Modular Plugin System".

## Coverage: the problems people found in v0.3

The old run was graded against 125 problems people found in v0.3. They come from Robi Tacutu's comments and tracked edits, the authors' own later fixes, the benchmark rerun and a journal's requirements. This run's frozen inventory (`findings.4.json`) was graded against the same set by a fresh Claude agent, with the same rules: full, partial or none, and dismissed flags never count. The files are in `benchmark/coverage/`.

| Set | Items | Old run (full / partial / none) | This run, graded | This run, counting fixes without a finding |
|---|---:|---|---|---|
| All | 125 | 52 / 24 / 49 | 38 / 31 / 56 | 42 / 31 / 52 |
| Substantive | 80 | 46 / 19 / 15 | 35 / 23 / 22 | 39 / 23 / 18 |
| Referee's comments, substantive | 25 | 8 / 10 / 7 | 9 / 12 / 4 | 9 / 12 / 4 |
| Authors' own findings, substantive | 27 | 20 / 3 / 4 | 11 / 2 / 14 | 15 / 2 / 10 |
| Benchmark rerun | 13 | 10 / 3 / 0 | 9 / 3 / 1 | 9 / 3 / 1 |
| Journal fit | 20 | 9 / 4 / 7 | 6 / 7 / 7 | 6 / 7 / 7 |

The last column counts four bibliography problems as caught: full titles of three entries, and the Shenhar year, title and volume. The reference check fixed them as routine corrections that carry no finding, so a grader who reads only findings cannot see them (`benchmark/coverage/adjustment.json`).

This run caught more of the human referee's substantive comments: it missed 4, against 7 for the old run. It caught fewer of the problems the authors found themselves later. Several of those are text that disagrees with the code: which engine does which join, the memory measurement, the contig normalisation, the repository table. The old run's integrity check found those, and this one did not. Two bibliography years are still wrong in this run (Broer 2014 for 2015, Tacutu 2017 for 2018): the reference check added their DOIs but kept the years.

## What this says

This run is safer and less complete. It damages less, keeps the voice, asks the authors to reject less and asks them 7 questions and 13 decisions instead of the old run's 72 questions. It is still as much better than the draft as the old run was. But it holds back or turns into questions corrections the old run made from the code, and a reader comparing the two notices the missing substance. Some of what the old run added was damage (the consent statement). Some was correct and useful, like the warm-run definition and the AI module's external services. The difference is in what the conservative setting treats as "a fact only the authors have". Part of what this run's adjudication listed as a decision for the authors could be settled from the code at the draft's commit (D8).

## Caveats

- One reviewer of each model per comparison; medium-confidence preferences rest on a single reading each.
- The old run used release 0.12.1 under its own settings; this run used the conservative edit setting.
- The independent re-check read an earlier build of this run's corrected version (revision.2). The version the reviewers read holds two more proposals and two routine follow-ups.
