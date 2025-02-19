from fastapi import APIRouter, Depends, HTTPException, Request
from typing import List, Optional
import logging

from ..config import settings
from ..vm.models import VMProvider, VMError, VMNotFoundError, VMStateError
from ..discovery.advertiser import ResourceMonitor
from .models import (
    CreateVMRequest,
    VMResponse,
    AddSSHKeyRequest,
    ErrorResponse,
    ListVMsResponse,
    ProviderStatusResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix=settings.API_V1_PREFIX)

async def get_vm_provider() -> VMProvider:
    """Dependency for getting VM provider."""
    # This will be initialized in the main application
    raise NotImplementedError()

@router.post(
    "/vms",
    response_model=VMResponse,
    responses={
        400: {"model": ErrorResponse},
        503: {"model": ErrorResponse}
    }
)
async def create_vm(
    request: CreateVMRequest,
    provider: VMProvider = Depends(get_vm_provider)
):
    """Create a new VM."""
    try:
        # Check if we can accept the resources
        if not ResourceMonitor.can_accept_resources(
            cpu=request.resources.cpu,
            memory=request.resources.memory,
            storage=request.resources.storage
        ):
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "RESOURCE_UNAVAILABLE",
                    "message": "Insufficient resources available"
                }
            )

        vm_info = await provider.create_vm(request)
        return VMResponse(**vm_info.dict())
    except VMError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VM_CREATE_ERROR",
                "message": str(e),
                "details": {"vm_id": e.vm_id} if e.vm_id else None
            }
        )

@router.get(
    "/vms",
    response_model=ListVMsResponse,
    responses={
        400: {"model": ErrorResponse}
    }
)
async def list_vms(
    status: Optional[str] = None,
    provider: VMProvider = Depends(get_vm_provider)
):
    """List all VMs."""
    try:
        vms = []
        total = 0
        for vm_id in provider.vms:
            vm_info = await provider.get_vm_status(vm_id)
            if status is None or vm_info.status == status:
                vms.append(VMResponse(**vm_info.dict()))
                total += 1
        return ListVMsResponse(vms=vms, total=total)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "LIST_VMS_ERROR",
                "message": str(e)
            }
        )

@router.get(
    "/vms/{vm_id}",
    response_model=VMResponse,
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse}
    }
)
async def get_vm(
    vm_id: str,
    provider: VMProvider = Depends(get_vm_provider)
):
    """Get VM status."""
    try:
        vm_info = await provider.get_vm_status(vm_id)
        return VMResponse(**vm_info.dict())
    except VMNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "VM_NOT_FOUND",
                "message": f"VM {vm_id} not found"
            }
        )
    except VMError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VM_STATUS_ERROR",
                "message": str(e)
            }
        )

@router.delete(
    "/vms/{vm_id}",
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse}
    }
)
async def delete_vm(
    vm_id: str,
    provider: VMProvider = Depends(get_vm_provider)
):
    """Delete a VM."""
    try:
        await provider.delete_vm(vm_id)
        return {"status": "success"}
    except VMNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "VM_NOT_FOUND",
                "message": f"VM {vm_id} not found"
            }
        )
    except VMError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VM_DELETE_ERROR",
                "message": str(e)
            }
        )

@router.post(
    "/vms/{vm_id}/start",
    response_model=VMResponse,
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse}
    }
)
async def start_vm(
    vm_id: str,
    provider: VMProvider = Depends(get_vm_provider)
):
    """Start a VM."""
    try:
        vm_info = await provider.start_vm(vm_id)
        return VMResponse(**vm_info.dict())
    except VMNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "VM_NOT_FOUND",
                "message": f"VM {vm_id} not found"
            }
        )
    except VMStateError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VM_STATE_ERROR",
                "message": str(e)
            }
        )
    except VMError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VM_START_ERROR",
                "message": str(e)
            }
        )

@router.post(
    "/vms/{vm_id}/stop",
    response_model=VMResponse,
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse}
    }
)
async def stop_vm(
    vm_id: str,
    provider: VMProvider = Depends(get_vm_provider)
):
    """Stop a VM."""
    try:
        vm_info = await provider.stop_vm(vm_id)
        return VMResponse(**vm_info.dict())
    except VMNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "VM_NOT_FOUND",
                "message": f"VM {vm_id} not found"
            }
        )
    except VMStateError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VM_STATE_ERROR",
                "message": str(e)
            }
        )
    except VMError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VM_STOP_ERROR",
                "message": str(e)
            }
        )


@router.get(
    "/status",
    response_model=ProviderStatusResponse
)
async def get_status(
    provider: VMProvider = Depends(get_vm_provider)
):
    """Get provider status."""
    monitor = ResourceMonitor()
    return ProviderStatusResponse(
        resources=monitor.get_available_resources(),
        vm_count=len(provider.vms),
        max_vms=settings.MAX_VMS
    )
