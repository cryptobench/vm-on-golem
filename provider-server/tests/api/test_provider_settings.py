from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from provider.errors import ValidationError
from provider.main import app
from provider.settings.domain import (
    ProviderSettings,
    ResourceSettings,
    UpdatePricingSettings,
    UpdateResourceSettings,
)
from provider.settings.service import ProviderSettingsService


class FakeResourceTracker:
    def __init__(self):
        self.detected_resources = {"cpu": 16, "memory": 64, "storage": 500}
        self.total_resources = {"cpu": 12, "memory": 48, "storage": 120}
        self.allocated_resources = {"cpu": 4, "memory": 16, "storage": 80}

    def get_available_resources(self):
        return {
            "cpu": self.total_resources["cpu"] - self.allocated_resources["cpu"],
            "memory": self.total_resources["memory"]
            - self.allocated_resources["memory"],
            "storage": self.total_resources["storage"]
            - self.allocated_resources["storage"],
        }

    async def set_offered_resources(self, resources):
        self.total_resources = dict(resources)


class FakeBroadcaster:
    def __init__(self):
        self.published = []

    async def publish(self, scopes):
        self.published.append(list(scopes))


def _settings():
    return {
        "PRICE_USD_PER_CORE_MONTH": 5.0,
        "PRICE_USD_PER_GB_RAM_MONTH": 2.0,
        "PRICE_USD_PER_GB_STORAGE_MONTH": 0.1,
        "PRICE_GLM_PER_CORE_MONTH": 10.0,
        "PRICE_GLM_PER_GB_RAM_MONTH": 4.0,
        "PRICE_GLM_PER_GB_STORAGE_MONTH": 0.2,
    }


def _service(env_path: Path):
    broadcaster = FakeBroadcaster()
    tracker = FakeResourceTracker()
    service = ProviderSettingsService(
        settings=_settings(),
        resource_tracker=tracker,
        broadcaster=broadcaster,
        env_path_resolver=lambda: str(env_path),
    )
    return service, tracker, broadcaster


@pytest.mark.asyncio
async def test_settings_get_returns_resource_and_pricing_state(tmp_path: Path):
    service, _, _ = _service(tmp_path / ".env")

    result = await service.get_settings()

    assert result.detected_resources == ResourceSettings(cpu=16, memory=64, storage=500)
    assert result.offered_resources == ResourceSettings(cpu=12, memory=48, storage=120)
    assert result.allocated_resources == ResourceSettings(cpu=4, memory=16, storage=80)
    assert result.available_resources == ResourceSettings(cpu=8, memory=32, storage=40)
    assert result.minimum_configurable_resources == ResourceSettings(
        cpu=4, memory=16, storage=80
    )
    assert result.pricing.usd_per_core_month == 5.0


@pytest.mark.asyncio
async def test_settings_get_uses_one_as_idle_minimum_configurable_resources(
    tmp_path: Path,
):
    service, tracker, _ = _service(tmp_path / ".env")
    tracker.allocated_resources = {"cpu": 0, "memory": 0, "storage": 0}

    result = await service.get_settings()

    assert result.minimum_configurable_resources == ResourceSettings(
        cpu=1, memory=1, storage=1
    )


@pytest.mark.asyncio
async def test_settings_resource_update_persists_updates_tracker_and_publishes(
    tmp_path: Path,
):
    env_path = tmp_path / ".env"
    service, tracker, broadcaster = _service(env_path)

    result = await service.update_resources(
        UpdateResourceSettings(cpu=10, memory=32, storage=100)
    )

    assert tracker.total_resources == {"cpu": 10, "memory": 32, "storage": 100}
    assert result.offered_resources == ResourceSettings(cpu=10, memory=32, storage=100)
    content = env_path.read_text()
    assert "GOLEM_PROVIDER_OFFERED_CPU_CORES=10" in content
    assert "GOLEM_PROVIDER_OFFERED_MEMORY_GB=32" in content
    assert "GOLEM_PROVIDER_OFFERED_STORAGE_GB=100" in content
    assert broadcaster.published == [["summary"]]


@pytest.mark.asyncio
async def test_settings_resource_update_rejects_below_allocated(tmp_path: Path):
    service, _, _ = _service(tmp_path / ".env")

    with pytest.raises(ValidationError):
        await service.update_resources(
            UpdateResourceSettings(cpu=3, memory=16, storage=80)
        )


@pytest.mark.asyncio
async def test_settings_resource_update_rejects_above_detected(tmp_path: Path):
    service, _, _ = _service(tmp_path / ".env")

    with pytest.raises(ValidationError):
        await service.update_resources(
            UpdateResourceSettings(cpu=17, memory=16, storage=80)
        )


@pytest.mark.asyncio
async def test_settings_pricing_update_recalculates_glm_and_publishes(
    tmp_path: Path, monkeypatch
):
    env_path = tmp_path / ".env"
    service, _, broadcaster = _service(env_path)
    monkeypatch.setattr(
        "provider.settings.service.fetch_glm_usd_price",
        lambda: Decimal("0.5"),
    )

    result = await service.update_pricing(
        UpdatePricingSettings(
            usd_per_core_month=6,
            usd_per_gb_ram_month=2.5,
            usd_per_gb_storage_month=0.12,
        )
    )

    assert result.pricing.glm_per_core_month == 12.0
    assert result.pricing.glm_per_gb_ram_month == 5.0
    assert result.pricing.glm_per_gb_storage_month == 0.24
    assert result.pricing.warning is None
    assert "GOLEM_PROVIDER_PRICE_USD_PER_CORE_MONTH=6.0" in env_path.read_text()
    assert broadcaster.published == [["summary"]]


@pytest.mark.asyncio
async def test_settings_pricing_update_warns_when_glm_price_unavailable(
    tmp_path: Path, monkeypatch
):
    service, _, _ = _service(tmp_path / ".env")
    monkeypatch.setattr("provider.settings.service.fetch_glm_usd_price", lambda: None)

    result = await service.update_pricing(
        UpdatePricingSettings(
            usd_per_core_month=6,
            usd_per_gb_ram_month=2.5,
            usd_per_gb_storage_month=0.12,
        )
    )

    assert result.pricing.usd_per_core_month == 6.0
    assert result.pricing.glm_per_core_month == 10.0
    assert result.pricing.warning is not None


class StubSettingsService:
    async def get_settings(self):
        return ProviderSettings(
            detected_resources=ResourceSettings(cpu=16, memory=64, storage=500),
            offered_resources=ResourceSettings(cpu=12, memory=48, storage=120),
            allocated_resources=ResourceSettings(cpu=4, memory=16, storage=80),
            available_resources=ResourceSettings(cpu=8, memory=32, storage=40),
            minimum_configurable_resources=ResourceSettings(
                cpu=4, memory=16, storage=80
            ),
            pricing={
                "usd_per_core_month": 5.0,
                "usd_per_gb_ram_month": 2.0,
                "usd_per_gb_storage_month": 0.1,
                "glm_per_core_month": 10.0,
                "glm_per_gb_ram_month": 4.0,
                "glm_per_gb_storage_month": 0.2,
            },
        )


def test_provider_settings_endpoint_returns_contract():
    client = TestClient(app)
    with app.container.provider_settings_service.override(StubSettingsService()):
        response = client.get("/api/v1/provider/settings")

    assert response.status_code == 200
    data = response.json()
    assert data["detected_resources"]["cpu"] == 16
    assert data["offered_resources"]["memory"] == 48
    assert data["pricing"]["usd_per_core_month"] == 5.0
    assert "payments" not in data
