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


def normalize_pmids(raw: object) -> list[str]:
    """Extract deduplicated digit-only PMID strings from any curated reference field.

    Prefers the explicit ``PMID <digits>`` form; if none is present (e.g. a bare integer or a
    ``quickpubmed`` number) falls back to standalone digit tokens. Returns ``[]`` for empty input
    or URL-only references (which carry no PubMed identifier).
    """
    if raw is None:
        return []
    text = str(raw).strip()
    if not text:
        return []

    # URL references (superhuman) carry rs-ids, not PMIDs — treat as ungrounded.
    if "http" in text.lower() and "pubmed" not in text.lower():
        return []

    matches = _PMID_PREFIXED.findall(text)
    if not matches:
        matches = _BARE_DIGITS.findall(text)

    seen: set[str] = set()
    out: list[str] = []
    for pmid in matches:
        pmid = pmid.lstrip("0") or pmid  # keep canonical digits, but never empty
        if pmid not in seen:
            seen.add(pmid)
            out.append(pmid)
    return out
