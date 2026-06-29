import pytest
import flask


@pytest.mark.unit
def test_health_ok():
    from cps.api import api_v1
    app = flask.Flask(__name__)
    app.testing = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.register_blueprint(api_v1)
    resp = app.test_client().get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok", "api": "v1"}
