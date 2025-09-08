from pathlib import Path

import pytest

import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from requestor.services.database_service import DatabaseService
from requestor.errors import DatabaseError


@pytest.mark.asyncio
async def test_database_service_save_and_get(tmp_path):
    svc = DatabaseService(tmp_path / "d.db")
    await svc.init()
    await svc.save_vm("a", "ip", "id", {"cpu": 1})
    vm = await svc.get_vm("a")
    assert vm["vm_id"] == "id"


@pytest.mark.asyncio
async def test_database_service_error_wrapped(tmp_path, monkeypatch):
    svc = DatabaseService(tmp_path / "d.db")
    await svc.init()

    async def boom(*args, **kwargs):
        raise RuntimeError("x")

    monkeypatch.setattr(svc.db, "save_vm", boom)
    with pytest.raises(DatabaseError):
        await svc.save_vm("a", "ip", "id", {})


@pytest.mark.asyncio
async def test_database_service_list_vms(tmp_path):
    svc = DatabaseService(tmp_path / "d.db")
    await svc.init()
    for i in range(2):
        await svc.save_vm(f"n{i}", "ip", f"id{i}", {"cpu": 1})
    vms = await svc.list_vms()
    assert len(vms) == 2


@pytest.mark.asyncio
async def test_database_service_delete_vm(tmp_path):
    svc = DatabaseService(tmp_path / "d.db")
    await svc.init()
    await svc.save_vm("n", "ip", "id", {})
    await svc.delete_vm("n")
    assert await svc.get_vm("n") is None


@pytest.mark.asyncio
async def test_database_service_update_status(tmp_path):
    svc = DatabaseService(tmp_path / "d.db")
    await svc.init()
    await svc.save_vm("n", "ip", "id", {}, status="running")
    await svc.update_vm_status("n", "stopped")
    vm = await svc.get_vm("n")
    assert vm["status"] == "stopped"


@pytest.mark.asyncio
async def test_get_vm_nonexistent(tmp_path):
    svc = DatabaseService(tmp_path / "d.db")
    await svc.init()
    assert await svc.get_vm("missing") is None


@pytest.mark.asyncio
async def test_database_service_execute_and_fetch(tmp_path):
    svc = DatabaseService(tmp_path / "d.db")
    await svc.init()
    await svc.execute(
        "INSERT INTO vms (name, provider_ip, vm_id, config) VALUES (?, ?, ?, ?)",
        ("n", "ip", "id", "{}"),
    )
    row = await svc.fetchone("SELECT vm_id FROM vms WHERE name=?", ("n",))
    assert row["vm_id"] == "id"
