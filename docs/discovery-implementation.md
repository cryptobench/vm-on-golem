# Discovery Service Implementation Guide

## Overview

The Discovery Service acts as a simple advertisement board for VM on Golem, responsible for:
1. Allowing providers to post their resource advertisements
2. Allowing requestors to discover available providers
3. Automatically expiring stale advertisements (after 5 minutes)

## Implementation Details

### 1. Core Service

```python
# src/discovery/service.py
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from datetime import datetime, timedelta
import asyncio

class DiscoveryService:
    def __init__(
        self,
        database_url: str,
        cleanup_interval: int = 60  # seconds
    ):
        self.engine = create_async_engine(database_url)
        self.cleanup_interval = cleanup_interval
        self.app = FastAPI(title="Golem Discovery Service")

    async def start(self) -> None:
        """Start the discovery service."""
        # Initialize database
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Start advertisement cleanup
        asyncio.create_task(self.cleanup_stale_advertisements())

    async def cleanup_stale_advertisements(self) -> None:
        """Remove advertisements older than 5 minutes."""
        while True:
            try:
                async with AsyncSession(self.engine) as session:
                    cutoff_time = datetime.utcnow() - timedelta(minutes=5)
                    await session.execute(
                        delete(Advertisement)
                        .where(Advertisement.updated_at < cutoff_time)
                    )
                    await session.commit()
            except Exception as e:
                logging.error(f"Advertisement cleanup failed: {e}")
            await asyncio.sleep(self.cleanup_interval)
```

### 2. Database Schema

```python
# src/discovery/database/models.py
from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Advertisement(Base):
    __tablename__ = 'advertisements'

    provider_id = Column(String, primary_key=True)
    ip_address = Column(String, nullable=False)
    resources = Column(JSON, nullable=False)  # CPU, memory, storage
    country = Column(String(2), nullable=False)  # ISO 3166-1 alpha-2
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
```

### 3. API Endpoints

```python
# src/discovery/api/routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime

router = APIRouter()

# Models
class AdvertisementPost(BaseModel):
    ip_address: str
    resources: dict
    country: str

class AdvertisementResponse(BaseModel):
    provider_id: str
    ip_address: str
    resources: dict
    country: str
    updated_at: datetime

# Provider Endpoints
@router.post("/api/v1/advertisements", response_model=AdvertisementResponse)
async def post_advertisement(
    ad: AdvertisementPost,
    provider_id: str = Depends(get_provider_id),
    session: AsyncSession = Depends(get_db)
):
    """Post or update a provider's advertisement."""
    advertisement = Advertisement(
        provider_id=provider_id,
        ip_address=ad.ip_address,
        resources=ad.resources,
        country=ad.country,
        updated_at=datetime.utcnow()
    )

    # Upsert advertisement
    await session.merge(advertisement)
    await session.commit()
    return advertisement

# Requestor Endpoints
@router.get("/api/v1/advertisements", response_model=List[AdvertisementResponse])
async def list_advertisements(
    cpu: Optional[int] = None,
    memory: Optional[int] = None,
    storage: Optional[int] = None,
    country: Optional[str] = None,
    session: AsyncSession = Depends(get_db)
):
    """List active advertisements matching criteria."""
    query = select(Advertisement)
    
    # Apply filters
    if cpu is not None:
        query = query.where(Advertisement.resources['cpu'].as_integer() >= cpu)
    if memory is not None:
        query = query.where(Advertisement.resources['memory'].as_integer() >= memory)
    if storage is not None:
        query = query.where(Advertisement.resources['storage'].as_integer() >= storage)
    if country is not None:
        query = query.where(Advertisement.country == country)

    # Only return non-expired advertisements
    five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
    query = query.where(Advertisement.updated_at >= five_minutes_ago)
    
    result = await session.execute(query)
    return result.scalars().all()
```

### 4. Provider Authentication

```python
# src/discovery/auth.py
from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader
from typing import Optional

X_PROVIDER_ID = APIKeyHeader(name="X-Provider-ID")
X_PROVIDER_SIGNATURE = APIKeyHeader(name="X-Provider-Signature")

async def verify_provider_signature(
    provider_id: str = Depends(X_PROVIDER_ID),
    signature: str = Depends(X_PROVIDER_SIGNATURE)
) -> str:
    """Verify provider's signature and return provider ID."""
    # Simple signature verification for now
    # In production, implement proper cryptographic signature verification
    if not provider_id or not signature:
        raise HTTPException(
            status_code=401,
            detail="Missing provider credentials"
        )
    return provider_id
```

### 5. Error Handling

```python
# src/discovery/errors.py
from fastapi import Request
from fastapi.responses import JSONResponse

class DiscoveryError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

@app.exception_handler(DiscoveryError)
async def discovery_error_handler(
    request: Request,
    error: DiscoveryError
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "code": error.code,
            "message": error.message
        }
    )
```

## Usage Examples

### 1. Provider Posting Advertisement

```bash
# Post advertisement
curl -X POST http://discovery.golem.network:9001/api/v1/advertisements \
  -H "X-Provider-ID: provider123" \
  -H "X-Provider-Signature: signature123" \
  -H "Content-Type: application/json" \
  -d '{
    "ip_address": "83.233.10.2",
    "resources": {
      "cpu": 4,
      "memory": 8,
      "storage": 100
    },
    "country": "SE"
  }'
```

### 2. Requestor Querying Providers

```bash
# Query providers with at least 2 CPU cores and 4GB memory
curl "http://discovery.golem.network:9001/api/v1/advertisements?cpu=2&memory=4"

# Query providers in Sweden
curl "http://discovery.golem.network:9001/api/v1/advertisements?country=SE"
```

## Database Indexes

```python
# Create indexes for efficient querying
Index('idx_advertisement_updated_at', Advertisement.updated_at)
Index('idx_advertisement_country', Advertisement.country)
```

## Security Considerations

1. **Provider Authentication**
   - Simple provider ID and signature for now
   - Can be enhanced with proper cryptographic signatures

2. **Rate Limiting**
   ```python
   from fastapi import Request
   from fastapi.middleware.throttling import ThrottlingMiddleware
   
   app.add_middleware(
       ThrottlingMiddleware,
       rate_limit=100,  # requests per minute
       rate_window=60   # window size in seconds
   )
   ```

3. **Input Validation**
   ```python
   class AdvertisementPost(BaseModel):
       ip_address: str = Field(..., regex=r'^(\d{1,3}\.){3}\d{1,3}$')
       resources: dict = Field(..., min_items=3)
       country: str = Field(..., min_length=2, max_length=2)
   
       @validator('resources')
       def validate_resources(cls, v):
           required = {'cpu', 'memory', 'storage'}
           if not all(k in v for k in required):
               raise ValueError('Missing required resources')
           return v
   ```

This simplified implementation focuses on the core functionality of the discovery service as an advertisement board, with automatic cleanup of stale advertisements after 5 minutes of inactivity.
