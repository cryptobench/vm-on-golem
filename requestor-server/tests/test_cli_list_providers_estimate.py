import types
import json
import pytest
from click.testing import CliRunner

from requestor.cli.commands import cli


def test_list_providers_with_spec_includes_estimate(monkeypatch):
    runner = CliRunner()

    # Stub ProviderService to return a fixed provider with pricing
    from requestor.cli import commands as cmds

    class StubProviderService:
        def __init__(self):
            self.estimate_spec = None
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def find_providers(self, **kwargs):
            return [{
                'provider_id': '0xabc',
                'provider_name': 'p1',
                'ip_address': '1.2.3.4',
                'country': 'SE',
                'resources': {'cpu': 8, 'memory': 16, 'storage': 200},
                'pricing': {
                    'usd_per_core_month': 6.0,
                    'usd_per_gb_ram_month': 2.0,
                    'usd_per_gb_storage_month': 0.1,
                    'glm_per_core_month': 12.0,
                    'glm_per_gb_ram_month': 4.0,
                    'glm_per_gb_storage_month': 0.2,
                },
                'created_at_block': 0,
            }]
        async def _format_block_timestamp(self, *_a, **_k):
            return 'N/A'
        async def format_provider_row(self, provider, colorize=False):
            # reuse real implementation by patching into a real instance
            from requestor.services.provider_service import ProviderService as RealPS
            real = RealPS()
            real.estimate_spec = self.estimate_spec
            return await RealPS.format_provider_row(real, provider, colorize=colorize)
        @property
        def provider_headers(self):
            from requestor.services.provider_service import ProviderService as RealPS
            real = RealPS()
            return RealPS.provider_headers.fget(real)

    monkeypatch.setattr(cmds, 'ProviderService', StubProviderService)

    result = runner.invoke(cli, ['vm', 'providers', '--cpu', '2', '--memory', '4', '--storage', '20'])
    assert result.exit_code == 0
    # Should show Est. $/mo based on 2c/4g/20g: 2*6 + 4*2 + 20*0.1 = 12 + 8 + 2 = 22
    assert '~$22.0/mo' in result.stdout
    # And per-hour next to ID: 22 / 730 = ~0.030137...
    assert '/hr' in result.stdout


def test_list_providers_json_includes_estimate(monkeypatch):
    runner = CliRunner()

    from requestor.cli import commands as cmds

    class StubProviderService:
        def __init__(self):
            self.estimate_spec = None
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def find_providers(self, **kwargs):
            return [{
                'provider_id': '0xabc',
                'provider_name': 'p1',
                'ip_address': '1.2.3.4',
                'country': 'SE',
                'resources': {'cpu': 8, 'memory': 16, 'storage': 200},
                'pricing': {
                    'usd_per_core_month': 6.0,
                    'usd_per_gb_ram_month': 2.0,
                    'usd_per_gb_storage_month': 0.1,
                    'glm_per_core_month': 12.0,
                    'glm_per_gb_ram_month': 4.0,
                    'glm_per_gb_storage_month': 0.2,
                },
                'created_at_block': 0,
            }]
        async def _format_block_timestamp(self, *_a, **_k):
            return 'N/A'
        async def format_provider_row(self, provider, colorize=False):
            from requestor.services.provider_service import ProviderService as RealPS
            real = RealPS()
            real.estimate_spec = self.estimate_spec
            return await RealPS.format_provider_row(real, provider, colorize=colorize)
        def compute_estimate(self, provider, spec):
            from requestor.services.provider_service import ProviderService as RealPS
            real = RealPS()
            return real.compute_estimate(provider, spec)
        @property
        def provider_headers(self):
            from requestor.services.provider_service import ProviderService as RealPS
            real = RealPS()
            return RealPS.provider_headers.fget(real)

    monkeypatch.setattr(cmds, 'ProviderService', StubProviderService)

    result = runner.invoke(cli, ['vm', 'providers', '--cpu', '2', '--memory', '4', '--storage', '20', '--json'])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert 'providers' in data and len(data['providers']) == 1
    est = data['providers'][0].get('estimate')
    assert est is not None
    assert est['usd_per_month'] == 22.0
    assert abs(est['usd_per_hour'] - (22.0/730.0)) < 1e-6
    assert est['glm_per_month'] is not None


def test_list_providers_json_no_pricing_has_no_estimate(monkeypatch):
    runner = CliRunner()
    from requestor.cli import commands as cmds

    class StubProviderService:
        def __init__(self):
            self.estimate_spec = None
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def find_providers(self, **kwargs):
            return [{
                'provider_id': '0xdef',
                'provider_name': 'p2',
                'ip_address': '5.6.7.8',
                'country': 'US',
                'resources': {'cpu': 2, 'memory': 4, 'storage': 50},
                'created_at_block': 0,
            }]
        async def _format_block_timestamp(self, *_a, **_k):
            return 'N/A'
        async def format_provider_row(self, provider, colorize=False):
            from requestor.services.provider_service import ProviderService as RealPS
            real = RealPS()
            real.estimate_spec = self.estimate_spec
            return await RealPS.format_provider_row(real, provider, colorize=colorize)
        def compute_estimate(self, provider, spec):
            from requestor.services.provider_service import ProviderService as RealPS
            real = RealPS()
            return real.compute_estimate(provider, spec)
        @property
        def provider_headers(self):
            from requestor.services.provider_service import ProviderService as RealPS
            real = RealPS()
            return RealPS.provider_headers.fget(real)

    monkeypatch.setattr(cmds, 'ProviderService', StubProviderService)

    result = runner.invoke(cli, ['vm', 'providers', '--cpu', '2', '--memory', '4', '--storage', '20', '--json'])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert 'providers' in data and len(data['providers']) == 1
    assert 'estimate' not in data['providers'][0]
