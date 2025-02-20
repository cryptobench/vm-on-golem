from typing import List
from pathlib import Path
from fastapi import APIRouter, HTTPException

from ..config import settings
from ..utils.logging import setup_logger, PROCESS, SUCCESS
from ..utils.ascii_art import vm_creation_animation, vm_status_change
from ..vm.models import VMCreateRequest, VMInfo, VMStatus, VMAccessInfo, VMConfig, VMResources
from ..vm.multipass import MultipassProvider, MultipassError
from ..discovery.resource_tracker import ResourceTracker

logger = setup_logger(__name__)
router = APIRouter()

# Initialize resource tracker and VM provider
resource_tracker = ResourceTracker()
provider = MultipassProvider(resource_tracker)

@router.post("/vms", response_model=VMInfo)
async def create_vm(request: VMCreateRequest) -> VMInfo:
    """Create a new VM."""
    try:
        logger.info(f"📥 Received VM creation request for '{request.name}'")
        
        # Determine resources based on size or explicit values
        if request.size:
            logger.process(f"🔄 Using predefined size: {request.size}")
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
            
            logger.process(f"🔄 Using custom resources: {cpu} CPU, {memory}GB RAM, {storage}GB storage")
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
        
        # Show VM creation animation
        await vm_creation_animation(request.name)
        
        # Create VM
        logger.process(f"🔄 Creating VM with config: {config}")
        vm_info = await provider.create_vm(config)
        
        # Show status change
        vm_status_change(vm_info.id, "RUNNING", f"SSH port: {vm_info.ssh_port}")
        logger.success(f"✨ Successfully created VM '{vm_info.name}' (ID: {vm_info.id})")
        return vm_info
        
    except MultipassError as e:
        logger.error(f"Failed to create VM: {e}")
        raise HTTPException(500, str(e))

@router.get("/vms", response_model=List[VMInfo])
async def list_vms() -> List[VMInfo]:
    """List all VMs."""
    try:
        logger.info("📋 Listing all VMs")
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
        logger.info(f"🔍 Getting status for VM {vm_id}")
        status = await provider.get_vm_status(vm_id)
        vm_status_change(vm_id, status.status.value)
        return status
    except MultipassError as e:
        logger.error(f"Failed to get VM status: {e}")
        raise HTTPException(500, str(e))

@router.get("/vms/{vm_id}/access", response_model=VMAccessInfo)
async def get_vm_access(vm_id: str) -> VMAccessInfo:
    """Get VM access information."""
    try:
        logger.process(f"📤 Preparing access credentials for requestor - VM {vm_id}")
        # Get VM info
        vm = await provider.get_vm_status(vm_id)
        if not vm:
            raise HTTPException(404, "VM not found")
        
        # Return access info
        access_info = VMAccessInfo(
            ssh_host=settings.PUBLIC_IP or "localhost",
            ssh_port=vm.ssh_port or 22
        )
        logger.success(f"✨ Access credentials sent to requestor - VM {vm_id}")
        return access_info
        
    except MultipassError as e:
        logger.error(f"Failed to get VM access info: {e}")
        raise HTTPException(500, str(e))

@router.delete("/vms/{vm_id}")
async def delete_vm(vm_id: str) -> None:
    """Delete a VM."""
    try:
        logger.process(f"🗑️  Deleting VM {vm_id}")
        vm_status_change(vm_id, "STOPPING", "Cleanup in progress")
        await provider.delete_vm(vm_id)
        vm_status_change(vm_id, "TERMINATED", "Cleanup complete")
        logger.success(f"✨ Successfully deleted VM {vm_id}")
    except MultipassError as e:
        logger.error(f"Failed to delete VM: {e}")
        raise HTTPException(500, str(e))
