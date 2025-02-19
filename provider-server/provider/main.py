import asyncio
import logging
import time
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn
from typing import Optional

from .config import settings
from .vm.multipass import MultipassProvider
from .discovery.advertiser import ResourceAdvertiser
from .api.routes import router, get_vm_provider
from .vm.models import VMProvider

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global provider instance
vm_provider: Optional[VMProvider] = None
resource_advertiser: Optional[ResourceAdvertiser] = None

# Create FastAPI app
logger.info("Creating FastAPI app...")
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json"
)
logger.info("FastAPI app created")

@app.on_event("startup")
async def startup_event():
    """Handle startup event."""
    try:
        # Initialize VM provider
        global vm_provider, resource_advertiser
        logger.info("Creating VM provider...")
        vm_provider = MultipassProvider(settings.MULTIPASS_PATH)
        logger.info("Initializing VM provider...")
        await vm_provider.initialize()  # Initialize the provider
        logger.info("VM provider initialized successfully")
        
        # Initialize and start resource advertiser
        logger.info("Creating resource advertiser...")
        resource_advertiser = ResourceAdvertiser(
            discovery_url=settings.DISCOVERY_URL,
            provider_id=settings.PROVIDER_ID,
            update_interval=settings.ADVERTISEMENT_INTERVAL
        )
        logger.info("Starting resource advertiser...")
        asyncio.create_task(resource_advertiser.start())
        logger.info("Resource advertiser started successfully")
        
        logger.info("Provider node initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize provider node: {e}")
        vm_provider = None  # Reset provider on failure
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Handle shutdown event."""
    try:
        if resource_advertiser:
            logger.info("Stopping resource advertiser...")
            await resource_advertiser.stop()
        if vm_provider:
            logger.info("Cleaning up VM provider...")
            await vm_provider.cleanup()  # Cleanup provider resources
        logger.info("Provider node shut down successfully")
    except Exception as e:
        logger.error(f"Failed to shut down provider node: {e}")

# Log app configuration
logger.info(f"Project Name: {settings.PROJECT_NAME}")
logger.info(f"API Prefix: {settings.API_V1_PREFIX}")
logger.info(f"Debug Mode: {settings.DEBUG}")
logger.info(f"Host: {settings.HOST}")
logger.info(f"Port: {settings.PORT}")
logger.info(f"Multipass Path: {settings.MULTIPASS_PATH}")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
class RateLimitMiddleware:
    def __init__(self, app):
        self.app = app
        self.requests = {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # Get client IP
        client_ip = scope.get("client")[0] if scope.get("client") else None
        if not client_ip:
            return await self.app(scope, receive, send)

        # Check rate limit
        current_time = time.time()
        if client_ip in self.requests:
            requests = [t for t in self.requests[client_ip] 
                       if current_time - t < 60]  # Last minute
            if len(requests) >= settings.RATE_LIMIT_PER_MINUTE:
                response = JSONResponse(
                    status_code=429,
                    content={
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": "Too many requests"
                    }
                )
                await response(scope, receive, send)
                return
            self.requests[client_ip] = requests + [current_time]
        else:
            self.requests[client_ip] = [current_time]

        await self.app(scope, receive, send)

# Add rate limiting
app.add_middleware(RateLimitMiddleware)

# Override get_vm_provider dependency
async def get_vm_provider_override() -> VMProvider:
    """Get the VM provider instance."""
    if vm_provider is None:
        raise RuntimeError("VM provider not initialized")
    return vm_provider

app.dependency_overrides[get_vm_provider] = get_vm_provider_override

# Include API routes
app.include_router(router)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.0"
    }

if __name__ == "__main__":
    uvicorn.run(
        "provider.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
