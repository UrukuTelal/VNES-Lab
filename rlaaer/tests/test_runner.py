"""Tests for the Experiment Runner."""

import os
import tempfile
import pytest
import yaml

from rlaaer.execution.runner import Runner, RunnerError
from rlaaer.config import SPEC_FILENAME


class TestRunner:
    @pytest.fixture
    def runner(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            r = Runner()
            r.experiments_dir = os.path.join(tmpdir, "experiments")
            r.checkpoint_dir = os.path.join(tmpdir, "checkpoints")
            os.makedirs(r.checkpoint_dir, exist_ok=True)
            yield r

    @pytest.fixture
    def experiment_dir(self, runner):
        exp_dir = os.path.join(runner.experiments_dir, "009_test")
        os.makedirs(exp_dir, exist_ok=True)
        spec = {
            "experiment": {"id": "009", "title": "test"},
            "systems": {"vnes_lab": {"enabled": True}},
            "parameters": {
                "independent": [
                    {"name": "x", "domain": [0, 1], "steps": 2, "source": "test", "rationale": "test"},
                ],
                "controlled": [
                    {"name": "seed", "value": 42},
                ],
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
        with open(os.path.join(exp_dir, SPEC_FILENAME), "w") as f:
            yaml.dump(spec, f)
        return exp_dir

    def test_dry_run(self, runner, experiment_dir):
        result = runner.run("009", dry_run=True)
        assert result["dry_run"] is True
        assert result["status"] == "ok"

    def test_run_completes(self, runner, experiment_dir):
        result = runner.run("009", dry_run=False)
        assert result["trials_completed"] == 2
        assert result["trials_failed"] == 0
        assert result["status"] == "completed"

    def test_results_written(self, runner, experiment_dir):
        runner.run("009")
        results_dir = os.path.join(experiment_dir, "results")
        assert os.path.exists(results_dir)
        assert os.path.exists(os.path.join(results_dir, "trial_0000.json"))
        assert os.path.exists(os.path.join(results_dir, "trial_0001.json"))
        assert os.path.exists(os.path.join(results_dir, "summary.json"))

    def test_experiment_not_found(self, runner):
        with pytest.raises(RunnerError):
            runner.run("999")

    def test_checkpoint_written(self, runner, experiment_dir):
        runner.run("009")
        checkpoints = os.listdir(runner.checkpoint_dir)
        assert len(checkpoints) > 0

    def test_timeout_respected(self, runner, experiment_dir):
        spec_path = os.path.join(experiment_dir, SPEC_FILENAME)
        with open(spec_path) as f:
            spec = yaml.safe_load(f)
        spec["execution"]["total_trials"] = 1000000  # impossible
        spec["execution"]["max_duration_minutes"] = 0.001  # very short
        with open(spec_path, "w") as f:
            yaml.dump(spec, f)

        result = runner.run("009")
        assert result["status"] == "timeout"
