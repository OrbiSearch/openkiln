# OpenKiln

Open-source, agentic GTM data workflow CLI. Built by OrbiSearch (orbisearch.com).

---

## Setup

```bash
pipx install git+https://github.com/OrbiSearch/openkiln.git
openkiln init
```

### Verify
```bash
openkiln --help      # must show real commands — init, status, skill, record, workflow
openkiln status      # must return a summary, not an error
```

If `openkiln --help` shows nothing or errors — the package is not
installed. Run the install command above.

> OpenKiln is fully implemented. All commands in `--help` are real
> and runnable. Do not attempt to reimplement anything.
> If a command errors, report it — do not rewrite the source.

---

## Architecture

Three primitives:

**Source** — pulls data in (from a skill's database or external service)
**Transform** — processes rows (validate, enrich, score)
**Sink** — pushes data out (to external services or databases)

A **Workflow** is a YAML file chaining one Source, one or more Transforms,
and one or more Sinks. See `workflows/examples/` for runnable examples.
See `WORKFLOWS.md` for the complete workflow guide.

**Skills** extend OpenKiln with new sources, transforms, and sinks.
Each skill owns its own SQLite database and provides its own CLI commands.
Skills are installed via the CLI and interact with each other only through
the database attach layer — never through Python imports.

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
openkiln workflow components
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
# write your workflow YAML (see WORKFLOWS.md for format)
openkiln workflow validate my-workflow.yml
```

### Step 6 — Execute
```bash
openkiln workflow run my-workflow.yml           # dry run
openkiln workflow run my-workflow.yml --apply    # execute
```

---

## Rules

1. Always dry run before `--apply`
2. Run `openkiln status` after every bulk operation
3. Never prompt interactively — fail with a clear error if input is missing
4. Use `--json` when processing output programmatically
5. Run `openkiln status` at session start — if it fails, run `openkiln init`

---

## Clarifying questions to ask the user

Before executing a workflow, confirm anything the CLI cannot discover:
- External campaign IDs or list IDs (e.g. Smartlead campaign ID)
- API keys if `openkiln status` shows they are not configured
- Intended record type if ambiguous from the CSV structure

---

## Conventions

**Skills** are self-contained packages in `openkiln/skills/<name>/`.
Each skill has: `__init__.py`, `skill.toml`, `SKILL.md`, `schema/`,
and optionally `api.py`, `cli.py`, `queries.py`, `workflow.py`.

**Workflow interfaces** are defined in `openkiln/core/` — `Source`,
`Transform`, `Sink`. Skills implement these in `workflow.py` and
declare them in `skill.toml`.

**Adding a skill:** Use the [Skill Maker](https://github.com/OrbiSearch/openkiln-skill-maker)
repo which provides the specification, templates, and validator.

**Adding a command:** Add to the relevant file in `openkiln/commands/`.
Every command must support `--json`. Write operations must require `--apply`.
Destructive commands must require `--yes`.

**Any change to a command, flag, construct, or skill must update
the relevant documentation. AGENTS.md is not the source of truth
for implementation detail — the code is.**
