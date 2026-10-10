# To investigate: single-score PRS may crash on haploid genotypes

Found on 2026-10-10 while validating Paper 1's description of the just-prs engines. It is not
reproduced in the app yet.

## What we know

- just-prs 0.10.1 (the version locked here) has two scoring engines. The **Polars** engine
  (`just_prs.prs.compute_prs`) raises `ComputeError: get index is out of bounds` on a haploid GT such
  as `"1"`, because `just_prs/vcf.py:238` splits the GT on `/` and reads index 1 without `null_on_oob`.
  The **DuckDB** engine scores the same row as dosage 1.
- Callers write haploid GTs on male chrX and on chrM. DRAGEN does; callers that write diploid
  genotypes everywhere do not.
- Our web UI computes a single score through the Polars path (`webui/src/webui/state.py`, around line
  3977, `_compute_prs_fn`). Batch and trait paths may use DuckDB (prs-ui's mixin defaults to DuckDB);
  which entry points are exposed is still to be checked.

## To check

1. Take a VCF that has haploid GTs (check first: count GT fields without `/` or `|` per contig; DRAGEN
   output from a male sample on chrX, or chrM from callers that write it haploid) and a PGS ID whose
   scoring file includes loci on that contig. Compute it from the single-score UI path and from the
   batch path. No such VCF is on this machine right now; the public genomes in `modules.yaml` are
   candidates to check, not known cases.
2. If it crashes, decide the fix upstream in just-prs. The two engines also disagree, so the fix is
   choosing hemizygous dosage semantics and making both engines follow them. The note is filed in
   the just-prs checkout as `docs/investigate-from-just-dna-lite-2026-10-10.md`. Meanwhile, consider
   whether the UI should call the DuckDB engine, which does not crash. Do not patch just-prs from
   here (CLAUDE.md: file upstream gaps, no workarounds for another repo's defect).
3. Add a regression test here once a fixed just-prs is published.

## Update 2026-10-11: fixed upstream in just-prs 0.10.2 (not yet on PyPI)

just-prs 0.10.2 (tag v0.10.2, commit f15dd7b) scores a haploid GT as homozygous on the 0..2 scale in
both engines, matching PLINK2's default `--xchr-model 2` and the 1000G reference distributions; male
chrX `1/1` stays 2. It does no sex inference. Once 0.10.2 is on PyPI, pin `just-prs>=0.10.2` here, add
the regression test (step 3 above) and close this note.

0.10.2 also changes just-prs's own `normalize_vcf`: its `genotype` list column now gives `[a, a]` for a
haploid GT, where it used to give `[]`. just-dna-lite does not call `normalize_vcf`, since annotation reads
its own `user_vcf_normalized` parquet, so annotation is unaffected. Only just-prs's cached normalized
parquets carry the old value until re-normalized.
