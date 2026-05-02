#!/usr/bin/env python3

import logging
import sys

from port_checker.main import start

logger = logging.getLogger(__name__)


def main():
    """Run the port checker server."""
    try:
        start()
    except Exception as exc:
        logger.error("Failed to start port checker server: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
