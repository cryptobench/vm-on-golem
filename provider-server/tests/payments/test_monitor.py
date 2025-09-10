import asyncio
import types
import pytest

from provider.payments.monitor import StreamMonitor


class DummyStreamMap:
    def __init__(self, mapping):
        self._mapping = mapping
    async def all_items(self):
        return dict(self._mapping)
    async def remove(self, vm_id):
        self._mapping.pop(vm_id, None)


class DummyVMService:
    def __init__(self):
        self.stopped = []
        self.deleted = []
    async def stop_vm(self, vm_id):
        self.stopped.append(vm_id)
    async def delete_vm(self, vm_id):
        self.deleted.append(vm_id)


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
async def test_monitor_does_not_stop_until_empty_and_withdraws(monkeypatch):
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

    # Should NOT stop while runway remains; but withdraw should occur
    assert vm_service.stopped == []
    # Withdraw should have been attempted (vested - withdrawn threshold met)
    assert client.withdrawn == [42]


@pytest.mark.asyncio
async def test_monitor_respects_withdraw_interval(monkeypatch):
    now = 2_000_000
    stream = {
        "token": "0xglm",
        "sender": "0xreq",
        "recipient": "0xprov",
        "startTime": now - 10_000,
        "stopTime": now + 10_000,
        "ratePerSecond": 10,
        "deposit": 200_000,
        "withdrawn": 0,
        "halted": False,
    }
    class S(DummySettings):
        STREAM_WITHDRAW_INTERVAL_SECONDS = 10
    settings = S()
    stream_map = DummyStreamMap({"vm-1": 7})
    vm_service = DummyVMService()
    reader = DummyReader(now, stream)
    client = DummyClient()
    mon = StreamMonitor(stream_map=stream_map, vm_service=vm_service, reader=reader, client=client, settings=settings)

    ticks = {"n": 0}
    async def fake_sleep(_):
        ticks["n"] += 1
        # advance time by 1 sec each loop
        reader._now += 1
        if ticks["n"] >= 3:
            raise asyncio.CancelledError
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    await mon._run()
    # Only one withdraw due to interval gating
    assert client.withdrawn == [7]


@pytest.mark.asyncio
async def test_monitor_accepts_dict_settings_and_does_not_stop_until_empty(monkeypatch):
    now = 3_000_000
    stream = {
        "token": "0xglm",
        "sender": "0xreq",
        "recipient": "0xprov",
        "startTime": now - 10_000,
        "stopTime": now + 100,  # trigger stop due to low remaining
        "ratePerSecond": 10,
        "deposit": 200_000,
        "withdrawn": 50_000,
        "halted": False,
    }

    class DictSettings(dict):
        pass

    settings = DictSettings({
        "STREAM_MONITOR_ENABLED": True,
        "STREAM_WITHDRAW_ENABLED": True,
        "STREAM_MONITOR_INTERVAL_SECONDS": 0,
        "STREAM_WITHDRAW_INTERVAL_SECONDS": 0,
        "STREAM_MIN_REMAINING_SECONDS": 3600,
        "STREAM_MIN_WITHDRAW_WEI": 100,
    })
    stream_map = DummyStreamMap({"vm-1": 5})
    vm_service = DummyVMService()
    reader = DummyReader(now, stream)
    client = DummyClient()
    mon = StreamMonitor(stream_map=stream_map, vm_service=vm_service, reader=reader, client=client, settings=settings)

    calls = {"n": 0}
    async def fake_sleep(_):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise asyncio.CancelledError
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    await mon._run()
    assert vm_service.stopped == []
    assert client.withdrawn == [5]


@pytest.mark.asyncio
async def test_monitor_deletes_when_stream_halted(monkeypatch):
    now = 4_000_000
    stream = {
        "token": "0xglm",
        "sender": "0xreq",
        "recipient": "0xprov",
        "startTime": now - 10_000,
        "stopTime": now + 10_000,
        "ratePerSecond": 10,
        "deposit": 200_000,
        "withdrawn": 0,
        "halted": True,
    }
    stream_map = DummyStreamMap({"vm-del": 11})
    vm_service = DummyVMService()
    reader = DummyReader(now, stream)
    client = DummyClient()
    settings = DummySettings()
    mon = StreamMonitor(stream_map=stream_map, vm_service=vm_service, reader=reader, client=client, settings=settings)

    calls = {"n": 0}
    async def fake_sleep(_):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise asyncio.CancelledError
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    await mon._run()
    # VM deleted due to halted stream, not just stopped
    assert vm_service.deleted == ["vm-del"]
    # No withdraw attempt for inactive stream path
    assert client.withdrawn == []


@pytest.mark.asyncio
async def test_monitor_stops_when_stream_ended(monkeypatch):
    now = 5_000_000
    stream = {
        "token": "0xglm",
        "sender": "0xreq",
        "recipient": "0xprov",
        "startTime": now - 10_000,
        "stopTime": now,  # ended
        "ratePerSecond": 10,
        "deposit": 200_000,
        "withdrawn": 0,
        "halted": False,
    }
    stream_map = DummyStreamMap({"vm-end": 12})
    vm_service = DummyVMService()
    reader = DummyReader(now, stream)
    client = DummyClient()
    settings = DummySettings()
    mon = StreamMonitor(stream_map=stream_map, vm_service=vm_service, reader=reader, client=client, settings=settings)

    calls = {"n": 0}
    async def fake_sleep(_):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise asyncio.CancelledError
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    await mon._run()
    # VM stopped (not deleted) due to exhausted runway
    assert vm_service.stopped == ["vm-end"]
    assert vm_service.deleted == []
    assert client.withdrawn == []
