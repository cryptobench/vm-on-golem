#!/usr/bin/env python3
"""Export FastAPI OpenAPI JSON for a service."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

SERVICES = {
    "central-discovery": {
        "path": ROOT / "central-discovery-server",
        "module": "central_discovery.main",
        "app": "app",
    },
    "port-checker": {
        "path": ROOT / "port-checker-server",
        "module": "port_checker.app",
        "factory": "create_app",
    },
    "provider": {
        "path": ROOT / "provider-server",
        "module": "provider.app",
        "factory": "create_app",
    },
    "requestor": {
        "path": ROOT / "requestor-server",
        "module": "requestor.api.main",
        "app": "app",
    },
}


def _load_app(service: str) -> Any:
    config = SERVICES[service]
    sys.path.insert(0, str(config["path"]))
    module = importlib.import_module(config["module"])
    if "factory" in config:
        return getattr(module, config["factory"])()
    return getattr(module, config["app"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", choices=sorted(SERVICES))
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    app = _load_app(args.service)
    schema = app.openapi()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
