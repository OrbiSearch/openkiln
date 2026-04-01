# core/workflow.py
#
# Workflow engine.
# Parses a workflow YAML definition and executes it as a pipeline:
#   Source -> Transform(s) -> Filter -> Sink(s)
#
# The engine discovers skill implementations via skill.toml manifests
# and instantiates Source/Transform/Sink classes at runtime.

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openkiln import config, db
from openkiln.core.source import Source
from openkiln.core.transform import Transform
from openkiln.core.sink import Sink


# ── Workflow Definition ──────────────────────────────────────


@dataclass
class WorkflowDef:
    """Parsed workflow YAML."""
    name: str
    version: str = "1.0.0"
    author: str = ""
    requires: list[str] = field(default_factory=list)
    source: dict = field(default_factory=dict)
    transforms: list[str] = field(default_factory=list)
    filter: dict = field(default_factory=dict)
    sinks: list[dict] = field(default_factory=list)
    file_path: str | None = None


def parse_workflow(file_path: Path) -> WorkflowDef:
    """Parse a workflow YAML file into a WorkflowDef."""
    try:
        import yaml
    except ImportError:
        raise RuntimeError(
            "PyYAML is required for workflows. "
            "Install it: pip install pyyaml"
        )

    content = file_path.read_text()
    data = yaml.safe_load(content)

    if not isinstance(data, dict):
        raise ValueError(f"Workflow file must be a YAML mapping: {file_path}")

    return WorkflowDef(
        name=data.get("name", file_path.stem),
        version=data.get("version", "1.0.0"),
        author=data.get("author", ""),
        requires=data.get("requires", []),
        source=data.get("source", {}),
        transforms=data.get("transforms", []),
        filter=data.get("filter", {}),
        sinks=data.get("sinks", []),
        file_path=str(file_path),
    )


# ── Skill Discovery ─────────────────────────────────────────


def _load_skill_toml(skill_name: str) -> dict:
    """Load a skill's skill.toml manifest."""
    import tomllib

    toml_path = (
        Path(__file__).parent.parent / "skills" / skill_name / "skill.toml"
    )
    if not toml_path.exists():
        raise RuntimeError(
            f"skill.toml not found for skill '{skill_name}': {toml_path}"
        )

    with open(toml_path, "rb") as f:
        return tomllib.load(f)


def _find_provider(
    skill_name: str,
    capability_name: str,
    capability_type: str,
) -> type:
    """
    Find and return the class implementing a workflow capability.

    Looks up the module and class from skill.toml's [[skill.provides]]
    entries. Returns the class (not an instance).
    """
    manifest = _load_skill_toml(skill_name)
    provides = manifest.get("skill", {}).get("provides", [])

    for entry in provides:
        if entry.get("name") == capability_name and entry.get("type") == capability_type:
            module_path = entry.get("module")
            class_name = entry.get("class")

            if not module_path or not class_name:
                raise RuntimeError(
                    f"skill.toml for '{skill_name}' declares "
                    f"'{capability_name}' but missing module/class fields"
                )

            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name, None)
            if cls is None:
                raise RuntimeError(
                    f"Class '{class_name}' not found in module '{module_path}'"
                )
            return cls

    raise RuntimeError(
        f"Skill '{skill_name}' does not provide "
        f"{capability_type} '{capability_name}'"
    )


# ── Validation ───────────────────────────────────────────────


def validate_workflow(wf: WorkflowDef) -> list[str]:
    """
    Validate a workflow definition. Returns a list of errors.
    Empty list = valid.
    """
    errors: list[str] = []

    # check source
    if not wf.source:
        errors.append("Workflow has no source defined.")
    elif not wf.source.get("skill"):
        errors.append("Source must specify a skill.")

    # check sinks
    if not wf.sinks:
        errors.append("Workflow has no sinks defined.")
    for i, sink in enumerate(wf.sinks):
        if not sink.get("skill"):
            errors.append(f"Sink {i + 1} must specify a skill.")

    # check required skills are installed
    if db.check_connection():
        with db.connection() as conn:
            installed = {
                row["skill_name"]
                for row in conn.execute(
                    "SELECT skill_name FROM installed_skills"
                ).fetchall()
            }
        for skill_name in wf.requires:
            if skill_name not in installed:
                errors.append(
                    f"Required skill '{skill_name}' is not installed. "
                    f"Run: openkiln skill install {skill_name}"
                )

    # check source skill provides the declared capability
    if wf.source and wf.source.get("skill"):
        source_skill = wf.source["skill"]
        source_type = wf.source.get("type", "contacts")
        capability_name = f"{source_skill}.{source_type}"
        try:
            _find_provider(source_skill, capability_name, "source")
        except RuntimeError as e:
            errors.append(str(e))

    # check transforms
    for transform_name in wf.transforms:
        parts = transform_name.split(".", 1)
        if len(parts) != 2:
            errors.append(
                f"Transform '{transform_name}' must be in format "
                "'skill.capability' (e.g. orbisearch.validate)"
            )
            continue
        try:
            _find_provider(parts[0], transform_name, "transform")
        except RuntimeError as e:
            errors.append(str(e))

    # check sinks
    for sink in wf.sinks:
        sink_skill = sink.get("skill", "")
        sink_action = sink.get("action", "")
        capability_name = f"{sink_skill}.{sink_action}"
        try:
            _find_provider(sink_skill, capability_name, "sink")
        except RuntimeError as e:
            errors.append(str(e))

    return errors


# ── Execution ────────────────────────────────────────────────


@dataclass
class WorkflowResult:
    """Result of a workflow run."""
    workflow_name: str
    status: str = "pending"  # pending, running, complete, failed
    records_in: int = 0
    records_out: int = 0
    error: str | None = None
    sink_results: list[dict] = field(default_factory=list)


def run_workflow(wf: WorkflowDef, *, dry_run: bool = True) -> WorkflowResult:
    """
    Execute a workflow pipeline.

    1. Read rows from source
    2. Apply transforms sequentially
    3. Apply post-transform filter
    4. Write surviving rows to each sink

    If dry_run=True, sources are read and transforms applied but
    sinks receive an empty list (no writes).
    """
    result = WorkflowResult(workflow_name=wf.name)

    # record the run
    run_id = None
    if not dry_run and db.check_connection():
        with db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO workflow_runs "
                "(workflow_name, workflow_file, status) VALUES (?, ?, 'running')",
                (wf.name, wf.file_path),
            )
            run_id = cursor.lastrowid

    try:
        # ── Source ────────────────────────────────────────
        source_skill = wf.source["skill"]
        source_type = wf.source.get("type", "contacts")
        capability_name = f"{source_skill}.{source_type}"

        source_cls = _find_provider(source_skill, capability_name, "source")
        source: Source = source_cls()

        source_config = dict(wf.source)
        source_config.pop("skill", None)

        rows: list[dict] = list(source.read(**source_config))
        result.records_in = len(rows)

        # ── Transforms ───────────────────────────────────
        for transform_name in wf.transforms:
            parts = transform_name.split(".", 1)
            transform_cls = _find_provider(parts[0], transform_name, "transform")
            transform: Transform = transform_cls()

            transformed: list[dict] = []
            for row in rows:
                out = transform.apply(row)
                if out is not None:
                    transformed.append(out)
            rows = transformed

        # ── Filter ───────────────────────────────────────
        if wf.filter:
            filtered: list[dict] = []
            for row in rows:
                match = True
                for key, expected in wf.filter.items():
                    if str(row.get(key, "")) != str(expected):
                        match = False
                        break
                if match:
                    filtered.append(row)
            rows = filtered

        result.records_out = len(rows)

        # ── Sinks ────────────────────────────────────────
        if dry_run:
            result.status = "complete"
            result.sink_results = [
                {"skill": s.get("skill"), "action": s.get("action"),
                 "would_write": len(rows)}
                for s in wf.sinks
            ]
        else:
            for sink_def in wf.sinks:
                sink_skill = sink_def["skill"]
                sink_action = sink_def.get("action", "")
                capability_name = f"{sink_skill}.{sink_action}"

                sink_cls = _find_provider(sink_skill, capability_name, "sink")
                sink: Sink = sink_cls()

                sink_config = dict(sink_def)
                sink_config.pop("skill", None)

                sink_result = sink.write(rows, **sink_config)
                result.sink_results.append({
                    "skill": sink_skill,
                    "action": sink_action,
                    **sink_result,
                })

            result.status = "complete"

    except Exception as e:
        result.status = "failed"
        result.error = str(e)

    # update workflow run record
    if run_id is not None and db.check_connection():
        with db.transaction() as conn:
            conn.execute(
                "UPDATE workflow_runs SET status = ?, records_in = ?, "
                "records_out = ?, error = ?, completed_at = datetime('now') "
                "WHERE id = ?",
                (result.status, result.records_in, result.records_out,
                 result.error, run_id),
            )

    return result
