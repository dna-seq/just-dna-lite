# Immutable (Public Demo) Mode

just-dna-lite can run in **immutable mode** — a read-only configuration designed for public demo servers, workshops, and conference presentations. In this mode, file uploads are disabled and only pre-configured public genomes are available.

## Why immutable mode?

Processing personal genomic data on a shared server triggers GDPR, HIPAA, and other data protection regulations. Immutable mode sidesteps this by limiting the server to publicly available genomes that were voluntarily shared under permissive open-source licenses.

## Configuration

### Enable via CLI flag (recommended for quick starts)

```bash
uv run start --immutable
```

This starts the full stack (Reflex UI + Dagster) in immutable mode. The flag sets `JUST_DNA_IMMUTABLE_MODE=true` for the session. You can also use it with the standalone UI command:

```bash
uv run --package webui run --immutable
```

### Enable via environment variable

```bash
JUST_DNA_IMMUTABLE_MODE=true
```

Add this to your `.env` file or set it in your deployment environment. This is better for persistent deployments (Docker, systemd, etc.).

### Configure in modules.yaml

The `immutable_mode` section in `modules.yaml` controls all settings:

```yaml
immutable_mode:
  enabled: false                    # overridden by JUST_DNA_IMMUTABLE_MODE env var
  allow_zenodo_import: false        # allow users to import additional Zenodo genomes
  disclaimer: "This is a public demo..."  # shown in topbar tooltip and left panel
  default_samples:
    - zenodo_url: "https://zenodo.org/records/18370498"
      label: "Anton Kulaga"
      subject_id: "antonkulaga"
      sex: "Male"
      species: "Homo sapiens"
      reference_genome: "GRCh38"
      license: "CC-Zero"
    - zenodo_url: "https://zenodo.org/records/19487816"
      label: "Livia Zaharia"
      subject_id: "SIMHIFQTILQ"
      sex: "Female"
      species: "Homo sapiens"
      reference_genome: "GRCh38"
      license: "CC-BY-4.0"
```

### Deployment modes

| Mode | File Upload | Zenodo Import | Default Samples | Use Case |
|------|------------|---------------|-----------------|----------|
| Normal (default) | Yes | Yes | Suggested | Local/personal use |
| Immutable + `allow_zenodo_import: true` | No | Yes | Pre-loaded | Workshop/conference |
| Immutable + `allow_zenodo_import: false` | No | No | Pre-loaded only | Strict public demo |

## How it works

1. On first page load, `on_load()` detects immutable mode and calls `resolve_default_samples()`.
2. Each default sample is downloaded from Zenodo (cached in `~/.cache/just-dna-pipelines/zenodo/`) and placed in `data/input/users/public/`.
3. All users share the `public` user identity — no login, no per-user directories.
4. The upload form is replaced with a disclaimer box and "Install locally" link.
5. A "Public Demo" badge appears in the topbar next to the Medical Disclaimer.
6. The FAQ page (`/faq`) is added to the navigation with install instructions.

## Adding new public genomes

To add a new public genome to the demo:

1. Ensure the genome is uploaded to Zenodo with:
   - `access_right: "open"`
   - A permissive license (CC-Zero, CC-BY, CC-BY-SA, etc.)
   - A `.vcf` or `.vcf.gz` file
2. Add a new entry under `immutable_mode.default_samples` in `modules.yaml`
3. Restart the server — the new genome will be auto-downloaded on first access

## Zenodo import (normal mode)

Independent of immutable mode, all users in normal mode can import genomes from Zenodo URLs. The "Import from Zenodo" section appears in the left panel. Validation ensures:

- The record is open-access
- The license is permissive
- The record contains a VCF file

Zenodo metadata (DOI, license, creator) is stored in the Dagster asset materialization for full provenance tracking.

## FAQ page

The `/faq` page is available in **all modes** (normal and immutable). Its content is loaded from `docs/FAQ.md` and covers:

- Getting started (installation, file formats, where to get sequenced)
- Privacy and data security
- Understanding your results (PRS, heritability, GWAS limitations)
- AI Module Creator
- Modules and data sources
- Legal and ethical questions
- Technical details
