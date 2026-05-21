import asyncio
import types

import pytest

from provider.payments.monitor import StreamMonitor


class DummyStreamMap:
    def __init__(self, mapping):
        self._mapping = mapping
        self.terminated = []
        self.cleanup = []

    async def all_items(self):
        return dict(self._mapping)

    async def active_items(self):
        return dict(self._mapping)

    async def remove(self, vm_id):
        self._mapping.pop(vm_id, None)

    async def mark_terminated(self, vm_id, **kwargs):
        self.terminated.append((vm_id, kwargs))

    async def set_cleanup_state(self, vm_id, cleanup_state):
        self.cleanup.append((vm_id, cleanup_state))


class DummyVMApplicationService:
    def __init__(self, *, expire_result=True):
        self.stopped = []
        self.deleted = []
        self.expired = []
        self.expire_result = expire_result

    async def stop_vm(self, vm_id):
        self.stopped.append(vm_id)

    async def delete_vm(self, vm_id):
        self.deleted.append(vm_id)

    async def cleanup_requestor_terminated_stream(self, vm_id, stream_id):
        self.deleted.append(vm_id)

    async def expire_vm_lease(self, vm_id, stream_id):
        self.expired.append((vm_id, stream_id))
        if self.expire_result:
            self.stopped.append(vm_id)
            self.deleted.append(vm_id)
        return self.expire_result


class DummyReader:
    def __init__(self, now, stream):
        self._now = now
        self._stream = stream
        self.web3 = types.SimpleNamespace(
            eth=types.SimpleNamespace(get_block=lambda x: {"timestamp": self._now})
        )

    def get_stream(self, stream_id):
        return dict(self._stream)


class DummyClient:
    def __init__(self):
        self.withdrawn = []

    def withdraw(self, sid):
        self.withdrawn.append(sid)


class CapturingWebhookService:
    def __init__(self):
        self.events = []

    async def emit(self, event_type, **kwargs):
        self.events.append((event_type, kwargs))


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
        "providerRatePerSecond": 10,
        "providerDeposit": 200_000,
        "providerWithdrawn": 50_000,
        "donationBps": 150,
        "donationRecipient": "0x94153E31AA476cE30C3AF64C255C623f80920BfF",
        "donationDeposit": int(200_000 * 150 / 10000),
        "donationWithdrawn": 0,
        "halted": False,
    }

    stream_map = DummyStreamMap({"vm-1": 42})
    vm_service = DummyVMApplicationService()
    reader = DummyReader(now, stream)
    client = DummyClient()
    settings = DummySettings()

    mon = StreamMonitor(
        stream_map=stream_map,
        vm_application_service=vm_service,
        reader=reader,
        client=client,
        settings=settings,
    )

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
        "providerRatePerSecond": 10,
        "providerDeposit": 200_000,
        "providerWithdrawn": 0,
        "donationBps": 150,
        "donationRecipient": "0x94153E31AA476cE30C3AF64C255C623f80920BfF",
        "donationDeposit": int(200_000 * 150 / 10000),
        "donationWithdrawn": 0,
        "halted": False,
    }

    class S(DummySettings):
        STREAM_WITHDRAW_INTERVAL_SECONDS = 10

    settings = S()
    stream_map = DummyStreamMap({"vm-1": 7})
    vm_service = DummyVMApplicationService()
    reader = DummyReader(now, stream)
    client = DummyClient()
    mon = StreamMonitor(
        stream_map=stream_map,
        vm_application_service=vm_service,
        reader=reader,
        client=client,
        settings=settings,
    )

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
        "providerRatePerSecond": 10,
        "providerDeposit": 200_000,
        "providerWithdrawn": 50_000,
        "donationBps": 150,
        "donationRecipient": "0x94153E31AA476cE30C3AF64C255C623f80920BfF",
        "donationDeposit": int(200_000 * 150 / 10000),
        "donationWithdrawn": 0,
        "halted": False,
    }

    class DictSettings(dict):
        pass

    settings = DictSettings(
        {
            "STREAM_MONITOR_ENABLED": True,
            "STREAM_WITHDRAW_ENABLED": True,
            "STREAM_MONITOR_INTERVAL_SECONDS": 0,
            "STREAM_WITHDRAW_INTERVAL_SECONDS": 0,
            "STREAM_MIN_REMAINING_SECONDS": 3600,
            "STREAM_MIN_WITHDRAW_WEI": 100,
        }
    )
    stream_map = DummyStreamMap({"vm-1": 5})
    vm_service = DummyVMApplicationService()
    reader = DummyReader(now, stream)
    client = DummyClient()
    mon = StreamMonitor(
        stream_map=stream_map,
        vm_application_service=vm_service,
        reader=reader,
        client=client,
        settings=settings,
    )

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
async def test_monitor_deletes_when_stream_terminated(monkeypatch):
    now = 4_000_000
    stream = {
        "token": "0xglm",
        "sender": "0xreq",
        "recipient": "0x0000000000000000000000000000000000000000",
        "startTime": now - 10_000,
        "stopTime": now + 10_000,
        "providerRatePerSecond": 10,
        "providerDeposit": 200_000,
        "providerWithdrawn": 0,
        "donationBps": 150,
        "donationRecipient": "0x94153E31AA476cE30C3AF64C255C623f80920BfF",
        "donationDeposit": int(200_000 * 150 / 10000),
        "donationWithdrawn": 0,
        "leaseId": "0x" + "11" * 32,
        "termsHash": "0x" + "22" * 32,
    }
    stream_map = DummyStreamMap({"vm-del": 11})
    vm_service = DummyVMApplicationService()
    reader = DummyReader(now, stream)
    client = DummyClient()
    settings = DummySettings()
    webhooks = CapturingWebhookService()
    mon = StreamMonitor(
        stream_map=stream_map,
        vm_application_service=vm_service,
        reader=reader,
        client=client,
        settings=settings,
        webhook_service=webhooks,
    )

    calls = {"n": 0}

    async def fake_sleep(_):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    await mon._run()
    # VM deleted due to terminated stream, not just stopped
    assert vm_service.deleted == ["vm-del"]
    # No withdraw attempt for inactive stream path
    assert client.withdrawn == []
    assert webhooks.events[0][0] == "payment.stream.lost"
    assert webhooks.events[0][1]["data"]["reason"] == "stream terminated"


@pytest.mark.asyncio
async def test_monitor_keeps_vm_during_expiry_grace(monkeypatch):
    now = 5_000_000
    stream = {
        "token": "0xglm",
        "sender": "0xreq",
        "recipient": "0xprov",
        "startTime": now - 10_000,
        "stopTime": now,  # ended
        "providerRatePerSecond": 10,
        "providerDeposit": 200_000,
        "providerWithdrawn": 0,
        "donationBps": 150,
        "donationRecipient": "0x94153E31AA476cE30C3AF64C255C623f80920BfF",
        "donationDeposit": int(200_000 * 150 / 10000),
        "donationWithdrawn": 0,
        "halted": False,
    }
    stream_map = DummyStreamMap({"vm-end": 12})
    vm_service = DummyVMApplicationService(expire_result=False)
    reader = DummyReader(now, stream)
    client = DummyClient()
    settings = DummySettings()
    webhooks = CapturingWebhookService()
    mon = StreamMonitor(
        stream_map=stream_map,
        vm_application_service=vm_service,
        reader=reader,
        client=client,
        settings=settings,
        webhook_service=webhooks,
    )

    calls = {"n": 0}

    async def fake_sleep(_):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    await mon._run()
    # Exhaustion is visible, but application service skips cleanup while the
    # latest chain read is still in the grace window.
    assert vm_service.stopped == []
    assert vm_service.deleted == []
    assert vm_service.expired == [("vm-end", 12)]
    assert client.withdrawn == []
    assert webhooks.events[0][0] == "payment.stream.lost"
    assert webhooks.events[0][1]["data"]["reason"] == "stream exhausted"


@pytest.mark.asyncio
async def test_monitor_deletes_when_stream_expired_after_grace(monkeypatch):
    now = 5_000_000
    stream = {
        "token": "0xglm",
        "sender": "0xreq",
        "recipient": "0xprov",
        "startTime": now - 10_000,
        "stopTime": now - 30,
        "providerRatePerSecond": 10,
        "providerDeposit": 200_000,
        "providerWithdrawn": 0,
        "donationBps": 150,
        "donationRecipient": "0x94153E31AA476cE30C3AF64C255C623f80920BfF",
        "donationDeposit": int(200_000 * 150 / 10000),
        "donationWithdrawn": 0,
        "halted": False,
    }
    stream_map = DummyStreamMap({"vm-end": 12})
    vm_service = DummyVMApplicationService(expire_result=True)
    reader = DummyReader(now, stream)
    client = DummyClient()
    settings = DummySettings()
    webhooks = CapturingWebhookService()
    mon = StreamMonitor(
        stream_map=stream_map,
        vm_application_service=vm_service,
        reader=reader,
        client=client,
        settings=settings,
        webhook_service=webhooks,
    )

    calls = {"n": 0}

    async def fake_sleep(_):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    await mon._run()
    assert vm_service.stopped == ["vm-end"]
    assert vm_service.deleted == ["vm-end"]
    assert vm_service.expired == [("vm-end", 12)]
    assert client.withdrawn == []
    assert webhooks.events[0][0] == "payment.stream.lost"
    assert webhooks.events[0][1]["data"]["reason"] == "stream exhausted"


@pytest.mark.asyncio
async def test_monitor_emits_stream_lost_when_lookup_fails(monkeypatch):
    class FailingReader:
        web3 = types.SimpleNamespace(
            eth=types.SimpleNamespace(get_block=lambda _x: {"timestamp": 6_000_000})
        )

        def get_stream(self, _stream_id):
            raise RuntimeError("chain unavailable")

    stream_map = DummyStreamMap({"vm-missing": 13})
    vm_service = DummyVMApplicationService()
    webhooks = CapturingWebhookService()
    mon = StreamMonitor(
        stream_map=stream_map,
        vm_application_service=vm_service,
        reader=FailingReader(),
        client=DummyClient(),
        settings=DummySettings(),
        webhook_service=webhooks,
    )

    calls = {"n": 0}

    async def fake_sleep(_):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    await mon._run()

    assert vm_service.deleted == []
    assert webhooks.events[0][0] == "payment.stream.lost"
    assert webhooks.events[0][1]["data"]["reason"] == "stream lookup failed"
