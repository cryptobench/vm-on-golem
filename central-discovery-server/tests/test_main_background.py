import runpy
import sys
import types

import pytest


@pytest.mark.asyncio
async def test_startup_and_shutdown_are_visible_lifecycle_hooks(caplog):
    import central_discovery.main as main

    caplog.set_level("INFO")
    await main.startup_event()
    await main.shutdown_event()

    assert "Starting central discovery service" in caplog.text
    assert "Shutting down central discovery service" in caplog.text


def test_main_guard_executes_start(monkeypatch):
    called = {}
    fake_uvicorn = types.SimpleNamespace(
        run=lambda *args, **kwargs: called.update({"ok": True})
    )
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)

    runpy.run_module("central_discovery.main", run_name="__main__")
    assert called.get("ok") is True
