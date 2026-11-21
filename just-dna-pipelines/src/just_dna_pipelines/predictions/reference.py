"""The GRCh38 reference sequence around a variant, read from an indexed FASTA with pyfaidx.

**Which FASTA.** The first that exists of:

1. ``$JUST_DNA_REFERENCE_FASTA`` (an explicit file);
2. ``<JUST_DNA_PIPELINES_CACHE_DIR>/reference/grch38/Homo_sapiens.GRCh38.dna.primary_assembly.fa``,
   which ``ensure_reference_fasta`` fills (the ``grch38_reference_fasta`` Dagster asset);
3. just-prs's reference-FASTA lane (``just_prs.reference.reference_fasta_path("GRCh38")``), so a
   copy just-prs already fetched is not fetched again.

All three are the Ensembl primary assembly, whose contigs are unprefixed (``1``, ``X``, ``MT``).
Contig names on both sides go through ``just_dna_format.vrs.normalize_chrom`` before they meet.

**Fetching.** ``ensure_reference_fasta`` streams Ensembl's ``.fa.gz`` (the URL just-prs pins, so the
release is named in one place), decompresses it on the way to disk and builds the ``.fai`` with
pyfaidx. just-prs's own downloader needs pysam only to build that index, and pysam has no Windows
wheels; pyfaidx is pure Python and is what reads the file anyway.

**Coordinates.** ``user_vcf_normalized.parquet`` keeps polars-bio's ``start``, which is the VCF
``POS`` (1-based; ``start == end`` for an SNV). A window of ``size`` bases is centred so that the
variant sits at 0-based index ``size // 2``.
"""

import gzip
import os
from collections.abc import Callable
from pathlib import Path

import aiohttp
import fsspec
import numpy as np
from eliot import log_message, start_action
from just_dna_format.vrs import normalize_chrom
from just_prs.reference import REFERENCE_FASTA, reference_fasta_path
from pyfaidx import Faidx, Fasta

from just_dna_pipelines.annotation.resources import get_cache_dir

REFERENCE_FASTA_ENV = "JUST_DNA_REFERENCE_FASTA"
GRCH38_FASTA_NAME = "Homo_sapiens.GRCh38.dna.primary_assembly.fa"
GRCH38_FASTA_URL: str = REFERENCE_FASTA["GRCh38"]["url"]
COPY_CHUNK_BYTES = 16 * 1024 * 1024
PROGRESS_EVERY_BYTES = 256 * 1024 * 1024
# A stalled connection fails after this long without data; the whole download has no time limit
# (aiohttp's default 5-minute total would cut a ~900 MB download on a slow link).
SOCKET_READ_TIMEOUT_S = 300

# A 0, C 1, G 2, T 3, anything else (N, IUPAC codes) 4. Lowercase is RepeatMasker soft-masking in
# Ensembl FASTA: the base is still known, so it encodes like uppercase.
BASE_CODES: dict[str, int] = {"A": 0, "C": 1, "G": 2, "T": 3}
UNKNOWN_BASE_CODE = 4
_LOOKUP = np.full(256, UNKNOWN_BASE_CODE, dtype=np.int64)
for _base, _code in BASE_CODES.items():
    _LOOKUP[ord(_base)] = _code
    _LOOKUP[ord(_base.lower())] = _code


def encode_bases(sequence: str) -> np.ndarray:
    """One int64 code per base (A 0, C 1, G 2, T 3, other 4), the model's ``bases`` input row."""
    return _LOOKUP[np.frombuffer(sequence.encode("ascii"), dtype=np.uint8)]


def cached_reference_fasta_path() -> Path:
    """Where ``ensure_reference_fasta`` puts the FASTA (may not exist yet)."""
    return get_cache_dir() / "reference" / "grch38" / GRCH38_FASTA_NAME


def reference_fasta_candidates() -> list[Path]:
    """Where a GRCh38 FASTA is looked for, in order."""
    candidates: list[Path] = []
    explicit = os.environ.get(REFERENCE_FASTA_ENV, "").strip()
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates.append(cached_reference_fasta_path())
    candidates.append(reference_fasta_path("GRCh38"))
    return candidates


def download_reference_fasta(
    destination: Path,
    url: str = GRCH38_FASTA_URL,
    on_progress: Callable[[int], None] | None = None,
) -> Path:
    """Stream the gzipped FASTA at *url* to *destination*, uncompressed, with its ``.fai``.

    Both files are written under names unique to this process and renamed into place index first,
    so a reader never sees a FASTA without its index, a cut download never lands under the final
    name (gzip raises on a truncated stream), and two runs fetching at once each finish a whole file.
    ``on_progress`` gets the uncompressed bytes written so far, every 256 MiB.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(f"{destination.name}.{os.getpid()}.downloading")
    partial_index = partial.with_name(partial.name + ".fai")
    timeout = aiohttp.ClientTimeout(total=None, sock_read=SOCKET_READ_TIMEOUT_S)
    with start_action(action_type="reference_fasta_download", url=url, dest=str(destination)):
        try:
            with fsspec.open(url, "rb", block_size=0, client_kwargs={"timeout": timeout}) as raw, gzip.open(
                raw, "rb"
            ) as source, partial.open("wb") as target:
                written = 0
                reported = 0
                while chunk := source.read(COPY_CHUNK_BYTES):
                    target.write(chunk)
                    written += len(chunk)
                    if on_progress is not None and written - reported >= PROGRESS_EVERY_BYTES:
                        on_progress(written)
                        reported = written
            Faidx(str(partial), indexname=str(partial_index)).close()
            partial_index.replace(destination.with_name(destination.name + ".fai"))
            partial.replace(destination)
        finally:
            partial.unlink(missing_ok=True)
            partial_index.unlink(missing_ok=True)
        log_message(message_type="reference_fasta_ready", path=str(destination), bytes=destination.stat().st_size)
    return destination


def ensure_reference_fasta(on_progress: Callable[[int], None] | None = None) -> Path:
    """The FASTA ``resolve_reference_fasta`` would use, fetched into the pipelines cache when there is none."""
    existing = next((path for path in reference_fasta_candidates() if path.is_file()), None)
    if existing is not None:
        return existing
    return download_reference_fasta(cached_reference_fasta_path(), on_progress=on_progress)


def resolve_reference_fasta() -> Path:
    """The first candidate FASTA that exists, or an error naming every place looked and how to fill one."""
    candidates = reference_fasta_candidates()
    for path in candidates:
        if path.is_file():
            return path
    looked = "\n".join(f"  - {p}" for p in candidates)
    raise FileNotFoundError(
        "No GRCh38 reference FASTA found. Looked in:\n"
        f"{looked}\n"
        f"Materialize the grch38_reference_fasta asset (or run `uv run pipelines predict fetch-reference`), "
        f"or set {REFERENCE_FASTA_ENV} to an uncompressed Ensembl GRCh38 primary assembly."
    )


class ReferenceGenome:
    """Random access to one FASTA by normalized contig name."""

    def __init__(self, fasta_path: Path) -> None:
        self.path = fasta_path
        # as_raw: plain str slices; pyfaidx writes the .fai beside the FASTA if it is missing.
        self._fasta = Fasta(str(fasta_path), as_raw=True, sequence_always_upper=False)
        self._names: dict[str, str] = {}
        for name in self._fasta.keys():
            key = normalize_chrom(name)
            if key is not None:
                self._names.setdefault(key, name)

    def close(self) -> None:
        self._fasta.close()

    def contig(self, chrom: str) -> str | None:
        """The FASTA's own name for this contig, or None when the assembly has no such contig."""
        key = normalize_chrom(chrom)
        return self._names.get(key) if key is not None else None

    def contig_length(self, chrom: str) -> int | None:
        name = self.contig(chrom)
        return len(self._fasta[name]) if name is not None else None

    def bases(self, chrom: str, start: int, end: int) -> str | None:
        """Bases at 1-based inclusive ``start..end`` as written in the FASTA (soft-masking kept).

        None when the contig is unknown or the interval leaves it.
        """
        name = self.contig(chrom)
        if name is None or start < 1:
            return None
        if end > len(self._fasta[name]):
            return None
        return str(self._fasta[name][start - 1 : end])

    def window(self, chrom: str, pos: int, size: int) -> str | None:
        """``size`` bases with the 1-based ``pos`` at index ``size // 2``, or None off the contig."""
        first = pos - size // 2
        return self.bases(chrom, first, first + size - 1)
