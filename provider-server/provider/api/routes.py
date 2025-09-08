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
from .models import CreateVMRequest, ProviderInfoResponse
from ..payments.blockchain_service import StreamPaymentReader
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
    stream_map = Depends(Provide[Container.stream_map]),
) -> VMInfo:
    """Create a new VM."""
    try:
        logger.info(f"📥 Received VM creation request for '{request.name}'")
        
        resources = request.resources or VMResources()

        # If payments are enabled, require a valid stream before starting
        if settings["STREAM_PAYMENT_ADDRESS"] and settings["STREAM_PAYMENT_ADDRESS"] != "0x0000000000000000000000000000000000000000":
            if request.stream_id is None:
                raise HTTPException(status_code=400, detail="stream_id required when payments are enabled")
            reader = StreamPaymentReader(settings["POLYGON_RPC_URL"], settings["STREAM_PAYMENT_ADDRESS"])
            ok, reason = reader.verify_stream(int(request.stream_id), settings["PROVIDER_ID"])
            if not ok:
                raise HTTPException(status_code=400, detail=f"invalid stream: {reason}")
        
        # Create VM config
        config = VMConfig(
            name=request.name,
            image=request.image or settings["DEFAULT_VM_IMAGE"],
            resources=resources,
            ssh_key=request.ssh_key
        )
        
        vm_info = await vm_service.create_vm(config)
        # Persist VM->stream mapping if provided
        if request.stream_id is not None:
            try:
                await stream_map.set(vm_info.id, int(request.stream_id))
            except Exception as e:
                logger.warning(f"failed to persist stream mapping for {vm_info.id}: {e}")
        await vm_creation_animation(request.name)
        return vm_info
    except MultipassError as e:
        logger.error(f"Failed to create VM: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        # Propagate explicit HTTP errors (e.g., payment gating)
        raise
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


@router.post("/vms/{requestor_name}/stop", response_model=VMInfo)
@inject
async def stop_vm(
    requestor_name: str,
    vm_service: VMService = Depends(Provide[Container.vm_service]),
) -> VMInfo:
    """Stop a VM."""
    try:
        logger.process(f"🛑 Stopping VM '{requestor_name}'")
        vm_info = await vm_service.stop_vm(requestor_name)
        vm_status_change(requestor_name, vm_info.status.value, "VM stopped")
        logger.success(f"✨ Successfully stopped VM '{requestor_name}'")
        return vm_info
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
    stream_map = Depends(Provide[Container.stream_map]),
) -> None:
    """Delete a VM."""
    try:
        logger.process(f"🗑️  Deleting VM '{requestor_name}'")
        vm_status_change(requestor_name, "STOPPING", "Cleanup in progress")
        await vm_service.delete_vm(requestor_name)
        try:
            await stream_map.remove(requestor_name)
        except Exception as e:
            logger.warning(f"failed to remove stream mapping for {requestor_name}: {e}")
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
@router.get("/provider/info", response_model=ProviderInfoResponse)
@inject
async def provider_info(settings: Settings = Depends(Provide[Container.config])) -> ProviderInfoResponse:
    return ProviderInfoResponse(
        provider_id=settings["PROVIDER_ID"],
        stream_payment_address=settings["STREAM_PAYMENT_ADDRESS"],
        glm_token_address=settings["GLM_TOKEN_ADDRESS"],
    )
