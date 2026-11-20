"""Genome prediction models run on a sample: variant-effect scoring with sequence-to-function models.

``models`` lists the models (one entry each), ``download`` fetches their files, ``reference`` reads
the GRCh38 sequence around a variant, ``variants`` picks which variants to score, ``scoring`` runs the
ONNX graph, ``report`` renders the separate HTML report, and ``assets`` wires it into Dagster.
"""
