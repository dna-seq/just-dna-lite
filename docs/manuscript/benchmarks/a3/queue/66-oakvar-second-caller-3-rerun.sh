#!/usr/bin/env bash
# A3 night 2, Generation I full run 3 of 3 on the second-caller genome (Livia, DRAGEN), again. Job 65's
# OakVar run was killed at 19:34:08 on 2026-10-13 when a PackageKit update restarted the Docker daemon
# (docker-ce 29.8.2 -> 29.9.0); its 18 Generation II runs had finished, so this job holds only the
# OakVar run. New series directory: a series directory is used once, and the failed one stays as
# evidence (make_tables.py FAILED). Re-queued 2026-10-15 at the user's call.
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
A3=/data/sources/just-dna-lite/docs/manuscript/benchmarks/a3
I=/data/a3-bench/inputs
echo "preflight $(date -Is) load: $(cut -d' ' -f1-3 /proc/loadavg) kernel: $(uname -r) $(docker --version)"
if ss -ltnH '( sport = :3000 or sport = :3005 or sport = :3006 )' | grep -q .; then
    echo "app stack is listening on 3000/3005/3006; refusing to time beside it"
    exit 3
fi
OV_FULL=(-a dbsnp clinvar omim ncbigene pubmed gnomad sift cardioboost
         -p just_cancer just_cardio just_coronary just_drugs just_longevitymap just_lipidmetabolism
            just_thrombophilia just_superhuman just_vo2max
         -t longevity2reporter)
cd /data/a3-bench/jdl
"$A3/scripts/bp" oakvar-series-second-caller-3-rerun \
    uv run --no-sync python -I "$A3/scripts/bench_annotation.py" --tool oakvar --genome second_caller \
    --vcf "$I/livia/SIMHIFQTILQ.hard-filtered.vcf.gz" \
    --series-dir /data/a3-bench/series/20261013T0200/oakvar/second_caller-3-rerun \
    --no-warmup --cold 0 --warm 0 --full 1 --oakvar-args "${OV_FULL[@]}"
