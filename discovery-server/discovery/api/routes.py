from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime

from ..db.session import get_db
from ..db.repository import AdvertisementRepository
from .models import (
    AdvertisementCreate,
    AdvertisementResponse,
    ResourceRequirements,
    ErrorResponse
)

router = APIRouter(prefix="/api/v1")

async def get_repository(session: AsyncSession = Depends(get_db)) -> AdvertisementRepository:
    """Dependency for getting the advertisement repository."""
    return AdvertisementRepository(session)

async def verify_provider_headers(
    x_provider_id: str = Header(...),
    x_provider_signature: str = Header(...)
) -> str:
    """Verify provider headers and return provider ID."""
    # TODO: Implement proper signature verification
    if not x_provider_id or not x_provider_signature:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "AUTH_003",
                "message": "Missing provider credentials"
            }
        )
    return x_provider_id

@router.post(
    "/advertisements",
    response_model=AdvertisementResponse,
    responses={
        401: {"model": ErrorResponse},
        400: {"model": ErrorResponse}
    }
)
async def create_advertisement(
    advertisement: AdvertisementCreate,
    provider_id: str = Depends(verify_provider_headers),
    repo: AdvertisementRepository = Depends(get_repository)
) -> AdvertisementResponse:
    """Create or update a provider advertisement."""
    try:
        db_advertisement = await repo.upsert_advertisement(
            provider_id=provider_id,
            ip_address=advertisement.ip_address,
            country=advertisement.country,
            resources=advertisement.resources
        )
        return db_advertisement
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ADV_001",
                "message": f"Failed to create advertisement: {str(e)}"
            }
        )

@router.get(
    "/advertisements",
    response_model=List[AdvertisementResponse],
    responses={
        400: {"model": ErrorResponse}
    }
)
async def list_advertisements(
    cpu: Optional[int] = None,
    memory: Optional[int] = None,
    storage: Optional[int] = None,
    country: Optional[str] = None,
    repo: AdvertisementRepository = Depends(get_repository)
) -> List[AdvertisementResponse]:
    """List all active advertisements matching the criteria."""
    try:
        # Validate requirements if provided
        if any(v is not None and v < 1 for v in [cpu, memory, storage]):
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "ADV_002",
                    "message": "Resource requirements must be >= 1"
                }
            )

        advertisements = await repo.find_by_requirements(
            cpu=cpu,
            memory=memory,
            storage=storage,
            country=country
        )
        return advertisements
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ADV_003",
                "message": f"Failed to list advertisements: {str(e)}"
            }
        )

@router.get(
    "/advertisements/{provider_id}",
    response_model=AdvertisementResponse,
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse}
    }
)
async def get_advertisement(
    provider_id: str,
    repo: AdvertisementRepository = Depends(get_repository)
) -> AdvertisementResponse:
    """Get a specific advertisement by provider ID."""
    advertisement = await repo.get_by_id(provider_id)
    if not advertisement:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "ADV_004",
                "message": "Advertisement not found"
            }
        )
    return advertisement

@router.delete(
    "/advertisements/{provider_id}",
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse}
    }
)
async def delete_advertisement(
    provider_id: str,
    current_provider: str = Depends(verify_provider_headers),
    repo: AdvertisementRepository = Depends(get_repository)
) -> dict:
    """Delete an advertisement."""
    # Verify provider owns the advertisement
    if provider_id != current_provider:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "AUTH_004",
                "message": "Not authorized to delete this advertisement"
            }
        )

    deleted = await repo.delete(provider_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "ADV_004",
                "message": "Advertisement not found"
            }
        )
    
    return {"status": "success"}
