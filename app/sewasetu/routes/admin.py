# -*- coding: utf-8 -*-
from flask import (Blueprint, request, session, redirect, url_for, render_template,
                   flash, abort, current_app)

from .. import repo
from ..security import admin_required, admin_required_403, credentials_match
from ..throttle import Throttle
from ..timeutil import now_ist
from datetime import timedelta

bp = Blueprint("admin", __name__)

STATUSES = ("PENDING", "APPROVED", "REJECTED", "DEEMED_APPROVED")
login_throttle = Throttle(limit=10, window_seconds=900)


def _cfg():
    return current_app.config["SETTINGS"]


@bp.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        key = request.remote_addr or "?"
        if login_throttle.blocked(key):
            flash("Too many failed attempts. Please try again after 15 minutes.")
            return render_template("admin_login.html")
        ok_user = credentials_match(_cfg().admin_username, request.form.get("username"))
        ok_pass = credentials_match(_cfg().admin_password, request.form.get("password"))
        if ok_user and ok_pass:
            login_throttle.reset(key)
            session.permanent = True
            session["admin"] = True
            return redirect(url_for("admin.admin_dashboard"))
        login_throttle.hit(key)
        flash("Invalid credentials.")
    return render_template("admin_login.html")


@bp.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin.admin_login"))


@bp.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    cutoff = now_ist() - timedelta(days=_cfg().sla_days)
    return render_template("admin_dashboard.html", by_status=repo.counts_by_status(),
                           overdue=repo.overdue_pending(cutoff),
                           by_block=repo.pending_by_block(), sla=_cfg().sla_days)


@bp.route("/admin/applications")
@admin_required
def admin_list():
    status = request.args.get("status", "PENDING")
    if status not in STATUSES:
        status = "PENDING"
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    rows = repo.admin_list(status, (page - 1) * 50)
    return render_template("admin_list.html", rows=rows, status=status, page=page)


@bp.route("/admin/application/<int:app_id>")
@admin_required
def admin_view(app_id):
    row = repo.admin_application(app_id)
    if not row:
        abort(404)
    return render_template("admin_view.html", a=row, app_id=app_id)


def _decide(app_id, status, message):
    changed = repo.decide(app_id, status, now_ist(), _cfg().admin_username)
    flash(message if changed else
          "This application is not pending, so it was not changed.")
    return redirect(url_for("admin.admin_list"))


@bp.route("/admin/approve/<int:app_id>", methods=["POST"])
@admin_required_403
def admin_approve(app_id):
    return _decide(app_id, "APPROVED", "Application approved.")


@bp.route("/admin/reject/<int:app_id>", methods=["POST"])
@admin_required_403
def admin_reject(app_id):
    return _decide(app_id, "REJECTED", "Application rejected.")
