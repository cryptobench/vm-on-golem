import logging
from typing import List
from pathlib import Path
from fastapi import APIRouter, HTTPException

from ..config import settings
from ..vm.models import VMCreateRequest, VMInfo, VMStatus, VMAccessInfo, VMConfig, VMResources
from ..vm.multipass import MultipassProvider, MultipassError
from ..discovery.resource_tracker import ResourceTracker

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize resource tracker and VM provider
resource_tracker = ResourceTracker()
provider = MultipassProvider(resource_tracker)

@router.post("/vms", response_model=VMInfo)
async def create_vm(request: VMCreateRequest) -> VMInfo:
    """Create a new VM."""
    try:
        # Determine resources based on size or explicit values
        if request.size:
            resources = VMResources.from_size(request.size)
        else:
            # Use explicit values or defaults
            cpu = request.cpu_cores or settings.MIN_CPU_CORES
            memory = request.memory_gb or settings.MIN_MEMORY_GB
            storage = request.storage_gb or settings.MIN_STORAGE_GB
            
            # Validate resource requirements
            if cpu < settings.MIN_CPU_CORES:
                raise HTTPException(400, f"Minimum CPU cores required: {settings.MIN_CPU_CORES}")
            if memory < settings.MIN_MEMORY_GB:
                raise HTTPException(400, f"Minimum memory required: {settings.MIN_MEMORY_GB}GB")
            if storage < settings.MIN_STORAGE_GB:
                raise HTTPException(400, f"Minimum storage required: {settings.MIN_STORAGE_GB}GB")
            
            resources = VMResources(
                cpu=cpu,
                memory=memory,
                storage=storage
            )
        
        # Create VM config
        config = VMConfig(
            name=request.name,
            image=request.image or settings.DEFAULT_VM_IMAGE,
            resources=resources,
            ssh_key=request.ssh_key
        )
        
        # Create VM
        vm_info = await provider.create_vm(config)
        return vm_info
        
    except MultipassError as e:
        logger.error(f"Failed to create VM: {e}")
        raise HTTPException(500, str(e))

@router.get("/vms", response_model=List[VMInfo])
async def list_vms() -> List[VMInfo]:
    """List all VMs."""
    try:
        vms = []
        for vm_id in resource_tracker.get_allocated_vms():
            vm_info = await provider.get_vm_status(vm_id)
            vms.append(vm_info)
        return vms
    except MultipassError as e:
        logger.error(f"Failed to list VMs: {e}")
        raise HTTPException(500, str(e))

@router.get("/vms/{vm_id}", response_model=VMInfo)
async def get_vm_status(vm_id: str) -> VMInfo:
    """Get VM status."""
    try:
        return await provider.get_vm_status(vm_id)
    except MultipassError as e:
        logger.error(f"Failed to get VM status: {e}")
        raise HTTPException(500, str(e))

@router.get("/vms/{vm_id}/access", response_model=VMAccessInfo)
async def get_vm_access(vm_id: str) -> VMAccessInfo:
    """Get VM access information."""
    try:
        # Get VM info
        vm = await provider.get_vm_status(vm_id)
        if not vm:
            raise HTTPException(404, "VM not found")
        
        # Return access info
        return VMAccessInfo(
            ssh_host=settings.PUBLIC_IP or "localhost",
            ssh_port=vm.ssh_port or 22
        )
        
    except MultipassError as e:
        logger.error(f"Failed to get VM access info: {e}")
        raise HTTPException(500, str(e))

@router.delete("/vms/{vm_id}")
async def delete_vm(vm_id: str) -> None:
    """Delete a VM."""
    try:
        await provider.delete_vm(vm_id)
    except MultipassError as e:
        logger.error(f"Failed to delete VM: {e}")
        raise HTTPException(500, str(e))
