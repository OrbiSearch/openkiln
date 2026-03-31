-- crm schema migration 003
-- Adds lifecycle_stage, lead_status, icp_tier to contacts/companies.
-- Adds lists and list_members tables.
-- segment column is deprecated but kept for backwards compatibility.

-- contacts: add lifecycle and status fields
ALTER TABLE contacts ADD COLUMN lifecycle_stage TEXT;
ALTER TABLE contacts ADD COLUMN lead_status     TEXT;

-- companies: add lifecycle and ICP tier fields
ALTER TABLE companies ADD COLUMN lifecycle_stage TEXT;
ALTER TABLE companies ADD COLUMN icp_tier        TEXT;

-- ============================================================
-- LISTS
-- Named collections of records for campaign targeting.
-- A list contains record_ids from core.db records table.
-- Any record type can be a list member.
-- type: static (manually managed) — dynamic lists are v2
-- ============================================================

CREATE TABLE IF NOT EXISTS lists (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name        TEXT    NOT NULL UNIQUE,
  description TEXT,
  type        TEXT    NOT NULL DEFAULT 'static',
  created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS list_members (
  list_id    INTEGER NOT NULL REFERENCES lists(id),
  record_id  INTEGER NOT NULL,
  added_at   TEXT    NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (list_id, record_id)
);

CREATE INDEX IF NOT EXISTS idx_list_members_list_id
  ON list_members (list_id);

CREATE INDEX IF NOT EXISTS idx_list_members_record_id
  ON list_members (record_id);
