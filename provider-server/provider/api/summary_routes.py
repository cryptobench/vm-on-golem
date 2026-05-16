from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from provider.auth.dependencies import require_provider_admin
from provider.auth.domain import AdminIdentity
from provider.container import Container
from provider.summary.domain import ProviderSummary
from provider.summary.service import ProviderSummaryService

router = APIRouter()


@router.get("/summary", response_model=ProviderSummary)
@inject
async def provider_summary(
    _admin: AdminIdentity = Depends(require_provider_admin),
    summary_service: ProviderSummaryService = Depends(
        Provide[Container.summary_service]
    ),
) -> ProviderSummary:
    return await summary_service.get_summary()
