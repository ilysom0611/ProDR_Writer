"""Regression: /api/config/test used to 500 with AttributeError because
test_connection() called cfg.llm.missing(), which exists only on AppConfig."""
from fastapi.testclient import TestClient

import prodr_writer.config as config_mod
from prodr_writer.config import AppConfig
from prodr_writer.web.server import create_app


def test_test_connection_incomplete_lists_fields():
    ok, message = config_mod.test_connection(AppConfig())
    assert ok is False
    assert "base_url" in message and "api_key" in message and "model" in message


def _client(monkeypatch, tmp_path):
    # Isolate BOTH config sources: the file AND the environment overrides
    # (load() precedence is env > file, so PRODR_* vars leak a complete
    # config into otherwise-empty environments).
    monkeypatch.setattr(config_mod, "CONFIG_FILE", tmp_path / "config.yaml")
    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
    for var in ("PRODR_API_KEY", "PRODR_BASE_URL", "PRODR_MODEL"):
        monkeypatch.delenv(var, raising=False)
    return TestClient(create_app(host="127.0.0.1"), base_url="http://localhost")


def test_config_test_endpoint_ok_on_incomplete(monkeypatch, tmp_path):
    """POST /api/config/test must answer 200 + ok:false when config is
    incomplete — not 500 AttributeError (regression)."""
    client = _client(monkeypatch, tmp_path)
    res = client.post("/api/config/test")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert "missing" in body["message"]


def test_config_test_endpoint_roundtrip(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)

    def fake_completion(**kwargs):
        message = type("M", (), {"content": "OK"})()
        choice = type("C", (), {"message": message})()
        return type("R", (), {"choices": [choice]})()

    import litellm
    monkeypatch.setattr(litellm, "completion", fake_completion)

    save = client.post("/api/config", json={
        "base_url": "https://api.example.com/v1", "api_key": "sk-test-12345678",
        "model": "gpt-test", "temperature": 0.3, "language": "en",
        "profile": "generic-enterprise"})
    assert save.status_code == 200, save.text
    res = client.post("/api/config/test")
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_index_and_static_no_cache(monkeypatch, tmp_path):
    """UI assets must be served no-cache so upgraded servers don't serve a
    stale app.js that posts an outdated payload shape (observed as 422s)."""
    client = _client(monkeypatch, tmp_path)
    assert client.get("/").headers["cache-control"] == "no-cache"
    res = client.get("/static/app.js")
    assert res.status_code == 200
    assert res.headers["cache-control"] == "no-cache"


def test_generate_endpoint_accepts_json_body(monkeypatch, tmp_path):
    """POST /api/generate must parse its JSON body — GeneratePayload used to
    be function-local and FastAPI degraded it to a query param (all
    generates returned 422). Incomplete LLM config is fine here: we only
    assert the payload is understood (400, not 422)."""
    client = _client(monkeypatch, tmp_path)
    res = client.post("/api/generate", json={
        "project_name": "Test Bank DR",
        "client_name": "ACME",
        "language": "en", "profile": "generic-enterprise"})
    assert res.status_code == 400, res.text  # 400 = config check; 422 would be the old bug
