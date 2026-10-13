#!/usr/bin/env bash
# Weekly event-log prune, meant for a crontab entry such as
#   17 4 * * 0 /path/to/just-dna-lite/scripts/prune_dagster_history.sh
#
# cron runs with a near-empty environment and no login shell, so the repo root is
# taken from this script's own location and uv's is spelled out.
#
# The prune works with the stack up or down: rows are deleted either way, while
# file removals and the vacuum defer to a pass with Dagster stopped. A failing
# prune must not skip the log trim, which is why the exit status is captured
# instead of ending the script.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="${REPO}/logs/prune-dagster-history.log"
UV="$(command -v uv || echo "${HOME}/.local/bin/uv")"

cd "${REPO}" || exit 1
mkdir -p "${REPO}/logs"

{
    echo "=== $(date -Is) ==="
    "${UV}" run pipelines prune-dagster-history 2>&1
    status=$?
    [ "${status}" -eq 0 ] || echo "prune exited ${status}"
} >>"${LOG}"

# Keep the log itself from becoming the next thing that fills the disk.
tail -n 2000 "${LOG}" >"${LOG}.tmp" && mv "${LOG}.tmp" "${LOG}"
