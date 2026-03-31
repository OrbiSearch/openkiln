-- orbisearch.db
-- OpenKiln OrbiSearch skill schema v1
--
-- Owns email verification results from the OrbiSearch API.
-- Schema maps 1:1 to EmailVerificationResponse in OrbiSearch
-- Public API v1 (frozen — these fields will not change).
-- References records.id in core.db.
--
-- API: https://api.orbisearch.com
-- API v1 response schema is frozen per OrbiSearch spec.
--
-- Two verification modes supported:
--   single  — /v1/verify  (real-time, one email)
--   bulk    — /v1/bulk    (async job, many emails)
-- Both write to the same verification_results table.

-- ============================================================
-- VERIFICATION RESULTS
-- One row per verified email per record.
-- Maps directly to EmailVerificationResponse schema.
--
-- status values (from API spec):
--   safe     — deliverable
--   risky    — uncertain (e.g. catch-all domain)
--   invalid  — undeliverable
--   unknown  — verification failed
--
-- substatus values (from API spec):
--   catch_all, disposable, role_account, invalid_syntax
-- ============================================================

CREATE TABLE IF NOT EXISTS verification_results (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,

  -- core reference
  record_id           INTEGER NOT NULL,

  -- exactly as returned by OrbiSearch API v1
  email               TEXT    NOT NULL,
  status              TEXT    NOT NULL,
  substatus           TEXT,
  explanation         TEXT    NOT NULL,
  email_provider      TEXT    NOT NULL,
  is_disposable       INTEGER,
  is_role_account     INTEGER,
  is_free             INTEGER,

  -- verification metadata
  verified_via        TEXT    NOT NULL DEFAULT 'single',
  bulk_job_id         TEXT,
  verified_at         TEXT    NOT NULL DEFAULT (datetime('now')),
  api_version         TEXT    NOT NULL DEFAULT 'v1',

  -- full raw response preserved for debugging and reprocessing
  raw_response        TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_verification_results_record_id
  ON verification_results (record_id);

CREATE INDEX IF NOT EXISTS idx_verification_results_email
  ON verification_results (email);

CREATE INDEX IF NOT EXISTS idx_verification_results_status
  ON verification_results (status);

CREATE INDEX IF NOT EXISTS idx_verification_results_verified_at
  ON verification_results (verified_at);

-- ============================================================
-- BULK JOBS
-- Tracks async bulk verification jobs submitted to OrbiSearch.
-- One row per /v1/bulk submission.
--
-- job_status values (from API spec):
--   pending, in_progress, partial_complete_retrying,
--   complete, failed
--
-- retry_status values (from API spec):
--   none, pending, partial, complete
-- ============================================================

CREATE TABLE IF NOT EXISTS bulk_jobs (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,

  -- OrbiSearch job identifiers
  job_id              TEXT    NOT NULL UNIQUE,
  job_status          TEXT    NOT NULL DEFAULT 'pending',
  retry_status        TEXT    NOT NULL DEFAULT 'none',

  -- progress
  total_emails        INTEGER NOT NULL,
  emails_processed    INTEGER NOT NULL DEFAULT 0,

  -- cost tracking
  estimated_cost      REAL,

  -- timestamps from API
  submitted_at        TEXT    NOT NULL DEFAULT (datetime('now')),
  completed_at        TEXT,

  -- openkiln metadata
  workflow_run_id     INTEGER,
  created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_bulk_jobs_job_id
  ON bulk_jobs (job_id);

CREATE INDEX IF NOT EXISTS idx_bulk_jobs_job_status
  ON bulk_jobs (job_status);
