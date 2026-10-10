#!/usr/bin/env python3
"""Describe each benchmark input VCF and write a3/inputs.json.

Usage: inputs_check.py OUT_JSON ROLE=PATH[@SOURCE] [ROLE=PATH[@SOURCE] ...]

For each file: size, md5, sha256, record count (non-header lines), and the header lines that name
the caller and the reference. Standard library only, so it runs before any project environment.
"""

import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

CALLER_HEADER = re.compile(
    r"^##(DeepVariant_version|DRAGENVersion|DRAGENCommandLine|source|reference|fileformat)=", re.I
)


def describe(path: Path) -> dict:
    md5 = hashlib.md5()
    sha = hashlib.sha256()
    with path.open("rb") as raw:
        for chunk in iter(lambda: raw.read(1 << 22), b""):
            md5.update(chunk)
            sha.update(chunk)

    opener = gzip.open if path.suffix in {".gz", ".bgz"} else open
    records = 0
    snv = 0
    header: list[str] = []
    contigs: set[str] = set()
    with opener(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("##"):
                if CALLER_HEADER.match(line):
                    header.append(line.rstrip("\n")[:300])
                continue
            if line.startswith("#"):
                continue
            records += 1
            fields = line.split("\t", 6)
            contigs.add(fields[0])
            if len(fields[3]) == 1 and all(len(a) == 1 for a in fields[4].split(",")):
                snv += 1

    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "md5": md5.hexdigest(),
        "sha256": sha.hexdigest(),
        "records": records,
        "snv_records": snv,
        "other_records": records - snv,
        "contigs": len(contigs),
        "caller_headers": header,
    }


def main() -> None:
    out = Path(sys.argv[1])
    result = json.loads(out.read_text()) if out.exists() else {}
    for arg in sys.argv[2:]:
        role, _, rest = arg.partition("=")
        path_str, _, source = rest.partition("@")
        entry = describe(Path(path_str))
        entry["source"] = source or None
        result[role] = entry
        print(json.dumps({role: {k: v for k, v in entry.items() if k != "caller_headers"}}, indent=1))
        for line in entry["caller_headers"]:
            print("   ", line[:160])
    out.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
