# -*- coding: utf-8 -*-
"""PostgreSQL access through a per-process connection pool.

The previous code opened a fresh connection for every query and left it open
whenever a request failed part-way, which exhausted Postgres
("sorry, too many clients already") during month-end traffic. Every use now
goes through `cursor()`, which always returns the connection to the pool.
"""
import os
import logging
import threading
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool

log = logging.getLogger("sewasetu.db")

_pool = None
_pool_lock = threading.Lock()
MIGRATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "migrations")


class DatabaseBusy(RuntimeError):
    """No database connection could be obtained right now."""


def init_pool(settings):
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = pool.ThreadedConnectionPool(
                1, settings.db_pool_max,
                host=settings.db_host, port=settings.db_port,
                dbname=settings.db_name, user=settings.db_user,
                password=settings.db_password, connect_timeout=5)
    return _pool


@contextmanager
def connection():
    if _pool is None:
        raise DatabaseBusy("database pool is not initialised")
    try:
        conn = _pool.getconn()
    except pool.PoolError as exc:
        raise DatabaseBusy(str(exc))
    broken = False
    try:
        if conn.closed:
            broken = True
            raise DatabaseBusy("stale database connection")
        yield conn
        conn.commit()
    except Exception:
        if not conn.closed:
            conn.rollback()
        raise
    finally:
        _pool.putconn(conn, close=broken or bool(conn.closed))


@contextmanager
def cursor():
    with connection() as conn:
        cur = conn.cursor()
        try:
            yield cur
        finally:
            cur.close()


def ensure_schema():
    """Apply idempotent migrations (indexes, OTP attempt counter).

    Runs under an advisory lock so concurrent gunicorn workers do not race.
    Each statement is applied on its own; a failing statement is logged and
    does not stop the rest.
    """
    with connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT pg_advisory_lock(727001)")
        try:
            for name in sorted(os.listdir(MIGRATIONS_DIR)):
                if not name.endswith(".sql"):
                    continue
                with open(os.path.join(MIGRATIONS_DIR, name), encoding="utf-8") as fh:
                    statements = [s.strip() for s in fh.read().split(";") if s.strip()
                                  and not all(line.strip().startswith("--")
                                              for line in s.strip().splitlines())]
                for stmt in statements:
                    try:
                        cur.execute(stmt)
                        conn.commit()
                    except psycopg2.Error as exc:
                        conn.rollback()
                        log.error("migration %s statement failed: %s", name, exc)
        finally:
            cur.execute("SELECT pg_advisory_unlock(727001)")
            conn.commit()
            cur.close()


# Exposed so route modules can catch UniqueViolation without importing psycopg2.
from psycopg2 import errors as psycopg2_errors  # noqa: E402
