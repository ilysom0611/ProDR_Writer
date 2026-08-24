"""Web UI server (FastAPI): config, generation with live progress, history, download."""
from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import sys
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp

from ..config import AppConfig, test_connection
from ..profiles import list_profiles
from ..schemas import ProjectInput
from .jobs import JobCapacityError, JobConcurrencyError, manager as _manager

STATIC_DIR = Path(__file__).parent / "static"

LOOPBACK_HOSTS = ["localhost", "127.0.0.1", "::1"]
_SK_RE = re.compile(r"sk-[A-Za-z0-9]{8,}")
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def _bind_host(explicit: Optional[str] = None) -> str:
    """Host the UI is served on.

    Resolution order: create_app(host=...) argument (the real uvicorn bind,
    passed by cli.py) > PRODR_WEB_HOST env (set by start.sh / start.bat) >
    PRODR_HOST env > loopback. An unknown bind must fail closed: policy below
    treats anything not provably loopback as token-required.
    """
    return (explicit
            or os.environ.get("PRODR_WEB_HOST")
            or os.environ.get("PRODR_HOST")
            or "127.0.0.1").strip()


def _is_loopback(host: str) -> bool:
    return host in ("localhost", "::1") or host.startswith("127.")


class _BearerTokenMiddleware(BaseHTTPMiddleware):
    """Require `Authorization: Bearer <token>` on every /api/* route.

    The SSE route also accepts ?token= because EventSource cannot send custom
    headers; tokens may then appear in access logs — an accepted trade-off for
    a single-user local tool.
    """

    def __init__(self, app: ASGIApp, token: str):
        super().__init__(app)
        self._token = token.encode()

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/"):
            auth = request.headers.get("authorization", "")
            supplied = auth[7:].strip() if auth.lower().startswith("bearer ") \
                else request.query_params.get("token", "")
            if not secrets.compare_digest(supplied.encode(), self._token):
                return JSONResponse(
                    {"detail": "Unauthorized — missing or invalid API token "
                               "(set via the PRODR_WEB_TOKEN environment variable)."},
                    status_code=401)
        return await call_next(request)


def _redact(message: str, api_key: Optional[str]) -> str:
    """Strip anything secret-looking from a provider error before it reaches
    the browser (litellm errors can embed base_url/api_key verbatim)."""
    redacted = _SK_RE.sub("sk-***", message)
    if api_key:
        redacted = redacted.replace(api_key, "***")
    return redacted


def _classify_provider_error(message: str) -> str:
    low = message.lower()
    if "timed out" in low or "timeout" in low:
        return "Connection timed out"
    if any(s in low for s in ("401", "403", "unauthorized", "invalid api key",
                              "incorrect api key", "authentication", "forbidden")):
        return "Authentication failed"
    if any(s in low for s in ("connection", "getaddrinfo", "name or service not known",
                              "refused", "ssl", "unreachable", "network")):
        return "Connection failed"
    return "Request failed"


def _docx_in(run_dir: str) -> Optional[Path]:
    d = Path(run_dir)
    if not d.is_dir():
        return None
    docx = sorted(d.glob("*.docx"), key=lambda p: p.stat().st_mtime)
    return docx[-1] if docx else None


def _public_summary(summary: dict) -> dict:
    """Summary safe for browsers: never leak absolute filesystem paths."""
    public = dict(summary or {})
    docx = public.get("docx")
    if docx:
        parts = Path(str(docx)).parts
        # only <run-dir-name>/<file>.docx relative to the output directory
        public["docx"] = "/".join(parts[-2:]) if len(parts) >= 2 else parts[-1]
    else:
        public.pop("docx", None)
    return public


def _resolve_output_dir(output_dir: str) -> Path:
    """Resolve the configured output dir; relative paths anchor to the project
    root (the repo checkout) rather than wherever the server was launched from,
    so manually-started servers see the same history as start.sh does."""
    path = Path(output_dir or "outputs")
    if not path.is_absolute():
        path = STATIC_DIR.parent.parent.parent / path
    return path.resolve()


def create_app(host: Optional[str] = None) -> FastAPI:
    # `host` must be what uvicorn will ACTUALLY bind — deriving it from the
    # environment alone let `prodr-writer web --host 0.0.0.0` run with the app
    # still believing it was loopback (no token middleware + localhost-only
    # Host allowlist), which both broke LAN serving and enabled an auth bypass.
    bind = _bind_host(host)
    token = os.environ.get("PRODR_WEB_TOKEN", "").strip()
    if not _is_loopback(bind) and not token:
        print(f"[ProDR_Writer] Refusing to start: binding to {bind} requires "
              "the PRODR_WEB_TOKEN environment variable.", file=sys.stderr)
        raise SystemExit(2)
    host = bind

    # -- Host allowlist + token policy ------------------------------------
    if _is_loopback(host):
        allowed_hosts = list(LOOPBACK_HOSTS)
    elif host in ("0.0.0.0", "::"):
        # Wildcard bind: Host-header validation cannot enumerate clients, and
        # serving unauthenticated would expose the stored API key config.
        if not token:
            print(f"[ProDR_Writer] Refusing to start: binding to {host} requires "
                  "the PRODR_WEB_TOKEN environment variable.", file=sys.stderr)
            raise SystemExit(2)
        allowed_hosts = ["*"]  # token auth protects every /api/* endpoint
    else:
        if not token:
            print(f"[ProDR_Writer] Refusing to start: non-loopback bind ({host}) "
                  "requires the PRODR_WEB_TOKEN environment variable.", file=sys.stderr)
            raise SystemExit(2)
        allowed_hosts = LOOPBACK_HOSTS + [host]

    app = FastAPI(title="ProDR_Writer", version="2.0")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    if token:
        app.add_middleware(_BearerTokenMiddleware, token=token)

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
        cfg = AppConfig.load()
        ok, message = test_connection(cfg)
        if ok:
            return {"ok": True, "message": message}
        # Provider exceptions can embed the URL / api key — redact + classify.
        detail = _redact(message, cfg.llm.api_key)
        return {"ok": False, "message": _classify_provider_error(detail), "detail": detail}

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

    def _create_job(kind: str, project_name: str) -> dict:
        try:
            job = _manager.create(kind, project_name)
        except JobConcurrencyError as exc:
            raise HTTPException(status_code=429, detail=str(exc))
        except JobCapacityError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        return job

    @app.post("/api/generate")
    def generate(payload: GeneratePayload):
        from ..pipeline import Pipeline

        cfg = AppConfig.load({"language": payload.language, "profile": payload.profile})
        if not cfg.llm.is_complete():
            raise HTTPException(status_code=400, detail=(
                "LLM configuration is incomplete — set base_url / api_key / model "
                "on the Configuration tab first."))
        inputs = ProjectInput(**payload.model_dump())
        job = _create_job("generate", inputs.project_name)
        _manager.start(job, lambda j: Pipeline(cfg, notify=j.emit).run(inputs)[1])
        return {"job_id": job.id}

    @app.post("/api/demo")
    def demo(payload: dict = {}):
        from ..pipeline import run_demo

        cfg = AppConfig.load({"language": (payload or {}).get("language") or "en",
                              "profile": (payload or {}).get("profile") or "generic-enterprise"})
        cfg.output_dir = cfg.output_dir or "outputs"
        job = _create_job("demo", "Demo proposal")
        _manager.start(job, lambda j: run_demo(cfg, notify=j.emit)[1])
        return {"job_id": job.id}

    # -- jobs / progress / history --------------------------------------------
    @app.get("/api/jobs/{job_id}/events")
    async def events(job_id: str, request: Request):
        job = _manager.get(job_id)
        if not job:
            status_code = 410 if _manager.was_evicted(job_id) else 404
            raise HTTPException(status_code=status_code, detail="Unknown or expired job")

        async def stream():
            waiter = job.attach_async()  # worker threads wake us without blocking a thread
            pos = 0
            started = time.monotonic()
            try:
                while True:
                    if await request.is_disconnected():
                        return
                    if pos >= job.total_events:
                        try:
                            await asyncio.wait_for(waiter.wait(), timeout=5.0)
                        except asyncio.TimeoutError:
                            pass
                        waiter.clear()
                    pos, fresh = job.events_since(pos)
                    for event in fresh:
                        yield f"data: {json.dumps(event)}\n\n"
                        if event["type"] in ("done", "error", "cancelled"):
                            return
                    if job.status in _manager.TERMINAL_STATUSES and pos >= job.total_events:
                        yield f"data: {json.dumps({'type': job.status, 'summary': _public_summary(job.summary), 'error': job.error})}\n\n"
                        return
                    if time.monotonic() - started > 1800:  # cap stalled streams at 30 min
                        yield 'data: {"type": "error", "error": "timeout"}\n\n'
                        return
            finally:
                job.detach_async(waiter)

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str):
        job = _manager.get(job_id)
        if not job:
            status_code = 410 if _manager.was_evicted(job_id) else 404
            raise HTTPException(status_code=status_code, detail="Unknown or expired job")
        return {"id": job.id, "status": job.status, "kind": job.kind,
                "project_name": job.project_name, "error": job.error,
                "cancel_requested": job.cancel_requested,
                "summary": _public_summary(job.summary)}

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str):
        """Best-effort cancel: stops queued jobs outright; for running jobs the
        pipeline has no hook we may call, so the current stage finishes first."""
        job = _manager.get(job_id)
        if not job:
            status_code = 410 if _manager.was_evicted(job_id) else 404
            raise HTTPException(status_code=status_code, detail="Unknown or expired job")
        cancelled = job.request_cancel()
        return {"id": job.id, "status": job.status,
                "cancel_requested": job.cancel_requested,
                "detail": "Job cancelled." if cancelled else
                          "Cancellation requested — the in-flight pipeline stage will finish first."}

    @app.get("/api/history")
    def history(limit: int = 30):
        limit = max(1, min(limit, 200))  # clamp: negative limit truncated the wrong end
        cfg = AppConfig.load()
        out_dir = _resolve_output_dir(cfg.output_dir)
        runs = []
        if out_dir.is_dir():
            entries = []
            for run_dir in out_dir.iterdir():
                try:
                    mtime = run_dir.stat().st_mtime
                    if not run_dir.is_dir():
                        continue
                except OSError:
                    continue  # entry vanished mid-listing
                entries.append((mtime, run_dir))
            entries.sort(key=lambda item: item[0], reverse=True)
            for _, run_dir in entries[:limit]:
                run_json = run_dir / "run.json"
                entry = {"name": run_dir.name, "path": "", "status": "unknown"}
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
        # Reject separators, traversal and Windows drive-relative names up front;
        # resolved containment below is the primary guard.
        if ("/" in name or "\\" in name or ".." in name or ":" in name
                or _WINDOWS_DRIVE_RE.match(name)):
            raise HTTPException(status_code=400, detail="Invalid run name")
        cfg = AppConfig.load()
        out_dir = _resolve_output_dir(cfg.output_dir)
        target = (out_dir / name).resolve()
        if not target.is_relative_to(out_dir):  # e.g. Path("outputs")/"C:" -> "C:"
            raise HTTPException(status_code=400, detail="Invalid run name")
        docx = _docx_in(str(target))
        if not docx:
            raise HTTPException(status_code=404, detail="No document in this run directory")
        return FileResponse(docx, filename=docx.name,
                            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    return app
