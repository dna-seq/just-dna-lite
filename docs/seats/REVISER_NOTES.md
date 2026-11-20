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
