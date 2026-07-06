"""
Genotype normalization for the v1 port.

The DSL's ``VariantRow.genotype`` must be exactly two uppercase A/C/G/T alleles, slash-separated
and alphabetically sorted (e.g. ``A/G``). Gen-I data expresses genotypes as concatenated pairs
(``AA``/``AG``/``GG``) or, in longevitymap, as an allele plus a zygosity (``het``/``hom``) that must
be combined with the reference allele. Rows that can't yield two clean nucleotides return ``None``
so the caller can skip and log them rather than emit an invalid row.
"""

from typing import Optional

_NUCS: frozenset[str] = frozenset("ACGT")


def _clean(allele: object) -> Optional[str]:
    if allele is None:
        return None
    a = str(allele).strip().upper()
    return a if len(a) == 1 and a in _NUCS else None


def to_slash_genotype(pair: object) -> Optional[str]:
    """Convert a concatenated genotype like ``AG`` (or ``A/G``) into sorted ``A/G`` form."""
    if pair is None:
        return None
    raw = str(pair).strip().upper().replace("/", "").replace("|", "")
    if len(raw) != 2:
        return None
    a, b = _clean(raw[0]), _clean(raw[1])
    if a is None or b is None:
        return None
    return "/".join(sorted((a, b)))


def genotype_from_allele_zygosity(
    allele: object, zygosity: object, ref: object, alt: object
) -> Optional[str]:
    """Build a genotype from an effect allele + zygosity (longevitymap ``allele_weights``).

    ``hom`` → two copies of the effect allele; ``het`` → the effect allele paired with the other
    (reference) allele. Falls back to ref/alt when the reference can't be inferred.
    """
    eff = _clean(allele)
    if eff is None:
        return None
    zyg = str(zygosity).strip().lower() if zygosity is not None else ""
    ref_c, alt_c = _clean(ref), _clean(alt)

    if zyg.startswith("hom"):
        return "/".join(sorted((eff, eff)))
    if zyg.startswith("het"):
        other = ref_c if eff != ref_c else alt_c
        if other is None:
            other = alt_c if eff == ref_c else ref_c
        if other is None:
            return None
        return "/".join(sorted((eff, other)))
    return None


def state_from_weight(weight: Optional[float]) -> str:
    """Derive the risk-direction label from a curated weight's sign.

    Reproduces the v1 reporter's ``get_color(weight)`` behavior: negative = risk, positive =
    protective, zero/None = neutral. The weight itself is never modified — this only supplies the
    ``state`` label the DSL requires when the source carries no explicit risk direction.
    """
    if weight is None:
        return "neutral"
    if weight < 0:
        return "risk"
    if weight > 0:
        return "protective"
    return "neutral"
