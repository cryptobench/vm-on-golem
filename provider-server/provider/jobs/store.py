import asyncio
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class JobRecord:
    job_id: str
    vm_id: str
    status: str
    lifecycle_stage: str
    status_message: str
    progress: int
    transitioning: bool
    next_poll_seconds: int
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
                        lifecycle_stage TEXT NOT NULL DEFAULT 'queued',
                        status_message TEXT NOT NULL DEFAULT 'Queued VM creation',
                        progress INTEGER NOT NULL DEFAULT 0,
                        transitioning INTEGER NOT NULL DEFAULT 1,
                        next_poll_seconds INTEGER NOT NULL DEFAULT 2,
                        error TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                existing = {
                    row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
                }
                migrations = {
                    "lifecycle_stage": "TEXT NOT NULL DEFAULT 'queued'",
                    "status_message": "TEXT NOT NULL DEFAULT 'Queued VM creation'",
                    "progress": "INTEGER NOT NULL DEFAULT 0",
                    "transitioning": "INTEGER NOT NULL DEFAULT 1",
                    "next_poll_seconds": "INTEGER NOT NULL DEFAULT 2",
                }
                for column, definition in migrations.items():
                    if column not in existing:
                        conn.execute(
                            f"ALTER TABLE jobs ADD COLUMN {column} {definition}"
                        )
        finally:
            conn.close()

    async def create_job(
        self,
        job_id: str,
        vm_id: str,
        status: str = "creating",
        *,
        lifecycle_stage: str = "queued",
        status_message: str = "Queued VM creation",
        progress: int = 0,
        transitioning: bool = True,
        next_poll_seconds: int = 2,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()

        def _op():
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO jobs (
                            job_id,
                            vm_id,
                            status,
                            lifecycle_stage,
                            status_message,
                            progress,
                            transitioning,
                            next_poll_seconds,
                            error,
                            created_at,
                            updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                        """,
                        (
                            job_id,
                            vm_id,
                            status,
                            lifecycle_stage,
                            status_message,
                            int(progress),
                            1 if transitioning else 0,
                            int(next_poll_seconds),
                            now,
                            now,
                        ),
                    )
            finally:
                conn.close()

        await asyncio.to_thread(_op)

    async def update_job(
        self,
        job_id: str,
        *,
        status: Optional[str] = None,
        lifecycle_stage: Optional[str] = None,
        status_message: Optional[str] = None,
        progress: Optional[int] = None,
        transitioning: Optional[bool] = None,
        next_poll_seconds: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()

        def _op():
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            try:
                with conn:
                    assignments = []
                    params = []
                    transition_value = None
                    if transitioning is not None:
                        transition_value = 1 if transitioning else 0
                    values = {
                        "status": status,
                        "lifecycle_stage": lifecycle_stage,
                        "status_message": status_message,
                        "progress": progress,
                        "transitioning": transition_value,
                        "next_poll_seconds": next_poll_seconds,
                        "error": error,
                    }
                    for column, value in values.items():
                        if value is not None:
                            assignments.append(f"{column} = ?")
                            params.append(value)
                    if not assignments:
                        return
                    assignments.append("updated_at = ?")
                    params.extend([now, job_id])
                    conn.execute(
                        f"UPDATE jobs SET {', '.join(assignments)} WHERE job_id = ?",
                        params,
                    )
            finally:
                conn.close()

        await asyncio.to_thread(_op)

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        def _op():
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            try:
                cur = conn.execute(
                    """
                    SELECT
                        job_id,
                        vm_id,
                        status,
                        lifecycle_stage,
                        status_message,
                        progress,
                        transitioning,
                        next_poll_seconds,
                        error,
                        created_at,
                        updated_at
                    FROM jobs
                    WHERE job_id = ?
                    """,
                    (job_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "job_id": row[0],
                    "vm_id": row[1],
                    "status": row[2],
                    "lifecycle_stage": row[3],
                    "status_message": row[4],
                    "progress": row[5],
                    "transitioning": bool(row[6]),
                    "next_poll_seconds": row[7],
                    "error": row[8],
                    "created_at": row[9],
                    "updated_at": row[10],
                }
            finally:
                conn.close()

        return await asyncio.to_thread(_op)
