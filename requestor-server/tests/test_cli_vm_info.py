import sys
import types
from pathlib import Path
import json

import pytest
from typer.testing import CliRunner

sys.path.append(str(Path(__file__).resolve().parents[1]))

from requestor.cli.commands import cli

@pytest.fixture
def runner(monkeypatch):
    async def init_stub():
        pass
    monkeypatch.setattr('requestor.cli.commands.db_service', types.SimpleNamespace(init=init_stub))

    class DummySSH:
        def __init__(self, key_dir):
            pass
    monkeypatch.setattr('requestor.cli.commands.SSHService', DummySSH)

    return CliRunner()


def test_vm_info_success(runner, monkeypatch):
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

    result = runner.invoke(cli, ['vm', 'info', 'vmname'])
    assert result.exit_code == 0
    out = result.output
    assert '1.2.3.4' in out
    assert '2222' in out
    assert '2' in out
    assert '4' in out
    assert '20' in out


def test_vm_info_json_output(runner, monkeypatch):
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


def test_vm_info_not_found(runner, monkeypatch):
    class DummyVMService:
        def __init__(self, db, ssh):
            pass

        async def get_vm(self, name):
            return None

    monkeypatch.setattr('requestor.cli.commands.VMService', DummyVMService)

    result = runner.invoke(cli, ['vm', 'info', 'missing'])
    assert result.exit_code != 0
