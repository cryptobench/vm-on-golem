import pytest
from decimal import Decimal

from provider.utils import pricing as pricing_mod
from provider.utils.pricing import (
    calculate_monthly_cost,
    calculate_monthly_cost_usd,
    usd_to_glm,
    update_glm_unit_prices_from_usd,
)
from provider.vm.models import VMResources
from provider.config import settings


def test_calculate_monthly_cost_basic(monkeypatch):
    # Set GLM per-unit prices to fixed values
    settings.PRICE_GLM_PER_CORE_MONTH = 1.5
    settings.PRICE_GLM_PER_GB_RAM_MONTH = 0.5
    settings.PRICE_GLM_PER_GB_STORAGE_MONTH = 0.05

    res = VMResources(cpu=2, memory=2, storage=10)
    glm = calculate_monthly_cost(res)
    # 2*1.5 + 2*0.5 + 10*0.05 = 3 + 1 + 0.5 = 4.5 GLM
    assert glm == Decimal("4.50000000")


def test_calculate_monthly_cost_usd(monkeypatch):
    settings.PRICE_GLM_PER_CORE_MONTH = 1
    settings.PRICE_GLM_PER_GB_RAM_MONTH = 1
    settings.PRICE_GLM_PER_GB_STORAGE_MONTH = 0
    res = VMResources(cpu=2, memory=2, storage=10)
    glm = calculate_monthly_cost(res)  # 4 GLM
    usd = calculate_monthly_cost_usd(res, Decimal("0.5"))  # 0.5 USD/GLM
    assert glm == Decimal("4.00000000")
    assert usd == Decimal("2.00")


def test_usd_to_glm_and_update_glm_unit_prices():
    # USD config
    settings.PRICE_USD_PER_CORE_MONTH = 6.0
    settings.PRICE_USD_PER_GB_RAM_MONTH = 2.5
    settings.PRICE_USD_PER_GB_STORAGE_MONTH = 0.12
    glm_usd = Decimal("0.5")

    core_glm, ram_glm, storage_glm = update_glm_unit_prices_from_usd(glm_usd)
    assert core_glm == Decimal("12.00000000")
    assert ram_glm == Decimal("5.00000000")
    assert storage_glm == Decimal("0.24000000")
    # Ensure settings updated
    assert settings.PRICE_GLM_PER_CORE_MONTH == float(core_glm)


def test_usd_to_glm_invalid_zero_price():
    with pytest.raises(ValueError):
        usd_to_glm(Decimal("1"), Decimal("0"))

