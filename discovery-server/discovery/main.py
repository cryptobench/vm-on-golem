import asyncio
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Callable
import time

from .config import settings
from .api.routes import router
from .api.models import ErrorResponse
from .db.session import init_db, cleanup_db
from .db.repository import AdvertisementRepository
from .db.session import AsyncSessionLocal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
from starlette.middleware.base import BaseHTTPMiddleware

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = {}

    async def dispatch(self, request: Request, call_next: Callable):
        # Get client IP
        client_ip = request.client.host

        # Check rate limit
        current_time = time.time()
        if client_ip in self.requests:
            requests = [t for t in self.requests[client_ip] 
                       if current_time - t < 60]  # Last minute
            if len(requests) >= self.requests_per_minute:
                return JSONResponse(
                    status_code=429,
                    content=ErrorResponse(
                        code="RATE_001",
                        message="Rate limit exceeded"
                    ).dict()
                )
            self.requests[client_ip] = requests + [current_time]
        else:
            self.requests[client_ip] = [current_time]

        return await call_next(request)

# Add rate limiting
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=settings.RATE_LIMIT_PER_MINUTE
)

# Include API routes
app.include_router(router)  # Remove prefix as it's already set in the router

# Background task for cleaning up expired advertisements
async def cleanup_expired_advertisements():
    """Periodically remove expired advertisements."""
    while True:
        try:
            async with AsyncSessionLocal() as session:
                repo = AdvertisementRepository(session)
                removed = await repo.cleanup_expired()
                if removed > 0:
                    logger.info(f"Removed {removed} expired advertisements")
        except Exception as e:
            logger.error(f"Error cleaning up advertisements: {e}")
        
        await asyncio.sleep(settings.CLEANUP_INTERVAL_SECONDS)

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized")

        # Start cleanup task
        asyncio.create_task(cleanup_expired_advertisements())
        logger.info("Advertisement cleanup task started")
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    try:
        await cleanup_db()
        logger.info("Database connection closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

def start():
    """Entry point for the discovery service."""
    import uvicorn
    uvicorn.run(
        "discovery:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning"
    )

if __name__ == "__main__":
    start()
