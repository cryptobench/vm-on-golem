from pathlib import Path

import pytest

import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from requestor.db.sqlite import Database


@pytest.mark.asyncio
async def test_init_creates_table(tmp_path):
    db = Database(tmp_path / "t.db")
    await db.init()
    assert (tmp_path / "t.db").exists()
    tables = await db.fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='vms'"
    )
    assert tables


@pytest.mark.asyncio
async def test_save_and_get_vm(tmp_path):
    db = Database(tmp_path / "t.db")
    await db.init()
    await db.save_vm("n", "ip", "id", {"cpu": 1}, "running")
    vm = await db.get_vm("n")
    assert vm["provider_ip"] == "ip"


@pytest.mark.asyncio
async def test_update_vm_status(tmp_path):
    db = Database(tmp_path / "t.db")
    await db.init()
    await db.save_vm("n", "ip", "id", {"cpu": 1}, "running")
    await db.update_vm_status("n", "stopped")
    vm = await db.get_vm("n")
    assert vm["status"] == "stopped"


@pytest.mark.asyncio
async def test_delete_vm(tmp_path):
    db = Database(tmp_path / "t.db")
    await db.init()
    await db.save_vm("n", "ip", "id", {"cpu": 1}, "running")
    await db.delete_vm("n")
    vm = await db.get_vm("n")
    assert vm is None


@pytest.mark.asyncio
async def test_list_vms(tmp_path):
    db = Database(tmp_path / "t.db")
    await db.init()
    for i in range(3):
        await db.save_vm(f"n{i}", "ip", f"id{i}", {"cpu": 1}, "running")
    vms = await db.list_vms()
    assert len(vms) == 3


@pytest.mark.asyncio
async def test_execute_and_fetchone(tmp_path):
    db = Database(tmp_path / "t.db")
    await db.init()
    await db.execute(
        "INSERT INTO vms (name, provider_ip, vm_id, config) VALUES (?, ?, ?, ?)",
        ("n", "ip", "id", "{}"),
    )
    row = await db.fetchone("SELECT vm_id FROM vms WHERE name=?", ("n",))
    assert row["vm_id"] == "id"


@pytest.mark.asyncio
async def test_fetchall_empty(tmp_path):
    db = Database(tmp_path / "t.db")
    await db.init()
    rows = await db.fetchall("SELECT * FROM vms")
    assert rows == []
