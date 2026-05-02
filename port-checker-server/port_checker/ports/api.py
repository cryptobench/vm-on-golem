from fastapi import APIRouter, Depends, Request

from port_checker.config import Settings

from .domain import HealthResponse, PortCheckRequest, PortCheckResponse
from .service import PortCheckService

router = APIRouter()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_port_check_service(
    settings: Settings = Depends(get_settings),
) -> PortCheckService:
    return PortCheckService(
        retries=settings.port_check_retries,
        retry_delay=settings.port_check_retry_delay,
        timeout=settings.port_check_timeout,
    )


@router.post("/check-ports", response_model=PortCheckResponse)
async def check_ports(
    request: PortCheckRequest,
    service: PortCheckService = Depends(get_port_check_service),
) -> PortCheckResponse:
    return await service.check_ports(request)


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok")
