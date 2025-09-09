import asyncio
import types
import pytest

from requestor.payments.monitor import RequestorStreamMonitor


class DummyDB:
    def __init__(self, vms):
        self._vms = vms
    async def list_vms(self):
        return list(self._vms)


@pytest.mark.asyncio
async def test_requestor_monitor_topups_when_below_min(monkeypatch):
    # VM with running status and no local stream_id in config; monitor will use resolver
    vms = [{
        "name": "vm-1",
        "provider_ip": "127.0.0.1",
        "vm_id": "id-1",
        "status": "running",
        "config": {}
    }]
    db = DummyDB(vms)
    mon = RequestorStreamMonitor(db)

    # Resolve stream id without network
    async def fake_resolve(vm):
        return 42
    monkeypatch.setattr(mon, "_resolve_stream_id", fake_resolve)

    # Stub web3 time and contract streams call
    now = 1_000_000
    rate = 10
    stop_time = now + 1000  # 1000s remaining
    # contract.functions.streams(stream_id).call() should return tuple
    class Fn:
        def __init__(self):
            pass
        def call(self):
            return (
                "0x0",  # token
                "0xsender",
                "0xrecipient",
                now - 10_000,  # startTime
                stop_time,
                rate,  # ratePerSecond
                0,     # deposit
                0,     # withdrawn
                False, # halted
            )
    class Contract:
        def __init__(self):
            self.functions = types.SimpleNamespace(streams=lambda _: Fn())
    mon._sp.contract = Contract()
    mon._sp.web3 = types.SimpleNamespace(eth=types.SimpleNamespace(get_block=lambda _: {"timestamp": now}))

    # Capture top_up calls
    calls = {"args": []}
    def top_up(sid, amount):
        calls["args"].append((sid, amount))
    monkeypatch.setattr(mon._sp, "top_up", top_up)

    # Make sleep cancel after first iteration
    async def fake_sleep(_):
        raise asyncio.CancelledError
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    # Run monitor loop for one iteration
    await mon._run()

    # Expect a top-up to 3600s target: deficit = 3600 - 1000 = 2600; add_wei = deficit * rate
    assert calls["args"] == [(42, 2600 * rate)]

