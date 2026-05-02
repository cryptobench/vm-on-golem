import asyncio
import os
import signal

from fastapi import APIRouter

from .models import AdminShutdownResponse

router = APIRouter()


@router.post("/admin/shutdown", response_model=AdminShutdownResponse)
async def admin_shutdown() -> AdminShutdownResponse:
    loop = asyncio.get_running_loop()

    def _signal_self() -> None:
        os.kill(os.getpid(), signal.SIGTERM)

    loop.call_later(0.2, _signal_self)
    return AdminShutdownResponse(ok=True)
