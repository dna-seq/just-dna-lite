#!/usr/bin/env bash
# A3 Generation I annotation benchmark (OakVar 2.13.1 in Docker), unattended: 3 runs on the primary
# genome, then 1 on the calibration genome. Each run is a fresh job directory with no page-cache drop
# (the "full" run type). Plan: docs/manuscript/benchmarks/a3_benchmark_rerun_plan.md;
# record: a3/PROTOCOL.md (module install, the cravat.util shim and the smoke test).
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
A3=/data/sources/just-dna-lite/docs/manuscript/benchmarks/a3
I=/data/a3-bench/inputs
SERIES="${A3_SERIES:-/data/a3-bench/series/$(date +%Y%m%dT%H%M)/oakvar}"
OV_ARGS=(-a dbsnp clinvar omim ncbigene pubmed gnomad sift cardioboost
         -p just_cancer just_cardio just_coronary just_drugs just_longevitymap just_lipidmetabolism
            just_thrombophilia just_superhuman just_vo2max
         -t longevity2reporter)

echo "preflight $(date -Is) load: $(cut -d' ' -f1-3 /proc/loadavg)"
if ss -ltnH '( sport = :3000 or sport = :3005 or sport = :3006 )' | grep -q .; then
    echo "app stack is listening on 3000/3005/3006; refusing to time beside it"
    exit 3
fi
docker image inspect jdl-bench-oakvar:2.13.1 --format 'image {{.Id}}'

run() {
    local genome="$1" vcf="$2" n="$3"
    # The driver needs psutil; it runs from the pinned Generation II worktree's environment, as the
    # Generation II series does.
    (cd /data/a3-bench/jdl && "$A3/scripts/bp" "oakvar-series-$genome" \
        uv run --no-sync python -I "$A3/scripts/bench_annotation.py" --tool oakvar --genome "$genome" --vcf "$vcf" \
        --series-dir "$SERIES/$genome" --no-warmup --cold 0 --warm 0 --full "$n" \
        --oakvar-args "${OV_ARGS[@]}")
}

run primary "$I/anton/antonkulaga.vcf" 3
run calibration "$I/newton/newtonwinter.GRCh38.ens106.deep.vcf.gz" 1
echo "finished $(date -Is)"
