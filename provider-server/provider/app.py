import logging
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from .api import routes
from .auth.dependencies import require_provider_admin
from .auth.errors import ForbiddenError, UnauthorizedError
from .container import Container
from .errors import (
    ConflictError,
    DomainError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)
from .payments.errors import (
    PaymentsDisabledError,
    StreamLookupError,
    StreamNotFoundError,
)
from .vm.models import VMNotFoundError
from .vm.multipass_adapter import MultipassError

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    logger.info("Creating provider API app")
    app = FastAPI(
        title="VM on Golem Provider",
        openapi_url="/api/v1/openapi.json",
    )
    container = Container()
    app.container = container
    _configure_safe_defaults(container)
    _wire_container(container)
    _register_exception_handlers(app)
    _register_middleware(app)
    _register_lifecycle(app, container)
    _register_prometheus_route(app)
    app.include_router(routes.router, prefix="/api/v1")
    return app


def _register_prometheus_route(app: FastAPI) -> None:
    @app.get("/metrics")
    async def prometheus_metrics(_admin=Depends(require_provider_admin)):
        monitoring_service = app.container.monitoring_service()
        return PlainTextResponse(
            await monitoring_service.prometheus_metrics(),
            media_type="text/plain; version=0.0.4",
        )


def _wire_container(container: Container) -> None:
    container.wire(
        modules=[
            ".api.routes",
            ".auth.api",
            ".auth.dependencies",
            ".api.vm_routes",
            ".api.payments_routes",
            ".api.provider_routes",
            ".api.settings_routes",
            ".api.summary_routes",
            ".api.monitoring_routes",
            ".api.live_routes",
            ".api.admin_routes",
        ]
    )


def _configure_safe_defaults(container: Container) -> None:
    container.config.from_dict(
        {
            "VM_DATA_DIR": str(Path.home() / ".golem" / "provider" / "vms"),
            "PROXY_STATE_DIR": str(Path.home() / ".golem" / "provider" / "proxy"),
            "PORT_RANGE_START": 50800,
            "PORT_RANGE_END": 50900,
            "PORT": 7466,
            "SKIP_PORT_VERIFICATION": True,
            "OFFERED_CPU_CORES": 0,
            "OFFERED_MEMORY_GB": 0,
            "OFFERED_STORAGE_GB": 0,
            "PRICE_USD_PER_CORE_MONTH": 5.0,
            "PRICE_USD_PER_GB_RAM_MONTH": 2.0,
            "PRICE_USD_PER_GB_STORAGE_MONTH": 0.1,
            "PRICE_GLM_PER_CORE_MONTH": 0.0,
            "PRICE_GLM_PER_GB_RAM_MONTH": 0.0,
            "PRICE_GLM_PER_GB_STORAGE_MONTH": 0.0,
        }
    )


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(VMNotFoundError)
    async def vm_not_found_exception_handler(request: Request, exc: VMNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(NotFoundError)
    async def not_found_exception_handler(request: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(StreamNotFoundError)
    async def stream_not_found_exception_handler(
        request: Request, exc: StreamNotFoundError
    ):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(UnauthorizedError)
    async def unauthorized_exception_handler(request: Request, exc: UnauthorizedError):
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(ForbiddenError)
    async def forbidden_exception_handler(request: Request, exc: ForbiddenError):
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(PaymentsDisabledError)
    async def payments_disabled_exception_handler(
        request: Request, exc: PaymentsDisabledError
    ):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict_exception_handler(request: Request, exc: ConflictError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(StreamLookupError)
    async def stream_lookup_exception_handler(request: Request, exc: StreamLookupError):
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(ExternalServiceError)
    async def external_service_exception_handler(
        request: Request, exc: ExternalServiceError
    ):
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(MultipassError)
    async def multipass_exception_handler(request: Request, exc: MultipassError):
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(DomainError)
    async def domain_exception_handler(request: Request, exc: DomainError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.error(
            "Unhandled provider API exception",
            extra={"path": request.url.path},
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected error occurred"},
        )


def _register_middleware(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _register_lifecycle(app: FastAPI, container: Container) -> None:
    @app.on_event("startup")
    async def startup_event():
        from .config import settings

        logger.info("Provider API startup beginning")
        container.config.from_dict(settings.model_dump())
        logger.info("Provider settings loaded into container")
        provider_service = container.provider_service()
        await provider_service.setup(app)
        logger.info("Provider API startup complete")

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Provider API shutdown beginning")
        provider_service = container.provider_service()
        await provider_service.cleanup()
        logger.info("Provider API shutdown complete")


app = create_app()
