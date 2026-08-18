"""
PMID normalization for the v1 port.

Gen-I modules store PubMed references in several forms:
- clean integers (``studies.pubmed_id`` in the three-table modules),
- bracketed/prefixed lists (``[PMID 17478681]; [PMID: 30278588];`` in coronary/vo2max/thrombophilia),
- bare numbers (``quickpubmed`` in longevitymap),
- NCBI SNP URLs (superhuman ``references`` — not PubMed IDs at all).

`normalize_pmids` turns any of the numeric forms into the digit-only strings required by the
ROADMAP 0.2 ``pmid`` rule, deduplicated and order-preserving. URL-only references yield ``[]`` so a
grounding gap surfaces explicitly rather than smuggling a fake identifier through.
"""

import re

# Matches "PMID 123", "PMID: 123", "[PMID123]" etc. — the prefixed forms in the curated text.
_PMID_PREFIXED: re.Pattern[str] = re.compile(r"PMID[:\s]*?(\d+)", re.IGNORECASE)
# Fallback for plain digit tokens (e.g. quickpubmed "8018664" or a bare pubmed_id).
_BARE_DIGITS: re.Pattern[str] = re.compile(r"\b(\d{4,9})\b")

#: What the format will actually accept in a ``pmid`` cell. ``spec.PMID_PATTERN`` is a *search*
#: pattern (``\b(\d{1,8})\b``); anchored here because we are validating a whole candidate token.
#:
#: Extraction stays deliberately permissive and the filter goes here instead, because narrowing
#: ``_PMID_PREFIXED``'s ``(\d+)`` would be worse than the bug: "PMID 168335863" would yield the
#: first eight digits and smuggle in ``16833586``, a real id for an unrelated paper. A too-long
#: token is not a PMID we can repair — it is one we must drop and report. ClinVar cites several
#: (Variation 12606 cites ``168335863``), which is why the ClinVar route drafts its own studies.
_ACCEPTABLE_PMID: re.Pattern[str] = re.compile(r"\d{1,8}")


def normalize_pmids(raw: object) -> list[str]:
    """Extract deduplicated digit-only PMID strings from any curated reference field.

    Prefers the explicit ``PMID <digits>`` form; if none is present (e.g. a bare integer or a
    ``quickpubmed`` number) falls back to standalone digit tokens. Returns ``[]`` for empty input
    or URL-only references (which carry no PubMed identifier).

    Tokens the format would refuse are dropped rather than returned: ``StudyRow.pmid`` caps at eight
    digits, so a nine-digit token passed through here reaches Pydantic and aborts the whole port.
    Use :func:`normalize_pmids_reporting` where the caller can surface what was dropped — a citation
    we discard is a grounding gap, and a silent one is worse than a loud one.
    """
    return normalize_pmids_reporting(raw)[0]


def normalize_pmids_reporting(raw: object) -> tuple[list[str], list[str]]:
    """:func:`normalize_pmids`, plus the tokens dropped for being unacceptable as a ``pmid``.

    Returns ``(accepted, dropped)``. ``dropped`` holds candidates that looked like an identifier and
    are not one the format can store — today only over-long digit runs. Callers with a warnings list
    should report them; the port must not fail on them, and must not truncate them into a different
    paper's id.
    """
    if raw is None:
        return [], []
    text = str(raw).strip()
    if not text:
        return [], []

    # URL references (superhuman) carry rs-ids, not PMIDs — treat as ungrounded.
    if "http" in text.lower() and "pubmed" not in text.lower():
        return [], []

    matches = _PMID_PREFIXED.findall(text)
    if not matches:
        matches = _BARE_DIGITS.findall(text)

    seen: set[str] = set()
    out: list[str] = []
    dropped: list[str] = []
    for pmid in matches:
        pmid = pmid.lstrip("0") or pmid  # keep canonical digits, but never empty
        if pmid in seen:
            continue
        seen.add(pmid)
        if _ACCEPTABLE_PMID.fullmatch(pmid):
            out.append(pmid)
        else:
            dropped.append(pmid)
    return out, dropped
