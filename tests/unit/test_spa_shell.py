import pytest
import flask


def _spa_app(monkeypatch, tmp_spa_dir=None):
    """Build a Flask app with the spa blueprint. When tmp_spa_dir is given, point
    the shell at it (with a minimal index.html) so the serving logic is tested
    independently of whether the real Vite bundle has been built — the Fast Tests
    CI job runs against source and never builds the frontend (that's the separate
    Frontend Build job + the Docker image build)."""
    import cps.spa as spa_mod
    if tmp_spa_dir is not None:
        (tmp_spa_dir / "index.html").write_text(
            "<!doctype html><title>Calibre-Web NextGen</title><div id=root></div>")
        monkeypatch.setattr(spa_mod, "_SPA_DIR", str(tmp_spa_dir))
    app = flask.Flask(__name__)
    app.register_blueprint(spa_mod.spa)
    return app


@pytest.mark.unit
def test_spa_disabled_404(monkeypatch):
    monkeypatch.delenv("CWNG_SPA", raising=False)
    app = _spa_app(monkeypatch)
    assert app.test_client().get("/app").status_code == 404


@pytest.mark.unit
def test_spa_missing_bundle_404(monkeypatch, tmp_path):
    """Enabled but no build artifact present -> 404 (don't serve a broken shell)."""
    monkeypatch.setenv("CWNG_SPA", "1")
    empty = tmp_path / "empty"
    empty.mkdir()
    import cps.spa as spa_mod
    monkeypatch.setattr(spa_mod, "_SPA_DIR", str(empty))
    app = flask.Flask(__name__)
    app.register_blueprint(spa_mod.spa)
    assert app.test_client().get("/app").status_code == 404


@pytest.mark.unit
def test_spa_enabled_serves_shell(monkeypatch, tmp_path):
    monkeypatch.setenv("CWNG_SPA", "1")
    app = _spa_app(monkeypatch, tmp_path)
    resp = app.test_client().get("/app")
    assert resp.status_code == 200
    assert b"NextGen" in resp.data


@pytest.mark.unit
@pytest.mark.parametrize("path", ["/app", "/app/", "/app/book/5", "/app/authors"])
def test_spa_serves_all_client_routes(monkeypatch, tmp_path, path):
    """The shell must answer /app, /app/ (trailing slash) and any deep client-side
    route, so a hard reload / shared link on any SPA path boots the app instead of
    hitting a server 404. Regression: /app/ previously 404'd because the
    /app/<path:path> rule doesn't match an empty path segment."""
    monkeypatch.setenv("CWNG_SPA", "1")
    app = _spa_app(monkeypatch, tmp_path)
    resp = app.test_client().get(path)
    assert resp.status_code == 200, f"{path} should serve the SPA shell"
    assert b"NextGen" in resp.data


@pytest.mark.unit
def test_spa_context_processor_exposes_flag(monkeypatch):
    """The legacy 'Switch to New UI' button is gated on cwng_spa_enabled, injected
    app-wide by the spa blueprint's context processor."""
    import cps.spa as spa_mod
    monkeypatch.setenv("CWNG_SPA", "1")
    assert spa_mod._inject_spa_flag() == {"cwng_spa_enabled": True}
    monkeypatch.delenv("CWNG_SPA", raising=False)
    assert spa_mod._inject_spa_flag() == {"cwng_spa_enabled": False}
