#!/usr/bin/env python3
import os
import sys
import uvicorn
from pathlib import Path
from dotenv import load_dotenv

from provider.utils.logging import setup_logger

# Configure logging with debug mode
logger = setup_logger(__name__, debug=True)

def check_requirements():
    """Check if all requirements are met."""
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
    from provider.vm.port_manager import PortManager
    from provider.utils.port_display import PortVerificationDisplay

    # Import settings after loading environment variables
    from provider.config import settings
    
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

def main():
    """Run the provider server."""
    try:
        # Load environment variables from .env file
        env_path = Path(__file__).parent / '.env'
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

        # Import settings after loading environment variables
        from provider.config import settings

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

if __name__ == "__main__":
    main()
