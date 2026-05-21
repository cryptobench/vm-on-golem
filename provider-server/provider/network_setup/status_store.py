import json
import os
from pathlib import Path
from typing import Any

from .domain import StartupSetupStatus


STATUS_FILENAME = "network_setup_status.json"


def startup_setup_status_path(settings: Any) -> Path:
    return Path(settings.PROXY_STATE_DIR) / STATUS_FILENAME


def write_startup_setup_status(settings: Any, status: StartupSetupStatus) -> None:
    path = startup_setup_status_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    tmp_path.write_text(json.dumps(status.model_dump(mode="json"), indent=2))
    os.replace(tmp_path, path)


def read_startup_setup_status(settings: Any) -> StartupSetupStatus | None:
    path = startup_setup_status_path(settings)
    if not path.exists():
        return None
    try:
        status = StartupSetupStatus.model_validate_json(path.read_text())
    except Exception as exc:
        raise RuntimeError(
            f"Failed to read startup setup status from {path}: {exc}"
        ) from exc

    start = getattr(settings, "PORT_RANGE_START", None)
    end = getattr(settings, "PORT_RANGE_END", None)
    if (
        status.vm_port_range_start is not None
        and start is not None
        and int(status.vm_port_range_start) != int(start)
    ):
        return None
    if (
        status.vm_port_range_end is not None
        and end is not None
        and int(status.vm_port_range_end) != int(end)
    ):
        return None
    return status
