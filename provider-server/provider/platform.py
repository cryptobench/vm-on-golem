import platform


def current_platform() -> str | None:
    """Return canonical provider CPU platform for discovery/API metadata."""

    raw = (platform.machine() or "").lower()
    if not raw:
        return None
    if "aarch64" in raw or "arm64" in raw or raw.startswith("arm"):
        return "arm64"
    if "x86_64" in raw or "amd64" in raw or "x64" in raw:
        return "x86_64"
    return raw
