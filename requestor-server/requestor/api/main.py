import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from ..config import config
from ..container import Container
from ..errors import (
    ConflictError,
    DatabaseError,
    DomainError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)
from ..payments.monitor import RequestorStreamMonitor
from ..services.database_service import DatabaseService
from . import routes

logger = logging.getLogger(__name__)

# Global variable to hold the database service instance
db_service: DatabaseService = None
stream_monitor: RequestorStreamMonitor | None = None
container = Container()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_service, stream_monitor
    logger.info(f"Initializing DatabaseService with db_path: {config.db_path}")
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    db_service = DatabaseService(config.db_path)
    try:
        await db_service.init()
        app.container.vm_repo().init_schema()
        logger.info("DatabaseService initialized successfully.")
    except DatabaseError as e:
        logger.error(f"Failed to initialize database during startup: {e}")
        raise RuntimeError(f"Database initialization failed: {e}") from e
    stream_monitor = RequestorStreamMonitor(db_service)
    stream_monitor.start()
    yield
    logger.info("Shutting down API.")
    if stream_monitor:
        await stream_monitor.stop()
    shutdown = app.container.shutdown_resources()
    if shutdown is not None:
        await shutdown


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan, openapi_url="/api/v1/openapi.json")
    app.container = container
    container.wire(
        modules=[
            routes,
            routes.discovery_api,
            routes.vm_api,
            routes.payments_api,
            routes.wallet_api,
        ]
    )
    app.include_router(routes.router, prefix="/api/v1")

    @app.exception_handler(NotFoundError)
    async def not_found_exception_handler(request: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict_exception_handler(request: Request, exc: ConflictError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ExternalServiceError)
    async def external_exception_handler(request: Request, exc: ExternalServiceError):
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(DomainError)
    async def domain_exception_handler(request: Request, exc: DomainError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    return app


app = create_app()


@app.get("/vms")
async def list_vms():
    """
    Endpoint to list all virtual machines stored in the database.
    """
    if db_service is None:
        logger.error("Database service not initialized.")
        raise HTTPException(status_code=500, detail="Database service unavailable")

    try:
        vms = await db_service.list_vms()
        logger.info(f"Retrieved {len(vms)} VMs from database.")
        return vms
    except DatabaseError as e:
        logger.error(f"API Error fetching VMs: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve VM list: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected API error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")


# Example of another endpoint (can be removed if not needed)
@app.get("/")
async def read_root():
    return {"message": "Golem Requestor API"}
