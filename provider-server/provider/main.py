import asyncio
import logging
from fastapi import FastAPI
from typing import Optional

from .config import settings
from .discovery.resource_tracker import ResourceTracker
from .discovery.advertiser import ResourceAdvertiser
from .vm.multipass import MultipassProvider

logger = logging.getLogger(__name__)

app = FastAPI(title="VM on Golem Provider")

async def setup_provider() -> None:
    """Setup and initialize the provider components."""
    try:
        # Create resource tracker
        logger.info("Initializing resource tracker...")
        resource_tracker = ResourceTracker()
        app.state.resource_tracker = resource_tracker
        
        # Create provider with resource tracker
        logger.info("Initializing VM provider...")
        provider = MultipassProvider(resource_tracker)
        try:
            await asyncio.wait_for(provider.initialize(), timeout=30)
            app.state.provider = provider
            
            # Store proxy manager reference for cleanup
            app.state.proxy_manager = provider.proxy_manager
            
        except asyncio.TimeoutError:
            logger.error("Provider initialization timed out")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize provider: {e}")
            raise
        
        # Create and start advertiser in background
        logger.info("Starting resource advertiser...")
        advertiser = ResourceAdvertiser(
            resource_tracker=resource_tracker,
            discovery_url=settings.DISCOVERY_URL,
            provider_id=settings.PROVIDER_ID
        )
        
        # Start advertiser in background task
        app.state.advertiser_task = asyncio.create_task(advertiser.start())
        app.state.advertiser = advertiser
        
        logger.info("Provider setup complete")
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
        logger.info("Provider cleanup complete")

@app.on_event("startup")
async def startup_event():
    """Handle application startup."""
    await setup_provider()

@app.on_event("shutdown")
async def shutdown_event():
    """Handle application shutdown."""
    await cleanup_provider()

# Import routes after app creation to avoid circular imports
from .api import routes
app.include_router(routes.router, prefix="/api/v1")

# Export app for uvicorn
__all__ = ["app"]
