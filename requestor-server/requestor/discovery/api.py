from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query

from requestor.container import Container
from requestor.discovery.domain import ProviderSearchQuery
from requestor.discovery.service import ProviderDiscoveryService

router = APIRouter()


@router.get("/providers")
@inject
async def list_providers(
    cpu: int | None = None,
    memory: int | None = None,
    storage: int | None = None,
    country: str | None = None,
    platform: str | None = None,
    backend: str | None = Query(default=None),
    payments_network: str | None = None,
    include_all_payments: bool = False,
    discovery_service: ProviderDiscoveryService = Depends(
        Provide[Container.discovery_service]
    ),
) -> dict:
    providers = await discovery_service.find_providers(
        ProviderSearchQuery(
            cpu=cpu,
            memory=memory,
            storage=storage,
            country=country,
            platform=platform,
            payments_network=payments_network,
            include_all_payments=include_all_payments,
        ),
        backend=backend,
    )
    return {"providers": providers}
