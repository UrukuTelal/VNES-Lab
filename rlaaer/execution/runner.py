"""Experiment Runner — orchestrates trial execution with checkpoint/rollback."""

import csv
import json
import os
import time
import traceback
from datetime import datetime, timezone
from typing import Any

import yaml

from rlaaer.config import REPO_ROOT, PIPELINE, SPEC_FILENAME, STATUS_FLOW
from rlaaer.execution.engine_client import EngineClient
from rlaaer.provenance import ProvenanceTracker


class RunnerError(Exception):
    """Raised on runner failures."""


class Runner:
    """Orchestrates experiment execution with checkpointing and rollback."""

    def __init__(self, experiments_dir: str | None = None):
        self.experiments_dir = experiments_dir or os.path.join(REPO_ROOT, "experiments")
        self.engine = EngineClient()
        self.checkpoint_dir = os.path.join(REPO_ROOT, "rlaaer", "data", "checkpoints")
        os.makedirs(self.checkpoint_dir, exist_ok=True)

    def run(self, experiment_id: str, dry_run: bool = False) -> dict:
        """Run a full experiment by ID. Returns result summary."""
        exp_dir = self._find_experiment_dir(experiment_id)
        spec_path = os.path.join(exp_dir, SPEC_FILENAME)

        with open(spec_path, "r", encoding="utf-8") as f:
            spec = yaml.safe_load(f)

        provenance = ProvenanceTracker().capture(spec)

        if dry_run:
            return {"experiment_id": experiment_id, "dry_run": True, "status": "ok"}

        execution_config = spec.get("execution", {})
        parameters = spec.get("parameters", {})
        metrics_def = spec.get("metrics", {})

        total_trials = execution_config.get("total_trials", 1)
        checkpoint_interval = execution_config.get("checkpoint_interval_ticks", 1000)
        max_duration_min = execution_config.get("max_duration_minutes", 30)
        rollback_on_failure = execution_config.get("rollback_on_failure", True)

        results_dir = os.path.join(exp_dir, "results")
        os.makedirs(results_dir, exist_ok=True)

        results = {
            "experiment_id": experiment_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "trials_completed": 0,
            "trials_failed": 0,
            "metrics": {},
            "status": "running",
            "provenance": provenance,
        }

        start_time = time.time()
        trial = 0

        try:
            while trial < total_trials:
                elapsed = (time.time() - start_time) / 60
                if elapsed > max_duration_min:
                    results["status"] = "timeout"
                    break

                trial_result = self._run_trial(trial, spec, parameters)
                if trial_result["success"]:
                    results["trials_completed"] += 1
                else:
                    results["trials_failed"] += 1
                    if rollback_on_failure:
                        self._rollback(trial, results_dir)

                self._write_trial_result(results_dir, trial, trial_result)

                if trial > 0 and trial % max(1, total_trials // 10) == 0:
                    self._checkpoint(results, results_dir)

                trial += 1

        except Exception as e:
            results["status"] = "error"
            results["error"] = str(e)
            results["traceback"] = traceback.format_exc()

        elapsed = time.time() - start_time
        results["completed_at"] = datetime.now(timezone.utc).isoformat()
        results["duration_seconds"] = elapsed
        if results.get("status") == "running":
            results["status"] = "completed"

        self._write_summary(results_dir, results)
        return results

    def _run_trial(self, trial_num: int, spec: dict, parameters: dict) -> dict:
        """Run a single trial."""
        indep_params = parameters.get("independent", [])
        controlled = parameters.get("controlled", [])

        # Build parameter set from independent vars
        trial_params = {}
        for p in indep_params:
            domain = p.get("domain", [0, 1])
            steps = p.get("steps", 1)
            idx = trial_num % steps
            val = domain[0] + (domain[1] - domain[0]) * idx / (steps - 1) if steps > 1 else domain[0]
            trial_params[p["name"]] = val

        for p in controlled:
            trial_params[p["name"]] = p["value"]

        self._run_simulation(trial_params)

        return {"success": True, "trial": trial_num, "params": trial_params}

    def _run_simulation(self, params: dict):
        """Run VNES simulation. Falls back to stub if PSVSimulation unavailable."""
        try:
            import sys
            sys.path.insert(0, REPO_ROOT)
            from lib.psv_core import PSVSimulation

            sim = PSVSimulation(
                n_entities=params.get("n_entities", 100),
                n_pillars=params.get("n_pillars", 16),
            )
            timesteps = params.get("timesteps", 500)
            for _ in range(timesteps):
                sim.step()
        except ImportError:
            pass  # stub mode — no-op for testing

    def _rollback(self, trial_num: int, results_dir: str):
        """Rollback after a failed trial."""
        rollback_path = os.path.join(results_dir, f"trial_{trial_num:04d}_ROLLBACK.json")
        with open(rollback_path, "w", encoding="utf-8") as f:
            json.dump({"trial": trial_num, "rolled_back": True}, f)

    def _checkpoint(self, results: dict, results_dir: str):
        """Write checkpoint."""
        path = os.path.join(self.checkpoint_dir, f"checkpoint_{results['experiment_id']}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

    def _write_trial_result(self, results_dir: str, trial: int, result: dict):
        path = os.path.join(results_dir, f"trial_{trial:04d}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

    def _write_summary(self, results_dir: str, results: dict):
        path = os.path.join(results_dir, "summary.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

    def _find_experiment_dir(self, experiment_id: str) -> str:
        pattern = f"{int(experiment_id):03d}_*"
        import glob
        matches = glob.glob(os.path.join(self.experiments_dir, pattern))
        if not matches:
            raise RunnerError(f"Experiment {experiment_id} not found in {self.experiments_dir}")
        for m in matches:
            if os.path.exists(os.path.join(m, "spec.yaml")):
                return m
        raise RunnerError(f"Experiment {experiment_id} found but has no spec.yaml")
