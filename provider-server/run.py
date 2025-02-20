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
