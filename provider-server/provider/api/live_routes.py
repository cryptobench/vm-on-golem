from typing import Optional

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query, WebSocket

from provider.container import Container
from provider.live.service import VMLiveService

router = APIRouter()


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
