#!/usr/bin/env bash
# A3 PRS benchmark (Section 4.2): just-prs v0.10.1 engines vs PLINK2 a6.33 on the primary genome,
# 100 PGS IDs, in the original and the fixed input configuration (a3/prs/bench_prs.py).
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
A3=/data/sources/just-dna-lite/docs/manuscript/benchmarks/a3
STAMP="$(date +%Y%m%dT%H%M)"

wait_quiet() {
    local waited=0
    while awk '{exit !($1 > 1.5)}' /proc/loadavg; do
        if (( waited >= 7200 )); then echo "load stayed above 1.5 for 2 h"; exit 4; fi
        sleep 30; waited=$((waited + 30))
    done
    echo "load gate open $(date -Is): $(cut -d' ' -f1-3 /proc/loadavg)"
}

cd /data/a3-bench/jdl
for config in original fixed; do
    wait_quiet
    "$A3/scripts/bp" "prs-$config" uv run --no-sync python -I "$A3/prs/bench_prs.py" \
        --config "$config" --vcf /data/a3-bench/inputs/anton/antonkulaga.vcf \
        --upstream /data/a3-bench/just-prs --plink2 /data/a3-bench/prs/plink2/plink2 \
        --work /data/a3-bench/prs --out "$A3/prs/results-$STAMP/$config"
done
echo "finished $(date -Is)"
