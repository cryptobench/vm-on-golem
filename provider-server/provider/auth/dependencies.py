from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from provider.auth.domain import AdminIdentity, RequestorIdentity
from provider.auth.errors import ForbiddenError, UnauthorizedError
from provider.auth.services import ProviderAuthService
from provider.container import Container

requestor_bearer = HTTPBearer(auto_error=False)
admin_bearer = HTTPBearer(auto_error=False)


@inject
async def require_requestor_vm_access(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(requestor_bearer),
    auth_service: ProviderAuthService = Depends(
        Provide[Container.provider_auth_service]
    ),
) -> RequestorIdentity:
    if credentials is None:
        raise UnauthorizedError("requestor session token required")
    vm_id = request.path_params.get("requestor_name")
    try:
        identity = auth_service.validate_requestor_token(credentials.credentials)
    except UnauthorizedError:
        auth_service.validate_admin_token(credentials.credentials)
        if vm_id is None:
            raise
        return RequestorIdentity(
            requestor_address=await auth_service.resolve_vm_owner(str(vm_id)),
            vm_id=str(vm_id),
            token_id="provider-admin",
            expires_at=0,
            scope="provider",
            is_admin=True,
        )
    if vm_id is not None:
        return await auth_service.require_vm_access(identity, str(vm_id))
    return identity


@inject
async def require_provider_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(admin_bearer),
    auth_service: ProviderAuthService = Depends(
        Provide[Container.provider_auth_service]
    ),
) -> AdminIdentity:
    if credentials is None:
        raise UnauthorizedError("provider admin token required")
    return auth_service.validate_admin_token(credentials.credentials)


async def require_matching_vm_id(identity: RequestorIdentity, vm_id: str) -> None:
    if identity.scope == "vm" and identity.vm_id != vm_id:
        raise ForbiddenError("requestor session is scoped to a different VM")
