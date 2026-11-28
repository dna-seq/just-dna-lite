# Reviser notes

The state the seat's last holder left. State, not rules: the rules are the priming, `REVISER.md` beside
this file, and the kit's role.

## 2026-11-18 — first seating, held for half an hour by the lead's session, then released

The session that held the lead seat took this seat too, by the maintainer's slip; he asked for the
reviser in a session of its own. Nothing in `docs/manuscript/` was edited. The first-seating handoff
was shown to that session and will not be shown again: its first work is repeated below.

### The one open item: the re-curated longevity module in the paper

- **Decided by the maintainer** (2026-11-18, `#agent-chat > general chat`, relayed to desk #60, closed):
  "add new longevity-loci curation section and what we learned from the new longevity analysis ... not
  as just examle but as a key module of the whole system and we can talk about longevity and
  genomics". Roadmap RM4.
- **The draft**, from longevity-loci's lead, whole: `docs/seats/reviser/item-longevity-loci-draft.md`.
  Its source is `dna-seq/longevity-loci` at `6cc9de0`, `docs/MANUSCRIPT_SECTION.md`. It is input, not
  text to paste.
- **Where it touches round v0.7:** a new section after 3.1 (which ends before line 219 of the master,
  where 3.2 Polygenic Risk Scores starts and would be renumbered), section 3.1's framing as "(example)",
  Table 1's Longevity Map row (line 187), and Table S14's part on how v2.0.0 handles the errors.
- **Checked against Table S14** (`supplementary/S14_generation1_longevitymap_audit.md`), all agree:
  528 rsIDs and 1,022 genotype rows; 462 rsIDs with at least one error (528 less 50 with none found
  and 16 not verifiable); 222 weighted though not significant; 124 with a direction inverted; 51 with a
  sex- or subgroup-only effect applied to everyone; 281 rows from Sebastiani 2012; 7 of 145 genome-wide
  rsIDs present (the draft says "about 7 of ~150": write 7 of 145).
- **Not checked, every one the other repository's claim:** all figures of the new module (164 or 169
  loci, 163 rsIDs, 489 genotype rows, 113/99/277, 679 study rows, 51 papers, the tier counts, 6,765
  quotes, 22,759 records screened, 111 general-ageing loci, 157 with unknown age of action), the
  "975 protective, 47 risk" split of v1, and each of the six findings about the genetics of longevity.
  Each needs its source read at that commit before it enters the master. The draft itself says the
  new rows have had no independent audit by the method of Table S14: that limit stays in the text.
- **Also the maintainer's to decide, as items:** whether 3.1 is rewritten around the new module or kept
  beside it; the claims of findings 2 to 4, which are about the field and stronger than a methods
  paper usually makes; the abstract and the contribution statements, if the section stays.

### Preflight, as far as it got

- pandoc and rclone are on this machine; **tectonic is not on the PATH**, so the PDF build is not
  known to run here (`MANUSCRIPT_TECTONIC` may point at one; not looked for). The docx build and the
  `gdrive` remote were not tried.
- The round's settings say `edits: apply`; the role expects `propose`. Not yet raised with the
  maintainer: raise it in the first message.
- Not read yet: `changes-from-v0.6.md`, `comments.yaml`, the record, the marks report.
- Not done: the picture (no drawing agent on this machine; ask in `#agent-chat>avatars`), the
  first-seating report to `@agents-kit/builder`. The hello to the secretary was sent.

## 2026-11-19 — seated in a session of its own; the draft checked

- **Preflight:** the marks lint clean (153 segments, 2 blind spots); the docx builds (`--no-pdf`); the master is
  unchanged since the co-authors got it (`d85c7f9`). No: tectonic (no PDF build here), rclone's `gdrive` remote
  (only `pulsewatch` configured, so no pull or push from this machine). `edits: apply` raised with Anton; the seat
  works as `propose` meanwhile.
- **Open with Anton (asked 2026-11-19 in session):** the longevity section and the answers to the 126 open comments
  (96 Georg Fuellen, 30 Livia Zaharia) go into a new `v0.8/` (default) or into v0.7 in place.
- **The draft, checked at longevity-loci `6cc9de0`** (a read-only clone beside this one).
  Confirmed: tiers 15/75/43/36 of 169; six axes; 111 general ageing, 17 heart, 9 metabolism; 157 age unknown;
  163 rsIDs, 489 genotype rows, 113/99/277 by `state`, 679 study rows, 51 PMIDs, no weight column; APOE once as
  ε pairs; ZW10/TTC12 A→B on heterogeneity; CHRNA3/5 A→B; FOXO3 tier B (multivariate only); v1 975/47 by `state`
  (`v1_audit_profile.json`); 127 of 132 inverted directions at Generation I curation (S14).
  Wrong or unsupported: build is 164 rows, findings 169; 6,765 quotes (nothing produces it); 19 markers are inside
  the 169 (6 tier A); "except APOE" uncounted, CDKN2B-AS1 contradicts it; "all present" false (11 of 145 leads
  have no v2 variant within 500 kb); CELSR2 seed tier is B; tier A rule drops "≥3k cases"; 22,759 is PubMed only;
  "18 rows" is queued papers; "about 7 of ~150" is 7 of 145; the five v1 rsIDs are rs429358, rs7412, rs2802292,
  rs9536314, rs2149954 (nine counting APOE proxies). Sent to longevity-loci/lead in #agent-chat > longevity-loci deck.
- **Waits on:** longevity-loci's PR into this repo (Anton, 2026-11-19: v2 supersedes the v1 port; supplements under
  `docs/longevitymap_v2/`, no S-number yet). The paper quotes the module that PR ships, read at its commit.
- **2026-11-19, later:** Anton: round v0.7 is worked in place. The Doc is read through the Google Docs connector
  (`read_doc` with comments; Drive connector also available); rclone is not needed. Nine Doc edits carried (0eb68c5),
  16 ledger items addressed. The Doc holds 71 open suggestions by "Winter Newt", all posted 2026-11-02 23:55 in one
  burst (an agent run's, it seems): Anton's to accept or reject, not signed by this seat.
- **Filed with the tooling seat 2026-11-19** (#agent-chat > manuscript-skills, 641742980), filed as dna-seq/manuscript-skills #6 and #7: (1) `comments.py import-gdoc` on a ledger first
  pulled from a .docx export does not know its items again: it doubled 132 items to 329 and wrote four people into
  `rev-marks.toml` unasked (reverted). (2) `comments.py status --strict` in a round worked in place flags every
  carried item "addressed, but its paragraph reads the same", since old and new round are one file.
- **2026-11-19, unattended (watchdog: maintainer away 2 h).** Desk #62 (who is corresponding author: the co-authors
  already took Georg's co-supervising asterisk off; default Anton) and #63 (Winter Newt an agent or Anton; default an
  agent's proposals; G Fue and Livia added as people in both options). Applied under the standing "do not block"
  word, signed `claude`, open for veto: S10, S14, S15, S19, S26 addressed, S21 partly (its "people and" waits on
  C58). Ledger: 105 open, 20 addressed, 1 partly, 6 not-on-point. The Google Docs connector was not connected at
  this turn, so the supplementary, S4 and S5 Docs are still not read. Longevity-loci's PR is #37, reviewed by the
  lead (checks hold at bcd2f7b); the section is drafted once it merges.
  Both fixed in manuscript-skills 0.69.1 (this machine still has 0.67.0 until the plugin syncs). `import-gdoc` still
  writes commenters into `rev-marks.toml` by default (put to Anton as desk #64): always pass `--no-people`.
- **Anton, 2026-11-19, forwarded by the lead (641950013):** "manuscript skills is super token consuming, please
  fininsh this run but do not initialize run withou asking me or getting explicit instruciton on it". The run in
  progress (`reviews/20261118T233751Z-7c381cd5`) is finished; no new manuscript-skills run, skill or subagent panel
  (claim checkers included) starts unless he asks for it in his own words or says yes when asked.
- **2026-11-20, unattended again.** Desk #69: Box 1's first user group, Georg's "Researchers, including citizen
  scientists" (default; matches the accepted Section 1.2) or Livia's "users" (C58, C130, S9, S11, S18, S20, S21).
  Open on the desk: #62, #63, #64, #69. Google Docs connector still disconnected (supplement, S4, S5 unread).
- **2026-11-20, the move to the supplement (C85, C100, C107, C140, C146, C147), under the default "move it, keep a
  plain summary":** 69e18a9 (2.1 to S12), 660e74b (3.2 to a new S15, 3.2.2 to a new S16, 4.1 to S10 and S2), 7991a73
  (4.2 to S3). Moved text is word for word; citations stay in the main text. S14 stays reserved for the
  Generation I audit tables (`supplementary/S14_*`), not yet cited in the master. Ledger: 99 open, 26 addressed,
  1 partly, 6 not-on-point. Next by the hardest-first order: C103 (weight of the speed claim), C108 (AI
  accountability), the Abstract (C46, C125, C49).
- **2026-11-20, unattended (2 h).** Filed desk #71 (weight of speed, C103), #72 (Abstract, C46/C125/C49), #74 (how
  co-authors vouch for AI-drafted text, C108). Defaults applied for veto: 6008ec3 (PRS runtimes to S3 as Table S3,
  concordance table renumbered Table 3; C108's sentence said plainly), 8569a64 (Abstract, 274 words; update on #72).
  #74's default leaves S11 unchanged. Open on the desk: #62, #63, #64, #69, #71, #72, #74. Ledger: 94 open, 29
  addressed, 3 partly, 6 not-on-point. Next: schemas and figures (C131, C133, C138), affiliations and names
  (C118 to C121), C122, C123, then the easy tail.
- **2026-11-20, later.** C121 (778 traits) and C122 (AI caveat kept) settled on the data, declined with reasons.
  Desk #75 (diagrams) default applied: c84c7e3, new Figures 2 (overview) and 3 (module lifecycle), Graphviz sources
  in `figures/*.dot`, old Figures 2 and 3 renumbered 4 and 5; Table S15 lists the catalogue's contents. Desk #76
  (affiliations, Fedorova, behaviour modules): defaults keep the paper as it is. Ledger: 89 open, 32 addressed,
  3 partly, 2 declined, 6 not-on-point. Next: the easy tail (S5, S12, S13, S16, S17, S20, S24, S29), then the rest.
- **2026-11-20, the easy tail.** 33ceba8: S5, S12, S13, S16, S17, S24 applied; S20, S29 declined with reasons.
  Ledger: 81 open, 38 addressed, 3 partly, 4 declined, 6 not-on-point.
- **2026-11-20, clarity batches** (the ledger's own `next`, no fork): cee136c (Sections 1 and 2), 94c5e68 (3.1, 3.2:
  the PRS definition now opens 3.2), bbb672a (Section 4 setup before results, Figure 5 caption, ancestry sites,
  5.4). 5.4 now says the web interface refuses a sample naming another build (5e31431, desk #59). Ledger: 44 open,
  75 addressed. Still open: Box 1's user group and its followers (desk #69: C58, S9, S11, S18, C110, C114, C130),
  authorship (#62: C64, C115, C116), carried facts (#76), and C51 to C53, C57, C66, C68 to C70, C72, C90, C91,
  C95, C117, C124, C126 to C128, C132, C134 to C137, C139, C141, C144, C145, C48, C56.
- **2026-11-20, two more batches.** cdaee05 (C48, C51, C53, C57, C66, C95, C117, C126, C136, C137, C145; C141 partly,
  page limit with the journal), 4249085 (C68, C69: Table 1's ClinVar rows give their size in variants from Table S4's
  `variant_count`). The weight formula is now a display equation (renders in the docx). Ledger: 30 open, 88 addressed,
  4 partly. Still open, no decision needed: C52, C70, C72, C90, C91, C124, C127, C132, C134, C135, C139, C144;
  C128 waits on the journal; the desk items as before.
- **2026-11-21, desk #69's default applied for veto** (53db27f), after the secretary's silence notice: Box 1's first
  group "Researchers, including citizen scientists"; S18 and S21 worded to match; C130 and S11 declined with reasons.
  Update posted on #69. Ledger: 22 open, 95 addressed, 3 partly, 6 declined. Open on the desk: #62, #63, #64, #69
  (applied, veto open), #71, #72, #74, #75, #76.
- **2026-11-22.** Desk kept current after two silence notices: updates on #71 and #75 (their defaults were applied
  on 11-20 with no post); #72, #74, #76, #69 true as written. b1c4ff6: C90 (MCP clients only as documented), C91
  (what was tested, not "should"), C134 (web interface = local; "public demonstration" for the site), C52 (by S5).
  Ledger: 18 open, 99 addressed. Left, no decision: C70 (weight rule, read Kulaga 2024), C72 (vector Figure 4),
  C124, C127, C139 (3.2 structure), C132 (page/line numbers in the build), C135 (check the demo is immutable), C144
  (S-table order); C128 with the journal; desk #62 and #76 items.
- **2026-11-22, longevity PR #37** (still open, head ffcfdfe): longevity-loci's lead says it now carries Longevity
  Map 2.0.0 with the 2015–2026 sweep: 172 loci, 513 genotype rows, 697 studies (was 169 / 489 / 679 when the draft
  was checked). Every figure of the section is read again at the merged commit; nothing drafted before the merge.
- **2026-11-22, later.** ce907e9: Table S15 cited from 3.2; every "Table S" reference resolves (C138; C144 partly,
  renumbering left to submission). C135 checked: the public demonstration hydrates with `is_immutable_mode` false
  and `allow_zenodo_import` true (a session over its own `/_event` socket, 13:5x UTC), so the paper's "uploads of
  private genome files are disabled there" is not true today. C135 open, `decision: true`, on desk #83:
  set `JUST_DNA_IMMUTABLE_MODE=true` on the deployment, or change the sentence. The deployment is not this seat's.
- **2026-11-23.** C135 on desk #83 (the demo accepts uploads). C132 taken by the lead as RM11 (page and line
  numbers in both builds). 9707337 C124 (the boundary with the companion paper in plain sentences), 3331ee0 C127
  (Abstract: what a PGS is first; waits for Anton's veto, Livia asked him), a05c730 C139 partly (3.2 opens with four
  steps, parts headed by step; reordering and a diagram left to the authors). `runs.py apply` refused a new
  paragraph and the run-in heads ("replaying the edits ... does not give the clean text"), so those went in by hand
  as `@rev C139a`–`d`. Ledger: 14 open, 101 addressed, 5 partly. Left without a decision: C70, C72.
- **2026-11-23 to 11-25.** RM11 landed (129a627): the .docx has a PAGE footer and line numbers, the .tex `lineno`
  and the three diagrams from their SVGs. 2e59df4 closes C132 and C72; Figures 1 and 5 now say they are
  screenshots (Livia's reply to C72). The PDF does not build on the cluster login node (the .venv tectonic needs GLIBC 2.35+);
  check vector figures in the .tex. `comments.py status` lists 20 `now` quotes not found verbatim, the same 20 at
  2e59df4's parent: older entries, not fixed yet. Demo re-checked 2026-11-24, still uploads on (#83 updated);
  #75 updated. #64 is manuscript-skills' question, not this seat's. Ledger: 12 open, 103 addressed, 5 partly.
  Open on the desk (this seat's): #62, #63, #69, #71, #72, #74, #75, #76, #83. PR #37 still open at ffcfdfe.
- **2026-11-28.** d6a2cdf: the 20 stale `now` quotes fixed; `comments.py status` reports 0 problems. GitHub issue 39
  (correspondence, confirmed on main a6e9150): a site the caller emitted but the quality filter dropped is restored as
  hom-ref. Supplementary S12 says restoration is "at sites the caller did not emit", which main does not keep today.
  The fix is the lead's. Default: if it has not landed by the next release of the paper, S12 reads "at sites with no
  call left after quality filtering" instead. PR #37 still open at e023a0f; no desk answers since 11-24.
  Same day: the lead's f5140aa fixed it (filtered-out positions kept beside the parquet and counted as emitted,
  RefCall included; restoration off when that record is missing). Read in restoration.py: S12 stands as written,
  no edit. The default above is void.
