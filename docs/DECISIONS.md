# Decisions

The decisions settled with the maintainer, each with the alternative rejected. Numbered in sequence;
an entry is amended by a new entry naming it, never rewritten. The lead seat keeps this file
(`docs/seats/LEAD.md`).

## D1 — The repository runs seats (2026-11-18)

The maintainer adopted the seats kit (agent-seat-blueprints) for this repository.

- **Seats:** `lead`, `correspondence` and `reviser`. The maintainer: "let's have lead seat", then
  "you can also add correspondence and reviser". Not taken: a strategist (`pm`), offered and left.
- **Where they run:** on the always-on server ("it must be on a server"), not on a laptop.
- **Who the lead talks to:** "at least secretary and longevity-loci lead"; its seat table names
  both, with this repository's other two seats.
- **Who else sees the kit:** an overlay, the default offered and not changed. The seat table stays
  untracked, so the clones of other people who commit here are unaffected. Rejected for now: tracking
  the table and the kit's version, which would load the kit into every clone's sessions. `overlay.py
  track` turns one into the other by a pull request.
- **What a seat may do with git:** commit only, the default offered and not changed; the maintainer
  pushes. Rejected for now: the lead pushing its own branches.
