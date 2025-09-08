import asyncio
import json
from pathlib import Path
from typing import Dict, Optional


class StreamMap:
    def __init__(self, storage_path: Path):
        self._path = storage_path
        self._lock = asyncio.Lock()
        self._data: Dict[str, int] = {}
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text())
            except Exception:
                self._data = {}

    async def set(self, vm_id: str, stream_id: int) -> None:
        async with self._lock:
            self._data[vm_id] = int(stream_id)
            self._persist()

    async def get(self, vm_id: str) -> Optional[int]:
        return self._data.get(vm_id)

    async def remove(self, vm_id: str) -> None:
        async with self._lock:
            if vm_id in self._data:
                del self._data[vm_id]
                self._persist()

    async def all_items(self) -> Dict[str, int]:
        return dict(self._data)

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2))
        tmp.replace(self._path)

