# CRM Skill

Contact and company data management for OpenKiln.

## Provides

| Type   | Name           | Description                      |
|--------|----------------|----------------------------------|
| source | crm.contacts   | Read contacts from crm.db        |
| source | crm.companies  | Read companies from crm.db       |
| sink   | crm.contacts   | Write/update contacts in crm.db  |
| sink   | crm.companies  | Write/update companies in crm.db |

## Record types

| Type    | Natural key | Description           |
|---------|-------------|-----------------------|
| contact | email       | A person record       |
| company | domain      | An organisation record|

## Importing contacts
```bash
openkiln record import <file.csv> --type contact --skill crm
```

The --skill crm flag writes contact data to crm.db alongside
the bare record in core.db. Without it, only a bare record
is created with no contact data attached.

### Expected CSV columns

| Column       | Type   | Notes                           |
|--------------|--------|---------------------------------|
| first_name   | text   |                                 |
| last_name    | text   |                                 |
| full_name    | text   |                                 |
| email        | text   | Natural dedup key               |
| phone        | text   |                                 |
| linkedin_url | text   |                                 |
| company_name | text   |                                 |
| job_title    | text   |                                 |
| department   | text   |                                 |
| seniority    | text   | c_suite/vp/director/manager/ic  |
| city         | text   |                                 |
| country      | text   |                                 |
| timezone     | text   |                                 |
| segment      | text   | User-defined e.g. gtm-agencies  |
| tags         | text   | Comma-separated e.g. hot-lead   |
| lead_score   | number |                                 |
| source       | text   | Where this record came from     |

All columns are optional. Unknown columns are skipped and reported.
Missing columns import as NULL.

If your CSV uses different column names, use --map to remap them:
```bash
openkiln record import contacts.csv --type contact --skill crm \
  --map "Title=job_title" \
  --map "linkedin_profile=linkedin_url" \
  --apply
```

Multiple --map flags are supported. The target must be a valid
column name from the schema above.

## Importing companies
```bash
openkiln record import <file.csv> --type company --skill crm
```

### Expected CSV columns

| Column         | Type   | Notes                           |
|----------------|--------|---------------------------------|
| name           | text   |                                 |
| domain         | text   | Natural dedup key               |
| website_url    | text   |                                 |
| linkedin_url   | text   |                                 |
| industry       | text   |                                 |
| employee_count | number |                                 |
| employee_range | text   | e.g. 1-10, 11-50, 51-200        |
| hq_city        | text   |                                 |
| hq_country     | text   |                                 |
| description    | text   |                                 |
| segment        | text   |                                 |
| tags           | text   | Comma-separated                 |
| icp_score      | number |                                 |
| source         | text   |                                 |

## Required config

None. CRM skill has no external API dependencies.

## Listing and filtering
```bash
# list contacts
openkiln crm list contacts
openkiln crm list contacts --segment "cold-email-agencies"
openkiln crm list contacts --tag "priority"
openkiln crm list contacts --not-contacted-since 30
openkiln crm list contacts --segment "cold-email-agencies" --not-contacted-since 30
openkiln crm list contacts --limit 100
openkiln crm list contacts --json

# list companies
openkiln crm list companies
openkiln crm list companies --segment "saas"
```

## Tagging and segmenting
```bash
# set segment on all contacts matching a filter
openkiln crm tag contacts --segment "cold-email-agencies" --dry-run
openkiln crm tag contacts --segment "cold-email-agencies" --apply

# add a tag to specific records
openkiln crm tag contacts --ids 1,2,3 --add-tag "priority" --apply

# update a single contact by email
openkiln crm tag contacts --email "john@acme.com" \
  --set-segment "cold-email-agencies" --apply

# remove a tag
openkiln crm tag contacts --tag "priority" --remove-tag "priority" --apply
```

## Stats
```bash
openkiln crm stats
openkiln crm stats --json
```

## Touch logging
```bash
# log an outbound email touch
openkiln crm touch log --record-id 1 --channel email --direction outbound

# log with a note
openkiln crm touch log --record-id 1 --channel linkedin \
  --note "Replied positively, follow up next week"

# log against a campaign
openkiln crm touch log --record-id 1 --channel email \
  --campaign-id "q2-outreach"
```

## Example workflow usage
```yaml
source:
  skill: crm
  type: contacts
  filter:
    segment: gtm-agencies

sinks:
  - skill: crm
    action: update
```
