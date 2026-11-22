# Releasing Longevity Map 2.0.0

Longevity Map 2.0.0 supersedes the Generation I port (1.2.0). The authored spec is
`data/modules/longevitymap_v2/`; what it is and what it found: `docs/longevitymap_v2/recuration/README.md`. It was
curated in [dna-seq/longevity-loci](https://github.com/dna-seq/longevity-loci) and rehearsed on the polygon as
`test-longevity-loci/longevitymap@2.0.0`.

**Publishing is the maintainer's call and the maintainer's hands** (`CLAUDE.md`, "Building and releasing modules").
Nothing below has been run against prod or the HuggingFace collection. Steps 1 and 2 are safe to repeat; steps 4
and 5 write in public.

## What stays frozen

- **1.2.0 is not rebuilt or republished.** `uv run pipelines v1-port port --all` still builds `longevitymap` from
  the Generation I SQLite into `data/interim/v1_port/` (the port code, `data/modules/just_longevitymap/` and
  `data/longevity_map.tsv` stay, as the audit in `docs/longevitymap_v2/audit/` reads them), but that build is not
  published again: from 2.0.0 on, the `longevitymap` name is published from the spec above.
- **On the registry**, `just-dna-seq/longevitymap@1.2.0` stays installable by its version; 2.0.0 is added after it.
- **On the HuggingFace collection**, `data/longevitymap/` holds one module, so step 5 replaces 1.2.0's files there;
  1.2.0 remains in the dataset's git history. If 1.2.0 should stay discoverable by default as well, publish it under
  its own folder name first (open point for the maintainer; not done here).

## 1. Compile strict (local, safe)

```bash
uv run pipelines module compile data/modules/longevitymap_v2 -o data/interim/release/longevitymap --strict
```

Expected (just-dna-compiler 0.8.5 and 0.8.9 alike): success; 513 weights rows, 697 studies, 6 haplotypes, 12 diplotypes, 3 sources; content signature
`sha256:997b3356f554793d149cc9c2f128dd8115741f96255605891826f7d658b1c024` (longevity-loci 9d87300: 172 loci with the literature
sweep's rows, the study notes worded for a reader; the same signature from longevity-loci's own build). Warnings: about 20 lines on indel VRS ids that cannot be verified without the reference
sequence, and `module_not_closed` (see "Before publishing").

## 2. Read it in the app (local, safe)

A module registered locally under a published name is shadowed by the remote one, so either annotate with the
HuggingFace source off:

```bash
cp -r data/interim/release/longevitymap data/output/modules/longevitymap
HF_HUB_OFFLINE=1 uv run annotate <a GRCh38 VCF> --user release-check -m longevitymap
```

Measured 2026-11-19 on the 164-locus build, on the public demo genome (Zenodo 18370498): 163 of the module's rows matched, 98 of them
inferred reference genotypes. The module takes the report's generic module section, not the Generation I pathway
section (`report_logic.uses_longevity_pathways`): its categories are the systems a locus acts through, not the 12
pathways, and in the pathway section every row dropped out ("0 Total variants"). Remove the local copy afterwards.

## 3. Before publishing

The report-voice rule applies (`CLAUDE.md`, "Report voice"): two independent reviewer agents, a lay reader and a
scientific reviewer, read the rendered report first. Known points for them and for the maintainer:

- **Flags render as a raw list** (`['tier:B', 'mech:cancer', ...]`) in the generic section. Owner: this repository's
  report, if it should change. **"Net weight 0.0"** came from the weight boxes not reading `manifest.weighting`; it is
  a report bug being fixed on main (review of 2026-11-19), not the module's.
- **No licence is stated** in `module_spec.yaml`; the sources' terms are in `licensing.csv`. The maintainer names
  one, or it ships without and says so.
- **APOE's ε-pair result is not called.** The module carries APOE as `haplotypes.csv` and `diplotypes.csv` (12 pair
  results), but the phenotype caller runs only on phenotype-led modules, and this one is weights-led: on the demo genome
  the report showed no APOE result (its two sites are not variant rows). Owner: this repository's engine (call a
  weights-led module's diplotypes too), or the module ships APOE as a separate phenotype module. Until one is done,
  2.0.0 shows less about APOE than 1.2.0, which scored rs429358 and rs7412 as rows.
- **Not closed.** The module carries no `close_module` stamp; closing marks authoring finished and is done once the
  text is final. Title and weighting are the v2 requirements' recommended defaults (`provenance.json`), not yet
  confirmed by the maintainer.

## 4. Registry (public)

A token that owns `just-dna-seq` is needed (`REGISTRY_TOKEN` and `REGISTRY_TOKEN_SANDBOX` do not). The rehearsal is
the same command against the polygon (`--url` of the `polygon` store, a test namespace and its token); it was run as
`test-longevity-loci/longevitymap@2.0.0` on 2026-11-16 (signature aebf5e38, the 164-locus build). This build (997b3356) is
not rehearsed yet; longevity-loci's module seat rehearses it before step 4.

```bash
uv run pipelines registry publish just-dna-seq longevitymap 2.0.0 data/modules/longevitymap_v2 \
  --changelog "2.0.0: re-curated from the evidence (172 loci, tiers A-D, no summed weights); supersedes the 1.2.0 port of HAGR's LongevityMap"
```

Every file in the spec directory travels, `quote_sources.csv` (the quotes the studies rest on) included.

## 5. HuggingFace collection (public)

In the same change, the display text: `module_metadata.longevitymap` in both `modules.yaml` files (the root and
`just-dna-pipelines/src/just_dna_pipelines/modules.yaml`) overrides the module's own title and description, and still
says "from LongevityMap database". Once 2.0.0 is the default it should read, for example, "Longevity-associated variants,
re-curated from the evidence and graded by tier (2.0.0; 1.2.0 is the frozen port of HAGR's LongevityMap)". It is not
changed by this pull request, because before the publish it would describe a module users cannot get yet.

Which title a user sees: `module_metadata` wins over the module's own `module_spec.yaml`, so the catalog and report
show "Longevity Map" / "Longevity Variants" from `modules.yaml`, not the spec's "Longevity genetics", until that block
is changed. Decide which name ships and make the two agree.

The HuggingFace publisher uploads and never deletes. Files of 1.2.0 that 2.0.0 does not carry (its `logo.png`, if
present) stay in `data/longevitymap/`; discovery reads what the new `manifest.json` attests, so a leftover file is
not read as part of 2.0.0, but delete it by hand if the folder should hold 2.0.0 alone.


```bash
uv run pipelines v1-port publish longevitymap --out data/interim/release --dry-run
uv run pipelines v1-port publish longevitymap --out data/interim/release
```

**This is the step that supersedes 1.2.0 for everyone.** It replaces 1.2.0 in place under the same name, so default
discovery hands every user 2.0.0 from then on; that is the intended effect of this release, and it is a decision,
not a side effect.

The dry run (2026-11-19) lists weights, annotations, studies, haplotypes, diplotypes, sources and manifest for
`just-dna-seq/annotators` at `data/longevitymap/`. After it, CI's annotate step (`.github/workflows/nix.yml`) and
`scripts/regression_snapshot.py compare` see 2.0.0 instead of 1.2.0; update their expectations in the same change.
