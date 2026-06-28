# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Auth endpoints for /api/v1 — reuse the existing cw_login session + CSRF."""
from flask import jsonify, request, url_for
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from . import api_v1
from .serializers import serialize_user
from .. import ub, config, constants, limiter
from ..cw_login import current_user, login_user, logout_user
from ..helper import (
    check_username, check_email, check_valid_domain, reset_password,
    send_registration_mail, generate_random_password,
)


def _err(code, message, status):
    return jsonify({"error": {"code": code, "message": message}}), status


def _oauth_providers():
    """OAuth/OIDC providers for the SPA login buttons, as {id, name, url}.

    Matches the classic login page EXACTLY: providers are only offered when the
    instance's login type is OAuth (config_login_type == LOGIN_OAUTH) AND the
    provider is registered in oauth_check. Without the login-type gate the buttons
    would appear on a standard- or LDAP-login instance and error on click (the
    provider isn't configured). URLs are built with url_for so they're correct
    behind a reverse-proxy subpath. Endpoints map to the same oauth.* routes the
    classic template links to."""
    if config.config_login_type != constants.LOGIN_OAUTH:
        return []
    endpoints = {1: "oauth.github_login", 2: "oauth.google_login", 3: "oauth.generic_login"}
    try:
        from ..oauth_bb import oauth_check
        out = []
        for cid, name in oauth_check.items():
            ep = endpoints.get(cid)
            if ep:
                try:
                    out.append({"id": cid, "name": name, "url": url_for(ep)})
                except Exception:
                    pass
        return out
    except Exception:
        return []

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
        "kobo_sync": bool(getattr(config, "config_kobo_sync", False)),
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


@api_v1.route("/auth/config")
def auth_config():
    """Public: what the login screen needs to render register / forgot / OAuth."""
    try:
        mail_ok = bool(config.get_mail_server_configured())
    except Exception:
        mail_ok = False
    # Magic-link ("remote") login — admin toggle config_remote_login. Same gate as
    # the classic login page; URL via url_for so it's reverse-proxy-subpath safe.
    remote_login = bool(getattr(config, "config_remote_login", False))
    try:
        remote_login_url = url_for("remotelogin.remote_login") if remote_login else ""
    except Exception:
        remote_login_url = ""
    return jsonify({
        "public_registration": bool(getattr(config, "config_public_reg", False)),
        "register_email": bool(getattr(config, "config_register_email", False)),
        "mail_configured": mail_ok,
        "standard_login_disabled": bool(getattr(config, "config_disable_standard_login", False)),
        "oauth_providers": _oauth_providers(),
        "remote_login": remote_login,
        "remote_login_url": remote_login_url,
    })


@api_v1.route("/auth/register", methods=["POST"])
@limiter.limit("40/day", key_func=lambda: get_remote_address())
@limiter.limit("3/minute", key_func=lambda: get_remote_address())
def auth_register():
    """Public self-registration. Mirrors web.register_post: gated on
    config_public_reg, requires a configured mail server, validates the
    username/email + allowed-domain, then emails the generated password."""
    if not config.config_public_reg:
        return _err("registration_disabled", "Public registration is disabled", 403)
    if not config.get_mail_server_configured():
        return _err("mail_not_configured", "The server's email settings aren't configured", 400)
    if current_user.is_authenticated:
        return _err("already_authenticated", "You're already signed in", 400)

    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip()
    name = (data.get("name") or "").strip()
    nickname = email if config.config_register_email else name
    if not nickname or not email:
        return _err("invalid_request", "Please complete all fields", 400)
    try:
        nickname = check_username(nickname)
        email = check_email(email)
    except Exception as ex:  # validators raise generic Exception with a message
        return _err("invalid_request", str(ex), 400)
    if not check_valid_domain(email):
        return _err("email_not_allowed", "That email domain isn't allowed to register", 403)

    content = ub.User()
    content.name = nickname
    content.email = email
    password = generate_random_password(config.config_password_min_length)
    content.password = generate_password_hash(password)
    content.role = config.config_default_role
    content.locale = config.config_default_locale
    content.sidebar_view = config.config_default_show
    try:
        content.theme = getattr(config, "config_theme", 1)
    except Exception:
        pass
    try:
        ub.session.add(content)
        ub.session.commit()
        try:
            from ..oauth_bb import register_user_with_oauth
            register_user_with_oauth(content)
        except Exception:
            pass  # oauth optional
        send_registration_mail(email, nickname, password)
    except Exception:
        ub.session.rollback()
        return _err("server_error", "Could not complete registration. Try again later.", 500)
    return jsonify({"ok": True, "message": "Confirmation email sent"})


@api_v1.route("/auth/forgot", methods=["POST"])
@limiter.limit("40/day", key_func=lambda: get_remote_address())
@limiter.limit("3/minute", key_func=lambda: get_remote_address())
def auth_forgot():
    """Email a reset password. Always returns ok (never reveals whether the
    account exists) — an improvement over the legacy flash that leaked it."""
    data = request.get_json(silent=True) or request.form
    username = (data.get("username") or "").strip().lower()
    if username:
        user = ub.session.query(ub.User).filter(func.lower(ub.User.name) == username).first()
        if user is not None and user.name != "Guest":
            try:
                reset_password(user.id)
            except Exception:
                pass
    return jsonify({"ok": True,
                    "message": "If that account exists, a reset email has been sent."})
