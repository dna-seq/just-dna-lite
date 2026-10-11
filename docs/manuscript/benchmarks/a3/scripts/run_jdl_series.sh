#!/usr/bin/env bash
# Generation II annotation series for every A3 genome: warm-up, then 3 cold, 11 warm and 5 full runs
# in the seeded order, plus one Ensembl run on the primary genome. Each genome is one bp step.
# Arguments name the genomes to run (default: all four, in the order below).
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

GENOMES=("$@")
(( ${#GENOMES[@]} )) || GENOMES=(primary second_caller community_reference calibration)
for genome in "${GENOMES[@]}"; do
    case "$genome" in
        primary) run primary "$I/anton/antonkulaga.vcf" --ensembl-extra ;;
        second_caller) run second_caller "$I/livia/SIMHIFQTILQ.hard-filtered.vcf.gz" ;;
        community_reference) run community_reference "$I/hg002/HG002.output.vcf.gz" ;;
        calibration) run calibration "$I/newton/newtonwinter.GRCh38.ens106.deep.vcf.gz" ;;
        *) echo "unknown genome: $genome" >&2; exit 2 ;;
    esac
done
