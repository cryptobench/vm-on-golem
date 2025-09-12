import os
import sqlite3
import importlib
import pytest


@pytest.mark.asyncio
async def test_init_db_adds_missing_platform_column(tmp_path, monkeypatch):
    # Point discovery to a real sqlite file we control
    db_path = tmp_path / "discovery.sqlite"
    os.environ["GOLEM_DISCOVERY_DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"

    # Pre-create an 'advertisements' table WITHOUT the 'platform' column
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE advertisements (
            provider_id TEXT PRIMARY KEY,
            ip_address TEXT NOT NULL,
            country TEXT NOT NULL,
            resources TEXT NOT NULL,
            pricing TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()

    # Patch session module to use an engine bound to this DB file
    import discovery.db.session as sess
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    monkeypatch.setattr(sess, "engine", engine, raising=False)
    monkeypatch.setattr(
        sess,
        "AsyncSessionLocal",
        sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False),
        raising=False,
    )

    # Run init_db which should detect the missing 'platform' and ALTER the table
    await sess.init_db()

    # Verify the column exists now
    conn2 = sqlite3.connect(db_path)
    cols = [row[1] for row in conn2.execute("PRAGMA table_info(advertisements)").fetchall()]
    conn2.close()
    assert "platform" in cols


@pytest.mark.asyncio
async def test_init_db_swallows_migration_probe_errors(monkeypatch):
    # Import the session module
    import discovery.db.session as sess

    class FakeConn:
        async def run_sync(self, fn):
            # Simulate create_all succeeding (no-op)
            return None

        async def exec_driver_sql(self, sql):
            # Force an error inside the migration probing block
            raise RuntimeError("boom")

    class FakeBegin:
        async def __aenter__(self):
            return FakeConn()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeEngine:
        # Ensure code path treats this as sqlite
        url = "sqlite+aiosqlite:///fake.db"

        def begin(self):
            return FakeBegin()

    # Patch the engine used by init_db
    monkeypatch.setattr(sess, "engine", FakeEngine(), raising=False)

    # Should complete without raising despite the internal error
    await sess.init_db()
