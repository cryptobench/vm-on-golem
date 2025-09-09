import logging
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

from ..services.database_service import DatabaseService
from ..config import config
from ..errors import DatabaseError
from ..payments.monitor import RequestorStreamMonitor

logger = logging.getLogger(__name__)

# Global variable to hold the database service instance
db_service: DatabaseService = None
stream_monitor: RequestorStreamMonitor | None = None

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
    # Start requestor stream monitor
    global stream_monitor
    stream_monitor = RequestorStreamMonitor(db_service)
    stream_monitor.start()
    yield
    # Shutdown: Cleanup (if needed)
    logger.info("Shutting down API.")
    if stream_monitor:
        await stream_monitor.stop()
    # No explicit cleanup needed for aiosqlite connection usually

app = FastAPI(lifespan=lifespan)

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
