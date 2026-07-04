"""Tests for the Scheduler."""

import os
import json
import tempfile
import time
import threading
import pytest
import yaml

from rlaaer.execution.runner import Runner
from rlaaer.execution.scheduler import (
    Scheduler, Worker, Job, ScheduleError, JOBS_DIR, SCHEDULER_DIR,
)
from rlaaer.registry import ExperimentRegistry
from rlaaer.config import SPEC_FILENAME


SAMPLE_SPEC = {
    "experiment": {"id": "009", "title": "sched test", "status": "draft"},
    "systems": {"vnes_lab": {"enabled": True}},
    "parameters": {
        "independent": [
            {"name": "x", "domain": [0, 1], "steps": 2, "source": "test", "rationale": "test"},
        ],
        "controlled": [{"name": "seed", "value": 42}],
    },
    "execution": {
        "trials_per_condition": 2,
        "total_trials": 2,
        "max_duration_minutes": 5,
        "checkpoint_interval_ticks": 100,
        "rollback_on_failure": True,
    },
    "metrics": {},
    "statistics": {"alpha": 0.05},
    "review": {},
    "publication": {},
}


@pytest.fixture
def tmp_home():
    with tempfile.TemporaryDirectory() as td:
        old_jobs = JOBS_DIR
        old_sched = SCHEDULER_DIR
        import rlaaer.execution.scheduler as sched_mod
        new_jobs = os.path.join(td, "scheduler", "jobs")
        new_sched = os.path.join(td, "scheduler")
        os.makedirs(new_jobs, exist_ok=True)
        sched_mod.JOBS_DIR = new_jobs
        sched_mod.SCHEDULER_DIR = new_sched
        yield td
        sched_mod.JOBS_DIR = old_jobs
        sched_mod.SCHEDULER_DIR = old_sched


@pytest.fixture
def exp_dir(tmp_home):
    """Create a temporary experiment directory with spec.yaml."""
    base = os.path.join(tmp_home, "experiments")
    ed = os.path.join(base, "009_sched_test")
    os.makedirs(ed, exist_ok=True)
    with open(os.path.join(ed, SPEC_FILENAME), "w") as f:
        yaml.dump(SAMPLE_SPEC, f)
    return ed


@pytest.fixture
def runner(exp_dir):
    r = Runner()
    r.experiments_dir = os.path.dirname(exp_dir)
    r.checkpoint_dir = os.path.join(os.path.dirname(exp_dir), "checkpoints")
    os.makedirs(r.checkpoint_dir, exist_ok=True)
    return r


@pytest.fixture
def registry(tmp_home):
    db_path = os.path.join(tmp_home, "test.db")
    reg = ExperimentRegistry(db_path=db_path)
    reg.register(SAMPLE_SPEC, path=os.path.dirname(exp_dir.__func__) if hasattr(exp_dir, '__func__') else "")
    yield reg
    reg.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


# ── Job Tests ──────────────────────────────────────────────

class TestJob:
    def test_create_and_save(self, tmp_home):
        job = Job(experiment_id="009", priority=1)
        assert job.status == "queued"
        assert job.retry_count == 0
        job.save()
        assert os.path.exists(job.file_path)

    def test_load(self, tmp_home):
        job = Job(experiment_id="009", priority=2, max_retries=5)
        job.save()
        loaded = Job.load("009")
        assert loaded is not None
        assert loaded.experiment_id == "009"
        assert loaded.priority == 2
        assert loaded.max_retries == 5

    def test_load_nonexistent(self, tmp_home):
        assert Job.load("999") is None

    def test_list_all(self, tmp_home):
        j1 = Job(experiment_id="001")
        j1.save()
        j2 = Job(experiment_id="002")
        j2.save()
        jobs = Job.list_all()
        assert len(jobs) == 2
        ids = [j.experiment_id for j in jobs]
        assert "001" in ids
        assert "002" in ids

    def test_delete(self, tmp_home):
        job = Job(experiment_id="009")
        job.save()
        assert os.path.exists(job.file_path)
        job.delete()
        assert not os.path.exists(job.file_path)

    def test_status_property_defaults(self, tmp_home):
        job = Job(experiment_id="009")
        assert job.status == "queued"
        assert job.priority == 2
        assert job.max_retries == 3

    def test_created_at_auto(self, tmp_home):
        job = Job(experiment_id="009")
        assert job.created_at != ""


# ── Scheduler Tests ────────────────────────────────────────

class TestScheduler:
    def test_enqueue(self, tmp_home):
        sched = Scheduler(max_workers=1)
        job = sched.enqueue("009", priority=0)
        assert job.experiment_id == "009"
        assert job.priority == 0
        assert job.status == "queued"

    def test_enqueue_duplicate(self, tmp_home):
        sched = Scheduler(max_workers=1)
        sched.enqueue("009")
        with pytest.raises(ScheduleError, match="already queued"):
            sched.enqueue("009")

    def test_cancel_queued(self, tmp_home):
        sched = Scheduler(max_workers=1)
        sched.enqueue("009")
        cancelled = sched.cancel("009")
        assert cancelled is not None
        assert cancelled.status == "cancelled"
        job = sched.job_status("009")
        assert job.status == "cancelled"

    def test_cancel_nonexistent(self, tmp_home):
        sched = Scheduler(max_workers=1)
        assert sched.cancel("999") is None

    def test_set_priority(self, tmp_home):
        sched = Scheduler(max_workers=1)
        sched.enqueue("009", priority=2)
        sched.set_priority("009", 0)
        job = sched.job_status("009")
        assert job.priority == 0

    def test_set_priority_not_queued(self, tmp_home):
        sched = Scheduler(max_workers=1)
        sched.enqueue("009")
        sched.cancel("009")
        with pytest.raises(ScheduleError, match="Cannot reprioritize"):
            sched.set_priority("009", 0)

    def test_set_priority_nonexistent(self, tmp_home):
        sched = Scheduler(max_workers=1)
        with pytest.raises(ScheduleError, match="not found"):
            sched.set_priority("999", 0)

    def test_job_status(self, tmp_home):
        sched = Scheduler(max_workers=1)
        assert sched.job_status("009") is None
        sched.enqueue("009")
        assert sched.job_status("009") is not None

    def test_list_jobs(self, tmp_home):
        sched = Scheduler(max_workers=1)
        sched.enqueue("001")
        sched.enqueue("002")
        jobs = sched.list_jobs()
        assert len(jobs) == 2

    def test_list_jobs_filtered(self, tmp_home):
        sched = Scheduler(max_workers=1)
        sched.enqueue("001")
        sched.enqueue("002")
        sched.cancel("001")
        jobs = sched.list_jobs(status="queued")
        assert len(jobs) == 1
        assert jobs[0].experiment_id == "002"

    def test_clear_completed(self, tmp_home):
        sched = Scheduler(max_workers=1)
        sched.enqueue("001")
        sched.enqueue("002")
        sched.cancel("001")
        sched.clear_completed()
        jobs = sched.list_jobs()
        assert len(jobs) == 1
        assert jobs[0].experiment_id == "002"


# ── Worker Tests ───────────────────────────────────────────

class TestWorker:
    def test_execute_success(self, tmp_home, runner, exp_dir):
        from rlaaer.execution.scheduler import Worker, Job
        worker = Worker(runner=runner)
        job = Job(experiment_id="009")
        job.save()
        result = worker.execute(job)
        assert result.status == "completed"
        assert result.result is not None
        assert result.result["trials_completed"] == 2

    def test_execute_error(self, tmp_home, runner):
        from rlaaer.execution.scheduler import Worker, Job
        worker = Worker(runner=runner)
        job = Job(experiment_id="999")
        job.save()
        result = worker.execute(job)
        assert result.status == "error"
        assert result.error is not None

    def test_execute_creates_files(self, tmp_home, runner, exp_dir):
        from rlaaer.execution.scheduler import Worker, Job
        worker = Worker(runner=runner)
        job = Job(experiment_id="009")
        job.save()
        worker.execute(job)
        results_dir = os.path.join(exp_dir, "results")
        assert os.path.exists(results_dir)
        assert os.path.exists(os.path.join(results_dir, "summary.json"))


# ── Queue Drain Tests ──────────────────────────────────────

class TestQueueDrain:
    def test_drain_empty_queue(self, tmp_home):
        sched = Scheduler(max_workers=1)
        jobs = sched.run_until_complete(timeout_sec=5)
        assert isinstance(jobs, list)

    def test_drain_single_job(self, tmp_home, runner, exp_dir):
        sched = Scheduler(max_workers=1)
        sched.enqueue("009")
        from rlaaer.execution.scheduler import Worker

        def patched_submit(job):
            worker = Worker(runner=runner)
            future = sched._executor.submit(worker.execute, job)
            sched._futures[job.experiment_id] = future

        sched._submit_job = patched_submit
        jobs = sched.run_until_complete(timeout_sec=10)
        for j in jobs:
            if j.experiment_id == "009":
                import time
                for _ in range(20):
                    if j.status == "completed":
                        break
                    time.sleep(0.05)
                    j = sched.job_status("009")
                assert j.status == "completed"

    def test_cancel_before_execution(self, tmp_home):
        sched = Scheduler(max_workers=1)
        sched.enqueue("001")
        sched.cancel("001")
        jobs = sched.run_until_complete(timeout_sec=5)
        for j in jobs:
            if j.experiment_id == "001":
                assert j.status == "cancelled"

    def test_priority_ordering(self, tmp_home):
        sched = Scheduler(max_workers=1)
        sched.enqueue("low", priority=3)
        sched.enqueue("high", priority=0)
        sched.enqueue("medium", priority=2)
        jobs = sched.list_jobs()
        priorities = [j.priority for j in jobs]
        assert priorities == sorted(priorities)

    def test_shutdown(self, tmp_home):
        sched = Scheduler(max_workers=2)
        sched.enqueue("001")
        sched.shutdown(wait=True)
        # Should not raise
