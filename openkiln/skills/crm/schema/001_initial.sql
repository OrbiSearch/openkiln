-- crm.db
-- OpenKiln CRM skill schema v1
--
-- Owns contact and company data.
-- Both tables reference records.id in core.db.
-- Referential integrity enforced at application layer
-- (SQLite cannot enforce FK constraints across attached databases).
--
-- Column types map directly to Clay's field types:
-- Text, Number, Select (stored as TEXT), Boolean (0/1), URL, Email

-- ============================================================
-- CONTACTS
-- People records. Email is the natural key.
-- company_id optionally references companies.record_id
-- in this same database (not core.db).
-- ============================================================

CREATE TABLE IF NOT EXISTS contacts (
  -- core reference
  record_id           INTEGER NOT NULL UNIQUE,

  -- identity (Clay: Text, Email)
  first_name          TEXT,
  last_name           TEXT,
  full_name           TEXT,
  email               TEXT,
  phone               TEXT,
  linkedin_url        TEXT,

  -- company association
  company_name        TEXT,
  company_record_id   INTEGER,
  job_title           TEXT,
  department          TEXT,
  seniority           TEXT,

  -- location (Clay: Text)
  city                TEXT,
  country             TEXT,
  timezone            TEXT,

  -- categorisation (Clay: Select)
  segment             TEXT,
  tags                TEXT,

  -- scoring (Clay: Number)
  lead_score          REAL,

  -- metadata
  source              TEXT,
  created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_contacts_record_id
  ON contacts (record_id);

CREATE INDEX IF NOT EXISTS idx_contacts_email
  ON contacts (email);

CREATE INDEX IF NOT EXISTS idx_contacts_company_record_id
  ON contacts (company_record_id);

CREATE INDEX IF NOT EXISTS idx_contacts_segment
  ON contacts (segment);

-- ============================================================
-- COMPANIES
-- Organisation records. Domain is the natural key.
-- ============================================================

CREATE TABLE IF NOT EXISTS companies (
  -- core reference
  record_id           INTEGER NOT NULL UNIQUE,

  -- identity (Clay: Text, URL)
  name                TEXT,
  domain              TEXT,
  website_url         TEXT,
  linkedin_url        TEXT,

  -- firmographics (Clay: Text, Number, Select)
  industry            TEXT,
  employee_count      INTEGER,
  employee_range      TEXT,
  hq_city             TEXT,
  hq_country          TEXT,
  description         TEXT,

  -- categorisation (Clay: Select)
  segment             TEXT,
  tags                TEXT,

  -- scoring (Clay: Number)
  icp_score           REAL,

  -- metadata
  source              TEXT,
  created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
  updated_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_companies_record_id
  ON companies (record_id);

CREATE INDEX IF NOT EXISTS idx_companies_domain
  ON companies (domain);

CREATE INDEX IF NOT EXISTS idx_companies_segment
  ON companies (segment);
