-- cleanco.db
-- OpenKiln cleanco skill schema v1
--
-- Caches cleaned company names to avoid re-calling the API
-- for names already processed.

-- ============================================================
-- CLEANED NAMES
-- One row per unique original company name.
-- Cache lookup: SELECT cleaned FROM cleaned_names WHERE original = ?
-- ============================================================

CREATE TABLE IF NOT EXISTS cleaned_names (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  original            TEXT    NOT NULL UNIQUE,
  cleaned             TEXT    NOT NULL,
  cleaned_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cleaned_names_original
  ON cleaned_names (original);
