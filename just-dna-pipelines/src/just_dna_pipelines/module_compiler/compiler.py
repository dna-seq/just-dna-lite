"""
Compatibility shim — the reference compiler now lives in ``just-dna-compiler``.

``validate_spec`` / ``compile_module`` / ``reverse_module`` were extracted verbatim to
``just_dna_compiler.compiler`` so the transform is shared by just-dna-pipelines,
just-dna-registry, and just-dna-agents. Import sites inside this repo keep working via these
re-exports; new code should import from ``just_dna_compiler.compiler`` directly.

Ensembl resolution differs by design: ``just-dna-compiler`` is inject-only (it never downloads a
reference), whereas this repo can provision the Ensembl DuckDB. That provisioning glue lives in
``just_dna_pipelines.module_compiler.resolver`` (``ensure_resolver_db`` + a ``resolve_variants``
wrapper). ``compile_module`` here is the library function; pass ``ensembl_cache`` (or have the
default cache present) for it to resolve — it will not auto-download mid-compile.
See just-dna-format/docs/{CHANGELOG,ROADMAP}.md.
"""

from just_dna_compiler.compiler import compile_module, reverse_module, validate_spec

__all__ = ["compile_module", "reverse_module", "validate_spec"]
