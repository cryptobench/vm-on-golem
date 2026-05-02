"""Compatibility module alias for ``discovery.main``."""

import sys

from central_discovery import main as _main

if __name__ == "__main__":
    _main.start()
else:
    sys.modules[__name__] = _main
