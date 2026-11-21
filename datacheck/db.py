"""SQLite engine, connection helpers and schema bootstrap."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

from .config import BASE_DIR, DATABASE_URL

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

_engine: Engine | None = None


def _configure_sqlite(dbapi_connection, _connection_record) -> None:
    """Foreign keys are off by default in SQLite; the schema relies on them."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA busy_timeout = 5000")
        cursor.close()


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = DATABASE_URL
        if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
            target = Path(url.replace("sqlite:///", "", 1))
            if not target.is_absolute():
                target = BASE_DIR / target
            target.parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{target}"
        _engine = create_engine(
            url,
            future=True,
            connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
        )
        if url.startswith("sqlite"):
            event.listen(_engine, "connect", _configure_sqlite)
        logger.info("datacheck: engine bound to %s", url)
    return _engine


def init_db() -> None:
    """Create the schema if it does not exist yet (idempotent)."""
    engine = get_engine()
    statements = [stmt.strip() for stmt in SCHEMA_PATH.read_text().split(";")]
    with engine.begin() as conn:
        for statement in statements:
            if not statement:
                continue
            # Skip bare PRAGMA statements that SQLAlchemy cannot wrap in a transaction.
            if statement.upper().startswith("PRAGMA"):
                continue
            conn.execute(text(statement))


class _TextConnection:
    """Thin wrapper that accepts plain SQL strings (SQLAlchemy 2 needs text())."""

    def __init__(self, connection) -> None:
        self._connection = connection

    def execute(self, statement, params=None):
        if isinstance(statement, str):
            statement = text(statement)
        return self._connection.execute(statement, params if params is not None else {})

    def __getattr__(self, item):
        return getattr(self._connection, item)


@contextmanager
def connect() -> Iterator[_TextConnection]:
    """Yield a connection inside an explicit transaction (commit on success)."""
    engine = get_engine()
    with engine.begin() as connection:
        yield _TextConnection(connection)


def fetch_all(sql: str, params: dict | None = None) -> list[dict]:
    with get_engine().connect() as conn:
        result = conn.execute(text(sql), params or {})
        return [dict(row._mapping) for row in result]


def fetch_one(sql: str, params: dict | None = None) -> dict | None:
    rows = fetch_all(sql, params)
    return rows[0] if rows else None
