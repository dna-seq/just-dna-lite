"""
Gene-symbol reconciliation for the ClinVar gene-panel modules.

Gen-I panel gene lists (``just_cardio``/``just_cancer`` ``data/genes.txt``) carry legacy HGNC symbols
and a few data-entry typos. ClinVar's ``GENEINFO`` uses current NCBI symbols, so a panel entry under
an old alias (e.g. ``MRE11A`` → ``MRE11``, ``CCDC114`` → ``ODAD1``) silently matches nothing. This
module resolves aliases to current symbols using NCBI's authoritative ``Homo_sapiens.gene_info`` table
(``Symbol`` + ``Synonyms`` columns) so the panel filter catches those variants. Symbols that are
neither current nor a known synonym (true typos) are reported, never guessed.
"""

import gzip
import os
from pathlib import Path
from typing import Optional

# NCBI human gene_info (Symbol + Synonyms). Override with $JUST_DNA_GENE_INFO.
DEFAULT_GENE_INFO = Path(
    os.environ.get("JUST_DNA_GENE_INFO", "/data/just-dna-cache/ncbi_gene/Homo_sapiens.gene_info.gz")
)


class SymbolResolver:
    """Maps legacy/alias gene symbols to current NCBI symbols."""

    def __init__(self, official: set[str], synonym_to_official: dict[str, str]) -> None:
        self.official = official
        self.synonym_to_official = synonym_to_official

    def current(self, symbol: str) -> Optional[str]:
        """Return the current symbol for ``symbol`` (itself if already current, else its alias
        target), or ``None`` if it's neither a current symbol nor a known synonym (a likely typo)."""
        s = symbol.strip().upper()
        if s in self.official:
            return s
        # HGNC mitochondrial symbols (MT-ND1, MT-TL1, …) are what ClinVar's GENEINFO uses, but NCBI
        # gene_info stores them unprefixed (ND1, TRNL1), so they miss the lookup above. They are
        # valid — keep them as-is rather than flagging them as typos.
        if s.startswith("MT-"):
            return s
        return self.synonym_to_official.get(s)


def load_symbol_resolver(gene_info_path: Path = DEFAULT_GENE_INFO) -> Optional[SymbolResolver]:
    """Build a resolver from NCBI gene_info, or ``None`` if the file isn't present (skip resolution)."""
    if not gene_info_path.exists():
        return None
    official: set[str] = set()
    synonym_to_official: dict[str, str] = {}
    with gzip.open(gene_info_path, "rt") as handle:
        handle.readline()  # header
        for line in handle:
            cols = line.rstrip("\n").split("\t")
            if len(cols) < 5:
                continue
            symbol = cols[2].strip().upper()
            official.add(symbol)
            for synonym in cols[4].split("|"):
                syn = synonym.strip().upper()
                if syn and syn != "-":
                    synonym_to_official.setdefault(syn, symbol)  # first (primary) mapping wins
    return SymbolResolver(official, synonym_to_official)


#: Curation decisions on the Gen-I panel gene lists, not guesses. Every entry is a **systematic
#: single-class OCR substitution** of a real, well-annotated cancer-predisposition gene — `B`↔`8`,
#: `5`↔`S`, `D`↔`O`, plus one letter transposition (`ATK1`/`AKT1`) — in a list that reads as scanned
#: from a printed panel. Each was verified two ways before being written here: the authored spelling
#: resolves to **nothing** in NCBI `gene_info` (neither a current symbol nor any known synonym), and
#: the corrected spelling resolves to itself as a current symbol.
#:
#: Left unresolved, these are not merely cosmetic. `resolve_panel_genes` correctly reports rather than
#: guesses, so the panel simply never asked ClinVar for them: **708 pathogenic/likely-pathogenic
#: records at ≥1★ are absent from `cancer` because of these 13 strings**, 526 of them ARID1B and 175
#: KDM5C, and RAD51 and SF3B1 among the rest. That is the highest-consequence failure mode in this
#: corpus — a cancer panel silently missing a gene reads exactly like a gene with no pathogenic variant.
#:
#: This is the panel-route counterpart of `adapters._CURATED_SYMBOL_FIXES`, which does the same job for
#: the curated modules' per-variant `gene` cells. Anything less certain than these belongs in
#: `unresolved` and stays reported.
_CURATED_PANEL_SYMBOL_FIXES: dict[str, str] = {
    "ARID18": "ARID1B",   # B -> 8
    "ATK1": "AKT1",       # KT transposed
    "CD798": "CD79B",     # B -> 8
    "CDKN18": "CDKN1B",   # B -> 8
    "CDKN28": "CDKN2B",   # B -> 8
    "EPHAS": "EPHA5",     # 5 -> S
    "ETVS": "ETV5",       # 5 -> S
    "HSO381": "HSD3B1",   # D -> O, B -> 8
    "INPP48": "INPP4B",   # B -> 8
    "KDMSC": "KDM5C",     # 5 -> S
    "LRP18": "LRP1B",     # B -> 8
    "RADS1": "RAD51",     # 5 -> S
    "SF381": "SF3B1",     # B -> 8
}


def resolve_panel_genes(
    genes: set[str], resolver: Optional[SymbolResolver]
) -> tuple[set[str], dict[str, str], list[str]]:
    """Expand a panel gene set to the current symbols ClinVar uses.

    Returns ``(wanted, alias_map, unresolved)``: ``wanted`` is the set to match against ClinVar
    (originals plus resolved current symbols), ``alias_map`` records ``old -> current`` remaps, and
    ``unresolved`` lists symbols that are neither current nor a known synonym (likely typos). Without
    a resolver, everything passes through unchanged and ``unresolved`` is empty.

    ``_CURATED_PANEL_SYMBOL_FIXES`` is consulted first and its remaps appear in ``alias_map`` like any
    other, so a build states them. They are recorded corrections to the source list, not inferences.
    """
    if resolver is None:
        return set(genes), {}, []
    wanted: set[str] = set()
    alias_map: dict[str, str] = {}
    unresolved: list[str] = []
    for gene in genes:
        g = gene.strip().upper()
        if not g:
            continue
        current = _CURATED_PANEL_SYMBOL_FIXES.get(g) or resolver.current(g)
        if current is None:
            unresolved.append(g)
            wanted.add(g)  # keep it anyway; it simply won't match ClinVar
            continue
        wanted.add(current)
        if current != g:
            alias_map[g] = current
    return wanted, alias_map, sorted(unresolved)
