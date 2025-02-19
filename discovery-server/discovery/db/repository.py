from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.dialects.sqlite import insert
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from .models import Advertisement

class AdvertisementRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_advertisement(
        self,
        provider_id: str,
        ip_address: str,
        country: str,
        resources: Dict[str, Any]
    ) -> Advertisement:
        """Create or update a provider advertisement."""
        stmt = insert(Advertisement).values(
            provider_id=provider_id,
            ip_address=ip_address,
            country=country,
            resources=resources,
            updated_at=datetime.utcnow()
        )
        
        # Handle upsert for SQLite
        stmt = stmt.on_conflict_do_update(
            index_elements=['provider_id'],
            set_={
                'ip_address': stmt.excluded.ip_address,
                'country': stmt.excluded.country,
                'resources': stmt.excluded.resources,
                'updated_at': stmt.excluded.updated_at
            }
        )
        
        await self.session.execute(stmt)
        await self.session.commit()
        
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
        country: Optional[str] = None
    ) -> List[Advertisement]:
        """Find providers matching resource requirements."""
        query = select(Advertisement)
        
        # Add resource requirements
        if cpu is not None:
            query = query.where(Advertisement.resources['cpu'].as_integer() >= cpu)
        if memory is not None:
            query = query.where(Advertisement.resources['memory'].as_integer() >= memory)
        if storage is not None:
            query = query.where(Advertisement.resources['storage'].as_integer() >= storage)
            
        # Add country filter if specified
        if country is not None:
            query = query.where(Advertisement.country == country)
            
        # Only return non-expired advertisements
        five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
        query = query.where(Advertisement.updated_at >= five_minutes_ago)
        
        result = await self.session.execute(query)
        return result.scalars().all()

    async def cleanup_expired(self) -> int:
        """Remove expired advertisements (older than 5 minutes)."""
        five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
        stmt = delete(Advertisement).where(Advertisement.updated_at < five_minutes_ago)
        result = await self.session.execute(stmt)
        await self.session.commit()
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
        return result.rowcount > 0
