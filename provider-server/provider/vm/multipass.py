import os
import json
import subprocess
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

from ..config import settings
from ..utils.logging import setup_logger, PROCESS, SUCCESS
from .models import VMInfo, VMStatus, VMCreateRequest, VMConfig, VMProvider, VMError, VMCreateError, VMResources, VMNotFoundError
from .cloud_init import generate_cloud_init, cleanup_cloud_init
from .proxy_manager import PythonProxyManager
from .name_mapper import VMNameMapper

logger = setup_logger(__name__)


class MultipassError(VMError):
    """Raised when multipass operations fail."""
    pass


class MultipassProvider(VMProvider):
    """Manages VMs using Multipass."""

    def __init__(self, resource_tracker: "ResourceTracker", port_manager: "PortManager"):
        """Initialize the multipass provider.

        Args:
            resource_tracker: Resource tracker instance
            port_manager: Port manager instance for SSH port allocation
        """
        self.resource_tracker = resource_tracker
        self.port_manager = port_manager
        self.multipass_path = settings.MULTIPASS_BINARY_PATH
        self.vm_data_dir = Path(settings.VM_DATA_DIR)
        self.vm_data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize managers
        self.proxy_manager = PythonProxyManager()
        self.name_mapper = VMNameMapper(self.vm_data_dir / "vm_names.json")

    def _verify_installation(self) -> None:
        """Verify multipass is installed and get version."""
        try:
            result = subprocess.run(
                [self.multipass_path, "version"],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info(f"🔧 Using Multipass version: {result.stdout.strip()}")
        except subprocess.CalledProcessError as e:
            raise MultipassError(
                f"Failed to verify multipass installation: {e.stderr}")
        except FileNotFoundError:
            raise MultipassError(
                f"Multipass not found at {self.multipass_path}")

    def _get_all_vms_resources(self) -> Dict[str, VMResources]:
        """Get resources for all running VMs from multipass.
        
        Returns:
            Dictionary mapping VM names to their resources
        """
        result = self._run_multipass(["list", "--format", "json"])
        data = json.loads(result.stdout)
        vm_resources = {}
        
        for vm in data.get("list", []):
            if vm.get("name", "").startswith("golem-"):
                try:
                    info = self._get_vm_info(vm["name"])
                    vm_resources[vm["name"]] = VMResources(
                        cpu=int(info.get("cpu_count", 1)),
                        memory=int(info.get("memory_total", 1024) / 1024),
                        storage=int(info.get("disk_total", 10 * 1024) / 1024)
                    )
                except Exception as e:
                    logger.error(f"Failed to get info for VM {vm['name']}: {e}")
                    continue
        
        return vm_resources

    async def initialize(self) -> None:
        """Initialize the provider."""
        self._verify_installation()

        # Create SSH key directory
        ssh_key_dir = Path(settings.SSH_KEY_DIR)
        ssh_key_dir.mkdir(parents=True, exist_ok=True)

        # Sync resource tracker with actual multipass state
        logger.info("🔄 Syncing resource tracker with multipass state...")
        vm_resources = self._get_all_vms_resources()
        await self.resource_tracker.sync_with_multipass(vm_resources)
        logger.info("✨ Resource tracker synced with multipass state")

    def _run_multipass(self, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run a multipass command.

        Args:
            args: Command arguments
            check: Whether to check return code

        Returns:
            CompletedProcess instance
        """
        try:
            return subprocess.run(
                [self.multipass_path, *args],
                capture_output=True,
                text=True,
                check=check
            )
        except subprocess.CalledProcessError as e:
            raise MultipassError(f"Multipass command failed: {e.stderr}")

    def _get_vm_info(self, vm_id: str) -> Dict:
        """Get detailed information about a VM.

        Args:
            vm_id: VM identifier

        Returns:
            Dictionary with VM information
        """
        result = self._run_multipass(["info", vm_id, "--format", "json"])
        try:
            info = json.loads(result.stdout)
            return info["info"][vm_id]
        except (json.JSONDecodeError, KeyError) as e:
            raise MultipassError(f"Failed to parse VM info: {e}")

    def _get_vm_ip(self, vm_id: str) -> Optional[str]:
        """Get IP address of a VM.

        Args:
            vm_id: VM identifier

        Returns:
            IP address or None if not found
        """
        try:
            info = self._get_vm_info(vm_id)
            return info.get("ipv4", [None])[0]
        except Exception:
            return None

    async def create_vm(self, config: VMConfig) -> VMInfo:
        """Create a new VM.

        Args:
            config: VM configuration

        Returns:
            Information about the created VM
        """
        multipass_name = f"golem-{config.name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        await self.name_mapper.add_mapping(config.name, multipass_name)

        # Verify resources are properly allocated
        if not self.resource_tracker.can_accept_resources(config.resources):
            raise VMCreateError("Resources not properly allocated or insufficient")

        # Generate cloud-init config with requestor's public key
        cloud_init_path = generate_cloud_init(
            hostname=config.name,
            ssh_key=config.ssh_key
        )

        try:
            # Launch VM
            logger.process(f"🚀 Launching VM {multipass_name}")
            launch_cmd = [
                "launch",
                config.image,
                "--name", multipass_name,
                "--cloud-init", cloud_init_path,
                "--cpus", str(config.resources.cpu),
                "--memory", f"{config.resources.memory}G",
                "--disk", f"{config.resources.storage}G"
            ]
            self._run_multipass(launch_cmd)

            # Get VM IP
            ip_address = self._get_vm_ip(multipass_name)
            if not ip_address:
                raise MultipassError("Failed to get VM IP address")

            # Allocate port and configure proxy
            try:
                # First allocate a verified port
                ssh_port = self.port_manager.allocate_port(multipass_name)
                if not ssh_port:
                    raise MultipassError("Failed to allocate verified SSH port")

                # Then configure proxy with allocated port
                success = await self.proxy_manager.add_vm(multipass_name, ip_address, port=ssh_port)
                if not success:
                    # Clean up allocated port if proxy fails
                    self.port_manager.deallocate_port(multipass_name)
                    raise MultipassError("Failed to configure proxy")

                # Create VM info and register with resource tracker
                vm_info = VMInfo(
                    id=config.name,  # Use requestor name as VM ID
                    name=config.name,
                    status=VMStatus.RUNNING,
                    resources=config.resources,
                    ip_address=ip_address,
                    ssh_port=ssh_port
                )

                # Update resource tracker with VM ID
                await self.resource_tracker.allocate(config.resources, config.name)

                return vm_info

            except Exception as e:
                # If proxy configuration fails, ensure we cleanup the VM and resources
                self._run_multipass(["delete", multipass_name, "--purge"], check=False)
                await self.resource_tracker.deallocate(config.resources, config.name)
                await self.name_mapper.remove_mapping(config.name)
                raise VMCreateError(
                    f"Failed to configure VM networking: {str(e)}", vm_id=config.name)

        except Exception as e:
            # Cleanup on failure (this catches VM creation errors)
            try:
                await self.delete_vm(config.name)
            except Exception as cleanup_error:
                logger.error(f"Error during VM cleanup: {cleanup_error}")
            # Ensure resources are deallocated even if delete_vm fails
            await self.resource_tracker.deallocate(config.resources, config.name)
            raise VMCreateError(f"Failed to create VM: {str(e)}", vm_id=config.name)

        finally:
            # Cleanup cloud-init file
            cleanup_cloud_init(cloud_init_path)

    def _verify_vm_exists(self, vm_id: str) -> bool:
        """Check if VM exists in multipass.
        
        Args:
            vm_id: VM identifier
            
        Returns:
            True if VM exists, False otherwise
        """
        try:
            result = self._run_multipass(["list", "--format", "json"])
            data = json.loads(result.stdout)
            vms = data.get("list", [])
            return any(vm.get("name") == vm_id for vm in vms)
        except Exception:
            return False

    async def delete_vm(self, requestor_name: str) -> None:
        """Delete a VM.

        Args:
            requestor_name: Requestor's VM name
        """
        # Get multipass name from mapper
        multipass_name = await self.name_mapper.get_multipass_name(requestor_name)
        if not multipass_name:
            logger.warning(f"No multipass name found for VM {requestor_name}")
            return

        logger.process(f"🗑️  Initiating deletion of VM {multipass_name}")
        
        # Get VM info for resource deallocation
        try:
            vm_info = await self.get_vm_status(requestor_name)
        except Exception as e:
            logger.error(f"Failed to get VM info for cleanup: {e}")
            vm_info = None

        # Check if VM exists
        if not self._verify_vm_exists(multipass_name):
            logger.warning(f"VM {multipass_name} not found in multipass")
        else:
            try:
                # First mark for deletion
                logger.info("🔄 Marking VM for deletion...")
                self._run_multipass(["delete", multipass_name], check=False)
                
                # Then purge
                logger.info("🔄 Purging deleted VM...")
                self._run_multipass(["purge"], check=False)
                
                # Verify deletion
                if self._verify_vm_exists(multipass_name):
                    logger.error(f"VM {multipass_name} still exists after deletion attempt")
                    # Try one more time with force
                    logger.info("🔄 Attempting forced deletion...")
                    self._run_multipass(["stop", "--all", multipass_name], check=False)
                    self._run_multipass(["delete", "--purge", multipass_name], check=False)
                    if self._verify_vm_exists(multipass_name):
                        raise MultipassError(f"Failed to delete VM {multipass_name}")
                
                logger.success("✨ VM instance removed")
            except Exception as e:
                logger.error(f"Error deleting VM {multipass_name} from multipass: {e}")
                raise

        # Clean up proxy config and port allocation
        try:
            logger.info("🔄 Cleaning up network configuration...")
            await self.proxy_manager.remove_vm(multipass_name)
            self.port_manager.deallocate_port(multipass_name)
            logger.success("✨ Network configuration cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up network configuration for VM {multipass_name}: {e}")
            
        # Deallocate resources
        if vm_info and vm_info.resources:
            try:
                logger.info("🔄 Deallocating resources...")
                await self.resource_tracker.deallocate(vm_info.resources, requestor_name)
                logger.success("✨ Resources deallocated")
            except Exception as e:
                logger.error(f"Error deallocating resources: {e}")

        # Remove name mapping
        try:
            await self.name_mapper.remove_mapping(requestor_name)
            logger.success("✨ Name mapping removed")
        except Exception as e:
            logger.error(f"Error removing name mapping: {e}")

        # Sync resource tracker with actual state
        logger.info("🔄 Syncing resource tracker with multipass state...")
        vm_resources = self._get_all_vms_resources()
        await self.resource_tracker.sync_with_multipass(vm_resources)
        logger.info("✨ Resource tracker synced with multipass state")

    async def start_vm(self, requestor_name: str) -> VMInfo:
        """Start a VM.

        Args:
            requestor_name: Requestor's VM name

        Returns:
            Updated VM information
        """
        # Get multipass name from mapper
        multipass_name = await self.name_mapper.get_multipass_name(requestor_name)
        if not multipass_name:
            raise VMNotFoundError(f"VM {requestor_name} not found")

        logger.process(f"🔄 Starting VM '{requestor_name}'")
        self._run_multipass(["start", multipass_name])
        status = await self.get_vm_status(requestor_name)
        logger.success(f"✨ VM '{requestor_name}' started successfully")
        return status

    async def stop_vm(self, requestor_name: str) -> VMInfo:
        """Stop a VM.

        Args:
            requestor_name: Requestor's VM name

        Returns:
            Updated VM information
        """
        # Get multipass name from mapper
        multipass_name = await self.name_mapper.get_multipass_name(requestor_name)
        if not multipass_name:
            raise VMNotFoundError(f"VM {requestor_name} not found")

        logger.process(f"🔄 Stopping VM '{requestor_name}'")
        self._run_multipass(["stop", multipass_name])
        status = await self.get_vm_status(requestor_name)
        logger.success(f"✨ VM '{requestor_name}' stopped successfully")
        return status

    async def get_vm_status(self, requestor_name: str) -> VMInfo:
        """Get current status of a VM.

        Args:
            requestor_name: Requestor's VM name

        Returns:
            VM status information
        """
        try:
            # Get multipass name from mapper
            multipass_name = await self.name_mapper.get_multipass_name(requestor_name)
            if not multipass_name:
                raise VMNotFoundError(f"VM {requestor_name} not found")

            # Get VM info from multipass
            info = self._get_vm_info(multipass_name)

            return VMInfo(
                id=requestor_name,  # Use requestor name as ID
                name=requestor_name,
                status=VMStatus(info.get("state", "unknown").lower()),
                resources=VMResources(
                    cpu=int(info.get("cpu_count", 1)),
                    memory=int(info.get("memory_total", 1024) / 1024),
                    storage=int(info.get("disk_total", 10 * 1024) / 1024)
                ),
                ip_address=info.get("ipv4", [None])[0],
                ssh_port=self.proxy_manager.get_port(multipass_name)
            )
        except Exception as e:
            logger.error(f"Error getting VM status: {e}")
            return VMInfo(
                id=requestor_name,
                name=requestor_name,
                status=VMStatus.ERROR,
                resources=VMResources(cpu=1, memory=1, storage=10),
                error_message=str(e)
            )

    async def add_ssh_key(self, vm_id: str, key: str) -> None:
        """Add SSH key to VM.

        Args:
            vm_id: VM identifier
            key: SSH key to add
        """
        # Not implemented - we use cloud-init for SSH key setup
        pass
