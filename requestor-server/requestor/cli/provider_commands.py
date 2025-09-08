"""Provider related CLI commands."""

import asyncio
import json
from typing import Optional

import click
from tabulate import tabulate

from ..config import config
from ..services.provider_service import ProviderService
from .shared import async_command, logger


@click.group()
def provider():
    """Provider management commands"""
    pass


@provider.command(name="list")
@click.option("--cpu", type=int, help="Minimum CPU cores required")
@click.option("--memory", type=int, help="Minimum memory (GB) required")
@click.option("--storage", type=int, help="Minimum storage (GB) required")
@click.option("--country", help="Preferred provider country")
@click.option(
    "--driver",
    type=click.Choice(["central", "golem-base"]),
    default=None,
    help="Discovery driver to use",
)
@click.option("--json", "as_json", is_flag=True, help="Output in JSON format")
@async_command
async def list_providers(
    cpu: Optional[int],
    memory: Optional[int],
    storage: Optional[int],
    country: Optional[str],
    driver: Optional[str],
    as_json: bool,
):
    """List available providers matching requirements."""
    try:
        if any([cpu, memory, storage, country]):
            logger.command("🔍 Searching for providers with criteria:")
            if cpu:
                logger.detail(f"CPU Cores: {cpu}+")
            if memory:
                logger.detail(f"Memory: {memory}GB+")
            if storage:
                logger.detail(f"Storage: {storage}GB+")
            if country:
                logger.detail(f"Country: {country}")

        discovery_driver = driver or config.discovery_driver
        logger.process(f"Querying discovery service via {discovery_driver}")

        provider_service = ProviderService()
        async with provider_service:
            providers = await provider_service.find_providers(
                cpu=cpu,
                memory=memory,
                storage=storage,
                country=country,
                driver=driver,
            )

        if not providers:
            logger.warning("No providers found matching criteria")
            return {"providers": []}

        result = {"providers": providers}

        if as_json:
            click.echo(json.dumps(result, indent=2))
        else:
            headers = provider_service.provider_headers
            rows = await asyncio.gather(
                *(
                    provider_service.format_provider_row(p, colorize=True)
                    for p in providers
                )
            )

            click.echo("\n" + "─" * 80)
            click.echo(
                click.style(
                    f"  🌍 Available Providers ({len(providers)} total)",
                    fg="blue",
                    bold=True,
                )
            )
            click.echo("─" * 80)

            click.echo(
                "\n"
                + tabulate(
                    rows,
                    headers=[click.style(h, bold=True) for h in headers],
                    tablefmt="grid",
                )
            )
            click.echo("\n" + "─" * 80)

        return result

    except Exception as e:
        logger.error(f"Failed to list providers: {str(e)}")
        raise click.Abort()

