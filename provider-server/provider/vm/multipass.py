import os
import json
import subprocess
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

from ..config import settings
from ..utils.logging import setup_logger, PROCESS, SUCCESS
from .models import VMInfo, VMStatus, VMCreateRequest, VMConfig, VMProvider, VMError, VMCreateError, VMResources
from .cloud_init import generate_cloud_init, cleanup_cloud_init
from .proxy_manager import PythonProxyManager

logger = setup_logger(__name__)


class MultipassError(VMError):
    """Raised when multipass operations fail."""
    pass


class MultipassProvider(VMProvider):
    """Manages VMs using Multipass."""

    def __init__(self, resource_tracker: "ResourceTracker"):
        """Initialize the multipass provider.

        Args:
            resource_tracker: Resource tracker instance
        """
        self.resource_tracker = resource_tracker
        self.multipass_path = settings.MULTIPASS_BINARY_PATH
        self.vm_data_dir = Path(settings.VM_DATA_DIR)
        self.vm_data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize proxy manager
        self.proxy_manager = PythonProxyManager()

    async def initialize(self) -> None:
        """Initialize the provider."""
        self._verify_installation()

        # Create SSH key directory
        ssh_key_dir = Path(settings.SSH_KEY_DIR)
        ssh_key_dir.mkdir(parents=True, exist_ok=True)

    async def cleanup(self) -> None:
        """Clean up all VMs and configurations."""
        try:
            # Get list of Golem VMs
            result = self._run_multipass(["list", "--format", "json"])
            data = json.loads(result.stdout)

            for vm in data.get("list", []):
                vm_id = vm.get("name")
                if vm_id and vm_id.startswith("golem-"):
                    await self.delete_vm(vm_id)

            # Clean up proxy configs
            await self.proxy_manager.cleanup()

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

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
        vm_id = f"golem-{config.name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        # Generate cloud-init config with requestor's public key
        cloud_init_path = generate_cloud_init(
            hostname=config.name,
            ssh_key=config.ssh_key
        )

        try:
            logger.process(f"🚀 Launching VM {vm_id}")
            logger.info(f"📦 Image: {config.image}")
            logger.info(f"💻 Resources: {config.resources.cpu} CPU, {config.resources.memory}GB RAM, {config.resources.storage}GB storage")
            
            # Launch VM
            launch_cmd = [
                "launch",
                config.image,
                "--name", vm_id,
                "--cloud-init", cloud_init_path,
                "--cpus", str(config.resources.cpu),
                "--memory", f"{config.resources.memory}G",
                "--disk", f"{config.resources.storage}G"
            ]
            logger.process("⚙️  Executing multipass launch command...")
            self._run_multipass(launch_cmd)
            logger.success("✨ VM instance launched successfully")

            # Get VM IP
            logger.process("🔍 Getting VM IP address...")
            ip_address = self._get_vm_ip(vm_id)
            if not ip_address:
                raise MultipassError("Failed to get VM IP address")
            logger.success(f"✨ VM IP address acquired: {ip_address}")

            # Configure proxy
            try:
                logger.process("🔄 Configuring network proxy...")
                ssh_port = await self.proxy_manager.add_vm(vm_id, ip_address)
                if not ssh_port:
                    raise MultipassError("Failed to configure proxy")
                logger.success(f"✨ Network proxy configured - SSH port: {ssh_port}")

                # Create VM info
                vm_info = VMInfo(
                    id=vm_id,
                    name=config.name,
                    status=VMStatus.RUNNING,
                    resources=config.resources,
                    ip_address=ip_address,
                    ssh_port=ssh_port
                )

                return vm_info

            except Exception as e:
                # If proxy configuration fails, ensure we cleanup the VM
                self._run_multipass(["delete", vm_id, "--purge"], check=False)
                raise VMCreateError(
                    f"Failed to configure VM networking: {str(e)}", vm_id=vm_id)

        except Exception as e:
            # Cleanup on failure (this catches VM creation errors)
            try:
                await self.delete_vm(vm_id)
            except Exception as cleanup_error:
                logger.error(f"Error during VM cleanup: {cleanup_error}")
            raise VMCreateError(f"Failed to create VM: {str(e)}", vm_id=vm_id)

        finally:
            # Cleanup cloud-init file
            cleanup_cloud_init(cloud_init_path)

    async def delete_vm(self, vm_id: str) -> None:
        """Delete a VM.

        Args:
            vm_id: VM identifier
        """
        logger.process(f"🗑️  Initiating deletion of VM {vm_id}")
        # First try to delete the VM itself
        try:
            logger.info("🔄 Removing VM instance...")
            self._run_multipass(["delete", vm_id, "--purge"], check=False)
            logger.success("✨ VM instance removed")
        except Exception as e:
            logger.error(f"Error deleting VM {vm_id} from multipass: {e}")

        # Then try to cleanup proxy config (even if VM deletion failed)
        try:
            logger.info("🔄 Cleaning up network proxy configuration...")
            await self.proxy_manager.remove_vm(vm_id)
            logger.success("✨ Network proxy configuration cleaned up")
        except Exception as e:
            logger.error(f"Error removing proxy config for VM {vm_id}: {e}")

    async def start_vm(self, vm_id: str) -> VMInfo:
        """Start a VM.

        Args:
            vm_id: VM identifier

        Returns:
            Updated VM information
        """
        logger.process(f"🔄 Starting VM {vm_id}")
        self._run_multipass(["start", vm_id])
        status = await self.get_vm_status(vm_id)
        logger.success(f"✨ VM {vm_id} started successfully")
        return status

    async def stop_vm(self, vm_id: str) -> VMInfo:
        """Stop a VM.

        Args:
            vm_id: VM identifier

        Returns:
            Updated VM information
        """
        logger.process(f"🔄 Stopping VM {vm_id}")
        self._run_multipass(["stop", vm_id])
        status = await self.get_vm_status(vm_id)
        logger.success(f"✨ VM {vm_id} stopped successfully")
        return status

    async def get_vm_status(self, vm_id: str) -> VMInfo:
        """Get current status of a VM.

        Args:
            vm_id: VM identifier

        Returns:
            VM status information
        """
        try:
            info = self._get_vm_info(vm_id)

            # Extract name from VM ID
            name = vm_id.split("-")[1]

            return VMInfo(
                id=vm_id,
                name=name,
                status=VMStatus(info.get("state", "unknown").lower()),
                resources=VMResources(
                    cpu=int(info.get("cpu_count", 1)),
                    memory=int(info.get("memory_total", 1024) / 1024),
                    storage=int(info.get("disk_total", 10 * 1024) / 1024)
                ),
                ip_address=info.get("ipv4", [None])[0],
                ssh_port=self.proxy_manager.get_port(vm_id)
            )
        except Exception as e:
            logger.error(f"Error getting VM status: {e}")
            return VMInfo(
                id=vm_id,
                name=vm_id,
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
