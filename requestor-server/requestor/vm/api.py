from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from requestor.container import Container
from requestor.vm.application_service import VMApplicationService
from requestor.vm.domain import (
    CloneVMCommand,
    CreateVMCommand,
    ResizeVMCommand,
    SnapshotCommand,
    VMCreateResult,
    VMImage,
    VMRecord,
    VMSnapshot,
)

router = APIRouter()


@router.get("/vms", response_model=list[VMRecord])
@inject
async def list_vms(
    vm_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> list[VMRecord]:
    return await vm_service.list_vms()


@router.post("/vms", response_model=VMCreateResult)
@inject
async def create_vm(
    command: CreateVMCommand,
    vm_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMCreateResult:
    return await vm_service.create_vm(command)


@router.get("/vms/{name}", response_model=VMRecord)
@inject
async def get_vm(
    name: str,
    vm_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMRecord:
    return await vm_service.get_vm(name)


@router.post("/vms/{name}/start", response_model=VMRecord)
@inject
async def start_vm(
    name: str,
    vm_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMRecord:
    return await vm_service.start_vm(name)


@router.post("/vms/{name}/stop", response_model=VMRecord)
@inject
async def stop_vm(
    name: str,
    vm_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMRecord:
    return await vm_service.stop_vm(name)


@router.post("/vms/{name}/restart", response_model=VMRecord)
@inject
async def restart_vm(
    name: str,
    vm_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMRecord:
    return await vm_service.restart_vm(name)


@router.post("/vms/{name}/suspend", response_model=VMRecord)
@inject
async def suspend_vm(
    name: str,
    vm_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMRecord:
    return await vm_service.suspend_vm(name)


@router.post("/vms/{name}/resume", response_model=VMRecord)
@inject
async def resume_vm(
    name: str,
    vm_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMRecord:
    return await vm_service.resume_vm(name)


@router.post("/vms/{name}/resize", response_model=VMRecord)
@inject
async def resize_vm(
    name: str,
    command: ResizeVMCommand,
    vm_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMRecord:
    return await vm_service.resize_vm(name, command)


@router.get("/providers/{provider_id}/images", response_model=list[VMImage])
@inject
async def list_provider_images(
    provider_id: str,
    vm_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> list[VMImage]:
    return await vm_service.list_provider_images(provider_id)


@router.get("/vms/{name}/snapshots", response_model=list[VMSnapshot])
@inject
async def list_snapshots(
    name: str,
    vm_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> list[VMSnapshot]:
    return await vm_service.list_snapshots(name)


@router.post("/vms/{name}/snapshots", response_model=VMSnapshot)
@inject
async def create_snapshot(
    name: str,
    command: SnapshotCommand,
    vm_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMSnapshot:
    return await vm_service.create_snapshot(name, command)


@router.post("/vms/{name}/snapshots/{snapshot_name}/restore", response_model=VMRecord)
@inject
async def restore_snapshot(
    name: str,
    snapshot_name: str,
    vm_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMRecord:
    return await vm_service.restore_snapshot(name, snapshot_name)


@router.delete("/vms/{name}/snapshots/{snapshot_name}")
@inject
async def delete_snapshot(
    name: str,
    snapshot_name: str,
    vm_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> None:
    await vm_service.delete_snapshot(name, snapshot_name)


@router.post("/vms/{name}/clone", response_model=VMRecord)
@inject
async def clone_vm(
    name: str,
    command: CloneVMCommand,
    vm_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> VMRecord:
    return await vm_service.clone_vm(name, command)


@router.delete("/vms/{name}")
@inject
async def delete_vm(
    name: str,
    vm_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> None:
    await vm_service.delete_vm(name)
