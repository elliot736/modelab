"""PostgreSQL connection pool and schema management."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from server.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS assignments (
    assignment_id TEXT PRIMARY KEY,
    flag_name     TEXT NOT NULL,
    variant_name  TEXT NOT NULL,
    user_id       TEXT NOT NULL,
    session_id    TEXT NOT NULL DEFAULT '',
    config_json   JSONB NOT NULL DEFAULT '{}',
    assigned_at   TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assignments_flag_variant
    ON assignments (flag_name, variant_name);
CREATE INDEX IF NOT EXISTS idx_assignments_flag_user
    ON assignments (flag_name, user_id);
CREATE INDEX IF NOT EXISTS idx_assignments_assigned_at
    ON assignments (assigned_at);

CREATE TABLE IF NOT EXISTS executions (
    assignment_id TEXT PRIMARY KEY REFERENCES assignments(assignment_id),
    latency_ms    DOUBLE PRECISION,
    input_tokens  INTEGER,
    output_tokens INTEGER,
    cost          DOUBLE PRECISION,
    error         TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}',
    recorded_at   TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    event_id      TEXT PRIMARY KEY,
    assignment_id TEXT NOT NULL REFERENCES assignments(assignment_id),
    event_type    TEXT NOT NULL,
    event_name    TEXT NOT NULL DEFAULT '',
    payload_json  JSONB NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_assignment
    ON events (assignment_id);
CREATE INDEX IF NOT EXISTS idx_events_assignment_type
    ON events (assignment_id, event_type);
"""

pool: ConnectionPool | None = None


def init_pool() -> None:
    """Initialize the PostgreSQL connection pool.

    Creates a pool with 2-10 connections using settings from config.
    """
    global pool
    pool = ConnectionPool(
        settings.DATABASE_URL,
        min_size=2,
        max_size=10,
        kwargs={"row_factory": dict_row},
    )


def close_pool() -> None:
    """Close the PostgreSQL connection pool and release all connections."""
    global pool
    if pool:
        pool.close()
        pool = None


def init_schema() -> None:
    """Create database tables and indexes if they don't exist.

    Executes the schema DDL stored in _SCHEMA. Idempotent due to
    IF NOT EXISTS clauses.
    """
    assert pool is not None
    with pool.connection() as conn:
        conn.execute(_SCHEMA)
        conn.commit()


@contextmanager
def get_conn() -> Generator[Any, None, None]:
    assert pool is not None
    with pool.connection() as conn:
        yield conn
