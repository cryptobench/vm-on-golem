import asyncio
import types
import sys
import runpy
import pytest


@pytest.mark.asyncio
async def test_cleanup_task_branches_and_cancel(monkeypatch):
    import discovery.main as m

    async def fake_cleanup_ok(self):
        return 1

    # Patch repo method to simulate removals
    monkeypatch.setattr(m.AdvertisementRepository, "cleanup_expired", fake_cleanup_ok, raising=False)
    monkeypatch.setattr(m.settings, "CLEANUP_INTERVAL_SECONDS", 0.01, raising=False)

    task = asyncio.create_task(m.cleanup_expired_advertisements())
    # Let it run one iteration
    await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Now force exception branch
    async def fake_cleanup_fail(self):
        raise RuntimeError("boom")

    monkeypatch.setattr(m.AdvertisementRepository, "cleanup_expired", fake_cleanup_fail, raising=False)
    task = asyncio.create_task(m.cleanup_expired_advertisements())
    await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def test_startup_and_shutdown_exception_paths(monkeypatch):
    import discovery.main as m

    def boom_init():
        raise RuntimeError("init boom")

    def boom_cleanup():
        raise RuntimeError("cleanup boom")

    monkeypatch.setattr(m, "init_db", boom_init)
    with pytest.raises(RuntimeError):
        # Directly call the handler
        asyncio.get_event_loop().run_until_complete(m.startup_event())

    monkeypatch.setattr(m, "cleanup_db", boom_cleanup)
    # Should not raise
    asyncio.get_event_loop().run_until_complete(m.shutdown_event())


def test_main_guard_executes_start(monkeypatch):
    # Ensure __main__ guard triggers start() when run as module
    # Provide fake uvicorn again to prevent actual server
    called = {}
    fake_uvicorn = types.SimpleNamespace(run=lambda *a, **k: called.update({"ok": True}))
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)

    runpy.run_module("discovery.main", run_name="__main__")
    assert called.get("ok") is True

