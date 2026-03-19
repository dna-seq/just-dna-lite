![just-dna-lite logo](images/just_dna_seq.jpg)

# just-dna-lite

**Your genome, your data, your call.**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)
[![GitHub](https://img.shields.io/badge/github-dna--seq%2Fjust--dna--lite-blue.svg)](https://github.com/dna-seq/just-dna-lite)

![just-dna-lite interface](images/just_dna_lite_annotations.jpg)

Upload your genome, pick what you want to know, get results in minutes. Other annotation tools can take hours. just-dna-lite runs locally on Polars and DuckDB, so your whole VCF gets normalized, annotated, and reported while you're still making coffee. Your data never leaves your machine.

The starting point here is that you have the right to look at your own genome without anyone filtering what you see. Consumer genomics tools like Nebula or Dante do show you a lot, but what they surface is ultimately a semi-arbitrary curatorial decision by their teams — interesting findings they picked, weighted toward things that are engaging or easy to explain. Clinical genomics is highly curated too, but for a different reason: it only shows findings where there's strong evidence and a clear path to action. This tool takes a different approach: you get access to everything — all modules, all 5,000+ PRS scores from the PGS Catalog, your complete variant table cross-referenced against Ensembl. What you do with that is your decision.

## What's inside

The tool ships with annotation modules for longevity, coronary artery disease, lipid metabolism, VO2 max, athletic performance, and pharmacogenomics (PharmGKB). These are a starting point. The real idea is that modules are easy to create and the list will grow fast.

**5,000+ Polygenic Risk Scores** from the [PGS Catalog](https://www.pgscatalog.org/) are available out of the box. Pick any score, click compute, and get your result with percentile ranking against 1000 Genomes reference populations (AFR, AMR, EAS, EUR, SAS). No command line, no scripting, just a few clicks. Under the hood, scoring runs via [just-prs](https://github.com/dna-seq/just-prs) using DuckDB (12.3× faster than PLINK2) or Polars (5.7× faster), with Pearson r = 0.9999 concordance against PLINK2 across 100 PGS IDs on a 4.66M-variant WGS. See the [full benchmark →](https://github.com/dna-seq/just-prs/blob/main/docs/benchmarks.md)

**AI Module Creator.** Got a research paper about a trait that interests you? Describe it in plain text, or upload the PDF directly. The tool has two modes:

- **Simple mode** — a single Gemini Pro agent queries biomedical databases (EuropePMC, Open Targets, BioRxiv), extracts variants with effect weights, validates the output, and writes the module. Takes roughly 2 minutes.
- **Research team mode** — a PI agent dispatches up to three independent Researcher agents (Gemini + GPT + Claude Sonnet, if you configure those keys) in parallel, each querying the literature separately. The PI synthesizes by majority vote — variants confirmed by ≥2 researchers are high confidence, weights where researchers disagree are taken as the median — then a Reviewer agent fact-checks the draft before the PI writes the final module. Takes roughly 7–8 minutes and produces deeper coverage.

Both modes output the same thing: a `module_spec.yaml` + `variants.csv` loaded into an editing slot for review, then one click to register it into the annotation pipeline. In documented test runs, all three scenarios produced ready-to-register modules with no manual edits required.

**Self-exploration.** Even without a specific module, you can browse your full variant table with sorting, filtering, and search. Cross-reference against [Ensembl](https://www.ensembl.org/) for clinical significance labels. Export everything as Parquet for your own analysis in Python, R, or any tool that reads Arrow.

## Quick start

You need a VCF file from whole genome (WGS) or whole exome (WES) sequencing aligned to GRCh38, and Python 3.13+. If you sequenced through [Nebula Genomics](https://nebula.org/), [Dante Labs](https://www.dantelabs.com/), [TruDiagnostic](https://trudiagnostic.com/), or a clinical lab, you should have a `.vcf` or `.vcf.gz` file. That's what you need. (23andMe and AncestryDNA produce microarray data, not VCFs. Microarray support is on the roadmap.)

First, install [uv](https://github.com/astral-sh/uv) (a fast Python package manager):

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

### macOS Apple Silicon: using Nix (optional)

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

### Individual components
To use the AI Module Creator, copy `.env.template` to `.env` and add your Gemini API key (free at [Google AI Studio](https://aistudio.google.com/apikey)). That's enough for both simple and team modes. Adding `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY` brings in GPT and Claude Sonnet as additional Researcher agents in team mode (more cross-model diversity). Everything else works without any API keys.

## How it works

You upload a VCF through the web interface. The pipeline normalizes it (quality filtering, chromosome prefix stripping, Parquet conversion), then matches your variants against whichever modules you've selected. Each module is a curated database of variants with effect weights from published research. Results come back as downloadable PDF/HTML reports. The whole process takes minutes, not hours.

For Polygenic Risk Scores, the tool pulls scoring files from the PGS Catalog, computes your score, and ranks it against five 1000 Genomes superpopulations (European, African, East Asian, South Asian, American).

All outputs are Parquet files. Open them in Polars, Pandas, DuckDB, R, or anything that speaks Arrow.

## What the numbers actually mean

Genomics has a gap between what sounds precise and what's actually known. Here's the short version before you start digging.

When a trait is described as "70% heritable," most people read that as "70% determined by genes." It doesn't mean that. Heritability is a population statistic — it measures how much of the variation *between people in a specific study* is associated with genetic differences. It changes depending on the environment. Height is around 80% heritable in well-nourished populations; that number drops significantly in populations with childhood malnutrition. The genes didn't change. The environment did. So heritability tells you something real, but not what most people think it tells you.

The tool doesn't display heritability estimates alongside most findings, which means you'll sometimes see a variant flagged as associated with something scary (or exciting) without knowing how heritable that trait actually is. For anything that catches your eye, it's worth looking that up separately — a finding tied to a trait with low heritability means the genetic component explains very little of who gets it. The rest is environment, chance, or factors we don't understand yet. On top of that, carrying a risk variant doesn't tell you much if the trait hasn't manifested. A lot of variants have low penetrance, meaning many people who carry them never develop the condition at all. The genomic signal and what actually happens to a person can be pretty different things.

A polygenic risk score is a weighted sum. You take a list of SNPs from GWAS studies, multiply each by its effect weight, add them up, and get a number that tells you where you sit in a reference population's distribution. That's it. It's not a probability of disease; it's a rank. The model is linear and the underlying biology isn't. And most PGS Catalog scores were built from predominantly European cohorts, so if your ancestry is different, the score loses accuracy — sometimes a little, sometimes a lot.

Most of the variants in GWAS-based annotation are statistical associations, not causal mechanisms. A lot of GWAS hits are tagging SNPs — correlated with a causal variant nearby, not the causal variant itself. Effect sizes also shrink consistently in replication studies; estimates from the original GWAS tend to be inflated.

A small set of genomic findings do have solid clinical evidence: pathogenic BRCA1/2 variants, monogenic conditions like Huntington's or familial hypercholesterolemia, pharmacogenomic variants like CYP2C19 or HLA-B*57:01. For these, someone ran prospective studies and proved that knowing the result changes outcomes. That's the clinical-grade bar. Most complex-trait associations haven't cleared it. The modules and PRS scores here are science-grade: findings from real published research, but probabilistic and population-level.

If you land in the 90th percentile for a disease PRS, don't immediately spiral. Most people in that percentile won't develop the condition. For nearly every common chronic disease, lifestyle factors — smoking, activity, diet, sleep — have larger effect sizes than any common genetic variant. An interesting longevity SNP isn't permission to stop sleeping. A high cardiovascular PRS isn't a sentence. Cross-reference things you're worried about in the literature, or ask a genetic counselor or an AI with access to recent papers. Take your time.

[Full explainer with more detail on heritability, GWAS, and what clinical-grade actually means →](docs/SCIENCE_LITERACY.md)

## Running individual components

```bash
uv run start             # Full stack (Web UI + pipeline)
uv run ui                # Web UI only
uv run dagster-ui        # Dagster pipeline UI only
uv run pipelines --help  # CLI tools
```

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

## License

AGPL v3. See [LICENSE](LICENSE).

## Contributors

[Anton Kulaga](https://github.com/antonkulaga) (IBAR) and Nikolay Usanov (HEALES), with contributions from the [Just-DNA-Seq](https://github.com/dna-seq) community.
