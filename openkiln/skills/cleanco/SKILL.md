# Cleanco Skill

Clean company names for outreach using OpenAI.

## Provides

| Type      | Name                  | Description                           |
|-----------|-----------------------|---------------------------------------|
| transform | cleanco.company_name  | Clean company names for cold email    |

## Required config
```bash
# Set via environment variable (recommended)
export OPENAI_API_KEY=your-key-here

# Or via config file (~/.openkiln/config.toml)
[skills.cleanco]
api_key = "your-key-here"
```

## What it cleans

- Legal suffixes: Inc, LLC, Ltd, GmbH, Corp, PLC, etc.
- Parenthetical descriptions: "Tiger Data (creators of TimescaleDB)" -> "Tiger Data"
- Pipe-separated taglines: "Rocketship | Digital Marketing Agency" -> "Rocketship"
- Colon-separated taglines: "eyreACT: AI Act Compliance Platform" -> "eyreACT"
- Preserves brand names: "1Password", "6sense" stay unchanged

Uses gpt-4o-mini for intelligent cleaning. Results are cached in
cleanco.db so each unique name is only cleaned once.

## CLI Commands

### clean

Clean company names in a CSV file.

```bash
# dry run — shows what would be cleaned
openkiln cleanco clean contacts.csv

# clean and write output (defaults to contacts-cleaned.csv)
openkiln cleanco clean contacts.csv --apply

# specify column and output path
openkiln cleanco clean contacts.csv --column company_name --output cleaned.csv --apply

# JSON output
openkiln cleanco clean contacts.csv --apply --json
```

**Flags:**
- `--column`, `-c` — Column name containing company names (default: `company_name`)
- `--output`, `-o` — Output file path (default: `<input>-cleaned.csv`)
- `--apply` — Actually clean and write output (default: dry run)
- `--json` — Output as JSON

### cache

Show cache statistics.

```bash
openkiln cleanco cache
openkiln cleanco cache --json
```

### show

Show cached name changes (where original differs from cleaned).

```bash
openkiln cleanco show
openkiln cleanco show --limit 50
openkiln cleanco show --json
```

**Flags:**
- `--limit`, `-n` — Number of entries to show (default: 20)
- `--json` — Output as JSON

## Example workflow usage

### Pre-import (CLI)
```bash
openkiln cleanco clean contacts.csv --apply
openkiln record import contacts-cleaned.csv --type contact --skill crm --apply
```

### Post-import (workflow)
```yaml
name: clean-validate-push
requires:
  - crm
  - cleanco
  - orbisearch
  - smartlead

source:
  skill: crm
  type: contacts
  filter:
    segment: clay-gtm-ops

transforms:
  - cleanco.company_name
  - orbisearch.validate

filter:
  status: safe

sinks:
  - skill: crm
    action: update
  - skill: smartlead
    action: push
    campaign_id: "3133669"
```
