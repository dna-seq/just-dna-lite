"""
Port Generation-I (OakVar postaggregator) annotation modules to the current just-dna-format.

The Gen-I modules live as ``just_*`` repos in the ``dna-seq`` GitHub org, each shipping a small
SQLite (or TSV/txt) data file curated by human geneticists. This package downloads those data
files, converts the **curated** weights/conclusions/studies into the authored DSL
(``module_spec.yaml`` + ``variants.csv`` + ``studies.csv``), fixes them to satisfy the
``just-dna-format`` 0.1.0 contract, and makes PMIDs digit-only (ROADMAP 0.2).

Core principle: curated ``weight`` values are copied **verbatim** — never recomputed. Only the
``state`` label (risk/protective/neutral) is taken from the curated weight's sign where the source
has no explicit risk direction, reproducing the v1 reporter's own ``get_color(weight)`` behavior.
"""
