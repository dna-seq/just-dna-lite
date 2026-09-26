# The just-dna-lite MCP server

just-dna-lite ships a Model Context Protocol server so an AI coding agent (Claude Code, Cursor,
Codex, or anything else that speaks MCP) can see which genomes and annotation modules this
installation holds, run annotations in the background, and read the results back.

The main user is an agent helping someone write a module with
[just-module-creator](https://github.com/dna-seq/just-module-creator): compile the module, install
it here, run it over a few genomes, look at what matched and how the scores are distributed, fix
the module, repeat.

Nothing leaves your machine because of this server. What the agent reads, however, goes to
whichever model provider the agent uses, and annotation results contain real people's genotypes.
Choose the genomes you run on with that in mind.

## Connecting

The server speaks two transports. Both use the same job store and the same `DAGSTER_HOME`, so a
job started through one shows up through the other and in the Dagster UI.

**stdio** (the client starts the server when it needs it; works whether or not the app is running):

```bash
# Claude Code
claude mcp add just-dna-lite -- uv run --project /path/to/just-dna-lite python -m just_dna_pipelines.lite_mcp
```

```json
// Cursor: .cursor/mcp.json (project) or ~/.cursor/mcp.json (global)
{
  "mcpServers": {
    "just-dna-lite": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/just-dna-lite", "python", "-m", "just_dna_pipelines.lite_mcp"]
    }
  }
}
```

`uv run pipelines mcp` does the same thing. The `python -m` form is recommended because it avoids
the `pipelines` console-script wrapper, which locked-down Windows machines refuse to run.

**HTTP** (served by `uv run start` next to the web UI, on port 3006 by default):

```bash
claude mcp add --transport http just-dna-lite http://localhost:3006/mcp
```

```json
{ "mcpServers": { "just-dna-lite": { "url": "http://localhost:3006/mcp" } } }
```

Set `JUST_DNA_MCP_PORT` to move it, `JUST_DNA_MCP_HOST` to bind elsewhere, and
`JUST_DNA_MCP_HTTP=false` to not start it. It binds to `127.0.0.1` by default. If the port is
already taken, `uv run start` says so and carries on without it. To serve HTTP without the rest of
the stack: `uv run pipelines mcp --transport http`.

Opening `http://127.0.0.1:3006/mcp` in a browser is not a tool list. The page that lists and calls
the tools is the MCP Inspector, pointed at the server `uv run start` is already serving:

```bash
npx @modelcontextprotocol/inspector http://127.0.0.1:3006/mcp
```

`npx` downloads it the first time. The process prints the page to open (port 6274 by default, and
the query token belongs in the address). `fastmcp dev apps` is a preview for tools registered with
`@app.ui()`; this server has none, so that page stays empty.

While that stack is running, the other two pages are the ones the launcher prints: the web app
(Reflex, `http://localhost:3000` only when that port was free) and the Dagster dashboard
(`http://127.0.0.1:3005` unless `DAGSTER_PORT` or `--dagster-port` moved it).

## Tools

| Tool | What it does |
|---|---|
| `status` | Which checkout this is, its versions, `DAGSTER_HOME`, how many modules and genomes, active jobs. Call it first. |
| `list_samples` | Genomes under `data/input/users/*`, whether each is normalized, earlier outputs, plus configured public genomes not downloaded yet. |
| `list_modules` | Discovered modules with source, lead table, and the version/digest they state. |
| `install_module` | Copy a compiled module directory in (no recompile, so the digest you tested is the one that runs). Replaces an earlier install of the same name made through this server; refuses to shadow another source's module or overwrite a registry install. |
| `uninstall_module` | Remove a module installed through `install_module`. |
| `start_annotation` | Start a background job: these genomes, these modules. Returns a job id at once. |
| `get_job` / `list_jobs` | Status, per-genome progress (live Dagster steps while running), errors, worker log tail. |
| `wait_for_job` | Block until the job settles, sending progress notifications. |
| `cancel_job` | Stop a job; genomes already finished keep their results. |
| `get_results` | Per genome: report path, and per module whether it annotated, was skipped or failed, and rows matched/restored. |
| `validate_module` | Coverage, score distribution and join health for one module over every genome in a job. |
| `get_variant_rows` | Per-genome rows: each sample's genotype at each module variant and the weight it got, or the coverage matrix filtered by status. |

## How jobs run

`start_annotation` writes `data/interim/lite_mcp/jobs/<job_id>/job.json` and starts a worker
process (`python -m just_dna_pipelines.lite_mcp.worker`) that runs the genomes one after another
through the same Dagster jobs as the web UI. Jobs queue behind each other, because a whole-genome
normalization takes a lot of memory. The worker is its own process, so a job keeps running after
the agent session that started it ends, and a later session can still ask about it.

A genome whose normalized parquet is current for the quality filters in force is not normalized
again (`annotate_modules_and_report_job`). The web UI uses the same staleness test. On the three
genomes used for testing, a first pass took 141 s and a second pass 50 s.

Runs write into each sample's normal output directory, exactly like a web UI run: the latest run
is what the UI shows for that sample, and every run adds a timestamped report. The worker also
copies each module's output parquet and the manifest into the job directory, so validating a job
later reads the bytes that job produced, not a later run's.

**Long calls and clients.** No tool call does annotation work itself. `wait_for_job` is the only
tool that blocks, and it sends a progress notification every few seconds. In Claude Code a call
still running after two minutes moves to a background task, and the result arrives when the job
settles. Clients that don't do that can poll `get_job` instead. Progress also keeps the call alive
under idle timeouts (Claude Code's default is 30 minutes for stdio servers and 5 minutes for HTTP).
The server does not use the MCP Tasks extension, because neither Claude Code nor Cursor supports
it yet.

## What `validate_module` checks

Every finding says which threshold triggered it. `not_assessed` means the check could not run,
never that it passed. These are readings for an author, not verdicts.

**Coverage.** For each authored locus in each genome, one of:

- `called_matched`: the sample was called there and its genotype matches an authored row.
- `restored_hom_ref`: no call, and the module authors the reference genotype, so the engine
  inferred it (whole-genome, variant-only callsets only).
- `called_unmatched`: called there, but with a genotype the module never authored.
- `called_ref_mismatch`: called there with a different reference allele than the module's `ref`.
  The engine discards these rows.
- `not_observed`: no call at that position.

Findings built from those statuses: `loci_never_observed` (a paper's variant that none of your
genomes carries), `called_but_never_matched` (usually a missing genotype row or a strand/allele
orientation mistake; compare `observed_unmatched_genotypes` with `authored_genotypes`), and
`reference_allele_mismatch` (a wrong coordinate, a different indel spelling, or a GRCh37 position).

**Scores.** Per genome, the sum of authored `weight` over matched rows, the positive and negative
parts, the variant that contributes most, and the share contributed by inferred rows. Across
genomes (at least three):

| Finding | What it means |
|---|---|
| `constant_score` | Every genome gets the same score. |
| `one_sided_scores` | Every genome lands on the same side of zero. |
| `dominated_by_one_variant` | One variant carries over 50% of the summed \|weight\| in most genomes. |
| `score_carried_by_inferred_rows` | Restored hom-ref rows carry over 50% of the \|weight\| in most genomes. |
| `weight_shared_by_all_genomes` | A (locus, genotype) row with non-zero weight matches in every genome, shifting every score. |
| `weight_outliers` | An authored \|weight\| over 10× the module's median non-zero \|weight\|. |

**Join health.** Position join or rsID fallback, rows without coordinates, ambiguous positions
(`locus_count > 1`), phased rows that cannot match, and modules skipped or failed per genome.

Validation reads presence from `user_vcf_normalized.parquet` and matches from the job's copy of the
module output. The full (genome, locus) matrix is written to
`jobs/<job_id>/validation/<module>_coverage.parquet` and can be read through `get_variant_rows`
with `coverage_status`.

## Code

- `just_dna_pipelines/lite_mcp/server.py`: the tools and the `serve` command.
- `just_dna_pipelines/lite_mcp/jobs.py`: the on-disk job store, spawning, reconciling a dead worker, and cancellation.
- `just_dna_pipelines/lite_mcp/worker.py`: runs one job.
- `just_dna_pipelines/lite_mcp/catalog.py`: samples, modules, and trial installs (the ledger is `data/interim/lite_mcp/installs.json`).
- `just_dna_pipelines/lite_mcp/validation.py`: coverage, scores and findings.
- `just_dna_pipelines/annotation/annotation_runner.py`: one sample's run, shared with `uv run annotate`.
- Tests: `just-dna-pipelines/tests/test_lite_mcp.py`.

If HuggingFace is slow, the server can take 20 s or more to start (module discovery reads every configured source at startup); raise the client's startup timeout (`MCP_TIMEOUT` in Claude Code) if the connection is dropped. A source that could not be reached at startup is skipped until `list_modules(refresh=true)`.

PRS is not exposed yet. It runs inside the Reflex UI rather than Dagster, so it needs its own job
first.
