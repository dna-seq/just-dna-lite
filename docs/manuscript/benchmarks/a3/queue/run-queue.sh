#!/usr/bin/env bash
# Night benchmark queue: run every other *.sh here in lexical order, one at a time.
# Each job logs to logs/<name>.log and ends with done/<name> or failed/<name> (holding the exit
# code). A failure does not stop the queue. A job already in done/ is skipped, so a rerun resumes.
set -u
Q=/data/bench-queue
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
mkdir -p "$Q/logs" "$Q/done" "$Q/failed"
exec >>"$Q/logs/run-queue.log" 2>&1
echo "== queue start $(date -Is) load: $(cut -d' ' -f1-3 /proc/loadavg)"
for job in "$Q"/*.sh; do
    name="$(basename "$job" .sh)"
    [[ "$name" == run-queue ]] && continue
    if [[ -e "$Q/done/$name" ]]; then
        echo "-- $name: already done, skipped"
        continue
    fi
    rm -f "$Q/failed/$name"
    echo "-- $name: start $(date -Is) load: $(cut -d' ' -f1-3 /proc/loadavg)"
    bash "$job" >"$Q/logs/$name.log" 2>&1
    rc=$?
    if [[ $rc -eq 0 ]]; then
        touch "$Q/done/$name"
    else
        echo "$rc" >"$Q/failed/$name"
    fi
    echo "-- $name: exit $rc at $(date -Is)"
done
echo "== queue end $(date -Is)"
