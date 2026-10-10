#!/usr/bin/env python3
"""Print one Dagster run's timing as JSON: the run record's timestamps and each step's duration.

Usage (DAGSTER_HOME set to the run's instance): dagster_stage_times.py RUN_ID

Run after the timed run, never during it. Imports dagster only, not the pipelines package.
"""

import json
import sys

from dagster import DagsterEventType, DagsterInstance, RunsFilter


def main() -> None:
    run_id = sys.argv[1]
    instance = DagsterInstance.get()
    [record] = instance.get_run_records(filters=RunsFilter(run_ids=[run_id]))
    starts: dict[str, float] = {}
    steps: dict[str, dict] = {}
    for entry in instance.all_logs(run_id):
        event = entry.dagster_event
        if event is None or event.step_key is None:
            continue
        if event.event_type == DagsterEventType.STEP_START:
            starts[event.step_key] = entry.timestamp
        elif event.event_type in (DagsterEventType.STEP_SUCCESS, DagsterEventType.STEP_FAILURE):
            begin = starts.get(event.step_key)
            steps[event.step_key] = {
                "status": event.event_type.value,
                "seconds": None if begin is None else round(entry.timestamp - begin, 3),
            }
    print(json.dumps({
        "run_id": run_id,
        "job_name": record.dagster_run.job_name,
        "status": record.dagster_run.status.value,
        "create_timestamp": record.create_timestamp.timestamp(),
        "start_time": record.start_time,
        "end_time": record.end_time,
        "steps": steps,
    }))


if __name__ == "__main__":
    main()
