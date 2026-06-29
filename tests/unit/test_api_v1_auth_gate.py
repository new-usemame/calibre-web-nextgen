"""Regression tests for the blueprint-level auth gate (cps.api._require_api_auth).

The gate must return a JSON 401 for unauthenticated requests to protected
endpoints — never an HTML 302 redirect to the login page, which an SPA fetch
would silently follow and then fail to JSON-parse on session expiry.
"""
import flask
import pytest
from unittest.mock import patch


def _app():
    from cps.api import api_v1
    app = flask.Flask(__name__)
    app.testing = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SECRET_KEY"] = "test"
    app.config["RATELIMIT_ENABLED"] = False
    app.register_blueprint(api_v1)
    return app


@pytest.mark.unit
def test_anon_protected_endpoint_returns_json_401():
    """An anonymous request to a protected endpoint short-circuits in
    before_request with a JSON 401 (the view, which needs the DB, never runs)."""
    app = _app()
    with patch("cps.api.current_user") as cu, patch("cps.api.config") as cfg:
        cu.is_authenticated = False
        cfg.config_allow_reverse_proxy_header_login = False
        cfg.config_anonbrowse = 0
        resp = app.test_client().get("/api/v1/authors")
    assert resp.status_code == 401
    assert resp.is_json
    assert resp.get_json()["error"]["code"] == "unauthorized"


@pytest.mark.unit
def test_health_is_public_even_when_anon():
    app = _app()
    with patch("cps.api.current_user") as cu, patch("cps.api.config") as cfg:
        cu.is_authenticated = False
        cfg.config_allow_reverse_proxy_header_login = False
        cfg.config_anonbrowse = 0
        resp = app.test_client().get("/api/v1/health")
    assert resp.status_code == 200


@pytest.mark.unit
def test_auth_endpoints_are_public():
    """csrf/login/me/logout must remain reachable without a session, or login
    would be impossible."""
    from cps.api import _PUBLIC_ENDPOINTS
    for ep in ("api_v1.health", "api_v1.auth_csrf", "api_v1.auth_login",
               "api_v1.auth_me", "api_v1.auth_logout"):
        assert ep in _PUBLIC_ENDPOINTS


@pytest.mark.unit
def test_authenticated_request_passes_gate():
    # Patches must be entered BEFORE pushing the bare-app request context:
    # mock.patch inspects the current_user LocalProxy on __enter__, which would
    # resolve against the (login_manager-less) bare app if a context were active.
    from cps.api import _require_api_auth
    app = _app()
    with patch("cps.api.current_user") as cu, patch("cps.api.config") as cfg:
        cu.is_authenticated = True
        cfg.config_allow_reverse_proxy_header_login = False
        cfg.config_anonbrowse = 0
        with app.test_request_context("/api/v1/authors"):
            assert _require_api_auth() is None


@pytest.mark.unit
def test_anonbrowse_mode_bypasses_gate():
    """When anonymous browsing is enabled, the gate lets the request through
    (returns None) so the public catalog is reachable without login."""
    from cps.api import _require_api_auth
    app = _app()
    with patch("cps.api.current_user") as cu, patch("cps.api.config") as cfg:
        cu.is_authenticated = False
        cfg.config_allow_reverse_proxy_header_login = False
        cfg.config_anonbrowse = 1
        with app.test_request_context("/api/v1/authors"):
            assert _require_api_auth() is None
