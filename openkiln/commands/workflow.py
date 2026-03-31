# workflow.py
#
# openkiln workflow <subcommand>
#
# Subcommands:
#
#   run <file.yml>
#     Executes a workflow file.
#     Reads requires: block, checks skills are installed.
#     Fails with clear instructions if required skills are missing.
#     Default: --dry-run (no data written)
#     Requires: --apply to write data
#
#   validate <file.yml>
#     Validates workflow syntax and skill dependencies.
#     Checks required skills are installed.
#     Checks source fields satisfy transform inputs.
#     Checks transform outputs satisfy sink inputs.
#     Does not run the workflow or touch any data.
#     Always run before: openkiln workflow run
#
#   template
#     Prints a starter workflow yml to stdout.
#     User redirects to a file: openkiln workflow template > my-workflow.yml
#     Template includes comments explaining every field.
#
#   schedule <file.yml>
#     Adds workflow to cron schedule defined in the yml file.
#
#   unschedule <name>
#     Removes a workflow from the cron schedule.
#
#   history [name]
#     Shows workflow run history from core.db workflow_runs table.
#     Filters by workflow name if provided.
#     Supports --json flag.
#
# All subcommands support --json flag for agent consumption.
# run and schedule require --apply for any data-writing operations.
