"""Tests for the Native Engine Streaming module."""

import math
import time
import pytest

from rlaaer.execution.streaming import (
    RunningStatistics,
    LiveStatistician,
    AdaptiveController,
    StreamProcessor,
    StreamEvent,
    LiveDashboard,
    AdaptiveRunner,
)
from rlaaer.execution.runner import Runner


# ── RunningStatistics Tests ───────────────────────────────

class TestRunningStatistics:
    def test_single_value(self):
        rs = RunningStatistics()
        rs.update(5.0)
        assert rs.n == 1
        assert rs.mean == 5.0
        assert rs.variance() == 0.0

    def test_multiple_values(self):
        rs = RunningStatistics()
        for v in [2.0, 4.0, 6.0]:
            rs.update(v)
        assert rs.n == 3
        assert rs.mean == 4.0
        assert rs.variance() == 4.0  # sample variance
        assert rs.std() == 2.0

    def test_known_values(self):
        rs = RunningStatistics()
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        for v in values:
            rs.update(v)
        assert rs.n == 5
        assert rs.mean == 3.0
        assert abs(rs.variance() - 2.5) < 1e-10
        assert abs(rs.std() - math.sqrt(2.5)) < 1e-10

    def test_single_value_variance(self):
        rs = RunningStatistics()
        rs.update(10.0)
        assert rs.variance() == 0.0

    def test_merge_empty(self):
        rs = RunningStatistics()
        other = RunningStatistics()
        other.update(5.0)
        rs.merge(other)
        assert rs.n == 1
        assert rs.mean == 5.0

    def test_merge_both_nonempty(self):
        rs1 = RunningStatistics()
        for v in [1.0, 2.0]:
            rs1.update(v)
        rs2 = RunningStatistics()
        for v in [3.0, 4.0, 5.0]:
            rs2.update(v)

        rs1.merge(rs2)
        assert rs1.n == 5
        assert abs(rs1.mean - 3.0) < 1e-10

    def test_many_values_stability(self):
        rs = RunningStatistics()
        for i in range(1, 10001):
            rs.update(float(i))
        assert rs.n == 10000
        assert abs(rs.mean - 5000.5) < 0.001
        # Population mean of 1..10000 is 5000.5

    def test_all_identical(self):
        rs = RunningStatistics()
        for _ in range(100):
            rs.update(7.0)
        assert rs.mean == 7.0
        assert rs.variance() == 0.0


# ── LiveStatistician Tests ────────────────────────────────

class TestLiveStatistician:
    def test_observe_metric(self):
        ls = LiveStatistician()
        ev = StreamEvent(type="metric_update", metric="coherence", value=0.85, trial=0)
        ls.observe(ev)
        assert ls.current_mean("coherence") == 0.85
        assert ls.current_n("coherence") == 1

    def test_observe_multiple(self):
        ls = LiveStatistician()
        for v in [0.7, 0.8, 0.9]:
            ls.observe(StreamEvent(type="metric_update", metric="coherence", value=v))
        assert abs(ls.current_mean("coherence") - 0.8) < 1e-10

    def test_control_treatment_split(self):
        ls = LiveStatistician()
        # Control trials
        for v in [0.7, 0.71, 0.69]:
            ls.observe(StreamEvent(type="metric_update", metric="coherence", value=v, detail={"group": "control"}))
        # Treatment trials
        for v in [0.8, 0.82, 0.79]:
            ls.observe(StreamEvent(type="metric_update", metric="coherence", value=v, detail={"group": "treatment"}))

        t_test = ls.sequential_t_test("coherence")
        assert t_test["sufficient"]
        assert t_test["p_value"] is not None
        assert t_test["t_statistic"] > 0  # treatment > control

    def test_cohens_d(self):
        ls = LiveStatistician()
        for v in [1.0, 1.0, 1.0]:
            ls.observe(StreamEvent(type="metric_update", metric="x", value=v, detail={"group": "control"}))
        for v in [4.0, 4.0, 4.0]:
            ls.observe(StreamEvent(type="metric_update", metric="x", value=v, detail={"group": "treatment"}))

        d = ls.cohens_d("x")
        assert d == float('inf')  # zero variance, infinite effect

    def test_cohens_d_no_overlap(self):
        ls = LiveStatistician()
        for v in [0.0, 0.1]:
            ls.observe(StreamEvent(type="metric_update", metric="x", value=v, detail={"group": "control"}))
        for v in [1.0, 1.1]:
            ls.observe(StreamEvent(type="metric_update", metric="x", value=v, detail={"group": "treatment"}))

        d = ls.cohens_d("x")
        assert d > 0.5  # should detect large effect

    def test_insufficient_data(self):
        ls = LiveStatistician()
        ls.observe(StreamEvent(type="metric_update", metric="coherence", value=0.5, detail={"group": "control"}))
        t_test = ls.sequential_t_test("coherence")
        assert t_test["sufficient"] is False

    def test_summary(self):
        ls = LiveStatistician()
        for i in range(5):
            ls.observe(StreamEvent(type="metric_update", metric="coherence", value=0.5 + i * 0.1,
                                   detail={"group": "control" if i % 2 == 0 else "treatment"}))
        s = ls.summary()
        assert "coherence" in s
        assert "mean" in s["coherence"]

    def test_unknown_metric_mean(self):
        ls = LiveStatistician()
        assert ls.current_mean("nonexistent") == 0.0

    def test_unknown_metric_std(self):
        ls = LiveStatistician()
        assert ls.current_std("nonexistent") == 0.0

    def test_trial_events_counted(self):
        ls = LiveStatistician()
        for t in range(5):
            ls.observe(StreamEvent(type="trial_complete", trial=t))
            ls.observe(StreamEvent(type="metric_update", metric="x", value=float(t)))
        assert len(ls.events) == 10

    def test_p_value_on_large_effect(self):
        ls = LiveStatistician()
        # Strong separation: control ~0, treatment ~1
        for v in [0.0, 0.1, -0.1, 0.05]:
            ls.observe(StreamEvent(type="metric_update", metric="x", value=v, detail={"group": "control"}))
        for v in [1.0, 1.1, 0.9, 1.05]:
            ls.observe(StreamEvent(type="metric_update", metric="x", value=v, detail={"group": "treatment"}))

        t_test = ls.sequential_t_test("x")
        assert t_test["significant"] is True
        assert t_test["p_value"] < 0.05


# ── AdaptiveController Tests ──────────────────────────────

class TestAdaptiveController:
    def test_continue_below_min(self):
        ls = LiveStatistician()
        ac = AdaptiveController(ls, min_trials=10)
        d = ac.evaluate(5)
        assert d["action"] == "continue"
        assert "min_trials" in d["reason"]

    def test_continue_insufficient(self):
        ls = LiveStatistician()
        ac = AdaptiveController(ls, min_trials=0)
        d = ac.evaluate(5)
        assert d["action"] == "continue"

    def test_early_stop_all_significant(self):
        ls = LiveStatistician()
        # Create strong separation
        for _ in range(10):
            ls.observe(StreamEvent(type="metric_update", metric="x", value=0.0, detail={"group": "control"}))
            ls.observe(StreamEvent(type="metric_update", metric="x", value=1.0, detail={"group": "treatment"}))

        ac = AdaptiveController(ls, min_trials=5, min_effect_size=0.3)
        d = ac.evaluate(20, metrics=["x"])
        assert d["action"] == "early_stop"
        assert "significant" in d["reason"]

    def test_max_trials_stop(self):
        ls = LiveStatistician()
        ac = AdaptiveController(ls, min_trials=0, max_trials=100)
        d = ac.evaluate(100)
        assert d["action"] == "early_stop"
        assert "max_trials" in d["reason"]

    def test_stopped_once(self):
        ls = LiveStatistician()
        ac = AdaptiveController(ls, min_trials=0, max_trials=10)
        ac.evaluate(10)
        d = ac.evaluate(15)
        assert d["action"] == "stopped"

    def test_decisions_accumulate(self):
        ls = LiveStatistician()
        ac = AdaptiveController(ls, min_trials=0, max_trials=10)
        ac.evaluate(5)
        ac.evaluate(10)
        assert len(ac.decisions) >= 1

    def test_adjust_parameters_near_significant(self):
        ls = LiveStatistician()
        # Deterministic data with d ≈ 0.3 (small effect, well below min_effect_size=0.5)
        control_vals = [0.0, 0.2, -0.3, 0.5, -0.1, 0.3, -0.4, 0.1, -0.2, 0.4]
        treatment_vals = [0.3, 0.5, 0.0, 0.8, 0.2, 0.6, -0.1, 0.4, 0.1, 0.7]
        for cv, tv in zip(control_vals, treatment_vals):
            ls.observe(StreamEvent(type="metric_update", metric="x", value=cv, detail={"group": "control"}))
            ls.observe(StreamEvent(type="metric_update", metric="x", value=tv, detail={"group": "treatment"}))

        ac = AdaptiveController(ls, min_trials=5, min_effect_size=0.5)
        d = ac.evaluate(20, metrics=["x"])
        assert d["action"] in ("continue", "adjust_parameters")

    def test_futility_stop(self):
        ls = LiveStatistician()
        # Identical distributions (d = 0 exactly)
        shared = [0.3, -0.1, 0.5, -0.4, 0.2, 0.0, -0.3, 0.1, -0.2, 0.4,
                  0.6, -0.5, 0.8, -0.6, 0.7, 0.9, -0.7, -0.8, 0.05, -0.05,
                  0.15, -0.15, 0.25, -0.25, 0.35, -0.35, 0.45, -0.45, 0.55, -0.55]
        for i in range(30):
            ls.observe(StreamEvent(type="metric_update", metric="x",
                                   value=shared[i], detail={"group": "control"}))
            ls.observe(StreamEvent(type="metric_update", metric="x",
                                   value=shared[i], detail={"group": "treatment"}))

        ac = AdaptiveController(ls, min_trials=5, min_effect_size=0.5, futility_stop=True)
        d = ac.evaluate(60, metrics=["x"])
        assert d["action"] == "early_stop"
        assert "Futility" in d["reason"]


# ── StreamProcessor Tests ─────────────────────────────────

class TestStreamProcessor:
    def test_synthetic_stream_yields_events(self):
        sp = StreamProcessor(poll_interval=0.001)
        events = list(sp.stream("009", total_trials=3))
        assert len(events) > 0

    def test_synthetic_contains_metric_updates(self):
        sp = StreamProcessor(poll_interval=0.001)
        events = list(sp.stream("009", total_trials=2))
        types = {e.type for e in events}
        assert "metric_update" in types
        assert "trial_complete" in types

    def test_synthetic_metrics_reasonable(self):
        sp = StreamProcessor(poll_interval=0.001)
        events = list(sp.stream("009", total_trials=5))
        for e in events:
            if e.type == "metric_update":
                assert 0.0 <= e.value <= 1.0 or e.metric == "entropy"

    def test_synthetic_has_group_tags(self):
        sp = StreamProcessor(poll_interval=0.001)
        events = list(sp.stream("009", total_trials=2))
        groups = set()
        for e in events:
            if e.detail and "group" in e.detail:
                groups.add(e.detail["group"])
        assert "control" in groups
        assert "treatment" in groups

    def test_stop_halts_stream(self):
        sp = StreamProcessor(poll_interval=0.001)
        gen = sp.stream("009", total_trials=1000)
        events = []
        for i, ev in enumerate(gen):
            if i >= 10:
                sp.stop()
            events.append(ev)
        assert len(events) < 100  # stopped early


# ── LiveDashboard Tests ───────────────────────────────────

class TestLiveDashboard:
    def test_observe_increments_trials(self):
        d = LiveDashboard()
        assert d.trial_count == 0
        d.observe(StreamEvent(type="trial_complete", trial=0))
        assert d.trial_count == 1

    def test_observe_metrics(self):
        d = LiveDashboard()
        d.observe(StreamEvent(type="metric_update", metric="coherence", value=0.85))
        assert d.current_metrics["coherence"] == 0.85

    def test_status_line(self):
        d = LiveDashboard()
        d.observe(StreamEvent(type="metric_update", metric="coherence", value=0.85))
        d.observe(StreamEvent(type="trial_complete", trial=0))
        line = d.status_line()
        assert "Trial" in line
        assert "coherence" in line

    def test_summary(self):
        d = LiveDashboard()
        d.observe(StreamEvent(type="metric_update", metric="coherence", value=0.85))
        d.observe(StreamEvent(type="trial_complete", trial=0))
        s = d.summary()
        assert "Total events" in s
        assert "Total trials" in s


# ── AdaptiveRunner Tests ──────────────────────────────────

class TestAdaptiveRunner:
    def test_run_adaptive_completes(self):
        ar = AdaptiveRunner(poll_interval=0.001, min_trials=2, max_trials=10)
        result = ar.run_adaptive("009")
        assert result["status"] == "completed"
        assert "final_statistics" in result
        assert "decisions" in result
        assert "dashboard" in result

    def test_run_adaptive_has_decisions(self):
        ar = AdaptiveRunner(poll_interval=0.001, min_trials=2, max_trials=10)
        result = ar.run_adaptive("009")
        assert len(result["decisions"]) > 0
        # At least some should be "continue" (early phase)

    def test_run_adaptive_events_recorded(self):
        ar = AdaptiveRunner(poll_interval=0.001, min_trials=2, max_trials=10)
        result = ar.run_adaptive("009")
        assert result["streaming_events"] > 0

    def test_callback_receives_events(self):
        received = []
        ar = AdaptiveRunner(poll_interval=0.001, min_trials=2, max_trials=5)
        ar.run_adaptive("009", event_callback=lambda e: received.append(e))
        assert len(received) > 0
        types = {e.type for e in received}
        assert "metric_update" in types

    def test_dry_run(self):
        ar = AdaptiveRunner()
        result = ar.run_adaptive("009", dry_run=True)
        assert result["dry_run"] is True

    def test_statistician_populated(self):
        ar = AdaptiveRunner(poll_interval=0.001, min_trials=2, max_trials=10)
        ar.run_adaptive("009")
        summary = ar.statistician.summary()
        assert len(summary) > 0  # at least one metric tracked
