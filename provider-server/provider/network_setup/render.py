from .domain import SetupStageState, StartupSetupStatus

_MARKERS = {
    SetupStageState.PENDING: ".",
    SetupStageState.RUNNING: "-",
    SetupStageState.SUCCESS: "OK",
    SetupStageState.FAILED: "!!",
}


def render_startup_panel(status: StartupSetupStatus) -> str:
    """Render a compact ASCII status panel for CLI startup."""
    failed = status.failed
    title = (
        "Secure Connection Setup Needs Attention"
        if failed
        else "Golem Provider Secure Connection Setup"
    )
    width = 46
    lines = [_border_top(width), _row(title, width), _border_mid(width)]
    for stage in status.stages:
        marker = _MARKERS[stage.state]
        label = _clip(f"{marker} {stage.label}", 27)
        detail = stage.detail or (
            "waiting" if stage.state == SetupStageState.PENDING else stage.state.value
        )
        lines.append(_row(f"{label:<28}{detail}", width))
    lines.append(_border_mid(width))
    message = status.message
    if not message:
        message = (
            "Golem Provider cannot start in direct mode."
            if failed
            else "Starting provider..."
        )
    for part in _wrap(message, width - 4):
        lines.append(_row(part, width))
    lines.append(_border_bottom(width))
    return "\n".join(lines)


def _border_top(width: int) -> str:
    return "+" + "-" * width + "+"


def _border_mid(width: int) -> str:
    return "+" + "-" * width + "+"


def _border_bottom(width: int) -> str:
    return "+" + "-" * width + "+"


def _row(text: str, width: int) -> str:
    clipped = text[:width]
    return "| " + clipped.ljust(width - 2) + " |"


def _clip(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    return text[: width - 1] + "."


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        next_value = word if not current else f"{current} {word}"
        if len(next_value) <= width:
            current = next_value
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]
