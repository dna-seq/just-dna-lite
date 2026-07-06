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


def resolve_panel_genes(
    genes: set[str], resolver: Optional[SymbolResolver]
) -> tuple[set[str], dict[str, str], list[str]]:
    """Expand a panel gene set to the current symbols ClinVar uses.

    Returns ``(wanted, alias_map, unresolved)``: ``wanted`` is the set to match against ClinVar
    (originals plus resolved current symbols), ``alias_map`` records ``old -> current`` remaps, and
    ``unresolved`` lists symbols that are neither current nor a known synonym (likely typos). Without
    a resolver, everything passes through unchanged and ``unresolved`` is empty.
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
        current = resolver.current(g)
        if current is None:
            unresolved.append(g)
            wanted.add(g)  # keep it anyway; it simply won't match ClinVar
            continue
        wanted.add(current)
        if current != g:
            alias_map[g] = current
    return wanted, alias_map, sorted(unresolved)
