from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Optional, Tuple
import time
import requests

from ..vm.models import VMResources
from .logging import setup_logger

logger = setup_logger(__name__)

def _get_settings():
    # Lazy import to avoid side effects during module import (e.g., JSON CLI quieting)
    from ..config import settings as _s
    return _s

# Increase precision for financial calcs
getcontext().prec = 28


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _coingecko_simple_price(ids: str) -> Optional[Decimal]:
    settings = _get_settings()
    base = settings.COINGECKO_API_URL.rstrip("/")
    url = f"{base}/simple/price"
    try:
        resp = requests.get(url, params={"ids": ids, "vs_currencies": "usd"}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # Try ids in order and return the first available
        for _id in ids.split(","):
            _id = _id.strip()
            if _id and _id in data and "usd" in data[_id]:
                usd = Decimal(str(data[_id]["usd"]))
                if usd > 0:
                    return usd
    except Exception as e:
        logger.warning(f"CoinGecko price fetch failed: {e}")
    return None


def fetch_glm_usd_price() -> Optional[Decimal]:
    """Fetch the current GLM price in USD from CoinGecko.

    Tries multiple IDs to hedge against slug changes.
    """
    settings = _get_settings()
    return _coingecko_simple_price(settings.COINGECKO_IDS)


def fetch_eth_usd_price() -> Optional[Decimal]:
    """Fetch the current ETH price in USD from CoinGecko.

    Uses the canonical "ethereum" id.
    """
    return _coingecko_simple_price("ethereum")


def usd_to_glm(usd_amount: Decimal, glm_usd: Decimal) -> Decimal:
    if glm_usd <= 0:
        raise ValueError("Invalid GLM/USD price")
    return (usd_amount / glm_usd).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def glm_to_usd(glm_amount: Decimal, glm_usd: Decimal) -> Decimal:
    return (glm_amount * glm_usd).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_monthly_cost(resources: VMResources) -> Decimal:
    """Calculate monthly cost in GLM for the given resources.

    Uses the GLM-denominated price-per-unit values configured in settings.
    """
    settings = _get_settings()
    core_price = Decimal(str(settings.PRICE_GLM_PER_CORE_MONTH))
    ram_price = Decimal(str(settings.PRICE_GLM_PER_GB_RAM_MONTH))
    storage_price = Decimal(str(settings.PRICE_GLM_PER_GB_STORAGE_MONTH))

    total = (
        core_price * Decimal(resources.cpu) +
        ram_price * Decimal(resources.memory) +
        storage_price * Decimal(resources.storage)
    )
    return total.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


# Note: function to derive per-unit prices from a total was intentionally not added.


def calculate_monthly_cost_usd(resources: VMResources, glm_usd: Decimal) -> Optional[Decimal]:
    cost_glm = calculate_monthly_cost(resources)
    try:
        return glm_to_usd(cost_glm, glm_usd)
    except Exception:
        return None


def update_glm_unit_prices_from_usd(glm_usd: Decimal) -> Tuple[Decimal, Decimal, Decimal]:
    """Recompute GLM per-unit monthly prices using current USD config and a GLM/USD rate.

    Returns a tuple of (core_glm, ram_glm, storage_glm).
    """
    settings = _get_settings()
    core_usd = Decimal(str(settings.PRICE_USD_PER_CORE_MONTH))
    ram_usd = Decimal(str(settings.PRICE_USD_PER_GB_RAM_MONTH))
    storage_usd = Decimal(str(settings.PRICE_USD_PER_GB_STORAGE_MONTH))

    core_glm = usd_to_glm(core_usd, glm_usd)
    ram_glm = usd_to_glm(ram_usd, glm_usd)
    storage_glm = usd_to_glm(storage_usd, glm_usd)

    # Persist on settings instance (in-memory)
    settings = _get_settings()
    settings.PRICE_GLM_PER_CORE_MONTH = float(core_glm)
    settings.PRICE_GLM_PER_GB_RAM_MONTH = float(ram_glm)
    settings.PRICE_GLM_PER_GB_STORAGE_MONTH = float(storage_glm)

    logger.info(
        f"Updated GLM prices from USD @ {glm_usd} USD/GLM: core={core_glm}, ram={ram_glm}, storage={storage_glm}"
    )
    return core_glm, ram_glm, storage_glm


class PricingAutoUpdater:
    """Background updater for pricing based on CoinGecko.

    It refreshes GLM-per-unit prices from USD config and can trigger callbacks (e.g., re-advertise).
    """

    def __init__(self, on_updated_callback=None):
        self._stop = False
        self._on_updated = on_updated_callback
        self._last_price: Optional[Decimal] = None

    async def start(self):
        settings = _get_settings()
        if not settings.PRICING_UPDATE_ENABLED:
            return

        # Choose update interval based on platform to avoid excessive on-chain updates
        interval = (
            settings.PRICING_UPDATE_INTERVAL_GOLEM_BASE
            if getattr(settings, "ADVERTISER_TYPE", "discovery_server") == "golem_base"
            else settings.PRICING_UPDATE_INTERVAL_DISCOVERY
        )
        await self._run_loop(interval)

    def stop(self):
        self._stop = True

    async def _run_loop(self, interval_discovery: int):
        import asyncio

        while not self._stop:
            try:
                glm_usd = fetch_glm_usd_price()
                if glm_usd:
                    changed = self._should_update(glm_usd)
                    if changed:
                        update_glm_unit_prices_from_usd(glm_usd)
                        if callable(self._on_updated):
                            # Inform callback which advertising platform is active
                            platform = getattr(settings, "ADVERTISER_TYPE", "discovery_server")
                            await self._on_updated(platform=platform, glm_usd=glm_usd)
                else:
                    logger.warning("Skipping pricing update; failed to fetch GLM price")
            except Exception as e:
                logger.error(f"Pricing update error: {e}")

            await asyncio.sleep(interval_discovery)

    def _should_update(self, new_price: Decimal) -> bool:
        if self._last_price is None:
            self._last_price = new_price
            return True
        old = self._last_price
        if old == 0:
            self._last_price = new_price
            return True
        delta = abs((new_price - old) / old) * Decimal("100")
        settings = _get_settings()
        if delta >= Decimal(str(settings.PRICING_UPDATE_MIN_DELTA_PERCENT)):
            self._last_price = new_price
            return True
        return False
