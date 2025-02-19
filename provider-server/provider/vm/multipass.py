import asyncio
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..config import settings
from .models import (
    VMConfig,
    VMInfo,
    VMStatus,
    VMResources,
    SSHKey,
    VMCreateError,
    VMNotFoundError,
    VMStateError,
    VMProvider,
    VMError,
    ResourceError,
)

logger = logging.getLogger(__name__)


class MultipassProvider(VMProvider):
    def __init__(
        self,
        resource_tracker: 'ResourceTracker',
        multipass_path: Optional[str] = None
    ):
        self.multipass_path = multipass_path or settings.MULTIPASS_PATH
        self.vms: Dict[str, VMInfo] = {}
        self.resource_tracker = resource_tracker

    async def initialize(self) -> None:
        """Initialize the provider."""
        try:
            # Verify multipass is installed and working
            stdout, _, _ = await self._run_command("version")
            logger.info(f"Multipass version: {stdout}")

            # List existing VMs and add them to our state
            stdout, _, _ = await self._run_command("list", "--format", "json")
            vms = json.loads(stdout)
            if "list" in vms:  # Check if list key exists
                for vm in vms["list"]:
                    vm_id = str(uuid.uuid4())
                    resources = VMResources(
                        cpu=vm.get("cpu", 1),
                        memory=vm.get("memory", 1),
                        storage=vm.get("disk", 10)
                    )
                    # Allocate resources for existing VMs
                    if not await self.resource_tracker.allocate(resources):
                        logger.warning(
                            f"Could not allocate resources for existing VM {vm['name']}"
                        )
                        continue

                    self.vms[vm_id] = VMInfo(
                        id=vm_id,
                        name=vm["name"],
                        status=VMStatus.RUNNING if vm["state"] == "Running" else VMStatus.STOPPED,
                        resources=resources,
                        ip_address=vm.get("ipv4", [])[
                            0] if vm.get("ipv4") else None,
                        ssh_port=22
                    )
            logger.info("Provider initialization complete")
        except Exception as e:
            logger.error(f"Failed to initialize provider: {e}")
            raise

    async def cleanup(self) -> None:
        """Cleanup provider resources."""
        try:
            # Stop all running VMs
            for vm_id, vm_info in self.vms.items():
                if vm_info.status == VMStatus.RUNNING:
                    try:
                        await self.stop_vm(vm_id)
                    except Exception as e:
                        logger.error(f"Failed to stop VM {vm_id}: {e}")
                # Deallocate resources
                await self.resource_tracker.deallocate(vm_info.resources)
        except Exception as e:
            logger.error(f"Failed to cleanup provider: {e}")
            raise

    async def _run_command(
        self,
        *args: str,
        check: bool = True,
        timeout: int = 30
    ) -> Tuple[str, str, int]:
        """Run a multipass command with timeout."""
        cmd = [self.multipass_path, *args]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            stdout_str = stdout.decode().strip()
            stderr_str = stderr.decode().strip()

            if check and process.returncode != 0:
                raise VMError(
                    f"Multipass command failed: {stderr_str}",
                    vm_id=args[1] if len(args) > 1 else None
                )

            return stdout_str, stderr_str, process.returncode
        except asyncio.TimeoutError:
            try:
                process.kill()
            except:
                pass
            raise VMError(f"Command timed out after {timeout} seconds: {' '.join(cmd)}")
        except Exception as e:
            try:
                process.kill()
            except:
                pass
            raise VMError(f"Command failed: {str(e)}")

    async def _get_vm_ip(self, name: str) -> Optional[str]:
        """Get VM IP address."""
        try:
            stdout, _, _ = await self._run_command("info", name, "--format", "json")
            info = json.loads(stdout)
            return info["info"][name]["ipv4"][0]
        except Exception as e:
            logger.error(f"Failed to get VM IP: {e}")
            return None

    async def create_vm(self, config: VMConfig) -> VMInfo:
        """Create a new VM using Multipass."""
        # First try to allocate resources
        if not await self.resource_tracker.allocate(config.resources):
            raise ResourceError("Insufficient resources available")

        vm_id = str(uuid.uuid4())
        vm_info = VMInfo(
            id=vm_id,
            name=config.name,
            status=VMStatus.CREATING,
            resources=config.resources
        )
        self.vms[vm_id] = vm_info

        try:
            # Create cloud-init config
            from .cloud_init import CloudInitManager
            cloud_init = CloudInitManager.create_config(config.ssh_key)

            # Launch VM with cloud-init
            await self._run_command(
                "launch",
                "--name", config.name,
                "--cpus", str(config.resources.cpu),
                "--memory", f"{config.resources.memory}GB",
                "--disk", f"{config.resources.storage}GB",
                "--cloud-init", str(cloud_init),
                config.image
            )

            # Get VM IP
            ip_address = await self._get_vm_ip(config.name)
            if not ip_address:
                raise VMCreateError("Failed to get VM IP address")

            # Update VM info
            vm_info.status = VMStatus.RUNNING
            vm_info.ip_address = ip_address
            vm_info.ssh_port = 22
            self.vms[vm_id] = vm_info

            return vm_info

        except Exception as e:
            # Deallocate resources on failure
            await self.resource_tracker.deallocate(config.resources)
            vm_info.status = VMStatus.ERROR
            vm_info.error_message = str(e)
            self.vms[vm_id] = vm_info
            raise VMCreateError(str(e), vm_id=vm_id)
        finally:
            # Clean up cloud-init file
            if 'cloud_init' in locals():
                cloud_init.unlink()

    async def delete_vm(self, vm_id: str) -> None:
        """Delete a VM."""
        vm_info = self.vms.get(vm_id)
        if not vm_info:
            raise VMNotFoundError(f"VM {vm_id} not found")

        try:
            await self._run_command("delete", vm_info.name)
            vm_info.status = VMStatus.DELETED
            self.vms[vm_id] = vm_info
            # Deallocate resources
            await self.resource_tracker.deallocate(vm_info.resources)
        except Exception as e:
            raise VMError(f"Failed to delete VM: {e}", vm_id=vm_id)

    async def start_vm(self, vm_id: str) -> VMInfo:
        """Start a VM."""
        vm_info = self.vms.get(vm_id)
        if not vm_info:
            raise VMNotFoundError(f"VM {vm_id} not found")

        if vm_info.status == VMStatus.RUNNING:
            return vm_info

        if vm_info.status not in [VMStatus.STOPPED, VMStatus.ERROR]:
            raise VMStateError(
                f"Cannot start VM in {vm_info.status} state",
                vm_id=vm_id
            )

        try:
            await self._run_command("start", vm_info.name)

            # Get VM IP
            ip_address = await self._get_vm_ip(vm_info.name)
            if not ip_address:
                raise VMError("Failed to get VM IP address")

            vm_info.status = VMStatus.RUNNING
            vm_info.ip_address = ip_address
            self.vms[vm_id] = vm_info
            return vm_info

        except Exception as e:
            vm_info.status = VMStatus.ERROR
            vm_info.error_message = str(e)
            self.vms[vm_id] = vm_info
            raise VMError(f"Failed to start VM: {e}", vm_id=vm_id)

    async def stop_vm(self, vm_id: str) -> VMInfo:
        """Stop a VM."""
        vm_info = self.vms.get(vm_id)
        if not vm_info:
            raise VMNotFoundError(f"VM {vm_id} not found")

        if vm_info.status == VMStatus.STOPPED:
            return vm_info

        if vm_info.status != VMStatus.RUNNING:
            raise VMStateError(
                f"Cannot stop VM in {vm_info.status} state",
                vm_id=vm_id
            )

        try:
            vm_info.status = VMStatus.STOPPING
            self.vms[vm_id] = vm_info

            await self._run_command("stop", vm_info.name)

            vm_info.status = VMStatus.STOPPED
            vm_info.ip_address = None
            self.vms[vm_id] = vm_info
            return vm_info

        except Exception as e:
            vm_info.status = VMStatus.ERROR
            vm_info.error_message = str(e)
            self.vms[vm_id] = vm_info
            raise VMError(f"Failed to stop VM: {e}", vm_id=vm_id)

    async def get_vm_status(self, vm_id: str) -> VMInfo:
        """Get VM status."""
        vm_info = self.vms.get(vm_id)
        if not vm_info:
            raise VMNotFoundError(f"VM {vm_id} not found")

        try:
            stdout, _, _ = await self._run_command(
                "info",
                vm_info.name,
                "--format",
                "json"
            )
            info = json.loads(stdout)
            state = info["info"][vm_info.name]["state"]

            # Map Multipass state to our VMStatus
            status_map = {
                "Running": VMStatus.RUNNING,
                "Stopped": VMStatus.STOPPED,
                "Starting": VMStatus.CREATING,
                "Stopping": VMStatus.STOPPING
            }

            vm_info.status = status_map.get(state, VMStatus.ERROR)
            if vm_info.status == VMStatus.RUNNING:
                vm_info.ip_address = info["info"][vm_info.name]["ipv4"][0]

            self.vms[vm_id] = vm_info
            return vm_info

        except Exception as e:
            vm_info.status = VMStatus.ERROR
            vm_info.error_message = str(e)
            self.vms[vm_id] = vm_info
            raise VMError(f"Failed to get VM status: {e}", vm_id=vm_id)
