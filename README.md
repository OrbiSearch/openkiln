# OpenKiln 🔥

Open source agentic data workflow CLI.
Built by [OrbiSearch](https://orbisearch.com).

Import, enrich, validate and push data — using composable workflow
blocks that agents and humans can chain, persist, and schedule.

> **AI agent?** Read [AGENTS.md](AGENTS.md) first.

---

## What it does

OpenKiln lets you build data workflows from composable blocks:

- **Sources** — pull data in (CSV, databases, APIs)
- **Transforms** — process rows (validate, enrich, score, filter)
- **Sinks** — push data out (outreach tools, CRMs, CSV export)

Workflows are defined in simple YAML files and run via the CLI.
Skills extend OpenKiln with new sources, transforms, and sinks.

---

## Quick start

**Requirements:** Python 3.11+, macOS or Linux
```bash
# install
pip install openkiln

# initialise
openkiln init

# verify
openkiln status
```

---

## Install skills

Skills add new capabilities. Install what you need:
```bash
openkiln skill list                    # see available skills
openkiln skill install crm             # contacts and companies
openkiln skill install orbisearch      # email verification
openkiln skill info <skill-name>       # what a skill provides
```

---

## Import data
```bash
# preview a CSV before importing
openkiln record inspect contacts.csv
openkiln record inspect contacts.csv --skill crm

# import contacts
openkiln record import contacts.csv --type contact --skill crm --dry-run
openkiln record import contacts.csv --type contact --skill crm --apply
```

---

## Run workflows

Workflows chain sources, transforms, and sinks into repeatable pipelines.
```bash
# discover what installed skills provide
openkiln skill info crm
openkiln skill info orbisearch

# get a starter workflow template
openkiln workflow template > my-workflow.yml

# validate before running
openkiln workflow validate my-workflow.yml

# run
openkiln workflow run my-workflow.yml --dry-run
openkiln workflow run my-workflow.yml --apply
```

See [workflows/examples/](workflows/examples/) for example workflows.

---

## Configuration

Config lives at `~/.openkiln/config.toml`, created by `openkiln init`.

API keys can be set in the config file or as environment variables.
Environment variables take precedence.
```bash
# OrbiSearch email verification
export ORBISEARCH_API_KEY=your-key-here

# Smartlead outreach
export SMARTLEAD_API_KEY=your-key-here
```

See [.env.example](.env.example) for all supported variables.

---

## Development
```bash
git clone https://github.com/OrbiSearch/openkiln
cd openkiln
make setup
make test
```

---

## Licence

[Elastic Licence 2.0](LICENSE) — free for internal use.
Commercial use requires a licence from OrbiSearch.

---

## Built by

[OrbiSearch](https://orbisearch.com) — email verification API
for developers and agents.
