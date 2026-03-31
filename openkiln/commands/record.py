import typer

app = typer.Typer(
    name="record",
    help="Record operations — import, list, clean.",
    no_args_is_help=True,
)

# subcommands implemented in later handovers:
#   openkiln record import <file.csv> --type <type>
#   openkiln record list --type <type>
#   openkiln record clean --status <status>
