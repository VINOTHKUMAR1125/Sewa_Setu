# -*- coding: utf-8 -*-
from contextlib import contextmanager
from datetime import datetime
from unittest import mock

from sewasetu import create_app, db
from sewasetu.config import load_settings


class FakeCursor:
    """Records every statement; `rows` maps a SQL fragment to fetchone/fetchall data."""

    def __init__(self, log, rows):
        self.log, self.rows, self._last = log, rows, None
        self.rowcount = 1

    def execute(self, sql, params=None):
        self.log.append((sql, params))
        self._last = sql

    def _match(self):
        for fragment, value in self.rows.items():
            if fragment in (self._last or ""):
                return value
        return None

    def fetchone(self):
        value = self._match()
        if isinstance(value, list):
            return value[0] if value else None
        return value

    def fetchall(self):
        value = self._match()
        return value if isinstance(value, list) else ([value] if value else [])

    def close(self):
        pass


class FakeDB:
    def __init__(self, rows=None):
        self.log, self.rows = [], rows or {}

    @contextmanager
    def cursor(self):
        yield FakeCursor(self.log, self.rows)

    def statements(self, fragment):
        return [(s, p) for s, p in self.log if fragment in s]


def make_client(rows=None, settings=None):
    fake = FakeDB(rows)
    app = create_app(settings or load_settings(), init_database=False)
    app.config["TESTING"] = True
    patcher = mock.patch.object(db, "cursor", fake.cursor)
    patcher.start()
    client = app.test_client()
    client._patcher = patcher
    return app, client, fake


def stop(client):
    client._patcher.stop()


APP_ROW = ("SSP26123456", "Runu Dutta", "9861908220", datetime(1961, 5, 20).date(),
           "Milanpur", "Borgaon", "3921227103603", "CNRB0004417", "PENDING",
           datetime(2026, 10, 1, 10, 0), None)
