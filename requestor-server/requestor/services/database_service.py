"""Database service for VM management."""
from typing import Dict, List, Optional
from pathlib import Path

from ..db.sqlite import Database
from ..errors import DatabaseError

class DatabaseService:
    """Service for database operations."""
    
    def __init__(self, db_path: Path):
        self.db = Database(db_path)

    async def init(self):
        """Initialize database."""
        try:
            await self.db.init()
        except Exception as e:
            raise DatabaseError(f"Failed to initialize database: {str(e)}")

    async def save_vm(
        self,
        name: str,
        provider_ip: str,
        vm_id: str,
        config: Dict,
        status: str = 'running'
    ) -> None:
        """Save VM details."""
        try:
            await self.db.save_vm(
                name=name,
                provider_ip=provider_ip,
                vm_id=vm_id,
                config=config,
                status=status
            )
        except Exception as e:
            raise DatabaseError(f"Failed to save VM: {str(e)}")

    async def get_vm(self, name: str) -> Optional[Dict]:
        """Get VM details by name."""
        try:
            vm = await self.db.get_vm(name)
            if not vm:
                return None
            return vm
        except Exception as e:
            raise DatabaseError(f"Failed to get VM details: {str(e)}")

    async def delete_vm(self, name: str) -> None:
        """Delete VM from database."""
        try:
            await self.db.delete_vm(name)
        except Exception as e:
            raise DatabaseError(f"Failed to delete VM: {str(e)}")

    async def update_vm_status(self, name: str, status: str) -> None:
        """Update VM status."""
        try:
            await self.db.update_vm_status(name, status)
        except Exception as e:
            raise DatabaseError(f"Failed to update VM status: {str(e)}")

    async def list_vms(self) -> List[Dict]:
        """List all VMs."""
        try:
            return await self.db.list_vms()
        except Exception as e:
            raise DatabaseError(f"Failed to list VMs: {str(e)}")

    async def execute(self, query: str, params: tuple = None) -> None:
        """Execute a raw SQL query."""
        try:
            await self.db.execute(query, params)
        except Exception as e:
            raise DatabaseError(f"Failed to execute query: {str(e)}")

    async def fetchone(self, query: str, params: tuple = None) -> Optional[Dict]:
        """Fetch a single row as a dictionary."""
        try:
            return await self.db.fetchone(query, params)
        except Exception as e:
            raise DatabaseError(f"Failed to fetch row: {str(e)}")

    async def fetchall(self, query: str, params: tuple = None) -> List[Dict]:
        """Fetch all rows as dictionaries."""
        try:
            return await self.db.fetchall(query, params)
        except Exception as e:
            raise DatabaseError(f"Failed to fetch rows: {str(e)}")
