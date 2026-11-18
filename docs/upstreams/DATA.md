# Upstream ledger: data sources

Kept by the correspondence seat (`docs/seats/CORRESPONDENCE.md`), as the liaison role's "A data source as
an upstream" says: a row per source the repository builds on. Opened on 2026-11-19; the release each
answers is not yet read from the caches, so that column starts empty and is filled at the first check.

| Source | Where it lives | Release in use |
|---|---|---|
| Ensembl variation snapshot | the enricher's `ensembl` lane | not yet read |
| Annotation modules | `just-dna-seq/annotators` on HuggingFace, ten modules, each with a `manifest.json` | not yet read |
| PGS Catalog scores and curation | `just-dna-seq/pgs-catalog`, pulled by just-prs | not yet read |
| GIAB low-mappability and segdup mask | fetched by `pipelines prepare-caches` | not yet read |
