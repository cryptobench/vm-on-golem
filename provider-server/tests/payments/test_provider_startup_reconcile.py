import asyncio
import types
import pytest

from provider.service import ProviderService
from provider.vm.models import VMResources


class DummyPortManager:
    async def initialize(self):
        return None


class DummyAdvertisementService:
    def __init__(self):
        self.started = False

    async def start(self):
        self.started = True

    async def stop(self):
        self.started = False


class DummyProvider:
    async def initialize(self):
        return None

    async def cleanup(self):
        return None


class DummyResourceTracker:
    def __init__(self):
        self.sync_calls = 0
        self.last_resources = None

    async def sync_with_multipass(self, vm_resources):
        self.sync_calls += 1
        self.last_resources = vm_resources


class DummyVMService:
    def __init__(self, vm_resources):
        self._resources = vm_resources
        self.provider = DummyProvider()
        self.resource_tracker = DummyResourceTracker()
        self.deleted = []

    async def get_all_vms_resources(self):
        return dict(self._resources)

    async def delete_vm(self, vm_id: str):
        self.deleted.append(vm_id)
        # reflect deletion in resources
        self._resources.pop(vm_id, None)


class DummyStreamMap:
    def __init__(self, mapping):
        self._map = dict(mapping)
        self.removed = []

    async def get(self, vm_id):
        return self._map.get(vm_id)

    async def remove(self, vm_id):
        self._map.pop(vm_id, None)
        self.removed.append(vm_id)

    async def all_items(self):
        return dict(self._map)


class DummyReader:
    def __init__(self, validity_by_stream):
        # validity_by_stream: {stream_id: (ok, msg)}
        self.validity = validity_by_stream

    def verify_stream(self, sid, expected_recipient):
        return self.validity.get(int(sid), (False, "not found"))


class DummyStreamMonitor:
    def start(self):
        pass

    async def stop(self):
        pass


class DummyPricingUpdater:
    def __init__(self, on_updated_callback=None):
        self._cb = on_updated_callback
        self.started = False

    async def start(self):
        self.started = True

    def stop(self):
        self.started = False


class DummyApp:
    def __init__(self, stream_map, reader, stream_monitor=None):
        class _C:
            def __init__(self, sm, rd, mon):
                self._sm = sm
                self._rd = rd
                self._mon = mon or DummyStreamMonitor()

            def stream_map(self):
                return self._sm

            def stream_reader(self):
                # In container we usually build via factory; here we return the dummy
                return self._rd

            def stream_monitor(self):
                return self._mon

        self.container = _C(stream_map, reader, stream_monitor)


@pytest.mark.asyncio
async def test_startup_terminates_vms_without_active_stream(monkeypatch):
    from provider import service as ps
    from provider.config import settings

    # Enable payments logic
    settings.STREAM_PAYMENT_ADDRESS = "0x1234567890abcdef1234567890abcdef12345678"
    settings.POLYGON_RPC_URL = "http://localhost"
    settings.STREAM_MONITOR_ENABLED = False
    settings.STREAM_WITHDRAW_ENABLED = False

    # Patch external collaborators (faucet + pricing updater)
    import provider.security.faucet as faucet_mod
    monkeypatch.setattr(faucet_mod, "FaucetClient", lambda *a, **k: types.SimpleNamespace(get_funds=lambda *_: asyncio.sleep(0)))
    monkeypatch.setattr(ps, "PricingAutoUpdater", DummyPricingUpdater)

    # One VM present, no stream mapping -> should be terminated
    vm_resources = {"vm-a": VMResources(cpu=2, memory=4, storage=20)}
    vm_service = DummyVMService(vm_resources)
    adv = DummyAdvertisementService()
    port = DummyPortManager()
    provider_service = ProviderService(vm_service=vm_service, advertisement_service=adv, port_manager=port)

    stream_map = DummyStreamMap({})
    reader = DummyReader({})
    app = DummyApp(stream_map, reader)

    await provider_service.setup(app)  # type: ignore[arg-type]

    # Assert VM was deleted and mapping removed
    assert vm_service.deleted == ["vm-a"]
    assert stream_map.removed == ["vm-a"]
    # Synced before and after termination
    assert vm_service.resource_tracker.sync_calls >= 2
    assert adv.started is True


@pytest.mark.asyncio
async def test_startup_keeps_vms_with_active_stream(monkeypatch):
    from provider import service as ps
    from provider.config import settings

    # Enable payments logic
    settings.STREAM_PAYMENT_ADDRESS = "0x1234567890abcdef1234567890abcdef12345678"
    settings.POLYGON_RPC_URL = "http://localhost"
    settings.STREAM_MONITOR_ENABLED = False
    settings.STREAM_WITHDRAW_ENABLED = False

    # Patch external collaborators
    import provider.security.faucet as faucet_mod
    monkeypatch.setattr(faucet_mod, "FaucetClient", lambda *a, **k: types.SimpleNamespace(get_funds=lambda *_: asyncio.sleep(0)))
    monkeypatch.setattr(ps, "PricingAutoUpdater", DummyPricingUpdater)

    vm_resources = {"vm-b": VMResources(cpu=2, memory=4, storage=20)}
    vm_service = DummyVMService(vm_resources)
    adv = DummyAdvertisementService()
    port = DummyPortManager()
    provider_service = ProviderService(vm_service=vm_service, advertisement_service=adv, port_manager=port)

    # Map stream and mark it valid
    stream_map = DummyStreamMap({"vm-b": 42})
    reader = DummyReader({42: (True, "ok")})
    app = DummyApp(stream_map, reader)

    await provider_service.setup(app)  # type: ignore[arg-type]

    # No deletions or removals; still synced twice and advertising started
    assert vm_service.deleted == []
    assert stream_map.removed == []
    assert vm_service.resource_tracker.sync_calls >= 2
    assert adv.started is True


@pytest.mark.asyncio
async def test_startup_skips_stream_checks_when_payments_disabled(monkeypatch):
    from provider import service as ps
    from provider.config import settings

    # Disable payments by zero address
    settings.STREAM_PAYMENT_ADDRESS = "0x0000000000000000000000000000000000000000"
    settings.POLYGON_RPC_URL = ""
    settings.STREAM_MONITOR_ENABLED = False
    settings.STREAM_WITHDRAW_ENABLED = False

    # Patch external collaborators
    import provider.security.faucet as faucet_mod
    monkeypatch.setattr(faucet_mod, "FaucetClient", lambda *a, **k: types.SimpleNamespace(get_funds=lambda *_: asyncio.sleep(0)))
    monkeypatch.setattr(ps, "PricingAutoUpdater", DummyPricingUpdater)

    vm_resources = {"vm-c": VMResources(cpu=2, memory=4, storage=20)}
    vm_service = DummyVMService(vm_resources)
    adv = DummyAdvertisementService()
    port = DummyPortManager()
    provider_service = ProviderService(vm_service=vm_service, advertisement_service=adv, port_manager=port)

    # If called, these would raise; but payments disabled should skip them
    class RaisingStreamMap:
        async def get(self, *_):
            raise AssertionError("stream_map.get should not be called")

        async def remove(self, *_):
            raise AssertionError("stream_map.remove should not be called")

        async def all_items(self):
            return {}

    class RaisingReader:
        def verify_stream(self, *_):
            raise AssertionError("verify_stream should not be called")

    app = DummyApp(RaisingStreamMap(), RaisingReader())

    await provider_service.setup(app)  # type: ignore[arg-type]

    # No deletions; synced at least once and advertising started
    assert vm_service.deleted == []
    assert vm_service.resource_tracker.sync_calls >= 1
    assert adv.started is True
