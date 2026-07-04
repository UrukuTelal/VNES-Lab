"""Experiment DAG — dependency graph, topological sort, validation, visualization.

Each experiment can declare `depends_on: [experiment_id, ...]` in its spec.yaml.
The DAG ensures correct execution order, detects cycles, and enables
parallel execution of independent branches.
"""

import os
import json
from collections import defaultdict, deque
from typing import Any

import yaml

from rlaaer.config import REPO_ROOT, SPEC_FILENAME


class DAGError(Exception):
    """Raised on DAG validation or execution errors."""


class DepGraph:
    """Directed acyclic graph of experiment dependencies.

    Nodes are experiment IDs. Edges are dependency relationships.
    """

    def __init__(self):
        self._nodes: dict[str, dict] = {}
        self._edges: dict[str, list[str]] = {}     # node -> list of dependencies
        self._parents: dict[str, list[str]] = {}   # node -> list of dependents
        self._depths: dict[str, int] = {}

    # ── Construction ────────────────────────────────────────

    def add_experiment(self, experiment_id: str, depends_on: list[str] | None = None,
                       metadata: dict | None = None):
        """Add an experiment node with optional dependencies."""
        if experiment_id in self._nodes:
            raise DAGError(f"Duplicate node: {experiment_id}")

        self._nodes[experiment_id] = metadata or {}
        self._edges[experiment_id] = depends_on or []
        self._parents[experiment_id] = []
        for dep in (depends_on or []):
            if dep not in self._parents:
                self._parents[dep] = []
            self._parents[dep].append(experiment_id)

    def from_spec(self, spec: dict) -> "DepGraph":
        """Load a single spec and its dependencies into the graph."""
        exp = spec.get("experiment", {})
        eid = exp.get("id", "")
        depends_on = exp.get("depends_on", [])
        self.add_experiment(eid, depends_on=depends_on, metadata=spec)
        return self

    def from_registry(self, experiment_ids: list[str]) -> "DepGraph":
        """Load multiple experiments from filesystem specs into the graph."""
        for eid in experiment_ids:
            spec = self._load_spec(eid)
            if spec:
                self.from_spec(spec)
        return self

    # ── Properties ─────────────────────────────────────────

    @property
    def nodes(self) -> set[str]:
        return set(self._nodes.keys())

    @property
    def edges(self) -> dict[str, list[str]]:
        return dict(self._edges)

    def dependencies(self, experiment_id: str) -> list[str]:
        return list(self._edges.get(experiment_id, []))

    def dependents(self, experiment_id: str) -> list[str]:
        return list(self._parents.get(experiment_id, []))

    def metadata(self, experiment_id: str) -> dict:
        return self._nodes.get(experiment_id, {})

    # ── Validation ─────────────────────────────────────────

    def validate(self) -> list[str]:
        """Validate the DAG. Returns list of error strings (empty = valid)."""
        errors = []

        # Check all referenced dependencies exist in the graph
        for eid, deps in self._edges.items():
            for dep in deps:
                if dep not in self._nodes:
                    errors.append(f"Experiment {eid} depends on {dep}, but {dep} is not in the graph")

        # Check for cycles using Kahn's algorithm
        in_degree = {n: 0 for n in self._nodes}
        for eid, deps in self._edges.items():
            for dep in deps:
                in_degree[eid] = in_degree.get(eid, 0) + 1

        queue = deque([n for n, d in in_degree.items() if d == 0])
        sorted_nodes = []
        while queue:
            n = queue.popleft()
            sorted_nodes.append(n)
            for parent in self._parents.get(n, []):
                in_degree[parent] -= 1
                if in_degree[parent] == 0:
                    queue.append(parent)

        if len(sorted_nodes) != len(self._nodes):
            cycle_nodes = set(self._nodes) - set(sorted_nodes)
            errors.append(f"Cycle detected involving: {', '.join(sorted(cycle_nodes))}")

        return errors

    def is_valid(self) -> bool:
        return len(self.validate()) == 0

    # ── Topological Sort ────────────────────────────────────

    def topological_sort(self) -> list[str]:
        """Return experiment IDs in execution order (dependencies first)."""
        errors = self.validate()
        if errors:
            raise DAGError(f"Cannot sort: {'; '.join(errors)}")

        in_degree = {n: 0 for n in self._nodes}
        for eid, deps in self._edges.items():
            for dep in deps:
                in_degree[eid] = in_degree.get(eid, 0) + 1

        queue = deque([n for n, d in in_degree.items() if d == 0])
        result = []
        while queue:
            n = queue.popleft()
            result.append(n)
            for parent in self._parents.get(n, []):
                in_degree[parent] -= 1
                if in_degree[parent] == 0:
                    queue.append(parent)
        return result

    def independent_branches(self) -> list[list[str]]:
        """Group experiments into independent levels (parallel execution groups).

        Each level contains experiments that have no dependencies on each other
        and can be executed in parallel.
        """
        levels = []
        remaining = set(self._nodes)
        edges = {eid: list(deps) for eid, deps in self._edges.items()}

        while remaining:
            # Nodes whose dependencies are all already satisfied
            ready = [n for n in remaining if not edges.get(n, [])]
            if not ready:
                break
            levels.append(ready)
            for n in ready:
                remaining.remove(n)
                for eid in list(edges.keys()):
                    if n in edges.get(eid, []):
                        edges[eid].remove(n)
        return levels

    def depth(self, experiment_id: str) -> int:
        """Compute depth (longest path from root)."""
        if experiment_id in self._depths:
            return self._depths[experiment_id]

        deps = self._edges.get(experiment_id, [])
        if not deps:
            self._depths[experiment_id] = 0
            return 0

        max_depth = max(self.depth(d) for d in deps) + 1
        self._depths[experiment_id] = max_depth
        return max_depth

    # ── Visualization ───────────────────────────────────────

    def render(self) -> str:
        """Render the DAG as ASCII art."""
        lines = ["Experiment DAG"]
        lines.append("=" * 60)

        levels = self.independent_branches()
        for i, level in enumerate(levels):
            prefix = "  " * i
            if i == 0:
                connectors = "   ".join(f"[{e}]" for e in level)
                lines.append(f"{prefix}{connectors}")
            else:
                # Show dependency arrows
                for eid in level:
                    deps = self._edges.get(eid, [])
                    dep_str = ", ".join(deps)
                    lines.append(f"{prefix}[{eid}] ── depends on: {dep_str}")
                lines.append("")

        lines.append(f"\n{len(self._nodes)} experiments, {sum(len(d) for d in self._edges.values())} dependencies")
        valid = self.is_valid()
        lines.append(f"DAG valid: {valid}")
        if not valid:
            for err in self.validate():
                lines.append(f"  ERROR: {err}")

        return "\n".join(lines)

    def render_compact(self) -> str:
        """One-line-per-node render showing dependencies."""
        lines = []
        for eid in self.topological_sort():
            deps = self._edges.get(eid, [])
            dep_str = f" ← {', '.join(deps)}" if deps else " (root)"
            lines.append(f"  [{eid}]{dep_str}")
        return "\n".join(lines)

    # ── Serialization ───────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "nodes": {n: {"dependencies": self._edges.get(n, []),
                          "dependents": self._parents.get(n, [])}
                     for n in self._nodes},
            "topological_order": self.topological_sort() if self.is_valid() else [],
            "levels": self.independent_branches(),
        }

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    # ── Helpers ─────────────────────────────────────────────

    @staticmethod
    def _load_spec(experiment_id: str) -> dict | None:
        pattern = f"{int(experiment_id):03d}_*"
        import glob
        base = os.path.join(REPO_ROOT, "experiments", pattern, SPEC_FILENAME)
        for match in glob.glob(base):
            try:
                with open(match, "r") as f:
                    return yaml.safe_load(f)
            except Exception:
                continue
        return None
