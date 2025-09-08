"""Server related CLI commands."""

import click
import uvicorn

from ..config import config
from .shared import logger


@click.group()
def server():
    """Server management commands"""
    pass


@server.command(name="api")
@click.option("--host", default="127.0.0.1", help="Host to bind the API server to.")
@click.option("--port", default=8000, type=int, help="Port to run the API server on.")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development.")
def run_api_server(host: str, port: int, reload: bool):
    """Run the Requestor API server."""
    logger.command(f"🚀 Starting Requestor API server on {host}:{port}")
    if reload:
        logger.warning("Auto-reload enabled (for development)")

    try:
        config.db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.detail(f"Ensured database directory exists: {config.db_path.parent}")
    except Exception as e:  # pragma: no cover - filesystem failure
        logger.error(f"Failed to create database directory {config.db_path.parent}: {e}")
        raise click.Abort()

    uvicorn.run(
        "requestor.api.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )

