# -*- coding: utf-8 -*-
"""All business time in Sewa Setu is Indian Standard Time.

The containers run in UTC, while the production data (and the 31 October
deadline) are in IST. Timestamps are stored as naive IST datetimes, exactly as
the existing records are, so everything that compares against them must use
`now_ist()` instead of `datetime.now()`.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist():
    return datetime.now(IST).replace(tzinfo=None)
