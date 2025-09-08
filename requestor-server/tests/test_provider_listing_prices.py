from requestor.services.provider_service import ProviderService
import pytest
import asyncio


@pytest.mark.asyncio
async def test_format_provider_row_includes_usd_prices():
    service = ProviderService()
    provider = {
        'provider_id': '0xabc',
        'provider_name': 'test-provider',
        'ip_address': '1.2.3.4',
        'country': 'SE',
        'resources': {'cpu': 4, 'memory': 8, 'storage': 100},
        'pricing': {
            'usd_per_core_month': 6.0,
            'usd_per_gb_ram_month': 2.5,
            'usd_per_gb_storage_month': 0.1,
        },
        'created_at_block': 0,
    }
    row = await service.format_provider_row(provider, colorize=False)
    headers = service.provider_headers
    # Ensure pricing columns exist and align
    assert "USD/core/mo" in headers
    assert "USD/GB RAM/mo" in headers
    assert "USD/GB Disk/mo" in headers
    # Row should include numeric prices (not placeholders)
    assert row[7] == 6.0
    assert row[8] == 2.5
    assert row[9] == 0.1


@pytest.mark.asyncio
async def test_format_provider_row_handles_missing_pricing():
    service = ProviderService()
    provider = {
        'provider_id': '0xdef',
        'provider_name': 'no-pricing',
        'ip_address': '5.6.7.8',
        'country': 'US',
        'resources': {'cpu': 2, 'memory': 4, 'storage': 50},
        'created_at_block': 0,
    }
    row = await service.format_provider_row(provider, colorize=False)
    # Pricing placeholders should be em-dash
    assert row[7] == '—'
    assert row[8] == '—'
    assert row[9] == '—'
