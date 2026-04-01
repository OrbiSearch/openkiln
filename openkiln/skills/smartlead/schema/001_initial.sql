-- smartlead.db
-- OpenKiln Smartlead skill schema v1
--
-- Tracks campaigns synced from Smartlead, lead pushes from CRM,
-- and campaign engagement statistics.
-- References records.id in core.db for lead_pushes.
--
-- API: https://server.smartlead.ai/api/v1

-- ============================================================
-- CAMPAIGNS
-- Local cache of Smartlead campaign metadata.
-- Populated by `openkiln smartlead sync`.
-- ============================================================

CREATE TABLE IF NOT EXISTS campaigns (
  id                  INTEGER PRIMARY KEY,     -- Smartlead campaign ID
  name                TEXT    NOT NULL,
  status              TEXT,                     -- DRAFTED, ACTIVE, PAUSED, STOPPED, ARCHIVED
  client_id           INTEGER,

  -- schedule
  timezone            TEXT,
  days_of_the_week    TEXT,                     -- JSON array e.g. [1,2,3,4,5]
  start_hour          TEXT,
  end_hour            TEXT,
  max_leads_per_day   INTEGER,

  -- metadata
  created_at          TEXT,                     -- from Smartlead
  synced_at           TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- CAMPAIGN_STATS
-- Snapshot of campaign-level analytics at a point in time.
-- Each sync appends a new row so we can track trends.
-- ============================================================

CREATE TABLE IF NOT EXISTS campaign_stats (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  campaign_id         INTEGER NOT NULL,

  -- counts
  total_leads         INTEGER,
  leads_contacted     INTEGER,
  leads_not_started   INTEGER,
  leads_in_progress   INTEGER,
  leads_completed     INTEGER,

  -- engagement
  sent_count          INTEGER,
  open_count          INTEGER,
  unique_open_count   INTEGER,
  click_count         INTEGER,
  unique_click_count  INTEGER,
  reply_count         INTEGER,
  bounce_count        INTEGER,
  unsubscribe_count   INTEGER,

  -- category breakdown
  interested_count    INTEGER,
  not_interested_count INTEGER,

  -- metadata
  synced_at           TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_campaign_stats_campaign_id
  ON campaign_stats (campaign_id);

CREATE INDEX IF NOT EXISTS idx_campaign_stats_synced_at
  ON campaign_stats (synced_at);

-- ============================================================
-- LEAD_PUSHES
-- Tracks which CRM contacts were pushed to which campaigns.
-- One row per contact per campaign.
-- Used for dedup (don't push same contact twice) and for
-- mapping Smartlead lead_id back to CRM record_id.
-- ============================================================

CREATE TABLE IF NOT EXISTS lead_pushes (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,

  -- core reference
  record_id           INTEGER NOT NULL,

  -- smartlead references
  campaign_id         INTEGER NOT NULL,
  smartlead_lead_id   INTEGER,
  email               TEXT    NOT NULL,

  -- status tracking
  push_status         TEXT    NOT NULL DEFAULT 'pushed',  -- pushed, active, paused, completed, bounced, unsubscribed
  smartlead_status    TEXT,                                -- lead status from Smartlead

  -- engagement (last known from sync)
  sent_count          INTEGER DEFAULT 0,
  open_count          INTEGER DEFAULT 0,
  click_count         INTEGER DEFAULT 0,
  reply_count         INTEGER DEFAULT 0,

  -- timestamps
  pushed_at           TEXT    NOT NULL DEFAULT (datetime('now')),
  last_synced_at      TEXT,

  UNIQUE(record_id, campaign_id)
);

CREATE INDEX IF NOT EXISTS idx_lead_pushes_record_id
  ON lead_pushes (record_id);

CREATE INDEX IF NOT EXISTS idx_lead_pushes_campaign_id
  ON lead_pushes (campaign_id);

CREATE INDEX IF NOT EXISTS idx_lead_pushes_email
  ON lead_pushes (email);

-- ============================================================
-- SEQUENCES
-- Local cache of campaign email sequences.
-- Used by duplicate command to copy sequences to new campaigns.
-- ============================================================

CREATE TABLE IF NOT EXISTS sequences (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  campaign_id         INTEGER NOT NULL,
  seq_number          INTEGER NOT NULL,
  seq_delay_days      INTEGER,
  variant_distribution TEXT,                    -- e.g. EQUAL
  variants            TEXT    NOT NULL,         -- JSON array of {subject, email_body, variant_label}

  synced_at           TEXT    NOT NULL DEFAULT (datetime('now')),

  UNIQUE(campaign_id, seq_number)
);

CREATE INDEX IF NOT EXISTS idx_sequences_campaign_id
  ON sequences (campaign_id);
