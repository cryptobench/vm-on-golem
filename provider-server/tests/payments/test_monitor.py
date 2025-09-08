import asyncio
import types
import pytest

from provider.payments.monitor import StreamMonitor


class DummyStreamMap:
    def __init__(self, mapping):
        self._mapping = mapping
    async def all_items(self):
        return dict(self._mapping)


class DummyVMService:
    def __init__(self):
        self.stopped = []
    async def stop_vm(self, vm_id):
        self.stopped.append(vm_id)


class DummyReader:
    def __init__(self, now, stream):
        self._now = now
        self._stream = stream
        self.web3 = types.SimpleNamespace(eth=types.SimpleNamespace(get_block=lambda x: {"timestamp": self._now}))
    def get_stream(self, stream_id):
        return dict(self._stream)


class DummyClient:
    def __init__(self):
        self.withdrawn = []
    def withdraw(self, sid):
        self.withdrawn.append(sid)


class DummySettings:
    STREAM_MONITOR_ENABLED = True
    STREAM_WITHDRAW_ENABLED = True
    STREAM_MONITOR_INTERVAL_SECONDS = 0
    STREAM_WITHDRAW_INTERVAL_SECONDS = 0
    STREAM_MIN_REMAINING_SECONDS = 3600
    STREAM_MIN_WITHDRAW_WEI = 100


@pytest.mark.asyncio
async def test_monitor_stops_low_runway_and_withdraws(monkeypatch):
    # Prepare a stream that started long ago with small remaining runway and some withdrawable amount
    now = 1_000_000
    stream = {
        "token": "0xglm",
        "sender": "0xreq",
        "recipient": "0xprov",
        "startTime": now - 10_000,
        "stopTime": now + 100,  # only 100s left
        "ratePerSecond": 10,
        "deposit": 200_000,
        "withdrawn": 50_000,
        "halted": False,
    }

    stream_map = DummyStreamMap({"vm-1": 42})
    vm_service = DummyVMService()
    reader = DummyReader(now, stream)
    client = DummyClient()
    settings = DummySettings()

    mon = StreamMonitor(stream_map=stream_map, vm_service=vm_service, reader=reader, client=client, settings=settings)

    # Make sleep run once, then cancel so the loop runs a single iteration
    calls = {"n": 0}
    async def fake_sleep(_):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise asyncio.CancelledError
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    await mon._run()

    # VM should be stopped due to low remaining runway
    assert vm_service.stopped == ["vm-1"]
    # Withdraw should have been attempted (vested - withdrawn threshold met)
    assert client.withdrawn == [42]
