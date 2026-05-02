import asyncio
import os
import signal

from fastapi import APIRouter

router = APIRouter()


@router.post("/admin/shutdown")
async def admin_shutdown() -> dict[str, bool]:
    loop = asyncio.get_running_loop()

    def _signal_self() -> None:
        os.kill(os.getpid(), signal.SIGTERM)

    loop.call_later(0.2, _signal_self)
    return {"ok": True}
