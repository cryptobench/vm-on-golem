import asyncio
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any


@dataclass
class JobRecord:
    job_id: str
    vm_id: str
    status: str
    error: Optional[str]
    created_at: str
    updated_at: str


class JobStore:
    """SQLite-backed store for VM creation jobs.

    Keeps minimal fields to track progress and errors across restarts.
    """

    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)
        # Ensure parent directory exists
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS jobs (
                        job_id TEXT PRIMARY KEY,
                        vm_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        error TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
        finally:
            conn.close()

    async def create_job(self, job_id: str, vm_id: str, status: str = "creating") -> None:
        now = datetime.now(timezone.utc).isoformat()

        def _op():
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            try:
                with conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO jobs (job_id, vm_id, status, error, created_at, updated_at) VALUES (?, ?, ?, NULL, ?, ?)",
                        (job_id, vm_id, status, now, now),
                    )
            finally:
                conn.close()

        await asyncio.to_thread(_op)

    async def update_job(self, job_id: str, *, status: Optional[str] = None, error: Optional[str] = None) -> None:
        now = datetime.now(timezone.utc).isoformat()

        def _op():
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            try:
                with conn:
                    if status is not None and error is not None:
                        conn.execute(
                            "UPDATE jobs SET status = ?, error = ?, updated_at = ? WHERE job_id = ?",
                            (status, error, now, job_id),
                        )
                    elif status is not None:
                        conn.execute(
                            "UPDATE jobs SET status = ?, updated_at = ? WHERE job_id = ?",
                            (status, now, job_id),
                        )
                    elif error is not None:
                        conn.execute(
                            "UPDATE jobs SET error = ?, updated_at = ? WHERE job_id = ?",
                            (error, now, job_id),
                        )
            finally:
                conn.close()

        await asyncio.to_thread(_op)

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        def _op():
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            try:
                cur = conn.execute(
                    "SELECT job_id, vm_id, status, error, created_at, updated_at FROM jobs WHERE job_id = ?",
                    (job_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "job_id": row[0],
                    "vm_id": row[1],
                    "status": row[2],
                    "error": row[3],
                    "created_at": row[4],
                    "updated_at": row[5],
                }
            finally:
                conn.close()

        return await asyncio.to_thread(_op)

