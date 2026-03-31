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
