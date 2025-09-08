"""Shared utilities for requestor CLI commands."""

import asyncio

import click

try:  # Python < 3.8 compatibility
    from importlib import metadata
except ImportError:  # pragma: no cover
    import importlib_metadata as metadata

from ..config import config
from ..services.database_service import DatabaseService
from ..utils.logging import setup_logger

# Logger used across command modules
logger = setup_logger("golem.requestor")

# Database service initialised once and reused by commands
db_service = DatabaseService(config.db_path)


def async_command(f):
    """Decorator that runs async click commands and ensures DB initialisation."""

    async def wrapper(*args, **kwargs):
        await db_service.init()
        return await f(*args, **kwargs)

    return lambda *args, **kwargs: asyncio.run(wrapper(*args, **kwargs))


def print_version(ctx, param, value):
    """Callback to print package version and exit."""
    if not value or ctx.resilient_parsing:
        return
    try:
        version = metadata.version("request-vm-on-golem")
    except metadata.PackageNotFoundError:  # pragma: no cover - during development
        version = "unknown"
    click.echo(f"Requestor VM on Golem CLI version {version}")
    ctx.exit()

