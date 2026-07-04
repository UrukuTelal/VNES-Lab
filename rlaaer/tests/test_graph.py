"""Tests for the Experiment Graph (DAG) module."""

import os
import tempfile
import pytest
import yaml

from rlaaer.graph.dag import DepGraph, DAGError
from rlaaer.graph.executor import DAGExecutor
from rlaaer.registry import ExperimentRegistry
from rlaaer.config import SPEC_FILENAME


# ── DepGraph Tests ─────────────────────────────────────────

class TestDepGraph:
    def test_empty_graph(self):
        dag = DepGraph()
        assert dag.nodes == set()
        assert dag.is_valid()

    def test_add_single_node(self):
        dag = DepGraph()
        dag.add_experiment("001")
        assert dag.nodes == {"001"}
        assert dag.dependencies("001") == []

    def test_add_duplicate_raises(self):
        dag = DepGraph()
        dag.add_experiment("001")
        with pytest.raises(DAGError, match="Duplicate"):
            dag.add_experiment("001")

    def test_simple_dependency(self):
        dag = DepGraph()
        dag.add_experiment("001")
        dag.add_experiment("002", depends_on=["001"])
        assert dag.dependencies("002") == ["001"]
        assert dag.dependents("001") == ["002"]

    def test_topological_sort_simple(self):
        dag = DepGraph()
        dag.add_experiment("001")
        dag.add_experiment("002", depends_on=["001"])
        dag.add_experiment("003", depends_on=["002"])
        order = dag.topological_sort()
        assert order == ["001", "002", "003"]

    def test_topological_sort_branches(self):
        dag = DepGraph()
        dag.add_experiment("001")
        dag.add_experiment("002", depends_on=["001"])
        dag.add_experiment("003", depends_on=["001"])
        dag.add_experiment("004", depends_on=["002", "003"])
        order = dag.topological_sort()
        assert order.index("001") == 0
        assert order.index("004") == len(order) - 1

    def test_independent_branches(self):
        dag = DepGraph()
        dag.add_experiment("001")
        dag.add_experiment("002", depends_on=["001"])
        dag.add_experiment("003", depends_on=["001"])
        dag.add_experiment("004", depends_on=["002", "003"])
        levels = dag.independent_branches()
        assert levels[0] == ["001"]
        assert set(levels[1]) == {"002", "003"}
        assert levels[2] == ["004"]

    def test_cycle_detection(self):
        dag = DepGraph()
        dag.add_experiment("001", depends_on=["002"])
        dag.add_experiment("002", depends_on=["001"])
        errors = dag.validate()
        assert len(errors) > 0
        assert "Cycle" in errors[0]
        assert not dag.is_valid()

    def test_cycle_topological_sort_raises(self):
        dag = DepGraph()
        dag.add_experiment("001", depends_on=["002"])
        dag.add_experiment("002", depends_on=["001"])
        with pytest.raises(DAGError, match="Cycle"):
            dag.topological_sort()

    def test_missing_dependency(self):
        dag = DepGraph()
        dag.add_experiment("002", depends_on=["001"])
        errors = dag.validate()
        assert len(errors) > 0
        assert "001" in errors[0]

    def test_depth(self):
        dag = DepGraph()
        dag.add_experiment("001")
        dag.add_experiment("002", depends_on=["001"])
        dag.add_experiment("003", depends_on=["002"])
        dag.add_experiment("004")
        assert dag.depth("001") == 0
        assert dag.depth("002") == 1
        assert dag.depth("003") == 2
        assert dag.depth("004") == 0

    def test_from_spec(self):
        spec = {
            "experiment": {"id": "009", "depends_on": ["001", "002"]},
        }
        dag = DepGraph().from_spec(spec)
        assert "009" in dag.nodes
        assert dag.dependencies("009") == ["001", "002"]

    def test_from_spec_no_depends(self):
        spec = {
            "experiment": {"id": "009"},
        }
        dag = DepGraph().from_spec(spec)
        assert dag.dependencies("009") == []

    def test_render(self):
        dag = DepGraph()
        dag.add_experiment("001")
        dag.add_experiment("002", depends_on=["001"])
        rendered = dag.render()
        assert "Experiment DAG" in rendered
        assert "[001]" in rendered
        assert "[002]" in rendered

    def test_render_compact(self):
        dag = DepGraph()
        dag.add_experiment("001")
        dag.add_experiment("002", depends_on=["001"])
        compact = dag.render_compact()
        assert "[001]" in compact
        assert "[002]" in compact

    def test_to_dict(self):
        dag = DepGraph()
        dag.add_experiment("001")
        dag.add_experiment("002", depends_on=["001"])
        d = dag.to_dict()
        assert "nodes" in d
        assert "topological_order" in d
        assert "levels" in d
        assert d["topological_order"] == ["001", "002"]

    def test_save_and_load(self):
        dag = DepGraph()
        dag.add_experiment("001")
        dag.add_experiment("002", depends_on=["001"])
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "dag.json")
        dag.save(path)
        import json
        with open(path) as f:
            data = json.load(f)
        assert "nodes" in data
        import shutil
        shutil.rmtree(tmpdir)

    def test_self_dependency(self):
        """Edge case: experiment depending on itself."""
        dag = DepGraph()
        dag.add_experiment("001", depends_on=["001"])
        errors = dag.validate()
        assert len(errors) > 0

    def test_large_diamond(self):
        """Diamond-shaped dependency: result has a clear topological order."""
        dag = DepGraph()
        dag.add_experiment("A")
        dag.add_experiment("B", depends_on=["A"])
        dag.add_experiment("C", depends_on=["A"])
        dag.add_experiment("D", depends_on=["B", "C"])
        dag.add_experiment("E", depends_on=["D"])
        order = dag.topological_sort()
        assert order[0] == "A"
        assert order[-1] == "E"
        assert order.index("B") < order.index("D")
        assert order.index("C") < order.index("D")


# ── DAG Executor Tests ────────────────────────────────────

class TestDAGExecutor:
    def test_execute_empty_dag(self):
        dag = DepGraph()
        executor = DAGExecutor()
        results = executor.execute(dag)
        assert results == {}

    def test_execute_single_dry_run(self):
        dag = DepGraph()
        dag.add_experiment("009")
        executor = DAGExecutor()
        results = executor.execute(dag, dry_run=True)
        assert "009" in results
        assert results["009"]["dry_run"] is True

    def test_execute_parallel_levels(self):
        dag = DepGraph()
        dag.add_experiment("A")
        dag.add_experiment("B", depends_on=["A"])
        dag.add_experiment("C", depends_on=["A"])
        executor = DAGExecutor(max_workers=4)
        results = executor.execute(dag, dry_run=True)
        assert len(results) == 3

    def test_callback_called(self):
        dag = DepGraph()
        dag.add_experiment("009")
        executor = DAGExecutor()
        called = []
        executor.execute(dag, dry_run=True, callback=lambda eid, s, r: called.append((eid, s)))
        assert len(called) == 1
        assert called[0][0] == "009"

    def test_status(self):
        dag = DepGraph()
        dag.add_experiment("009")
        executor = DAGExecutor()
        statuses = executor.status(dag)
        assert "009" in statuses
        assert "registry_status" in statuses["009"]

    def test_invalid_dag_raises(self):
        dag = DepGraph()
        dag.add_experiment("001", depends_on=["002"])
        executor = DAGExecutor()
        with pytest.raises(DAGError, match="DAG validation failed"):
            executor.execute(dag)

    def test_error_isolation(self):
        """One failing experiment should not block other branches."""
        dag = DepGraph()
        dag.add_experiment("001")
        dag.add_experiment("002", depends_on=["001"])
        executor = DAGExecutor(max_workers=1)
        results = executor.execute(dag, dry_run=True)
        assert len(results) == 2
        assert results["002"]["dry_run"] is True

    def test_partial_execution_skips(self):
        """With partial=True and no reg changes, experiments may be skipped."""
        dag = DepGraph()
        dag.add_experiment("001")
        dag.add_experiment("002", depends_on=["001"])
        executor = DAGExecutor()
        results = executor.execute(dag, dry_run=False, partial=True)
        assert len(results) == 2

    def test_thread_safety(self):
        """Multiple experiments at same level should not deadlock."""
        dag = DepGraph()
        for i in range(10):
            dag.add_experiment(f"{i:03d}")
        executor = DAGExecutor(max_workers=4)
        results = executor.execute(dag, dry_run=True)
        assert len(results) == 10


# ── Validation Tests ──────────────────────────────────────

class TestDependsOnValidation:
    def test_valid_depends_on(self):
        from rlaaer.validation import validate
        spec = {
            "experiment": {"id": "009", "title": "DAG Test", "hypothesis": "If A then B.", "status": "draft",
                           "author": "test", "created": "2026-07-03", "tags": ["dag"],
                           "depends_on": ["001", "002"]},
            "systems": {"vnes_lab": {"enabled": True}},
            "data_sources": [{"source": "census", "tier": 1, "rationale": "test"}],
            "parameters": {"independent": [], "controlled": []},
            "metrics": {"stability": [], "invariants": []},
            "statistics": {"alpha": 0.05, "power": 0.80, "minimum_effect_size": 0.3, "method": "t"},
            "execution": {"trials_per_condition": 1, "total_trials": 1, "max_duration_minutes": 5},
            "review": {"pre_registration_required": True, "approval_threshold": 12, "max_revision_rounds": 3},
            "publication": {"format": "markdown", "license": "CC-BY-4.0", "authors": [{"name": "test"}]},
        }
        errors = validate(spec)
        assert len(errors) == 0

    def test_invalid_depends_on_type(self):
        from rlaaer.validation import validate
        spec_minimal = {
            "experiment": {"id": "009", "title": "Test", "hypothesis": "If A then B.", "status": "draft",
                           "author": "test", "created": "2026-07-03", "tags": [],
                           "depends_on": "not_a_list"},
            "systems": {"vnes_lab": {"enabled": True}},
            "data_sources": [{"source": "census", "tier": 1, "rationale": "test"}],
            "parameters": {"independent": [], "controlled": []},
            "metrics": {"stability": [], "invariants": []},
            "statistics": {"alpha": 0.05, "power": 0.80, "minimum_effect_size": 0.3, "method": "t"},
            "execution": {"trials_per_condition": 1, "total_trials": 1, "max_duration_minutes": 5},
            "review": {"pre_registration_required": True, "approval_threshold": 12, "max_revision_rounds": 3},
            "publication": {"format": "markdown", "license": "CC-BY-4.0", "authors": [{"name": "test"}]},
        }
        errors = validate(spec_minimal)
        assert any("depends_on" in e for e in errors)
