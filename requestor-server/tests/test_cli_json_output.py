import sys
import types
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

sys.path.append(str(Path(__file__).resolve().parents[1]))

from requestor.cli.commands import cli


@pytest.fixture
def runner(monkeypatch):
    async def init_stub():
        pass

    monkeypatch.setattr(
        'requestor.cli.commands.db_service',
        types.SimpleNamespace(init=init_stub),
    )

    class DummySSH:
        def __init__(self, key_dir):
            pass

    monkeypatch.setattr('requestor.cli.commands.SSHService', DummySSH)

    return CliRunner()


def test_vm_info_json(runner, monkeypatch):
    expected = {
        'status': 'running',
        'provider_ip': '1.2.3.4',
        'config': {'ssh_port': 2222, 'cpu': 2, 'memory': 4, 'storage': 20},
    }

    class DummyVMService:
        def __init__(self, db, ssh):
            pass

        async def get_vm(self, name):
            return expected

    monkeypatch.setattr('requestor.cli.commands.VMService', DummyVMService)

    result = runner.invoke(cli, ['vm', 'info', 'vmname', '--json'])
    assert result.exit_code == 0
    assert json.loads(result.output) == expected

    from requestor.cli import commands as cmd

    assert cmd.info_vm('vmname', as_json=True) == expected


def test_vm_list_json(runner, monkeypatch):
    expected = [{'name': 'vm1'}, {'name': 'vm2'}]

    class DummyVMService:
        def __init__(self, db, ssh, client):
            pass

        async def list_vms(self):
            return expected

    monkeypatch.setattr('requestor.cli.commands.VMService', DummyVMService)

    result = runner.invoke(cli, ['vm', 'list', '--json'])
    assert result.exit_code == 0
    assert json.loads(result.output) == {'vms': expected}

    from requestor.cli import commands as cmd

    assert cmd.list_vms(as_json=True) == {'vms': expected}


def test_list_providers_json(runner, monkeypatch):
    expected = [{'id': 'p1'}, {'id': 'p2'}]

    class DummyProviderService:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def find_providers(self, cpu=None, memory=None, storage=None, country=None, driver=None):
            return expected

    monkeypatch.setattr('requestor.cli.commands.ProviderService', DummyProviderService)

    result = runner.invoke(cli, ['vm', 'providers', '--json'])
    assert result.exit_code == 0
    assert json.loads(result.output) == {'providers': expected}

    from requestor.cli import commands as cmd

    assert cmd.list_providers(None, None, None, None, None, as_json=True) == {'providers': expected}

