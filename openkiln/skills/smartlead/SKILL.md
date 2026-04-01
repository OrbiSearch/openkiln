# Smartlead Skill

Campaign management and lead outreach via the Smartlead API.

## Provides

| Type   | Name             | Description                                  |
|--------|------------------|----------------------------------------------|
| sink   | smartlead.push   | Push contacts to a Smartlead campaign         |
| source | smartlead.stats  | Pull campaign engagement data back            |

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
openkiln smartlead campaigns
openkiln smartlead campaigns <id>
```

### Campaign analytics
```bash
openkiln smartlead stats <campaign_id>
```

### Email accounts
```bash
openkiln smartlead accounts
```

### Syncing campaign data locally
```bash
openkiln smartlead sync
```

## Creating campaigns

```bash
# create a new drafted campaign
openkiln smartlead create "My Campaign"

# duplicate an existing campaign's sequences
openkiln smartlead duplicate <campaign_id>

# set sequences from a YAML file
openkiln smartlead sequence <campaign_id> --file sequences.yml

# configure schedule
openkiln smartlead schedule <campaign_id> \
  --timezone "US/Eastern" \
  --days 1,2,3,4,5 \
  --start-hour "09:00" \
  --end-hour "17:00" \
  --max-leads-per-day 50

# assign email accounts
openkiln smartlead accounts add <campaign_id> --account-id <id>
```

## Pushing contacts

Push CRM contacts to a Smartlead campaign:
```bash
# preview (dry run)
openkiln smartlead push <campaign_id>

# push a specific segment
openkiln smartlead push <campaign_id> --segment "gtm-agencies" --apply

# push contacts from a CRM list
openkiln smartlead push <campaign_id> --list "q2-outreach" --apply
```

Contacts are batched (max 400 per API call), deduplicated against
previous pushes, and tracked in smartlead.db.

CRM fields are mapped to Smartlead lead fields automatically:
| CRM field     | Smartlead field    |
|---------------|--------------------|
| email         | email              |
| first_name    | first_name         |
| last_name     | last_name          |
| company_name  | company_name       |
| phone         | phone_number       |
| linkedin_url  | linkedin_profile   |
| city          | location           |

## Launch and monitor

```bash
# start a campaign
openkiln smartlead start <campaign_id>

# pause / stop
openkiln smartlead pause <campaign_id>
openkiln smartlead stop <campaign_id>

# monitor live stats
openkiln smartlead monitor <campaign_id>
```

## Syncing engagement back to CRM

```bash
# pull Smartlead activity into CRM touches
openkiln smartlead sync-touches <campaign_id>
```

## Example workflow usage
```yaml
sinks:
  - skill: smartlead
    action: push
    campaign_id: "12345"
```
