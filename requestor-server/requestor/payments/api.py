from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from requestor.container import Container
from requestor.payments.domain import (
    CreateStreamCommand,
    StreamActionResult,
    TopUpStreamCommand,
    VMStreamStatus,
)
from requestor.payments.service import RequestorPaymentService

router = APIRouter()


@router.get("/vms/{name}/stream", response_model=VMStreamStatus)
@inject
async def get_vm_stream_status(
    name: str,
    payment_service: RequestorPaymentService = Depends(
        Provide[Container.payment_service]
    ),
) -> VMStreamStatus:
    return await payment_service.get_vm_stream_status(name)


@router.get("/payments/streams", response_model=list[VMStreamStatus])
@inject
async def list_streams(
    payment_service: RequestorPaymentService = Depends(
        Provide[Container.payment_service]
    ),
) -> list[VMStreamStatus]:
    return await payment_service.list_vm_stream_statuses()


@router.post("/payments/streams", response_model=StreamActionResult)
@inject
async def create_stream(
    command: CreateStreamCommand,
    payment_service: RequestorPaymentService = Depends(
        Provide[Container.payment_service]
    ),
) -> StreamActionResult:
    return await payment_service.create_stream(command)


@router.post("/payments/streams/{stream_id}/topups", response_model=StreamActionResult)
@inject
async def top_up_stream(
    stream_id: int,
    command: TopUpStreamCommand,
    payment_service: RequestorPaymentService = Depends(
        Provide[Container.payment_service]
    ),
) -> StreamActionResult:
    return await payment_service.top_up_stream(stream_id, command.amount_wei)
