import typer
from openkiln.commands import init, status, workflow, skill, record

app = typer.Typer(
    name="openkiln",
    help="Open source agentic data workflow CLI. Built by OrbiSearch.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)

# command groups
app.add_typer(workflow.app, name="workflow")
app.add_typer(skill.app,    name="skill")
app.add_typer(record.app,   name="record")

# single commands
app.command("init")(init.run)
app.command("status")(status.run)

if __name__ == "__main__":
    app()
