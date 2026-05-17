import asyncio
import os
import signal

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from provider.auth.dependencies import require_provider_admin
from provider.auth.domain import AdminIdentity
from provider.container import Container
from provider.vm.application_service import VMApplicationService
from provider.vm.domain import LeaseTerminationResult

from .models import AdminShutdownResponse

router = APIRouter()


@router.post("/admin/shutdown", response_model=AdminShutdownResponse)
async def admin_shutdown(
    _admin: AdminIdentity = Depends(require_provider_admin),
) -> AdminShutdownResponse:
    loop = asyncio.get_running_loop()

    def _signal_self() -> None:
        os.kill(os.getpid(), signal.SIGTERM)

    loop.call_later(0.2, _signal_self)
    return AdminShutdownResponse(ok=True)


@router.post(
    "/admin/vms/{requestor_name}/terminate-lease",
    response_model=LeaseTerminationResult,
)
@inject
async def terminate_vm_lease(
    requestor_name: str,
    _admin: AdminIdentity = Depends(require_provider_admin),
    vm_app_service: VMApplicationService = Depends(
        Provide[Container.vm_application_service]
    ),
) -> LeaseTerminationResult:
    return await vm_app_service.terminate_lease_by_provider(requestor_name)
