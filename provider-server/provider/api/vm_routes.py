from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from provider.container import Container
from provider.payments.auth import requestor_action_signer
from provider.vm.application_service import VMApplicationService
from provider.vm.domain import CreateVMCommand
from provider.vm.models import (
    CloneVMRequest,
    CreateSnapshotRequest,
    ResizeVMRequest,
    VMAccessInfo,
    VMImage,
    VMInfo,
    VMResources,
    VMSnapshot,
)

from .models import (
    CreateVMJobResponse,
    CreateVMJobStatus,
    CreateVMRequest,
    VMAccessPendingResponse,
)

router = APIRouter()


@router.get("/images", response_model=list[VMImage])
@inject
async def list_images(
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> list[VMImage]:
    return await vm_app_service.list_images()


@router.post(
    "/vms",
    response_model=VMInfo,
    responses={202: {"model": CreateVMJobResponse}},
)
@inject
async def create_vm(
    request: CreateVMRequest,
    action_signer: str | None = Depends(requestor_action_signer),
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
    async_mode: bool = Query(default=False, alias="async"),
) -> VMInfo | JSONResponse:
    resources = request.resources or VMResources(cpu=1, memory=1, storage=10)
    result = await vm_app_service.create_vm(
        CreateVMCommand(
            name=request.name,
            image=request.image,
            resources=resources,
            ssh_key=request.ssh_key,
            payment=request.payment,
            action_signer=action_signer,
            async_mode=async_mode,
        )
    )
    if isinstance(result, VMInfo):
        return result
    response = CreateVMJobResponse(**result.model_dump())
    return JSONResponse(status_code=202, content=response.model_dump())


@router.get("/vms/jobs/{job_id}", response_model=CreateVMJobStatus)
@inject
async def get_create_job(
    job_id: str,
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> CreateVMJobStatus:
    return CreateVMJobStatus(**await vm_app_service.get_create_job(job_id))


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


@router.get(
    "/vms/{requestor_name}/access",
    response_model=VMAccessInfo,
    responses={202: {"model": VMAccessPendingResponse}},
)
@inject
async def get_vm_access(
    requestor_name: str,
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMAccessInfo | JSONResponse:
    result = await vm_app_service.get_vm_access(requestor_name)
    if isinstance(result, dict):
        return JSONResponse(status_code=202, content=result)
    return result


@router.post("/vms/{requestor_name}/stop", response_model=VMInfo)
@inject
async def stop_vm(
    requestor_name: str,
    action_signer: str | None = Depends(requestor_action_signer),
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMInfo:
    return await vm_app_service.stop_vm(requestor_name, action_signer)


@router.post("/vms/{requestor_name}/start", response_model=VMInfo)
@inject
async def start_vm(
    requestor_name: str,
    action_signer: str | None = Depends(requestor_action_signer),
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMInfo:
    return await vm_app_service.start_vm(requestor_name, action_signer)


@router.post("/vms/{requestor_name}/restart", response_model=VMInfo)
@inject
async def restart_vm(
    requestor_name: str,
    action_signer: str | None = Depends(requestor_action_signer),
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMInfo:
    return await vm_app_service.restart_vm(requestor_name, action_signer)


@router.post("/vms/{requestor_name}/suspend", response_model=VMInfo)
@inject
async def suspend_vm(
    requestor_name: str,
    action_signer: str | None = Depends(requestor_action_signer),
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMInfo:
    return await vm_app_service.suspend_vm(requestor_name, action_signer)


@router.post("/vms/{requestor_name}/resume", response_model=VMInfo)
@inject
async def resume_vm(
    requestor_name: str,
    action_signer: str | None = Depends(requestor_action_signer),
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMInfo:
    return await vm_app_service.start_vm(requestor_name, action_signer)


@router.post("/vms/{requestor_name}/resize", response_model=VMInfo)
@inject
async def resize_vm(
    requestor_name: str,
    request: ResizeVMRequest,
    action_signer: str | None = Depends(requestor_action_signer),
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMInfo:
    return await vm_app_service.resize_vm(
        requestor_name, request.resources, action_signer
    )


@router.get("/vms/{requestor_name}/snapshots", response_model=list[VMSnapshot])
@inject
async def list_snapshots(
    requestor_name: str,
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> list[VMSnapshot]:
    return await vm_app_service.list_snapshots(requestor_name)


@router.post("/vms/{requestor_name}/snapshots", response_model=VMSnapshot)
@inject
async def create_snapshot(
    requestor_name: str,
    request: CreateSnapshotRequest,
    action_signer: str | None = Depends(requestor_action_signer),
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMSnapshot:
    return await vm_app_service.create_snapshot(
        requestor_name, request.name, request.comment, action_signer
    )


@router.post(
    "/vms/{requestor_name}/snapshots/{snapshot_name}/restore", response_model=VMInfo
)
@inject
async def restore_snapshot(
    requestor_name: str,
    snapshot_name: str,
    action_signer: str | None = Depends(requestor_action_signer),
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMInfo:
    return await vm_app_service.restore_snapshot(
        requestor_name, snapshot_name, action_signer
    )


@router.delete("/vms/{requestor_name}/snapshots/{snapshot_name}")
@inject
async def delete_snapshot(
    requestor_name: str,
    snapshot_name: str,
    action_signer: str | None = Depends(requestor_action_signer),
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> None:
    await vm_app_service.delete_snapshot(requestor_name, snapshot_name, action_signer)


@router.post("/vms/{requestor_name}/clone", response_model=VMInfo)
@inject
async def clone_vm(
    requestor_name: str,
    request: CloneVMRequest,
    action_signer: str | None = Depends(requestor_action_signer),
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMInfo:
    return await vm_app_service.clone_vm(requestor_name, request.name, action_signer)


@router.delete("/vms/{requestor_name}")
@inject
async def delete_vm(
    requestor_name: str,
    action_signer: str | None = Depends(requestor_action_signer),
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> None:
    await vm_app_service.delete_vm(requestor_name, action_signer)
