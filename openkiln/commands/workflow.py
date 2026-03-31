import typer

app = typer.Typer(
    name="workflow",
    help="Workflow operations — run, validate, template, schedule, history.",
    no_args_is_help=True,
)

# subcommands implemented in later handovers:
#   openkiln workflow run <file.yml>
#   openkiln workflow validate <file.yml>
#   openkiln workflow template
#   openkiln workflow schedule <file.yml>
#   openkiln workflow unschedule <name>
#   openkiln workflow history [name]
