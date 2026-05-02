from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from requestor.container import Container
from requestor.wallet.domain import FaucetResult
from requestor.wallet.service import WalletService

router = APIRouter()


@router.post("/wallet/faucet", response_model=FaucetResult)
@inject
async def request_faucet_funds(
    wallet_service: WalletService = Depends(Provide[Container.wallet_service]),
) -> FaucetResult:
    return await wallet_service.request_faucet_funds()
