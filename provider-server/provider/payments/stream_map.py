import asyncio
import json
from pathlib import Path
from typing import Any, Dict, Optional


class StreamMap:
    def __init__(self, storage_path: Path):
        self._path = storage_path
        self._lock = asyncio.Lock()
        self._data: Dict[str, Any] = {}
        if self._path.exists():
            data = json.loads(self._path.read_text())
            if not isinstance(data, dict):
                raise ValueError(f"stream map {self._path} must contain a JSON object")
            self._data = data

    async def set(
        self, vm_id: str, stream_id: int, requestor_address: str | None = None
    ) -> None:
        async with self._lock:
            self._data[vm_id] = {
                "stream_id": int(stream_id),
                "requestor_address": requestor_address,
            }
            self._persist()

    async def get(self, vm_id: str) -> Optional[int]:
        value = self._data.get(vm_id)
        if isinstance(value, dict):
            stream_id = value.get("stream_id")
            return int(stream_id) if stream_id is not None else None
        return int(value) if value is not None else None

    async def get_owner(self, vm_id: str) -> Optional[str]:
        value = self._data.get(vm_id)
        if isinstance(value, dict):
            owner = value.get("requestor_address")
            return str(owner) if owner else None
        return None

    async def set_owner(self, vm_id: str, requestor_address: str) -> None:
        async with self._lock:
            value = self._data.get(vm_id)
            if isinstance(value, dict):
                value["requestor_address"] = requestor_address
            elif value is not None:
                value = {
                    "stream_id": int(value),
                    "requestor_address": requestor_address,
                }
                self._data[vm_id] = value
            else:
                raise KeyError(f"stream mapping for VM {vm_id} not found")
            self._persist()

    async def remove(self, vm_id: str) -> None:
        async with self._lock:
            if vm_id in self._data:
                del self._data[vm_id]
                self._persist()

    async def all_items(self) -> Dict[str, int]:
        items: Dict[str, int] = {}
        for vm_id, value in self._data.items():
            if isinstance(value, dict):
                stream_id = value.get("stream_id")
                if stream_id is not None:
                    items[vm_id] = int(stream_id)
            elif value is not None:
                items[vm_id] = int(value)
        return items

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2))
        tmp.replace(self._path)
