# core/workflow.py
#
# Workflow runner.
# Parses a workflow YAML definition and executes it
# as a pipeline: Source -> Transform(s) -> Sink.
# Handles logging, error recovery, and dry-run mode.
