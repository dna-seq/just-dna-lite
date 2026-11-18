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
