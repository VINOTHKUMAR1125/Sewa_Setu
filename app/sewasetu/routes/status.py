# -*- coding: utf-8 -*-
"""Citizen status portal. A citizen can only ever read their own application."""
import io

from flask import (Blueprint, request, session, redirect, url_for, render_template,
                   flash, abort, send_file, current_app)

from .. import repo, validators
from ..ack_pdf import build_acknowledgment
from ..security import hash_password, password_matches
from ..sms import send_sms_async
from ..throttle import Throttle

bp = Blueprint("status", __name__)

login_throttle = Throttle(limit=10, window_seconds=900)
reset_throttle = Throttle(limit=5, window_seconds=900)


@bp.route("/status", methods=["GET", "POST"])
def status_login():
    if request.method == "POST":
        try:
            mobile = validators.normalize_mobile(request.form.get("mobile"))
        except validators.ValidationError as exc:
            flash(str(exc))
            return render_template("status_login.html")
        if login_throttle.blocked(mobile):
            flash("Too many failed logins for this number. Please try again "
                  "after 15 minutes.")
            return render_template("status_login.html")
        stored = repo.portal_password_hash(mobile)
        if stored and password_matches(stored, request.form.get("password", "").strip()):
            login_throttle.reset(mobile)
            session["portal_mobile"] = mobile
            app_id = repo.application_id_for_mobile(mobile)
            if app_id:
                return redirect(url_for("status.view_application", app_id=app_id))
            flash("No application was found for this mobile number.")
            return redirect(url_for("status.status_login"))
        login_throttle.hit(mobile)
        flash("The mobile number or password is not correct. The password is "
              "the date of birth as DDMMYYYY, for example 25031958 for "
              "25 March 1958. If you forgot it, use 'Forgot password'.")
    return render_template("status_login.html")


@bp.route("/status/logout")
def status_logout():
    session.pop("portal_mobile", None)
    return redirect(url_for("public.index"))


@bp.route("/application/<int:app_id>")
def view_application(app_id):
    mobile = session.get("portal_mobile")
    if not mobile:
        flash("Please log in to view your application status.")
        return redirect(url_for("status.status_login"))
    row = repo.application_for_citizen(app_id, mobile)
    if not row:
        abort(404)
    return render_template("application.html", a=row, app_id=app_id)


@bp.route("/ack/<int:app_id>.pdf")
def ack_pdf(app_id):
    row = repo.application_for_ack(app_id)
    owner = session.get("portal_mobile")
    if not row or not (session.get("admin") or (owner and owner == row[0])):
        abort(404)
    data = build_acknowledgment(row[1:])
    return send_file(io.BytesIO(data), mimetype="application/pdf")


@bp.route("/status/reset", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        message = ("If the mobile number is registered, the password has been "
                   "reset and sent by SMS.")
        try:
            mobile = validators.normalize_mobile(request.form.get("mobile"))
        except validators.ValidationError as exc:
            flash(str(exc))
            return render_template("reset.html")
        if reset_throttle.blocked(mobile):
            flash("Too many reset requests for this number. Please try again later.")
            return render_template("reset.html")
        reset_throttle.hit(mobile)
        if repo.portal_user_exists(mobile):
            dob = repo.dob_for_reset(mobile)
            if dob:
                repo.reset_portal_password(mobile, hash_password(dob.strftime("%d%m%Y")))
                send_sms_async(current_app.config["SETTINGS"].sms_gateway_url, mobile,
                               "Sewa Setu: your password has been reset to your "
                               "date of birth (DDMMYYYY).")
        flash(message)
    return render_template("reset.html")
