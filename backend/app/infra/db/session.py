"""SQLite engine/session factory for optional persistence."""

from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

_SQLITE_FILE_PREFIX = "sqlite:///"


def _sqlite_file_path(database_url: str) -> Path | None:
    """The on-disk path a sqlite URL points at, or None for in-memory/non-sqlite URLs."""
    if not database_url.startswith(_SQLITE_FILE_PREFIX):
        return None
    raw_path = database_url[len(_SQLITE_FILE_PREFIX) :]
    if raw_path in ("", ":memory:"):
        return None
    return Path(raw_path)


def create_db_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine with SQLite-friendly defaults."""
    is_sqlite = database_url.startswith("sqlite")
    file_path = _sqlite_file_path(database_url)

    if is_sqlite and file_path is not None:
        file_path.parent.mkdir(parents=True, exist_ok=True)

    connect_args = {"check_same_thread": False} if is_sqlite else {}
    # In-memory SQLite is per-connection; pin it to a single shared connection
    # so every session in the process (and every test) sees the same tables.
    poolclass = StaticPool if is_sqlite and file_path is None else None

    kwargs = {"connect_args": connect_args}
    if poolclass is not None:
        kwargs["poolclass"] = poolclass

    return create_engine(database_url, **kwargs)


def create_db_and_tables(engine: Engine) -> None:
    """Create all SQLModel tables if they do not already exist."""
    # Import models so SQLModel.metadata is populated before create_all.
    from app.infra.db import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session(engine: Engine) -> Session:
    """Open a new SQLModel session bound to the given engine."""
    return Session(engine)
