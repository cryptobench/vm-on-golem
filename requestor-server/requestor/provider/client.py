from typing import Dict, Optional

import aiohttp

from requestor.errors import ProviderError


class ProviderClient:
    def __init__(self, provider_url: str):
        self.provider_url = provider_url
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def create_vm(
        self,
        name: str,
        cpu: int,
        memory: int,
        storage: int,
        ssh_key: str,
        stream_id: int | None = None,
    ) -> Dict:
        """Create a VM on the provider (async job semantics)."""
        session = self._require_session()
        payload = {
            "name": name,
            "resources": {"cpu": cpu, "memory": memory, "storage": storage},
            "ssh_key": ssh_key,
        }
        if stream_id is not None:
            payload["stream_id"] = int(stream_id)
        async with session.post(
            f"{self.provider_url}/api/v1/vms?async=true", json=payload
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to create VM: {error_text}")
            data = await response.json()
            # Normalize: support both old (VMInfo) and new (job) responses
            # New shape: { job_id, vm_id, status }
            # Old shape: { id, ... }
            if isinstance(data, dict) and "job_id" in data:
                return data
            # Fallback: synthesize a job-like envelope from immediate VM info
            vm_id = data.get("id") or data.get("name") or name
            return {
                "job_id": "",
                "vm_id": vm_id,
                "status": data.get("status", "ready"),
                "_vm": data,
            }

    async def get_vm_info(self, vm_id: str) -> Dict:
        session = self._require_session()
        async with session.get(f"{self.provider_url}/api/v1/vms/{vm_id}") as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to get VM info: {error_text}")
            return await response.json()

    async def get_provider_info(self) -> Dict:
        session = self._require_session()
        async with session.get(f"{self.provider_url}/api/v1/provider/info") as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to fetch provider info: {error_text}")
            return await response.json()

    async def add_ssh_key(self, vm_id: str, key: str) -> None:
        """Add SSH key to VM."""
        session = self._require_session()
        async with session.post(
            f"{self.provider_url}/api/v1/vms/{vm_id}/ssh-keys",
            json={"key": key, "name": "default"},
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to add SSH key: {error_text}")

    async def start_vm(self, vm_id: str) -> Dict:
        """Start a VM."""
        session = self._require_session()
        async with session.post(
            f"{self.provider_url}/api/v1/vms/{vm_id}/start"
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to start VM: {error_text}")
            return await response.json()

    async def stop_vm(self, vm_id: str) -> Dict:
        """Stop a VM."""
        session = self._require_session()
        async with session.post(
            f"{self.provider_url}/api/v1/vms/{vm_id}/stop"
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to stop VM: {error_text}")
            return await response.json()

    async def restart_vm(self, vm_id: str) -> Dict:
        """Restart a VM."""
        return await self._post_vm_action(vm_id, "restart", "restart VM")

    async def suspend_vm(self, vm_id: str) -> Dict:
        """Suspend a VM."""
        return await self._post_vm_action(vm_id, "suspend", "suspend VM")

    async def resume_vm(self, vm_id: str) -> Dict:
        """Resume a suspended VM."""
        return await self._post_vm_action(vm_id, "resume", "resume VM")

    async def resize_vm(self, vm_id: str, cpu: int, memory: int, storage: int) -> Dict:
        """Resize a VM."""
        session = self._require_session()
        async with session.post(
            f"{self.provider_url}/api/v1/vms/{vm_id}/resize",
            json={"resources": {"cpu": cpu, "memory": memory, "storage": storage}},
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to resize VM: {error_text}")
            return await response.json()

    async def list_images(self) -> list[Dict]:
        """List provider images."""
        session = self._require_session()
        async with session.get(f"{self.provider_url}/api/v1/images") as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to list images: {error_text}")
            return await response.json()

    async def list_snapshots(self, vm_id: str) -> list[Dict]:
        """List VM snapshots."""
        session = self._require_session()
        async with session.get(
            f"{self.provider_url}/api/v1/vms/{vm_id}/snapshots"
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to list snapshots: {error_text}")
            return await response.json()

    async def create_snapshot(
        self, vm_id: str, name: str | None = None, comment: str | None = None
    ) -> Dict:
        """Create a VM snapshot."""
        session = self._require_session()
        payload = {}
        if name:
            payload["name"] = name
        if comment:
            payload["comment"] = comment
        async with session.post(
            f"{self.provider_url}/api/v1/vms/{vm_id}/snapshots", json=payload
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to create snapshot: {error_text}")
            return await response.json()

    async def restore_snapshot(self, vm_id: str, snapshot_name: str) -> Dict:
        """Restore a VM snapshot."""
        session = self._require_session()
        async with session.post(
            f"{self.provider_url}/api/v1/vms/{vm_id}/snapshots/{snapshot_name}/restore"
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to restore snapshot: {error_text}")
            return await response.json()

    async def delete_snapshot(self, vm_id: str, snapshot_name: str) -> None:
        """Delete a VM snapshot."""
        session = self._require_session()
        async with session.delete(
            f"{self.provider_url}/api/v1/vms/{vm_id}/snapshots/{snapshot_name}"
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to delete snapshot: {error_text}")

    async def clone_vm(self, vm_id: str, name: str) -> Dict:
        """Clone a VM."""
        session = self._require_session()
        async with session.post(
            f"{self.provider_url}/api/v1/vms/{vm_id}/clone", json={"name": name}
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to clone VM: {error_text}")
            return await response.json()

    async def destroy_vm(self, vm_id: str) -> None:
        """Destroy a VM."""
        session = self._require_session()
        async with session.delete(
            f"{self.provider_url}/api/v1/vms/{vm_id}"
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to destroy VM: {error_text}")

    async def get_vm_access(self, vm_id: str) -> Dict:
        """Get VM access information."""
        session = self._require_session()
        async with session.get(
            f"{self.provider_url}/api/v1/vms/{vm_id}/access"
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to get VM access info: {error_text}")
            return await response.json()

    async def get_vm_stream_status(self, vm_id: str) -> Dict:
        """Get on-chain stream status for a VM from provider."""
        session = self._require_session()
        async with session.get(
            f"{self.provider_url}/api/v1/vms/{vm_id}/stream"
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to get VM stream status: {error_text}")
            return await response.json()

    def _require_session(self) -> aiohttp.ClientSession:
        if self.session is None:
            raise ProviderError(
                "ProviderClient must be used as an async context manager"
            )
        return self.session

    async def _post_vm_action(self, vm_id: str, action: str, label: str) -> Dict:
        session = self._require_session()
        async with session.post(
            f"{self.provider_url}/api/v1/vms/{vm_id}/{action}"
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to {label}: {error_text}")
            return await response.json()
