# init.py
#
# openkiln init
#
# Onboarding wizard. Run once on first use.
# Creates ~/.openkiln/ directory structure:
#   ~/.openkiln/config.toml   — default config file
#   ~/.openkiln/core.db       — core database
#   ~/.openkiln/skills/       — skill databases directory
#
# Applies core schema migrations via Alembic.
# Does not overwrite existing config or databases.
# Safe to re-run — idempotent.
