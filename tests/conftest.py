"""Shared pytest fixtures for WinB tests."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session, sessionmaker

from winb.data import get_engine


@pytest.fixture
def session() -> Session:
    """Per-test session wrapped in a transaction that is rolled back after.

    Rolls back only if the transaction is still active — IntegrityError on
    flush() auto-deassociates the transaction, and calling rollback() on it
    again would emit a SAWarning.
    """
    engine = get_engine()
    connection = engine.connect()
    trans = connection.begin()
    Session_ = sessionmaker(bind=connection, future=True, expire_on_commit=False)
    s = Session_()
    try:
        yield s
    finally:
        s.close()
        if trans.is_active:
            trans.rollback()
        connection.close()
