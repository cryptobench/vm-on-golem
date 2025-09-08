import asyncio
import os
import socket
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from .config import settings, ensure_config
from .utils.logging import setup_logger
from .utils.ascii_art import startup_animation
from .discovery.resource_tracker import ResourceTracker
from .discovery.advertiser import DiscoveryServerAdvertiser
from .container import Container
from .service import ProviderService


logger = setup_logger(__name__)

app = FastAPI(title="VM on Golem Provider")
container = Container()
container.config.from_pydantic(settings)
app.container = container
container.wire(modules=[".api.routes"])

from .vm.models import VMNotFoundError
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(VMNotFoundError)
async def vm_not_found_exception_handler(request: Request, exc: VMNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"message": str(exc)},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"message": "An unexpected error occurred"},
    )

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.on_event("startup")
async def startup_event():
    """Handle application startup."""
    provider_service = container.provider_service()
    await provider_service.setup(app)


@app.on_event("shutdown")
async def shutdown_event():
    """Handle application shutdown."""
    provider_service = container.provider_service()
    await provider_service.cleanup()

# Import routes after app creation to avoid circular imports
from .api import routes
app.include_router(routes.router, prefix="/api/v1")

# Export app for uvicorn
__all__ = ["app", "start"]


def check_requirements():
    """Check if all requirements are met."""
    try:
        # Import settings to trigger validation
        from .config import settings
        return True
    except Exception as e:
        logger.error(f"Requirements check failed: {e}")
        return False


async def verify_provider_port(port: int) -> bool:
    """Verify that the provider port is available for binding.

    Args:
        port: The port to verify

    Returns:
        bool: True if the port is available, False otherwise
    """
    try:
        # Try to create a temporary listener
        server = await asyncio.start_server(
            lambda r, w: None,  # Empty callback
            '0.0.0.0',
            port
        )
        server.close()
        await server.wait_closed()
        logger.info(f"✅ Provider port {port} is available")
        return True
    except Exception as e:
        logger.error(f"❌ Provider port {port} is not available: {e}")
        logger.error("Please ensure:")
        logger.error(f"1. Port {port} is not in use by another application")
        logger.error("2. You have permission to bind to this port")
        logger.error("3. Your firewall allows binding to this port")
        return False


# The get_local_ip function has been removed as this logic is now handled in config.py


import typer
try:
    from importlib import metadata
except ImportError:
    # Python < 3.8
    import importlib_metadata as metadata

cli = typer.Typer()

def print_version(ctx: typer.Context, value: bool):
    if not value:
        return
    try:
        version = metadata.version('golem-vm-provider')
    except metadata.PackageNotFoundError:
        version = 'unknown'
    print(f'Provider VM on Golem CLI version {version}')
    raise typer.Exit()

@cli.callback()
def main(
    version: bool = typer.Option(None, "--version", callback=print_version, is_eager=True, help="Show the version and exit.")
):
    ensure_config()
    pass

@cli.command()
def start(no_verify_port: bool = typer.Option(False, "--no-verify-port", help="Skip provider port verification.")):
    """Start the provider server."""
    run_server(dev_mode=False, no_verify_port=no_verify_port)

@cli.command()
def dev(no_verify_port: bool = typer.Option(True, "--no-verify-port", help="Skip provider port verification.")):
    """Start the provider server in development mode."""
    run_server(dev_mode=True, no_verify_port=no_verify_port)

def run_server(dev_mode: bool, no_verify_port: bool):
    """Helper to run the uvicorn server."""
    import sys
    from pathlib import Path
    from dotenv import load_dotenv
    import uvicorn
    # Load appropriate .env file
    env_file = ".env.dev" if dev_mode else ".env"
    env_path = Path(__file__).parent.parent / env_file
    load_dotenv(dotenv_path=env_path)
    
    # The logic for setting the public IP in dev mode is now handled in config.py
    # The following lines are no longer needed and have been removed.

    # Import settings after loading env
    from .config import settings

    # Configure logging with debug mode
    logger = setup_logger(__name__, debug=dev_mode)

    try:
        # Log environment variables
        logger.info("Environment variables:")
        for key, value in os.environ.items():
            if key.startswith('GOLEM_PROVIDER_'):
                logger.info(f"{key}={value}")

        # Check requirements
        if not check_requirements():
            logger.error("Requirements check failed")
            sys.exit(1)

        # Verify provider port is available
        if not no_verify_port and not asyncio.run(verify_provider_port(settings.PORT)):
            logger.error(f"Provider port {settings.PORT} is not available")
            sys.exit(1)

        # Configure uvicorn logging
        log_config = uvicorn.config.LOGGING_CONFIG
        log_config["formatters"]["access"]["fmt"] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        # Run server
        logger.process(
            f"🚀 Starting provider server on {settings.HOST}:{settings.PORT}")
        uvicorn.run(
            "provider:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=settings.DEBUG,
            log_level="debug" if dev_mode else "info",
            log_config=log_config,
            timeout_keep_alive=60,  # Increase keep-alive timeout
            limit_concurrency=100,  # Limit concurrent connections
        )
    except Exception as e:
        logger.error(f"Failed to start provider server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    cli()
