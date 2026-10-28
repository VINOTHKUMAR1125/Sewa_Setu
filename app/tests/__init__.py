# -*- coding: utf-8 -*-
"""Make the suite runnable without a database or the PDF library installed.

When psycopg2 / fpdf are missing (e.g. a laptop without the Docker image), tiny
stand-ins are registered so the application code can be imported. In the Docker
image the real libraries are used.
"""
import os
import sys
import types

os.environ.setdefault("DB_PASSWORD", "test-db-password")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("LOG_DIR", "/tmp/sewasetu-test-logs")

try:
    import psycopg2  # noqa: F401
except ImportError:
    pg = types.ModuleType("psycopg2")
    pool = types.ModuleType("psycopg2.pool")
    errors = types.ModuleType("psycopg2.errors")

    class Error(Exception):
        pass

    class PoolError(Error):
        pass

    class UniqueViolation(Error):
        pass

    pg.Error, pool.PoolError, errors.UniqueViolation = Error, PoolError, UniqueViolation
    pool.ThreadedConnectionPool = object
    pg.pool, pg.errors = pool, errors
    sys.modules.update({"psycopg2": pg, "psycopg2.pool": pool, "psycopg2.errors": errors})

try:
    import fpdf  # noqa: F401
except ImportError:
    fp = types.ModuleType("fpdf")
    fp.FPDF = object
    sys.modules["fpdf"] = fp
