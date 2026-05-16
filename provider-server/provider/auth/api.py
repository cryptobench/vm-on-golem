from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from provider.auth.domain import RequestorSession, RequestorSessionCommand
from provider.auth.services import ProviderAuthService
from provider.container import Container

router = APIRouter()


@router.post("/auth/requestor-sessions", response_model=RequestorSession)
@inject
async def create_requestor_session(
    command: RequestorSessionCommand,
    auth_service: ProviderAuthService = Depends(
        Provide[Container.provider_auth_service]
    ),
) -> RequestorSession:
    return auth_service.issue_requestor_session(command)
