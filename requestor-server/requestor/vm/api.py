from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from requestor.container import Container
from requestor.vm.application_service import VMApplicationService
from requestor.vm.domain import CreateVMCommand, VMCreateResult, VMRecord

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


@router.delete("/vms/{name}")
@inject
async def delete_vm(
    name: str,
    vm_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> None:
    await vm_service.delete_vm(name)
