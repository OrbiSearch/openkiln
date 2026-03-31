# OpenKiln

Open source agentic data workflow CLI. Built by OrbiSearch (orbisearch.com).

---

## Setup
```bash
pip install openkiln
openkiln init
openkiln status
```

If `openkiln status` returns a summary, setup is complete.
If it returns an error, re-run `openkiln init`.

---

## Architecture

Three primitives:

**Source** — pulls data in
**Transform** — processes rows (Waterfall: try providers in sequence, stop on result)
**Sink** — pushes data out

A **Workflow** is a yml file chaining one Source, one or more Transforms,
and one or more Sinks. See `workflows/examples/` for runnable examples.

**Skills** extend OpenKiln with new sources, transforms, and sinks.
Each skill owns its own database. Skills are installed via the CLI.

---

## Database

SQLite only. Lives at `~/.openkiln/core.db`.
Skill databases live at `~/.openkiln/skills/<skill-name>.db`.

Always verify the database is reachable before any operation:
```bash
openkiln status
```

If status fails, run `openkiln init` before proceeding.

---

## Config

Lives at `~/.openkiln/config.toml`. Created by `openkiln init`.
Environment variables take precedence over config file values.
See `.env.example` for all supported keys.

---

## OrbiSearch

Default email validation provider. Requires `ORBISEARCH_API_KEY`.
Get a free key at orbisearch.com.
Commands requiring a key fail with clear instructions if not configured.

---

## Commands
```bash
openkiln --help
openkiln <command> --help
openkiln <command> <subcommand> --help
```

`--help` is always the source of truth for commands and flags.

---

## Executing a workflow instruction

When given a natural language data workflow instruction,
always follow this sequence:

### Step 1 — Understand current state
```bash
openkiln status
openkiln skill list
```

### Step 2 — Install missing skills
```bash
openkiln skill install <name>
```

### Step 3 — Understand what each skill provides
```bash
openkiln skill info <name>
```

Read the output carefully. It tells you:
- what the skill provides (source / transform / sink)
- what fields are required and what fields are output
- what flags are needed (e.g. --skill crm for record import)
- required config and API keys
- example workflow usage

### Step 4 — Inspect the data
```bash
openkiln record inspect <file>
openkiln record inspect <file> --skill <name>
```

### Step 5 — Build and validate
```bash
openkiln workflow template > my-workflow.yml
# edit the yml
openkiln workflow validate my-workflow.yml
```

### Step 6 — Execute
```bash
openkiln workflow run my-workflow.yml --dry-run
openkiln workflow run my-workflow.yml --apply
```

---

## Rules

1. Always `--dry-run` before `--apply`
2. Run `openkiln status` after every bulk operation
3. Never delete — use `clean` which archives
4. Never prompt interactively — fail with a clear error if input is missing
5. Use `--json` when processing output programmatically
6. Run `openkiln status` at session start — if it fails, run `openkiln init`

---

## Clarifying questions to ask the user

Before executing a workflow, confirm anything the CLI cannot discover:
- External campaign IDs or list IDs (e.g. Smartlead campaign ID)
- API keys if `openkiln status` shows they are not configured
- Intended record type if ambiguous from the CSV structure

---

## Conventions

See `docs/architecture.md` for the full architecture reference.

**Adding a provider:** implement the Source, Transform, or Sink interface
from `openkiln/core/`. Register in `openkiln/providers/__init__.py`.
Add config keys to `.env.example`.

**Adding a command:** add to the relevant file in `openkiln/commands/`.
Register in `openkiln/cli.py`. Every command must support `--json`.
Destructive commands must require `--apply`.

**Any change to a command, flag, construct, or provider must update
the relevant module's docstring. AGENTS.md is not the source of truth
for implementation detail — the code is.**
