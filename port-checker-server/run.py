#!/usr/bin/env python3
import os
import sys
import uvicorn
from pathlib import Path
from dotenv import load_dotenv

# Configure logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Run the port checker server."""
    try:
        # Load environment variables from .env file
        env_path = Path(__file__).parent / '.env'
        load_dotenv(dotenv_path=env_path)

        # Get configuration from environment
        host = os.getenv('PORT_CHECKER_HOST', '0.0.0.0')
        port = int(os.getenv('PORT_CHECKER_PORT', '7466'))
        debug = os.getenv('PORT_CHECKER_DEBUG', 'false').lower() == 'true'

        # Configure uvicorn logging
        log_config = uvicorn.config.LOGGING_CONFIG
        log_config["formatters"]["access"]["fmt"] = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        
        # Run server
        logger.info(f"🚀 Starting port checker server on {host}:{port}")
        uvicorn.run(
            "port_checker.main:app",
            host=host,
            port=port,
            reload=debug,
            log_level="debug" if debug else "info",
            log_config=log_config,
            timeout_keep_alive=60,
            limit_concurrency=100,
        )
    except Exception as e:
        logger.error(f"Failed to start port checker server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
