#!/usr/bin/env bash
# A3 Generation II annotation benchmark (just-dna-lite), all four genomes, unattended.
# Plan: docs/manuscript/benchmarks/a3_benchmark_rerun_plan.md; record: a3/PROTOCOL.md.
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
A3=/data/sources/just-dna-lite/docs/manuscript/benchmarks/a3

echo "preflight $(date -Is) load: $(cut -d' ' -f1-3 /proc/loadavg)"
# Never beside a live app stack (two Dagster instances fight; it would also load the machine).
if ss -ltnH '( sport = :3000 or sport = :3005 or sport = :3006 )' | grep -q .; then
    echo "app stack is listening on 3000/3005/3006; refusing to time beside it"
    ss -ltnp '( sport = :3000 or sport = :3005 or sport = :3006 )'
    exit 3
fi
# Cold runs drop the page cache through a privileged container; prove it works before timing.
before=$(free -m | awk '/^Mem:/{print $6}')
docker run --rm --privileged \
    alpine:3.20@sha256:d9e853e87e55526f6b2917df91a2115c36dd7c696a35be12163d44e6e2a4b6bc \
    sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'
echo "page-cache drop works: buff/cache ${before} MB -> $(free -m | awk '/^Mem:/{print $6}') MB"

"$A3/scripts/run_jdl_series.sh"
echo "finished $(date -Is)"
