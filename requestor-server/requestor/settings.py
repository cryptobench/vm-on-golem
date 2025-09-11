import json
from pathlib import Path
from typing import Literal, TypedDict

from .config import config


class _Prefs(TypedDict, total=False):
    price_display: Literal["fiat", "native"]


_PREFS_FILE = config.base_dir / "settings.json"


def _read_prefs() -> _Prefs:
    try:
        if _PREFS_FILE.exists():
            data = json.loads(_PREFS_FILE.read_text())
            if isinstance(data, dict):
                return data  # type: ignore[return-value]
    except Exception:
        pass
    return {}


def _write_prefs(p: _Prefs) -> None:
    try:
        _PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(str(_PREFS_FILE) + ".tmp")
        tmp.write_text(json.dumps(p, indent=2))
        tmp.replace(_PREFS_FILE)
    except Exception:
        # Best-effort persistence; ignore write errors
        pass


def get_price_display() -> Literal["fiat", "native"]:
    prefs = _read_prefs()
    mode = prefs.get("price_display")
    if mode in ("fiat", "native"):
        return mode
    return "fiat"


def set_price_display(mode: Literal["fiat", "native"]) -> None:
    prefs = _read_prefs()
    prefs["price_display"] = mode
    _write_prefs(prefs)

