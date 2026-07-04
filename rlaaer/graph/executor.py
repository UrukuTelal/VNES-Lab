"""DAG Executor — parallel experiment execution with dependency resolution.

Executes experiments in topological order, parallelizing independent branches.
Supports partial re-execution based on changed dependencies.
"""

import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from rlaaer.execution.runner import Runner, RunnerError
from rlaaer.execution.scheduler import Scheduler, Job
from rlaaer.graph.dag import DepGraph, DAGError
from rlaaer.registry import ExperimentRegistry


class DAGExecutor:
    """Executes experiments defined as a DAG, respecting dependency order.

    Features:
    - Topological sort execution
    - Parallel execution of independent branches
    - Partial re-execution (only changed ancestors)
    - Status tracking per experiment
    """

    def __init__(self, max_workers: int = 2, registry: ExperimentRegistry | None = None):
        self.max_workers = max_workers
        self.registry = registry or ExperimentRegistry()
        self.results: dict[str, dict] = {}

    def execute(self, dag: DepGraph, dry_run: bool = False,
                callback: Callable[[str, str, dict], None] | None = None,
                partial: bool = False) -> dict[str, dict]:
        """Execute all experiments in the DAG.

        Args:
            dag: The dependency graph to execute.
            dry_run: If True, validate without executing.
            callback: Optional callback(eid, status, result) per experiment.
            partial: If True, skip experiments whose dependencies haven't changed.

        Returns:
            dict mapping experiment_id -> result summary.
        """
        if not dag.is_valid():
            errors = dag.validate()
            raise DAGError(f"DAG validation failed: {'; '.join(errors)}")

        levels = dag.independent_branches()
        self.results = {}

        for level_idx, level in enumerate(levels):
            if dry_run:
                for eid in level:
                    self.results[eid] = {"experiment_id": eid, "dry_run": True, "status": "ok"}
                    if callback:
                        callback(eid, "dry_run", self.results[eid])
                continue

            # Check partial execution: skip if no ancestors changed
            if partial:
                non_skipped = []
                for eid in level:
                    if self._should_execute(dag, eid):
                        non_skipped.append(eid)
                    else:
                        prev = self.registry.get(eid)
                        self.results[eid] = {"experiment_id": eid, "status": "skipped",
                                             "reason": "No dependency changes detected"}
                        if callback:
                            callback(eid, "skipped", self.results[eid])
                level = non_skipped
                if not level:
                    continue

            # Execute level in parallel
            with ThreadPoolExecutor(max_workers=min(self.max_workers, len(level))) as pool:
                futures = {}
                for eid in level:
                    future = pool.submit(self._run_single, dag, eid, dry_run)
                    futures[future] = eid

                for future in as_completed(futures):
                    eid = futures[future]
                    try:
                        result = future.result()
                        self.results[eid] = result
                        if callback:
                            status = result.get("status", "unknown")
                            callback(eid, status, result)
                    except Exception as e:
                        error_result = {"experiment_id": eid, "status": "error", "error": str(e)}
                        self.results[eid] = error_result
                        if callback:
                            callback(eid, "error", error_result)

        return dict(self.results)

    def _run_single(self, dag: DepGraph, experiment_id: str, dry_run: bool) -> dict:
        """Run a single experiment within the DAG context."""
        runner = Runner()
        return runner.run(experiment_id, dry_run=dry_run)

    def _should_execute(self, dag: DepGraph, experiment_id: str) -> bool:
        """Check if an experiment needs to be re-executed based on ancestor changes."""
        deps = dag.dependencies(experiment_id)
        if not deps:
            return True  # root experiments always execute

        current = self.registry.get(experiment_id)
        if not current:
            return True  # never executed

        # Check if any dependency has been re-executed
        for dep_id in deps:
            dep_result = self.results.get(dep_id)
            if dep_result and dep_result.get("status") != "skipped":
                return True  # dependency was re-executed this run

        return False

    def status(self, dag: DepGraph) -> dict[str, dict]:
        """Return execution status for all experiments in the DAG."""
        statuses = {}
        for eid in dag.nodes:
            entry = self.registry.get(eid)
            statuses[eid] = {
                "registry_status": entry.get("status", "unknown") if entry else "not_registered",
                "executed": eid in self.results,
                "result_status": self.results.get(eid, {}).get("status", "pending") if eid in self.results else "pending",
            }
        return statuses
