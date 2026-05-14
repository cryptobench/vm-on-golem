"""VM management service."""
import logging
from datetime import datetime
from typing import Dict, List, Optional

from ..errors import RequestorError, VMError
from ..provider.client import ProviderClient
from ..vm.access import require_ssh_user
from .database_service import DatabaseService
from .ssh_service import SSHService

logger = logging.getLogger(__name__)


class VMService:
    """Service for VM operations."""

    def __init__(
        self,
        db_service: DatabaseService,
        ssh_service: SSHService,
        provider_client: Optional[ProviderClient] = None,
        blockchain_client: Optional[object] = None,
    ):
        self.db = db_service
        self.ssh_service = ssh_service
        self.provider_client = provider_client
        self.blockchain_client = blockchain_client

    async def create_vm(
        self,
        name: str,
        cpu: int,
        memory: int,
        storage: int,
        provider_ip: str,
        ssh_key: str,
        stream_id: int | None = None,
    ) -> Dict:
        """Create a new VM with validation and error handling."""
        try:
            logger.info(
                "Legacy requestor VM create requested",
                extra={"vm_name": name, "provider_ip": provider_ip},
            )
            # Check if VM name already exists
            existing_vm = await self.db.get_vm(name)
            if existing_vm:
                raise VMError(f"VM with name '{name}' already exists")

            # Create VM on provider (returns job envelope)
            job = await self.provider_client.create_vm(
                name=name,
                cpu=cpu,
                memory=memory,
                storage=storage,
                ssh_key=ssh_key,
                stream_id=stream_id,
            )
            logger.info(
                "Provider accepted legacy VM create request",
                extra={"vm_name": name, "job_id": job.get("job_id")},
            )

            vm_id = job.get("vm_id") or job.get("id") or name

            # Save initial record with 'creating' status (no port yet)
            await self.db.save_vm(
                name=name,
                provider_ip=provider_ip,
                vm_id=vm_id,
                config={
                    "cpu": cpu,
                    "memory": memory,
                    "storage": storage,
                    **({"stream_id": stream_id} if stream_id is not None else {}),
                },
                status="creating",
            )
            logger.info("Saved legacy VM creation record", extra={"vm_name": name})

            if "job_id" in job and job.get("status") not in {"ready", "running"}:
                # Poll provider until VM is ready, then fetch access info.
                import asyncio as _asyncio

                deadline = _asyncio.get_event_loop().time() + 600.0  # 10 minutes max
                last_status = "creating"
                while _asyncio.get_event_loop().time() < deadline:
                    info = await self.provider_client.get_vm_info(vm_id)
                    last_status = (info.get("status") or "").lower() or last_status
                    logger.debug(
                        "Polling legacy VM create status",
                        extra={"vm_name": name, "vm_id": vm_id, "status": last_status},
                    )
                    if last_status == "running":
                        break
                    await _asyncio.sleep(2.0)
                if last_status != "running":
                    logger.warning(
                        "Timed out waiting for legacy VM to become ready",
                        extra={"vm_name": name, "last_status": last_status},
                    )
                    raise VMError(
                        f"VM did not become ready in time (status={last_status})"
                    )

            # Get VM access info (ssh port)
            access_info = await self.provider_client.get_vm_access(vm_id)

            # Preserve any provided stream_id; do not auto-create streams here
            # Stream creation should be explicit via CLI `vm stream open` command.

            # Save VM details to database
            config = {
                "cpu": cpu,
                "memory": memory,
                "storage": storage,
                "ssh_port": access_info["ssh_port"],
                "ssh_user": require_ssh_user(access_info),
                **({"stream_id": stream_id} if stream_id is not None else {}),
            }
            await self.db.save_vm(
                name=name,
                provider_ip=provider_ip,
                vm_id=access_info["vm_id"],
                config=config,
                status="running",
            )
            logger.info("Legacy requestor VM is running", extra={"vm_name": name})

            return {
                "name": name,
                "provider_ip": provider_ip,
                "vm_id": access_info["vm_id"],
                "config": config,
                "status": "running",
            }

        except Exception as e:
            logger.error("Legacy requestor VM create failed", exc_info=True)
            raise VMError(f"Failed to create VM: {str(e)}")

    async def destroy_vm(self, name: str) -> None:
        """Destroy a VM and clean up resources."""
        try:
            # Get VM details
            vm = await self.db.get_vm(name)
            if not vm:
                raise VMError(f"VM '{name}' not found")

            # Terminate stream before deleting provider resources. This is the
            # billing end-of-lease operation: it pays vested funds and refunds
            # unused deposit.
            stream_id = vm.get("config", {}).get("stream_id")
            if stream_id is not None and self.blockchain_client:
                try:
                    self.blockchain_client.terminate(stream_id)
                except Exception as e:
                    if "no-stream" not in str(e).lower():
                        logger.error(
                            "Failed to terminate stream during legacy VM destroy",
                            extra={"vm_name": name, "stream_id": stream_id},
                            exc_info=True,
                        )
                        raise
                    logger.warning(
                        "Ignoring missing stream during legacy VM destroy",
                        extra={"vm_name": name, "stream_id": stream_id},
                    )

            try:
                # Destroy VM on provider
                await self.provider_client.destroy_vm(vm["vm_id"])
            except Exception as e:
                if "Not Found" not in str(e):
                    raise

            # Remove from database
            await self.db.delete_vm(name)
            logger.info("Legacy requestor VM destroyed", extra={"vm_name": name})

        except Exception as e:
            logger.error(
                "Legacy requestor VM destroy failed",
                extra={"vm_name": name},
                exc_info=True,
            )
            raise VMError(f"Failed to destroy VM: {str(e)}")

    async def start_vm(self, name: str) -> None:
        """Start a stopped VM."""
        try:
            # Get VM details
            vm = await self.db.get_vm(name)
            if not vm:
                raise VMError(f"VM '{name}' not found")

            # Start VM on provider
            await self.provider_client.start_vm(vm["vm_id"])

            # Update status in database
            await self.db.update_vm_status(name, "running")
            logger.info("Legacy requestor VM started", extra={"vm_name": name})

        except Exception as e:
            logger.error(
                "Legacy requestor VM start failed",
                extra={"vm_name": name},
                exc_info=True,
            )
            raise VMError(f"Failed to start VM: {str(e)}")

    async def stop_vm(self, name: str) -> None:
        """Stop a running VM."""
        try:
            # Get VM details
            vm = await self.db.get_vm(name)
            if not vm:
                raise VMError(f"VM '{name}' not found")

            # Stop VM on provider
            await self.provider_client.stop_vm(vm["vm_id"])

            # Update status in database
            await self.db.update_vm_status(name, "stopped")
            logger.info("Legacy requestor VM stopped", extra={"vm_name": name})

        except Exception as e:
            logger.error(
                "Legacy requestor VM stop failed",
                extra={"vm_name": name},
                exc_info=True,
            )
            raise VMError(f"Failed to stop VM: {str(e)}")

    async def restart_vm(self, name: str) -> Dict:
        """Restart a VM."""
        return await self._vm_action(name, "restart_vm", "running")

    async def suspend_vm(self, name: str) -> Dict:
        """Suspend a VM."""
        return await self._vm_action(name, "suspend_vm", "suspended")

    async def resume_vm(self, name: str) -> Dict:
        """Resume a suspended VM."""
        return await self._vm_action(name, "resume_vm", "running")

    async def resize_vm(
        self,
        name: str,
        cpu: int,
        memory: int,
        storage: int,
        stream_id: int | None = None,
    ) -> Dict:
        """Resize a stopped VM."""
        try:
            vm = await self.db.get_vm(name)
            if not vm:
                raise VMError(f"VM '{name}' not found")
            if vm.get("config", {}).get("stream_id") is not None and stream_id is None:
                logger.warning(
                    "Paid legacy VM resize missing replacement stream",
                    extra={"vm_name": name},
                )
                raise VMError("resizing a paid VM requires a replacement stream")

            result = await self.provider_client.resize_vm(
                vm["vm_id"], cpu, memory, storage
            )
            config = {
                **vm["config"],
                "cpu": cpu,
                "memory": memory,
                "storage": storage,
                **({"stream_id": stream_id} if stream_id is not None else {}),
            }
            await self.db.update_vm_config(
                name, config, result.get("status", vm["status"])
            )
            logger.info("Legacy requestor VM resized", extra={"vm_name": name})
            return result
        except Exception as e:
            logger.error(
                "Legacy requestor VM resize failed",
                extra={"vm_name": name},
                exc_info=True,
            )
            raise VMError(f"Failed to resize VM: {str(e)}")

    async def list_images(self) -> List[Dict]:
        """List images exposed by the selected provider client."""
        try:
            return await self.provider_client.list_images()
        except Exception as e:
            raise VMError(f"Failed to list images: {str(e)}")

    async def list_snapshots(self, name: str) -> List[Dict]:
        """List snapshots for a VM."""
        vm = await self._require_vm(name)
        return await self.provider_client.list_snapshots(vm["vm_id"])

    async def create_snapshot(
        self, name: str, snapshot_name: str | None = None, comment: str | None = None
    ) -> Dict:
        """Create a VM snapshot."""
        vm = await self._require_vm(name)
        return await self.provider_client.create_snapshot(
            vm["vm_id"], snapshot_name, comment
        )

    async def restore_snapshot(self, name: str, snapshot_name: str) -> Dict:
        """Restore a VM snapshot."""
        vm = await self._require_vm(name)
        result = await self.provider_client.restore_snapshot(vm["vm_id"], snapshot_name)
        await self._sync_status_from_result(name, vm, result)
        return result

    async def delete_snapshot(self, name: str, snapshot_name: str) -> None:
        """Delete a VM snapshot."""
        vm = await self._require_vm(name)
        await self.provider_client.delete_snapshot(vm["vm_id"], snapshot_name)

    async def clone_vm(
        self, source_name: str, new_name: str, stream_id: int | None = None
    ) -> Dict:
        """Clone a stopped VM."""
        source = await self._require_vm(source_name)
        existing = await self.db.get_vm(new_name)
        if existing:
            raise VMError(f"VM with name '{new_name}' already exists")
        if source.get("config", {}).get("stream_id") is not None and stream_id is None:
            raise VMError("cloning a paid VM requires a replacement stream")
        result = await self.provider_client.clone_vm(source["vm_id"], new_name)
        config = {
            **source["config"],
            **({"stream_id": stream_id} if stream_id is not None else {}),
        }
        await self.db.save_vm(
            name=new_name,
            provider_ip=source["provider_ip"],
            vm_id=result.get("id") or new_name,
            config=config,
            status=result.get("status", "stopped"),
        )
        return result

    async def list_vms(self) -> List[Dict]:
        """List all VMs with their current status."""
        try:
            logger.debug("Listing legacy requestor VMs")
            return await self.db.list_vms()
        except Exception as e:
            raise VMError(f"Failed to list VMs: {str(e)}")

    async def get_vm(self, name: str) -> Optional[Dict]:
        """Get VM details by name."""
        try:
            vm = await self.db.get_vm(name)
            if not vm:
                return None
            return await self._ensure_ssh_user(vm)
        except Exception as e:
            raise VMError(f"Failed to get VM details: {str(e)}")

    async def _ensure_ssh_user(self, vm: Dict) -> Dict:
        if vm.get("config", {}).get("ssh_user"):
            return vm
        if self.provider_client is None:
            raise VMError(
                "VM access details are missing SSH login user and provider "
                "connection is unavailable"
            )

        access_info = await self.provider_client.get_vm_access(vm["vm_id"])
        logger.debug("Backfilled legacy VM SSH access", extra={"vm_name": vm["name"]})
        config = {
            **vm["config"],
            "ssh_user": require_ssh_user(access_info),
            **(
                {"ssh_port": access_info.get("ssh_port")}
                if access_info.get("ssh_port") is not None
                else {}
            ),
        }
        await self.db.update_vm_config(vm["name"], config, vm.get("status"))
        return {**vm, "config": config}

    async def _vm_action(
        self, name: str, method_name: str, fallback_status: str
    ) -> Dict:
        try:
            vm = await self._require_vm(name)
            result = await getattr(self.provider_client, method_name)(vm["vm_id"])
            await self._sync_status_from_result(name, vm, result, fallback_status)
            logger.info(
                "Legacy requestor VM lifecycle action completed",
                extra={"vm_name": name, "action": method_name},
            )
            return result
        except Exception as e:
            logger.error(
                "Legacy requestor VM lifecycle action failed",
                extra={"vm_name": name, "action": method_name},
                exc_info=True,
            )
            raise VMError(f"Failed to update VM lifecycle: {str(e)}")

    async def _require_vm(self, name: str) -> Dict:
        vm = await self.db.get_vm(name)
        if not vm:
            raise VMError(f"VM '{name}' not found")
        return vm

    async def _sync_status_from_result(
        self,
        name: str,
        vm: Dict,
        result: Dict,
        fallback_status: str | None = None,
    ) -> None:
        resources = result.get("resources") or {}
        config = {
            **vm["config"],
            **(
                {
                    "cpu": resources.get("cpu"),
                    "memory": resources.get("memory"),
                    "storage": resources.get("storage"),
                }
                if resources
                else {}
            ),
            **(
                {"ssh_port": result.get("ssh_port")}
                if result.get("ssh_port") is not None
                else {}
            ),
            **(
                {"ssh_user": require_ssh_user(result)}
                if result.get("ssh_user") is not None
                else {}
            ),
        }
        await self.db.update_vm_config(
            name, config, result.get("status", fallback_status or vm["status"])
        )

    def format_vm_row(self, vm: Dict, colorize: bool = False) -> List:
        """Format VM information for display."""
        from click import style

        key_pair = self.ssh_service.get_key_pair_sync()
        connect_command = self.ssh_service.format_ssh_command(
            host=vm["provider_ip"],
            port=vm["config"].get("ssh_port", "N/A"),
            private_key_path=key_pair.private_key.absolute(),
            username=self._local_ssh_user(vm),
        )

        row = [
            vm["name"],
            vm["status"],
            vm["provider_ip"],
            vm["config"].get("ssh_port", "N/A"),
            vm["config"]["cpu"],
            vm["config"]["memory"],
            vm["config"]["storage"],
            connect_command,
            vm["created_at"],
        ]

        if colorize:
            # Format status with color and icon
            status = row[1]
            if status == "running":
                row[1] = style("● " + status, fg="green", bold=True)
            elif status == "stopped":
                row[1] = style("● " + status, fg="yellow", bold=True)
            else:
                row[1] = style("● " + status, fg="red", bold=True)

            # Format other columns
            row[0] = style(row[0], fg="cyan")  # Name
            row[2] = style(row[2], fg="cyan")  # IP
            row[3] = style(str(row[3]), fg="cyan")  # Port

        return row

    @property
    def vm_headers(self) -> List[str]:
        """Get headers for VM display."""
        return [
            "Name",
            "Status",
            "IP Address",
            "SSH Port",
            "CPU",
            "Memory (GB)",
            "Disk (GB)",
            "Connect Command",
            "Created",
        ]

    async def get_vm_stats(self, name: str) -> Dict:
        """Get VM stats by name."""
        try:
            vm = await self.get_vm(name)
            if not vm:
                raise VMError(f"VM '{name}' not found")

            key_pair = await self.ssh_service.get_key_pair()

            return self.ssh_service.get_vm_stats(
                host=vm["provider_ip"],
                port=vm["config"]["ssh_port"],
                private_key_path=key_pair.private_key,
                username=require_ssh_user(vm["config"]),
            )
        except Exception as e:
            raise VMError(f"Failed to get VM stats: {str(e)}")

    @staticmethod
    def _local_ssh_user(vm: Dict) -> str:
        return require_ssh_user(vm.get("config", {}))
