# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Auth endpoints for /api/v1 — reuse the existing cw_login session + CSRF."""
from flask import jsonify, request
from sqlalchemy import func
from werkzeug.security import check_password_hash

from . import api_v1
from .serializers import serialize_user
from .. import ub, config, limiter
from ..cw_login import current_user, login_user, logout_user

try:
    from flask_wtf.csrf import generate_csrf
except ImportError:  # flask_wtf is optional/container-only
    generate_csrf = None

try:
    from flask_limiter.util import get_remote_address
except ImportError:  # flask_limiter is optional/container-only
    get_remote_address = lambda: "127.0.0.1"  # noqa: E731


def _login_key_func():
    """Rate-limit key: posted username (lower-stripped), falling back to remote IP."""
    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip().lower()
    return username or get_remote_address()


@api_v1.route("/auth/csrf")
def auth_csrf():
    token = generate_csrf() if generate_csrf else ""
    return jsonify({"csrf_token": token})


def _server_features():
    """Instance-level capability flags the SPA gates UI off (mirrors the Jinja
    template gates: hide-books button, send-to-e-reader, register link, …).
    Authoritative enforcement stays server-side on each endpoint."""
    try:
        mail_ok = bool(config.get_mail_server_configured())
    except Exception:
        mail_ok = False
    return {
        "hide_books": bool(getattr(config, "config_user_hide_enabled", False)),
        "mail_configured": mail_ok,
        "public_registration": bool(getattr(config, "config_public_reg", False)),
        "anon_browse": bool(getattr(config, "config_anonbrowse", False)),
    }


@api_v1.route("/auth/me")
def auth_me():
    if not current_user.is_authenticated:
        return jsonify({"error": {"code": "unauthenticated", "message": "Login required"}}), 401
    payload = serialize_user(current_user)
    payload["features"] = _server_features()
    return jsonify(payload)


@api_v1.route("/auth/login", methods=["POST"])
@limiter.limit("40/day", key_func=_login_key_func)
@limiter.limit("3/minute", key_func=_login_key_func)
def auth_login():
    # I2: Honour config_disable_standard_login.
    # LDAP/OAuth login routing is deferred to the auth-bridge sub-project (sub-project 2).
    if config.config_disable_standard_login:
        return jsonify({"error": {"code": "standard_login_disabled",
                                  "message": "Standard login is disabled"}}), 403

    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip().lower()
    password = data.get("password") or ""
    user = ub.session.query(ub.User).filter(func.lower(ub.User.name) == username).first()
    if user and not user.role_anonymous() and check_password_hash(str(user.password), password):
        login_user(user, remember=bool(data.get("remember")))
        payload = serialize_user(user)
        payload["features"] = _server_features()
        return jsonify(payload)
    return jsonify({"error": {"code": "invalid_credentials",
                              "message": "Invalid username or password"}}), 401


@api_v1.route("/auth/logout", methods=["POST"])
def auth_logout():
    logout_user()
    return "", 204
