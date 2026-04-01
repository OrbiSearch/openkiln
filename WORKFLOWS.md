# Workflows

A workflow is a data pipeline defined in YAML. It connects skills together:
read data from a **source**, process it through **transforms**, filter the
results, and write to one or more **sinks**.

```
Source → Transform(s) → Filter → Sink(s)
```

You don't write code. You install skills, then compose them in YAML.

## Quick Start

```bash
# 1. See what's available
openkiln workflow components

# 2. Write a workflow YAML file (see format below)

# 3. Validate it
openkiln workflow validate my-workflow.yml

# 4. Dry run (reads data, applies transforms, shows what would be written)
openkiln workflow run my-workflow.yml

# 5. Execute for real
openkiln workflow run my-workflow.yml --apply

# 6. Check history
openkiln workflow history
```

## YAML Format

```yaml
name: my-workflow               # workflow name (used in history)
version: 1.0.0                  # optional
author: your-name               # optional

requires:                       # skills that must be installed
  - crm
  - orbisearch
  - smartlead

source:                         # where to read data from
  skill: crm                    # which skill provides the source
  type: contacts                # record type (skill-specific)
  filter:                       # optional filters (skill-specific)
    segment: gtm-agencies
    record_status: active

transforms:                     # processing steps (in order)
  - orbisearch.validate         # each is skill.capability

filter:                         # drop rows after transforms
  status: safe                  # exact match on field values

sinks:                          # where to write results
  - skill: crm                  # first sink
    action: update

  - skill: smartlead            # second sink
    action: push
    campaign_id: "3020548"      # sink-specific config
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `source` | mapping | Data source — must have `skill` key |
| `sinks` | list | At least one sink — each must have `skill` key |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Workflow name (defaults to filename) |
| `version` | string | Semver version |
| `author` | string | Author name |
| `requires` | list | Skill names that must be installed |
| `transforms` | list | Transform capabilities to apply (in order) |
| `filter` | mapping | Key-value pairs for exact-match filtering |

## Example: Validate and Push

This workflow reads contacts from CRM, verifies their email addresses
via OrbiSearch, filters to only deliverable emails, updates the CRM
with verification results, and pushes safe contacts to a Smartlead
campaign.

```yaml
name: validate-and-push
requires:
  - crm
  - orbisearch
  - smartlead

source:
  skill: crm
  type: contacts
  filter:
    segment: gtm-agencies
    record_status: active

transforms:
  - orbisearch.validate

filter:
  status: safe

sinks:
  - skill: crm
    action: update

  - skill: smartlead
    action: push
    campaign_id: "3020548"
```

### What happens step by step:

1. **Source** reads all active contacts in the "gtm-agencies" segment
   from crm.db. Each row is a dict with fields like email, first_name,
   company_name, etc.

2. **Transform** `orbisearch.validate` calls the OrbiSearch API for
   each contact's email. Adds fields to each row: `status` (safe/risky/
   invalid/unknown), `substatus`, `explanation`, `email_provider`.
   Stores the result in orbisearch.db.

3. **Filter** `status: safe` drops any row where status is not "safe".
   Risky, invalid, and unknown emails don't reach the sinks.

4. **Sink** `crm.update` writes the verification fields back to the
   CRM contact records (updates the contact with the new data).

5. **Sink** `smartlead.push` pushes the surviving contacts to
   Smartlead campaign 3020548. Deduplicates against previously
   pushed contacts. Batches in groups of 400.

### Running it:

```bash
# check skills are installed
openkiln skill list

# validate the workflow
openkiln workflow validate validate-and-push.yml

# dry run — see how many contacts would flow through
openkiln workflow run validate-and-push.yml
# Output: Records read: 500, After filter: 420, Sinks: would write 420

# execute
openkiln workflow run validate-and-push.yml --apply
```

## Discovering Components

To see what sources, transforms, and sinks are available from your
installed skills:

```bash
openkiln workflow components
```

This reads each installed skill's `skill.toml` manifest and lists
what it provides. Example output:

```
Sources:
  crm.contacts      — Read contacts from crm.db
  crm.companies     — Read companies from crm.db

Transforms:
  orbisearch.validate — Verify email deliverability

Sinks:
  crm.update         — Update contacts or companies in crm.db
  smartlead.push     — Push contacts to a Smartlead campaign
```

For detailed information about what a skill provides (input/output
fields, configuration, usage examples), read its documentation:

```bash
openkiln skill info orbisearch
openkiln skill info smartlead
```

## How Filters Work

The `filter` section applies after all transforms. It does exact
string matching on row fields:

```yaml
filter:
  status: safe          # row["status"] must equal "safe"
  country: US           # row["country"] must equal "US"
```

All conditions must match (AND logic). Rows that don't match are
dropped and don't reach sinks.

Filter keys are whatever fields exist on the row at that point —
source fields plus any fields added by transforms. Check each
transform's SKILL.md to see what fields it adds.

## Dry Run vs Apply

By default, `openkiln workflow run` does a **dry run**:
- Source is read (data flows through)
- Transforms are applied (API calls happen, results are stored)
- Filter is applied
- Sinks report what they **would** write, but don't write

Use `--apply` to execute sinks and write data.

Note: transforms run even in dry-run mode because they may call
external APIs and their results are needed to apply filters.
OrbiSearch will consume credits during a dry run.

## Workflow History

Every `--apply` run is recorded in the database:

```bash
# show recent runs
openkiln workflow history

# filter by workflow name
openkiln workflow history validate-and-push

# JSON output
openkiln workflow history --json
```

## Tips

- **Start with dry run.** Always run without `--apply` first to see
  record counts and verify the pipeline works as expected.

- **Use `workflow validate` before `workflow run`.** It checks that
  all skills are installed and all capabilities exist without
  executing anything.

- **Check `workflow components`** to see what you can compose.
  You can only use sources, transforms, and sinks that are
  declared in installed skills' manifests.

- **Transforms are ordered.** They apply left to right in the
  `transforms` list. Each transform receives the output of the
  previous one.

- **Multiple sinks are independent.** All sinks receive the same
  filtered rows. They execute in order but don't affect each other.

- **All commands support `--json`** for machine-readable output,
  useful when an agent is running workflows programmatically.
