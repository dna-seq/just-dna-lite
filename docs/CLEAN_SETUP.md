# Clean Setup Guide

This document explains the Dagster instance bootstrap used by the workspace scripts.

## What Happens on First Run

When you run `uv run start` or `uv run dagster-ui` for the first time, the script will:

- create `data/interim/dagster/` (or `$DAGSTER_HOME` if set)
- create `dagster.yaml` if missing, with auto-materialization enabled

## Setup Steps

### 1. Clone and Install

```bash
git clone git@github.com:dna-seq/just-dna-lite.git
cd just-dna-lite
uv sync
```

### 2. Start the Application

Choose one of these commands from the repo root:

```bash
# Start full stack (Web UI + Dagster pipelines)
uv run start

# Or start only Dagster UI
uv run dagster-ui

# Or start only Web UI
uv run ui
```

On first run you should see a line confirming the config file was created:

```
Created Dagster config at .../data/interim/dagster/dagster.yaml
```

## Configuration Details

### Default dagster.yaml

The generated `dagster.yaml` currently includes:

```yaml
# Dagster instance configuration
# Storage defaults to DAGSTER_HOME

# Enable auto-materialization for assets with AutoMaterializePolicy
auto_materialize:
  enabled: true
  minimum_interval_seconds: 60
```

### Customizing Configuration

If you need to customize Dagster configuration:

1. Check `dagster.yaml.template` in the repo root for options and examples.
2. Edit `data/interim/dagster/dagster.yaml` (or `$DAGSTER_HOME/dagster.yaml`) directly.
3. The bootstrap will not overwrite an existing config.

### Git Ignore Strategy

- `data/interim/dagster/dagster.yaml` is gitignored (instance-specific).
- `dagster.yaml.template` is tracked as a reference.

## How It Works

### Initialization Function

The bootstrap code lives in `src/just_dna_lite/cli.py` (`_ensure_dagster_config`).

### When It Runs

The initialization is called by:

1. Workspace scripts: `uv run start` and `uv run dagster-ui`.
2. The Web UI when it needs a Dagster instance (see `webui/src/webui/state.py`).

## Environment Variables

You can override the default location:

```bash
# Custom Dagster home
export DAGSTER_HOME="$HOME/.local/share/just-dna-lite/dagster"

# Pipeline paths
export JUST_DNA_PIPELINES_CACHE_DIR="$HOME/.cache/just-dna-pipelines"
export JUST_DNA_PIPELINES_OUTPUT_DIR="$PWD/data/output/users"
export JUST_DNA_PIPELINES_INPUT_DIR="$PWD/data/input/users"
```

## Verification

To verify your setup is working:

```bash
# Run the test suite
uv run pytest just-dna-pipelines/tests/test_clean_setup.py -vvv
uv run pytest just-dna-pipelines/tests/test_dagster_config.py -vvv

# Check that config was created
ls -la data/interim/dagster/dagster.yaml

# Start Dagster and verify auto-materialization is enabled
uv run dagster-ui
# Visit http://localhost:3005 and check Deployment -> Configuration
```

## Troubleshooting

### Issue: "No Dagster config found"

Solution: run the Dagster UI via the workspace script:

```bash
uv run dagster-ui
```

### Issue: "Auto-materialization not working"

Solution: check your `dagster.yaml`:

```bash
cat data/interim/dagster/dagster.yaml
```

Ensure it contains:

```yaml
auto_materialize:
  enabled: true
  minimum_interval_seconds: 60
```

### Issue: "Permission denied" when creating config

Solution: check directory permissions:

```bash
mkdir -p data/interim/dagster
chmod 755 data/interim/dagster
```

## Related Documentation

- [Dagster Comprehensive Guide](DAGSTER_GUIDE.md)
- [Hugging Face Modules](HF_MODULES.md)
- [Main README](../README.md)

