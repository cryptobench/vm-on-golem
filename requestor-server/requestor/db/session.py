from pathlib import Path
from typing import Callable

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def make_sqlite_engine(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )


def make_session_factory(engine: Engine) -> Callable[[], Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
