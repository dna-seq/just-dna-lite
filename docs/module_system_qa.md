# Module System — Q&A Document

Answers derived from code analysis of `just-dna-lite` + `just-dna-pipelines`.
Items that require author input or a real walkthrough example are marked **[NEEDS INPUT]**.

---

## N1 — Simple AI Module Creation Mode

### Q: What does the user provide as input?

A free-text description typed into the chat textarea on the Module Manager page.
The user can optionally attach up to 5 files (PDF, CSV, Markdown, or plain text) via the paperclip button.
Example inputs:
- `"Create a module for cardiovascular disease risk based on established GWAS hits"`
- `"Build a longevity module from the attached paper"` (with PDF attached)
- `"Update the module in the editing slot: add rs429358 APOE variants"`

No structured form is required — free natural language works.

### Q: What does the AI output?

A set of files written to disk under `data/modules/generated/<module_name>/`:

| File | Content |
|------|---------|
| `module_spec.yaml` | Module metadata: name, version, title, description, icon, color, genome build |
| `variants.csv` | Per-variant annotation table: rsid, genotype, weight, state, conclusion, gene, phenotype, category |
| `studies.csv` | Evidence table: rsid, PMID, population, p-value, conclusion, study design |
| `MODULE.md` | Human-readable documentation / design notes |
| `logo.png` | AI-generated thumbnail image (via Imagen 3 / `gemini-2.0-flash`) |

After writing, the agent calls `validate_spec()` automatically.
The web UI loads the result into the **Editing Slot** for review before registration.

### Q: What LLM is called, and how?

**Primary model:** Google Gemini Pro (default `gemini-3-pro-preview`, overridable via `GEMINI_MODEL` env var).

**Framework:** [Agno](https://github.com/agno-ai/agno) — Python multi-agent orchestration library.

**Execution path:**
1. `AgentState.send_agent_message()` (Reflex state handler) is called on form submit.
2. With team mode OFF: calls `run_agent_async()` from `just_dna_pipelines.agents.module_creator`.
3. `run_agent_async()` creates a solo `Agent` via `create_module_agent_solo()`.
4. The agent streams responses via `agent.arun(message, stream=True, stream_events=True)`.
5. Status and tool-call events are forwarded to the UI via callbacks.

**System prompt:** loaded from `just_dna_pipelines/agents/prompts/module_creator.yaml`.
It instructs the agent to: research variants, write spec files, validate, register, and document.

**Tool calls available to the solo agent:**
- `write_spec_files` — write module_spec.yaml + CSVs to disk
- `validate_spec` — dry-run validation (returns stats or errors)
- `register_module` — compile CSVs to Parquet + add to modules.yaml
- `write_module_md` — write MODULE.md documentation
- `generate_logo` — generate logo.png via Imagen 3
- BioContext MCP tools (variant lookup, EuropePMC, Ensembl, Open Targets)

**Max iterations:** 10 (Agno agent loop; each iteration = one LLM round trip).

### Q: What happens if the generated module has errors?

1. The agent calls `validate_spec()` as part of its tool sequence.
2. If validation fails, the error text is returned as the tool result and fed back into the agent's context for the next iteration.
3. The agent attempts to self-correct by rewriting the offending files and re-validating.
4. The web UI shows each tool call in the events panel (expandable, labeled with ✓ / spinner).
5. If the agent exhausts its iterations without resolving the error, the partial output remains in the editing slot and the user can continue chatting to request fixes.
6. There is **no automatic retry outside the agent loop** — the user must send a follow-up message.

### Short example prompt and resulting module code

**Example prompt:**
```
Create a module for MTHFR methylation variants. Include rs1801133 (C677T) and rs1801131 (A1298C).
Focus on homocysteine metabolism and cardiovascular risk.
```

**Resulting `module_spec.yaml`:**
```yaml
schema_version: "1.0"
module:
  name: mthfr_methylation
  version: 1
  title: "MTHFR Methylation Variants"
  description: "MTHFR variants affecting homocysteine metabolism and cardiovascular risk."
  report_title: "Methylation & Cardiovascular Risk"
  icon: dna
  color: "#21ba45"
defaults:
  curator: ai-module-creator
  method: literature-review
  priority: medium
genome_build: GRCh38
```

**Resulting `variants.csv` (excerpt):**
```csv
rsid,genotype,weight,state,conclusion,gene,phenotype,category
rs1801133,C/C,0,neutral,"Typical MTHFR C677T activity; normal homocysteine metabolism.",MTHFR,Homocysteine Metabolism,Methylation
rs1801133,C/T,-0.6,risk,"MTHFR C677T heterozygote; ~35% reduced enzyme activity; mildly elevated homocysteine risk.",MTHFR,Homocysteine Metabolism,Methylation
rs1801133,T/T,-1.1,risk,"MTHFR C677T homozygote; ~70% reduced enzyme activity; significantly elevated cardiovascular risk.",MTHFR,Homocysteine Metabolism,Methylation
rs1801131,A/A,0,neutral,"Typical MTHFR A1298C activity.",MTHFR,Homocysteine Metabolism,Methylation
rs1801131,A/C,-0.4,risk,"MTHFR A1298C heterozygote; mildly reduced enzyme activity.",MTHFR,Homocysteine Metabolism,Methylation
rs1801131,C/C,-0.8,risk,"MTHFR A1298C homozygote; compound effect when combined with C677T.",MTHFR,Homocysteine Metabolism,Methylation
```

---

## N2 — Agentic Swarm Mode (Research Team)

### Q: How many agents are involved and what is each agent's role?

The team has **3–5 agents** depending on which API keys are configured:

| Agent | Role | Model |
|-------|------|-------|
| **PI (Principal Investigator)** | Team coordinator. Delegates tasks, synthesizes consensus, writes final module, calls all write/validate/register tools. | Gemini Pro (`gemini-3-pro-preview`) |
| **Researcher 1** | Independent variant research using BioContext MCP. Always present. | Gemini Pro (`gemini-3-pro-preview`) |
| **Researcher 2** | Same role as Researcher 1, different LLM for diversity. Present if `OPENAI_API_KEY` is set. | OpenAI GPT (`gpt-5.2`) |
| **Researcher 3** | Same role, third perspective. Present if `ANTHROPIC_API_KEY` is set. | Claude Sonnet (`claude-sonnet-4-5-20250929`) |
| **Reviewer** | Quality review: checks variant integrity, provenance (how many researchers confirmed each variant), weight consistency, PMID validity. | Gemini Flash (`gemini-3-flash-preview`) |

Minimum team: PI + 1 Researcher + Reviewer = 3 agents (Gemini key only).
Maximum team: PI + 3 Researchers + Reviewer = 5 agents (all three keys configured).

### Q: What is the step-by-step flow?

1. **User sends message** (with optional PDF/CSV attachments) → received by PI.
2. **PI delegates** the full research task independently to each Researcher simultaneously (`mode="coordinate"`).
3. **Researchers work in parallel**, each:
   - Extracting variants from attached documents first.
   - For each variant: confirming rsid or GRCh38 position, identifying gene, assessing effect direction, collecting PMIDs.
   - Returning a structured list: rsid, coordinates, genotypes with weights, evidence PMIDs.
4. **PI synthesizes consensus**:
   - Variants confirmed by ≥2 researchers → high confidence → include.
   - Variants from 1 researcher only → scrutinize; omit unless ≥2 strong PMIDs.
   - Weight disagreements → use median estimate.
5. **PI delegates draft** (draft CSV + all researcher outputs) to Reviewer.
6. **Reviewer checks**:
   - Provenance (how many researchers agreed).
   - Variant integrity (rsid format, genotype sorting, wild-type presence).
   - Weight/state consistency (negative=risk, positive=protective, magnitude range).
   - Scientific accuracy (PMID spot-check via Google Search).
   - Returns structured `## ERRORS / ## WARNINGS / ## OK` report.
7. **PI incorporates feedback**: fixes all ERRORs, addresses WARNINGs, rewrites if necessary.
8. **PI writes final module**: `write_spec_files` → `validate_spec` → `write_module_md` → `generate_logo`.
9. **Web UI loads result** into Editing Slot.

### Q: What LLM(s) does each agent use? Are they configurable?

See table above. Configurability:
- PI and Researcher 1 always use Gemini Pro. Model ID overridable via `GEMINI_MODEL` env var.
- Researcher 2 (OpenAI) model hardcoded to `gpt-5.2` in `module_creator.py`.
- Researcher 3 (Anthropic) model hardcoded to `claude-sonnet-4-5-20250929`.
- Reviewer uses Gemini Flash (`gemini-3-flash-preview`) — lighter model, sufficient for structured review.
- Logo generation uses `gemini-2.0-flash` (Imagen 3).

API keys are entered in the left panel's **API Keys** section and saved to `.env`.

### Q: How does the user interact during the process?

**Watch-only during the run.** The chat panel shows:
- A spinner with live status labels (e.g., "Researcher 1 is running...", "Writing spec files...").
- Collapsible tool-call events in the activity panel (each tool call shows label + expandable JSON detail).
- Intermediate researcher outputs are shown as agent messages (Markdown rendered, scrollable).

After the run completes, the user can:
- Review the module in the Editing Slot (title, description, file list, version badge).
- Download the module as a `.zip`.
- **Register** it as an annotation source (compiles to Parquet, adds to `modules.yaml`).
- Send a follow-up chat message to iterate or fix anything.

There are **no approve/reject steps between agent phases** — the PI orchestrates end-to-end.

### Q: What are the current limitations?

- **Max 5 file attachments** per chat message.
- **Supported file types:** PDF, CSV, Markdown (.md), plain text (.txt). No DOCX or HTML.
- **BioContext MCP tool budget:** each Researcher is limited to 9 tool calls (3 tools × 3 queries max) to prevent context overflow. Very large variant sets may be truncated.
- **No human-in-the-loop** between PI→Researcher→Reviewer phases. If the PI misinterprets the task, the entire run must be restarted or corrected via follow-up chat.
- **Gemini key is required.** Without it, neither solo nor team mode runs. OpenAI and Anthropic keys add researchers but are optional.
- **Only GRCh38 and GRCh37 genome builds** are supported in module_spec.yaml.
- **Modules can only annotate SNPs/indels** defined by rsid or chrom/position. Structural variants and copy-number variants are not supported.
- **Logo generation** requires Gemini API access; silently skipped if it fails.
- **No audit trail** stored in the app (intermediate researcher outputs visible in chat session only; not persisted across page reloads).

---

## N3 — Concrete Walkthrough Example

**[NEEDS INPUT]**

This section requires:
1. A real module that was created with the AI system (pick one from `data/output/modules/`).
2. The original user prompt or uploaded paper used to create it.
3. Intermediate agent outputs (researcher responses, reviewer feedback) — visible in the chat session at creation time; not automatically logged.
4. The final module code.
5. Any manual edits made after initial generation.

**Suggested source:** The `longevity_rare_variants` module visible in the screenshots.
If that module was AI-generated, its `MODULE.md` file may contain design notes and the original prompt context.

---

## N4 — Modular Plugin System

### Q: What interface must a module implement?

A module is **not a Python class or function** — it is a directory of DSL files.
No Python code is required from the module author.

Required files:

```
module_name/
├── module_spec.yaml    # Required: metadata, version, genome build
├── variants.csv        # Required: per-variant annotation table
```

Optional files:

```
├── studies.csv         # Evidence: rsid → PMID links
├── MODULE.md           # Human-readable documentation
├── logo.png/jpg/jpeg   # Thumbnail image
└── metadata.json/yaml  # Additional properties
```

**`module_spec.yaml` minimum viable example:**

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

**`variants.csv` required columns:**

| Column | Type | Description |
|--------|------|-------------|
| `rsid` | string | dbSNP ID (e.g. `rs1234567`). Can be blank if chrom/start/ref/alts provided. |
| `genotype` | string | Slash-separated alleles, alphabetically sorted (e.g. `A/G`). |
| `weight` | float | Effect size: negative = risk, positive = protective, 0 = neutral. Range: −1.2 to +1.2. |
| `state` | string | `risk` / `protective` / `neutral`. Must match weight direction. |
| `conclusion` | string | Clinical interpretation (≤50 words). |
| `gene` | string | HGNC gene symbol. |

Additional columns (phenotype, category, chrom, start, ref, alts, etc.) are preserved in annotation output.

### Q: How are modules discovered and loaded at runtime?

1. **Configuration** is read from `modules.yaml` at project root (or fallback path inside the package).
2. **`discover_all_modules()`** iterates over all configured sources.
3. For each source, the loader checks the protocol:
   - `hf://` or bare `org/repo` → Hugging Face Hub
   - `github://org/repo` → GitHub
   - `s3://bucket/path` → AWS S3
   - `https://...` → HTTP
   - `/absolute/path` or `./relative` → local filesystem
4. Auto-detection of `module` vs `collection`: if `weights.parquet` exists at root → single module; otherwise scan subfolders.
5. Result is stored in `MODULE_INFOS: dict[str, ModuleInfo]` and `DISCOVERED_MODULES: list[str]` — module-level globals, populated at import time.
6. **`refresh_modules()`** re-reads `modules.yaml` and re-discovers without a process restart. Called automatically after registration.

**`modules.yaml` source entry formats:**

```yaml
sources:
  - just-dna-seq/annotators          # shorthand: HF Hub collection
  - url: /data/output/modules        # local filesystem collection
    kind: collection
  - url: github://myorg/myrepo       # GitHub collection
    kind: collection
  - url: https://example.com/mods/   # HTTP collection
    kind: collection
```

### Q: Can modules depend on external packages? How are dependencies handled?

Modules are pure-data (YAML + CSV). They have **no Python dependencies**.

The annotation engine (`just_dna_pipelines`) loads modules via Polars LazyFrame — no Python code from the module is executed. All processing logic lives in the pipeline, not the module.

External tool dependencies are on the **pipeline side** (e.g., Polars, pyarrow, huggingface_hub), managed via `uv` in the workspace `pyproject.toml`.

### Q: What data does a module receive as input and what must it return?

The module itself does not "receive" anything — it is a static data source.
The **pipeline** does the work:

**Input to the pipeline:** A normalized VCF file (converted to Parquet by `prepare_vcf_for_module_annotation()`).

**Join process** (`annotate_vcf_with_module_weights()`):
1. Load `weights.parquet` as a Polars LazyFrame.
2. Join against the VCF LazyFrame:
   - **rsid-based join:** `VCF.rsid == weights.rsid` (default)
   - **position-based join:** `VCF.chrom == weights.chrom AND VCF.start == weights.start`
3. Append all columns from the weights table to matching VCF rows.

**Output:** Annotated DataFrame with all VCF columns plus module annotation columns (`weight`, `state`, `conclusion`, `gene`, and any custom columns from `variants.csv`).

**Minimal "Hello World" module:**

`module_spec.yaml`:
```yaml
schema_version: "1.0"
module:
  name: hello_world
  version: 1
  title: "Hello World"
  description: "Minimal example module with one variant."
  report_title: "Hello World Annotations"
  icon: dna
  color: "#21ba45"
defaults:
  curator: human
  method: literature-review
  priority: low
genome_build: GRCh38
```

`variants.csv`:
```csv
rsid,genotype,weight,state,conclusion,gene,phenotype,category
rs1801133,C/C,0,neutral,"Typical MTHFR activity.",MTHFR,Metabolism,Example
rs1801133,C/T,-0.6,risk,"Reduced MTHFR activity.",MTHFR,Metabolism,Example
rs1801133,T/T,-1.1,risk,"Severely reduced MTHFR activity.",MTHFR,Metabolism,Example
```

Register via the web UI: upload these two files to the Editing Slot → click **Register Module as source**.

---

## N5 — AI Module Creation Workflow Diagram

**[NEEDS INPUT / DESIGN WORK]**

Suggested content for a two-lane diagram:

**Lane 1: Simple Mode**
```
User types prompt
      ↓
[optional] Attach PDF/CSV
      ↓
Solo Agent (Gemini Pro)
  ├── BioContext MCP (variant lookup, PMIDs)
  ├── write_spec_files
  ├── validate_spec ──→ [errors?] ──→ self-correct (up to 10 iterations)
  ├── write_module_md
  └── generate_logo
      ↓
Module in Editing Slot
      ↓
User: Register / Download / Iterate
```

**Lane 2: Research Team Mode**
```
User types prompt + optional attachments
      ↓
PI (Gemini Pro) receives task
      ↓ delegates in parallel ↓
Researcher 1    Researcher 2    Researcher 3
(Gemini Pro)    (GPT, optional) (Claude, optional)
      ↓               ↓               ↓
  variant list    variant list    variant list
      ↓
PI synthesizes consensus
  (majority vote on variants; median weights)
      ↓
Draft CSV → Reviewer (Gemini Flash)
  checks: provenance, rsid format, weights, PMIDs
      ↓ returns ERRORS / WARNINGS / OK
PI fixes errors & addresses warnings
      ↓
write_spec_files → validate_spec → write_module_md → generate_logo
      ↓
Module in Editing Slot
      ↓
User: Register / Download / Iterate
```

Decision points:
- After `validate_spec`: errors → agent self-corrects; OK → continue.
- After Reviewer: ERRORs → PI must fix; WARNINGs → PI addresses or documents.
- After Registration: module immediately available in annotation pipeline.
