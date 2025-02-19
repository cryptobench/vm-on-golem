from fastapi import APIRouter, Depends, HTTPException
from typing import List

from ..vm.models import (
    VMConfig,
    VMInfo,
    VMCreateError,
    VMNotFoundError,
    VMStateError,
    ResourceError
)
from ..vm.multipass import MultipassProvider
from ..discovery.resource_tracker import ResourceTracker

router = APIRouter()

def get_provider() -> MultipassProvider:
    """Get VM provider from app state."""
    from ..main import app
    return app.state.provider

def get_resource_tracker() -> ResourceTracker:
    """Get resource tracker from app state."""
    from ..main import app
    return app.state.resource_tracker

@router.post("/vms", response_model=VMInfo)
async def create_vm(
    config: VMConfig,
    provider: MultipassProvider = Depends(get_provider),
    resource_tracker: ResourceTracker = Depends(get_resource_tracker)
):
    """Create a new VM."""
    try:
        # Resource check is now handled by provider
        vm_info = await provider.create_vm(config)
        return vm_info
    except ResourceError as e:
        raise HTTPException(
            status_code=503,
            detail={"code": "RESOURCE_UNAVAILABLE", "message": str(e)}
        )
    except VMCreateError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "VM_CREATE_ERROR", "message": str(e)}
        )

@router.get("/vms", response_model=List[VMInfo])
async def list_vms(
    provider: MultipassProvider = Depends(get_provider)
):
    """List all VMs."""
    return list(provider.vms.values())

@router.get("/vms/{vm_id}", response_model=VMInfo)
async def get_vm(
    vm_id: str,
    provider: MultipassProvider = Depends(get_provider)
):
    """Get VM status."""
    try:
        return await provider.get_vm_status(vm_id)
    except VMNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "VM_NOT_FOUND", "message": f"VM {vm_id} not found"}
        )

@router.post("/vms/{vm_id}/start", response_model=VMInfo)
async def start_vm(
    vm_id: str,
    provider: MultipassProvider = Depends(get_provider)
):
    """Start a VM."""
    try:
        return await provider.start_vm(vm_id)
    except VMNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "VM_NOT_FOUND", "message": f"VM {vm_id} not found"}
        )
    except VMStateError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "VM_STATE_ERROR", "message": str(e)}
        )

@router.post("/vms/{vm_id}/stop", response_model=VMInfo)
async def stop_vm(
    vm_id: str,
    provider: MultipassProvider = Depends(get_provider)
):
    """Stop a VM."""
    try:
        return await provider.stop_vm(vm_id)
    except VMNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "VM_NOT_FOUND", "message": f"VM {vm_id} not found"}
        )
    except VMStateError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "VM_STATE_ERROR", "message": str(e)}
        )

@router.delete("/vms/{vm_id}")
async def delete_vm(
    vm_id: str,
    provider: MultipassProvider = Depends(get_provider)
):
    """Delete a VM."""
    try:
        await provider.delete_vm(vm_id)
        return {"status": "success"}
    except VMNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "VM_NOT_FOUND", "message": f"VM {vm_id} not found"}
        )

@router.get("/resources")
async def get_resources(
    resource_tracker: ResourceTracker = Depends(get_resource_tracker)
):
    """Get current resource availability."""
    return {
        "total": resource_tracker.total_resources,
        "allocated": resource_tracker.allocated_resources,
        "available": resource_tracker.get_available_resources()
    }
