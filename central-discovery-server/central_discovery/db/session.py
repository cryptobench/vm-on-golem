import logging
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from ..config import settings
from .models import Base

logger = logging.getLogger(__name__)

# Create database directory if it doesn't exist
Path(settings.DATABASE_DIR).mkdir(parents=True, exist_ok=True)

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    # SQLite specific configs
    connect_args={"check_same_thread": False},
)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db():
    """Initialize database tables and apply lightweight migrations."""
    async with engine.begin() as conn:
        # Create tables if not exist
        await conn.run_sync(Base.metadata.create_all)

        # Lightweight migrations for SQLite: add missing columns
        try:
            url = str(engine.url)
            if url.startswith("sqlite"):
                # Ensure 'platform' column exists on 'advertisements'
                res = await conn.exec_driver_sql("PRAGMA table_info(advertisements)")
                cols = [row[1] for row in res.fetchall()]  # second field is name
                migrations = {
                    "platform": "ALTER TABLE advertisements ADD COLUMN platform TEXT NULL",
                    "endpoint_protocol": "ALTER TABLE advertisements ADD COLUMN endpoint_protocol TEXT NULL",
                    "endpoint_host": "ALTER TABLE advertisements ADD COLUMN endpoint_host TEXT NULL",
                    "endpoint_port": "ALTER TABLE advertisements ADD COLUMN endpoint_port INTEGER NULL",
                    "endpoint_url": "ALTER TABLE advertisements ADD COLUMN endpoint_url TEXT NULL",
                }
                for column, statement in migrations.items():
                    if column not in cols:
                        await conn.exec_driver_sql(statement)
        except Exception:
            logger.exception("Failed to apply central discovery database migrations")
            raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def cleanup_db():
    """Cleanup database connection."""
    await engine.dispose()
