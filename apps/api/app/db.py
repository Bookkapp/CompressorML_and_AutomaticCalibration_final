from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

from .config import get_settings


_engine: Engine | None = None
_source_engine: Engine | None = None


def get_engine() -> Engine | None:
    global _engine
    settings = get_settings()
    if settings.database_url is None:
        return None
    if _engine is None:
        _engine = create_engine(
            settings.database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=1800,
            future=True,
        )
    return _engine


def get_source_engine() -> Engine | None:
    global _source_engine
    settings = get_settings()
    if settings.source_database_url is None:
        return None
    if _source_engine is None:
        _source_engine = create_engine(
            settings.source_database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=1800,
            future=True,
        )
    return _source_engine


@contextmanager
def connection() -> Connection:
    engine = get_engine()
    if engine is None:
        raise RuntimeError("Analytics database credentials are not configured")
    with engine.begin() as conn:
        yield conn


@contextmanager
def source_connection() -> Connection:
    engine = get_source_engine()
    if engine is None:
        raise RuntimeError("Source telemetry MySQL credentials are not configured")
    with engine.connect() as conn:
        yield conn
