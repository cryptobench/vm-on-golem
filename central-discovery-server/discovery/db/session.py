"""Compatibility module alias for ``discovery.db.session``."""

import sys

from central_discovery.db import session as _session

sys.modules[__name__] = _session
