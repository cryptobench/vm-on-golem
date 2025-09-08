import sys
import types
from pathlib import Path
from importlib import reload

import pytest
from typer.testing import CliRunner

sys.path.append(str(Path(__file__).resolve().parents[1]))


class DummyDatabaseService:
    def __init__(self, db_path):
        self.db_path = db_path
    async def init(self):
        pass


def load_commands(monkeypatch):
    config_stub = types.SimpleNamespace(
        db_path=Path('/tmp/db.sqlite'),
        ssh_key_dir=Path('/tmp/ssh'),
        get_provider_url=lambda ip: ip,
        environment='development',
    )
    monkeypatch.setitem(sys.modules, 'requestor.config', types.SimpleNamespace(config=config_stub))
    monkeypatch.setitem(sys.modules, 'requestor.services.database_service', types.SimpleNamespace(DatabaseService=DummyDatabaseService))
    monkeypatch.setitem(sys.modules, 'requestor.services.ssh_service', types.SimpleNamespace(SSHService=object))
    monkeypatch.setitem(sys.modules, 'requestor.services.vm_service', types.SimpleNamespace(VMService=object))
    monkeypatch.setitem(sys.modules, 'requestor.services.provider_service', types.SimpleNamespace(ProviderService=object))
    monkeypatch.setitem(sys.modules, 'requestor.provider.client', types.SimpleNamespace(ProviderClient=object))
    monkeypatch.setitem(sys.modules, 'requestor.errors', types.SimpleNamespace(RequestorError=Exception))

    import requestor.cli.commands as commands
    reload(commands)
    return commands


@pytest.fixture
def runner():
    return CliRunner()


def test_vm_connect_alias_calls_ssh_callback(runner, monkeypatch):
    commands = load_commands(monkeypatch)
    called = {}

    def fake_callback(name: str):
        called['name'] = name

    monkeypatch.setattr(commands, 'ssh_vm', fake_callback)
    monkeypatch.setattr(commands, 'db_service', types.SimpleNamespace(init=lambda: None))

    result = runner.invoke(commands.cli, ['vm', 'connect', 'myvm'])

    assert result.exit_code == 0
    assert called['name'] == 'myvm'


def test_vm_delete_alias_calls_destroy_callback(runner, monkeypatch):
    commands = load_commands(monkeypatch)
    called = {}

    def fake_callback(name: str):
        called['name'] = name

    monkeypatch.setattr(commands, 'destroy_vm', fake_callback)
    monkeypatch.setattr(commands, 'db_service', types.SimpleNamespace(init=lambda: None))

    result = runner.invoke(commands.cli, ['vm', 'delete', 'oldvm'])

    assert result.exit_code == 0
    assert called['name'] == 'oldvm'
