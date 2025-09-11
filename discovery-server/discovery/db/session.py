from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator
from pathlib import Path

from ..config import settings
from .models import Base

# Create database directory if it doesn't exist
Path(settings.DATABASE_DIR).mkdir(parents=True, exist_ok=True)

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    # SQLite specific configs
    connect_args={"check_same_thread": False}
)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
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
                if 'platform' not in cols:
                    await conn.exec_driver_sql("ALTER TABLE advertisements ADD COLUMN platform TEXT NULL")
        except Exception:
            # Do not fail startup if migration probing fails; better to continue
            pass

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
