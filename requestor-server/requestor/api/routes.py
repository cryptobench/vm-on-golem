from fastapi import APIRouter

from requestor.discovery import api as discovery_api
from requestor.payments import api as payments_api
from requestor.vm import api as vm_api
from requestor.wallet import api as wallet_api

router = APIRouter()
router.include_router(discovery_api.router)
router.include_router(vm_api.router)
router.include_router(payments_api.router)
router.include_router(wallet_api.router)


@router.get("/settings")
async def settings() -> dict:
    from requestor.config import config

    return {
        "environment": config.environment,
        "network": config.network,
        "payments_network": config.payments_network,
        "discovery_backend": config.discovery_backend,
        "arkiv_rpc_url": config.arkiv_rpc_url,
        "arkiv_ws_url": config.arkiv_ws_url,
        "central_discovery_url": config.discovery_url,
        "faucet_enabled": config.faucet_enabled,
    }
