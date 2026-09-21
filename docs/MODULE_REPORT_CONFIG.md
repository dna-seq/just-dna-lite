# What a module could be allowed to say about its own report

**Research note, 2026-08-21. No code changed.** A survey of the annotation → report pipeline asking
one question: which presentation decisions are currently made *for* a module by this repo, and which
of them the module's author is actually the right person to make.

The short answer is that there are three tiers, and the first one costs nothing:

- **Tier 0** — knobs modules *already carry* in `module_spec.yaml` / `manifest.json` that this repo
  reads and throws away, or never reads at all. No format change. This is the bulk of the value.
- **Tier 1** — a new advisory `report:` block in `module_spec.yaml`, additive minor on the format
  side, carried through `manifest.json` the same way `weighting` already is.
- **Tier 2** — shapes nothing implements yet on either side.

---

## The finding that reframes the question

A module's authored `module:` block extends `just_dna_format.manifest.Display` (`manifest.py:126`,
`spec.py:173`) and already carries **`title`, `description`, `report_title`, `icon`, `icon_set`,
`color`** — six curated presentation fields, validated (hex-colour rule, `icon_set` vocabulary), with
`extra="forbid"` so a typo is a hard error.

Nothing ever reads them at report time. They reach a reader, when they reach one at all, through a
**one-time copy made at registration** into the *consumer's* config — which turns out to be a worse
arrangement than either reading them or ignoring them.

`get_module_meta` (`module_config.py:814`) reads `MODULES_CONFIG.module_metadata` — the merged
`modules.yaml` — and nothing else. A module not listed there gets `name.replace("_", " ").title()`.
Everything downstream (`get_module_display_name`, the report `<h1>`, every module `<h2>`, the webui
card grid via `build_module_metadata_dict`) is fed from that one function. The three acquisition
paths then differ:

| Path | What happens to the authored Display | Result |
|---|---|---|
| Local compile (`module_registry.py:171`) | Copied from `spec_config.module` into `module_metadata` at register time | Works — but `icon_set` is dropped, and the value is now a consumer override |
| Registry install (`module_registry.py:273`) | Copied from the installed `manifest.json`'s `display` block, best-effort | Same, `icon_set` dropped |
| Remote discovery (HuggingFace, any fsspec source) | **Nothing.** `_probe_module_at_path` fetches and validates the whole manifest (`hf_modules.py:282`) and projects three fields off it (`hf_modules.py:333-335`: `manifest_version`, `manifest_digest`, `manifest_weighting`), discarding `manifest.display` | Titlecased folder name unless a human hand-writes an entry in `modules.yaml` |

Three things follow, and the third is the one that matters most.

**The remote path is a straight repeat of a bug we already fixed once.** The commit that added
`manifest_version` / `manifest_digest` / `manifest_weighting` exists because, in CLAUDE.md's own
words, *"every HF-discovered module rendered Not stated for data the same function had already
fetched and thrown away."* Display is the identical bug, one field group over — and it covers all
ten modules published in `just-dna-seq/annotators`. The six that render correct titles today do so
**because someone hand-copied them into `modules.yaml`** (`modules.yaml:56-100`), not because the
modules state them; `pharmgkb`, which nobody copied, renders as "Pharmgkb".

**`icon_set` is dropped on every path**, because `ModuleMetadata` (`module_config.py:123`) has no
such field. A module declaring `awesome` silently gets Fomantic glyphs, and the format validated
that choice against a vocabulary for nothing.

**The copy conflates the author's claim with the deployment's override, in a file that is
rewritten at runtime.** `register_custom_module` and `register_downloaded_module` write into
`data/interim/modules.yaml` — the working copy, which is *also* where a deployment's deliberate
overrides live, and which is merged over the repo-root defaults. Once written, nothing can tell the
two apart. A re-register clobbers a deployment's deliberate rename; an authored change made after
registration never propagates, because there is no path that re-reads it. The right arrangement —
read the module's claim live, let `modules.yaml` override it — is not available, because the claim
is written *into* the override.

**Before designing new knobs, the pipeline should honour the knobs modules already have.**

---

## The config table

`file:line` is the wiring point — where the decision is made today.

### Tier 0 — already authored, dropped or ignored here

| Knob | Where authored | Governs | Today's behaviour | Wiring point | Format change |
|---|---|---|---|---|---|
| `title` | `module:` block (`Display`) | Module card title in the webui | Copied into `modules.yaml` at register time (local paths only); titlecased folder name for anything remote | `module_config.py:814`, `module_registry.py:171,273` | none |
| `description` | `module:` block | Report subtitle (single-module run), card body | Same copy-at-register; `"Annotation module: {name}"` for anything remote | `report_logic.py:66` | none |
| `report_title` | `module:` block | Report `<h1>` and each module `<h2>`; the two-word filename stem | Same copy-at-register; titlecase for anything remote | `report_logic.py:54,76` | none |
| `icon` + `icon_set` | `module:` block | Module glyph | `icon` copied at register; **`icon_set` dropped on every path** — `ModuleMetadata` has no such field | `module_config.py:123` | none |
| `color` | `module:` block | Card/section accent | Same copy-at-register; `#6435c9` for anything remote | `module_config.py:123` | none |
| `acmg_sf` | `VariantRow` (`spec.py:577`) | Whether a finding is an ACMG secondary-finding gene | **Renders nowhere.** Zero hits across `just-dna-pipelines/src`, `webui/src`, `tests` | `report_logic.py:619` (`_AUTHORED_AXES`) | none |
| `actionability` | `VariantRow` (`spec.py:580`) | Whether a finding is clinically actionable | **Renders nowhere**, same grep | `report_logic.py:619` | none |
| `priority` | `VariantRow` | An inert detail row (`Priority`) | Rendered as text; governs no ordering, no preview inclusion | template:654 | none |
| `flags` | `VariantRow` | An inert detail row (`Flags`) | Same | template:670 | none |

`acmg_sf` and `actionability` are the render-11-of-37 failure mode recurring in miniature: the engine
projects nothing, so both columns reach the user's parquet on every run and stop at the view model.
Adding them to `_AUTHORED_AXES` is one line each; whether an ACMG secondary finding deserves more
than a detail row (a badge, a pinned position) is the interesting half.

### Tier 1 — a proposed `report:` block in `module_spec.yaml`

Advisory metadata in the same class as `panel:` / `authorship:` / `license:` / `weighting:` — see
*Constraints* below.

| Knob | Governs | Default when absent | Wiring point | Format change |
|---|---|---|---|---|
| `categories:` — map of key → `{title, description, order}` | Section headings and grouping within a module's table | `LONGEVITY_CATEGORIES`, a dict of five hardcoded longevity pathways with hand-written prose, applied to exactly one module by name | `report_logic.py:157`, gate at `report_logic.py:1403` | minor |
| `sort_by:` — closed vocabulary (`weight_abs`, `evidence_level`, `effect_size`, `clin_sig`, `priority`, `p_value`, `gene`, `authored`) | Row order within a table | Guessed from lead table: `abs(weight)` for weights-led, `evidence_rank` for `pharm_variants` | `report_logic.py:954,1033,1097,1104` | minor |
| `group_by:` — `category` / `gene` / `drug` / `phenotype` / `none` | The unit a reader scans | Inferred from lead table; `drug` for pgx, flat otherwise, `category` for longevitymap only | `report_logic.py:1396-1406` | minor |
| `preview_rows:` — int | How many rows show before "show all" | Global `TABLE_PREVIEW_ROWS = 10` for every module | `report_logic.py:44` | minor |
| `row_budget:` / `promote_priority:` | Which rows lead and which collapse into the fold | Nothing — a 20-row curated module and a 53,098-locus ClinVar panel are treated identically | `report_logic.py:600` (template macro) | minor |
| `weight_display:` — `hide` / `numeric` / `bar`, plus `weight_range` | Whether the Weight column shows, and the colour ramp's scale | Always shown; `_weight_color` hardcodes `min(abs(w)*200, 200)` — an implicit 0–1 assumption | `report_logic.py:271` | minor |
| `ai_explain:` — `on` / `off`, optional `prompt_preamble` | The four prompt-prefill links per row | Always on, one generic preamble | `report_logic.py:645,700` | minor |
| `gene_link_base:` | Where a gene symbol links | Hardcoded NCBI in two places | template:617,911 | minor |

Notes on the three most load-bearing:

**`categories:`** is the one that pays for itself immediately. `generate_longevity_report` still
carries `elif mod_name == "longevitymap"` (`report_logic.py:1403`) — the exact hardcoded name the
`lead_table` dispatch was introduced to remove, surviving because the *category prose* has nowhere
else to live. Move the prose into the module and the name gate becomes a data check: does this module
declare categories? A second module wanting pathway sections needs a spec edit, not a code edit.

**`sort_by:`** must be validated against the columns actually present in the artifact, and mismatch
must **log and fall back**, never raise. A module declaring `sort_by: effect_size` when every
`effect_size` is null is a report that renders in scan order with a warning, not a failed run — the
same posture as `UnsupportedLeadTable` recording a skip rather than aborting the other modules.

**`weight_display:`** is the narrow, presentational half of a problem the format has already ruled on.
`Weighting` (`manifest.py:1257`) is free text on purpose, and its docstring explicitly refuses a typed
*precedence* field — "that would put two methodologies in one summable column". A knob saying *don't
render a weight column* or *this scale runs 0–5* takes nothing back: it does not blend, combine, or
reinterpret weights, it stops this repo from drawing a 0–1 colour ramp over a `log(OR)` module. The
report already renders `manifest.weighting` verbatim in "Modules in this report"; this is the same
statement made machine-actionable for one CSS function.

### Tier 2 — nothing implements these on either side

| Knob | Blocked on |
|---|---|
| Bin-family rendering (`measure_bins`, `activity_phenotype`, `repeat_alleles`, `heteroplasmy`) — how a binned measure is presented, units, thresholds to surface | No consumer implements the bin lookup at all. `binning.py` is 1073 lines of authored contract with no reader here. |
| `requires_callable` / `quality_from` withholding directives | Blocked on our own parquet: `user_vcf_normalized` flattens INFO and FORMAT into one namespace, so `DP` is ambiguous. Three upstream prerequisites named in CLAUDE.md. |
| Custom free-form sections / per-module methodology prose | Wants a sanitisation story before a module can put markup in a report. |

---

## Constraints any such block must satisfy

These are what make the proposal acceptable upstream, and they should be stated in the format's
ROADMAP note rather than discovered later.

1. **Advisory, exactly like `license:` and `weighting:`.** Out of `artifact.digest`, out of
   `content_signature`, not reconstructed by the lossy `reverse_module`. Additive-optional, so it
   lands in a **minor** under Principle 3 as amended — a new optional block moves neither identity.

2. **Tri-state, and absent means today's behaviour exactly.** `None` is *the module has not said*.
   Never a fabricated default, never coalesced. Every module we have published predates this block,
   so the absent path is the normal path for the whole 0.x tail.

3. **Precedence must be written down before it is implemented.** The only defensible order is
   `modules.yaml` override → module's authored claim → auto-generated fallback, and it should be
   documented in the same sentence as the existing convention it mirrors ("a local manifest still
   wins wherever it speaks"). A deployment must be able to override a module's presentation without
   editing the module; an unlisted module must stop rendering as a titlecased folder name.

4. **A module is untrusted input, so no knob may touch the report's integrity apparatus.** This is
   the first question a reviewer will ask and the line has to be drawn explicitly. A module may
   govern the presentation of *its own content*. It may not suppress:
   - the `inferred` badge and its "this can also mean the position was not covered" note
     (template:618,643) — the whole point of holding `genotype_evidence` apart;
   - the `locus_count > 1` "Position ambiguous" caveat (template:676);
   - "Data sources and licences" (template:997) — that is a redistribution obligation, not a
     presentation choice, and its tri-state permission booleans render *Not stated*, never
     permission;
   - "Modules in this report" (template:924) — version, digest, weighting, source;
   - "Modules not read in this run" (template:961) — a module cannot hide its own skip.

   Every one of those exists because its absence previously read as a positive claim. A knob that can
   turn one off is a knob that lets a module launder a caveat.

5. **A malformed `report:` block degrades, it does not fail.** Same posture as
   `_read_yaml_tolerant` for the working-copy `modules.yaml`: report the reason on both channels and
   fall back to current behaviour. Presentation metadata must never be able to cost a reader their
   annotations.

---

## Suggested order of work

1. **Tier 0 display plumbing** (this repo only, no format change): carry `manifest.display` onto
   `ModuleInfo` beside `manifest_version` / `manifest_digest` (`hf_modules.py:333-335`), read it in
   `get_module_meta` behind the `modules.yaml` override, and add `icon_set` to `ModuleMetadata`.
   Then **stop writing the authored Display into `module_metadata` at registration**
   (`module_registry.py:171,273`) — with a live read, that copy is what makes an author's claim
   indistinguishable from a deployment's override. This fixes every remotely discovered module's
   title, makes the ten `modules.yaml` entries optional rather than load-bearing, and gives
   precedence somewhere honest to live.
2. **Tier 0 axes**: `acmg_sf` and `actionability` into `_AUTHORED_AXES` + template rows.
3. **Tier 1 note** into `just-dna-format`'s ROADMAP — the sanctioned channel. `categories:` and
   `sort_by:` are the two worth arguing for first; `preview_rows:` is the cheapest.

## Related

- [MODULE_RELEASE_0_5.md](MODULE_RELEASE_0_5.md) — the module build/publish runbook
- [V1_PARITY.md](V1_PARITY.md) — what each shipped module is
- `CLAUDE.md` § *The report's side of the contract* — the render-if-present rule this note extends
