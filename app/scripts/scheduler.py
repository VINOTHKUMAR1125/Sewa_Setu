# -*- coding: utf-8 -*-
"""Runs the deemed-approval job once at start-up (catch-up after the outage) and
then every day at 02:00 IST. Replaces cron, which did not receive the container's
environment (database password) and hid failures in a log nobody read."""
import os
import sys
import time
import traceback
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts import deemed_approval  # noqa: E402
from sewasetu.timeutil import now_ist  # noqa: E402

RUN_HOUR = 2


def seconds_until_next_run(now):
    target = now.replace(hour=RUN_HOUR, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def run_once():
    try:
        deemed_approval.main([])
    except Exception:
        traceback.print_exc()
        sys.stderr.flush()


def main():
    run_once()
    while True:
        time.sleep(seconds_until_next_run(now_ist()))
        run_once()


if __name__ == "__main__":
    main()
