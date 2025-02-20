from typing import List
from pathlib import Path
from fastapi import APIRouter, HTTPException

from ..config import settings
from ..utils.logging import setup_logger, PROCESS, SUCCESS
from ..utils.ascii_art import vm_creation_animation, vm_status_change
from ..vm.models import VMInfo, VMStatus, VMAccessInfo, VMConfig, VMResources
from .models import CreateVMRequest
from ..vm.multipass import MultipassProvider, MultipassError
from ..discovery.resource_tracker import ResourceTracker

logger = setup_logger(__name__)
router = APIRouter()

# Initialize resource tracker and VM provider
resource_tracker = ResourceTracker()
provider = MultipassProvider(resource_tracker)

@router.post("/vms", response_model=VMInfo)
async def create_vm(request: CreateVMRequest) -> VMInfo:
    """Create a new VM."""
    try:
        logger.info(f"📥 Received VM creation request for '{request.name}'")
        
        # Determine resources based on request
        resources = request.resources
        if resources is None:
            # This shouldn't happen due to validator, but just in case
            resources = VMResources(cpu=1, memory=1, storage=10)
            
        logger.info(f"📥 Using resources: {resources.cpu} CPU, {resources.memory}GB RAM, {resources.storage}GB storage")
        
        # Validate against minimum requirements
        if resources.cpu < settings.MIN_CPU_CORES:
            logger.error(f"❌ CPU cores {resources.cpu} below minimum {settings.MIN_CPU_CORES}")
            raise HTTPException(400, f"Minimum CPU cores required: {settings.MIN_CPU_CORES}")
        if resources.memory < settings.MIN_MEMORY_GB:
            logger.error(f"❌ Memory {resources.memory}GB below minimum {settings.MIN_MEMORY_GB}GB")
            raise HTTPException(400, f"Minimum memory required: {settings.MIN_MEMORY_GB}GB")
        if resources.storage < settings.MIN_STORAGE_GB:
            logger.error(f"❌ Storage {resources.storage}GB below minimum {settings.MIN_STORAGE_GB}GB")
            raise HTTPException(400, f"Minimum storage required: {settings.MIN_STORAGE_GB}GB")

        # Check and allocate resources
        logger.process("🔄 Allocating resources")
        if not await resource_tracker.allocate(resources):
            logger.error("❌ Insufficient resources available")
            raise HTTPException(400, "Insufficient resources available on provider")
        
        try:
            # Create VM config
            config = VMConfig(
                name=request.name,
                image=request.image or settings.DEFAULT_VM_IMAGE,
                resources=resources,
                ssh_key=request.ssh_key
            )
            
            # Create VM
            logger.process(f"🔄 Creating VM with config: {config}")
            vm_info = await provider.create_vm(config)

            # Show success message
            await vm_creation_animation(request.name)
            return vm_info
        except Exception as e:
            # If VM creation fails, deallocate resources
            logger.warning("⚠️ VM creation failed, deallocating resources")
            await resource_tracker.deallocate(resources)
            raise
        
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
        logger.process(f"🗑️  Deleting VM {vm_id}")
        vm_status_change(vm_id, "STOPPING", "Cleanup in progress")
        await provider.delete_vm(vm_id)
        vm_status_change(vm_id, "TERMINATED", "Cleanup complete")
        logger.success(f"✨ Successfully deleted VM {vm_id}")
    except MultipassError as e:
        logger.error(f"Failed to delete VM: {e}")
        raise HTTPException(500, str(e))
