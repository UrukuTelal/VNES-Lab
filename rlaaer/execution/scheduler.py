"""Scheduler — priority job queue, worker pool, retries, and resource allocation."""

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Callable, Any

from rlaaer.config import REPO_ROOT
from rlaaer.execution.runner import Runner, RunnerError
from rlaaer.registry import ExperimentRegistry


SCHEDULER_DIR = os.path.join(REPO_ROOT, "rlaaer", "data", "scheduler")
JOBS_DIR = os.path.join(SCHEDULER_DIR, "jobs")


class ScheduleError(Exception):
    """Raised on scheduler failures."""


@dataclass
class Job:
    experiment_id: str
    priority: int = 2          # 0=critical, 1=high, 2=normal, 3=low
    max_retries: int = 3
    timeout_minutes: float = 60.0
    status: str = "queued"     # queued, running, completed, failed, cancelled
    retry_count: int = 0
    created_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    result: dict | None = None
    error: str | None = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    @property
    def file_path(self) -> str:
        return os.path.join(JOBS_DIR, f"{self.experiment_id}.json")

    def save(self):
        os.makedirs(JOBS_DIR, exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2, default=str)

    @classmethod
    def load(cls, experiment_id: str) -> "Job | None":
        path = os.path.join(JOBS_DIR, f"{experiment_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)

    @classmethod
    def list_all(cls) -> list["Job"]:
        os.makedirs(JOBS_DIR, exist_ok=True)
        jobs = []
        for fn in sorted(os.listdir(JOBS_DIR)):
            if fn.endswith(".json"):
                path = os.path.join(JOBS_DIR, fn)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    jobs.append(cls(**data))
                except (json.JSONDecodeError, OSError):
                    continue
        return jobs

    def delete(self):
        if os.path.exists(self.file_path):
            os.remove(self.file_path)


class Worker:
    """Executes a single job: runs the experiment, updates registry, handles retries."""

    def __init__(self, runner: Runner | None = None, registry: ExperimentRegistry | None = None):
        self.runner = runner or Runner()
        self.registry = registry or ExperimentRegistry()

    def execute(self, job: Job) -> Job:
        """Run the job. Returns updated Job with result or error."""
        job.started_at = datetime.now(timezone.utc).isoformat()
        job.status = "running"
        job.save()

        try:
            result = self.runner.run(job.experiment_id)
            job.result = result
            status = result.get("status", "completed")
            if status in ("completed", "published"):
                job.status = "completed"
            elif status == "timeout":
                job.status = "timeout"
            else:
                job.status = "error"
                job.error = result.get("error") or f"Unknown status: {status}"
        except RunnerError as e:
            job.status = "error"
            job.error = str(e)
        except Exception as e:
            job.status = "error"
            job.error = f"{type(e).__name__}: {e}"

        job.completed_at = datetime.now(timezone.utc).isoformat()
        job.save()

        if job.status == "completed":
            self.registry.update_status(job.experiment_id, "executing")
            result = job.result or {}
            self.registry.update_status(job.experiment_id, result.get("status", "completed"), detail=result)

        return job


class Scheduler:
    """Manages job queue, worker pool, retries, and prioritization."""

    def __init__(self, max_workers: int = 2, registry: ExperimentRegistry | None = None):
        self.max_workers = max_workers
        self.registry = registry or ExperimentRegistry()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._futures: dict[str, Future] = {}
        self._lock = threading.Lock()
        os.makedirs(JOBS_DIR, exist_ok=True)

    # ── Queue Management ──────────────────────────────────────

    def enqueue(self, experiment_id: str, priority: int = 2, max_retries: int = 3,
                timeout_minutes: float = 60.0) -> Job:
        """Add an experiment to the queue."""
        if Job.load(experiment_id) is not None:
            raise ScheduleError(f"Experiment {experiment_id} already queued")

        job = Job(
            experiment_id=experiment_id,
            priority=priority,
            max_retries=max_retries,
            timeout_minutes=timeout_minutes,
        )
        job.save()
        return job

    def cancel(self, experiment_id: str) -> Job | None:
        """Cancel a queued (not running) job."""
        with self._lock:
            if experiment_id in self._futures:
                future = self._futures[experiment_id]
                if not future.done():
                    cancelled = future.cancel()
                    if cancelled:
                        job = Job.load(experiment_id)
                        if job:
                            job.status = "cancelled"
                            job.completed_at = datetime.now(timezone.utc).isoformat()
                            job.save()
                        del self._futures[experiment_id]
                        return job
            job = Job.load(experiment_id)
            if job and job.status == "queued":
                job.status = "cancelled"
                job.completed_at = datetime.now(timezone.utc).isoformat()
                job.save()
                return job
        return None

    def set_priority(self, experiment_id: str, priority: int) -> Job:
        """Change priority of a queued job."""
        job = Job.load(experiment_id)
        if not job:
            raise ScheduleError(f"Job {experiment_id} not found")
        if job.status != "queued":
            raise ScheduleError(f"Cannot reprioritize job in status '{job.status}'")
        job.priority = priority
        job.save()
        return job

    def job_status(self, experiment_id: str) -> Job | None:
        """Get job status."""
        return Job.load(experiment_id)

    def list_jobs(self, status: str | None = None) -> list[Job]:
        """List all jobs, optionally filtered by status."""
        jobs = Job.list_all()
        if status:
            jobs = [j for j in jobs if j.status == status]
        jobs.sort(key=lambda j: (j.priority, j.created_at))
        return jobs

    def clear_completed(self):
        """Remove completed/failed/cancelled jobs from the queue."""
        for job in Job.list_all():
            if job.status in ("completed", "failed", "cancelled", "timeout"):
                job.delete()

    # ── Execution ─────────────────────────────────────────────

    def _process_backlog(self):
        """Pick the highest-priority queued job and submit it to the worker pool."""
        with self._lock:
            running_count = sum(1 for f in self._futures.values() if not f.done())
            if running_count >= self.max_workers:
                return

            queued = self.list_jobs(status="queued")
            if not queued:
                return

            # Find a job not already tracked
            for job in queued:
                if job.experiment_id not in self._futures:
                    self._submit_job(job)
                    return

    def _submit_job(self, job: Job):
        """Submit a job to the worker pool."""
        worker = Worker(registry=self.registry)
        future = self._executor.submit(worker.execute, job)
        self._futures[job.experiment_id] = future

    def tick(self):
        """Process backlog and check for completions/retries. Call periodically."""
        self._process_backlog()
        self._check_completions()

    def _check_completions(self):
        """Check for completed futures, handle retries."""
        with self._lock:
            done_ids = [eid for eid, f in self._futures.items() if f.done()]
            for eid in done_ids:
                future = self._futures.pop(eid)
                job = Job.load(eid)
                if job and job.status in ("error", "timeout") and job.retry_count < job.max_retries:
                    job.retry_count += 1
                    job.status = "queued"
                    job.save()
                    self._submit_job(job)

    def run_until_complete(self, timeout_sec: float = 300.0) -> list[Job]:
        """Synchronously drain the queue: process all jobs until done or timeout."""
        start = time.time()
        while True:
            if time.time() - start > timeout_sec:
                break
            self.tick()
            remaining = [j for j in Job.list_all() if j.status not in ("completed", "failed", "cancelled", "timeout")]
            if not remaining:
                break
            time.sleep(0.5)
        return Job.list_all()

    def shutdown(self, wait: bool = True):
        """Shut down the executor."""
        self._executor.shutdown(wait=wait)
