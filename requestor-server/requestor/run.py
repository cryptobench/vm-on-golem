#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

if "--json" in sys.argv:
    os.environ["GOLEM_SILENCE_LOGS"] = "1"
    try:
        import logging as _logging
        _logging.getLogger().setLevel(_logging.CRITICAL)
        _logging.getLogger('rlp').setLevel(_logging.CRITICAL)
        _logging.getLogger('rlp.codec').setLevel(_logging.CRITICAL)
    except Exception:
        pass

from requestor.utils.logging import setup_logger

# Configure logging with debug mode from environment variable
logger = setup_logger(__name__)


def get_ssh_key_dir() -> Path:
    """Return the path to the SSH key directory."""
    return Path(
        os.environ.get(
            "GOLEM_REQUESTOR_SSH_KEY_DIR",
            str(Path.home() / ".golem" / "requestor" / "ssh"),
        )
    )


def secure_directory(path: Path) -> bool:
    """Create the directory if needed and set strict permissions."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o700)
    except Exception as e:  # pragma: no cover - OS-related failures
        logger.error(f"Failed to create required directories: {e}")
        return False
    return True


def check_requirements() -> bool:
    """Check if all requirements are met."""
    return secure_directory(get_ssh_key_dir())

def main():
    """Run the requestor CLI."""
    try:
        # Load environment variables based on unified environment
        env_mode = (os.environ.get('GOLEM_ENVIRONMENT') or os.environ.get('GOLEM_REQUESTOR_ENVIRONMENT') or '').lower()
        base_dir = Path(__file__).parent.parent
        env_file = '.env.dev' if env_mode == 'development' else '.env'
        env_path = base_dir / env_file
        # If chosen file does not exist, fallback to the other
        if not env_path.exists():
            alt = base_dir / ('.env' if env_file == '.env.dev' else '.env.dev')
            env_path = alt if alt.exists() else env_path
        load_dotenv(dotenv_path=env_path)
        logger.info(f"Loading environment variables from: {env_path}")

        # Check requirements
        if not check_requirements():
            logger.error("Requirements check failed")
            sys.exit(1)

        # Run CLI
        from requestor.cli.commands import cli

        cli()
    except Exception as e:
        logger.error(f"Failed to start requestor CLI: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
