import typer

app = typer.Typer(
    name="skill",
    help="Skill operations — install, uninstall, list, info, update.",
    no_args_is_help=True,
)

# subcommands implemented in later handovers:
#   openkiln skill install <name>
#   openkiln skill uninstall <name>
#   openkiln skill list
#   openkiln skill info <name>
#   openkiln skill update <name>
