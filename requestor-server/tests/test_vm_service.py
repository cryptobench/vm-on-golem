import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from requestor.services.vm_service import VMService


class DummyDB:
    def __init__(self, vm):
        self.vm = vm

    async def get_vm(self, name):
        return self.vm


def dummy_key_pair(tmp_path):
    priv = tmp_path / "k"
    priv.write_text("p")
    pub = tmp_path / "k.pub"
    pub.write_text("pub")
    return SimpleNamespace(private_key=priv, public_key=pub)


def test_vm_headers():
    svc = VMService(SimpleNamespace(), SimpleNamespace())
    headers = svc.vm_headers
    assert "Name" in headers and "Status" in headers


def test_format_vm_row(monkeypatch, tmp_path):
    vm = {
        "name": "n",
        "status": "running",
        "provider_ip": "ip",
        "config": {
            "cpu": 1,
            "memory": 1,
            "storage": 1,
            "ssh_port": 22,
            "ssh_user": "ubuntu",
        },
        "created_at": "now",
    }

    db = DummyDB(vm)

    class DummySSH:
        def get_key_pair_sync(self):
            return dummy_key_pair(tmp_path)

        def format_ssh_command(self, **kwargs):
            return "cmd"

    svc = VMService(db, DummySSH(), SimpleNamespace())
    row = svc.format_vm_row(vm)
    assert row[0] == "n"
    assert "cmd" in row[7]


@pytest.mark.asyncio
async def test_get_vm_refreshes_missing_ssh_user():
    vm = {
        "name": "n",
        "status": "running",
        "provider_ip": "ip",
        "vm_id": "vm-1",
        "config": {"cpu": 1, "memory": 1, "storage": 1, "ssh_port": 22},
        "created_at": "now",
    }

    class UpdatingDB(DummyDB):
        async def update_vm_config(self, name, config, status=None):
            self.vm = {
                **self.vm,
                "config": config,
                "status": status or self.vm["status"],
            }

    class Provider:
        async def get_vm_access(self, vm_id):
            return {"vm_id": vm_id, "ssh_port": 22, "ssh_user": "ubuntu"}

    svc = VMService(UpdatingDB(vm), SimpleNamespace(), Provider())

    refreshed = await svc.get_vm("n")

    assert refreshed["config"]["ssh_user"] == "ubuntu"


@pytest.mark.asyncio
async def test_get_vm_fails_when_provider_omits_ssh_user():
    vm = {
        "name": "n",
        "status": "running",
        "provider_ip": "ip",
        "vm_id": "vm-1",
        "config": {"cpu": 1, "memory": 1, "storage": 1, "ssh_port": 22},
        "created_at": "now",
    }

    class Provider:
        async def get_vm_access(self, vm_id):
            return {"vm_id": vm_id, "ssh_port": 22}

    svc = VMService(DummyDB(vm), SimpleNamespace(), Provider())

    with pytest.raises(Exception, match="SSH login user"):
        await svc.get_vm("n")
