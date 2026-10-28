# -*- coding: utf-8 -*-
import unittest
from datetime import timedelta
from unittest import mock

from scripts import deemed_approval, scheduler
from sewasetu.config import load_settings
from sewasetu.timeutil import now_ist


class FakeConn:
    def __init__(self):
        self.executed = []

    def cursor(self):
        conn = self

        class Cur:
            def execute(self, sql, params=None):
                conn.executed.append((sql, params))

            def fetchall(self):
                return [("SSP26111111", "9876543210")]

            def fetchone(self):
                return (4100,)

            def close(self):
                pass
        return Cur()

    def commit(self):
        pass

    def close(self):
        pass


class DeemedApprovalTests(unittest.TestCase):
    def test_job_loads_the_settings_that_actually_exist(self):
        # The old script opened config/settings.ini, which no longer exists.
        settings = load_settings()
        self.assertEqual(settings.sla_days, 15)

    def test_overdue_pending_applications_are_approved_and_notified(self):
        conn, sent = FakeConn(), []
        with mock.patch.object(deemed_approval.psycopg2, "connect", return_value=conn, create=True):
            count, rows = deemed_approval.run(
                load_settings(), notify=lambda url, mobile, text: sent.append(mobile))
        sql, params = conn.executed[0]
        self.assertIn("DEEMED_APPROVED", sql)
        self.assertIn("status = 'PENDING'", sql)
        self.assertLess(params[1], now_ist() - timedelta(days=14, hours=23))
        self.assertEqual((count, sent), (1, ["9876543210"]))

    def test_dry_run_changes_nothing(self):
        conn = FakeConn()
        with mock.patch.object(deemed_approval.psycopg2, "connect", return_value=conn, create=True):
            count, _ = deemed_approval.run(load_settings(), dry_run=True)
        self.assertEqual(count, 4100)
        self.assertNotIn("UPDATE", conn.executed[0][0])

    def test_scheduler_waits_until_0200_ist(self):
        from datetime import datetime
        self.assertEqual(scheduler.seconds_until_next_run(datetime(2026, 10, 27, 1, 0)), 3600)
        self.assertEqual(scheduler.seconds_until_next_run(datetime(2026, 10, 27, 3, 0)), 23 * 3600)


if __name__ == "__main__":
    unittest.main()
