![just-dna-lite logo](images/just_dna_seq.jpg)

# just-dna-lite

**Your genome, your data, your call.**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![GitHub](https://img.shields.io/badge/github-dna--seq%2Fjust--dna--lite-blue.svg)](https://github.com/dna-seq/just-dna-lite)

![just-dna-lite interface](images/just_dna_lite_annotations.jpg)

<sub><i>Research Use Only (RUO): just-dna-lite is a bioinformatics research tool for academic studies, citizen science, and educational self-exploration. It is not a medical device, not intended for clinical diagnostic use, and does not provide medical advice. The software and its modules (including AI-generated content) are provided "as is" without warranties of any kind. Our philosophy is to display everything — including PRS scores and community-generated AI modules that may attempt to predict disease probabilities — but you must never use this tool to make medical, diagnostic, or health-related decisions. Always consult a qualified healthcare professional or genetic counselor for any health concerns or clinical interpretation of genomic data.</i></sub>

**Runs on your laptop.** Upload your genome file, pick what you want to know, get results in minutes. Installs in four commands, runs entirely on your machine, nothing leaves your computer.

> **Just want to try it?** Jump to [Quick start](#quick-start) — you'll be up and running in under five minutes.

You have the right to look at your own genome without anyone filtering what you see. Consumer genomics tools surface findings their teams picked; clinical genomics only shows what has strong evidence and a clear path to action. This tool takes a different approach: you get access to everything — all modules, all 5,000+ PRS scores from the [PGS Catalog](https://www.pgscatalog.org/), your complete variant table cross-referenced against [Ensembl](https://www.ensembl.org/), community-built annotation modules, and an AI assistant that can turn a research paper into a new genetic module in minutes. What you do with all of that is your decision.

## Genomic Annotations

### Built-in Modules

The tool ships with annotation modules for longevity, coronary artery disease, lipid metabolism, VO2 max, athletic performance. These modules were created with the expert curation of geneticist Olga Borysova and serve as a reliable starting point. The real idea, however, is that modules are easy to create and the list will grow fast.

### Polygenic Risk Scores (PRS)

**5,000+ Polygenic Risk Scores** from the [PGS Catalog](https://www.pgscatalog.org/) are available out of the box. Pick any score, click compute, and get your result with percentile ranking against 1000 Genomes reference populations (AFR, AMR, EAS, EUR, SAS). No command line, no scripting, just a few clicks. Under the hood, scoring runs via [just-prs](https://github.com/dna-seq/just-prs) using DuckDB (12.3× faster than PLINK2) or Polars (5.7× faster), with Pearson r = 0.9999 concordance against PLINK2 across 100 PGS IDs on a 4.66M-variant WGS. See the [full benchmark →](https://github.com/dna-seq/just-prs/blob/main/docs/benchmarks.md)

### AI Module Creator

Annotation modules in just-dna-lite are curated SNP filter sets containing variants, per-genotype weights, states, and literature evidence. Building these by hand is labour-intensive. To solve this, just-dna-lite includes an **AI Module Creator**—an agentic pipeline that turns arbitrary input (a research article PDF, CSV dump, or free-text description) into a valid, deployable annotation module.

Got a research paper about a trait that interests you? Just upload the PDF and ask the AI to build a module. Powered by the Agno agentic framework, the tool supports Gemini, GPT, and Claude. It operates in two modes:

- **Simple mode (Solo Agent)** — a single agent handles everything. It queries biomedical databases (EuropePMC, Open Targets, BioRxiv) using the BioContext MCP, extracts variants with per-genotype weights, validates the spec, and writes the module. If validation fails, the agent self-corrects and retries.
  - *Best for:* Single well-defined papers, quick iteration, simple trait panels.
  - *Typical runtime:* ~2 minutes for a single paper.

- **Research team mode (Multi-Agent Swarm)** — a coordinated team of agents. A Principal Investigator (PI) agent dispatches up to three Researcher agents (e.g., Gemini, GPT, and Claude Sonnet) in parallel, each independently querying the literature. This model diversity reduces systematic blind spots. The PI synthesises the findings by consensus (variants need ≥2 researchers to confirm; weight disagreements use the median). A Reviewer agent then fact-checks the data via Google Search before the PI writes the final module.
  - *Best for:* Complex topics spanning multiple papers, large variant sets, cross-model validation.
  - *Typical runtime:* ~7–8 minutes.

Both modes output a deterministic DSL specification (`module_spec.yaml` + `variants.csv` + `studies.csv`), which the compiler validates and turns into Parquet tables. The drafted module is loaded into an editing slot for your review. You can manually edit the files, iterate by sending follow-up messages to the AI in the same chat, and then register the module with one click so it becomes instantly available in your local app.

[Full walkthrough with real examples and timing logs →](docs/AI_MODULE_WALKTHROUGH.md)

### Self-exploration

Even without a specific module, you can browse your full variant table with sorting, filtering, and search. Cross-reference against [Ensembl](https://www.ensembl.org/) for clinical significance labels. Export everything as Parquet for your own analysis in Python, R, or any tool that reads Arrow.

### VCF export

Annotation results are stored as Parquet for speed and columnar tooling, but you can also get **standard VCF** files. The pipeline materializes a `user_vcf_exports` asset: one VCF per selected HF module (annotations in INFO), an optional Ensembl-annotated VCF when you run Ensembl, and a **combined** VCF that merges module (and Ensembl) fields into INFO. Exports land under your sample’s `vcf_exports/` folder.

In the web app, open **Outputs** → **Data Files** and use **Export VCF** to run the export job again (for example after new modules or a stale run). While the job runs, **View in Dagster** opens the live run in the pipeline UI—exports that join large Ensembl tables can take several minutes.

## Creating a Module with the AI Team

Got a research paper about a trait that interests you? Upload the PDF, describe what you want, and the AI team does the rest — querying EuropePMC, Open Targets, and BioRxiv, extracting variants with per-genotype weights, validating the spec, and writing all module files in one uninterrupted run. No bioinformatics knowledge needed.

<div>
  <img src="images/just_dna_lite_AI_module_builder_step_I.jpg" alt="Step 1: open Module Manager, attach your paper, describe the module, click Send" width="960">
  <img src="images/just_dna_lite_AI_module_builder_step_II.jpg" alt="Step 2: module auto-loaded with all files generated; register as annotation source in one click" width="960">
</div>

The module lands in the editing slot automatically with its name, description, and all generated files: `module_spec.yaml` and `variants.csv` (the core spec), `studies.csv` (literature references), `MODULE.md` (human-readable summary), an AI-generated `logo.png`, and a timestamped log for each creation or edit run. Review the files, then click **Register Module as source** — the module appears immediately in the Annotation tab's module list. Re-run the annotation job on your sample and the report will include the new module automatically. You can iterate by sending follow-up messages in the same chat — the team reads the existing module and extends it to a new version, adding a fresh log entry for each revision.

Simple mode runs in about 2 minutes. Research team mode takes 7–8 minutes: a PI (Principal Investigator) agent dispatches Researcher agents in parallel, then a Reviewer fact-checks via Google Search before the PI writes the final module. With only a Gemini key you get one Researcher; adding an OpenAI key brings in a GPT researcher, and adding an Anthropic key adds Claude Sonnet — up to three researchers running simultaneously, each independently querying the literature and reporting findings back to the PI. Having multiple models report independently and requiring cross-model agreement (the PI only retains variants confirmed by at least two researchers, using the median weight on disagreements) greatly reduces hallucination and increases the reliability of the resulting module. Both modes require a free Gemini API key.

## Quick start

Everything runs locally on your computer. You can install it on a laptop, a desktop, or a lab workstation — no cloud account, no institutional server, no IT department needed.

### What you need

You need a `.vcf` or `.vcf.gz` file from whole genome (WGS) or whole exome (WES) sequencing. If you had your genome sequenced through a company like DNA Complete (Nebula), Dante Labs, or Sequencing.com, log into your account and look for a **"Download Raw Data"** or **"Download VCF"** option. The file you want ends in `.vcf` or `.vcf.gz`. You may also see `.bam` or `.fastq` files — you don't need those, just the VCF. Most providers deliver GRCh38 by default. If unsure, check with your provider.

> **23andMe, AncestryDNA, MyHeritage?** These services use microarray chips that read a few hundred thousand pre-selected positions — a tiny fraction of your genome. just-dna-lite needs a file from whole genome or whole exome sequencing, which covers millions of positions. If your data comes from a chip-based service, it won't work here yet (microarray support is planned). Not sure what you have? Check with your provider.

**Where to get your genome sequenced?**
If you want to sequence your own genome, there are several commercial providers. As of early 2026, popular and accessible options include [DNA Complete](https://dnacomplete.com/) (formerly Nebula Genomics), [Dante Labs](https://www.dantelabs.com/), and [Sequencing.com](https://sequencing.com/). Make sure the provider allows you to download your raw `.vcf` or `.vcf.gz` file. *(Disclaimer: We provide these links only as examples and are in no way affiliated with any of these companies or services).*

If you live in Romania, you should follow the **[ROGEN (Romanian Genomics) project](https://rogen.umfcd.ro/)**. It is a major national initiative sequencing 5,000 individuals to create a genomic map of the population, and you might be able to get recruited to have your genome sequenced for free.

**Don't have your genome sequenced yet?**
You can use any public genome to try out the tool. For example, some of our authors have open-sourced their genomes — you can download [Anton Kulaga's genome here](https://zenodo.org/records/18370498) and see what you discover! You can also find other public genomes on platforms like [Open Humans](https://www.openhumans.org/).

### Install from source (Python)

If you're comfortable with a terminal, this is the fastest way to get started. Open a terminal (Terminal on macOS, PowerShell on Windows, any terminal on Linux) and run the commands below. You'll need [git](https://git-scm.com/downloads) installed.

First, install [uv](https://github.com/astral-sh/uv) — a tool that manages Python and all dependencies for you automatically:

```bash
# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then clone and run:

```bash
git clone https://github.com/dna-seq/just-dna-lite.git
cd just-dna-lite
uv sync
uv run start
```

Open the URL printed in the terminal (usually `http://localhost:3000`). Upload your VCF and start exploring.

### Run with Podman or Docker (no Python required)

Don't want to install Python? [Podman](https://podman.io/) (or [Docker](https://www.docker.com/products/docker-desktop/)) packages the entire app so it runs the same on any computer. This still runs on your machine — the container is just a convenient way to get everything pre-installed.

We recommend **Podman** — it runs without root privileges by default, which is a better fit for a tool that handles personal genomic data. Docker works identically; just swap `podman` for `docker` in any command below.

**Install Podman** (one-time):

```bash
# Linux (Debian/Ubuntu)
sudo apt install podman

# macOS (via Homebrew — install Homebrew first from https://brew.sh if needed)
brew install podman && podman machine init && podman machine start

# Windows: install Podman Desktop from https://podman-desktop.io
# Or install Docker Desktop from https://www.docker.com/products/docker-desktop/
```

**Step 1.** Create a folder and put your VCF files in it:

```bash
mkdir -p my_genomes
# Copy or move your .vcf / .vcf.gz file into my_genomes/
```

**Step 2.** Run the app:

```bash
podman run -it --rm \
  -p 3000:3000 -p 3005:3005 -p 8000:8000 \
  -v ./my_genomes:/app/data/input/users/default \
  -v ./my_results:/app/data/output/users/default \
  -v just-dna-cache:/app/data/cache \
  ghcr.io/dna-seq/just-dna-lite:latest
```

> **Docker users:** replace `podman` with `docker` — everything else stays the same.

**Step 3.** Open `http://localhost:3000` in your browser. Upload your VCF and start exploring.

**Step 4.** When annotation finishes, find your reports and results in the `my_results/` folder (created automatically next to `my_genomes/`). The Ensembl cache (~14 GB, downloaded on first use) and PRS scores are persisted so they survive restarts.

#### Advanced container usage

<details>
<summary>Compose, building from source, ports, and environment variables</summary>

**Using Podman Compose or Docker Compose:**

```bash
git clone https://github.com/dna-seq/just-dna-lite.git
cd just-dna-lite

# Podman (recommended)
podman-compose up --build

# Docker
docker compose up --build
```

The compose file automatically creates `my_genomes/` and `my_results/` folders in your project directory.

**Building from source:**

```bash
# Podman
podman build -t just-dna-lite .

# Docker
docker build -t just-dna-lite .
```

**Ports:**

| Port | Service |
|------|---------|
| 3000 | Web UI (main interface) |
| 3005 | Dagster pipeline dashboard |
| 8000 | Backend API (used internally) |

**Environment variables** (pass via `-e` or `--env-file .env`):

| Variable | Purpose |
|----------|---------|
| `HF_TOKEN` | HuggingFace token (for private datasets) |
| `GEMINI_API_KEY` | Enables AI Module Creator |
| `API_URL` | Override backend URL (for remote deployments) |
| `JUST_DNA_PIPELINES_LOGIN` | `none` (default in container), `false` (email login), or `user:pass` |

</details>

To use the AI Module Creator, copy `.env.template` to `.env` and add your Gemini API key (free at [Google AI Studio](https://aistudio.google.com/apikey) — see [this short video](https://www.youtube.com/watch?v=SbT6WbISBow) if you haven't done this before). That's enough for both simple and team modes. Adding `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY` brings in GPT and Claude Sonnet as additional Researcher agents in team mode (more cross-model diversity). Everything else works without any API keys.

<details>
<summary><strong>macOS Apple Silicon: using Nix (optional)</strong></summary>

If you're on an Apple Silicon Mac (M1/M2/M3/M4) and run into architecture issues (e.g. Polars CPU warnings, wrong native bindings), the included [Nix flake](https://nix.dev/concepts/flakes) provides Python, Node.js, and uv at the correct architecture automatically.

```bash
# Install Nix (one-time, ~2 minutes)
sh <(curl -L https://nixos.org/nix/install)
# Restart your terminal, then enable flakes:
mkdir -p ~/.config/nix
echo "experimental-features = nix-command flakes" >> ~/.config/nix/nix.conf

# Enter the dev environment and start as usual
cd just-dna-lite
nix develop
uv sync
uv run start
```

Run `nix develop` each time you open a new terminal to work on this project, or use [direnv](https://direnv.net/) to activate it automatically (`echo "use flake" > .envrc && direnv allow`).

</details>

## How it works

You upload a VCF through the web interface. The pipeline normalizes it (quality filtering, chromosome prefix stripping, Parquet conversion), then matches your variants against whichever modules you've selected. Each module is a curated database of variants with effect weights from published research. Results come back as downloadable PDF/HTML reports. The whole process takes minutes, not hours.

For Polygenic Risk Scores, the tool pulls scoring files from the PGS Catalog, computes your score, and ranks it against five 1000 Genomes superpopulations (European, African, East Asian, South Asian, American).

Primary outputs are **Parquet** files—open them in Polars, Pandas, DuckDB, R, or anything that speaks Arrow. **VCF export** (see above) is available when you need a classic variant file with annotations in INFO.

## What the numbers actually mean

Genomics has a gap between what sounds precise and what's actually known. Here's the short version before you start digging.

> **⚠️ IMPORTANT LIABILITY NOTICE:** just-dna-lite is a bioinformatics research tool for personal self-exploration and research purposes only. It is **not** a medical device, diagnostic tool, or a substitute for professional medical advice. By using this tool, you acknowledge that the developers, contributors, and affiliated institutions accept **zero liability** for any physical, psychological, or financial harm resulting from the interpretation of these results. Always consult a healthcare provider or certified genetic counselor for clinical interpretation.

### What to do when you see something scary

Imagine you run your genome through a module and see a red flag—a variant labeled "pathogenic" or a PRS score in the 99th percentile for a serious disease. 

**Do not rush to panic.** Studies of healthy populations (like the 1000 Genomes Project) show that the average, completely healthy person walks around with *dozens to hundreds* of variants historically flagged as "pathogenic" in research databases. Why aren't they sick? Because many of these database entries are false alarms, or the variants have very low penetrance (meaning they only cause disease in a tiny fraction of the people who carry them). Furthermore, for nearly every common chronic disease, lifestyle factors — smoking, activity, diet, sleep — have larger effect sizes than any common genetic variant. If the disease hasn't manifested, a standalone variant is often not a concern.

**Understand our tool's limits.** We built just-dna-lite for rapid exploration, open access, and speed of development. We do *not* validate our modules with the rigorous, painstaking manual curation of a clinical laboratory. Our **AI-generated modules** are even less reliable—they are literal first drafts written by an AI agent reading a PDF, and they *will* contain mistakes.

**The clinical reality check.** Raw VCFs have false positives, and automated annotations have high error rates. In a true clinical setting, a genomic finding is *never* trusted from a single exploratory sequencing run. If a potential risk variant aligns with your family history and you are genuinely concerned, you must get it orthogonally validated. This means going to a doctor and getting a targeted, clinical-grade test (like quantitative PCR or Sanger sequencing) from a certified lab to prove the variant is actually there, followed by a genetic counselor's interpretation. Never make medical decisions based on a hit in this app.

### Heritability and GWAS limitations

When a trait is described as "70% heritable," most people read that as "70% determined by genes." It doesn't mean that. Heritability is a population statistic — it measures how much of the variation *between people in a specific study* is associated with genetic differences. It changes depending on the environment. Height is around 80% heritable in well-nourished populations; that number drops significantly in populations with childhood malnutrition. The genes didn't change. The environment did. So heritability tells you something real, but not what most people think it tells you.

A polygenic risk score is a weighted sum. You take a list of SNPs from GWAS studies, multiply each by its effect weight, add them up, and get a number that tells you where you sit in a reference population's distribution. That's it. It's not a probability of disease; it's a rank. The model is linear and the underlying biology isn't. And most PGS Catalog scores were built from predominantly European cohorts, so if your ancestry is different, the score loses accuracy — sometimes a little, sometimes a lot.

Most of the variants in GWAS-based annotation are statistical associations, not causal mechanisms. A lot of GWAS hits are tagging SNPs — correlated with a causal variant nearby, not the causal variant itself. Effect sizes also shrink consistently in replication studies; estimates from the original GWAS tend to be inflated.

[Full explainer with more detail on heritability, GWAS, and what clinical-grade actually means →](docs/SCIENCE_LITERACY.md)

## Running individual components

```bash
uv run start             # Full stack (Web UI + pipeline)
uv run ui                # Web UI only
uv run dagster-ui        # Dagster pipeline UI only
uv run pipelines --help  # CLI tools
```

### Optional: pre-download Ensembl annotations

Cross-referencing your variants against [Ensembl](https://www.ensembl.org/) (for clinical significance labels and full variant metadata) requires the Ensembl variation database, which is roughly **14 GB**. This data is downloaded on demand the first time you run an Ensembl annotation job, but if you'd rather fetch it upfront while you have time and a stable connection, run:

```bash
uv run pipelines ensembl-setup
```

This pre-caches the data to `~/.cache/just-dna-pipelines/ensembl_variations/` so the annotation job starts immediately instead of waiting for the download.

## For bioinformaticians

The project is a [uv workspace](https://docs.astral.sh/uv/concepts/workspaces/) with two packages: `just-dna-pipelines` (Dagster assets, VCF processing, annotation logic, CLI) and `webui` (Reflex web UI, pure Python).

The pipeline runs on [Dagster](https://dagster.io/) with Software-Defined Assets, giving you automatic data lineage and resource tracking (CPU, RAM, duration). Data processing uses [Polars](https://pola.rs/) by default, with [DuckDB](https://duckdb.org/) for streaming joins when memory is tight. VCF reading goes through [polars-bio](https://github.com/polars-contrib/polars-bio). PRS computation comes from [just-prs](https://pypi.org/project/just-prs/) with reusable [prs-ui](https://pypi.org/project/prs-ui/) Reflex components.

Annotation modules are auto-discovered from any [fsspec](https://filesystem-spec.readthedocs.io/)-compatible URL (HuggingFace, GitHub, S3, HTTP). Sources and quality filters live in `modules.yaml` at the project root.

### Writing a module by hand

A module is a directory with two files — no Python required:

```
my_module/
├── module_spec.yaml    # metadata, version, genome build
└── variants.csv        # per-variant annotation table
```

Minimal `module_spec.yaml`:

```yaml
schema_version: "1.0"
module:
  name: my_module
  version: 1
  title: "My Module"
  description: "One-line description."
  report_title: "My Module Report Section"
  icon: dna
  color: "#21ba45"
defaults:
  curator: human
  method: literature-review
  priority: medium
genome_build: GRCh38
```

`variants.csv` required columns: `rsid`, `genotype` (slash-separated, alphabetically sorted e.g. `A/G`), `weight` (negative = risk, positive = protective, range −1.2 to +1.2), `state` (`risk`/`protective`/`neutral`), `conclusion` (≤50 words), `gene` (HGNC symbol). Extra columns are preserved in annotation output.

To add the module: upload it in the UI editing slot and click **Register**, or add its path/URL as a source in `modules.yaml`. Modules hosted on HuggingFace, GitHub, S3, or any HTTP server are supported.

For architecture, pipeline details, and configuration, see the [docs](#documentation).

## Just-DNA-Seq vs Just-DNA-Lite

just-dna-lite is a ground-up rewrite of [Just-DNA-Seq](https://just-dna.life/). The original used OakVar and took hours per VCF. The rewrite drops OakVar in favor of Dagster + Polars/DuckDB and finishes in seconds. The web UI moved from OakVar's viewer to [Reflex](https://reflex.dev/) (pure Python, no JavaScript). Data lineage is automatic. And adding new modules went from "write Python code" to "upload a paper and let the AI handle it."

## Testing

```bash
uv run pytest                           # All tests
uv run pytest just-dna-pipelines/tests/ # Pipeline tests only
```

## Documentation

- [Understanding Your Genome: Science vs Clinical Grade](docs/SCIENCE_LITERACY.md) — what heritability means, why PRS are linear models, when to act on a finding (and when not to)
- [Architecture Overview](docs/ARCHITECTURE.md)
- [AI Module Creation](docs/AI_MODULE_CREATION.md) — DSL spec, compiler, registry API, Agno agent (solo + team), module discovery
- [AI Module Walkthrough](docs/AI_MODULE_WALKTHROUGH.md) — three real end-to-end examples with timing logs, agent outputs, and generated module files
- [Dagster Pipeline Guide](docs/DAGSTER_GUIDE.md)
- [Annotation Modules](docs/HF_MODULES.md)
- [Configuration & Setup](docs/CLEAN_SETUP.md)
- [Design System & UI Architecture](docs/DESIGN.md)

## Roadmap

GRCh38 VCF files (WGS and WES) are fully supported, along with PRS and AI-assisted module creation. GRCh37/hg19 support, T2T reference genomes, microarray data (23andMe, AncestryDNA), and multi-species support are planned but not yet available.

## Related projects

- [just-prs](https://github.com/antonkulaga/just-prs) — Polygenic Risk Score library and UI ([PyPI](https://pypi.org/project/just-prs/))
- [prepare-annotations](https://github.com/dna-seq/prepare-annotations) — upstream pipeline for Ensembl and module annotation data
- [Just-DNA-Seq](https://just-dna.life/) — the original project

## Funding and Support

This project is open source and intended for users worldwide. One of its core developers, [Anton Kulaga](https://github.com/antonkulaga), is funded through the **[ROGEN (Romanian Genomic) consortium](https://rogen.umfcd.ro/)**, and some parts of this roadmap are being developed with future ROGEN research use in mind.

ROGEN recruitment and data collection are still ongoing, so the points below should be read as research targets and planned directions rather than completed outcomes. The broader goal is to contribute to the understanding of the genetic landscape of European populations while building methods that remain useful for users and researchers in Romania and beyond. Current priorities of the consortium include:

1. **Risk-stratified prevention:** Romanian-calibrated PRSes and aging clocks as future tools for more cost-effective prevention programs.
2. **Reducing health inequities:** Better imputation panels and ancestry-aware models for under-represented populations.
3. **Gene-environment insights:** Analyses of interactions between genetics and factors such as diet, smoking, air pollution, occupational exposures, and pathogen burdens.
4. **Reproducible public-health research:** Privacy-preserving analyses aligned with international research and regulatory norms for priorities such as cardiovascular risk, diabetes, and dementia.
5. **Clinical translation:** Locally calibrated models that could eventually help inform clinical guidelines once properly validated.

## License and Disclaimer

AGPL v3. See [LICENSE](LICENSE).

**LIMITATION OF LIABILITY:** The software is provided "AS IS", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and non-infringement. In no event shall the authors, contributors, or copyright holders be liable for any claim, damages, or other liability, whether in an action of contract, tort, or otherwise, arising from, out of, or in connection with the software or the use or other dealings in the software.

## Contributors

[Anton Kulaga](https://github.com/antonkulaga) (IBAR) and Nikolay Usanov (HEALES), with contributions from the [Just-DNA-Seq](https://github.com/dna-seq) community.
