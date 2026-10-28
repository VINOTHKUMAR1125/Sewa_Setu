# -*- coding: utf-8 -*-
import hashlib
import hmac
from functools import wraps

from flask import session, redirect, url_for, abort


def hash_password(password):
    # Existing portal accounts use unsalted SHA-256 of the DOB (DDMMYYYY);
    # kept so that citizens who registered before can still log in.
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def password_matches(stored_hash, supplied):
    return hmac.compare_digest(stored_hash or "", hash_password(supplied or ""))


def credentials_match(expected, supplied):
    return hmac.compare_digest((expected or "").encode("utf-8"),
                               (supplied or "").encode("utf-8"))


def admin_required(view):
    """Staff-only page: redirect to login. Citizen sessions never qualify."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin.admin_login"))
        return view(*args, **kwargs)
    return wrapper


def admin_required_403(view):
    """Staff-only action (POST): refuse outright."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            abort(403)
        return view(*args, **kwargs)
    return wrapper
