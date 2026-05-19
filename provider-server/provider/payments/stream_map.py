import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from provider.utils.time import utc_now

StreamState = Literal["active", "terminated"]
TerminationActor = Literal["requestor", "provider"]
TerminationReason = Literal[
    "requestor_terminated", "provider_terminated", "stream_expired"
]
CleanupState = Literal["not_started", "completed", "failed"]

REQUIRED_RECORD_KEYS = {
    "vm_id",
    "stream_id",
    "requestor_address",
    "state",
    "terminated_by",
    "termination_reason",
    "terminated_at",
    "settlement_tx_hash",
    "cleanup_state",
}


class StreamMap:
    def __init__(self, storage_path: Path):
        self._path = storage_path
        self._lock = asyncio.Lock()
        self._data: Dict[str, dict[str, Any]] = {}
        if self._path.exists():
            data = json.loads(self._path.read_text())
            if not isinstance(data, dict):
                raise ValueError(f"stream map {self._path} must contain a JSON object")
            self._data = self._validate_records(data)

    async def set(
        self, vm_id: str, stream_id: int, requestor_address: str | None = None
    ) -> None:
        if not requestor_address:
            raise ValueError("requestor_address is required for stream records")
        async with self._lock:
            self._data[vm_id] = {
                "vm_id": vm_id,
                "stream_id": int(stream_id),
                "requestor_address": requestor_address,
                "state": "active",
                "terminated_by": None,
                "termination_reason": None,
                "terminated_at": None,
                "settlement_tx_hash": None,
                "cleanup_state": None,
            }
            self._persist()

    async def get(self, vm_id: str) -> Optional[int]:
        record = self._data.get(vm_id)
        if not record or record["state"] != "active":
            return None
        return int(record["stream_id"])

    async def get_record(self, vm_id: str) -> Optional[dict[str, Any]]:
        record = self._data.get(vm_id)
        return dict(record) if record else None

    async def get_owner(self, vm_id: str) -> Optional[str]:
        record = self._data.get(vm_id)
        if record:
            owner = record.get("requestor_address")
            return str(owner) if owner else None
        return None

    async def set_owner(self, vm_id: str, requestor_address: str) -> None:
        async with self._lock:
            record = self._data.get(vm_id)
            if not record:
                raise KeyError(f"stream mapping for VM {vm_id} not found")
            record["requestor_address"] = requestor_address
            self._persist()

    async def mark_terminated(
        self,
        vm_id: str,
        *,
        terminated_by: TerminationActor,
        termination_reason: TerminationReason,
        settlement_tx_hash: str | None,
        cleanup_state: CleanupState,
    ) -> dict[str, Any]:
        async with self._lock:
            record = self._data.get(vm_id)
            if not record:
                raise KeyError(f"stream mapping for VM {vm_id} not found")
            record.update(
                {
                    "state": "terminated",
                    "terminated_by": terminated_by,
                    "termination_reason": termination_reason,
                    "terminated_at": utc_now().isoformat(),
                    "settlement_tx_hash": settlement_tx_hash,
                    "cleanup_state": cleanup_state,
                }
            )
            self._persist()
            return dict(record)

    async def set_cleanup_state(
        self, vm_id: str, cleanup_state: CleanupState
    ) -> dict[str, Any]:
        async with self._lock:
            record = self._data.get(vm_id)
            if not record:
                raise KeyError(f"stream mapping for VM {vm_id} not found")
            if record["state"] != "terminated":
                raise ValueError(f"stream mapping for VM {vm_id} is not terminated")
            record["cleanup_state"] = cleanup_state
            self._persist()
            return dict(record)

    async def remove(self, vm_id: str) -> None:
        async with self._lock:
            if vm_id in self._data:
                del self._data[vm_id]
                self._persist()

    async def all_items(self) -> Dict[str, int]:
        return await self.active_items()

    async def active_items(self) -> Dict[str, int]:
        items: Dict[str, int] = {}
        for vm_id, record in self._data.items():
            if record["state"] == "active":
                items[vm_id] = int(record["stream_id"])
        return items

    async def records(self) -> Dict[str, dict[str, Any]]:
        return {vm_id: dict(record) for vm_id, record in self._data.items()}

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2))
        tmp.replace(self._path)

    def _validate_records(self, data: dict[str, Any]) -> Dict[str, dict[str, Any]]:
        records: Dict[str, dict[str, Any]] = {}
        for vm_id, raw in data.items():
            if not isinstance(raw, dict):
                raise ValueError(
                    f"stream map {self._path} contains legacy entry for {vm_id}; "
                    "delete or recreate the file with structured stream records"
                )
            missing = REQUIRED_RECORD_KEYS.difference(raw)
            if missing:
                raise ValueError(
                    f"stream map {self._path} entry {vm_id} is missing required "
                    f"fields: {', '.join(sorted(missing))}"
                )
            if raw["vm_id"] != vm_id:
                raise ValueError(
                    f"stream map {self._path} entry {vm_id} has mismatched vm_id"
                )
            state = raw["state"]
            if state not in {"active", "terminated"}:
                raise ValueError(f"stream map {self._path} entry {vm_id} has bad state")
            if int(raw["stream_id"]) < 0:
                raise ValueError(
                    f"stream map {self._path} entry {vm_id} has bad stream_id"
                )
            if not raw["requestor_address"]:
                raise ValueError(
                    f"stream map {self._path} entry {vm_id} requires requestor_address"
                )
            if state == "active":
                if any(
                    raw[field] is not None
                    for field in (
                        "terminated_by",
                        "termination_reason",
                        "terminated_at",
                        "settlement_tx_hash",
                        "cleanup_state",
                    )
                ):
                    raise ValueError(
                        f"stream map {self._path} active entry {vm_id} contains "
                        "terminal metadata"
                    )
            else:
                if raw["terminated_by"] not in {"requestor", "provider"}:
                    raise ValueError(
                        f"stream map {self._path} terminated entry {vm_id} has bad "
                        "terminated_by"
                    )
                if raw["termination_reason"] not in {
                    "requestor_terminated",
                    "provider_terminated",
                    "stream_expired",
                }:
                    raise ValueError(
                        f"stream map {self._path} terminated entry {vm_id} has bad "
                        "termination_reason"
                    )
                if raw["cleanup_state"] not in {
                    "not_started",
                    "completed",
                    "failed",
                }:
                    raise ValueError(
                        f"stream map {self._path} terminated entry {vm_id} has bad "
                        "cleanup_state"
                    )
            records[vm_id] = dict(raw)
        return records
