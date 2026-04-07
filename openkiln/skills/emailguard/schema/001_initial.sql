-- emailguard.db
-- OpenKiln EmailGuard skill schema v1
--
-- Tracks inbox placement tests and their results.
-- API: https://app.emailguard.io

-- ============================================================
-- PLACEMENT TESTS
-- One row per EmailGuard test.
-- ============================================================

CREATE TABLE IF NOT EXISTS placement_tests (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  test_uuid           TEXT    NOT NULL UNIQUE,
  name                TEXT    NOT NULL,
  status              TEXT    NOT NULL DEFAULT 'created',
  overall_score       REAL,
  filter_phrase       TEXT    NOT NULL,

  gmail_seed_count    INTEGER NOT NULL DEFAULT 0,
  msft_seed_count     INTEGER NOT NULL DEFAULT 0,

  created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
  completed_at        TEXT,
  synced_at           TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_placement_tests_uuid
  ON placement_tests (test_uuid);

CREATE INDEX IF NOT EXISTS idx_placement_tests_status
  ON placement_tests (status);

-- ============================================================
-- SEED RESULTS
-- One row per seed email per test.
-- Records whether each seed received the email in Inbox or Spam.
-- ============================================================

CREATE TABLE IF NOT EXISTS seed_results (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  test_uuid           TEXT    NOT NULL,
  seed_email          TEXT    NOT NULL,
  provider            TEXT    NOT NULL,   -- Google, Microsoft
  sender_email        TEXT,               -- which account sent to this seed
  status              TEXT    NOT NULL DEFAULT 'waiting_for_email',
  folder              TEXT,               -- Inbox, Spam, Junk, null

  synced_at           TEXT    NOT NULL DEFAULT (datetime('now')),

  UNIQUE(test_uuid, seed_email)
);

CREATE INDEX IF NOT EXISTS idx_seed_results_test_uuid
  ON seed_results (test_uuid);

-- ============================================================
-- ACCOUNT SCORES
-- Historical deliverability scores per sending account.
-- Aggregated from seed_results after each test completes.
-- Enables tracking deliverability trends over time.
-- ============================================================

CREATE TABLE IF NOT EXISTS account_scores (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  test_uuid           TEXT    NOT NULL,
  account_email       TEXT    NOT NULL,
  domain              TEXT    NOT NULL,

  total_seeds         INTEGER NOT NULL DEFAULT 0,
  inbox_count         INTEGER NOT NULL DEFAULT 0,
  spam_count          INTEGER NOT NULL DEFAULT 0,
  inbox_rate          REAL,               -- inbox_count / total_seeds

  gmail_inbox         INTEGER NOT NULL DEFAULT 0,
  gmail_spam          INTEGER NOT NULL DEFAULT 0,
  msft_inbox          INTEGER NOT NULL DEFAULT 0,
  msft_spam           INTEGER NOT NULL DEFAULT 0,

  tested_at           TEXT    NOT NULL DEFAULT (datetime('now')),

  UNIQUE(test_uuid, account_email)
);

CREATE INDEX IF NOT EXISTS idx_account_scores_account_email
  ON account_scores (account_email);

CREATE INDEX IF NOT EXISTS idx_account_scores_domain
  ON account_scores (domain);

CREATE INDEX IF NOT EXISTS idx_account_scores_tested_at
  ON account_scores (tested_at);
