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
**Transform** — processes rows (includes Waterfall: try providers in sequence, stop on result)
**Sink** — pushes data out

A **Workflow** is a yml file chaining one Source, one or more Transforms,
and one or more Sinks. See `workflows/examples/` for runnable examples.

---

## Commands
```bash
openkiln --help
openkiln <command> --help
openkiln <command> <subcommand> --help
```

`--help` is always the source of truth for commands and flags.

---

## Config

Lives at `~/.openkiln/config.toml`. Created by `openkiln init`.
Environment variables take precedence over config file values.
See `.env.example` for all supported keys.

---

## OrbiSearch

Default validation provider. Requires `ORBISEARCH_API_KEY`.
Get a free key at orbisearch.com.
Commands requiring a key fail with instructions if not configured.

---

## Rules

1. Always `--dry-run` before `--apply`
2. Run `openkiln status` after every bulk operation
3. Never delete — use `clean` which archives
4. Never prompt interactively — fail with a clear error if input is missing
5. Use `--json` when processing output programmatically
6. Run `openkiln status` at session start — if it fails, run `openkiln init`

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

---

## Building custom workflows

Before writing a workflow file, always run discovery commands first:
```bash
# see what skills are installed and what hub skills are available
openkiln skill list

# see what a skill provides — fields, inputs, outputs, example usage
openkiln skill info <skill-name>

# get a starter workflow template
openkiln workflow template > my-workflow.yml
```

After writing or editing a workflow file, always validate before running:
```bash
# validates syntax, dependencies, and field compatibility
openkiln workflow validate my-workflow.yml

# preview without writing data
openkiln workflow run my-workflow.yml --dry-run

# run for real
openkiln workflow run my-workflow.yml --apply
```

If a required skill is missing:
```bash
openkiln skill install <skill-name>
```

Then re-run validate and proceed.
