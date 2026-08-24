"""In-memory generation job manager (threaded, SSE-friendly)."""
from __future__ import annotations

import asyncio
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

MAX_EVENTS_PER_JOB = 500  # trim older events so long-running jobs don't grow forever


class JobConcurrencyError(RuntimeError):
    """Too many jobs are running at once; caller should answer HTTP 429."""


class JobCapacityError(RuntimeError):
    """Job store is full with nothing evictable; caller should answer HTTP 503."""


@dataclass
class Job:
    id: str
    kind: str  # generate | demo
    project_name: str = ""
    created_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending | running | done | error | cancelled
    error: str = ""
    summary: dict = field(default_factory=dict)
    run_dir: str = ""
    events: List[dict] = field(default_factory=list)
    cancel_requested: bool = False
    _dropped: int = field(default=0, repr=False)  # events trimmed off the head
    _cond: threading.Condition = field(default_factory=threading.Condition, repr=False)
    # Async wakeup plumbing for SSE streams (see attach_async / detach_async).
    # A list of (loop, event) waiters: several browsers tabs may stream the
    # same job, and a single slot let one listener detach-blind the other.
    _waiters: List[Tuple[asyncio.AbstractEventLoop, asyncio.Event]] = field(
        default_factory=list, repr=False)

    # -- events -----------------------------------------------------------
    @property
    def total_events(self) -> int:
        with self._cond:
            return self._dropped + len(self.events)

    def emit(self, event: dict) -> None:
        event = {**event, "ts": time.time()}
        with self._cond:
            self.events.append(event)
            if len(self.events) > MAX_EVENTS_PER_JOB:
                drop = len(self.events) - MAX_EVENTS_PER_JOB
                del self.events[:drop]
                self._dropped += drop
            self._cond.notify_all()
        self._wake_async()

    def events_since(self, pos: int) -> Tuple[int, List[dict]]:
        """Return (new_pos, events) appended since absolute position `pos`.

        Positions are absolute (compensated for trimmed head events), so
        consumers resume without repeats even after trimming.
        """
        with self._cond:
            end = self._dropped + len(self.events)
            if end <= pos:
                return pos, []
            start = max(pos - self._dropped, 0)
            return end, list(self.events[start:])

    # -- async wakeup -------------------------------------------------------
    def attach_async(self) -> asyncio.Event:
        """Bind an asyncio.Event on the current loop so worker threads can wake
        this SSE stream via call_soon_threadsafe (no threadpool token held)."""
        event = asyncio.Event()
        self._waiters.append((asyncio.get_running_loop(), event))
        return event

    def detach_async(self, event: Optional[asyncio.Event] = None) -> None:
        """Remove one waiter (the given event, or all — e.g. on job teardown)."""
        if event is None:
            self._waiters.clear()
        else:
            self._waiters = [(l, ev) for l, ev in self._waiters if ev is not event]

    def _wake_async(self) -> None:
        """Thread-safe nudge for async waiters (called from worker threads)."""
        for loop, aevent in list(self._waiters):
            try:
                loop.call_soon_threadsafe(aevent.set)
            except RuntimeError:
                pass  # that waiter's event loop is closed; its stream is gone

    # -- lifecycle ----------------------------------------------------------
    def begin(self) -> bool:
        """Transition pending -> running. Returns False if already cancelled."""
        with self._cond:
            if self.cancel_requested:
                self.status = "cancelled"
                self._cond.notify_all()
                cancelled = True
            else:
                self.status = "running"
                self._cond.notify_all()
                cancelled = False
        if cancelled:
            self._wake_async()
        return not cancelled

    def request_cancel(self) -> bool:
        """Best-effort cancellation.

        NOTE: the pipeline lives in pipeline.py, which exposes no cancellation
        hook we could call from here, so an in-flight LLM stage always runs to
        completion before the job settles. This flag reliably cancels a job
        that has not started executing yet and surfaces intent in the API/UI.
        """
        with self._cond:
            self.cancel_requested = True
            if self.status == "pending":
                self.status = "cancelled"
            self._cond.notify_all()
        self._wake_async()
        return self.status == "cancelled"


class JobManager:
    MAX_JOBS = 200   # evict oldest finished jobs beyond this to bound memory
    MAX_RUNNING = 2  # hard cap on simultaneously running pipelines

    ACTIVE_STATUSES = ("pending", "running")
    TERMINAL_STATUSES = ("done", "error", "cancelled")

    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._evicted: Dict[str, None] = {}  # insertion-ordered memory of evicted ids
        self._lock = threading.Lock()

    def _active_count_locked(self) -> int:
        return sum(1 for j in self._jobs.values() if j.status in self.ACTIVE_STATUSES)

    def _remember_evicted_locked(self, job_id: str) -> None:
        self._evicted[job_id] = None
        while len(self._evicted) > self.MAX_JOBS:
            self._evicted.pop(next(iter(self._evicted)))

    def create(self, kind: str, project_name: str) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], kind=kind, project_name=project_name)
        with self._lock:
            if self._active_count_locked() >= self.MAX_RUNNING:
                raise JobConcurrencyError(
                    f"At most {self.MAX_RUNNING} jobs may run at once — "
                    "wait for a running job to finish.")
            if len(self._jobs) >= self.MAX_JOBS:
                finished = sorted(
                    (j for j in self._jobs.values() if j.status not in self.ACTIVE_STATUSES),
                    key=lambda j: j.created_at,
                )
                need = len(self._jobs) - self.MAX_JOBS + 1
                for old in finished[:need]:
                    del self._jobs[old.id]
                    self._remember_evicted_locked(old.id)
            if len(self._jobs) >= self.MAX_JOBS:
                raise JobCapacityError(
                    f"Job history is full ({self.MAX_JOBS} active jobs) — try again later.")
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, limit: int = 50) -> List[Job]:
        """Jobs for the /api/jobs listing: active first (oldest first, so the
        longest-waiting job leads), then finished newest-first."""
        with self._lock:
            jobs = list(self._jobs.values())
        active = sorted((j for j in jobs if j.status in self.ACTIVE_STATUSES),
                        key=lambda j: j.created_at)
        finished = sorted((j for j in jobs if j.status not in self.ACTIVE_STATUSES),
                          key=lambda j: j.created_at, reverse=True)
        return (active + finished)[:max(1, limit)]

    def was_evicted(self, job_id: str) -> bool:
        """True if this id belonged to a job we evicted (=> HTTP 410 for pollers)."""
        with self._lock:
            return job_id in self._evicted

    def start(self, job: Job, target) -> None:
        def runner():
            if not job.begin():  # cancelled while still queued
                return
            try:
                result = target(job)
                job.summary = result
                docx = result.get("docx") if isinstance(result, dict) else None
                job.run_dir = str(Path(docx).parent) if docx else ""
                job.status = "done"
                job.emit({"type": "done", "summary": result})
            except Exception as exc:  # noqa: BLE001 — surfaced to the browser
                job.error = f"{type(exc).__name__}: {exc}"
                job.status = "error"
                job.emit({"type": "error", "error": job.error})

        threading.Thread(target=runner, daemon=True).start()


manager = JobManager()
