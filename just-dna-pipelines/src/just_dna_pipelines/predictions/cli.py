"""``pipelines predict``: genome prediction models from the command line.

``run`` executes the same Dagster job the web UI submits (``predict_variant_effects_job``) in this
process, against the sample's existing ``user_vcf_normalized.parquet``, so a run started here shows
up in the Dagster UI when ``DAGSTER_HOME`` matches.
"""

from typing import Annotated

import typer
from dagster import DagsterInstance
from just_prs.reference import download_reference_fasta
from rich.console import Console
from rich.table import Table

from just_dna_pipelines.annotation.annotation_runner import ensure_dagster_home
from just_dna_pipelines.annotation.assets import user_vcf_partitions
from just_dna_pipelines.annotation.resources import get_user_output_dir
from just_dna_pipelines.predictions.download import ensure_model_files, model_files_present
from just_dna_pipelines.predictions.models import DEFAULT_PREDICTION_MODEL, PREDICTION_MODELS, get_prediction_model
from just_dna_pipelines.predictions.reference import resolve_reference_fasta
from just_dna_pipelines.predictions.run_config import (
    DEFAULT_MAX_VARIANTS,
    PREDICTION_ASSET,
    PREDICTION_JOB,
    VARIANT_SET_ANNOTATED,
    VARIANT_SET_REGION,
    parse_region,
    prediction_run_config,
)
from just_dna_pipelines.runtime import load_env

app = typer.Typer(name="predict", help="Genome prediction models (variant effects).", no_args_is_help=True)
console = Console()


@app.command("models")
def list_models() -> None:
    """List the prediction models and whether their files are cached."""
    load_env()
    table = Table(title="Prediction models")
    for column in ("id", "title", "licence", "revision", "cached"):
        table.add_column(column)
    for model in PREDICTION_MODELS.values():
        table.add_row(model.id, model.title, model.licence, model.revision[:12], "yes" if model_files_present(model) else "no")
    console.print(table)


@app.command("fetch-model")
def fetch_model(
    model: Annotated[str, typer.Option("--model", "-m", help="Model id.")] = DEFAULT_PREDICTION_MODEL,
) -> None:
    """Download a model's files (pinned revision) into the pipelines cache."""
    load_env()
    directory = ensure_model_files(get_prediction_model(model))
    console.print(f"[green]Model files ready:[/green] {directory}")


@app.command("fetch-reference")
def fetch_reference() -> None:
    """Fetch the Ensembl GRCh38 primary assembly through just-prs's reference lane (needs pysam)."""
    load_env()
    path = download_reference_fasta("GRCh38")
    console.print(f"[green]Reference FASTA ready:[/green] {path}")


@app.command("run")
def run(
    sample: Annotated[str, typer.Option("--sample", "-s", help="Sample name (VCF file name without .vcf/.vcf.gz).")],
    user: Annotated[str, typer.Option("--user", "-u", help="User the sample belongs to.")],
    model: Annotated[str, typer.Option("--model", "-m", help="Model id.")] = DEFAULT_PREDICTION_MODEL,
    region: Annotated[
        str | None, typer.Option("--region", "-r", help="Score every variant in chrom:start-end (at most 1 Mb).")
    ] = None,
    max_variants: Annotated[
        int, typer.Option("--max-variants", "-n", help="Score at most this many variants (0: no cap).")
    ] = DEFAULT_MAX_VARIANTS,
) -> None:
    """Score a sample's variants with a prediction model and write the parquet and HTML report.

    Without ``--region`` it scores the variants the sample's latest annotation run matched in modules.
    """
    # Building the definitions runs module discovery (network), so it stays inside the command, as in
    # `pipelines annotate`; listing models or fetching files must not pay for it.
    from just_dna_pipelines.annotation.definitions import defs

    load_env()
    get_prediction_model(model)
    if region:
        parse_region(region)
    resolve_reference_fasta()
    ensure_dagster_home()
    partition_key = f"{user}/{sample}"
    normalized = get_user_output_dir() / partition_key / "user_vcf_normalized.parquet"
    if not normalized.is_file():
        console.print(f"[red]No normalized VCF for {partition_key}[/red] ({normalized}). Run an analysis first.")
        raise typer.Exit(1)

    instance = DagsterInstance.get()
    if partition_key not in instance.get_dynamic_partitions(user_vcf_partitions.name):
        instance.add_dynamic_partitions(user_vcf_partitions.name, [partition_key])
    run_config = prediction_run_config(
        model_id=model,
        variant_set=VARIANT_SET_REGION if region else VARIANT_SET_ANNOTATED,
        region=region,
        max_variants=max_variants,
    )
    console.print(f"Predicting variant effects for [bold]{partition_key}[/bold] with {model}")
    result = defs.resolve_job_def(PREDICTION_JOB).execute_in_process(
        run_config=run_config,
        instance=instance,
        raise_on_error=False,
        tags={"dagster/partition": partition_key, "source": "cli"},
    )
    if not result.success:
        failures = [
            f"{event.step_key}: {event.event_specific_data.error.message.strip()}"
            for event in result.all_events
            if event.is_step_failure and event.event_specific_data is not None
        ]
        console.print(f"[bold red]Prediction failed[/bold red] (run_id={result.run_id})")
        for failure in failures:
            console.print(f"  {failure}")
        raise typer.Exit(1)
    materialization = result.asset_materializations_for_node(PREDICTION_ASSET)[-1]
    console.print(f"[bold green]Done[/bold green] (run_id={result.run_id})")
    for key in ("scored", "not_assessed", "provider", "parquet_path", "report_path"):
        console.print(f"  {key}: {materialization.metadata[key].value}")
