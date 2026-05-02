from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from provider.container import Container
from provider.payments.domain import StreamStatus
from provider.payments.stream_status_service import StreamStatusService

router = APIRouter()


@router.get("/vms/{requestor_name}/stream", response_model=StreamStatus)
@inject
async def get_vm_stream_status(
    requestor_name: str,
    stream_status_service: StreamStatusService = Depends(
        Provide[Container.stream_status_service]
    ),
) -> StreamStatus:
    return await stream_status_service.get_vm_stream_status(requestor_name)


@router.get("/payments/streams", response_model=list[StreamStatus])
@inject
async def list_stream_statuses(
    stream_status_service: StreamStatusService = Depends(
        Provide[Container.stream_status_service]
    ),
) -> list[StreamStatus]:
    return await stream_status_service.list_stream_statuses()
