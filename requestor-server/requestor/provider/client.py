import logging
import hashlib
import json
import time
from typing import Dict, Optional

import aiohttp
from eth_account import Account
from eth_account.messages import encode_typed_data

from requestor.errors import ProviderError
from requestor.config import config

logger = logging.getLogger(__name__)


class ProviderClient:
    def __init__(self, provider_url: str):
        self.provider_url = provider_url
        self.session = None

    async def __aenter__(self):
        trace_config = aiohttp.TraceConfig()

        async def on_request_start(session, trace_config_ctx, params):
            trace_config_ctx.started_at = time.perf_counter()

        async def on_request_end(session, trace_config_ctx, params):
            elapsed = time.perf_counter() - trace_config_ctx.started_at
            log = logger.warning if params.response.status >= 400 else logger.debug
            log(
                "Provider HTTP request completed",
                extra={
                    "method": params.method,
                    "url": str(params.url),
                    "status_code": params.response.status,
                    "elapsed_seconds": round(elapsed, 3),
                },
            )

        async def on_request_exception(session, trace_config_ctx, params):
            elapsed = time.perf_counter() - getattr(
                trace_config_ctx, "started_at", time.perf_counter()
            )
            logger.warning(
                "Provider HTTP request failed",
                extra={
                    "method": params.method,
                    "url": str(params.url),
                    "elapsed_seconds": round(elapsed, 3),
                    "error": str(params.exception),
                },
            )

        trace_config.on_request_start.append(on_request_start)
        trace_config.on_request_end.append(on_request_end)
        trace_config.on_request_exception.append(on_request_exception)
        self.session = aiohttp.ClientSession(trace_configs=[trace_config])
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
        payment: dict | None = None,
    ) -> Dict:
        """Create a VM on the provider (async job semantics)."""
        payload = {
            "name": name,
            "resources": {"cpu": cpu, "memory": memory, "storage": storage},
            "ssh_key": ssh_key,
        }
        if payment is not None:
            payload["payment"] = payment
        async with self._post_json("/api/v1/vms?async=true", payload) as response:
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

    async def create_lease_quote(self, payload: Dict) -> Dict:
        session = self._require_session()
        async with session.post(
            f"{self.provider_url}/api/v1/payments/lease-quotes", json=payload
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to create lease quote: {error_text}")
            return await response.json()

    async def get_create_job(self, job_id: str) -> Dict:
        """Get provider-side VM creation job lifecycle status."""
        session = self._require_session()
        async with session.get(
            f"{self.provider_url}/api/v1/vms/jobs/{job_id}"
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to get VM creation job: {error_text}")
            return await response.json()

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
        async with self._post_json(f"/api/v1/vms/{vm_id}/start", {}) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to start VM: {error_text}")
            return await response.json()

    async def stop_vm(self, vm_id: str) -> Dict:
        """Stop a VM."""
        async with self._post_json(f"/api/v1/vms/{vm_id}/stop", {}) as response:
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
        async with self._post_json(
            f"/api/v1/vms/{vm_id}/resize",
            {"resources": {"cpu": cpu, "memory": memory, "storage": storage}},
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
        payload = {}
        if name:
            payload["name"] = name
        if comment:
            payload["comment"] = comment
        async with self._post_json(
            f"/api/v1/vms/{vm_id}/snapshots", payload
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to create snapshot: {error_text}")
            return await response.json()

    async def restore_snapshot(self, vm_id: str, snapshot_name: str) -> Dict:
        """Restore a VM snapshot."""
        async with self._post_json(
            f"/api/v1/vms/{vm_id}/snapshots/{snapshot_name}/restore", {}
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to restore snapshot: {error_text}")
            return await response.json()

    async def delete_snapshot(self, vm_id: str, snapshot_name: str) -> None:
        """Delete a VM snapshot."""
        async with self._delete_signed(
            f"/api/v1/vms/{vm_id}/snapshots/{snapshot_name}"
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to delete snapshot: {error_text}")

    async def clone_vm(self, vm_id: str, name: str) -> Dict:
        """Clone a VM."""
        async with self._post_json(
            f"/api/v1/vms/{vm_id}/clone", {"name": name}
        ) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to clone VM: {error_text}")
            return await response.json()

    async def destroy_vm(self, vm_id: str) -> None:
        """Destroy a VM."""
        async with self._delete_signed(f"/api/v1/vms/{vm_id}") as response:
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
        async with self._post_json(f"/api/v1/vms/{vm_id}/{action}", {}) as response:
            if not response.ok:
                error_text = await response.text()
                raise ProviderError(f"Failed to {label}: {error_text}")
            return await response.json()

    def _signed_headers(self, method: str, path: str, body: str) -> Dict[str, str]:
        account = Account.from_key(config.ethereum_private_key)
        deadline = int(time.time()) + 300
        body_hash = "0x" + hashlib.sha256(body.encode()).hexdigest()
        nonce = str(time.time_ns())
        signable = encode_typed_data(
            domain_data={"name": "GolemProviderAction", "version": "2"},
            message_types={
                "ProviderAction": [
                    {"name": "requestor", "type": "address"},
                    {"name": "method", "type": "string"},
                    {"name": "path", "type": "string"},
                    {"name": "bodyHash", "type": "bytes32"},
                    {"name": "nonce", "type": "string"},
                    {"name": "deadline", "type": "uint256"},
                ]
            },
            message_data={
                "requestor": account.address,
                "method": method.upper(),
                "path": path,
                "bodyHash": body_hash,
                "nonce": nonce,
                "deadline": deadline,
            },
        )
        signature = Account.sign_message(
            signable, private_key=config.ethereum_private_key
        ).signature.hex()
        return {
            "content-type": "application/json",
            "x-golem-requestor": account.address,
            "x-golem-signature": signature,
            "x-golem-nonce": nonce,
            "x-golem-deadline": str(deadline),
        }

    def _post_json(self, path: str, payload: Dict):
        session = self._require_session()
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        clean_path = path.split("?", 1)[0]
        return session.post(
            f"{self.provider_url}{path}",
            data=body,
            headers=self._signed_headers("POST", clean_path, body),
        )

    def _delete_signed(self, path: str):
        session = self._require_session()
        body = ""
        return session.delete(
            f"{self.provider_url}{path}",
            headers=self._signed_headers("DELETE", path, body),
        )
