# Seats

The standing roles agent sessions take in this repository, run by the seats kit
(agent-seat-blueprints). A seat is a standing job one session holds, with a written job description
(its priming, below) and a notes file it keeps between sessions. A session takes a seat with
`/seats:seat NAME`, one session per seat.

The kit is an overlay here: the seat table (`.blueprints.toml`) is placed untracked in the clone of
whoever runs seats, and its master copy is on their desk. A clone without it is unaffected, and its
sessions work as `CLAUDE.md` says.

| Seat | Role (the kit's) | Owns | Priming | Notes |
|---|---|---|---|---|
| `lead` | `lead` | `docs/ROADMAP.md`, `docs/DECISIONS.md`, the code, its tests and their docs | [LEAD.md](LEAD.md) | [LEAD_NOTES.md](LEAD_NOTES.md) |
| `correspondence` | `correspondence` (triage and liaison) | `docs/upstreams/`, the issues and outside pull requests, dependency bumps | [CORRESPONDENCE.md](CORRESPONDENCE.md) | [CORRESPONDENCE_NOTES.md](CORRESPONDENCE_NOTES.md) |
| `reviser` | `reviser` | `docs/manuscript/`, the open round | [REVISER.md](REVISER.md) | [REVISER_NOTES.md](REVISER_NOTES.md) |

All three run on one always-on server. The lead pushes `main` (a fast-forward); the other two commit
and the lead pushes what they committed.
