import aiosqlite
from pathlib import Path
from typing import Optional, Dict, List
import json

class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def init(self):
        """Initialize database."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS vms (
                    name TEXT PRIMARY KEY,
                    provider_ip TEXT NOT NULL,
                    vm_id TEXT NOT NULL,
                    config TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'running',
                    ssh_key_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def save_vm(
        self,
        name: str,
        provider_ip: str,
        vm_id: str,
        config: Dict,
        ssh_key_name: Optional[str] = None,
        status: str = 'running'
    ) -> None:
        """Save VM details."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO vms (name, provider_ip, vm_id, config, ssh_key_name, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, provider_ip, vm_id, json.dumps(config), ssh_key_name, status)
            )
            await db.commit()

    async def get_vm(self, name: str) -> Optional[Dict]:
        """Get VM details."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM vms WHERE name = ?",
                (name,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    vm = dict(row)
                    vm['config'] = json.loads(vm['config'])
                    return vm
                return None

    async def delete_vm(self, name: str) -> None:
        """Delete VM details."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM vms WHERE name = ?",
                (name,)
            )
            await db.commit()

    async def update_vm_status(self, name: str, status: str) -> None:
        """Update VM status."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE vms SET status = ? WHERE name = ?",
                (status, name)
            )
            await db.commit()

    async def list_vms(self) -> List[Dict]:
        """List all VMs."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM vms") as cursor:
                rows = await cursor.fetchall()
                vms = []
                for row in rows:
                    vm = dict(row)
                    vm['config'] = json.loads(vm['config'])
                    vms.append(vm)
                return vms
