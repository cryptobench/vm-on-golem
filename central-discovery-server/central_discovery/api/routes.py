import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.repository import AdvertisementRepository
from ..db.session import get_db
from .models import (
    AdvertisementCreate,
    AdvertisementResponse,
    DeleteAdvertisementResponse,
    ErrorResponse,
    ResourceRequirements,
)

router = APIRouter(prefix="/api/v1")
logger = logging.getLogger(__name__)


async def get_repository(
    session: AsyncSession = Depends(get_db),
) -> AdvertisementRepository:
    """Dependency for getting the advertisement repository."""
    return AdvertisementRepository(session)


async def verify_provider_headers(
    x_provider_id: str = Header(...), x_provider_signature: str = Header(...)
) -> str:
    """Verify provider headers and return provider ID."""
    # TODO: Implement proper signature verification
    if not x_provider_id or not x_provider_signature:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_003", "message": "Missing provider credentials"},
        )
    return x_provider_id


@router.post(
    "/advertisements",
    response_model=AdvertisementResponse,
    responses={401: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def create_advertisement(
    advertisement: AdvertisementCreate,
    provider_id: str = Depends(verify_provider_headers),
    repo: AdvertisementRepository = Depends(get_repository),
) -> AdvertisementResponse:
    """Create or update a provider advertisement."""
    try:
        db_advertisement = await repo.upsert_advertisement(
            provider_id=provider_id,
            ip_address=advertisement.ip_address,
            country=advertisement.country,
            resources=advertisement.resources,
            pricing=advertisement.pricing,
            platform=advertisement.platform,
            endpoint_protocol=advertisement.endpoint_protocol,
            endpoint_host=advertisement.endpoint_host,
            endpoint_port=advertisement.endpoint_port,
            endpoint_url=advertisement.endpoint_url,
        )
        resources = advertisement.resources
        logger.info(
            "Advertisement upserted",
            extra={
                "provider_id": provider_id,
                "endpoint_host": advertisement.endpoint_host,
                "endpoint_port": advertisement.endpoint_port,
                "country": advertisement.country,
                "platform": advertisement.platform,
                "cpu": resources.get("cpu"),
                "memory": resources.get("memory"),
                "storage": resources.get("storage"),
            },
        )
        return db_advertisement
    except Exception as e:
        logger.error(
            "Failed to create advertisement",
            extra={"provider_id": provider_id},
            exc_info=True,
        )
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ADV_001",
                "message": f"Failed to create advertisement: {str(e)}",
            },
        )


@router.get(
    "/advertisements",
    response_model=List[AdvertisementResponse],
    responses={400: {"model": ErrorResponse}},
)
async def list_advertisements(
    cpu: Optional[int] = None,
    memory: Optional[int] = None,
    storage: Optional[int] = None,
    country: Optional[str] = None,
    platform: Optional[str] = None,
    repo: AdvertisementRepository = Depends(get_repository),
) -> List[AdvertisementResponse]:
    """List all active advertisements matching the criteria."""
    try:
        # Validate requirements if provided
        if any(v is not None and v < 1 for v in [cpu, memory, storage]):
            logger.warning(
                "Invalid advertisement resource filter",
                extra={"cpu": cpu, "memory": memory, "storage": storage},
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "ADV_002",
                    "message": "Resource requirements must be >= 1",
                },
            )

        advertisements = await repo.find_by_requirements(
            cpu=cpu,
            memory=memory,
            storage=storage,
            country=country,
            platform=platform,
        )
        logger.debug(
            "Advertisement list query completed",
            extra={
                "cpu": cpu,
                "memory": memory,
                "storage": storage,
                "country": country,
                "platform": platform,
                "result_count": len(advertisements),
            },
        )
        return advertisements
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list advertisements", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ADV_003",
                "message": f"Failed to list advertisements: {str(e)}",
            },
        )


@router.get(
    "/advertisements/{provider_id}",
    response_model=AdvertisementResponse,
    responses={404: {"model": ErrorResponse}, 400: {"model": ErrorResponse}},
)
async def get_advertisement(
    provider_id: str, repo: AdvertisementRepository = Depends(get_repository)
) -> AdvertisementResponse:
    """Get a specific advertisement by provider ID."""
    advertisement = await repo.get_by_id(provider_id)
    if not advertisement:
        raise HTTPException(
            status_code=404,
            detail={"code": "ADV_004", "message": "Advertisement not found"},
        )
    return advertisement


@router.delete(
    "/advertisements/{provider_id}",
    response_model=DeleteAdvertisementResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def delete_advertisement(
    provider_id: str,
    current_provider: str = Depends(verify_provider_headers),
    repo: AdvertisementRepository = Depends(get_repository),
) -> DeleteAdvertisementResponse:
    """Delete an advertisement."""
    # Verify provider owns the advertisement
    if provider_id != current_provider:
        logger.warning(
            "Unauthorized advertisement delete attempt",
            extra={"provider_id": provider_id, "current_provider": current_provider},
        )
        raise HTTPException(
            status_code=401,
            detail={
                "code": "AUTH_004",
                "message": "Not authorized to delete this advertisement",
            },
        )

    deleted = await repo.delete(provider_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={"code": "ADV_004", "message": "Advertisement not found"},
        )

    logger.info("Advertisement deleted", extra={"provider_id": provider_id})
    return DeleteAdvertisementResponse(status="success")
