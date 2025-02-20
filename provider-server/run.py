#!/usr/bin/env python3
import os
import sys
import asyncio
import uvicorn
from pathlib import Path
from dotenv import load_dotenv

from provider.utils.logging import setup_logger

# Configure logging with debug mode
logger = setup_logger(__name__, debug=True)

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

def check_requirements():
    """Check if all requirements are met."""
    try:
        # Import settings to trigger validation
        from provider.config import settings
        return True
    except Exception as e:
        logger.error(f"Requirements check failed: {e}")
        return False

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

if __name__ == "__main__":
    main()
