from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request

from provider.auth.dependencies import (
    require_provider_admin,
    require_requestor_vm_access,
)
from provider.auth.domain import AdminIdentity, RequestorIdentity
from provider.container import Container
from provider.errors import ValidationError
from provider.payments.domain import LeaseQuote, LeaseQuoteCommand, StreamStatus
from provider.payments.lease_quote_service import LeaseQuoteService
from provider.payments.stream_status_service import StreamStatusService
from provider.utils.logging import setup_logger

router = APIRouter()
logger = setup_logger(__name__)


@router.post("/payments/lease-quotes", response_model=LeaseQuote)
@inject
async def create_lease_quote(
    request: Request,
    command: LeaseQuoteCommand,
    lease_quote_service: LeaseQuoteService = Depends(
        Provide[Container.lease_quote_service]
    ),
) -> LeaseQuote:
    logger.info(
        "Creating provider lease quote",
        extra={
            "path": request.url.path,
            "requestor_address": command.requestor_address,
            "vm_name": command.vm_name,
            "cpu": command.cpu,
            "memory": command.memory,
            "storage": command.storage,
            "duration_seconds": command.duration_seconds,
        },
    )
    try:
        quote = lease_quote_service.create_quote(command)
    except ValidationError:
        logger.warning(
            "Lease quote request rejected",
            extra={
                "path": request.url.path,
                "requestor_address": command.requestor_address,
                "vm_name": command.vm_name,
                "cpu": command.cpu,
                "memory": command.memory,
                "storage": command.storage,
                "duration_seconds": command.duration_seconds,
            },
            exc_info=True,
        )
        raise
    except Exception:
        logger.error(
            "Lease quote creation failed",
            extra={
                "path": request.url.path,
                "requestor_address": command.requestor_address,
                "vm_name": command.vm_name,
                "cpu": command.cpu,
                "memory": command.memory,
                "storage": command.storage,
                "duration_seconds": command.duration_seconds,
            },
            exc_info=True,
        )
        raise
    logger.info(
        "Provider lease quote created",
        extra={
            "path": request.url.path,
            "requestor_address": command.requestor_address,
            "vm_name": command.vm_name,
            "lease_id": quote.lease_id,
            "chain_id": quote.chain_id,
            "rate_per_second_wei": quote.rate_per_second_wei,
            "min_deposit_wei": quote.min_deposit_wei,
        },
    )
    return quote


@router.get("/vms/{requestor_name}/stream", response_model=StreamStatus)
@inject
async def get_vm_stream_status(
    requestor_name: str,
    _identity: RequestorIdentity = Depends(require_requestor_vm_access),
    stream_status_service: StreamStatusService = Depends(
        Provide[Container.stream_status_service]
    ),
) -> StreamStatus:
    return await stream_status_service.get_vm_stream_status(requestor_name)


@router.get("/payments/streams", response_model=list[StreamStatus])
@inject
async def list_stream_statuses(
    _admin: AdminIdentity = Depends(require_provider_admin),
    stream_status_service: StreamStatusService = Depends(
        Provide[Container.stream_status_service]
    ),
) -> list[StreamStatus]:
    return await stream_status_service.list_stream_statuses()
