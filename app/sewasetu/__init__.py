# -*- coding: utf-8 -*-
"""Sewa Setu - Old Age Pension Portal, Government of Purvanchal."""
import logging
import os
from datetime import timedelta

from flask import Flask, render_template, flash, redirect, request, url_for

from . import db
from .config import load_settings


def create_app(settings=None, init_database=True):
    settings = settings or load_settings()
    app = Flask(__name__, template_folder=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates"))
    app.config["SETTINGS"] = settings
    app.secret_key = settings.secret_key
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=settings.session_minutes)
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_bytes + 1024 * 1024

    _setup_logging(app)

    from .routes import public, apply_flow, status, admin
    for module in (public, apply_flow, status, admin):
        app.register_blueprint(module.bp)

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    @app.errorhandler(404)
    def not_found(_):
        return render_template("error.html", title="Page not found",
                               message="We could not find that page. Please go back "
                                       "to the home page."), 404

    @app.errorhandler(413)
    def too_large(_):
        flash("The file is too large. The maximum allowed size is %d MB."
              % (settings.max_upload_bytes // 1048576))
        return redirect(url_for("apply.upload") if "upload" in request.path
                        else url_for("public.index"))

    @app.errorhandler(db.DatabaseBusy)
    def busy(_):
        return render_template("error.html", title="Service busy",
                               message="The service is very busy right now. Nothing "
                                       "was lost. Please try again in a minute."), 503

    @app.errorhandler(500)
    def server_error(_):
        return render_template("error.html", title="Something went wrong",
                               message="Something went wrong on our side. Please "
                                       "try again in a minute."), 500

    if init_database:
        db.init_pool(settings)
        try:
            db.ensure_schema()
        except Exception as exc:  # DB may still be starting; do not crash the worker
            app.logger.error("schema check failed: %s", exc)
    return app


def _setup_logging(app):
    app.logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s in app: %(message)s")
    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    app.logger.addHandler(stream)
    logdir = os.environ.get("LOG_DIR", "/var/log/sewasetu")
    try:
        os.makedirs(logdir, exist_ok=True)
        fh = logging.FileHandler(os.path.join(logdir, "sewasetu-app.log"))
        fh.setFormatter(fmt)
        app.logger.addHandler(fh)
    except OSError:
        pass
    logging.getLogger("sewasetu").setLevel(logging.INFO)
    for name in ("sewasetu",):
        logging.getLogger(name).addHandler(stream)
