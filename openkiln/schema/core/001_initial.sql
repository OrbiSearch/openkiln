-- core.db
-- OpenKiln core schema v1
--
-- Owns only what the engine itself needs.
-- No domain knowledge. No skill-specific fields.
-- Skills reference records.id but never modify this schema.
--
-- Migrations run automatically on CLI startup.
-- Users never run migrations manually.

-- ============================================================
-- RECORDS
-- Universal ID anchor. Every skill references this table.
-- type is free text, user-defined (contact, company, investor)
-- record_status: active, archived
-- Nothing is deleted — archived_at marks inactive rows.
-- ============================================================

CREATE TABLE IF NOT EXISTS records (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  type            TEXT    NOT NULL,
  record_status   TEXT    NOT NULL DEFAULT 'active',
  created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_records_type
  ON records (type);

CREATE INDEX IF NOT EXISTS idx_records_type_status
  ON records (type, record_status);

-- ============================================================
-- WORKFLOW RUNS
-- Execution log owned by the engine.
-- One row per workflow run.
-- status: pending, running, complete, failed
-- ============================================================

CREATE TABLE IF NOT EXISTS workflow_runs (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  workflow_name   TEXT    NOT NULL,
  workflow_file   TEXT,
  status          TEXT    NOT NULL DEFAULT 'pending',
  records_in      INTEGER,
  records_out     INTEGER,
  error           TEXT,
  started_at      TEXT    NOT NULL DEFAULT (datetime('now')),
  completed_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_name
  ON workflow_runs (workflow_name);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_status
  ON workflow_runs (status);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_started_at
  ON workflow_runs (started_at);

-- ============================================================
-- INSTALLED SKILLS
-- Registry of installed skills and their database paths.
-- Engine reads this on startup to attach skill databases
-- and run pending migrations.
-- ============================================================

CREATE TABLE IF NOT EXISTS installed_skills (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  skill_name      TEXT    NOT NULL UNIQUE,
  skill_version   TEXT    NOT NULL,
  db_path         TEXT    NOT NULL,
  installed_at    TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);
