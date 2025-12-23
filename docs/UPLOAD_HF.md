# Hugging Face Hub datasets

This repo pulls reference data from Hugging Face Hub for annotation (it does not currently provide a first-class "upload my dataset" CLI).

## Overview

The `ensembl_annotations` Dagster asset downloads the Ensembl Parquet shards from Hugging Face into a local cache. Downstream assets (e.g. user annotation) read from that cache.

## Prerequisites

### Authentication

If the dataset is private (or rate limits become an issue), set a Hugging Face token:

```bash
export HF_TOKEN="your_token_here"
```

### Repository Access

You only need read access to download. The default Ensembl dataset used by this repo is:

- `just-dna-seq/ensembl_variations`

## Usage

### Materialize the reference cache (Dagster)

1. Start Dagster: `uv run dagster-ui` (or `uv run start`)
2. In the UI, materialize `ensembl_annotations`
3. The downloaded cache will land under:

- default: your OS user cache for `just-dna-pipelines`
- override: `JUST_DNA_PIPELINES_CACHE_DIR`

## Troubleshooting

### Authentication Errors

If you get authentication errors or rate limiting:

```bash
# Login to Hugging Face CLI
huggingface-cli login

# Or set token explicitly
export HF_TOKEN="your_token_here"
```

### Permission Errors

If the download fails with authorization errors, make sure your `HF_TOKEN` has access to the dataset and that it is exported in the environment used by Dagster.

### Network Errors

Check the Dagster run logs for the failing asset materialization. If you run from the terminal, the `dagster-ui` process will print the error and the path where it tried to write the cache.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `HF_TOKEN` | Hugging Face API token |
| `JUST_DNA_PIPELINES_CACHE_DIR` | Base cache directory for reference assets |
| `JUST_DNA_PIPELINES_OUTPUT_DIR` | Base output directory for user assets |
| `JUST_DNA_PIPELINES_INPUT_DIR` | Base input directory for user VCFs |

## Notes

- Reference downloads use `huggingface_hub.snapshot_download`.

