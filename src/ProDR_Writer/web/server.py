"""Web UI server (FastAPI): config, generation with live progress, history, download."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from ..config import AppConfig, test_connection
from ..profiles import list_profiles
from ..schemas import ProjectInput

STATIC_DIR = Path(__file__).parent / "static"


def _docx_in(run_dir: str) -> Optional[Path]:
    d = Path(run_dir)
    if not d.is_dir():
        return None
    docx = sorted(d.glob("*.docx"), key=lambda p: p.stat().st_mtime)
    return docx[-1] if docx else None


def create_app() -> FastAPI:
    app = FastAPI(title="ProDR_Writer", version="2.0")

    # -- static ---------------------------------------------------------
    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    from fastapi.staticfiles import StaticFiles

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # -- config -----------------------------------------------------------
    class ConfigPayload(BaseModel):
        base_url: str = ""
        api_key: Optional[str] = None  # None = keep existing
        model: str = ""
        temperature: float = 0.3
        language: str = "en"
        profile: str = "generic-enterprise"

    @app.get("/api/config")
    def get_config():
        cfg = AppConfig.load()
        key = cfg.llm.api_key
        return {
            "base_url": cfg.llm.base_url,
            "api_key_masked": ("***" + key[-4:]) if len(key) > 4 else "",
            "has_api_key": bool(key),
            "model": cfg.llm.model,
            "temperature": cfg.llm.temperature,
            "language": cfg.language,
            "profile": cfg.profile,
            "complete": cfg.llm.is_complete(),
        }

    @app.post("/api/config")
    def save_config(payload: ConfigPayload):
        cfg = AppConfig.load()
        cfg.llm.base_url = payload.base_url.strip()
        if payload.api_key:  # empty/None keeps the stored key
            cfg.llm.api_key = payload.api_key.strip()
        cfg.llm.model = payload.model.strip()
        cfg.llm.temperature = payload.temperature
        cfg.language = payload.language
        cfg.profile = payload.profile
        path = cfg.save()
        return {"saved": True, "path": str(path)}

    @app.post("/api/config/test")
    def test_config():
        ok, message = test_connection(AppConfig.load())
        return {"ok": ok, "message": message}

    @app.get("/api/meta")
    def meta():
        return {"profiles": list_profiles(), "languages": ["en", "zh"],
                "industries": ["general", "insurance", "banking", "healthcare",
                               "government", "telecom", "manufacturing", "retail", "energy"]}

    # -- generation --------------------------------------------------------
    class GeneratePayload(BaseModel):
        project_name: str
        client_name: str = ""
        vendor_name: str = ""
        industry: str = "general"
        overall_rto: str = "< 4 hours"
        overall_rpo: str = "< 1 hour"
        budget: str = ""
        language: str = "en"
        profile: str = "generic-enterprise"

    @app.post("/api/generate")
    def generate(payload: GeneratePayload):
        from ..pipeline import Pipeline

        cfg = AppConfig.load({"language": payload.language, "profile": payload.profile})
        if not cfg.llm.is_complete():
            raise HTTPException(status_code=400, detail=(
                "LLM configuration is incomplete — set base_url / api_key / model "
                "on the Configuration tab first."))
        inputs = ProjectInput(**payload.model_dump())
        job = _manager.create("generate", inputs.project_name)
        _manager.start(job, lambda j: Pipeline(cfg, notify=j.emit).run(inputs)[1])
        return {"job_id": job.id}

    @app.post("/api/demo")
    def demo(payload: dict = {}):
        from ..pipeline import run_demo

        cfg = AppConfig.load({"language": (payload or {}).get("language") or "en",
                              "profile": (payload or {}).get("profile") or "generic-enterprise"})
        cfg.output_dir = cfg.output_dir or "outputs"
        job = _manager.create("demo", "Demo proposal")
        _manager.start(job, lambda j: run_demo(cfg, notify=j.emit)[1])
        return {"job_id": job.id}

    # -- jobs / progress / history --------------------------------------------
    @app.get("/api/jobs/{job_id}/events")
    def events(job_id: str):
        job = _manager.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Unknown job")

        def stream():
            index = 0
            start = time.time()
            while True:
                got = job.wait_event(index, timeout=5.0)
                if got:
                    index, event = got
                    yield f"data: {json.dumps(event)}\n\n"
                    if event["type"] in ("done", "error"):
                        return
                elif job.status != "running" and index >= len(job.events):
                    yield f'data: {{"type": "{job.status}", "summary": {json.dumps(job.summary)}, "error": {json.dumps(job.error)}}}\n\n'
                    return
                elif time.time() - start > 1800:  # hard cap a stalled stream at 30 min
                    yield 'data: {"type": "error", "error": "timeout"}\n\n'
                    return

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str):
        job = _manager.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Unknown job")
        return {"id": job.id, "status": job.status, "kind": job.kind,
                "project_name": job.project_name, "error": job.error, "summary": job.summary}

    @app.get("/api/history")
    def history(limit: int = 30):
        cfg = AppConfig.load()
        out_dir = Path(cfg.output_dir)
        runs = []
        if out_dir.is_dir():
            for run_dir in sorted(out_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
                if not run_dir.is_dir():
                    continue
                run_json = run_dir / "run.json"
                entry = {"name": run_dir.name, "path": str(run_dir), "status": "unknown"}
                if run_json.exists():
                    try:
                        data = json.loads(run_json.read_text(encoding="utf-8"))
                        entry.update({
                            "status": data.get("status", "success"),
                            "project_name": data.get("input", {}).get("project_name"),
                            "language": data.get("language"),
                            "score": (data.get("review") or {}).get("score"),
                            "fatal_findings": sum(
                                1 for f in data.get("validation", {}).get("findings", [])
                                if f.get("severity") == "fatal") if data.get("validation") else None,
                        })
                    except (json.JSONDecodeError, OSError):
                        pass
                entry["downloadable"] = _docx_in(str(run_dir)) is not None
                runs.append(entry)
        return {"runs": runs}

    @app.get("/api/history/{name}/download")
    def download(name: str):
        if "/" in name or "\\" in name or ".." in name:
            raise HTTPException(status_code=400, detail="Invalid run name")
        cfg = AppConfig.load()
        docx = _docx_in(str(Path(cfg.output_dir) / name))
        if not docx:
            raise HTTPException(status_code=404, detail="No document in this run directory")
        return FileResponse(docx, filename=docx.name,
                            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    return app


from .jobs import manager as _manager  # noqa: E402  (single shared instance)
