"""
Tests for the workflow engine and interfaces.

Covers: interface contracts, engine parsing, validation, execution
with mock source/transform/sink, CLI commands.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from typer.testing import CliRunner

from openkiln import db
from openkiln.cli import app
from openkiln.core import Sink, Source, Transform
from openkiln.core.workflow import (
    WorkflowDef,
    parse_workflow,
    run_workflow,
    validate_workflow,
)

runner = CliRunner()


# ── Interface Tests ──────────────────────────────────────────


def test_source_is_abstract():
    """Source cannot be instantiated directly."""
    import pytest

    with pytest.raises(TypeError):
        Source()  # type: ignore[abstract]


def test_transform_is_abstract():
    """Transform cannot be instantiated directly."""
    import pytest

    with pytest.raises(TypeError):
        Transform()  # type: ignore[abstract]


def test_sink_is_abstract():
    """Sink cannot be instantiated directly."""
    import pytest

    with pytest.raises(TypeError):
        Sink()  # type: ignore[abstract]


def test_source_subclass():
    """A Source subclass can be instantiated."""

    class TestSource(Source):
        def read(self, **config):
            yield {"record_id": 1, "email": "a@b.com"}

    src = TestSource()
    rows = list(src.read())
    assert len(rows) == 1
    assert rows[0]["email"] == "a@b.com"


def test_transform_subclass():
    """A Transform subclass can process rows."""

    class TestTransform(Transform):
        def apply(self, row):
            row["processed"] = True
            return row

    t = TestTransform()
    out = t.apply({"email": "a@b.com"})
    assert out["processed"] is True


def test_transform_can_drop_rows():
    """A Transform can return None to drop a row."""

    class DropAll(Transform):
        def apply(self, row):
            return None

    t = DropAll()
    assert t.apply({"email": "a@b.com"}) is None


def test_sink_subclass():
    """A Sink subclass can write rows."""

    class TestSink(Sink):
        def __init__(self):
            self.written = []

        def write(self, rows, **config):
            self.written.extend(rows)
            return {"written": len(rows)}

    s = TestSink()
    result = s.write([{"email": "a@b.com"}])
    assert result["written"] == 1
    assert len(s.written) == 1


# ── CRM Interface Tests ─────────────────────────────────────


def test_crm_source_implements_interface():
    """CrmSource is a valid Source subclass."""
    from openkiln.skills.crm.workflow import CrmSource

    assert issubclass(CrmSource, Source)


def test_crm_sink_implements_interface():
    """CrmSink is a valid Sink subclass."""
    from openkiln.skills.crm.workflow import CrmSink

    assert issubclass(CrmSink, Sink)


def test_orbisearch_transform_implements_interface():
    """OrbiSearchTransform is a valid Transform subclass."""
    from openkiln.skills.orbisearch.workflow import OrbiSearchTransform

    assert issubclass(OrbiSearchTransform, Transform)


def test_smartlead_sink_implements_interface():
    """SmartleadSink is a valid Sink subclass."""
    from openkiln.skills.smartlead.workflow import SmartleadSink

    assert issubclass(SmartleadSink, Sink)


# ── Parser Tests ─────────────────────────────────────────────


def test_parse_workflow():
    """parse_workflow reads YAML correctly."""
    with tempfile.NamedTemporaryFile(suffix=".yml", mode="w", delete=False) as f:
        f.write("""
name: test-flow
version: "2.0.0"
requires:
  - crm
source:
  skill: crm
  type: contacts
transforms:
  - orbisearch.validate
filter:
  status: safe
sinks:
  - skill: crm
    action: update
""")
        f.flush()
        wf = parse_workflow(Path(f.name))

    assert wf.name == "test-flow"
    assert wf.version == "2.0.0"
    assert wf.requires == ["crm"]
    assert wf.source["skill"] == "crm"
    assert wf.transforms == ["orbisearch.validate"]
    assert wf.filter == {"status": "safe"}
    assert len(wf.sinks) == 1


# ── Validation Tests ─────────────────────────────────────────


def test_validate_empty_source():
    """Validation catches missing source."""
    wf = WorkflowDef(name="bad", source={}, sinks=[{"skill": "crm", "action": "update"}])
    errors = validate_workflow(wf)
    assert any("source" in e.lower() for e in errors)


def test_validate_empty_sinks():
    """Validation catches missing sinks."""
    wf = WorkflowDef(name="bad", source={"skill": "crm", "type": "contacts"}, sinks=[])
    errors = validate_workflow(wf)
    assert any("sink" in e.lower() for e in errors)


def test_validate_missing_skill(openkiln_home):
    """Validation catches uninstalled required skill."""
    runner.invoke(app, ["init"])
    wf = WorkflowDef(
        name="bad",
        requires=["nonexistent_skill"],
        source={"skill": "crm", "type": "contacts"},
        sinks=[{"skill": "crm", "action": "update"}],
    )
    errors = validate_workflow(wf)
    assert any("nonexistent_skill" in e for e in errors)


# ── Engine Tests ─────────────────────────────────────────────


def test_run_workflow_dry_run(openkiln_home):
    """Dry run reads source but doesn't write to sinks."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "crm"])

    # insert a test contact
    with db.transaction(attach_skills=["crm"]) as conn:
        cursor = conn.execute("INSERT INTO records (type, record_status) VALUES ('contact', 'active')")
        rid = cursor.lastrowid
        conn.execute(
            "INSERT INTO crm.contacts (record_id, email, first_name) "
            "VALUES (?, 'test@example.com', 'Test')",
            (rid,),
        )

    wf = WorkflowDef(
        name="test-dry",
        source={"skill": "crm", "type": "contacts"},
        transforms=[],
        filter={},
        sinks=[{"skill": "crm", "action": "update"}],
    )

    result = run_workflow(wf, dry_run=True)
    assert result.status == "complete"
    assert result.records_in >= 1
    assert result.records_out >= 1
    assert result.sink_results[0]["would_write"] >= 1


def test_run_workflow_apply(openkiln_home):
    """Apply mode writes to sinks and records the run."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "crm"])

    # insert a test contact
    with db.transaction(attach_skills=["crm"]) as conn:
        cursor = conn.execute("INSERT INTO records (type, record_status) VALUES ('contact', 'active')")
        rid = cursor.lastrowid
        conn.execute(
            "INSERT INTO crm.contacts (record_id, email, first_name, country) "
            "VALUES (?, 'test@example.com', 'Test', 'US')",
            (rid,),
        )

    wf = WorkflowDef(
        name="test-apply",
        source={"skill": "crm", "type": "contacts"},
        transforms=[],
        filter={},
        sinks=[{"skill": "crm", "action": "update"}],
    )

    result = run_workflow(wf, dry_run=False)
    assert result.status == "complete"
    assert result.records_in >= 1

    # check workflow run was recorded
    with db.connection() as conn:
        run = conn.execute("SELECT * FROM workflow_runs WHERE workflow_name = 'test-apply'").fetchone()
    assert run is not None
    assert run["status"] == "complete"


def test_run_workflow_filter(openkiln_home):
    """Filter drops rows that don't match."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "crm"])

    # insert contacts with different countries
    with db.transaction(attach_skills=["crm"]) as conn:
        for email, country in [("a@test.com", "US"), ("b@test.com", "UK")]:
            cursor = conn.execute(
                "INSERT INTO records (type, record_status) VALUES ('contact', 'active')"
            )
            rid = cursor.lastrowid
            conn.execute(
                "INSERT INTO crm.contacts (record_id, email, country) VALUES (?, ?, ?)",
                (rid, email, country),
            )

    wf = WorkflowDef(
        name="test-filter",
        source={"skill": "crm", "type": "contacts"},
        transforms=[],
        filter={"country": "US"},
        sinks=[{"skill": "crm", "action": "update"}],
    )

    result = run_workflow(wf, dry_run=True)
    assert result.records_in == 2
    assert result.records_out == 1  # only US


# ── CLI Tests ────────────────────────────────────────────────


def test_workflow_validate_command(openkiln_home):
    """workflow validate command works."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "crm"])

    with tempfile.NamedTemporaryFile(suffix=".yml", mode="w", delete=False) as f:
        f.write("""
name: test-validate
source:
  skill: crm
  type: contacts
sinks:
  - skill: crm
    action: update
""")
        f.flush()
        result = runner.invoke(app, ["workflow", "validate", f.name])

    assert result.exit_code == 0
    assert "valid" in result.output.lower()


def test_workflow_run_command_dry(openkiln_home):
    """workflow run command works in dry-run mode."""
    runner.invoke(app, ["init"])
    runner.invoke(app, ["skill", "install", "crm"])

    with tempfile.NamedTemporaryFile(suffix=".yml", mode="w", delete=False) as f:
        f.write("""
name: test-run-dry
source:
  skill: crm
  type: contacts
sinks:
  - skill: crm
    action: update
""")
        f.flush()
        result = runner.invoke(app, ["workflow", "run", f.name])

    assert result.exit_code == 0
    assert "Dry run" in result.output


def test_workflow_history_command(openkiln_home):
    """workflow history command works."""
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["workflow", "history"])
    assert result.exit_code == 0
