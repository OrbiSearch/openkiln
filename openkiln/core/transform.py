# core/transform.py
#
# Transform base class.
# A Transform takes rows and produces modified rows.
# Subclasses implement .apply(row) -> Row.
# Transforms can be chained in a pipeline.
