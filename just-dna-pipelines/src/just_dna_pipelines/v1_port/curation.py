"""
Curated corrections to Generation-I module content.

The Gen-I SQLites in ``data/interim/v1_port/_sources/`` are read-only seed artifacts, and the compiler
copies an authored cell verbatim (report-never-repair). So a *factual* error in the source — an
inverted weight sign, prose describing a different genotype than the row it sits on, a strand-flipped
genotype, a mistyped PMID — cannot be fixed by the adapter guessing, and must not be. It is fixed by a
recorded curation decision, per row, with a reason.

This is the same mechanism ``adapt_superhuman`` already uses for
``data/superhuman_pmid_curation.csv`` and ``_CURATED_SYMBOL_FIXES`` uses for gene symbols, generalized
so every adapter can reach it. Two tables per module, both tracked in the package:

* ``data/curation/<module>.csv`` — variant rows: ``rsid,genotype,field,new_value,reason``
* ``data/curation/<module>_studies.csv`` — study rows: ``rsid,pmid,field,new_value,reason``

``genotype`` identifies which row of an rsID is meant, or ``*`` for every row of it. ``field`` names
what changes; ``drop`` removes the row. Every correction is **reported as a warning** so a build states
what it overrode — a silent correction is indistinguishable from a silent corruption.

**A correction is a curation decision, not a repair the code inferred.** Nothing here is derived; each
row was adjudicated against the literature and the reason column says on what basis. Where the source
is internally contradictory and the literature does not settle it, there is deliberately **no row** —
those stay as authored and are reported by the audit instead.
"""

import csv
from pathlib import Path
from typing import Optional

from just_dna_pipelines.module_compiler.models import StudyRow, VariantRow
from just_dna_pipelines.v1_port.genotype import state_from_weight

_CURATION_DIR = Path(__file__).with_name("data") / "curation"

#: What a variant correction may change. `genotype` rewrites the authored genotype (a strand flip);
#: `drop` removes the row entirely.
VARIANT_FIELDS = frozenset({"weight", "conclusion", "genotype", "state", "gene", "drop"})

#: What a study correction may change.
STUDY_FIELDS = frozenset({"pmid", "p_value", "conclusion", "population", "drop"})

_ANY_GENOTYPE = "*"


def _read(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [
            {k: (v or "").strip() for k, v in row.items()}
            for row in csv.DictReader(handle)
            # A blank line or a `#`-led row is a comment; the tables are meant to be read by a human.
            if (row.get("rsid") or "").strip() and not (row.get("rsid") or "").startswith("#")
        ]


def variant_corrections(module: str) -> list[dict[str, str]]:
    """Curated variant-row corrections for ``module`` (empty when the module has none)."""
    return _read(_CURATION_DIR / f"{module}.csv")


def study_corrections(module: str) -> list[dict[str, str]]:
    """Curated study-row corrections for ``module`` (empty when the module has none)."""
    return _read(_CURATION_DIR / f"{module}_studies.csv")


def _matches(correction: dict[str, str], rsid: str, genotype: str) -> bool:
    if correction["rsid"] != rsid:
        return False
    want = correction.get("genotype") or _ANY_GENOTYPE
    return want in (_ANY_GENOTYPE, genotype)


def apply_variant_corrections(
    module: str, variants: list[VariantRow], warnings: list[str]
) -> list[VariantRow]:
    """Apply ``data/curation/<module>.csv`` to freshly adapted variant rows.

    Returns the corrected list. Every applied correction and every correction that matched nothing is
    reported — an unmatched row means the source changed under a decision made against the old shape,
    which is exactly when a stale override would otherwise be applied to the wrong variant or silently
    do nothing.
    """
    corrections = variant_corrections(module)
    if not corrections:
        return variants

    applied: list[str] = []
    used: set[int] = set()
    out: list[VariantRow] = []
    for variant in variants:
        row = variant
        dropped = False
        for index, correction in enumerate(corrections):
            field, value = correction["field"], correction["new_value"]
            if field not in VARIANT_FIELDS or not _matches(correction, row.rsid, row.genotype):
                continue
            used.add(index)
            if field == "drop":
                applied.append(f"{row.rsid} {row.genotype}: dropped ({correction['reason']})")
                dropped = True
                break
            before = getattr(row, field, None)
            parsed: object = float(value) if field == "weight" else value
            update: dict[str, object] = {field: parsed}
            # `state` is derived from the weight's sign at adapter time, so correcting a weight without
            # re-deriving it leaves the two disagreeing — and `state` is the axis the report colours by
            # (`report_logic._effective_direction` falls back to `direction_from_state`). A sign fix
            # that left a stale `protective` would change the number and keep the wrong rendering,
            # which is the whole defect. An explicit `state` correction still wins: it is applied as
            # its own row and overwrites this.
            if field == "weight":
                update["state"] = state_from_weight(parsed)
            row = row.model_copy(update=update)
            applied.append(
                f"{correction['rsid']} {row.genotype}: {field} {before!r} -> {parsed!r} "
                f"({correction['reason']})"
            )
        if not dropped:
            out.append(row)

    unmatched = [c for i, c in enumerate(corrections) if i not in used]
    if applied:
        warnings.append(
            f"applied {len(applied)} curated correction(s) to source content: " + "; ".join(applied)
        )
    if unmatched:
        warnings.append(
            f"{len(unmatched)} curated correction(s) matched no row — the source may have changed "
            f"under them: "
            + "; ".join(f"{c['rsid']} {c.get('genotype') or '*'} {c['field']}" for c in unmatched)
        )
    return out


def apply_study_corrections(
    module: str, studies: list[StudyRow], warnings: list[str]
) -> list[StudyRow]:
    """Apply ``data/curation/<module>_studies.csv`` to freshly adapted study rows."""
    corrections = study_corrections(module)
    if not corrections:
        return studies

    applied: list[str] = []
    used: set[int] = set()
    out: list[StudyRow] = []
    for study in studies:
        row = study
        dropped = False
        for index, correction in enumerate(corrections):
            field, value = correction["field"], correction["new_value"]
            if field not in STUDY_FIELDS:
                continue
            if correction["rsid"] != row.rsid or correction.get("pmid") not in (row.pmid, "", None):
                continue
            used.add(index)
            if field == "drop":
                applied.append(f"{row.rsid}/{row.pmid}: dropped ({correction['reason']})")
                dropped = True
                break
            before = getattr(row, field, None)
            row = row.model_copy(update={field: value})
            applied.append(
                f"{correction['rsid']}/{correction['pmid']}: {field} {before!r} -> {value!r} "
                f"({correction['reason']})"
            )
        if not dropped:
            out.append(row)

    unmatched = [c for i, c in enumerate(corrections) if i not in used]
    if applied:
        warnings.append(
            f"applied {len(applied)} curated study correction(s): " + "; ".join(applied)
        )
    if unmatched:
        warnings.append(
            f"{len(unmatched)} curated study correction(s) matched no row: "
            + "; ".join(f"{c['rsid']}/{c.get('pmid')} {c['field']}" for c in unmatched)
        )
    return out
