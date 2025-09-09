import aiohttp
from typing import Dict, Optional
from pathlib import Path

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
        """Create a VM on the provider."""
        payload = {
            "name": name,
            "resources": {
                "cpu": cpu,
                "memory": memory,
                "storage": storage
            },
            "ssh_key": ssh_key
        }
        if stream_id is not None:
            payload["stream_id"] = int(stream_id)
        async with self.session.post(
            f"{self.provider_url}/api/v1/vms",
            json=payload
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise Exception(f"Failed to create VM: {error_text}")
            return await response.json()

    async def get_provider_info(self) -> Dict:
        async with self.session.get(f"{self.provider_url}/api/v1/provider/info") as response:
            if not response.ok:
                error_text = await response.text()
                raise Exception(f"Failed to fetch provider info: {error_text}")
            return await response.json()

    async def add_ssh_key(self, vm_id: str, key: str) -> None:
        """Add SSH key to VM."""
        async with self.session.post(
            f"{self.provider_url}/api/v1/vms/{vm_id}/ssh-keys",
            json={
                "key": key,
                "name": "default"
            }
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise Exception(f"Failed to add SSH key: {error_text}")

    async def start_vm(self, vm_id: str) -> Dict:
        """Start a VM."""
        async with self.session.post(
            f"{self.provider_url}/api/v1/vms/{vm_id}/start"
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise Exception(f"Failed to start VM: {error_text}")
            return await response.json()

    async def stop_vm(self, vm_id: str) -> Dict:
        """Stop a VM."""
        async with self.session.post(
            f"{self.provider_url}/api/v1/vms/{vm_id}/stop"
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise Exception(f"Failed to stop VM: {error_text}")
            return await response.json()

    async def destroy_vm(self, vm_id: str) -> None:
        """Destroy a VM."""
        async with self.session.delete(
            f"{self.provider_url}/api/v1/vms/{vm_id}"
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise Exception(f"Failed to destroy VM: {error_text}")

    async def get_vm_access(self, vm_id: str) -> Dict:
        """Get VM access information."""
        async with self.session.get(
            f"{self.provider_url}/api/v1/vms/{vm_id}/access"
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise Exception(f"Failed to get VM access info: {error_text}")
            return await response.json()

    async def get_vm_stream_status(self, vm_id: str) -> Dict:
        """Get on-chain stream status for a VM from provider."""
        async with self.session.get(
            f"{self.provider_url}/api/v1/vms/{vm_id}/stream"
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise Exception(f"Failed to get VM stream status: {error_text}")
            return await response.json()
