import json
import uuid
import subprocess
from pathlib import Path
import asyncio
from typing import Dict, List, Optional
from ..utils.retry import async_retry_unless_not_found, NonRetryableError

from ..config import settings
from ..utils.logging import setup_logger
from .models import VMConfig, VMInfo, VMResources, VMStatus, VMError, VMNotFoundError
from .provider import VMProvider

logger = setup_logger(__name__)


class MultipassError(VMError):
    """Raised when multipass operations fail."""
    pass


class NonRetryableMultipassError(MultipassError, NonRetryableError):
    """Multipass error that should not be retried (e.g., parse/validation errors)."""
    pass


class MultipassAdapter(VMProvider):
    """Manages VMs using Multipass."""

    def __init__(self, proxy_manager, name_mapper):
        self.multipass_path = settings.MULTIPASS_BINARY_PATH
        self.proxy_manager = proxy_manager
        self.name_mapper = name_mapper

    async def _run_multipass(self, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run a multipass command."""
        # Commands that produce JSON or version info that we need to parse.
        commands_to_capture = ['info', 'version']
        should_capture = args[0] in commands_to_capture

        # We add a timeout to the launch command to prevent it from hanging indefinitely
        # e.g. during image download. 300 seconds = 5 minutes.
        timeout = settings.LAUNCH_TIMEOUT_SECONDS if args[0] == 'launch' else None

        try:
            return await asyncio.to_thread(
                subprocess.run,
                [self.multipass_path, *args],
                capture_output=should_capture,
                text=True,
                check=check,
                timeout=timeout
            )
        except subprocess.CalledProcessError as e:
            stderr = e.stderr if should_capture and e.stderr else "No stderr captured. See provider logs for command output."
            raise MultipassError(f"Multipass command failed: {stderr}")
        except subprocess.TimeoutExpired as e:
            stderr = e.stderr if should_capture and e.stderr else "No stderr captured. See provider logs for command output."
            raise MultipassError(f"Multipass command '{' '.join(args)}' timed out after {timeout} seconds. Stderr: {stderr}")

    @async_retry_unless_not_found(
        retries=settings.RETRY_ATTEMPTS,
        delay=settings.RETRY_DELAY_SECONDS,
        backoff=settings.RETRY_BACKOFF,
    )
    async def _get_vm_info(self, vm_id: str) -> Dict:
        """Get detailed information about a VM."""
        try:
            result = await self._run_multipass(["info", vm_id, "--format", "json"])
            logger.info(f"Raw multipass info for {vm_id}: {result.stdout}")
            info = json.loads(result.stdout)
            vm_info = info["info"][vm_id]
            essential_fields = ["state", "ipv4", "cpu_count", "memory", "disks"]
            if not all(field in vm_info for field in essential_fields):
                raise KeyError(f"Essential fields missing from VM info. Got: {list(vm_info.keys())}")
            return vm_info
        except MultipassError as e:
            if "does not exist" in str(e):
                raise VMNotFoundError(f"VM {vm_id} not found in multipass") from e
            raise
        except (json.JSONDecodeError, KeyError) as e:
            # Parsing/validation issues are not transient; do not waste time retrying
            raise NonRetryableMultipassError(
                f"Failed to parse VM info or essential fields are missing: {e}"
            )

    async def initialize(self) -> None:
        """Initialize the VM provider."""
        try:
            result = await self._run_multipass(["version"])
            logger.info(f"🔧 Using Multipass version: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise MultipassError(f"Failed to verify multipass installation: {e}")

    async def create_vm(self, config: VMConfig) -> VMInfo:
        """Create a new VM."""
        multipass_name = f"golem-{uuid.uuid4()}"
        await self.name_mapper.add_mapping(config.name, multipass_name)

        launch_cmd = [
            "launch",
            config.image,
            "--name", multipass_name,
            "--cloud-init", config.cloud_init_path,
            "--cpus", str(config.resources.cpu),
            "--memory", f"{config.resources.memory}G",
            "--disk", f"{config.resources.storage}G"
        ]
        try:
            logger.info(f"Running multipass command: {' '.join(launch_cmd)}")
            await self._run_multipass(launch_cmd)
            logger.info(f"VM {multipass_name} launched, waiting for it to be ready...")

            ip_address = None
            max_retries = settings.CREATE_VM_MAX_RETRIES
            retry_delay = settings.CREATE_VM_RETRY_DELAY_SECONDS  # seconds
            for attempt in range(max_retries):
                try:
                    info = await self._get_vm_info(multipass_name)
                    if info.get("state", "").lower() == "running" and info.get("ipv4"):
                        ip_address = info["ipv4"][0]
                        break
                    logger.debug(f"VM {config.name} status is {info.get('state')}, waiting...")
                except (MultipassError, VMNotFoundError):
                    logger.debug(f"VM {config.name} not found yet, retrying in {retry_delay}s...")
                
                await asyncio.sleep(retry_delay)
            
            if not ip_address:
                raise MultipassError(f"VM {config.name} did not become ready or get an IP in time.")

            # Configure proxy to allocate a port
            if not await self.proxy_manager.add_vm(multipass_name, ip_address):
                raise MultipassError(f"Failed to configure proxy for VM {multipass_name}")

            # Now get the full status, which will include the allocated port
            vm_info = await self.get_vm_status(multipass_name)
            logger.info(f"Successfully created VM: {vm_info.dict()}")
            return vm_info

        except Exception as e:
            logger.error(f"VM creation for {config.name} failed. Cleaning up.", exc_info=True)
            await self._run_multipass(["delete", multipass_name, "--purge"], check=False)
            await self.proxy_manager.remove_vm(multipass_name)
            await self.name_mapper.remove_mapping(config.name)
            raise MultipassError(f"Failed to create VM {config.name}: {e}") from e

    async def delete_vm(self, multipass_name: str) -> None:
        """Delete a VM."""
        requestor_name = await self.name_mapper.get_requestor_name(multipass_name)
        if not requestor_name:
            logger.warning(f"No mapping found for {multipass_name}, cannot remove mapping.")
        else:
            await self.name_mapper.remove_mapping(requestor_name)
        await self._run_multipass(["delete", multipass_name, "--purge"], check=False)

    async def list_vms(self) -> List[VMInfo]:
        """List all VMs."""
        all_mappings = self.name_mapper.list_mappings()
        vms = []
        for requestor_name in all_mappings.keys():
            try:
                vm_info = await self.get_vm_status(requestor_name)
                vms.append(vm_info)
            except VMNotFoundError:
                logger.warning(f"VM {requestor_name} not found, but a mapping exists. It may have been deleted externally.")
        return vms

    async def start_vm(self, multipass_name: str) -> VMInfo:
        """Start a VM."""
        await self._run_multipass(["start", multipass_name])
        return await self.get_vm_status(multipass_name)

    async def stop_vm(self, multipass_name: str) -> VMInfo:
        """Stop a VM."""
        await self._run_multipass(["stop", multipass_name])
        return await self.get_vm_status(multipass_name)

    async def get_vm_status(self, multipass_name: str) -> VMInfo:
        """Get the status of a VM."""
        try:
            info = await self._get_vm_info(multipass_name)
        except MultipassError:
            raise VMNotFoundError(f"VM {multipass_name} not found in multipass")

        requestor_name = await self.name_mapper.get_requestor_name(multipass_name)
        if not requestor_name:
            raise VMNotFoundError(f"Mapping for VM {multipass_name} not found")

        ipv4 = info.get("ipv4")
        ip_address = ipv4[0] if ipv4 else None
        logger.debug(f"Parsed VM info for {requestor_name}: {info}")
        
        disks_info = info.get("disks", {})
        total_storage = sum(int(disk.get("total", 0)) for disk in disks_info.values())
        vm_info_obj = VMInfo(
            id=requestor_name,
            name=requestor_name,
            status=VMStatus(info["state"].lower()),
            resources=VMResources(
                cpu=int(info.get("cpu_count", "1")),
                memory=round(info.get("memory", {}).get("total", 1024**3) / (1024**3)),
                storage=round(total_storage / (1024**3)) if total_storage > 0 else 10
            ),
            ip_address=ip_address,
            ssh_port=self.proxy_manager.get_port(multipass_name)
        )
        logger.debug(f"Constructed VMInfo object: {vm_info_obj.dict()}")
        return vm_info_obj

    async def get_all_vms_resources(self) -> Dict[str, VMResources]:
        """Get resources for all running VMs."""
        all_mappings = self.name_mapper.list_mappings()
        vm_resources = {}
        for requestor_name, multipass_name in all_mappings.items():
            try:
                info = await self._get_vm_info(multipass_name)
                disks_info = info.get("disks", {})
                total_storage = sum(int(disk.get("total", 0)) for disk in disks_info.values())
                vm_resources[requestor_name] = VMResources(
                    cpu=int(info.get("cpu_count", "1")),
                    memory=round(info.get("memory", {}).get("total", 1024**3) / (1024**3)),
                    storage=round(total_storage / (1024**3)) if total_storage > 0 else 10
                )
            except (MultipassError, VMNotFoundError):
                logger.warning(f"Could not retrieve resources for VM {requestor_name} ({multipass_name}). It may have been deleted.")
            except Exception as e:
                logger.error(f"Failed to get info for VM {requestor_name}: {e}")
        return vm_resources

    async def cleanup(self) -> None:
        """Cleanup resources used by the provider."""
        pass
