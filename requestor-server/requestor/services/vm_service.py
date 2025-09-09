"""VM management service."""
from typing import Dict, List, Optional
from datetime import datetime

from ..provider.client import ProviderClient
from ..errors import RequestorError, VMError
from .database_service import DatabaseService
from .ssh_service import SSHService

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
            # Check if VM name already exists
            existing_vm = await self.db.get_vm(name)
            if existing_vm:
                raise VMError(f"VM with name '{name}' already exists")

            # Create VM on provider
            vm = await self.provider_client.create_vm(
                name=name,
                cpu=cpu,
                memory=memory,
                storage=storage,
                ssh_key=ssh_key,
                stream_id=stream_id
            )

            # Get VM access info
            access_info = await self.provider_client.get_vm_access(vm['id'])

            # Preserve any provided stream_id; do not auto-create streams here
            # Stream creation should be explicit via CLI `vm stream open` command.

            # Save VM details to database
            config = {
                'cpu': cpu,
                'memory': memory,
                'storage': storage,
                'ssh_port': access_info['ssh_port'],
                **({"stream_id": stream_id} if stream_id is not None else {}),
            }
            await self.db.save_vm(
                name=name,
                provider_ip=provider_ip,
                vm_id=access_info['vm_id'],
                config=config
            )

            return {
                'name': name,
                'provider_ip': provider_ip,
                'vm_id': access_info['vm_id'],
                'config': config,
                'status': 'running'
            }

        except Exception as e:
            raise VMError(f"Failed to create VM: {str(e)}")

    async def destroy_vm(self, name: str) -> None:
        """Destroy a VM and clean up resources."""
        try:
            # Get VM details
            vm = await self.db.get_vm(name)
            if not vm:
                raise VMError(f"VM '{name}' not found")

            try:
                # Destroy VM on provider
                await self.provider_client.destroy_vm(vm['vm_id'])
            except Exception as e:
                if "Not Found" not in str(e):
                    raise

            # Attempt to terminate stream if present
            try:
                stream_id = vm.get('config', {}).get('stream_id')
                if stream_id is not None and self.blockchain_client:
                    self.blockchain_client.terminate(stream_id)
            except Exception:
                # Best-effort: do not block deletion on chain failure
                pass

            # Remove from database
            await self.db.delete_vm(name)

        except Exception as e:
            raise VMError(f"Failed to destroy VM: {str(e)}")

    async def start_vm(self, name: str) -> None:
        """Start a stopped VM."""
        try:
            # Get VM details
            vm = await self.db.get_vm(name)
            if not vm:
                raise VMError(f"VM '{name}' not found")

            # Start VM on provider
            await self.provider_client.start_vm(vm['vm_id'])
            
            # Update status in database
            await self.db.update_vm_status(name, "running")

        except Exception as e:
            raise VMError(f"Failed to start VM: {str(e)}")

    async def stop_vm(self, name: str) -> None:
        """Stop a running VM."""
        try:
            # Get VM details
            vm = await self.db.get_vm(name)
            if not vm:
                raise VMError(f"VM '{name}' not found")

            # Stop VM on provider
            await self.provider_client.stop_vm(vm['vm_id'])
            
            # Update status in database
            await self.db.update_vm_status(name, "stopped")

            # Best-effort terminate stream on stop (treat stop as end of agreement)
            try:
                stream_id = vm.get('config', {}).get('stream_id')
                if stream_id is not None and self.blockchain_client:
                    self.blockchain_client.terminate(stream_id)
            except Exception:
                pass

        except Exception as e:
            raise VMError(f"Failed to stop VM: {str(e)}")

    async def list_vms(self) -> List[Dict]:
        """List all VMs with their current status."""
        try:
            return await self.db.list_vms()
        except Exception as e:
            raise VMError(f"Failed to list VMs: {str(e)}")

    async def get_vm(self, name: str) -> Optional[Dict]:
        """Get VM details by name."""
        try:
            vm = await self.db.get_vm(name)
            if not vm:
                return None
            return vm
        except Exception as e:
            raise VMError(f"Failed to get VM details: {str(e)}")

    def format_vm_row(self, vm: Dict, colorize: bool = False) -> List:
        """Format VM information for display."""
        from click import style

        key_pair = self.ssh_service.get_key_pair_sync()
        connect_command = self.ssh_service.format_ssh_command(
            host=vm['provider_ip'],
            port=vm['config'].get('ssh_port', 'N/A'),
            private_key_path=key_pair.private_key.absolute()
        )

        row = [
            vm['name'],
            vm['status'],
            vm['provider_ip'],
            vm['config'].get('ssh_port', 'N/A'),
            vm['config']['cpu'],
            vm['config']['memory'],
            vm['config']['storage'],
            connect_command,
            vm['created_at']
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
            "Created"
        ]

    async def get_vm_stats(self, name: str) -> Dict:
        """Get VM stats by name."""
        try:
            vm = await self.db.get_vm(name)
            if not vm:
                raise VMError(f"VM '{name}' not found")

            key_pair = await self.ssh_service.get_key_pair()

            return self.ssh_service.get_vm_stats(
                host=vm['provider_ip'],
                port=vm['config']['ssh_port'],
                private_key_path=key_pair.private_key
            )
        except Exception as e:
            raise VMError(f"Failed to get VM stats: {str(e)}")
