# Clean Setup Guide

This document explains how the project handles automatic configuration on first setup.

## What Happens on First Run

When you clone the repository and run the application for the first time, the system automatically:

1. **Creates directory structure**: `data/interim/dagster/`
2. **Generates configuration**: `data/interim/dagster/dagster.yaml`
3. **Enables auto-materialization**: Dagster assets with `AutoMaterializePolicy` will automatically update

**No manual configuration is required!**

## Setup Steps

### 1. Clone and Install

```bash
git clone git@github.com:dna-seq/just-dna-lite.git
cd just-dna-lite
uv sync
```

### 2. Start the Application

Choose one of these commands:

```bash
# Start full stack (Web UI + Dagster pipelines)
uv run start

# Or start only Dagster UI
uv run dagster

# Or start only Web UI
uv run ui
```

On first run, you'll see:

```
✅ Created Dagster config at /path/to/data/interim/dagster/dagster.yaml
🚀 Starting Dagster Dev...
```

That's it! The configuration is automatically created with optimal defaults.

## Configuration Details

### Default dagster.yaml

The automatically generated configuration includes:

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

1. **Reference the template**: See `dagster.yaml.template` in the repo root for all available options
2. **Modify after creation**: Edit `data/interim/dagster/dagster.yaml` directly
3. **Your changes are preserved**: The initialization code never overwrites existing config

### Git Ignore Strategy

- `data/interim/dagster/dagster.yaml` - **Gitignored** (instance-specific)
- `dagster.yaml.template` - **Tracked** (documentation reference)

This ensures:
- Each developer can have their own Dagster configuration
- New users get automatic setup with sane defaults
- Configuration template is documented and version-controlled

## How It Works

### Initialization Function

The core initialization is in `src/just_dna_lite/cli.py`:

```python
def _ensure_dagster_config(dagster_home: Path) -> None:
    """
    Ensure dagster.yaml exists with proper configuration.
    
    Creates the config file if missing, enabling auto-materialization
    and other important features.
    """
    config_file = dagster_home / "dagster.yaml"
    
    if config_file.exists():
        return  # Never overwrite existing config
    
    dagster_home.mkdir(parents=True, exist_ok=True)
    
    config_content = """# Dagster instance configuration
# Storage defaults to DAGSTER_HOME

# Enable auto-materialization for assets with AutoMaterializePolicy
auto_materialize:
  enabled: true
  minimum_interval_seconds: 60
"""
    
    config_file.write_text(config_content, encoding="utf-8")
```

### When It Runs

The initialization is called by:

1. **CLI commands** (`uv run start`, `uv run dagster`, etc.)
   - In `cli.py`: All commands that use Dagster call `_ensure_dagster_config()`
   
2. **Web UI** (when it needs Dagster access)
   - In `webui/src/webui/state.py`: `get_dagster_instance()` calls initialization

3. **Any Python code** that uses `DagsterInstance.get()`
   - As long as they import and call the initialization function first

## Environment Variables

You can override the default location:

```bash
# Custom Dagster home
export DAGSTER_HOME=/custom/path/to/dagster

# Other environment variables (see .env.template)
export JUST_DNA_PIPELINES_CACHE_DIR=~/.cache/just-dna-pipelines
export JUST_DNA_PIPELINES_OUTPUT_DIR=~/genomics/output
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
uv run dagster
# Visit http://localhost:3005 and check Deployment → Configuration
```

## Troubleshooting

### Issue: "No Dagster config found"

**Solution**: Run any CLI command that initializes Dagster:
```bash
uv run dagster
```

### Issue: "Auto-materialization not working"

**Solution**: Check your `dagster.yaml`:
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

**Solution**: Check directory permissions:
```bash
mkdir -p data/interim/dagster
chmod 755 data/interim/dagster
```

## For Contributors

If you're modifying the initialization logic:

1. **Update the template**: Modify `dagster.yaml.template`
2. **Update the code**: Modify `_ensure_dagster_config()` in `cli.py`
3. **Update tests**: Run and update tests in `test_clean_setup.py` and `test_dagster_config.py`
4. **Update docs**: Update this guide and `docs/DAGSTER_MULTI_USER.md`

## Related Documentation

- [Dagster Multi-User Architecture](DAGSTER_MULTI_USER.md)
- [Dagster Assets](DAGSTER_ASSETS.md)
- [Main README](../README.md)
- [Environment Template](../.env.template)
- [Configuration Template](../dagster.yaml.template)

