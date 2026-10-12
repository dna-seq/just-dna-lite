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
# A3 night 2: fairness pair. Generation I with dbSNP only (no postaggregators, VCF reporter), 3 runs
# on the primary genome, the counterpart of Generation II with the full Ensembl join (job 62).
ov oakvar-series-primary-dbsnp-only primary "$I/anton/antonkulaga.vcf" /data/a3-bench/series/20261013T0200/oakvar/primary-dbsnp \
    --full 3 --full-label dbsnp_only --oakvar-args -a dbsnp -t vcf
