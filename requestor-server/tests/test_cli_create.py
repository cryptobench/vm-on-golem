from pathlib import Path

import pytest
from click.testing import CliRunner

from requestor.cli import commands


class DummyProviderService:
    def __init__(self, provider):
        self.provider = provider
        self.provider_headers = ["ID", "CPU", "Memory", "Storage"]

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def find_providers(self, *args, **kwargs):
        return [self.provider]

    async def verify_provider(self, pid):
        return self.provider

    async def check_resource_availability(self, pid, cpu, memory, storage):
        return True

    async def format_provider_row(self, provider, colorize=False):
        r = provider["resources"]
        return [provider["provider_id"], r["cpu"], r["memory"], r["storage"]]


class NoProviderService(DummyProviderService):
    async def find_providers(self, *args, **kwargs):
        return []


class DummyKeyPair:
    public_key_content = "pub"
    private_key = Path("key")


class DummySSHService:
    def __init__(self, *args, **kwargs):
        pass

    async def get_key_pair(self):
        return DummyKeyPair()

    def format_ssh_command(self, *args, **kwargs):
        return "ssh cmd"


class DummyVMService:
    def __init__(self, *args, **kwargs):
        pass

    async def create_vm(self, **kwargs):
        return {"config": {"ssh_port": 2222}}


class DummyProviderClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        pass


def setup_mocks(monkeypatch, service_class):
    provider = {
        "provider_id": "prov1",
        "ip_address": "1.1.1.1",
        "resources": {"cpu": 8, "memory": 16, "storage": 200},
    }
    monkeypatch.setattr(commands, "ProviderService", lambda: service_class(provider))
    monkeypatch.setattr(commands, "SSHService", DummySSHService)
    monkeypatch.setattr(commands, "VMService", DummyVMService)
    monkeypatch.setattr(commands, "ProviderClient", DummyProviderClient)
    return provider


def test_create_vm_auto_selects_provider_and_prompts(monkeypatch):
    provider = setup_mocks(monkeypatch, DummyProviderService)
    runner = CliRunner()
    result = runner.invoke(
        commands.create_vm,
        ["vm1"],
        input="2\n4\n10\ny\n",
    )
    assert result.exit_code == 0
    assert f"Selected provider {provider['provider_id']}" in result.output
    assert "Resources  : 2 CPU, 4GB RAM, 10GB Storage" in result.output


def test_create_vm_aborts_when_user_declines(monkeypatch):
    setup_mocks(monkeypatch, DummyProviderService)
    runner = CliRunner()
    result = runner.invoke(
        commands.create_vm,
        ["vm1"],
        input="2\n4\n10\nn\n",
    )
    assert result.exit_code != 0
    assert "Aborted!" in result.output


def test_create_vm_no_providers(monkeypatch):
    setup_mocks(monkeypatch, NoProviderService)
    runner = CliRunner()
    result = runner.invoke(commands.create_vm, ["vm1"], input="")
    assert result.exit_code != 0
    assert result.output.strip() == "Aborted!"
