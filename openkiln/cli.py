# cli.py
#
# Main CLI entry point using Typer.
# Registers all command groups:
#
#   openkiln init        — onboarding wizard
#   openkiln status      — installation summary
#   openkiln record      — record operations (import, list, clean)
#   openkiln workflow    — workflow operations (run, validate, template,
#                          schedule, unschedule, history)
#   openkiln skill       — skill operations (install, uninstall, list,
#                          info, update)
#
# Global flags available on all commands:
#   --json               — machine-readable output (for agents)
#   --dry-run            — preview without writing data (default)
#   --apply              — required to write data
#
# No command ever prompts for interactive input.
# If required input is missing, command fails with a clear error message.
# Every destructive command requires --apply flag.
