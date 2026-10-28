# -*- coding: utf-8 -*-
"""Mobile -> OTP -> form steps -> upload -> declaration -> submission."""
import hmac
import os
import random
import uuid
from datetime import timedelta

from flask import (Blueprint, request, session, redirect, url_for,
                   render_template, flash, abort, current_app)

from .. import repo, validators
from ..db import psycopg2_errors
from ..security import hash_password
from ..sms import send_sms, send_sms_async
from ..timeutil import now_ist
from .public import deadline_remaining

bp = Blueprint("apply", __name__)

OTP_MAX_ATTEMPTS = 5
OTP_MAX_REQUESTS = 5
OTP_REQUEST_WINDOW = timedelta(minutes=15)


def _cfg():
    return current_app.config["SETTINGS"]


def _need_verified():
    if not session.get("verified_mobile"):
        flash("Your session has ended. Please verify your mobile number again.")
        return redirect(url_for("apply.apply"))
    return None


def new_application_no():
    return "SSP" + now_ist().strftime("%y") + str(random.randint(100000, 999999))


@bp.route("/apply", methods=["GET", "POST"])
def apply():
    if deadline_remaining() is None:
        flash("The application window for this scheme has closed.")
        return redirect(url_for("public.index"))
    if request.method == "POST":
        try:
            mobile = validators.normalize_mobile(request.form.get("mobile"))
        except validators.ValidationError as exc:
            flash(str(exc))
            return render_template("apply.html")
        now = now_ist()
        if repo.recent_otp_count(mobile, now - OTP_REQUEST_WINDOW) >= OTP_MAX_REQUESTS:
            flash("Too many OTP requests for this number. Please wait about 15 "
                  "minutes and try again.")
            return render_template("apply.html")
        code = str(random.randint(100000, 999999))
        repo.insert_otp(mobile, code, now)
        sent = send_sms(_cfg().sms_gateway_url, mobile,
                        "Your Sewa Setu OTP is %s. Valid for 5 minutes." % code)
        if not sent:
            flash("We could not send the SMS right now. Please try again in a "
                  "few minutes.")
            return render_template("apply.html")
        session.permanent = True
        session["apply_mobile"] = mobile
        return redirect(url_for("apply.verify"))
    return render_template("apply.html")


@bp.route("/verify", methods=["GET", "POST"])
def verify():
    mobile = session.get("apply_mobile")
    if not mobile:
        return redirect(url_for("apply.apply"))
    if request.method == "POST":
        code = request.form.get("otp", "").strip()
        row = repo.latest_otp(mobile)
        if row is None:
            flash("No OTP was found for this number. Please request a new OTP.")
            return redirect(url_for("apply.apply"))
        otp_id, stored, created_at, attempts = row
        if (now_ist() - created_at).total_seconds() > _cfg().otp_validity_seconds:
            flash("This OTP has expired (it is valid for 5 minutes). "
                  "Please request a new OTP.")
            return redirect(url_for("apply.apply"))
        if attempts >= OTP_MAX_ATTEMPTS:
            flash("Too many wrong attempts. Please request a new OTP.")
            return redirect(url_for("apply.apply"))
        if hmac.compare_digest(stored or "", code):
            repo.clear_otps(mobile)
            session["verified_mobile"] = mobile
            session["form_data"] = {}
            session.pop("doc_path", None)
            if repo.application_exists(mobile):
                session.pop("verified_mobile", None)
                flash("An application already exists for this mobile number. "
                      "Each person can apply only once. You can check its status "
                      "below using your mobile number and password.")
                return redirect(url_for("status.status_login"))
            return redirect(url_for("apply.form_step", step=1))
        repo.bump_otp_attempts(otp_id)
        left = OTP_MAX_ATTEMPTS - attempts - 1
        flash("The OTP you entered is not correct. Please check the SMS and try "
              "again (%d attempt%s left). The SMS can take up to a minute to arrive."
              % (left, "" if left == 1 else "s"))
    return render_template("verify.html", mobile=mobile)


@bp.route("/form/<int:step>", methods=["GET", "POST"])
def form_step(step):
    redirect_resp = _need_verified()
    if redirect_resp:
        return redirect_resp
    if step not in validators.STEP_FIELDS:
        abort(404)
    data = session.get("form_data", {})
    if request.method == "POST":
        submitted = {k: request.form.get(k, "") for k in validators.STEP_FIELDS[step]}
        _, errors = validators.validate_step(step, submitted, now_ist().date(),
                                             _cfg().min_age)
        if errors:
            for message in errors:
                flash(message)
            merged = dict(data)
            merged.update(submitted)
            return render_template("form_step%d.html" % step, data=merged,
                                   blocks=validators.BLOCKS)
        data.update(submitted)
        session["form_data"] = data
        if step < 3:
            return redirect(url_for("apply.form_step", step=step + 1))
        return redirect(url_for("apply.upload"))
    return render_template("form_step%d.html" % step, data=data,
                           blocks=validators.BLOCKS)


@bp.route("/upload", methods=["GET", "POST"])
def upload():
    redirect_resp = _need_verified()
    if redirect_resp:
        return redirect_resp
    if request.method == "POST":
        f = request.files.get("document")
        content = f.read() if f is not None and f.filename else b""
        try:
            ext = validators.validate_upload(f.filename if f else "", len(content),
                                             _cfg().max_upload_bytes)
        except validators.ValidationError as exc:
            flash(str(exc))
            return render_template("upload.html")
        os.makedirs(_cfg().upload_dir, exist_ok=True)
        path = os.path.join(_cfg().upload_dir, "%s_%s%s" % (
            session["verified_mobile"], uuid.uuid4().hex, ext))
        with open(path, "wb") as out:
            out.write(content)
        session["doc_path"] = path
        return redirect(url_for("apply.declaration"))
    return render_template("upload.html")


@bp.route("/declaration", methods=["GET", "POST"])
def declaration():
    redirect_resp = _need_verified()
    if redirect_resp:
        return redirect_resp
    if request.method == "POST":
        return handle_submission()
    return render_template("declaration.html")


def collect_application(data, today, min_age):
    """Re-validate everything collected across the three steps.

    Returns (values, first_bad_step, errors)."""
    values = {}
    for step in (1, 2, 3):
        cleaned, errors = validators.validate_step(step, data, today, min_age)
        if errors:
            return None, step, errors
        values.update(cleaned)
    return values, None, []


def handle_submission():
    cfg = _cfg()
    mobile = session.get("verified_mobile")
    now = now_ist()
    if now > cfg.scheme_deadline:
        flash("The application deadline has passed.")
        return redirect(url_for("public.index"))

    values, bad_step, errors = collect_application(
        session.get("form_data", {}), now.date(), cfg.min_age)
    if errors:
        for message in errors:
            flash(message)
        return redirect(url_for("apply.form_step", step=bad_step))

    values.update(mobile=mobile, doc_path=session.get("doc_path", ""),
                  submitted_at=now)
    portal_hash = hash_password(values["dob"].strftime("%d%m%Y"))

    new_id = app_no = None
    for _ in range(5):
        app_no = new_application_no()
        values["application_no"] = app_no
        try:
            new_id = repo.insert_application(values, portal_hash)
            break
        except psycopg2_errors.UniqueViolation as exc:
            if "mobile" in (getattr(exc.diag, "constraint_name", "") or ""):
                flash("An application already exists for this mobile number. "
                      "Duplicate applications are not permitted.")
                return redirect(url_for("status.status_login"))
    if new_id is None:
        flash("We could not save your application just now. Nothing was lost - "
              "please press Submit again.")
        return render_template("declaration.html")

    for key in ("form_data", "doc_path", "verified_mobile", "apply_mobile"):
        session.pop(key, None)
    session["portal_mobile"] = mobile  # lets the citizen open their own acknowledgment
    send_sms_async(cfg.sms_gateway_url, mobile,
                   "Sewa Setu: application %s received. Track at the status portal "
                   "with mobile no. and password (DOB as DDMMYYYY)." % app_no)
    return render_template("confirmation.html", app_no=app_no, app_id=new_id)
