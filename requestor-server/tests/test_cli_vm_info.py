import sys
import types
from pathlib import Path

import pytest
from click.testing import CliRunner

sys.path.append(str(Path(__file__).resolve().parents[1]))

from requestor.cli.cli import cli
import requestor.cli.vm_commands as vm_cmds

@pytest.fixture
def runner(monkeypatch):
    async def init_stub():
        pass
    stub_db = types.SimpleNamespace(init=init_stub)
    monkeypatch.setattr('requestor.cli.shared.db_service', stub_db)
    monkeypatch.setattr('requestor.cli.vm_commands.db_service', stub_db)

    class DummySSH:
        def __init__(self, key_dir):
            pass
    monkeypatch.setattr('requestor.cli.vm_commands.SSHService', DummySSH)

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

    monkeypatch.setattr('requestor.cli.vm_commands.VMService', DummyVMService)

    result = runner.invoke(cli, ['vm', 'info', 'vmname'])
    assert result.exit_code == 0
    out = result.output
    assert '1.2.3.4' in out
    assert '2222' in out
    assert '2' in out
    assert '4' in out
    assert '20' in out


def test_vm_info_not_found(runner, monkeypatch):
    class DummyVMService:
        def __init__(self, db, ssh):
            pass

        async def get_vm(self, name):
            return None

    monkeypatch.setattr('requestor.cli.vm_commands.VMService', DummyVMService)

    result = runner.invoke(cli, ['vm', 'info', 'missing'])
    assert result.exit_code != 0
    assert 'Aborted' in result.output
