from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import Settings
from .errors import (
    BadGatewayError,
    ConfigurationError,
    DependencyUnavailableError,
    DomainError,
    ForbiddenError,
    GatewayTimeoutError,
    NotFoundError,
    PayloadTooLargeError,
    ValidationError,
)
from .ports.api import router as ports_router
from .proxy.api import router as proxy_router


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings()
    app = FastAPI(title="Golem Port Checker", openapi_url="/openapi.json")
    app.state.settings = app_settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _register_exception_handlers(app)
    app.include_router(ports_router)
    app.include_router(proxy_router)
    return app


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ForbiddenError)
    async def forbidden_exception_handler(request: Request, exc: ForbiddenError):
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(NotFoundError)
    async def not_found_exception_handler(request: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(PayloadTooLargeError)
    async def payload_too_large_exception_handler(
        request: Request, exc: PayloadTooLargeError
    ):
        return JSONResponse(status_code=413, content={"detail": str(exc)})

    @app.exception_handler(GatewayTimeoutError)
    async def gateway_timeout_exception_handler(
        request: Request, exc: GatewayTimeoutError
    ):
        return JSONResponse(status_code=504, content={"detail": str(exc)})

    @app.exception_handler(BadGatewayError)
    async def bad_gateway_exception_handler(request: Request, exc: BadGatewayError):
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(DependencyUnavailableError)
    async def dependency_unavailable_exception_handler(
        request: Request, exc: DependencyUnavailableError
    ):
        return JSONResponse(status_code=501, content={"detail": str(exc)})

    @app.exception_handler(ConfigurationError)
    async def configuration_exception_handler(
        request: Request, exc: ConfigurationError
    ):
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.exception_handler(DomainError)
    async def domain_exception_handler(request: Request, exc: DomainError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})
