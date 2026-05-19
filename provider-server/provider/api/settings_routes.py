from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from provider.auth.dependencies import require_provider_admin
from provider.auth.domain import AdminIdentity
from provider.container import Container
from provider.settings.domain import (
    ProviderSettings,
    UpdatePricingSettings,
    UpdateResourceSettings,
)
from provider.settings.service import ProviderSettingsService

router = APIRouter()


@router.get("/provider/settings", response_model=ProviderSettings)
@inject
async def provider_settings(
    _admin: AdminIdentity = Depends(require_provider_admin),
    settings_service: ProviderSettingsService = Depends(
        Provide[Container.provider_settings_service]
    ),
) -> ProviderSettings:
    return await settings_service.get_settings()


@router.patch("/provider/settings/resources", response_model=ProviderSettings)
@inject
async def update_provider_resources(
    command: UpdateResourceSettings,
    _admin: AdminIdentity = Depends(require_provider_admin),
    settings_service: ProviderSettingsService = Depends(
        Provide[Container.provider_settings_service]
    ),
) -> ProviderSettings:
    return await settings_service.update_resources(command)


@router.patch("/provider/settings/pricing", response_model=ProviderSettings)
@inject
async def update_provider_pricing(
    command: UpdatePricingSettings,
    _admin: AdminIdentity = Depends(require_provider_admin),
    settings_service: ProviderSettingsService = Depends(
        Provide[Container.provider_settings_service]
    ),
) -> ProviderSettings:
    return await settings_service.update_pricing(command)
