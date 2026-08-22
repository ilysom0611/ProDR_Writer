"""In-memory generation job manager (threaded, SSE-friendly)."""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class Job:
    id: str
    kind: str  # generate | demo
    project_name: str = ""
    created_at: float = field(default_factory=time.time)
    status: str = "running"  # running | done | error
    error: str = ""
    summary: dict = field(default_factory=dict)
    run_dir: str = ""
    events: List[dict] = field(default_factory=list)
    _cond: threading.Condition = field(default_factory= threading.Condition, repr=False)

    def emit(self, event: dict) -> None:
        event = {**event, "ts": time.time()}
        with self._cond:
            self.events.append(event)
            self._cond.notify_all()

    def wait_event(self, after_index: int, timeout: float = 15.0):
        """Block until an event newer than `after_index` exists.

        Returns (next_index, event) so callers can resume without repeats.
        """
        with self._cond:
            if len(self.events) <= after_index:
                self._cond.wait(timeout)
            if len(self.events) > after_index:
                return after_index + 1, self.events[after_index]
        return None


class JobManager:
    MAX_JOBS = 200  # evict oldest finished jobs beyond this to bound memory

    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, kind: str, project_name: str) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], kind=kind, project_name=project_name)
        with self._lock:
            if len(self._jobs) >= self.MAX_JOBS:
                finished = sorted(
                    (j for j in self._jobs.values() if j.status != "running"),
                    key=lambda j: j.created_at,
                )
                for old in finished[: len(self._jobs) - self.MAX_JOBS + 1]:
                    del self._jobs[old.id]
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def start(self, job: Job, target) -> None:
        def runner():
            try:
                result = target(job)
                job.summary = result
                job.run_dir = str(Path(result["docx"]).parent)
                job.status = "done"
                job.emit({"type": "done", "summary": result})
            except Exception as exc:  # noqa: BLE001 — surfaced to the browser
                job.error = f"{type(exc).__name__}: {exc}"
                job.status = "error"
                job.emit({"type": "error", "error": job.error})

        threading.Thread(target=runner, daemon=True).start()


manager = JobManager()
