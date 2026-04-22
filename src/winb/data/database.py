"""SQLAlchemy engine / session factory.

The engine is built from the ``DATABASE_URL`` environment variable. Inside the
Docker compose stack this resolves to ``postgresql+psycopg2://…@db:5432/winb``.

Usage:
    from winb.data.database import get_engine, session_scope

    with session_scope() as session:
        session.add(Team(...))
        # commit on exit; rollback on exception
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import cast

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def get_database_url() -> str:
    """Return DATABASE_URL from environment or raise."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set; expected postgresql+psycopg2://user:pass@host:port/db"
        )
    return url


def get_engine(echo: bool = False) -> Engine:
    """Return (and memoize) the module-level SQLAlchemy Engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_database_url(),
            echo=echo,
            pool_pre_ping=True,
            future=True,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )
    return _SessionFactory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Yield a session that commits on clean exit and rolls back on error."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_for_testing(url: str | None = None) -> Engine:
    """Rebind the module-level engine / session factory to ``url``.

    Intended only for tests (e.g. an in-memory SQLite). Production callers
    should not touch this.
    """
    global _engine, _SessionFactory
    _engine = create_engine(url or get_database_url(), future=True)
    _SessionFactory = sessionmaker(
        bind=_engine, autoflush=False, expire_on_commit=False, future=True
    )
    return cast(Engine, _engine)
