# OpenKiln

Open-source, GTM agentic data workflow CLI. It's like OpenClaw & Clay had a baby.

Build data enrichment and outbound pipelines from modular building blocks.
Install skills to connect services, compose them into workflows with YAML,
run from anywhere — your terminal, Telegram, or any LLM coding agent.

Built by [OrbiSearch](https://orbisearch.com).

---

## Key Concepts

OpenKiln is built around a few simple ideas that snap together like LEGO:

**Skills** are plugins that connect OpenKiln to external services and data.
Each skill owns its own database and provides building blocks for workflows.
Install only what you need:

- **CRM** — manage contacts and companies, import from CSV, tag, filter, track touches
- **OrbiSearch** — verify email addresses (catch-all, disposable, role account detection)
- **Smartlead** — manage campaigns, push contacts, monitor engagement

**Sources** read data in. A source pulls rows from a skill's database or
an external service. Example: read all contacts in a segment from CRM.

**Transforms** process each row. A transform enriches, validates, or modifies
data as it flows through the pipeline. Example: verify each email via OrbiSearch.

**Sinks** write data out. A sink pushes rows to an external service or updates
a database. Example: push verified contacts to a Smartlead campaign.

**Workflows** connect these blocks. A workflow is a YAML file that declares:
read from this source, apply these transforms, filter the results, write to
these sinks. No code required.

```
Source → Transform(s) → Filter → Sink(s)
```

See what's available:
```bash
openkiln workflow components
```

---

## Quick Start

**Requirements:** Python 3.11+

```bash
# install
pip install openkiln

# initialise (creates ~/.openkiln/)
openkiln init

# install skills
openkiln skill install crm
openkiln skill install orbisearch
openkiln skill install smartlead

# import contacts from CSV
openkiln record import contacts.csv --type contact --skill crm --apply

# verify emails, push safe contacts to a Smartlead campaign
openkiln workflow run my-workflow.yml --apply
```

---

## Skills

Skills extend OpenKiln with new capabilities. Each skill is self-contained —
it owns its own SQLite database, provides its own CLI commands, and declares
what sources, transforms, and sinks it offers for workflows.

```bash
# see what's available
openkiln skill list

# install a skill
openkiln skill install smartlead

# learn what a skill provides
openkiln skill info smartlead
```

### Available Skills

| Skill | What it does | Provides |
|-------|-------------|----------|
| **crm** | Contact and company management | Source + Sink |
| **orbisearch** | Email verification | Transform |
| **smartlead** | Campaign management and outreach | Sink |

More skills are available in the [skills directory](https://github.com/OrbiSearch/openkiln-skill-maker).
Anyone can build and submit a skill.

---

## Workflows

Workflows are YAML files that chain skills together into repeatable pipelines.

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

transforms:
  - orbisearch.validate

filter:
  status: safe

sinks:
  - skill: crm
    action: update
  - skill: smartlead
    action: push
    campaign_id: "12345"
```

```bash
# validate your workflow
openkiln workflow validate my-workflow.yml

# dry run (shows what would happen)
openkiln workflow run my-workflow.yml

# execute
openkiln workflow run my-workflow.yml --apply
```

See [WORKFLOWS.md](WORKFLOWS.md) for the complete workflow guide — YAML format,
how filters work, discovering components, and tips.

---

## Deployment

**Recommended setup:** Run OpenKiln on an always-on server (VPS, home server,
cloud instance). Access it from any device via [Telegram](https://telegram.org)
through Claude Code channels, or any LLM coding agent.

This gives you:
- Persistent data that doesn't disappear when you close your laptop
- Run workflows and monitor campaigns from your phone
- Switch between devices seamlessly

You can also run OpenKiln directly in your terminal, through
[Claude Code](https://claude.ai/claude-code), or any LLM chatbot
that can execute shell commands.

---

## Configuration

Config lives at `~/.openkiln/config.toml`, created by `openkiln init`.

API keys can be set as environment variables (recommended) or in the config file.
Environment variables take precedence.

```bash
export ORBISEARCH_API_KEY=your-key-here
export SMARTLEAD_API_KEY=your-key-here
```

---

## Build a Skill

Want to connect a service OpenKiln doesn't support yet? Build a skill.

The [OpenKiln Skill Maker](https://github.com/OrbiSearch/openkiln-skill-maker)
provides everything you need — a specification, templates, examples, and a
validator. Point your LLM coding agent at the repo with an API spec, and it
builds the skill for you.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute.

---

## Development

```bash
git clone https://github.com/OrbiSearch/openkiln
cd openkiln
make setup    # creates venv, installs dependencies
make test     # runs test suite
```

---

## License

[Elastic License 2.0](LICENSE) — free to use, modify, and redistribute.
Cannot be offered as a managed service or used to build competing products.

---

Built by [OrbiSearch](https://orbisearch.com) — email verification for developers and agents.
