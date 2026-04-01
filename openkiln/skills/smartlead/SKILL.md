# Smartlead Skill

Campaign management and lead outreach via the Smartlead API.

## Provides

| Type   | Name             | Description                          |
|--------|------------------|--------------------------------------|
| sink   | smartlead.push   | Push contacts to a Smartlead campaign |

## Required config
```bash
# Set via environment variable (recommended)
export SMARTLEAD_API_KEY=your-key-here

# Or via config file (~/.openkiln/config.toml)
[skills.smartlead]
api_key = "your-key-here"
```

Get your API key from app.smartlead.ai > Settings > API Keys.

## Campaigns

### Listing campaigns
```bash
# list all campaigns
openkiln smartlead campaigns

# show campaign detail with sequences
openkiln smartlead campaigns <id>

# JSON output
openkiln smartlead campaigns --json
```

### Campaign analytics
```bash
# top-level stats
openkiln smartlead stats <campaign_id>

# date-range breakdown (max 30 day window)
openkiln smartlead stats <campaign_id> --start-date 2025-03-01 --end-date 2025-03-30
```

### Email accounts
```bash
# list all email accounts
openkiln smartlead accounts list

# add email account(s) to a campaign
openkiln smartlead accounts add <campaign_id> --account-id <id>

# remove an email account from a campaign
openkiln smartlead accounts remove <campaign_id> --account-id <id>
```

### Syncing campaign data locally
```bash
openkiln smartlead sync
```

Pulls all campaigns, sequences, and analytics snapshots into
smartlead.db for offline reference and dedup during lead pushes.

## Creating campaigns

```bash
# create a new drafted campaign
openkiln smartlead create "My Campaign"

# duplicate an existing campaign (copies sequences + email accounts)
openkiln smartlead duplicate <campaign_id>
openkiln smartlead duplicate <campaign_id> --name "New angle v2"

# set sequences from a JSON file
openkiln smartlead sequence <campaign_id> --file sequences.json

# configure schedule
openkiln smartlead schedule <campaign_id> \
  --timezone "US/Eastern" \
  --days 1,2,3,4,5 \
  --start-hour "09:00" \
  --end-hour "17:00" \
  --max-leads-per-day 50

# delete a campaign
openkiln smartlead delete <campaign_id>
```

### Sequence file format (JSON)
```json
[
  {
    "seq_number": 1,
    "seq_delay_details": {"delay_in_days": 0},
    "subject": "Hello {{first_name}}",
    "email_body": "<div>Your email body here</div>"
  },
  {
    "seq_number": 2,
    "seq_delay_details": {"delay_in_days": 3},
    "subject": "Following up",
    "email_body": "<div>Follow up body</div>"
  }
]
```

## Pushing contacts

Push contacts to a Smartlead campaign. Reads contacts from any
skill that has a contacts table (default: crm).

```bash
# preview (dry run)
openkiln smartlead push <campaign_id>

# push a specific segment
openkiln smartlead push <campaign_id> --segment "gtm-agencies" --apply

# push contacts from a named list
openkiln smartlead push <campaign_id> --list "q2-outreach" --apply

# filter by lifecycle stage or lead status
openkiln smartlead push <campaign_id> --lifecycle sql --status contacted --apply

# read contacts from a different skill
openkiln smartlead push <campaign_id> --skill my_contacts --apply

# bypass dedup (re-push previously pushed contacts)
openkiln smartlead push <campaign_id> --force --apply
```

Contacts are batched (max 400 per API call), deduplicated against
previous pushes, and tracked in smartlead.db.

Contact fields are mapped automatically:
| Contact field | Smartlead field    |
|---------------|--------------------|
| email         | email              |
| first_name    | first_name         |
| last_name     | last_name          |
| company_name  | company_name       |
| phone         | phone_number       |
| linkedin_url  | linkedin_profile   |
| city          | location           |

Additional fields (job_title, department, seniority, country, etc.)
are sent as Smartlead custom_fields, usable as template variables
in email sequences (e.g. `{{job_title}}`).

## Launch and monitor

```bash
# start a campaign (requires confirmation)
openkiln smartlead start <campaign_id>

# pause / stop
openkiln smartlead pause <campaign_id>
openkiln smartlead stop <campaign_id>

# monitor lead-level engagement
openkiln smartlead monitor <campaign_id>
openkiln smartlead monitor <campaign_id> --limit 50 --offset 100

# export all leads as CSV
openkiln smartlead export <campaign_id>
```

## Lead operations

```bash
# look up a lead by email
openkiln smartlead lead find <email>

# view email thread history
openkiln smartlead lead thread <campaign_id> <lead_id>

# pause / resume / unsubscribe a lead
openkiln smartlead lead pause <campaign_id> <lead_id>
openkiln smartlead lead resume <campaign_id> <lead_id>
openkiln smartlead lead unsubscribe <campaign_id> <lead_id>
```

## Syncing engagement back

```bash
# pull Smartlead activity into CRM as touches
openkiln smartlead sync-touches <campaign_id>

# actually create the touch records
openkiln smartlead sync-touches <campaign_id> --apply

# write to a different skill's touches table
openkiln smartlead sync-touches <campaign_id> --skill my_contacts --apply
```

## Example workflow usage
```yaml
sinks:
  - skill: smartlead
    action: push
    campaign_id: "12345"
```
