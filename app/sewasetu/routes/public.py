# -*- coding: utf-8 -*-
import math

import requests
from flask import Blueprint, render_template, request, current_app

from .. import db
from ..timeutil import now_ist

bp = Blueprint("public", __name__)


def deadline_remaining():
    cfg = current_app.config["SETTINGS"]
    seconds = (cfg.scheme_deadline - now_ist()).total_seconds()
    if seconds <= 0:
        return None
    return max(1, int(math.ceil(seconds / 3600.0)))


@bp.route("/")
def index():
    return render_template("index.html", hours_left=deadline_remaining())


@bp.route("/about")
def about():
    return render_template("about.html")


@bp.route("/healthz")
def healthz():
    try:
        with db.cursor() as cur:
            cur.execute("SELECT 1")
        return {"status": "ok"}
    except Exception:
        return {"status": "database unavailable"}, 503


@bp.route("/__gateway/", defaults={"subpath": ""})
@bp.route("/__gateway/<path:subpath>")
def gateway_proxy(subpath):
    # The simulated SMS gateway runs on the internal network only; its console is
    # shown here so OTPs are readable without exposing a second port.
    cfg = current_app.config["SETTINGS"]
    try:
        r = requests.get(cfg.sms_gateway_url + "/" + subpath,
                         params=request.args, timeout=5)
        return (r.content, r.status_code,
                {"Content-Type": r.headers.get("Content-Type", "text/html")})
    except Exception as exc:
        current_app.logger.error("gateway proxy error: %s", exc)
        return ("SMS gateway unreachable", 502)
