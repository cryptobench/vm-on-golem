import logging
import time
from typing import Callable

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .domain import HealthResponse
from .api.routes import router
from .config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_PREFIX}/openapi.json"
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
class RateLimitMiddleware:
    def __init__(self, app, requests_per_minute: int = 100):
        self.app = app
        self.requests_per_minute = requests_per_minute
        self.requests = {}

    async def __call__(self, scope, receive: Callable, send: Callable):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Get client IP
        client = scope.get("client")
        client_ip = client[0] if client else "unknown"

        # Check rate limit
        current_time = time.time()
        if client_ip in self.requests:
            requests = [
                t for t in self.requests[client_ip] if current_time - t < 60
            ]  # Last minute
            if len(requests) >= self.requests_per_minute:
                logger.warning(
                    "Rate limit exceeded",
                    extra={
                        "client_ip": client_ip,
                        "requests_per_minute": self.requests_per_minute,
                    },
                )
                response = JSONResponse(
                    status_code=429,
                    content=jsonable_encoder({"detail": "Rate limit exceeded"}),
                )
                await response(scope, receive, send)
                return
            self.requests[client_ip] = requests + [current_time]
        else:
            self.requests[client_ip] = [current_time]

        await self.app(scope, receive, send)


# Add rate limiting
app.add_middleware(
    RateLimitMiddleware, requests_per_minute=settings.RATE_LIMIT_PER_MINUTE
)

# Include websocket API routes
app.include_router(router, prefix=settings.API_V1_PREFIX)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info("Starting central discovery service")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    logger.info("Shutting down central discovery service")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy")


def start():
    """Entry point for the central discovery service."""
    import uvicorn

    uvicorn.run(
        "central_discovery:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning",
    )


if __name__ == "__main__":
    start()
