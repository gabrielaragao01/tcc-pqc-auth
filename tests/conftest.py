from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from collections.abc import Generator

import pytest

from src.config import settings
from src.db import database
from src.db.database import _CREATE_USERS_TABLE


@pytest.fixture
def memory_db(monkeypatch: pytest.MonkeyPatch) -> Generator[sqlite3.Connection, None, None]:
    """Provide an isolated in-memory SQLite database for tests.

    SQLite :memory: databases are per-connection. This fixture creates a single
    shared connection, patches get_connection() to always yield it, and
    initialises the schema — so init_db() and UserRepository share the same DB.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    @contextmanager
    def _shared_conn() -> Generator[sqlite3.Connection, None, None]:
        try:
            yield conn
        finally:
            pass  # fixture owns the lifetime; do not close here

    # Patch at both the database module and the repository module
    # (in case get_connection is already imported before patching)
    monkeypatch.setattr(database, "get_connection", _shared_conn)
    monkeypatch.setattr(settings, "database_path", ":memory:")

    # Patch in repository module as well to handle already-imported references
    from src.db import repository
    monkeypatch.setattr(repository, "get_connection", _shared_conn)

    # Create schema in the shared connection directly
    conn.execute(_CREATE_USERS_TABLE)
    conn.commit()

    yield conn

    conn.close()
