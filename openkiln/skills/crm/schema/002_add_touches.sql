-- crm schema migration 002
-- Adds touches table and last_contacted_at to contacts and companies.
-- Touches are owned by the CRM skill — not a separate skill.

ALTER TABLE contacts ADD COLUMN last_contacted_at TEXT;
ALTER TABLE companies ADD COLUMN last_contacted_at TEXT;

-- ============================================================
-- TOUCHES
-- Every interaction logged against a contact or company.
-- record_id references records.id in core.db.
-- channel: email, linkedin, phone, in_person, other
-- direction: outbound, inbound
-- ============================================================

CREATE TABLE IF NOT EXISTS touches (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  record_id         INTEGER NOT NULL,
  channel           TEXT    NOT NULL DEFAULT 'email',
  direction         TEXT    NOT NULL DEFAULT 'outbound',
  note              TEXT,
  campaign_id       TEXT,
  touched_at        TEXT    NOT NULL DEFAULT (datetime('now')),
  metadata          TEXT    NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_touches_record_id
  ON touches (record_id);

CREATE INDEX IF NOT EXISTS idx_touches_touched_at
  ON touches (touched_at);

CREATE INDEX IF NOT EXISTS idx_touches_channel
  ON touches (channel);
