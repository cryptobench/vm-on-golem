import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from central_discovery.time import utc_now

from .models import Advertisement

logger = logging.getLogger(__name__)


class AdvertisementRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_advertisement(
        self,
        provider_id: str,
        ip_address: str,
        country: str,
        resources: Dict[str, Any],
        pricing: Optional[Dict[str, Any]] = None,
        platform: Optional[str] = None,
        endpoint_protocol: Optional[str] = None,
        endpoint_host: Optional[str] = None,
        endpoint_port: Optional[int] = None,
        endpoint_url: Optional[str] = None,
    ) -> Advertisement:
        """Create or update a provider advertisement."""
        stmt = insert(Advertisement).values(
            provider_id=provider_id,
            ip_address=ip_address,
            country=country,
            platform=platform,
            endpoint_protocol=endpoint_protocol,
            endpoint_host=endpoint_host,
            endpoint_port=endpoint_port,
            endpoint_url=endpoint_url,
            resources=resources,
            pricing=pricing,
            updated_at=utc_now(),
        )

        # Handle upsert for SQLite
        stmt = stmt.on_conflict_do_update(
            index_elements=["provider_id"],
            set_={
                "ip_address": stmt.excluded.ip_address,
                "country": stmt.excluded.country,
                "platform": stmt.excluded.platform,
                "endpoint_protocol": stmt.excluded.endpoint_protocol,
                "endpoint_host": stmt.excluded.endpoint_host,
                "endpoint_port": stmt.excluded.endpoint_port,
                "endpoint_url": stmt.excluded.endpoint_url,
                "resources": stmt.excluded.resources,
                "pricing": stmt.excluded.pricing,
                "updated_at": stmt.excluded.updated_at,
            },
        )

        await self.session.execute(stmt)
        await self.session.commit()
        logger.debug(
            "Advertisement upsert committed", extra={"provider_id": provider_id}
        )

        # Fetch and return the updated advertisement
        result = await self.session.execute(
            select(Advertisement).where(Advertisement.provider_id == provider_id)
        )
        return result.scalar_one()

    async def find_by_requirements(
        self,
        cpu: Optional[int] = None,
        memory: Optional[int] = None,
        storage: Optional[int] = None,
        country: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> List[Advertisement]:
        """Find providers matching resource requirements."""
        query = select(Advertisement)

        # Add resource requirements
        if cpu is not None:
            query = query.where(Advertisement.resources["cpu"].as_integer() >= cpu)
        if memory is not None:
            query = query.where(
                Advertisement.resources["memory"].as_integer() >= memory
            )
        if storage is not None:
            query = query.where(
                Advertisement.resources["storage"].as_integer() >= storage
            )

        # Add country filter if specified
        if country is not None:
            query = query.where(Advertisement.country == country)
        if platform is not None:
            query = query.where(Advertisement.platform == platform)

        # Only return non-expired advertisements
        five_minutes_ago = utc_now() - timedelta(minutes=5)
        query = query.where(Advertisement.updated_at >= five_minutes_ago)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def cleanup_expired(self) -> int:
        """Remove expired advertisements (older than 5 minutes)."""
        five_minutes_ago = utc_now() - timedelta(minutes=5)
        stmt = delete(Advertisement).where(Advertisement.updated_at < five_minutes_ago)
        result = await self.session.execute(stmt)
        await self.session.commit()
        logger.debug(
            "Expired advertisement cleanup committed",
            extra={"removed_count": result.rowcount},
        )
        return result.rowcount

    async def get_by_id(self, provider_id: str) -> Optional[Advertisement]:
        """Get advertisement by provider ID."""
        result = await self.session.execute(
            select(Advertisement).where(Advertisement.provider_id == provider_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, provider_id: str) -> bool:
        """Delete an advertisement."""
        result = await self.session.execute(
            delete(Advertisement).where(Advertisement.provider_id == provider_id)
        )
        await self.session.commit()
        logger.debug(
            "Advertisement delete committed",
            extra={"provider_id": provider_id, "deleted": result.rowcount > 0},
        )
        return result.rowcount > 0
