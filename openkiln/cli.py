# cli.py
#
# Main CLI entry point using Typer.
# Registers all command groups:
#   - contact (import, list, validate, clean, push)
#   - company (import, list, enrich)
#   - workflow (run, schedule, history, unschedule)
#   - status
#   - init (onboarding wizard)
#
# All commands support --json and --dry-run flags.
# No command prompts for input interactively.
# Every destructive command requires --apply flag.
# Default behaviour is always --dry-run.
