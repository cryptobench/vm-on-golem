import asyncio
import os
import signal

from fastapi import APIRouter, Depends

from provider.auth.dependencies import require_provider_admin
from provider.auth.domain import AdminIdentity

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
