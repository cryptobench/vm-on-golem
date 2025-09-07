import json
from typing import List
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request

from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, HTTPException, Depends

from ..config import Settings
from ..container import Container
from ..utils.logging import setup_logger
from ..utils.ascii_art import vm_creation_animation, vm_status_change
from ..vm.models import VMInfo, VMAccessInfo, VMConfig, VMResources, VMNotFoundError
from .models import CreateVMRequest
from ..vm.service import VMService
from ..vm.multipass_adapter import MultipassError

logger = setup_logger(__name__)
router = APIRouter()


@router.post("/vms", response_model=VMInfo)
@inject
async def create_vm(
    request: CreateVMRequest,
    vm_service: VMService = Depends(Provide[Container.vm_service]),
    settings: Settings = Depends(Provide[Container.config]),
) -> VMInfo:
    """Create a new VM."""
    try:
        logger.info(f"📥 Received VM creation request for '{request.name}'")
        
        resources = request.resources or VMResources()
        
        # Create VM config
        config = VMConfig(
            name=request.name,
            image=request.image or settings["DEFAULT_VM_IMAGE"],
            resources=resources,
            ssh_key=request.ssh_key
        )
        
        vm_info = await vm_service.create_vm(config)
        await vm_creation_animation(request.name)
        return vm_info
    except MultipassError as e:
        logger.error(f"Failed to create VM: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.get("/vms", response_model=List[VMInfo])
@inject
async def list_vms(
    vm_service: VMService = Depends(Provide[Container.vm_service]),
) -> List[VMInfo]:
    """List all VMs."""
    try:
        logger.info("📋 Listing all VMs")
        return await vm_service.list_vms()
    except MultipassError as e:
        logger.error(f"Failed to list VMs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.get("/vms/{requestor_name}", response_model=VMInfo)
@inject
async def get_vm_status(
    requestor_name: str,
    vm_service: VMService = Depends(Provide[Container.vm_service]),
) -> VMInfo:
    """Get VM status."""
    try:
        logger.info(f"🔍 Getting status for VM '{requestor_name}'")
        status = await vm_service.get_vm_status(requestor_name)
        vm_status_change(requestor_name, status.status.value)
        return status
    except VMNotFoundError as e:
        logger.error(f"VM not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except MultipassError as e:
        logger.error(f"Failed to get VM status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.get("/vms/{requestor_name}/access", response_model=VMAccessInfo)
@inject
async def get_vm_access(
    requestor_name: str,
    vm_service: VMService = Depends(Provide[Container.vm_service]),
    settings: Settings = Depends(Provide[Container.config]),
) -> VMAccessInfo:
    """Get VM access information."""
    try:
        vm = await vm_service.get_vm_status(requestor_name)
        if not vm:
            raise HTTPException(404, "VM not found")
        
        multipass_name = await vm_service.name_mapper.get_multipass_name(requestor_name)
        if not multipass_name:
            raise HTTPException(404, "VM mapping not found")
        
        return VMAccessInfo(
            ssh_host=settings["PUBLIC_IP"] or "localhost",
            ssh_port=vm.ssh_port,
            vm_id=requestor_name,
            multipass_name=multipass_name
        )
    except MultipassError as e:
        logger.error(f"Failed to get VM access info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


@router.post("/vms/{requestor_name}/stop")
@inject
async def stop_vm(
    requestor_name: str,
    vm_service: VMService = Depends(Provide[Container.vm_service]),
) -> None:
    """Stop a VM."""
    try:
        logger.process(f"🛑 Stopping VM '{requestor_name}'")
        await vm_service.stop_vm(requestor_name)
        vm_status_change(requestor_name, "STOPPED", "VM stopped")
        logger.success(f"✨ Successfully stopped VM '{requestor_name}'")
    except VMNotFoundError as e:
        logger.error(f"VM not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except MultipassError as e:
        logger.error(f"Failed to stop VM: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
 
 
@router.delete("/vms/{requestor_name}")
@inject
async def delete_vm(
    requestor_name: str,
    vm_service: VMService = Depends(Provide[Container.vm_service]),
) -> None:
    """Delete a VM."""
    try:
        logger.process(f"🗑️  Deleting VM '{requestor_name}'")
        vm_status_change(requestor_name, "STOPPING", "Cleanup in progress")
        await vm_service.delete_vm(requestor_name)
        vm_status_change(requestor_name, "TERMINATED", "Cleanup complete")
        logger.success(f"✨ Successfully deleted VM '{requestor_name}'")
    except VMNotFoundError as e:
        logger.error(f"VM not found: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except MultipassError as e:
        logger.error(f"Failed to delete VM: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred")
