import asyncio
import json
import subprocess
import uuid
from typing import Dict, List, Optional

from ..config import settings
from ..utils.logging import setup_logger
from ..utils.retry import NonRetryableError, async_retry_unless_not_found
from .multipass_requirements import (
    MultipassCompatibilityError,
    check_host_virtualization_compatibility,
    detect_multipass_binary,
)
from .lifecycle import ProgressCallback, creation_lifecycle, lifecycle_for_status
from .models import (
    VMConfig,
    VMError,
    VMImage,
    VMInfo,
    VMNotFoundError,
    VMResources,
    VMSnapshot,
    VMStatus,
)
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
        self.multipass_path = (
            settings.MULTIPASS_BINARY_PATH
            or detect_multipass_binary()
            or "multipass"
        )
        self.proxy_manager = proxy_manager
        self.name_mapper = name_mapper

    @staticmethod
    def _safe_int(value, default: int = 0) -> int:
        """Best-effort int conversion that treats missing/blank values as default.

        Multipass may return empty strings for numeric fields (e.g., when a VM is
        stopped). This helper prevents ValueError by mapping '', None, or
        unparsable values to a sensible default.
        """
        try:
            if value is None:
                return default
            if isinstance(value, str):
                v = value.strip()
                if v == "":
                    return default
                return int(v)
            return int(value)
        except (ValueError, TypeError):
            return default

    async def _run_multipass(
        self, args: List[str], check: bool = True
    ) -> subprocess.CompletedProcess:
        """Run a multipass command."""
        # Commands that produce JSON or version info that we need to parse.
        commands_to_capture = ["info", "version", "find"]
        should_capture = args[0] in commands_to_capture

        # We add a timeout to the launch command to prevent it from hanging indefinitely
        # e.g. during image download. 300 seconds = 5 minutes.
        timeout = settings.LAUNCH_TIMEOUT_SECONDS if args[0] == "launch" else None

        try:
            return await asyncio.to_thread(
                subprocess.run,
                [self.multipass_path, *args],
                capture_output=should_capture,
                text=True,
                check=check,
                timeout=timeout,
            )
        except subprocess.CalledProcessError as e:
            stderr = (
                e.stderr
                if should_capture and e.stderr
                else "No stderr captured. See provider logs for command output."
            )
            raise MultipassError(f"Multipass command failed: {stderr}")
        except subprocess.TimeoutExpired as e:
            stderr = (
                e.stderr
                if should_capture and e.stderr
                else "No stderr captured. See provider logs for command output."
            )
            raise MultipassError(
                f"Multipass command '{' '.join(args)}' timed out after {timeout} seconds. Stderr: {stderr}"
            )

    @async_retry_unless_not_found(
        retries=settings.RETRY_ATTEMPTS,
        delay=settings.RETRY_DELAY_SECONDS,
        backoff=settings.RETRY_BACKOFF,
    )
    async def _get_vm_info(self, vm_id: str) -> Dict:
        """Get detailed information about a VM."""
        try:
            result = await self._run_multipass(["info", vm_id, "--format", "json"])
            # Only log raw multipass output in debug mode to avoid noisy logs
            logger.debug(f"Raw multipass info for {vm_id}: {result.stdout}")
            info = json.loads(result.stdout)
            vm_info = info["info"][vm_id]
            essential_fields = ["state", "ipv4", "cpu_count", "memory", "disks"]
            if not all(field in vm_info for field in essential_fields):
                raise KeyError(
                    f"Essential fields missing from VM info. Got: {list(vm_info.keys())}"
                )
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
            self._check_host_virtualization_compatibility()
            if hasattr(self.proxy_manager, "initialize"):
                await self.proxy_manager.initialize()
            await self._restore_missing_proxy_listeners()
            await self._log_startup_mapping_summary()
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            raise MultipassError(f"Failed to verify multipass installation: {e}")

    async def create_vm(
        self,
        config: VMConfig,
        progress_callback: ProgressCallback | None = None,
    ) -> VMInfo:
        """Create a new VM.

        Uses a pre-assigned multipass_name from VMConfig when provided to keep
        name mapping stable across the provisioning window. Falls back to a
        generated name for backward compatibility.
        """
        multipass_name = config.multipass_name or f"golem-{uuid.uuid4()}"
        # If the name was generated here, ensure the mapping exists.
        if not config.multipass_name:
            await self.name_mapper.add_mapping(config.name, multipass_name)

        launch_cmd = [
            "launch",
            config.image,
            "--name",
            multipass_name,
            "--cloud-init",
            config.cloud_init_path,
            "--cpus",
            str(config.resources.cpu),
            "--memory",
            f"{config.resources.memory}G",
            "--disk",
            f"{config.resources.storage}G",
        ]
        try:
            logger.info(f"Running multipass command: {' '.join(launch_cmd)}")
            await self._report_progress(
                progress_callback,
                "launching",
                "Launching VM image",
                35,
            )
            await self._run_multipass(launch_cmd)
            logger.info(f"VM {multipass_name} launched, waiting for it to be ready...")
            await self._report_progress(
                progress_callback,
                "waiting_for_guest",
                "Waiting for VM to start",
                60,
            )

            ip_address = None
            max_retries = settings.CREATE_VM_MAX_RETRIES
            retry_delay = settings.CREATE_VM_RETRY_DELAY_SECONDS  # seconds
            for attempt in range(max_retries):
                try:
                    info = await self._get_vm_info(multipass_name)
                    if info.get("state", "").lower() == "running" and info.get("ipv4"):
                        ip_address = info["ipv4"][0]
                        break
                    state = info.get("state") or "starting"
                    await self._report_progress(
                        progress_callback,
                        "waiting_for_guest",
                        f"Multipass reports {state}",
                        min(85, 60 + attempt),
                    )
                    logger.debug(
                        f"VM {config.name} status is {info.get('state')}, waiting..."
                    )
                except (MultipassError, VMNotFoundError):
                    logger.debug(
                        f"VM {config.name} not found yet, retrying in {retry_delay}s..."
                    )

                await asyncio.sleep(retry_delay)

            if not ip_address:
                raise MultipassError(
                    f"VM {config.name} did not become ready or get an IP in time."
                )

            # Configure proxy to allocate a port
            await self._report_progress(
                progress_callback,
                "configuring_access",
                "Configuring SSH access",
                90,
            )
            if not await self.proxy_manager.add_vm(multipass_name, ip_address):
                raise MultipassError(
                    f"Failed to configure proxy for VM {multipass_name}"
                )

            # Now get the full status, which will include the allocated port
            vm_info = await self.get_vm_status(multipass_name)
            await self._report_progress(
                progress_callback,
                "ready",
                "VM is online",
                100,
            )
            logger.info(f"Successfully created VM: {vm_info.dict()}")
            return vm_info

        except Exception as e:
            logger.error(
                f"VM creation for {config.name} failed. Cleaning up.", exc_info=True
            )
            await self._run_multipass(
                ["delete", multipass_name, "--purge"], check=False
            )
            await self.proxy_manager.remove_vm(multipass_name)
            await self.name_mapper.remove_mapping(config.name)
            raise MultipassError(f"Failed to create VM {config.name}: {e}") from e

    async def delete_vm(self, multipass_name: str) -> None:
        """Delete a VM."""
        requestor_name = await self.name_mapper.get_requestor_name(multipass_name)
        if not requestor_name:
            logger.warning(
                f"No mapping found for {multipass_name}, cannot remove mapping."
            )
        else:
            await self.name_mapper.remove_mapping(requestor_name)
        await self._run_multipass(["delete", multipass_name, "--purge"], check=False)

    async def list_vms(self) -> List[VMInfo]:
        """List all VMs."""
        all_mappings = self.name_mapper.list_mappings()
        vms: List[VMInfo] = []
        for requestor_name, multipass_name in list(all_mappings.items()):
            try:
                # Pass requestor id; get_vm_status accepts either id
                vm_info = await self.get_vm_status(requestor_name)
                vms.append(vm_info)
            except VMNotFoundError:
                logger.warning(
                    f"VM {requestor_name} not found, but a mapping exists. It may have been deleted externally."
                )
                # Cleanup stale mapping and proxy allocation to avoid repeated warnings
                try:
                    await self.proxy_manager.remove_vm(multipass_name)
                except Exception:
                    pass
                try:
                    await self.name_mapper.remove_mapping(requestor_name)
                except Exception:
                    pass
        return vms

    async def start_vm(self, multipass_name: str) -> VMInfo:
        """Start a VM."""
        await self._run_multipass(["start", multipass_name])
        return await self.get_vm_status(multipass_name)

    async def stop_vm(self, multipass_name: str) -> VMInfo:
        """Stop a VM."""
        await self._run_multipass(["stop", multipass_name])
        return await self.get_vm_status(multipass_name)

    async def restart_vm(self, multipass_name: str) -> VMInfo:
        """Restart a VM."""
        await self._run_multipass(["restart", multipass_name])
        return await self.get_vm_status(multipass_name)

    async def suspend_vm(self, multipass_name: str) -> VMInfo:
        """Suspend a VM."""
        await self._run_multipass(["suspend", multipass_name])
        return await self.get_vm_status(multipass_name)

    async def resize_vm(self, multipass_name: str, resources: VMResources) -> VMInfo:
        """Resize a stopped VM."""
        settings_to_apply = {
            "cpus": str(resources.cpu),
            "memory": f"{resources.memory}G",
            "disk": f"{resources.storage}G",
        }
        for key, value in settings_to_apply.items():
            await self._run_multipass(["set", f"local.{multipass_name}.{key}={value}"])
        return await self.get_vm_status(multipass_name)

    async def list_images(self) -> list[VMImage]:
        """List available Multipass images."""
        result = await self._run_multipass(["find", "--format", "json"])
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise NonRetryableMultipassError(
                f"Failed to parse Multipass image list: {exc}"
            ) from exc

        images: list[VMImage] = []
        entries = data.get("images", data)
        if isinstance(entries, dict):
            iterable = entries.values()
        elif isinstance(entries, list):
            iterable = entries
        else:
            iterable = []
        for entry in iterable:
            if not isinstance(entry, dict):
                continue
            alias = (
                entry.get("alias")
                or entry.get("release")
                or entry.get("name")
                or entry.get("os")
            )
            if alias:
                images.append(
                    VMImage(
                        alias=str(alias),
                        version=entry.get("version"),
                        description=entry.get("description") or entry.get("title"),
                    )
                )
        return images

    async def list_snapshots(self, multipass_name: str) -> list[VMSnapshot]:
        """List snapshots for a VM."""
        result = await self._run_multipass(
            ["info", multipass_name, "--snapshots", "--format", "json"]
        )
        try:
            data = json.loads(result.stdout)
            vm_info = data.get("info", {}).get(multipass_name, {})
        except (json.JSONDecodeError, AttributeError) as exc:
            raise NonRetryableMultipassError(
                f"Failed to parse Multipass snapshot info: {exc}"
            ) from exc

        snapshots = vm_info.get("snapshots", {})
        if isinstance(snapshots, dict):
            items = snapshots.items()
        elif isinstance(snapshots, list):
            items = (
                (snap.get("name"), snap) for snap in snapshots if isinstance(snap, dict)
            )
        else:
            items = []

        return [
            VMSnapshot(
                name=str(name),
                vm_id=await self._requestor_name_for(multipass_name),
                comment=snap.get("comment") if isinstance(snap, dict) else None,
                created_at=(
                    snap.get("created")
                    or snap.get("created_at")
                    or snap.get("creation_time")
                )
                if isinstance(snap, dict)
                else None,
            )
            for name, snap in items
            if name
        ]

    async def create_snapshot(
        self, multipass_name: str, name: str | None = None, comment: str | None = None
    ) -> VMSnapshot:
        """Create a snapshot for a stopped VM."""
        args = ["snapshot", multipass_name]
        if name:
            args.extend(["--name", name])
        if comment:
            args.extend(["--comment", comment])
        before = {snap.name for snap in await self.list_snapshots(multipass_name)}
        await self._run_multipass(args)
        snapshots = await self.list_snapshots(multipass_name)
        if name:
            for snapshot in snapshots:
                if snapshot.name == name:
                    return snapshot
            return VMSnapshot(
                name=name,
                vm_id=await self._requestor_name_for(multipass_name),
                comment=comment,
            )
        created = [snapshot for snapshot in snapshots if snapshot.name not in before]
        if created:
            return created[-1]
        return VMSnapshot(
            name="snapshot",
            vm_id=await self._requestor_name_for(multipass_name),
            comment=comment,
        )

    async def restore_snapshot(self, multipass_name: str, snapshot_name: str) -> VMInfo:
        """Restore a stopped VM from a snapshot."""
        await self._run_multipass(
            ["restore", "-d", f"{multipass_name}.{snapshot_name}"]
        )
        return await self.get_vm_status(multipass_name)

    async def delete_snapshot(self, multipass_name: str, snapshot_name: str) -> None:
        """Delete a snapshot."""
        await self._run_multipass(
            ["delete", f"{multipass_name}.{snapshot_name}"], check=False
        )

    async def clone_vm(
        self, source_multipass_name: str, destination_name: str
    ) -> VMInfo:
        """Clone a stopped VM."""
        await self._run_multipass(
            ["clone", source_multipass_name, "--name", destination_name]
        )
        return await self.get_vm_status(destination_name)

    async def _requestor_name_for(self, multipass_name: str) -> str:
        requestor_name = await self.name_mapper.get_requestor_name(multipass_name)
        return requestor_name or multipass_name

    async def get_vm_status(self, name_or_id: str) -> VMInfo:
        """Get VM status by multipass name or requestor id."""
        # Resolve identifiers flexibly
        requestor_name = await self.name_mapper.get_requestor_name(name_or_id)
        if requestor_name:
            multipass_name = name_or_id
        else:
            multipass_name = await self.name_mapper.get_multipass_name(name_or_id)
            if not multipass_name:
                raise VMNotFoundError(f"VM {name_or_id} mapping not found")
            requestor_name = name_or_id
        try:
            info = await self._get_vm_info(multipass_name)
        except MultipassError:
            raise VMNotFoundError(f"VM {multipass_name} not found in multipass")

        ipv4 = info.get("ipv4")
        ip_address = ipv4[0] if ipv4 else None
        logger.debug(f"Parsed VM info for {requestor_name}: {info}")

        disks_info = info.get("disks", {})
        total_storage = 0
        for disk in disks_info.values():
            total_storage += self._safe_int(disk.get("total"), 0)

        # Memory reported by multipass is in bytes; default to 1 GiB if missing/blank
        mem_total_bytes = self._safe_int(info.get("memory", {}).get("total"), 1024**3)
        vm_info_obj = VMInfo(
            id=requestor_name,
            name=requestor_name,
            status=VMStatus.from_multipass(info.get("state")),
            resources=VMResources(
                cpu=self._safe_int(info.get("cpu_count"), 1),
                memory=round(mem_total_bytes / (1024**3)),
                storage=round(total_storage / (1024**3)) if total_storage > 0 else 10,
            ),
            ip_address=ip_address,
            ssh_port=self.proxy_manager.get_port(multipass_name),
        )
        lifecycle = lifecycle_for_status(vm_info_obj.status)
        vm_info_obj.lifecycle_stage = lifecycle.lifecycle_stage
        vm_info_obj.status_message = lifecycle.status_message
        vm_info_obj.progress = lifecycle.progress
        vm_info_obj.transitioning = lifecycle.transitioning
        vm_info_obj.next_poll_seconds = lifecycle.next_poll_seconds
        logger.debug(f"Constructed VMInfo object: {vm_info_obj.dict()}")
        return vm_info_obj

    async def _restore_missing_proxy_listeners(self) -> None:
        """Start SSH proxies for running mapped VMs whose proxy is not listening."""
        if not hasattr(self.name_mapper, "list_mappings"):
            return
        mappings = self.name_mapper.list_mappings()
        if not mappings:
            logger.info("No VM name mappings found during proxy restoration")
            return
        logger.info(f"Checking {len(mappings)} VM mapping(s) for SSH proxy listeners")
        for requestor_name, multipass_name in list(mappings.items()):
            if self.proxy_manager.get_port(multipass_name) is not None:
                continue
            try:
                info = await self._get_vm_info(multipass_name)
            except (MultipassError, VMNotFoundError) as exc:
                logger.warning(
                    f"Could not restore SSH proxy for {requestor_name}: {exc}"
                )
                continue
            if info.get("state", "").lower() != "running" or not info.get("ipv4"):
                continue
            vm_ip = info["ipv4"][0]
            if await self.proxy_manager.add_vm(multipass_name, vm_ip):
                logger.info(
                    f"Restored missing SSH proxy for {requestor_name} ({multipass_name})"
                )
            else:
                logger.error(
                    f"Failed to restore SSH proxy for {requestor_name} ({multipass_name})"
                )

    async def _log_startup_mapping_summary(self) -> None:
        """Log requestor-to-Multipass mappings and live SSH proxy state."""
        if not hasattr(self.name_mapper, "list_mappings"):
            return
        mappings = self.name_mapper.list_mappings()
        if not mappings:
            logger.info("Startup VM mapping summary: no VM mappings")
            return

        logger.info(f"Startup VM mapping summary: {len(mappings)} mapping(s)")
        for requestor_name, multipass_name in sorted(mappings.items()):
            proxy_port = self.proxy_manager.get_port(multipass_name)
            try:
                info = await self._get_vm_info(multipass_name)
                state = info.get("state") or "unknown"
                ipv4 = info.get("ipv4") or []
                ip_address = ipv4[0] if ipv4 else None
                logger.info(
                    "VM mapping "
                    f"requestor_vm={requestor_name} "
                    f"multipass={multipass_name} "
                    f"multipass_state={state} "
                    f"ip={ip_address or 'none'} "
                    f"ssh_proxy_port={proxy_port or 'not_listening'}"
                )
            except (MultipassError, VMNotFoundError) as exc:
                logger.warning(
                    "VM mapping "
                    f"requestor_vm={requestor_name} "
                    f"multipass={multipass_name} "
                    f"multipass_state=unavailable "
                    f"ssh_proxy_port={proxy_port or 'not_listening'} "
                    f"error={exc}"
                )

    @staticmethod
    async def _report_progress(
        progress_callback: ProgressCallback | None,
        stage: str,
        message: str,
        progress: int,
    ) -> None:
        if progress_callback is None:
            return
        await progress_callback(creation_lifecycle(stage, message, progress))

    async def get_all_vms_resources(self) -> Dict[str, VMResources]:
        """Get resources for all running VMs."""
        all_mappings = self.name_mapper.list_mappings()
        vm_resources: Dict[str, VMResources] = {}
        for requestor_name, multipass_name in list(all_mappings.items()):
            try:
                info = await self._get_vm_info(multipass_name)
                disks_info = info.get("disks", {})
                total_storage = 0
                for disk in disks_info.values():
                    total_storage += self._safe_int(disk.get("total"), 0)
                mem_total_bytes = self._safe_int(
                    info.get("memory", {}).get("total"), 1024**3
                )
                vm_resources[requestor_name] = VMResources(
                    cpu=self._safe_int(info.get("cpu_count"), 1),
                    memory=round(mem_total_bytes / (1024**3)),
                    storage=round(total_storage / (1024**3))
                    if total_storage > 0
                    else 10,
                )
            except (MultipassError, VMNotFoundError):
                logger.warning(
                    f"Could not retrieve resources for VM {requestor_name} ({multipass_name}). It may have been deleted."
                )
                # Cleanup stale mapping and proxy allocation
                try:
                    await self.proxy_manager.remove_vm(multipass_name)
                except Exception:
                    pass
                try:
                    await self.name_mapper.remove_mapping(requestor_name)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Failed to get info for VM {requestor_name}: {e}")
        return vm_resources

    async def cleanup(self) -> None:
        """Cleanup resources used by the provider."""
        pass

    def _check_host_virtualization_compatibility(self) -> None:
        """Fail early for known host/driver combinations that cannot launch VMs."""
        try:
            check_host_virtualization_compatibility(self.multipass_path)
        except MultipassCompatibilityError as exc:
            raise MultipassError(str(exc)) from exc
