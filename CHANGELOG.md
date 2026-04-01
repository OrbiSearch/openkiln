# Changelog

All notable changes to OpenKiln will be documented in this file.

## [0.1.0] — 2026-04-01

Initial release.

### Skills
- **CRM** — contact and company management, CSV import, tags, lists, lifecycle stages, touch logging, linking
- **OrbiSearch** — email verification (single + bulk), credit balance, CLI commands
- **Smartlead** — campaign management, lead push, monitoring, engagement sync, 22 CLI commands

### Workflow Engine
- YAML-based pipeline definitions: Source → Transform → Filter → Sink
- `openkiln workflow run` with dry-run default and --apply
- `openkiln workflow validate` — checks skills, capabilities, and YAML structure
- `openkiln workflow components` — lists available sources, transforms, sinks
- `openkiln workflow history` — past run tracking

### Core
- Skill system with per-skill SQLite databases and auto-discovery
- Source, Transform, Sink interfaces for workflow composition
- Database attach layer for cross-skill queries without Python coupling
- Schema migration system with tracking and idempotent application
- skill.toml manifest format for machine-readable skill metadata

### CLI
- `openkiln init` — first-time setup
- `openkiln status` — installation summary
- `openkiln update` — upgrade via pipx or git
- `openkiln skill install/list/info/update` — skill management
- `openkiln record import/inspect` — CSV import with column mapping and dedup
- All commands support `--json` output
