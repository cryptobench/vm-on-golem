#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

from requestor.utils.logging import setup_logger
from requestor.cli.commands import cli

# Configure logging with debug mode from environment variable
logger = setup_logger(__name__)

def check_requirements():
    """Check if all requirements are met."""
    # Check required directories
    ssh_key_dir = os.environ.get(
        'GOLEM_REQUESTOR_SSH_KEY_DIR',
        str(Path.home() / '.golem' / 'requestor' / 'ssh')
    )
    
    try:
        # Create and secure directories
        path = Path(ssh_key_dir)
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o700)  # Secure permissions for SSH keys
    except Exception as e:
        logger.error(f"Failed to create required directories: {e}")
        return False
        
    return True

def main():
    """Run the requestor CLI."""
    try:
        # Load environment variables from .env file
        env_path = Path(__file__).parent / '.env'
        load_dotenv(dotenv_path=env_path)

        # Check requirements
        if not check_requirements():
            logger.error("Requirements check failed")
            sys.exit(1)

        # Run CLI
        cli()
    except Exception as e:
        logger.error(f"Failed to start requestor CLI: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
