# Annotation Module Marketplace — Specification

> **Status:** Design / reference specification.
> **Audience:** Implementers of the standalone `just-dna-marketplace` service and of the
> `just-dna-pipelines` / `webui` integration.
> **Purpose:** Seed document for a new repository. Self-contained; can be copied into
> `just-dna-marketplace` as its founding `SPEC.md`.

---

## 1. Motivation

Today, just-dna-lite has **no catalog**. Annotation modules are discovered by reading a
static list of `sources` in `modules.yaml` (HuggingFace dataset repos, local directories,
HTTP, S3). The "Module Manager" page (`webui/src/webui/pages/modules.py`) lists those
sources and hosts an AI module *creator*, but there is:

- no way to **browse a shared catalog** of modules across authors,
- no way to **publish** a module so others can install it,
- no **integrity guarantee** that a downloaded artifact matches its declared inputs.

The goal is a **two-way marketplace**:

1. **Download / install** — browse, search, inspect stats, install. After install a module
   is immediately editable, usable for annotation, and exportable.
2. **Publish / upload** — authors push their own modules under a namespace, with versions.

Every module card shows real stats (variant count, study count, genes, categories), and
every published artifact carries an **integrity contract**: SHA-256 of the input CSVs, a
"compilation succeeded on this input set" flag, and per-file digests a downloader verifies
before installing.

### Key architectural decision

**The marketplace is a standalone server-side service in its own repo
(`just-dna-marketplace`), not part of the Reflex webui.** It needs object storage, a
metadata database, authentication, upload handling, and server-side validation/compilation
— none of which belong in the client web app. The webui and the Dagster pipeline become
*consumers* of the marketplace API.

The marketplace plugs into the existing `Source` discovery model as **just another source**,
so existing HuggingFace/local modules keep working with zero migration.

---

## 2. Background: what an annotation module is

A module is authored as a **DSL spec directory** and compiled into a **three-parquet
artifact**.

**Spec inputs** (authored by hand or by the AI creator):

| File | Purpose |
|---|---|
| `module_spec.yaml` | Identity + display metadata: `name` (`^[a-z][a-z0-9_]*$`), `title`, `description`, `report_title`, `icon` (Fomantic UI icon name), `color` (`#rrggbb`), `genome_build` (default `GRCh38`), `defaults.curator`, `defaults.method` |
| `variants.csv` | One row per genotype: `rsid`, `chrom`/`start`/`ref`/`alts`, `genotype`, `weight`, `state` (risk\|protective\|neutral\|significant\|alt\|ref), `conclusion`, `gene`, `phenotype`, `category`, ClinVar flags |
| `studies.csv` | Grounding evidence (mandatory): `rsid`/position, `pmid`, `population`, `p_value`, `conclusion`, `study_design` |
| `logo.png` / `MODULE.md` | Optional logo image and readme |

**Compiled outputs** (`compile_module()` in
`just-dna-pipelines/src/just_dna_pipelines/module_compiler/compiler.py`):

| File | Content |
|---|---|
| `weights.parquet` | One row per genotype with weights |
| `annotations.parquet` | Deduplicated per variant: gene / phenotype / category |
| `studies.parquet` | Study evidence rows |

**Discovery** (`just-dna-pipelines/src/just_dna_pipelines/annotation/hf_modules.py`) probes
a path for `weights.parquet` (required) plus optional `annotations.parquet`,
`studies.parquet`, `logo.*`, and — importantly — **already probes for `metadata.json` /
`metadata.yaml`** (`_probe_module_at_path`). Nothing currently *writes* that metadata file.
**This is the seam the marketplace extends.**

The `Source` model (`module_config.py`) already supports HuggingFace (`org/repo`), local
dirs, HTTP, S3/GCS (fsspec), and `github://`. Versioned layouts (`{name}/v{N}/`) are already
understood by discovery and are the live convention for compiled output.

---

## 3. System overview

```
┌─────────────────┐    browse / search / install / publish (HTTPS/JSON)  ┌──────────────────────────┐
│  webui (Reflex) │ ─────────────────────────────────────────────────────▶│  just-dna-marketplace     │
│  + Dagster      │◀──────────────── module manifest + artifacts ──────────│  (FastAPI, new repo)      │
└─────────────────┘                                                        │  • catalog index (DB)     │
        │ install writes to CUSTOM_MODULES_DIR                              │  • auth / namespaces      │
        ▼                                                                   │  • server-side compile    │
  register_custom_module + refresh_module_registry (existing)              │  • integrity manifests    │
                                                                            └──────────┬───────────────┘
                                                                                       │ artifacts + versions
                                                                                       ▼
                                                                            HuggingFace Hub datasets
                                                                            (storage / CDN / versioning)
```

**Backend recommendation — hybrid.** Use **HuggingFace Hub datasets as the artifact store**
(modules already live at `just-dna-seq/annotators`; free CDN, git-revision versioning,
existing `HfFileSystem` discovery path → zero migration) fronted by a **thin FastAPI
indexer** for search, faceted filters, card stats, auth-gated publish, and the server-side
compile/validate gate that HF cannot provide. The service DB is a *projection* built by
crawling each module's `manifest.json`.

**Publish trust model — server-side re-compile.** The publisher uploads the **spec only**;
the server runs `compile_module()` itself, so `compile_success`, input hashes, and artifact
digests are produced by the trusted party and cannot be forged. This reuses existing
pipeline code (the service depends on `just-dna-pipelines`).

### Build-fresh vs. reuse HuggingFace Hub — tradeoffs

| | Reuse HF Hub as backend | Build fully fresh |
|---|---|---|
| Two-way (download + upload) | Native (repos, uploads, tokens, git-revision versions, CDN) | Must build upload/auth/storage |
| Existing modules | Zero migration — they already live on HF | Must mirror/import |
| Faceted search (by gene/category) | Weak (repo-level only) | Full control |
| Server-side compile/validate gate | Not native | First-class |
| Ops burden | Low (HF hosts artifacts) | Host DB + bucket + API |

**Chosen: hybrid** — HF for storage/CDN/versioning + a thin fresh indexer for the catalog
features HF can't provide.

---

## 4. Metadata contract — the `manifest.json`

The manifest is the heart of the design. It is the `metadata.json` that discovery already
looks for, extended with provenance and integrity fields. It is written next to the parquets
for **every** compiled module (locally and on publish) and is the **source of truth**; the
service DB is just a queryable projection of it.

Fields known at **compile time** are filled by `compile_module()`. Fields that are
**marketplace-level** (namespace, version, owner, license, published_at, canonical_id) are
left null by the local compiler and filled by the service on publish.

```json
{
  "manifest_version": "1.0",
  "schema_version": "1.0",

  "identity": {
    "namespace": "just-dna-seq",
    "name": "longevity_variants_2026",
    "version": "2.0.0",
    "canonical_id": "just-dna-seq/longevity_variants_2026@2.0.0"
  },

  "display": {
    "title": "Longevity Variants 2026",
    "description": "Rare protective variants associated with familial longevity...",
    "report_title": "Familial Longevity & cGAS-STING Pathway",
    "icon": "heart-pulse",
    "color": "#21ba45"
  },

  "genome_build": "GRCh38",
  "curator": "ai-module-creator",
  "method": "literature-review",
  "license": "CC-BY-4.0",

  "owner": "antonkulaga",
  "authors": ["antonkulaga"],
  "created_at": "2025-10-24T12:00:00Z",
  "published_at": "2025-10-24T12:05:00Z",

  "stats": {
    "variant_count": 16,
    "weights_rows": 48,
    "study_count": 5,
    "gene_count": 8,
    "genes": ["CGAS", "NUP210L", "SLC27A3", "CD1A", "IBTK", "RARS2", "SH2D3A", "TERT"],
    "categories": ["cGAS-STING pathway", "multimorbidity"]
  },

  "compilation": {
    "compile_success": true,
    "compiled_by": "marketplace-server",
    "compiler_version": "just-dna-pipelines 0.1.6",
    "ensembl_reference": "just-dna-seq/ensembl_variations@<rev>",
    "compiled_at": "2025-10-24T12:04:30Z",
    "warnings": []
  },

  "inputs": [
    { "name": "module_spec.yaml", "sha256": "sha256:ee..", "size": 417 },
    { "name": "variants.csv",     "sha256": "sha256:ff..", "size": 4350 },
    { "name": "studies.csv",      "sha256": "sha256:11..", "size": 2900 }
  ],

  "artifact": {
    "digest": "sha256:9f2c...ab",
    "files": [
      { "name": "weights.parquet",     "sha256": "sha256:aa..", "size": 40190 },
      { "name": "annotations.parquet", "sha256": "sha256:bb..", "size": 3120 },
      { "name": "studies.parquet",     "sha256": "sha256:cc..", "size": 2210 },
      { "name": "logo.png",            "sha256": "sha256:dd..", "size": 280932 }
    ]
  }
}
```

**Mapping to existing code:**
- `display.*`, `genome_build`, `curator`, `method` map 1:1 from `ModuleSpecConfig`
  (`module_compiler/models.py`).
- `stats.variant_count` = `unique_variants`, `study_count` = `study_rows`, `genes` /
  `categories` come from `validate_spec` (which already computes these sets; it must be
  extended to emit the *lists*, filtering `None`).
- `inputs[]` and `artifact` are the new compile-time integrity fields.

---

## 5. Integrity mechanism

All hashes are SHA-256, lowercase hex, prefixed `sha256:`.

- **Input hashes** (`inputs[].sha256`): SHA-256 over the **raw bytes** of each input file
  (`module_spec.yaml`, `variants.csv`, `studies.csv`), no normalization → byte-reproducible
  by any downloader holding the same file.
- **Per-file artifact hashes** (`artifact.files[].sha256`): SHA-256 over the concrete written
  bytes of each parquet and the logo. Parquet is **not** deterministic across polars/arrow
  versions, so the manifest hashes the *bytes actually written* and pins `compiler_version`
  + `ensembl_reference` so a re-compile can be reproduced when needed.
- **Artifact digest** (`artifact.digest`): SHA-256 over a canonical listing of the files —
  build the JSON array `[{"name","sha256","size"}, ...]` sorted by `name`, serialized with
  sorted keys and no whitespace, then hash. This is a Merkle-style root: verifying it
  verifies the whole set cheaply, and it is the version's content identity.
- **`compile_success`**: `true` only when the server's own `compile_module()` returned
  success. A downloader treats `false`, or a foreign `compiled_by`, as untrusted.

**Client verify-then-install flow:**
1. Fetch `manifest.json`.
2. For each `artifact.files[]`: download, compute SHA-256, compare. Any mismatch → abort.
3. Recompute `artifact.digest` from the verified file list; compare to the manifest.
4. Check `compilation.compile_success == true` and `compiled_by == "marketplace-server"`.
5. (Optional, strongest) If spec files were downloaded, recompute `inputs[].sha256` and
   compare — proves the artifact's declared inputs match the shipped inputs. A power user can
   then re-run `compile_module()` with the pinned versions and diff parquets for full
   reproducibility.
6. Only then write the directory into `CUSTOM_MODULES_DIR` and `refresh_module_registry()`.

**Future:** the server can sign `artifact.digest` with an Ed25519 key and publish the pubkey,
so clients can defend against a compromised storage backend. Not required for MVP.

---

## 6. Versioning & identity

- **Identity** = `namespace/name`. `name` keeps the existing rule `^[a-z][a-z0-9_]*$`;
  `namespace` is an owned account/org slug. This ends the current flat-name collision problem
  (today discovery just takes "earliest source wins" on name collision).
- **Version** = SemVer `MAJOR.MINOR.PATCH` for public ordering. Map the legacy integer /
  `vN` directory convention as `v1 → 1.0.0`, `v2 → 2.0.0` on import.
  - **MAJOR**: variant set / weights changed in a way that alters annotation results.
  - **MINOR**: variants/studies added; weights unchanged for existing genotypes.
  - **PATCH**: metadata/description/logo/typo only (no data change).
- **Content identity** vs. SemVer: SemVer orders for humans; `artifact.digest` is the
  immutable content identity. Identical bytes → identical digest.
- **Immutability**: a published `(namespace, name, version)` is immutable. Re-publishing an
  existing version → `409`. **Yank** (`POST .../yank`) sets `yanked=true`: the version
  disappears from default listings and `latest`, but its manifest + artifact remain fetchable
  so existing installs keep verifying. Un-yank is allowed.

---

## 7. Service capabilities

| Capability | Approach |
|---|---|
| Catalog index | SQLite (MVP) → Postgres. Rows per `(namespace, name, version)` + a denormalized "latest" view for the card grid. `manifest.json` is source of truth; the DB is a projection. Side tables `version_genes` / `version_categories` for facet filters. |
| Artifact storage | HF Hub datasets (hybrid) or S3/MinIO. Immutable, content-addressed by digest (`artifacts/sha256/<digest>/…`). |
| Search / facets | DB full-text over title/description + side-table joins for `?gene=` / `?category=`. |
| Versioning | SemVer for ordering + `artifact.digest` for identity/integrity (§6). |
| Auth & ownership | Bearer tokens. A `namespace` is owned by exactly one account (or an org with members). Publish under a namespace requires membership. |
| Publish validation | **Always** run `validate_spec()`. **Default** server-side `compile_module()` (see below). |
| Integrity | Per-file SHA-256 + Merkle-root `artifact.digest` + input-CSV hashes (§5). |
| Rate limiting | Per-token token buckets: publish 10/h, download 1000/h, search 60/min. Anonymous reads allowed but throttled harder. |

**Validate vs. re-compile on publish:**
- **Minimum (always):** run `validate_spec()` on the uploaded spec (reuses
  `just_dna_pipelines.module_compiler.validate_spec`). Reject invalid specs.
- **Recommended default — server re-compiles:** publisher uploads the spec only; the server
  runs `compile_module()`, producing the parquets and manifest. This makes `compile_success`,
  input hashes, and artifact digests trustworthy, pins one Ensembl reference across the
  ecosystem, and prevents shipping a parquet that disagrees with its CSVs. The service
  depends on `just-dna-pipelines` for this.
- **Alternative — trust-but-verify upload:** publisher uploads pre-built parquets + manifest;
  server re-validates and (if spec included) re-compiles in a sandbox and compares digests,
  rejecting on mismatch. Use only if server compile cost is prohibitive.

---

## 8. Interface contract (REST)

Base URL: `https://marketplace.dna-seq.org/api/v1`. All bodies JSON unless noted. List
responses paginate with `?page`, `?per_page` (max 100) → `{items, total, page, per_page}`.

### 8.1 Endpoint table

| # | Method | Path | Auth | Purpose |
|---|---|---|---|---|
| 1 | GET | `/modules` | none | List/search (card grid) |
| 2 | GET | `/modules/{ns}/{name}` | none | Detail + stats + versions + readme |
| 3 | GET | `/modules/{ns}/{name}/versions` | none | Version list |
| 4 | GET | `/modules/{ns}/{name}/versions/{v}/manifest` | none | Full manifest |
| 5 | GET | `/modules/{ns}/{name}/versions/{v}/download` | none | Artifact tarball (302 → presigned) |
| 6 | GET | `/modules/{ns}/{name}/versions/{v}/files/{file}` | none | Single file (presigned redirect) |
| 7 | POST | `/modules/{ns}/{name}/versions` | bearer | Publish init → presigned PUT targets |
| 8 | POST | `/modules/{ns}/{name}/versions/{v}/finalize` | bearer | Validate/recompile, index |
| 9 | POST | `/modules/{ns}/{name}/versions/{v}/yank` | bearer | Yank (unlist, keep artifact) |
| 10 | POST | `/auth/tokens` | credentials | Issue a token |
| 11 | GET | `/auth/whoami` | bearer | Identity + namespaces |

Search params on #1: `?q=`, `?category=`, `?gene=`, `?genome_build=`, `?owner=`,
`?license=`, `?sort=downloads|recent|name`.

### 8.2 List / search — `GET /modules`

```json
{
  "items": [
    {
      "namespace": "just-dna-seq",
      "name": "longevity_variants_2026",
      "title": "Longevity Variants 2026",
      "description": "Rare protective variants associated with familial longevity...",
      "icon": "heart-pulse",
      "color": "#21ba45",
      "latest_version": "2.0.0",
      "genome_build": "GRCh38",
      "license": "CC-BY-4.0",
      "owner": "antonkulaga",
      "stats": {
        "variant_count": 16, "study_count": 5, "gene_count": 8,
        "genes": ["CGAS", "NUP210L", "SLC27A3"],
        "categories": ["cGAS-STING pathway", "multimorbidity"]
      },
      "downloads": 214,
      "updated_at": "2025-10-24T12:00:00Z"
    }
  ],
  "total": 47, "page": 1, "per_page": 20
}
```

`genes` in the card view is truncated (top N); the full list lives in the detail/manifest.

### 8.3 Detail — `GET /modules/{ns}/{name}`

Returns the card object plus `readme` (MODULE.md), the full `stats.genes`, the embedded
`versions` array, and `latest_manifest` inline.

### 8.4 Versions — `GET /modules/{ns}/{name}/versions`

```json
{
  "items": [
    {
      "version": "2.0.0",
      "artifact_digest": "sha256:9f2c...ab",
      "compile_success": true,
      "yanked": false,
      "created_at": "2025-10-24T12:00:00Z",
      "changelog": "Integrated 18 genotypes across 6 novel loci.",
      "manifest_url": "/api/v1/modules/just-dna-seq/longevity_variants_2026/versions/2.0.0/manifest"
    }
  ],
  "total": 2, "page": 1, "per_page": 20
}
```

### 8.5 Download — `GET .../versions/{v}/download`

Default: `302` redirect to a presigned URL for `module.tar.zst` (whole module dir +
`manifest.json`). `?format=files` instead returns per-file `{name, url, sha256, size}` for
selective download + verification.

### 8.6 Publish init — `POST /modules/{ns}/{name}/versions`

Request declares the version and files (with client-computed hashes):

```json
{
  "version": "2.0.0",
  "changelog": "Integrated 18 genotypes across 6 novel loci.",
  "publish_mode": "recompile",
  "files": [
    { "name": "module_spec.yaml", "sha256": "sha256:ee..", "size": 417 },
    { "name": "variants.csv",     "sha256": "sha256:ff..", "size": 4350 },
    { "name": "studies.csv",      "sha256": "sha256:11..", "size": 2900 },
    { "name": "logo.png",         "sha256": "sha256:dd..", "size": 280932 },
    { "name": "MODULE.md",        "sha256": "sha256:22..", "size": 1970 }
  ]
}
```

Response: presigned PUT targets + a finalize URL. (A single `multipart/form-data` POST is an
acceptable MVP alternative; presigned scales better for large parquet.)

```json
{
  "upload_id": "up_01H...",
  "targets": [ { "name": "variants.csv", "put_url": "https://cdn/...", "expires_at": "..." } ],
  "finalize_url": "/api/v1/modules/just-dna-seq/longevity_variants_2026/versions/2.0.0/finalize"
}
```

Errors: `409 version_exists` (immutability), `403 not_namespace_member`, `422 invalid_version`.

### 8.7 Finalize — `POST .../versions/{v}/finalize`

Body `{ "upload_id": "up_..." }`. Server then:
1. Verifies each uploaded file's SHA-256 against the declared hash.
2. Runs `validate_spec()`. On error → `422` with the `errors[]` / `warnings[]` arrays.
3. `recompile` mode: runs `compile_module()` (pinned Ensembl reference), computes stats +
   digests, sets `compile_success`. `prebuilt` mode: re-compiles in a sandbox and compares
   parquet digests → `422 digest_mismatch` on disagreement.
4. Writes artifacts to storage keyed by digest, builds `manifest.json`, inserts DB rows.

Response `201`: the full manifest (§4).

### 8.8 Auth — `POST /auth/tokens`

```json
// request
{ "grant": "api_key", "key": "mk_live_..." }
// response
{ "token": "eyJ...", "token_type": "Bearer", "expires_in": 86400,
  "identity": { "account": "antonkulaga", "namespaces": ["antonkulaga", "just-dna-seq"] } }
```

Publish endpoints require `Authorization: Bearer <token>`; the token's `namespaces` must
include the path `{ns}`.

---

## 9. Storage & deployment shape

Recommended MVP: a **FastAPI** service (new repo `just-dna-marketplace`) depending on
`just-dna-pipelines` for `validate_spec` / `compile_module` / the manifest models.

- **Metadata DB:** SQLite (single file) for MVP → Postgres for production. Tables:
  `accounts`, `namespaces`, `namespace_members`, `modules(namespace, name, …)`,
  `versions(module_id, version, digest, manifest_json, compile_success, yanked, created_at,
  downloads)`, plus `version_genes` / `version_categories` for facet queries.
- **Artifact storage:** HF Hub dataset repos (hybrid path) — commit the module directory
  (parquets + spec + `manifest.json`) to `data/{name}/v{N}/`; or S3/MinIO keyed by digest.
  Content-addressing gives dedup + immutability for free.
- **Serving:** the API serves JSON + issues 302 redirects to presigned/CDN URLs.
- Deployable as one container + a bucket/HF repo + a DB. No heavyweight orchestration.

Concretely: `finalize` compiles server-side, commits to the HF dataset repo, and upserts the
DB projection. Download endpoints redirect to HF `resolve` URLs.

---

## 10. Prerequisite work in `just-dna-pipelines` (this repo)

This is a **purely additive** refactor that unblocks card stats + integrity *before* the
service exists. Discovery already probes for `metadata.json` — this closes that seam.

**A1 — `ModuleManifest` model.** Add to
`just-dna-pipelines/src/just_dna_pipelines/module_compiler/models.py` a Pydantic
`ModuleManifest` (with sub-models for `identity`, `display`, `stats`, `compilation`,
`inputs[]`, `artifact`), matching §4. Marketplace-only fields (namespace, version, owner,
license, published_at, canonical_id) are `Optional`, filled by the service on publish.

**A2 — emit `manifest.json` from compilation.** In `compile_module()`
(`module_compiler/compiler.py`, after the parquets are written): compute `inputs[].sha256`
over the raw input bytes, `artifact.files[].sha256`/`size` over the written outputs,
`artifact.digest` (canonical Merkle root), set `compilation.compile_success` /
`compiler_version` / `compiled_at`, and write `manifest.json` into `output_dir`.

**A3 — gene/category lists.** `validate_spec()` already computes the `genes` / `categories`
sets (currently reports only counts). Extend `ValidationResult.stats` to also emit
`genes: list[str]`, `categories: list[str]` (filtering `None`), `variant_count`,
`study_count`, `gene_count`; thread these into `manifest.stats`.

**A4 — packaging & registration.** The `.zip` export endpoint (`webui/src/webui/app.py`,
`agent-spec-zip` route) already bundles all non-`.parquet` files, so `manifest.json` is
included once written. Add `.json` to `_SPEC_SUFFIXES` in
`module_registry.py` (`register_custom_module`) so `manifest.json` is preserved on install.

**A5 — backfill.** A one-off crawl that runs `validate_spec` / `compile_module` over existing
HF/local modules to generate `manifest.json` for each, populating the extended contract
across the current catalog.

---

## 11. Consumer integration in `webui` (this repo)

- **Discovery:** add a `marketplace://` branch in `discover_modules_from_source`
  (`hf_modules.py`) that calls `GET /modules` + per-version manifest instead of walking a
  filesystem; register the marketplace as one entry in `ModulesConfig.sources`
  (`module_config.py`). Existing sources untouched.
- **Install:** reuse the existing `register_custom_module` write-and-refresh path — installed
  modules are immediately editable / annotatable / exportable with no new code path.
- **Catalog page:** a new page under `webui/src/webui/pages/` — card grid + search/filter +
  detail drawer, reusing the existing `module_metadata_list` computed var (`state.py`) shape
  and the `/api/module-logo/{name}` endpoint. Register via `app.add_page`; add a topbar nav
  tab in `components/layout.py`. A "Publish" action uploads the current editing-slot spec.

---

## 12. Compatibility & migration

**The marketplace is an additional `Source`, not a replacement** — lowest-risk path,
minimal client change.

- Existing HF/local/S3 sources keep working unchanged.
- Because the marketplace uses HF Hub as backend, existing modules in
  `just-dna-seq/annotators` need **zero migration** — the same repo is both a legacy `Source`
  and marketplace-indexed. The only additive step is generating a `manifest.json` per module
  (the A5 backfill), which discovery consumes automatically.
- Installs write to `CUSTOM_MODULES_DIR` exactly like `register_custom_module` today.
- Never remove the generic `Source` mechanism; optionally deprecate ad-hoc HTTP/S3 sources in
  favor of the marketplace later.

**Phasing:**
1. Prerequisite work (§10) — additive, in `just-dna-pipelines`.
2. Backfill manifests for existing HF modules.
3. Stand up the FastAPI indexer + publish over HF backend (`just-dna-marketplace`).
4. Add the `marketplace://` source branch + catalog page + install/publish UI in `webui`.
5. Later: optional Ed25519 signing.

---

## 13. Verification

- **Prerequisite (§10):** unit-test that `compile_module` emits `manifest.json` with correct
  `inputs[].sha256` (vs. `hashlib.sha256` of the source CSVs), non-empty `artifact.files[]`,
  `compile_success=true`, and `stats.genes`/`categories` matching a fixture. Round-trip:
  compile → tamper one parquet byte → client verification detects the digest mismatch.
- **Service:** contract tests per endpoint. `finalize` with an invalid spec → `422` carrying
  `ValidationResult.errors`; re-publishing an existing version → `409`.
- **End-to-end:** publish a module from webui → it appears in `GET /modules` with correct
  stats → install in a second client → integrity verification passes → the module shows in
  Module Manager, can be selected for annotation, and can be exported (`.zip`).
- **Migration:** run the backfill over `just-dna-seq/annotators`; confirm each module gets a
  valid `manifest.json` and still discovers/annotates unchanged.

---

## 14. Key files referenced

**`just-dna-pipelines`:**
- `src/just_dna_pipelines/module_compiler/compiler.py` — `compile_module`, `validate_spec`.
- `src/just_dna_pipelines/module_compiler/models.py` — DSL models; add `ModuleManifest`.
- `src/just_dna_pipelines/annotation/hf_modules.py` — discovery; probes `metadata.json`; add `marketplace://` branch.
- `src/just_dna_pipelines/module_registry.py` — `register_custom_module` (install target); `_SPEC_SUFFIXES`.
- `src/just_dna_pipelines/module_config.py` — `Source` / `ModulesConfig`.

**`webui`:**
- `src/webui/pages/modules.py` — existing Module Manager.
- `src/webui/pages/` — new catalog page.
- `src/webui/components/layout.py` — topbar nav tab.
- `src/webui/app.py` — page registration; `agent-spec-zip` export route.
- `src/webui/state.py` — `module_metadata_list` computed var (catalog card shape).

**New repo `just-dna-marketplace`** — FastAPI service; depends on `just-dna-pipelines` for
`validate_spec` / `compile_module` / `ModuleManifest`.
