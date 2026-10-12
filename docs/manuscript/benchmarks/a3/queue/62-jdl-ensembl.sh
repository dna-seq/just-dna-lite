#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
A3=/data/sources/just-dna-lite/docs/manuscript/benchmarks/a3
I=/data/a3-bench/inputs
echo "preflight $(date -Is) load: $(cut -d' ' -f1-3 /proc/loadavg)"
if ss -ltnH '( sport = :3000 or sport = :3005 or sport = :3006 )' | grep -q .; then
    echo "app stack is listening on 3000/3005/3006; refusing to time beside it"
    exit 3
fi
OV_FULL=(-a dbsnp clinvar omim ncbigene pubmed gnomad sift cardioboost
         -p just_cancer just_cardio just_coronary just_drugs just_longevitymap just_lipidmetabolism
            just_thrombophilia just_superhuman just_vo2max
         -t longevity2reporter)
ov() {  # ov <slug> <genome> <vcf> <series-dir> <driver args...>
    local slug="$1" genome="$2" vcf="$3" series="$4"; shift 4
    (cd /data/a3-bench/jdl && "$A3/scripts/bp" "$slug" \
        uv run --no-sync python -I "$A3/scripts/bench_annotation.py" --tool oakvar --genome "$genome" \
        --vcf "$vcf" --series-dir "$series" --no-warmup --cold 0 --warm 0 "$@")
}
# A3 night 2: Generation II full + Ensembl (annotate_all_job), 3 runs on the primary genome (n=1 -> 4).
(cd /data/a3-bench/jdl && "$A3/scripts/bp" jdl-series-primary-ensembl \
    uv run --no-sync python -I "$A3/scripts/bench_annotation.py" --tool jdl --genome primary \
    --vcf "$I/anton/antonkulaga.vcf" --series-dir /data/a3-bench/series/20261013T0200/jdl/primary-ensembl --no-warmup \
    --cold 0 --warm 0 --full 0 --ensembl 3 \
    -m cancer -m cardio -m coronary -m lipidmetabolism -m longevitymap -m pathogenic \
    -m pharmgkb -m superhuman -m thrombophilia -m vo2max)
