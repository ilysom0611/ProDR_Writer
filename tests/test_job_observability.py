"""Observability regressions: job listing after refresh, retry visibility,
and failed runs appearing in history."""
import json

from fastapi.testclient import TestClient
from pydantic import BaseModel

from prodr_writer import llm as llm_mod
from prodr_writer.config import AppConfig
from prodr_writer.pipeline import Pipeline
from prodr_writer.schemas import ProjectInput
from prodr_writer.web.jobs import manager as job_manager
from prodr_writer.web.server import create_app


def _client(monkeypatch, tmp_path):
    monkeypatch.setattr("prodr_writer.config.CONFIG_FILE", tmp_path / "config.yaml")
    for var in ("PRODR_API_KEY", "PRODR_BASE_URL", "PRODR_MODEL"):
        monkeypatch.delenv(var, raising=False)
    return TestClient(create_app(host="127.0.0.1"), base_url="http://localhost")


def test_jobs_endpoint_lists_running_job(monkeypatch, tmp_path):
    """A refreshed browser must be able to rediscover its running job
    (GET /api/jobs) — previously the only handle was the page's memory."""
    client = _client(monkeypatch, tmp_path)
    job = job_manager.create("generate", "Refresh DR")
    try:
        res = client.get("/api/jobs")
        assert res.status_code == 200
        ids = [j["id"] for j in res.json()["jobs"]]
        assert job.id in ids
    finally:
        # keep other tests isolated from this stub job
        with job_manager._lock:
            job_manager._jobs.pop(job.id, None)


def test_run_stage_emits_retry_events(monkeypatch):
    """Provider errors are retried with backoff — the caller (web UI) must see
    a retry event instead of the stage silently hanging."""

    class Out(BaseModel):
        ok: bool = True

    attempts = {"n": 0}

    def fake_kickoff(self):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise ConnectionError("connection reset by peer")
        return type("R", (), {"raw": '{"ok": true}'})()

    class FakeCrew:
        def __init__(self, agents=None, tasks=None):
            pass
        kickoff = fake_kickoff

    monkeypatch.setattr(llm_mod, "Task", lambda **kw: object())
    monkeypatch.setattr(llm_mod, "Crew", FakeCrew)
    monkeypatch.setattr(llm_mod.time, "sleep", lambda s: None)  # no backoff wait

    events = []
    out = llm_mod.run_stage(None, "desc", "json", Out, "bia",
                            max_retries=2, notify=events.append)
    assert out.ok is True
    retries = [e for e in events if e["type"] == "retry"]
    assert len(retries) == 1
    assert retries[0]["stage"] == "bia"
    assert "ConnectionError" in retries[0]["reason"] or "provider" in retries[0]["reason"]


def test_failed_run_writes_error_run_json(tmp_path):
    """A failing stage must leave run.json with status:"error" so the run
    shows up in history with its failure reason — not vanish silently."""
    pipe = Pipeline(AppConfig(output_dir=str(tmp_path)))

    def boom(*a, **kw):
        raise RuntimeError("LLM endpoint unreachable")

    pipe._bia = boom  # fail at the first LLM stage
    try:
        pipe.run(ProjectInput(project_name="Acme DR"))
        raise AssertionError("run() should have raised")
    except RuntimeError:
        pass
    data = json.loads((pipe._prepare_run_dir(ProjectInput(project_name="Acme DR"))
                       / "run.json").read_text(encoding="utf-8"))
    assert data["status"] == "error"
    assert "LLM endpoint unreachable" in data["error"]
