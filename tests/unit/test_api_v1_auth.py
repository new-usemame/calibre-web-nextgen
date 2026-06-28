import inspect
import pytest
import flask
from unittest.mock import patch, MagicMock

import cps.api.auth


def _app():
    from cps.api import api_v1
    app = flask.Flask(__name__)
    app.testing = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SECRET_KEY"] = "test"
    app.config["RATELIMIT_ENABLED"] = False  # disable rate-limiting in unit tests
    app.register_blueprint(api_v1)
    return app


@pytest.mark.unit
def test_csrf_returns_token_key():
    resp = _app().test_client().get("/api/v1/auth/csrf")
    assert resp.status_code == 200
    assert "csrf_token" in resp.get_json()


@pytest.mark.unit
def test_me_anonymous_401():
    app = _app()
    with patch("cps.api.auth.current_user") as cu:
        cu.is_authenticated = False
        resp = app.test_client().get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.unit
def test_me_authenticated_returns_user():
    app = _app()
    from cps import ub, constants
    u = ub.User()
    u.id, u.name, u.locale, u.theme = 5, "maggie", "en", 1
    u.role = constants.ROLE_USER
    with patch("cps.api.auth.current_user", u):
        resp = app.test_client().get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "maggie"


@pytest.mark.unit
def test_login_success():
    app = _app()
    from cps import ub, constants
    u = ub.User()
    u.id, u.name, u.password, u.locale, u.theme = 1, "admin", "hash", "en", 1
    u.role = constants.ROLE_ADMIN
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = u
    with patch("cps.api.auth.ub.session", mock_session), \
         patch("cps.api.auth.check_password_hash", return_value=True), \
         patch("cps.api.auth.config.config_disable_standard_login", False, create=True), \
         patch("cps.api.auth.login_user") as lu:
        resp = app.test_client().post("/api/v1/auth/login", json={"username": "admin", "password": "x"})
    assert resp.status_code == 200
    # M3: assert login_user called with the exact user object and remember=False
    lu.assert_called_once_with(u, remember=False)
    assert resp.get_json()["name"] == "admin"


@pytest.mark.unit
def test_login_bad_password_401():
    app = _app()
    from cps import ub, constants
    u = ub.User()
    u.name, u.password = "admin", "hash"
    u.role = constants.ROLE_ADMIN
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.first.return_value = u
    with patch("cps.api.auth.ub.session", mock_session), \
         patch("cps.api.auth.check_password_hash", return_value=False), \
         patch("cps.api.auth.config.config_disable_standard_login", False, create=True), \
         patch("cps.api.auth.login_user") as lu:
        resp = app.test_client().post("/api/v1/auth/login", json={"username": "admin", "password": "x"})
    assert resp.status_code == 401
    assert not lu.called
    # M3: assert the response body carries the expected error code
    body = resp.get_json()
    assert body["error"]["code"] == "invalid_credentials"


@pytest.mark.unit
def test_logout_204():
    app = _app()
    with patch("cps.api.auth.logout_user") as lo:
        resp = app.test_client().post("/api/v1/auth/logout")
    assert resp.status_code == 204
    assert lo.called


# ── Regression: I1 — rate-limit decorator is present on auth_login ────────────

@pytest.mark.unit
def test_auth_login_has_rate_limit_decorator():
    """Source-pin: auth_login must carry flask_limiter rate-limit decorators.

    We inspect the source of the module-level function (before Flask unwraps it)
    to confirm both limit strings are present.  This will fail if the @limiter.limit
    decorators are removed.
    """
    src = inspect.getsource(cps.api.auth.auth_login)
    # The decorator stacks are on auth_login's own source lines.
    # Since limiter.limit wraps it, getsource returns the inner function; check the module.
    module_src = inspect.getsource(cps.api.auth)
    assert "40/day" in module_src, "40/day rate limit missing from cps.api.auth"
    assert "3/minute" in module_src, "3/minute rate limit missing from cps.api.auth"
    assert "_login_key_func" in module_src, "key_func helper missing from cps.api.auth"


# ── Regression: I2 — standard_login_disabled returns 403 ────────────────────

@pytest.mark.unit
def test_login_standard_login_disabled_returns_403():
    """When config_disable_standard_login is True, auth_login must return 403
    with code='standard_login_disabled' and must NOT call login_user."""
    app = _app()
    with patch("cps.api.auth.config.config_disable_standard_login", True, create=True), \
         patch("cps.api.auth.login_user") as lu:
        resp = app.test_client().post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "x"},
        )
    assert resp.status_code == 403
    body = resp.get_json()
    assert body["error"]["code"] == "standard_login_disabled"
    lu.assert_not_called()


# ── register / forgot / config (#22) ─────────────────────────────────────────

@pytest.mark.unit
def test_auth_config_is_public_and_shaped():
    app = _app()
    with patch.object(cps.api.auth, "config") as cfg, \
         patch.object(cps.api.auth, "_oauth_providers", return_value=[]):
        cfg.config_public_reg = True
        cfg.config_register_email = False
        cfg.get_mail_server_configured.return_value = True
        cfg.config_disable_standard_login = False
        resp = app.test_client().get("/api/v1/auth/config")
    assert resp.status_code == 200
    d = resp.get_json()
    assert d["public_registration"] is True
    assert d["mail_configured"] is True
    assert d["oauth_providers"] == []


@pytest.mark.unit
def test_register_disabled_returns_403():
    app = _app()
    with patch.object(cps.api.auth, "config") as cfg:
        cfg.config_public_reg = False
        resp = app.test_client().post("/api/v1/auth/register",
                                      json={"name": "x", "email": "y@z.com"})
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "registration_disabled"


@pytest.mark.unit
def test_register_requires_mail_configured():
    app = _app()
    with patch.object(cps.api.auth, "config") as cfg:
        cfg.config_public_reg = True
        cfg.get_mail_server_configured.return_value = False
        resp = app.test_client().post("/api/v1/auth/register",
                                      json={"name": "x", "email": "y@z.com"})
    assert resp.status_code == 400
    assert resp.get_json()["error"]["code"] == "mail_not_configured"


@pytest.mark.unit
def test_forgot_always_ok_even_for_unknown_user():
    app = _app()
    with patch.object(cps.api.auth, "ub") as ub:
        ub.session.query.return_value.filter.return_value.first.return_value = None
        resp = app.test_client().post("/api/v1/auth/forgot", json={"username": "ghost"})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


@pytest.mark.unit
def test_oauth_providers_hidden_unless_login_type_oauth():
    """REGRESSION: OAuth buttons must only appear when the instance login type is
    OAuth — matching the classic login page. Otherwise they'd show + error on a
    standard/LDAP-login instance where OAuth isn't configured."""
    from cps import constants
    with patch.object(cps.api.auth, "config") as cfg, \
         patch.dict("cps.oauth_bb.oauth_check", {1: "GitHub", 3: "Generic"}, clear=True):
        cfg.config_login_type = constants.LOGIN_STANDARD
        assert cps.api.auth._oauth_providers() == []


@pytest.mark.unit
def test_oauth_providers_maps_ids_to_urls_when_oauth():
    from cps import constants
    with patch.object(cps.api.auth, "config") as cfg, \
         patch.object(cps.api.auth, "url_for", side_effect=lambda ep: "/" + ep.replace(".", "/")), \
         patch.dict("cps.oauth_bb.oauth_check", {1: "GitHub", 2: "Google"}, clear=True):
        cfg.config_login_type = constants.LOGIN_OAUTH
        provs = cps.api.auth._oauth_providers()
    by_id = {p["id"]: p for p in provs}
    assert by_id[1]["url"] == "/oauth/github_login"
    assert by_id[2]["name"] == "Google"


@pytest.mark.unit
def test_auth_config_exposes_remote_login():
    """Magic-link (remote) login is surfaced for the SPA login when enabled."""
    app = _app()
    with patch.object(cps.api.auth, "config") as cfg, \
         patch.object(cps.api.auth, "_oauth_providers", return_value=[]), \
         patch.object(cps.api.auth, "url_for", return_value="/remote/login"):
        cfg.config_public_reg = False
        cfg.config_register_email = False
        cfg.get_mail_server_configured.return_value = True
        cfg.config_disable_standard_login = False
        cfg.config_remote_login = True
        d = app.test_client().get("/api/v1/auth/config").get_json()
    assert d["remote_login"] is True
    assert d["remote_login_url"] == "/remote/login"
