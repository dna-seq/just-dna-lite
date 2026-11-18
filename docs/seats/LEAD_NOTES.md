# Lead notes

The state the seat's last holder left. State, not rules: the rules are the priming, `LEAD.md` beside
this file, and the kit's role.

## 2026-11-18 — first seating, on the always-on server

- **Seated** by the session that ran the adoption. The kit is an overlay: `.blueprints.toml` is
  untracked here and its master is on the desk.
- **Kept from before the kit:** `plans/handoffs/` (one handoff, a record; no new file goes there) and
  `.cursor/rules/` (another client's rules). Nothing retired, nothing moved under the watchdog.
- **Watchers:** plan, desk, duties, brief, automode and the chat all started at punch-in.
- **Picture:** this machine has no drawing agent. Asked in `#agent-chat>avatars` (2026-11-18); set it
  with `watchdog.py avatar lead --from ID --says TEXT` when a seat replies with one.
- **Toolchain:** `uv sync --dry-run` wants to reinstall the three workspace members (lead, pipelines,
  webui; the versions in `pyproject.toml` moved past the installed ones) and nothing else. Not run:
  the account's rule stops on any "Would uninstall" while jobs may use the environment. Run it when
  nothing else uses this clone's `.venv`. No test run yet. Whether this machine can show the web UI
  is not checked: until it is, every UI item is "built, not viewed".
- **The roadmap** (`docs/ROADMAP.md`): RM1 (README and FAQ wording) and RM2 (the haploid PRS regression
  test) were built on 2026-11-18 while the maintainer was away, and left the plan. RM3 is on the desk as
  #59 (default: the small fix, built once they have been present and away again), RM4 as #60 (default:
  nothing changes). Desk #61 asks whether Winternewt is a maintainer for the seats (default: member).
  RM5 waits on an upstream release, RM6 on the correspondence seat, RM7 follows RM3.
- **longevity-loci's lead** asked for the manuscript, figures, logo and colours for its deck; answered
  in `#agent-chat>longevity-loci deck` on 2026-11-18 with paths in the public repository. It may send
  what its re-curation changed, for the paper: that goes to the reviser as an item (RM4).
- **Acting duty:** milestones (the kit's `classes/pm/PM.md`), since no pm seat exists: the channel's
  `state` post kept in place, source `docs/seats/lead/state.md`, and a `milestones` post per landed result.
- **Another session without a seat** works in this clone, and other people's sessions push to the
  trunk: pull before each item, build only in own worktrees.

## For the maintainer to push

- Local `main` is four commits ahead of origin: `2f7d1c2` and `91ed9be` (the roadmap and these notes),
  `2ac82b3` (RM1), `77ef72f` (RM2), and the notes commit after them.
- The local branches `build/rm1` and `build/rm2` are merged; `git branch -d` refuses them until `main`
  is pushed. Delete them after the push.
