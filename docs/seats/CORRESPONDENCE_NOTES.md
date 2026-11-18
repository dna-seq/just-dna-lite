# Correspondence notes

The state the seat's last holder left. State, not rules: the rules are the priming, `CORRESPONDENCE.md`
beside this file, and the kit's roles.

## 2026-11-19 — not yet seated; the lead acted for it

Nobody held the seat, so the lead did its first work by its priming and grant, on the maintainer's
standing word (`LEAD.md`, "Acting for a seat nobody holds"). The first-seating handoff is still armed
and is shown at the first punch-in; its items 2 and 3 are done below. Nothing was posted on the forge.

### Liaison (up)

- Ledgers opened under `docs/upstreams/`, one per upstream, each read mark at the version locked on
  2026-11-19, and `DATA.md` for the data sources, whose releases are not read yet.
- Two items wait upstream: the enricher's `groups/` sidecars (S150, RM437; roadmap RM5) and
  polars-bio#453.
- The watchers `upstream-index` and `issues` start only when a session takes this seat. Until then
  nothing says a new release or a new issue.

### Triage (down): the first reading of the inbox, 2026-11-19

Twelve issues, all from June 2026, none answered since August except #8. A proposal for each, for the
maintainer; nothing is closed or commented without his word on the text.

| Issue | What it asks | Proposal |
|---|---|---|
| #7 MCP server and skill | an MCP server for the app | close as done: `uv run pipelines mcp`, `docs/MCP_SERVER.md` |
| #11 MCP or skill for the module builder | module authoring without API keys | close as done: the just-module-creator plugin with our MCP server |
| #10 ask an AI from reports | AI prompt links in reports | close as done: four prompt links per row and per phenotype result |
| #9 installers | regular installers, Windows first | keep open; pull request 28 is the work |
| #16 installation tutorials | per-OS and Podman tutorials | keep open; check `docs/CLEAN_SETUP.md` and the README first, may be partly done |
| #8 23andMe and Ancestry chips | chip file support | keep open as a roadmap item; the README now says it is planned |
| #17 .csv support (dimasximik, outside) | MyHeritage low-pass CSV | answer: not supported, VCF only; same item as #8. The one issue from outside the team: answer first |
| #19, #20 sorting (Livia) | sort PRS runs, annotations and reports by date or name | one small roadmap item for the lead |
| #12 ancestry | ancestry beyond PRS calibration | roadmap, the maintainer's priority |
| #13 Rosalind | a low-memory aligner and caller | likely decline: the app does not call variants (`CLAUDE.md`); the maintainer's word |
| #14 methylation | methylation clocks from just-biomarkers | roadmap or decline, the maintainer's word |

- **Pull request 28** (the Windows installer, from outside, +153/−62, last updated 2026-07-11): reviewed
  in `docs/reviews/pr-28-windows-installer.md`, which asks for one change and one bug fix. Whether
  that review was ever posted to the author is not known here: check before anything is posted.
