from typing import Any

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from provider.container import Container
from provider.vm.application_service import VMApplicationService
from provider.vm.domain import CreateVMCommand
from provider.vm.models import VMAccessInfo, VMInfo, VMResources

from .models import CreateVMJobResponse, CreateVMRequest

router = APIRouter()


@router.post("/vms")
@inject
async def create_vm(
    request: CreateVMRequest,
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
    async_mode: bool = Query(default=False, alias="async"),
) -> Any:
    resources = request.resources or VMResources(cpu=1, memory=1, storage=10)
    result = await vm_app_service.create_vm(
        CreateVMCommand(
            name=request.name,
            image=request.image,
            resources=resources,
            ssh_key=request.ssh_key,
            stream_id=request.stream_id,
            async_mode=async_mode,
        )
    )
    if isinstance(result, VMInfo):
        return result
    response = CreateVMJobResponse(**result.model_dump())
    return JSONResponse(status_code=202, content=response.model_dump())


@router.get("/vms/jobs/{job_id}")
@inject
async def get_create_job(
    job_id: str,
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> dict:
    return await vm_app_service.get_create_job(job_id)


@router.get("/vms", response_model=list[VMInfo])
@inject
async def list_vms(
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> list[VMInfo]:
    return await vm_app_service.list_vms()


@router.get("/vms/{requestor_name}", response_model=VMInfo)
@inject
async def get_vm_status(
    requestor_name: str,
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMInfo:
    return await vm_app_service.get_vm_status(requestor_name)


@router.get("/vms/{requestor_name}/access", response_model=None)
@inject
async def get_vm_access(
    requestor_name: str,
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> Any:
    result = await vm_app_service.get_vm_access(requestor_name)
    if isinstance(result, dict):
        return JSONResponse(status_code=202, content=result)
    return result


@router.post("/vms/{requestor_name}/stop", response_model=VMInfo)
@inject
async def stop_vm(
    requestor_name: str,
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMInfo:
    return await vm_app_service.stop_vm(requestor_name)


@router.delete("/vms/{requestor_name}")
@inject
async def delete_vm(
    requestor_name: str,
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> None:
    await vm_app_service.delete_vm(requestor_name)
