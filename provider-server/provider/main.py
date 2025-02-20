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
        # Initialize port manager (verification already done in run.py)
        logger.process("🔄 Initializing port manager...")
        port_manager = PortManager()
        app.state.port_manager = port_manager
        
        # Create resource tracker
        logger.process("🔄 Initializing resource tracker...")
        resource_tracker = ResourceTracker()
        app.state.resource_tracker = resource_tracker
        
        # Create provider with resource tracker and port manager
        logger.process("🔄 Initializing VM provider...")
        provider = MultipassProvider(resource_tracker, port_manager=port_manager)
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
    # Display startup animation
    await startup_animation()
    # Initialize provider
    await setup_provider()

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
    import os
    from pathlib import Path
    
    # Check if multipass is installed
    multipass_path = os.environ.get('GOLEM_PROVIDER_MULTIPASS_BINARY_PATH', '/usr/local/bin/multipass')
    if not Path(multipass_path).exists():
        logger.error(f"Multipass binary not found at {multipass_path}")
        return False
        
    # Check required directories
    vm_data_dir = os.environ.get(
        'GOLEM_PROVIDER_VM_DATA_DIR',
        str(Path.home() / '.golem' / 'provider' / 'vms')
    )
    ssh_key_dir = os.environ.get(
        'GOLEM_PROVIDER_SSH_KEY_DIR',
        str(Path.home() / '.golem' / 'provider' / 'ssh')
    )
    proxy_state_dir = os.environ.get(
        'GOLEM_PROVIDER_PROXY_STATE_DIR',
        str(Path.home() / '.golem' / 'provider' / 'proxy')
    )
    
    try:
        # Create and secure directories
        for directory in [vm_data_dir, ssh_key_dir, proxy_state_dir]:
            path = Path(directory)
            path.mkdir(parents=True, exist_ok=True)
            if directory == ssh_key_dir:
                path.chmod(0o700)  # Secure permissions for SSH keys
    except Exception as e:
        logger.error(f"Failed to create required directories: {e}")
        return False
        
    return True

async def verify_ports():
    """Verify port accessibility before starting server."""
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
        return False
    
    logger.success(f"✅ Port verification successful - {len(port_manager.verified_ports)} ports available")
    return True

def start():
    """Start the provider server."""
    import sys
    import asyncio
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

        # Verify ports before starting server
        if not asyncio.run(verify_ports()):
            logger.error("Port verification failed")
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
