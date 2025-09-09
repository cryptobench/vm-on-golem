import os
import pytest
from datetime import datetime, timedelta


@pytest.mark.asyncio
async def test_repository_filters_and_cleanup():
    os.environ["GOLEM_DISCOVERY_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

    from discovery.db.session import AsyncSessionLocal, init_db
    from discovery.db.repository import AdvertisementRepository
    from discovery.db.models import Advertisement
    from sqlalchemy import update, select

    await init_db()

    async with AsyncSessionLocal() as session:
        repo = AdvertisementRepository(session)

        # Insert two providers
        await repo.upsert_advertisement(
            provider_id="PX",
            ip_address="10.0.0.1",
            country="US",
            resources={"cpu": 2, "memory": 4, "storage": 10},
        )
        await repo.upsert_advertisement(
            provider_id="PY",
            ip_address="10.0.0.2",
            country="SE",
            resources={"cpu": 4, "memory": 8, "storage": 20},
        )

        # Filters: cpu
        res = await repo.find_by_requirements(cpu=3)
        assert {r.provider_id for r in res} == {"PY"}

        # Filters: country
        res = await repo.find_by_requirements(country="US")
        assert {r.provider_id for r in res} == {"PX"}

        # get_by_id
        got = await repo.get_by_id("PX")
        assert got is not None and got.provider_id == "PX"

        # Mark PX as expired by setting updated_at far in the past
        await session.execute(
            update(Advertisement)
            .where(Advertisement.provider_id == "PX")
            .values(updated_at=datetime.utcnow() - timedelta(minutes=10))
        )
        await session.commit()

        # Cleanup removes expired PX
        removed = await repo.cleanup_expired()
        assert removed >= 1

        # Delete remaining PY
        deleted = await repo.delete("PY")
        assert deleted is True

        # Now both should be gone
        all_rows = (await session.execute(select(Advertisement))).scalars().all()
        assert all_rows == []

