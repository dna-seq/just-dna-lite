# To investigate: the web UI treats every sample as GRCh38

Found on 2026-10-10 by a validator checking Paper 1's input-format claims (code reading only; not
reproduced in a running app).

## What the code does

- `webui/src/webui/state.py:4713` sets `self.genome_build = "GRCh38"` on every file load. No UI control
  calls `set_prs_genome_build` (`state.py:4773`), and the sample badge is a static "GRCh38"
  (`webui/src/webui/pages/annotate.py:3125`).
- **PRS:** `state.py:4965` passes `sample_build=genome_build`, so just-prs's build-mismatch guard
  (`prs.py:699-721`) never fires. A GRCh37 sample is scored with GRCh38 positions, although the library
  supports GRCh37 through the Catalog's harmonized files (`prs_catalog.py:64-67`).
- **Ancestry:** `detect_sample_ancestry` passes the same `sample_build`; the library would lift a GRCh37
  sample to each panel's build (`prs_catalog.py:957-965`) but is never told the sample is GRCh37.
- **Annotation:** no build check exists in the pipeline; `reference_genome` is recorded as metadata only
  (`hf_logic.py:955`). The upload form warns only when the VCF header's build differs from the dropdown
  (`state.py:788-797`). A GRCh37 VCF is position-joined against GRCh38 module coordinates, so results
  are silently wrong or empty.
- **Docs disagree:** `README.md:122` and `docs/FAQ.md:33` say GRCh37 "can be lifted" or is "handled
  through liftover"; no VCF liftover exists (CLAUDE.md, "Writing preferences").
- **T2T:** `REFERENCE_GENOMES` lists `T2T-CHM13v2.0` (`state.py:149`); it is handled as GRCh38, with
  no T2T-specific processing.

## To check and decide

1. Upload a known GRCh37 VCF and confirm the behaviour above.
2. Carry the detected or selected build into `PRSState.genome_build` and the ancestry call, so the
   library's GRCh37 paths are used.
3. Refuse or prominently warn when annotation runs on a non-GRCh38 sample, rather than joining
   silently.
4. Fix README.md and docs/FAQ.md, which say "lifted". Paper 1 states the GRCh38-only status (N1, N2).
