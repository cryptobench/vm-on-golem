import os
import re
from pathlib import Path
from typing import Mapping


def active_provider_env_path(environment: str | None = None) -> str:
    env = (
        environment
        or os.environ.get("GOLEM_ENVIRONMENT")
        or os.environ.get("GOLEM_PROVIDER_ENVIRONMENT")
        or ""
    )
    env_file = ".env.dev" if env.strip().lower() == "development" else ".env"
    return str(Path(__file__).parent.parent / env_file)


def provider_env_path_for(dev_mode: bool | None) -> str:
    return active_provider_env_path("development" if dev_mode else "production")


def write_env_vars(path: str, updates: Mapping[str, object]) -> None:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        lines = []

    pattern = re.compile(r"^(?P<k>[A-Z0-9_]+)=.*$")
    out: list[str] = []
    seen: set[str] = set()
    keys = {str(key): value for key, value in updates.items()}

    for line in lines:
        match = pattern.match(line.strip())
        if not match:
            out.append(line)
            continue
        key = match.group("k")
        if key in keys:
            out.append(f"{key}={keys[key]}\n")
            seen.add(key)
        else:
            out.append(line)

    for key, value in keys.items():
        if key not in seen:
            out.append(f"{key}={value}\n")

    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(out)
