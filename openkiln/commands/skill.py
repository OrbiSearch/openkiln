# skill.py
#
# openkiln skill <subcommand>
#
# Subcommands:
#
#   install <name>
#     Installs a skill from the OpenKiln hub.
#     Creates skill database at ~/.openkiln/skills/<name>.db
#     Runs skill schema migrations.
#     Adds skill entry to core.db installed_skills table.
#     Adds skill config section to ~/.openkiln/config.toml.
#     Prompts for required API keys if not set in environment.
#
#   uninstall <name>
#     Removes a skill.
#     Drops skill database (with confirmation).
#     Removes from installed_skills table.
#     Removes config section from config.toml.
#
#   list
#     Lists installed skills with name, version, db path.
#     Also lists skills available on hub but not installed.
#     Supports --json flag.
#
#   info <name>
#     Shows detailed information about a skill:
#       - version
#       - description
#       - what it provides (source / transform / sink)
#       - input and output fields
#       - required config / env vars
#       - example workflow usage
#     Works for both installed and hub skills.
#     Supports --json flag.
#
#   update <name>
#     Updates an installed skill to the latest hub version.
#     Runs any new schema migrations.
#
# All subcommands support --json flag for agent consumption.
