"""Top level CLI module that aggregates command groups."""

import click

from ..config import ensure_config
from .shared import print_version
from .provider_commands import provider
from .server_commands import server
from .vm_commands import vm


@click.group()
@click.option(
    "--version",
    is_flag=True,
    callback=print_version,
    expose_value=False,
    is_eager=True,
    help="Show the version and exit.",
)
def cli():
    """VM on Golem management CLI"""
    ensure_config()


# Register command groups
cli.add_command(vm)
cli.add_command(provider)
cli.add_command(server)


def main() -> None:  # pragma: no cover - convenience wrapper
    """Entry point for manual execution."""
    cli()


if __name__ == "__main__":  # pragma: no cover
    main()

