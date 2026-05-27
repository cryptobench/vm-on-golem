import io
import sys

import pytest
from rich.console import Console

from provider.network.port_verifier import PortVerificationResult, ServerAttempt
from provider.utils import ascii_art
from provider.utils.port_display import PortVerificationDisplay


class Cp1252Stream:
    encoding = "cp1252"

    def __init__(self):
        self._buffer = io.StringIO()

    def write(self, text: str) -> int:
        text.encode(self.encoding)
        return self._buffer.write(text)

    def flush(self) -> None:
        self._buffer.flush()

    def isatty(self) -> bool:
        return True


async def _no_sleep(_seconds: float) -> None:
    return None


async def _no_display_animation(self, text: str, duration: float = 1.0) -> None:
    return None


@pytest.mark.asyncio
async def test_provider_startup_console_output_is_cp1252_safe(monkeypatch):
    stream = Cp1252Stream()
    monkeypatch.setattr(
        ascii_art,
        "console",
        Console(file=stream, force_terminal=True, color_system=None),
    )
    monkeypatch.setattr(ascii_art.asyncio, "sleep", _no_sleep)

    await ascii_art.startup_animation()
    await ascii_art.provider_ready_message(8000)
    await ascii_art.vm_creation_animation("vm-test")
    ascii_art.vm_status_change("vm-test", "running")


@pytest.mark.asyncio
async def test_port_verification_display_output_is_cp1252_safe(monkeypatch):
    stream = Cp1252Stream()
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(
        PortVerificationDisplay, "animate_verification", _no_display_animation
    )

    display = PortVerificationDisplay(
        provider_port=7466,
        port_range_start=50800,
        port_range_end=50803,
    )
    accessible = PortVerificationResult(
        port=7466,
        accessible=True,
        verified_by="local_verification",
        attempts=[ServerAttempt(server="local", success=True)],
    )
    failed = PortVerificationResult(
        port=7466,
        accessible=False,
        error="blocked",
        attempts=[ServerAttempt(server="check", success=False, error="timeout")],
    )

    display.print_header()
    await display.print_discovery_status(accessible)
    await display.print_ssh_status({50800: accessible, 50801: failed})
    display.print_critical_issues(failed, {50800: failed})
    display.print_quick_fix(failed, {50800: failed})
    display.print_summary(None, {})
    display.print_summary(failed, {50800: failed})
    display.print_summary(accessible, {50800: accessible})

    skip_display = PortVerificationDisplay(
        provider_port=7466,
        port_range_start=50800,
        port_range_end=50803,
        skip_verification=True,
    )
    await skip_display.print_ssh_status({})
    skip_display.print_summary(accessible, {})
