from typing import Optional

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query, WebSocket

from provider.container import Container
from provider.live.service import HostLiveService, ProviderLiveService, VMLiveService

router = APIRouter()


@router.websocket("/provider/live")
@inject
async def provider_live(
    websocket: WebSocket,
    live_service: ProviderLiveService = Depends(
        Provide[Container.provider_live_service]
    ),
) -> None:
    await live_service.stream_provider(websocket)


@router.websocket("/monitoring/host/live")
@inject
async def host_live(
    websocket: WebSocket,
    history_range: str = Query(default="1h"),
    live_service: HostLiveService = Depends(Provide[Container.host_live_service]),
) -> None:
    await live_service.stream_host(websocket, history_range=history_range)


@router.websocket("/vms/{requestor_name}/live")
@inject
async def vm_live(
    websocket: WebSocket,
    requestor_name: str,
    history_range: str = Query(default="1h"),
    job_id: Optional[str] = Query(default=None),
    live_service: VMLiveService = Depends(Provide[Container.vm_live_service]),
) -> None:
    await live_service.stream_vm(
        websocket,
        vm_id=requestor_name,
        history_range=history_range,
        job_id=job_id,
    )
