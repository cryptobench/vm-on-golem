import asyncio
from decimal import Decimal

import pytest

from provider.config import settings
from provider.utils.pricing import PricingAutoUpdater


@pytest.mark.asyncio
async def test_pricing_auto_updater_calls_callback_with_platform(monkeypatch):
    # Configure to update on any change
    settings.PRICING_UPDATE_MIN_DELTA_PERCENT = 0.0

    events = []

    async def on_updated(platform: str, glm_usd):
        events.append((platform, glm_usd))

    updater = PricingAutoUpdater(on_updated_callback=on_updated)

    settings.DISCOVERY_BACKEND = "central"

    calls = {"n": 0}

    def fake_fetch():
        calls["n"] += 1
        # Stop after first update to keep test fast
        if calls["n"] >= 1:
            updater.stop()
        return Decimal("0.5")

    # Patch fetch and sleep to run instantly
    monkeypatch.setattr("provider.utils.pricing.fetch_glm_usd_price", fake_fetch)

    async def no_sleep(*_a, **_k):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    await updater.start()

    assert len(events) >= 1
    platform, price = events[0]
    assert platform == "central"
    assert price == Decimal("0.5")
