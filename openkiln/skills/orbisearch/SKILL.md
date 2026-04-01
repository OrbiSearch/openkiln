# OrbiSearch Skill

Email verification via the OrbiSearch API.
Built and maintained by OrbiSearch (orbisearch.com).

## Provides

| Type      | Name                | Description                    |
|-----------|---------------------|--------------------------------|
| transform | orbisearch.validate | Verify email deliverability    |

## Required config
```bash
# Set via environment variable (recommended)
export ORBISEARCH_API_KEY=your-key-here

# Or via config file (~/.openkiln/config.toml)
[skills.orbisearch]
api_key = "your-key-here"
```

Get a free API key at orbisearch.com.
If no key is configured, commands requiring this skill will fail
with instructions to set the key.

## CLI Commands

### verify

Verify a single email address in real-time.

```bash
openkiln orbisearch verify jane.doe@acme.com
openkiln orbisearch verify jane.doe@acme.com --timeout 30
openkiln orbisearch verify jane.doe@acme.com --json
```

**Flags:**
- `--timeout` — Timeout in seconds, 3-90 (default: 70)
- `--json` — Output as JSON

### credits

Show your current OrbiSearch credit balance.

```bash
openkiln orbisearch credits
openkiln orbisearch credits --json
```

**Flags:**
- `--json` — Output as JSON

### bulk-submit

Submit a bulk email verification job. Defaults to dry-run.

```bash
# Dry run — shows what would be submitted
openkiln orbisearch bulk-submit user1@example.com user2@example.com

# Actually submit the job
openkiln orbisearch bulk-submit user1@example.com user2@example.com --apply
openkiln orbisearch bulk-submit user1@example.com user2@example.com --apply --json
```

**Flags:**
- `--apply` — Actually submit the job (default: dry-run)
- `--json` — Output as JSON

### bulk-status

Check the status and progress of a bulk verification job.

```bash
openkiln orbisearch bulk-status 123e4567-e89b-12d3-a456-426614174000
openkiln orbisearch bulk-status 123e4567-e89b-12d3-a456-426614174000 --json
```

**Flags:**
- `--json` — Output as JSON

### bulk-results

Retrieve results of a completed bulk verification job.

```bash
openkiln orbisearch bulk-results 123e4567-e89b-12d3-a456-426614174000
openkiln orbisearch bulk-results 123e4567-e89b-12d3-a456-426614174000 --json
```

**Flags:**
- `--json` — Output as JSON

## Status values

| Status  | Meaning                                              |
|---------|------------------------------------------------------|
| safe    | Deliverable — safe to email                          |
| risky   | Uncertain — send with caution (e.g. catch-all domain)|
| invalid | Undeliverable — do not email                         |
| unknown | Verification failed — retry or skip                  |

## Verification modes

**Single** (default) — real-time, one email at a time:
- Recommended rate: ~16 requests/second
- Cost: 0.2 credits per verification
- Results cached 24 hours

**Bulk** — async job, better for large lists:
- Submit a job, poll for completion, retrieve results
- Cost: 0.2 credits per email (deduplicated)
- Recommended for lists over 20 emails

## Example workflow usage
```yaml
transforms:
  - orbisearch.validate

filter:
  status: safe
```
