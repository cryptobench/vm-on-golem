from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from provider.container import Container
from provider.provider_info.domain import ProviderInfo
from provider.provider_info.service import ProviderInfoService

router = APIRouter()


@router.get("/provider/info", response_model=ProviderInfo)
@inject
async def provider_info(
    provider_info_service: ProviderInfoService = Depends(
        Provide[Container.provider_info_service]
    ),
) -> ProviderInfo:
    return provider_info_service.get_info()
