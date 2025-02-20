# Provider Node Implementation Guide

## Overview

The Provider Node is responsible for:

1. Managing VM lifecycle using Multipass
2. Advertising available resources to the discovery service
3. Exposing a REST API for VM operations
4. Handling secure SSH key provisioning
5. Monitoring and enforcing resource thresholds

## Implementation Details

### 1. VM Management Layer

```python
# provider/vm/multipass.py
from typing import Dict, Optional
from .models import VMConfig, VMInfo, VMStatus, VMError

class MultipassProvider:
    def __init__(self, multipass_path: Optional[str] = None):
        self.multipass_path = multipass_path
        self.vms: Dict[str, VMInfo] = {}

    async def initialize(self) -> None:
        """Initialize provider and load existing VMs."""
        # Verify multipass installation
        # Load existing VMs from multipass
        pass

    async def create_vm(self, config: VMConfig) -> VMInfo:
        """Create a new VM using Multipass."""
        vm_id = str(uuid.uuid4())
        try:
            # Create cloud-init config for SSH key
            cloud_init = CloudInitManager.create_config(config.ssh_key)

            # Launch VM
            await self._run_command(
                "launch",
                "--name", config.name,
                "--cpus", str(config.resources.cpu),
                "--memory", f"{config.resources.memory}GB",
                "--disk", f"{config.resources.storage}GB",
                "--cloud-init", str(cloud_init),
                config.image
            )

            # Get VM IP and update info
            ip_address = await self._get_vm_ip(config.name)
            return VMInfo(
                id=vm_id,
                name=config.name,
                status=VMStatus.RUNNING,
                ip_address=ip_address,
                ssh_port=22,
                resources=config.resources
            )
        except Exception as e:
            raise VMError(str(e), vm_id=vm_id)

    async def delete_vm(self, vm_id: str) -> None:
        """Delete a VM."""
        vm_info = self.vms.get(vm_id)
        if not vm_info:
            raise VMNotFoundError(f"VM {vm_id} not found")
        await self._run_command("delete", vm_info.name)

    async def start_vm(self, vm_id: str) -> VMInfo:
        """Start a VM."""
        vm_info = self.vms.get(vm_id)
        if not vm_info:
            raise VMNotFoundError(f"VM {vm_id} not found")
        await self._run_command("start", vm_info.name)
        return await self.get_vm_status(vm_id)

    async def stop_vm(self, vm_id: str) -> VMInfo:
        """Stop a VM."""
        vm_info = self.vms.get(vm_id)
        if not vm_info:
            raise VMNotFoundError(f"VM {vm_id} not found")
        await self._run_command("stop", vm_info.name)
        return await self.get_vm_status(vm_id)
```

### 2. Resource Management and Advertisement

```python
# provider/discovery/advertiser.py
class ResourceMonitor:
    """Monitor system resources."""

    @staticmethod
    def get_available_resources() -> Dict[str, int]:
        """Get available system resources."""
        return {
            "cpu": psutil.cpu_count(),
            "memory": psutil.virtual_memory().available // (1024**3),
            "storage": psutil.disk_usage("/").free // (1024**3)
        }

    @classmethod
    def can_accept_resources(cls, cpu: int, memory: int, storage: int) -> bool:
        """Check if system can accept requested resources."""
        # Check against thresholds
        if cls.get_cpu_percent() > settings.CPU_THRESHOLD:
            return False
        if cls.get_memory_percent() > settings.MEMORY_THRESHOLD:
            return False
        if cls.get_storage_percent() > settings.STORAGE_THRESHOLD:
            return False

        # Check absolute values
        resources = cls.get_available_resources()
        return (
            cpu <= resources["cpu"] and
            memory <= resources["memory"] and
            storage <= resources["storage"]
        )

class ResourceAdvertiser:
    """Advertise available resources to discovery service."""

    def __init__(
        self,
        discovery_url: Optional[str] = None,
        provider_id: Optional[str] = None,
        update_interval: Optional[int] = None
    ):
        self.discovery_url = discovery_url or settings.DISCOVERY_URL
        self.provider_id = provider_id or settings.PROVIDER_ID
        self.update_interval = update_interval or settings.ADVERTISEMENT_INTERVAL
        self.monitor = ResourceMonitor()

    async def start(self):
        """Start advertising resources."""
        self.session = aiohttp.ClientSession()
        while not self._stop_event.is_set():
            try:
                await self._post_advertisement()
            except Exception as e:
                logger.error(f"Failed to post advertisement: {e}")
                await asyncio.sleep(min(60, self.update_interval))
            else:
                await asyncio.sleep(self.update_interval)

    async def _post_advertisement(self):
        """Post resource advertisement to discovery service."""
        # Skip if resources too low
        if not self.monitor.can_accept_resources(
            cpu=settings.MIN_CPU_CORES,
            memory=settings.MIN_MEMORY_GB,
            storage=settings.MIN_STORAGE_GB
        ):
            logger.warning("Resources too low, skipping advertisement")
            return

        resources = self.monitor.get_available_resources()
        async with self.session.post(
            f"{self.discovery_url}/api/v1/advertisements",
            headers={"X-Provider-ID": self.provider_id},
            json={
                "ip_address": await self._get_public_ip(),
                "country": settings.COUNTRY,
                "resources": resources
            }
        ) as response:
            if not response.ok:
                raise Exception(f"Failed to post advertisement: {response.status}")
```

### 3. REST API

```python
# provider/api/routes.py
@router.post("/vms", response_model=VMResponse)
async def create_vm(
    request: CreateVMRequest,
    provider: VMProvider = Depends(get_vm_provider)
):
    """Create a new VM."""
    # Check resource availability
    if not ResourceMonitor.can_accept_resources(
        cpu=request.resources.cpu,
        memory=request.resources.memory,
        storage=request.resources.storage
    ):
        raise HTTPException(
            status_code=503,
            detail={"code": "RESOURCE_UNAVAILABLE"}
        )

    try:
        vm_info = await provider.create_vm(request)
        return VMResponse(**vm_info.dict())
    except VMError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "VM_CREATE_ERROR", "message": str(e)}
        )

@router.get("/vms/{vm_id}", response_model=VMResponse)
async def get_vm(vm_id: str, provider: VMProvider = Depends(get_vm_provider)):
    """Get VM status."""
    try:
        vm_info = await provider.get_vm_status(vm_id)
        return VMResponse(**vm_info.dict())
    except VMNotFoundError:
        raise HTTPException(status_code=404)

@router.post("/vms/{vm_id}/start", response_model=VMResponse)
async def start_vm(vm_id: str, provider: VMProvider = Depends(get_vm_provider)):
    """Start a VM."""
    try:
        vm_info = await provider.start_vm(vm_id)
        return VMResponse(**vm_info.dict())
    except VMError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/vms/{vm_id}/stop", response_model=VMResponse)
async def stop_vm(vm_id: str, provider: VMProvider = Depends(get_vm_provider)):
    """Stop a VM."""
    try:
        vm_info = await provider.stop_vm(vm_id)
        return VMResponse(**vm_info.dict())
    except VMError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### 4. Configuration

```python
# provider/config.py
class Settings(BaseSettings):
    # Provider Settings
    PROVIDER_ID: str
    PROVIDER_NAME: str = "golem-provider"
    COUNTRY: str = "SE"

    # Discovery Settings
    DISCOVERY_URL: str = "http://discovery.golem.network:7465"
    ADVERTISEMENT_INTERVAL: int = 240  # 4 minutes

    # VM Settings
    MAX_VMS: int = 10
    DEFAULT_VM_IMAGE: str = "ubuntu:24.04"
    VM_DATA_DIR: DirectoryPath

    # Resource Settings
    MIN_MEMORY_GB: int = 1
    MIN_STORAGE_GB: int = 10
    MIN_CPU_CORES: int = 1

    # Resource Thresholds
    CPU_THRESHOLD: int = 90
    MEMORY_THRESHOLD: int = 85
    STORAGE_THRESHOLD: int = 90

    class Config:
        env_prefix = "GOLEM_PROVIDER_"
```

## Security Considerations

1. **Resource Protection**

    - CPU, memory, and storage thresholds prevent overallocation
    - Rate limiting protects API endpoints
    - Resource validation before VM creation

2. **VM Isolation**

    - VMs are isolated using Multipass
    - Each VM gets its own SSH key pair
    - Proper directory permissions (700) for SSH keys

3. **Error Handling**
    - Detailed error types for different failure scenarios
    - Proper cleanup on failures
    - Logging of all critical operations

## Usage Example

1. Start the provider node:

```bash
export GOLEM_PROVIDER_ID="provider123"
export GOLEM_PROVIDER_DISCOVERY_URL="http://localhost:7465"
python -m provider.main
```

2. The provider will:
    - Initialize Multipass and load existing VMs
    - Start advertising resources every 4 minutes
    - Handle VM lifecycle operations via REST API
    - Monitor and enforce resource thresholds

## Error Types

```python
class VMError(Exception):
    """Base class for VM errors."""
    def __init__(self, message: str, vm_id: Optional[str] = None):
        self.message = message
        self.vm_id = vm_id
        super().__init__(message)

class VMNotFoundError(VMError):
    """VM not found error."""
    pass

class VMStateError(VMError):
    """Invalid VM state transition error."""
    pass
```

This implementation provides a robust provider node with:

-   Comprehensive resource monitoring and protection
-   Proper VM lifecycle management
-   Secure SSH key handling
-   Detailed error handling
-   Clean configuration management
