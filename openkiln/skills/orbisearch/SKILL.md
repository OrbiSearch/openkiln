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

## Transform: orbisearch.validate

Verifies email addresses via the OrbiSearch API.

### Input fields required

| Field | Type | Notes                         |
|-------|------|-------------------------------|
| email | text | Must be present on the record |

### Output fields written to orbisearch.db

| Field          | Type    | Values                                              |
|----------------|---------|-----------------------------------------------------|
| status         | text    | safe, risky, invalid, unknown                       |
| substatus      | text    | catch_all, disposable, role_account,                |
|                |         | invalid_syntax, null                                |
| explanation    | text    | Human-readable result description                   |
| email_provider | text    | Google Workspace, Microsoft Outlook, etc            |
| is_disposable  | boolean |                                                     |
| is_role_account| boolean |                                                     |
| is_free        | boolean |                                                     |

### Status values

| Status  | Meaning                                              |
|---------|------------------------------------------------------|
| safe    | Deliverable — safe to email                          |
| risky   | Uncertain — send with caution (e.g. catch-all domain)|
| invalid | Undeliverable — do not email                         |
| unknown | Verification failed — retry or skip                  |

### Verification modes

Single (default) — real-time, one email at a time:
  - Recommended rate: 20 requests/second
  - Cost: 0.2 credits per verification
  - Results cached 24 hours

Bulk — async job, better for large lists:
  - Submit a job, poll for completion, retrieve results
  - Cost: 0.2 credits per email (deduplicated)
  - Recommended for lists over 20 emails

OpenKiln uses bulk mode automatically when validating
more than 20 emails in a single workflow run.

## Credits

Check your current OrbiSearch credit balance:
```bash
openkiln skill info orbisearch --credits
```

## Example workflow usage
```yaml
transforms:
  - orbisearch.validate

filter:
  status: safe
```
