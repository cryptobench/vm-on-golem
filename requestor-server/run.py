#!/usr/bin/env python3
"""Development entry point for VM on Golem requestor CLI."""

import asyncio
from requestor.cli.commands import main

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)
