<div align="center">
  <img src="webui/assets/just_dna_seq.jpg" alt="just-dna-lite logo" width="200px">

# just-dna-lite
</div>

You have a DNA file (VCF) from a sequencing service. This tool takes that file, cross-references it against curated databases of genetic research, and tells you what your variants mean — from longevity markers to metabolic traits. Everything runs locally on your machine. Your genome never leaves your computer.

Under the hood it is a Python monorepo combining a [Dagster](https://dagster.io/) data pipeline with a [Reflex](https://reflex.dev/) web UI. You upload a VCF, pick annotation modules, and get an annotated report.

## Getting Started

### 1. Install uv

[uv](https://github.com/astral-sh/uv) is the only system-level dependency.

```bash
# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Clone and configure

```bash
git clone https://github.com/dna-seq/just-dna-lite.git
cd just-dna-lite
cp .env.template .env
```

Open `.env` in any text editor (the file starts with a dot, so it may be hidden in your file manager — opening it from the terminal is the easiest option):

```bash
# Linux / macOS
nano .env

# Windows
notepad .env
```

Find the line `#GEMINI_API_KEY=your_gemini_api_key_here`, remove the leading `#`, and replace `your_gemini_api_key_here` with your actual key.

> A free Gemini API key is available at <https://aistudio.google.com/apikey>. All other variables have sensible defaults and are optional.

### 3. Start

```bash
cd just-dna-lite
uv sync
uv run start
```

This launches the Web UI and the Dagster pipeline server together. Open the URL printed in the terminal.

### Individual components

Run components separately if needed:

- Dagster UI only: `uv run dagster-ui`
- Web UI only: `uv run ui`
- CLI: `uv run pipelines --help`

To register VCF files placed under `data/input/users/` as Dagster partitions:

```bash
uv run pipelines sync-vcf-partitions
```

## AI Module Creation

The **Module Manager** page lets you create and edit annotation modules through a chat interface powered by a multi-agent AI team (Google Gemini).

Instead of hand-curating a CSV of SNP annotations, you describe what you want — or attach a research paper — and the agents do the literature review, extract variants with weights and conclusions, cross-check against each other for consensus, and write a validated module spec ready for annotation.

### How it works

1. Open **Module Manager** in the web UI.
2. Optionally attach PDFs or CSVs (up to 5 files) with the paperclip button.
3. Type what module you want (e.g. *"Create a longevity module based on the attached paper"*).
4. The **Research Team** mode dispatches three independent researcher agents and a reviewer agent. Each researcher queries live biomedical databases (Ensembl, EuropePMC, Open Targets) and the reviewer checks consensus before anything is written.
5. The finished module lands in the **Editing Slot**. Review it, then hit **Register Module as source** to compile it to Parquet and make it available for annotation immediately.

You can also load any previously registered custom module back into the slot, edit it via chat, and re-register as a new version.

> **Single agent mode** (uncheck *Research team*) skips the multi-agent pipeline and uses one agent directly — faster for quick edits or simple modules.

## Features

### Pipeline Features
- VCF ingestion from `data/input/users/{user}/` and annotation outputs under `data/output/users/{user}/`.
- Two join engines: Polars (default) and DuckDB (streaming, low memory).
- Reference data assets cached under a per-user cache directory (see `JUST_DNA_PIPELINES_CACHE_DIR`).
- Resource tracking (time / CPU / peak memory) surfaced in Dagster materializations.

### Web UI Features
- **File Management**: Upload VCF files with drag-and-drop, view file library with status badges.
- **Sample Metadata**: 
  - Species selection using Latin scientific names (Homo sapiens, Mus musculus, Rattus norvegicus, etc.)
  - Reference genome selection (GRCh38, T2T-CHM13v2.0, GRCh37 for humans)
  - Editable fields: Subject ID, Study Name, Notes
  - **Custom Fields**: Add any metadata field with custom name (e.g., Batch ID, Sequencer, Library Prep)
- **Run-Centric Layout**: View outputs, run history, and start new analyses in a unified interface.
- **Real-time Monitoring**: Live status updates and log streaming from Dagster jobs.
- **Output Downloads**: Download annotated parquet files directly from the browser.

## Configuration

### Module Sources

Annotation module sources are configured in **`modules.yaml`** at the project root. Modules are auto-discovered from any fsspec-compatible URL (HuggingFace, GitHub, HTTP, S3, etc.). To add a new source, edit the `sources:` list in the YAML. Display metadata (titles, icons, colors) can be overridden under `module_metadata:`.

The loader also checks `just-dna-pipelines/src/just_dna_pipelines/modules.yaml` as a fallback, but the root-level file takes priority.

### Environment Variables

The stack is configured via environment variables (a `.env` in the repo root is fine):

```bash
export JUST_DNA_PIPELINES_CACHE_DIR="$HOME/.cache/just-dna-pipelines"
export JUST_DNA_PIPELINES_OUTPUT_DIR="$PWD/data/output/users"
export JUST_DNA_PIPELINES_INPUT_DIR="$PWD/data/input/users"

export JUST_DNA_PIPELINES_DOWNLOAD_WORKERS="8"
export JUST_DNA_PIPELINES_PARQUET_WORKERS="4"
export JUST_DNA_PIPELINES_WORKERS="4"
```

## Development

On first run, `uv run start` / `uv run dagster-ui` will create `data/interim/dagster/dagster.yaml` if it doesn't exist.

### Testing

```bash
# Run all tests
uv run pytest

# Run only library tests
uv run pytest just-dna-pipelines/tests/
```

## Documentation

- [Clean setup](docs/CLEAN_SETUP.md)
- [Dagster guide](docs/DAGSTER_GUIDE.md)
- [Performance & Engines](docs/DAGSTER_GUIDE.md#performance--engine-optimization)
- [Hugging Face Integration](docs/DAGSTER_GUIDE.md#hugging-face-integration--authentication)
- [Annotation Modules](docs/HF_MODULES.md)
- [Web UI Status](docs/WEBUI_STATUS.md) - Current implementation status and architecture
- [Design System](docs/DESIGN.md) - Fomantic UI patterns and component styling
- [Agent Guidelines](AGENTS.md)

## Connected Repositories

- [dna-seq/prepare-annotations](https://github.com/dna-seq/prepare-annotations): Upstream repository used to download, process, and upload the Ensembl and module annotations used by this project.

## License

MIT License - see [LICENSE](LICENSE) file for details.
