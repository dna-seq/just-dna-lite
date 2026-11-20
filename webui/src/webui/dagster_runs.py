"""Dagster writes the web UI makes: registering a sample, creating and submitting a run.

Each function runs in a `webui.compute` worker (`await run_in_compute(fn, ...)`), never on the
event loop and never in a thread of the ASGI process. Creating a run built the job snapshot on the
loop (0.31 s measured for Start Analysis), and every write met the shared SQLite file there. Inputs
and results are plain values; Dagster's `MetadataValue`s pickle unchanged.
"""

from __future__ import annotations

from typing import Any

from dagster import AssetMaterialization

from just_dna_pipelines.annotation.assets import user_vcf_partitions
from just_dna_pipelines.annotation.definitions import defs
from webui.dagster_env import get_dagster_instance

# Runs the web UI starts carry this tag, so shutdown and startup touch only those.
WEBUI_SOURCE_TAG = "webui"


def register_vcf_source(partition_key: str, metadata: dict[str, Any]) -> None:
    """Add the sample's partition if missing and record a `user_vcf_source` materialization."""
    instance = get_dagster_instance()
    if partition_key not in instance.get_dynamic_partitions(user_vcf_partitions.name):
        instance.add_dynamic_partitions(user_vcf_partitions.name, [partition_key])
    instance.report_runless_asset_event(
        AssetMaterialization(asset_key="user_vcf_source", partition=partition_key, metadata=metadata)
    )


def create_webui_run(job_name: str, run_config: dict[str, Any], partition_key: str) -> str:
    """Create a run of *job_name* for the partition, tagged as the web UI's; returns its id."""
    run = get_dagster_instance().create_run_for_job(
        job_def=defs.resolve_job_def(job_name),
        run_config=run_config,
        tags={"dagster/partition": partition_key, "source": WEBUI_SOURCE_TAG},
    )
    return run.run_id


def submit_or_discard_run(run_id: str) -> tuple[bool, str]:
    """Hand the run to the daemon; if it refuses, delete the placeholder and say why.

    The caller then runs the job in a compute child, which creates the real run
    (`execute_job_with_run_discovery`). A refusal is the usual case when the web UI was
    started without the daemon ("External pipeline origin must be set").
    """
    instance = get_dagster_instance()
    try:
        instance.submit_run(run_id, workspace=None)
    except Exception as exc:  # any refusal means: run it ourselves
        instance.delete_run(run_id)
        return False, str(exc)
    return True, ""
