# -*- coding: utf-8 -*-
"""
Deemed-approval job.

Under the Purvanchal Right to Public Services Act, an application not processed
within the statutory SLA stands approved. This job marks such applications
DEEMED_APPROVED and notifies the applicant by SMS.

Run by scripts/scheduler.py every day at 02:00 IST. `--dry-run` only counts.
(The old cron entry read a config/settings.ini that no longer exists after the
March 2026 consolidation, so from then on it failed every night.)
"""
import os
import sys
import logging
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2  # noqa: E402

from sewasetu.config import load_settings  # noqa: E402
from sewasetu.sms import send_sms  # noqa: E402
from sewasetu.timeutil import now_ist  # noqa: E402

log = logging.getLogger("deemed_approval")


def run(settings, dry_run=False, notify=send_sms):
    conn = psycopg2.connect(host=settings.db_host, port=settings.db_port,
                            dbname=settings.db_name, user=settings.db_user,
                            password=settings.db_password)
    try:
        now = now_ist()
        cutoff = now - timedelta(days=settings.sla_days)
        cur = conn.cursor()
        if dry_run:
            cur.execute("SELECT count(*) FROM applications "
                        "WHERE status = 'PENDING' AND submitted_at < %s", (cutoff,))
            return cur.fetchone()[0], []
        cur.execute("""UPDATE applications
                       SET status = 'DEEMED_APPROVED', decided_at = %s,
                           decided_by = 'RTPS-AUTO'
                       WHERE status = 'PENDING' AND submitted_at < %s
                       RETURNING application_no, mobile""", (now, cutoff))
        rows = cur.fetchall()
        conn.commit()
        cur.close()
    finally:
        conn.close()
    for app_no, mobile in rows:
        notify(settings.sms_gateway_url, mobile,
               "Sewa Setu: your pension application %s stands approved under "
               "the RTPS Act." % app_no)
    return len(rows), rows


def main(argv):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    dry = "--dry-run" in argv
    count, _ = run(load_settings(), dry_run=dry)
    print("%s deemed approval%s: %d applications %s"
          % (now_ist().strftime("%Y-%m-%d %H:%M:%S"), " (dry run)" if dry else "",
             count, "would be approved" if dry else "approved"), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
