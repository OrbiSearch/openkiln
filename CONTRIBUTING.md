# Contributing to OpenKiln

Thanks for your interest in contributing! This guide covers how to
contribute code, skills, and improvements.

## Getting Started

```bash
git clone https://github.com/OrbiSearch/openkiln
cd openkiln
make setup    # creates venv, installs deps
make test     # runs the test suite (153+ tests)
```

## How to Contribute

### Build a Skill

The best way to contribute is by building a skill for a service
OpenKiln doesn't support yet.

Use the [OpenKiln Skill Maker](https://github.com/OrbiSearch/openkiln-skill-maker)
— it provides the specification, templates, examples, and a validator.
You can point an LLM coding agent at the repo with an API spec and it
builds the skill for you.

When your skill is ready:
1. Run the validator: `python validate/validate.py openkiln/skills/<name>/`
2. Run the full test suite: `make test`
3. Submit a pull request

### Fix a Bug or Add a Feature

1. Check [existing issues](https://github.com/OrbiSearch/openkiln/issues)
   or open a new one to discuss your idea
2. Fork the repo and create a branch
3. Make your changes
4. Run `make test` — all tests must pass
5. Run `ruff check openkiln/ tests/` — no lint errors
6. Run `ruff format openkiln/ tests/` — consistent formatting
7. Submit a pull request

## Pull Request Guidelines

- **One PR, one thing.** Keep PRs focused — a skill, a bug fix, a feature.
  Don't bundle unrelated changes.
- **Tests required.** New features need tests. Bug fixes need a test that
  reproduces the bug.
- **CI must pass.** The PR will run lint, format, tests, and skill validation
  automatically. All checks must be green.
- **Follow existing patterns.** Look at how existing skills and commands are
  structured. Match the conventions.

## Code Style

- Python 3.11+
- [Ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Line length: 105
- Use type hints
- Use `from __future__ import annotations` in all files

## Architecture Rules

These are non-negotiable:

1. **Skills never import other skills' Python code.** Use the db attach
   layer (`db.connection(attach_skills=[...])`) for cross-skill data access.
2. **No unused code.** Every API method must have a CLI command. Every CLI
   command must be documented.
3. **No silent failures.** Caught errors must surface a warning or clear message.
4. **Dry-run by default.** Write operations require `--apply`.
5. **All commands support `--json`.** For machine-readable output.

See [SKILL-SPEC.md](https://github.com/OrbiSearch/openkiln-skill-maker/blob/main/SKILL-SPEC.md)
in the skill-maker repo for the complete specification.

## Project Structure

```
openkiln/
  core/           — Source, Transform, Sink interfaces + workflow engine
  commands/       — CLI command groups (skill, record, workflow, init, status)
  skills/         — skill packages (crm/, orbisearch/, smartlead/)
    <name>/
      __init__.py   — version + constants
      skill.toml    — manifest
      SKILL.md      — documentation
      schema/       — SQL migrations
      api.py        — API client (if external)
      cli.py        — CLI commands
      queries.py    — database queries
      workflow.py   — Source/Transform/Sink implementations
  config.py       — config file management
  db.py           — database connections, migrations, batch helpers
tests/            — test suite
workflows/        — example workflow YAML files
```

## License

By contributing, you agree that your contributions will be licensed
under the [Elastic License 2.0](LICENSE).
