import sys
import types
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

sys.path.append(str(Path(__file__).resolve().parents[1]))

from requestor.cli.commands import cli


@pytest.fixture
def runner(monkeypatch):
    async def init_stub():
        pass

    # Stub db_service with async list_vms
    async def list_vms_stub():
        return [
            {"name": "vm-unmapped", "vm_id": "vm-unmapped", "provider_ip": "10.0.0.1"},
            {"name": "vm-mapped", "vm_id": "vm-mapped", "provider_ip": "10.0.0.2"},
        ]

    monkeypatch.setattr(
        'requestor.cli.commands.db_service',
        types.SimpleNamespace(init=init_stub, list_vms=list_vms_stub),
    )

    # Stub ProviderClient to simulate provider responses
    class DummyProviderClient:
        def __init__(self, url):
            self.url = url

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def get_vm_stream_status(self, vm_id):
            if vm_id == "vm-unmapped":
                raise Exception("no stream mapped for this VM")
            # Return a minimal but realistic payload
            return {
                "stream_id": 123,
                "verified": True,
                "reason": "ok",
                "computed": {
                    "remaining_seconds": 3600,
                    "withdrawable_wei": 1000,
                },
            }

    monkeypatch.setattr('requestor.cli.commands.ProviderClient', DummyProviderClient)

    # Provide trivial config helpers used by the command
    cfg = types.SimpleNamespace(get_provider_url=lambda ip: f"http://{ip}:8000")
    monkeypatch.setattr('requestor.cli.commands.config', cfg)

    return CliRunner()


def test_stream_list_help(runner):
    result = runner.invoke(cli, ['vm', 'stream', 'list', '--help'])
    assert result.exit_code == 0
    assert 'Output in JSON format' in result.output


def test_stream_list_json_output(runner):
    result = runner.invoke(cli, ['vm', 'stream', 'list', '--json'])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert 'streams' in data
    assert len(data['streams']) == 2

    # Unmapped VM
    s0 = data['streams'][0]
    assert s0['name'] == 'vm-unmapped'
    assert s0['stream_id'] is None
    assert s0['verified'] is False
    assert s0['reason'] == 'unmapped'

    # Mapped VM
    s1 = data['streams'][1]
    assert s1['name'] == 'vm-mapped'
    assert s1['stream_id'] == 123
    assert s1['verified'] is True
    assert s1['reason'] == 'ok'
    assert s1['computed']['remaining_seconds'] == 3600


def test_stream_list_table_output(runner):
    result = runner.invoke(cli, ['vm', 'stream', 'list'])
    assert result.exit_code == 0
    # Basic smoke assertions on table content
    assert 'Streams (2 VMs)' in result.output
    assert 'vm-unmapped' in result.output
    assert 'vm-mapped' in result.output
    assert '123' in result.output


def test_stream_list_no_vms(monkeypatch):
    from requestor.cli import commands as cmd

    async def init_stub():
        pass

    async def empty_list():
        return []

    monkeypatch.setattr(
        'requestor.cli.commands.db_service',
        types.SimpleNamespace(init=init_stub, list_vms=empty_list),
    )

    # Minimal config to satisfy the command
    cfg = types.SimpleNamespace(get_provider_url=lambda ip: ip)
    monkeypatch.setattr('requestor.cli.commands.config', cfg)

    runner = CliRunner()
    result = runner.invoke(cli, ['vm', 'stream', 'list'])
    assert result.exit_code == 0
    assert 'No VMs found' in result.output

