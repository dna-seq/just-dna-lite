#!/usr/bin/env bash
# Generation II annotation series for every A3 genome: warm-up, then 3 cold, 11 warm and 5 full runs
# in the seeded order, plus one Ensembl run on the primary genome. Each genome is one bp step.
set -euo pipefail

A3="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
I=/data/a3-bench/inputs
# A series directory is used once; each launch gets its own (override with A3_SERIES).
SERIES="${A3_SERIES:-/data/a3-bench/series/$(date +%Y%m%dT%H%M)/jdl}"
MODULES=(-m cancer -m cardio -m coronary -m lipidmetabolism -m longevitymap -m pathogenic
         -m pharmgkb -m superhuman -m thrombophilia -m vo2max)

run() {
    local genome="$1" vcf="$2"
    shift 2
    (cd /data/a3-bench/jdl && "$A3/scripts/bp" "jdl-series-$genome" \
        uv run --no-sync python -I "$A3/scripts/bench_annotation.py" --tool jdl --genome "$genome" \
        --vcf "$vcf" --series-dir "$SERIES/$genome" "${MODULES[@]}" "$@")
}

run primary "$I/anton/antonkulaga.vcf" --ensembl-extra
run second_caller "$I/livia/SIMHIFQTILQ.hard-filtered.vcf.gz"
run community_reference "$I/hg002/HG002.output.vcf.gz"
run calibration "$I/newton/newtonwinter.GRCh38.ens106.deep.vcf.gz"
