from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from port_checker.config import Settings

from .direct_service import DirectProxyService
from .domain import DirectProxyCommand, ProviderProxyCommand, ProxyResponse
from .provider_service import ProviderProxyService

router = APIRouter()


def _client_host(request: Request) -> str:
    return request.client.host if request.client else ""


def _to_response(response: ProxyResponse) -> Response:
    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=response.headers,
    )


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_provider_proxy_service(
    settings: Settings = Depends(get_settings),
) -> ProviderProxyService:
    return ProviderProxyService(settings)


def get_direct_proxy_service(
    settings: Settings = Depends(get_settings),
) -> DirectProxyService:
    return DirectProxyService(settings)


@router.api_route(
    "/proxy/provider/{provider_id}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def http_proxy_provider(
    request: Request,
    provider_id: str,
    path: str,
    port: int = Query(default=80),
    x_proxy_source: Optional[str] = Header(default=None),
    x_proxy_token: Optional[str] = Header(default=None),
    x_proxy_arkiv_rpc: Optional[str] = Header(default=None),
    x_proxy_arkiv_ws: Optional[str] = Header(default=None),
    service: ProviderProxyService = Depends(get_provider_proxy_service),
) -> Response:
    result = await service.proxy(
        ProviderProxyCommand(
            method=request.method,
            provider_id=provider_id,
            path=path,
            query=request.url.query,
            headers=dict(request.headers),
            body=await request.body(),
            client_host=_client_host(request),
            port=port,
            source=x_proxy_source,
            token=x_proxy_token,
            arkiv_rpc_url=x_proxy_arkiv_rpc,
            arkiv_ws_url=x_proxy_arkiv_ws,
        )
    )
    return _to_response(result)


@router.api_route(
    "/proxy/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def http_proxy(
    request: Request,
    path: str,
    x_forward_to: Optional[str] = Header(default=None),
    x_forward_protocol: Optional[str] = Header(default=None),
    x_proxy_token: Optional[str] = Header(default=None),
    target: Optional[str] = Query(default=None),
    service: DirectProxyService = Depends(get_direct_proxy_service),
) -> Response:
    result = await service.proxy(
        DirectProxyCommand(
            method=request.method,
            path=path,
            query=request.url.query,
            headers=dict(request.headers),
            body=await request.body(),
            client_host=_client_host(request),
            forward_to=x_forward_to,
            protocol=x_forward_protocol,
            token=x_proxy_token,
            target=target,
        )
    )
    return _to_response(result)
