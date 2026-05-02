from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from provider.container import Container
from provider.summary.domain import ProviderSummary
from provider.summary.service import ProviderSummaryService

router = APIRouter()


@router.get("/summary", response_model=ProviderSummary)
@inject
async def provider_summary(
    summary_service: ProviderSummaryService = Depends(
        Provide[Container.summary_service]
    ),
) -> ProviderSummary:
    return await summary_service.get_summary()
