import logging
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from ..services.database_service import DatabaseService
from ..config import config
from ..errors import DatabaseError

logger = logging.getLogger(__name__)

# Global variable to hold the database service instance
db_service: DatabaseService = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database service
    global db_service
    logger.info(f"Initializing DatabaseService with db_path: {config.db_path}")
    # Ensure parent directory exists
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    db_service = DatabaseService(config.db_path)
    try:
        await db_service.init()
        logger.info("DatabaseService initialized successfully.")
    except DatabaseError as e:
        logger.error(f"Failed to initialize database during startup: {e}")
        # Depending on requirements, you might want to prevent the app from starting
        # raise RuntimeError(f"Database initialization failed: {e}") from e
    yield
    # Shutdown: Cleanup (if needed)
    logger.info("Shutting down API.")
    # No explicit cleanup needed for aiosqlite connection usually

app = FastAPI(lifespan=lifespan)
# Standardized Error Response Model
class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[str] = None

class StandardErrorResponse(BaseModel):
    error: ErrorResponse


# Custom Exception Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    error_code = f"HTTP_{exc.status_code}"
    error_message = exc.detail
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": error_code,
                "message": error_message,
                "details": None  # HTTPException detail is usually user-friendly enough
            }
        },
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    # Use config.debug for showing details, assuming it exists
    show_details = getattr(config, 'debug', False)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred on the server.",
                "details": str(exc) if show_details else None
            }
        },
    )

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
        raise HTTPException(status_code=500, detail=f"Failed to retrieve VM list: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected API error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An unexpected error occurred")

# Example of another endpoint (can be removed if not needed)
@app.get("/")
async def read_root():
    return {"message": "Golem Requestor API"}
