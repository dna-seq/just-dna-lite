#!/usr/bin/env bash
# Pull OakVar's own step and module timings out of each timed run's container log, which is too
# large to commit (about 6 million lines, nearly all vcf-converter RefCall skips).
#
#   extract_steps.sh SERIES_DIR > steps.tsv
#   SERIES_DIR is the oakvar series directory, e.g. /data/a3-bench/series/20261011T0810/oakvar
set -euo pipefail

series="$1"
printf 'genome\trun\tkind\tname\tseconds\n'
for log in "$series"/*/*/cli.log; do
    run_dir="$(dirname "$log")"
    run="$(basename "$run_dir")"
    genome="$(basename "$(dirname "$run_dir")")"
    grep -E 'oakvar +(.+ finished in [0-9.]+s|finished normally\. Runtime: [0-9.]+s)$' "$log" \
        | sed -E 's/^[0-9\/]+ [0-9:]+ oakvar +//' \
        | awk -v g="$genome" -v r="$run" '
            /^finished normally/ { sub(/s$/, "", $NF); print g "\t" r "\ttotal\truntime\t" $NF; next }
            { secs = $NF; sub(/s$/, "", secs)
              name = $0; sub(/ finished in [0-9.]+s$/, "", name)
              kind = (name ~ / step$/) ? "step" : "module"
              sub(/ step$/, "", name)
              print g "\t" r "\t" kind "\t" name "\t" secs }'
done
