import asyncio
import os
from fastapi import FastAPI
from typing import Optional

from .config import settings
from .utils.logging import setup_logger, PROCESS, SUCCESS
from .utils.ascii_art import startup_animation
from .discovery.resource_tracker import ResourceTracker
from .discovery.advertiser import ResourceAdvertiser
from .vm.multipass import MultipassProvider
from .vm.port_manager import PortManager

logger = setup_logger(__name__)

app = FastAPI(title="VM on Golem Provider")

async def setup_provider() -> None:
    """Setup and initialize the provider components."""
    try:
        # Port manager is already initialized and verified in startup_event
        port_manager = app.state.port_manager
        
        # Create resource tracker
        logger.process("🔄 Initializing resource tracker...")
        resource_tracker = ResourceTracker()
        app.state.resource_tracker = resource_tracker
        
        # Create provider with resource tracker and port manager
        logger.process("🔄 Initializing VM provider...")
        provider = MultipassProvider(resource_tracker, port_manager=port_manager)
        try:
            await asyncio.wait_for(provider.initialize(), timeout=30)
            
            # Store provider and proxy manager references
            app.state.provider = provider
            app.state.proxy_manager = provider.proxy_manager
            
            # Restore proxy configurations
            logger.process("🔄 Restoring proxy configurations...")
            await app.state.proxy_manager._load_state()
            
        except asyncio.TimeoutError:
            logger.error("Provider initialization timed out")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize provider: {e}")
            raise
        
        # Create and start advertiser in background
        logger.process("🔄 Starting resource advertiser...")
        advertiser = ResourceAdvertiser(
            resource_tracker=resource_tracker,
            discovery_url=settings.DISCOVERY_URL,
            provider_id=settings.PROVIDER_ID
        )
        
        # Start advertiser in background task
        app.state.advertiser_task = asyncio.create_task(advertiser.start())
        app.state.advertiser = advertiser
        
        logger.success("✨ Provider setup complete and ready to accept requests")
    except Exception as e:
        logger.error(f"Failed to setup provider: {e}")
        # Attempt cleanup of any initialized components
        await cleanup_provider()
        raise

async def cleanup_provider() -> None:
    """Cleanup provider components."""
    cleanup_errors = []
    
    # Stop advertiser
    if hasattr(app.state, "advertiser"):
        try:
            await app.state.advertiser.stop()
            if hasattr(app.state, "advertiser_task"):
                app.state.advertiser_task.cancel()
                try:
                    await app.state.advertiser_task
                except asyncio.CancelledError:
                    pass
        except Exception as e:
            cleanup_errors.append(f"Failed to stop advertiser: {e}")
    
    # Cleanup proxy manager first to stop all proxy servers
    if hasattr(app.state, "proxy_manager"):
        try:
            await asyncio.wait_for(app.state.proxy_manager.cleanup(), timeout=30)
        except asyncio.TimeoutError:
            cleanup_errors.append("Proxy manager cleanup timed out")
        except Exception as e:
            cleanup_errors.append(f"Failed to cleanup proxy manager: {e}")
    
    # Cleanup provider
    if hasattr(app.state, "provider"):
        try:
            await asyncio.wait_for(app.state.provider.cleanup(), timeout=30)
        except asyncio.TimeoutError:
            cleanup_errors.append("Provider cleanup timed out")
        except Exception as e:
            cleanup_errors.append(f"Failed to cleanup provider: {e}")
    
    if cleanup_errors:
        error_msg = "\n".join(cleanup_errors)
        logger.error(f"Errors during cleanup:\n{error_msg}")
    else:
        logger.success("✨ Provider cleanup complete")

@app.on_event("startup")
async def startup_event():
    """Handle application startup."""
    try:
        # Display startup animation
        await startup_animation()

        # Verify ports first
        from .vm.port_manager import PortManager
        from .utils.port_display import PortVerificationDisplay
        from .config import settings

        display = PortVerificationDisplay(
            provider_port=settings.PORT,
            port_range_start=settings.PORT_RANGE_START,
            port_range_end=settings.PORT_RANGE_END
        )
        display.print_header()

        # Initialize port manager
        logger.process("🔄 Verifying port accessibility...")
        port_manager = PortManager(
            start_port=settings.PORT_RANGE_START,
            end_port=settings.PORT_RANGE_END,
            discovery_port=settings.PORT
        )
        if not await port_manager.initialize():
            logger.error("Port verification failed. Please ensure:")
            logger.error(f"1. Port {settings.PORT} is accessible for provider access")
            logger.error(f"2. Some ports in range {settings.PORT_RANGE_START}-{settings.PORT_RANGE_END} are accessible for VM access")
            logger.error("3. Your firewall/router is properly configured")
            raise RuntimeError("Port verification failed")

        logger.success(f"✅ Port verification successful - {len(port_manager.verified_ports)} ports available")
        
        # Store port manager in app state for later use
        app.state.port_manager = port_manager

        # Initialize provider
        await setup_provider()
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        # Ensure proper cleanup
        await cleanup_provider()
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Handle application shutdown."""
    await cleanup_provider()

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

def start():
    """Start the provider server."""
    import sys
    from pathlib import Path
    from dotenv import load_dotenv
    import uvicorn
    from .utils.logging import setup_logger
    from .config import settings
    
    # Configure logging with debug mode
    logger = setup_logger(__name__, debug=True)
    
    try:
        # Load environment variables from .env file
        env_path = Path(__file__).parent.parent / '.env'
        load_dotenv(dotenv_path=env_path)
        
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
        if not asyncio.run(verify_provider_port(settings.PORT)):
            logger.error(f"Provider port {settings.PORT} is not available")
            sys.exit(1)
        
        # Configure uvicorn logging
        log_config = uvicorn.config.LOGGING_CONFIG
        log_config["formatters"]["access"]["fmt"] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        
        # Run server
        logger.process(f"🚀 Starting provider server on {settings.HOST}:{settings.PORT}")
        uvicorn.run(
            "provider:app",
            host=settings.HOST,
            port=settings.PORT,
            reload=settings.DEBUG,
            log_level="info" if not settings.DEBUG else "debug",
            log_config=log_config,
            timeout_keep_alive=60,  # Increase keep-alive timeout
            limit_concurrency=100,  # Limit concurrent connections
        )
    except Exception as e:
        logger.error(f"Failed to start provider server: {e}")
        sys.exit(1)
