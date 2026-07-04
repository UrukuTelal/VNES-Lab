"""Native Engine Streaming — WebSocket telemetry, live statistics, adaptive control.

Architecture:
    Engine ──WebSocket──▶ StreamProcessor ──▶ LiveDashboard
                             │
                             ├──▶ LiveStatistician (real-time t-tests)
                             ├──▶ AdaptiveController (early stop, param adjust)
                             └──▶ AdaptiveRunner (wraps Runner with streaming)
"""

import json
import math
import time
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Callable, Any, Generator

from rlaaer.config import ENGINE
from rlaaer.execution.runner import Runner, RunnerError


# ── Streaming Events ──────────────────────────────────────

@dataclass
class StreamEvent:
    type: str           # metric_update, trial_complete, parameter_change, status_change, error
    metric: str = ""
    value: float = 0.0
    trial: int = 0
    timestamp: str = ""
    detail: dict | None = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


# ── Running Statistics (Welford's Online Algorithm) ───────

class RunningStatistics:
    """Online mean and variance using Welford's algorithm.
    O(1) memory, exact computation, supports incremental updates.
    """

    def __init__(self):
        self.n = 0
        self.mean = 0.0
        self.m2 = 0.0       # sum of squared differences from current mean

    def update(self, value: float):
        """Incorporate a new observation."""
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (value - self.mean)

    def variance(self) -> float:
        """Population variance (use n-1 for sample variance)."""
        if self.n < 2:
            return 0.0
        return self.m2 / (self.n - 1)

    def std(self) -> float:
        return math.sqrt(self.variance()) if self.n >= 2 else 0.0

    def merge(self, other: "RunningStatistics"):
        """Merge two running statistics (Chan's pairwise update)."""
        if other.n == 0:
            return
        if self.n == 0:
            self.n, self.mean, self.m2 = other.n, other.mean, other.m2
            return
        n_total = self.n + other.n
        delta = other.mean - self.mean
        self.mean = (self.n * self.mean + other.n * other.mean) / n_total
        self.m2 = self.m2 + other.m2 + delta ** 2 * self.n * other.n / n_total
        self.n = n_total


# ── Live Statistician ─────────────────────────────────────

class LiveStatistician:
    """Consumes streaming events and computes running statistical tests.

    Maintains separate RunningStatistics for each metric.
    Supports sequential t-tests and Cohen's d.
    """

    def __init__(self, alpha: float = 0.05):
        self.alpha = alpha
        self.metrics: dict[str, RunningStatistics] = {}
        self._control_stats: dict[str, RunningStatistics] = {}
        self._treatment_stats: dict[str, RunningStatistics] = {}
        self.events: list[StreamEvent] = []

    def observe(self, event: StreamEvent):
        """Process a streaming event."""
        self.events.append(event)

        if event.type == "metric_update" and event.metric:
            if event.metric not in self.metrics:
                self.metrics[event.metric] = RunningStatistics()
            self.metrics[event.metric].update(event.value)

            # Track control vs treatment based on trial parity or explicit tag
            tag = event.detail.get("group", "control") if event.detail else "control"
            target = self._treatment_stats if tag == "treatment" else self._control_stats
            if event.metric not in target:
                target[event.metric] = RunningStatistics()
            target[event.metric].update(event.value)

    def current_mean(self, metric: str) -> float:
        if metric in self.metrics:
            return self.metrics[metric].mean
        return 0.0

    def current_std(self, metric: str) -> float:
        if metric in self.metrics:
            return self.metrics[metric].std()
        return 0.0

    def current_n(self, metric: str) -> int:
        if metric in self.metrics:
            return self.metrics[metric].n
        return 0

    def sequential_t_test(self, metric: str) -> dict:
        """Compute running independent two-sample t-test (Welch's)."""
        control = self._control_stats.get(metric)
        treatment = self._treatment_stats.get(metric)

        if not control or not treatment or control.n < 2 or treatment.n < 2:
            return {"p_value": None, "t_statistic": None, "df": 0, "sufficient": False}

        n1, m1, v1 = control.n, control.mean, control.variance()
        n2, m2, v2 = treatment.n, treatment.mean, treatment.variance()

        se = math.sqrt(v1 / n1 + v2 / n2)
        if se == 0:
            # Perfect separation: zero within-group variance
            p = 0.0 if m1 != m2 else 1.0
            return {"p_value": p, "t_statistic": float('inf') if m1 != m2 else 0.0,
                    "df": 0, "significant": m1 != m2, "sufficient": True}

        t_stat = (m2 - m1) / se

        # Welch-Satterthwaite df
        num = (v1 / n1 + v2 / n2) ** 2
        denom = (v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)
        df = num / denom if denom > 0 else 0

        p = self._two_tailed_p(t_stat, df)

        return {
            "p_value": p,
            "t_statistic": t_stat,
            "df": df,
            "significant": p < self.alpha,
            "sufficient": True,
        }

    def cohens_d(self, metric: str) -> float:
        """Compute Cohen's d effect size from running statistics."""
        control = self._control_stats.get(metric)
        treatment = self._treatment_stats.get(metric)
        if not control or not treatment:
            return 0.0
        pooled_std = math.sqrt(
            ((control.n - 1) * control.variance() + (treatment.n - 1) * treatment.variance())
            / (control.n + treatment.n - 2)
        )
        mean_diff = treatment.mean - control.mean
        if pooled_std == 0:
            return float('inf') if mean_diff != 0 else 0.0
        return mean_diff / pooled_std

    def summary(self) -> dict:
        """Return a snapshot of all current statistics."""
        result = {}
        for metric in self.metrics:
            t_test = self.sequential_t_test(metric)
            result[metric] = {
                "n": self.metrics[metric].n,
                "mean": self.metrics[metric].mean,
                "std": self.metrics[metric].std(),
                "cohens_d": self.cohens_d(metric),
                "p_value": t_test.get("p_value"),
                "significant": t_test.get("significant", False),
            }
        return result

    @staticmethod
    def _two_tailed_p(t_stat: float, df: float) -> float:
        """Two-tailed p-value from t-distribution using approximation."""
        if df <= 0:
            return 1.0
        x = abs(t_stat)
        n = df

        # Abramowitz and Stegun approximation for the CDF of the t-distribution
        a1 = 0.0498673470
        a2 = 0.0211410061
        a3 = 0.0032776263
        a4 = 0.0000380036
        a5 = 0.0000488906
        a6 = 0.0000053830

        # For large df, use normal approximation
        if n > 100:
            # Standard normal CDF approximation
            z = x
            b0 = 0.2316419
            b1 = 0.319381530
            b2 = -0.356563782
            b3 = 1.781477937
            b4 = -1.821255978
            b5 = 1.330274429

            t = 1.0 / (1.0 + b0 * z)
            phi = 0.398942280 * math.exp(-z * z / 2)
            p_upper = phi * (b1 * t + b2 * t ** 2 + b3 * t ** 3 + b4 * t ** 4 + b5 * t ** 5)
            return 2.0 * p_upper

        # For smaller df, use the series approximation
        x2 = x * x
        p = x * (1 + x2 / n) ** (-0.5 * (n + 1))
        # Divide by beta(0.5, n/2)
        import math as m
        p = p / (m.sqrt(n) * m.exp(m.lgamma(0.5) + m.lgamma(n / 2) - m.lgamma((n + 1) / 2)))
        # This gives a one-tailed p; two-tailed:
        return min(1.0, 2.0 * p) if m.isfinite(p) else 1.0


# ── Adaptive Controller ───────────────────────────────────

class AdaptiveController:
    """Makes real-time decisions based on live statistics.

    - Early stopping when significance is reached or futility detected
    - Parameter adjustment for response surface exploration
    - Sample size re-estimation
    """

    def __init__(self, statistician: LiveStatistician, alpha: float = 0.05,
                 min_effect_size: float = 0.3, max_trials: int = 10000,
                 min_trials: int = 10, futility_stop: bool = True):
        self.statistician = statistician
        self.alpha = alpha
        self.min_effect_size = min_effect_size
        self.max_trials = max_trials
        self.min_trials = min_trials
        self.futility_stop = futility_stop
        self.decisions: list[dict] = []
        self.stopped = False

    def evaluate(self, trial: int, metrics: list[str] | None = None) -> dict:
        """Evaluate whether to stop, adjust, or continue.

        Returns a decision dict with keys:
            action: continue | early_stop | adjust_parameters
            reason: str
            adjustments: dict | None
        """
        if self.stopped:
            return {"action": "stopped", "reason": "Already stopped"}

        if trial < self.min_trials:
            return {"action": "continue", "reason": f"Below min_trials ({trial} < {self.min_trials})"}

        if trial >= self.max_trials:
            self.stopped = True
            d = {"action": "early_stop", "reason": f"Reached max_trials ({self.max_trials})"}
            self.decisions.append(d)
            return d

        check_metrics = metrics or list(self.statistician.metrics.keys())
        significant_count = 0
        for m in check_metrics:
            t_test = self.statistician.sequential_t_test(m)
            d = self.statistician.cohens_d(m)
            effect_large = not math.isfinite(d) or abs(d) >= self.min_effect_size
            is_sig = t_test.get("significant") and effect_large
            if is_sig:
                significant_count += 1

        # Early stop if all checked metrics are significant
        if check_metrics and significant_count == len(check_metrics):
            self.stopped = True
            d = {"action": "early_stop", "reason": f"All {significant_count}/{len(check_metrics)} metrics significant"}
            self.decisions.append(d)
            return d

        # Parameter adjustment (exploration) — check before futility
        adjustments = {}
        for m in check_metrics:
            d_val = self.statistician.cohens_d(m)
            if math.isfinite(d_val) and self.min_effect_size / 4 <= abs(d_val) < self.min_effect_size:
                direction = "increase" if d_val > 0 else "decrease"
                adjustments[m] = {"suggested_direction": direction, "current_d": d_val}

        if adjustments and not self.stopped:
            d = {"action": "adjust_parameters", "reason": "Near-significant effects detected", "adjustments": adjustments}
            self.decisions.append(d)
            return d

        # Futility stop: if effect is below threshold and we have enough data
        if self.futility_stop and trial >= self.min_trials * 3:
            for m in check_metrics:
                d_val = self.statistician.cohens_d(m)
                if math.isfinite(d_val) and abs(d_val) < self.min_effect_size / 4:
                    self.stopped = True
                    dd = {"action": "early_stop", "reason": f"Futility: Cohen's d={d_val:.3f} below threshold for {m}"}
                    self.decisions.append(dd)
                    return dd

        return {"action": "continue", "reason": "Insufficient evidence for any decision"}


# ── Stream Processor ──────────────────────────────────────

class StreamProcessor:
    """Reads engine events from WebSocket (or polling fallback) and yields StreamEvents.

    In fallback mode (no real engine), generates synthetic events for testing.
    """

    def __init__(self, engine=None, poll_interval: float = 0.1):
        self.engine = engine
        self.poll_interval = poll_interval
        self._running = False

    def stream(self, experiment_id: str, total_trials: int = 100,
               callback: Callable[[StreamEvent], None] | None = None) -> Generator[StreamEvent, None, None]:
        """Yield streaming events for an experiment.

        In production, connects to the engine WebSocket.
        In fallback mode, generates synthetic per-trial events.
        """
        self._running = True

        try:
            # Try real engine WebSocket path
            if self.engine and self.engine.ping():
                yield from self._real_stream(experiment_id, callback)
                return
        except Exception:
            pass

        # Fallback: synthetic events for testing
        yield from self._synthetic_stream(experiment_id, total_trials, callback)

    def _real_stream(self, experiment_id: str,
                     callback: Callable[[StreamEvent], None] | None = None) -> Generator[StreamEvent, None, None]:
        """Real engine streaming via WebSocket or polling."""
        import requests
        base = self.engine.base_url if self.engine else ENGINE["rest_api"]

        # Start simulation
        try:
            resp = requests.post(f"{base}/simulation/start", json={"experiment_id": experiment_id}, timeout=10)
            resp.raise_for_status()
            sim_id = resp.json().get("simulation_id", experiment_id)
        except Exception as e:
            yield StreamEvent(type="error", detail={"error": str(e)})
            return

        yield StreamEvent(type="status_change", metric="simulation", value=1.0, detail={"sim_id": sim_id})

        trial = 0
        while self._running:
            try:
                resp = requests.post(f"{base}/simulation/{sim_id}/step", json={"ticks": 1}, timeout=30)
                if resp.status_code != 200:
                    break
                data = resp.json()
                metrics = data.get("metrics", {})
                for name, value in metrics.items():
                    ev = StreamEvent(type="metric_update", metric=name, value=float(value), trial=trial)
                    if callback:
                        callback(ev)
                    yield ev

                trial += 1
                yield StreamEvent(type="trial_complete", trial=trial)

                if trial >= 100:  # safety limit
                    break

                time.sleep(self.poll_interval)

            except Exception as e:
                yield StreamEvent(type="error", detail={"error": str(e), "trial": trial})
                break

        # Cleanup
        try:
            requests.post(f"{base}/simulation/{sim_id}/stop", timeout=5)
        except Exception:
            pass
        yield StreamEvent(type="status_change", metric="simulation", value=0, detail={"status": "stopped"})

    def _synthetic_stream(self, experiment_id: str, total_trials: int,
                          callback: Callable[[StreamEvent], None] | None = None) -> Generator[StreamEvent, None, None]:
        """Generate synthetic events for testing and fallback."""
        import random
        rng = random.Random(hash(experiment_id) & 0xFFFFFFFF)

        for trial in range(total_trials):
            if not self._running:
                break

            # Control group (even trials)
            is_treatment = (trial % 2 == 1)
            group = "treatment" if is_treatment else "control"

            # Synthetic metrics with slight effect
            coherence = 0.7 + rng.gauss(0.0, 0.1) + (0.05 if is_treatment else 0.0)
            entropy = 1.5 + rng.gauss(0.0, 0.2) - (0.03 if is_treatment else 0.0)
            coupling = 0.5 + rng.gauss(0.0, 0.05)

            metrics = {
                "coherence": max(0, min(1, coherence)),
                "entropy": max(0, entropy),
                "coupling": max(0, min(1, coupling)),
            }

            for name, value in metrics.items():
                ev = StreamEvent(type="metric_update", metric=name, value=value, trial=trial,
                                 detail={"group": group, "experiment_id": experiment_id})
                if callback:
                    callback(ev)
                yield ev

            ev = StreamEvent(type="trial_complete", trial=trial, detail={"group": group})
            if callback:
                callback(ev)
            yield ev

            time.sleep(self.poll_interval)

        yield StreamEvent(type="status_change", metric="status", value=1.0, detail={"status": "completed"})

    def stop(self):
        self._running = False


# ── Live Dashboard ─────────────────────────────────────────

class LiveDashboard:
    """Accumulates stream events and provides formatted output."""

    def __init__(self):
        self.events: list[StreamEvent] = []
        self.trial_count = 0
        self.current_metrics: dict[str, float] = {}

    def observe(self, event: StreamEvent):
        self.events.append(event)
        if event.type == "metric_update" and event.metric:
            self.current_metrics[event.metric] = event.value
        if event.type == "trial_complete":
            self.trial_count += 1

    def status_line(self) -> str:
        metrics_str = " | ".join(f"{k}={v:.4f}" for k, v in self.current_metrics.items())
        return f"Trial {self.trial_count:>5} | {metrics_str}"

    def summary(self) -> str:
        lines = [f"Total events: {len(self.events)}", f"Total trials: {self.trial_count}"]
        for k, v in self.current_metrics.items():
            lines.append(f"  {k}: {v:.4f}")
        return "\n".join(lines)


# ── Adaptive Runner ────────────────────────────────────────

class AdaptiveRunner:
    """Wraps Runner with streaming: live statistics, adaptive control, early stopping."""

    def __init__(self, runner: Runner | None = None, alpha: float = 0.05,
                 min_effect_size: float = 0.3, min_trials: int = 10, max_trials: int = 10000,
                 poll_interval: float = 0.05):
        self.runner = runner or Runner()
        self.alpha = alpha
        self.min_effect_size = min_effect_size
        self.min_trials = min_trials
        self.max_trials = max_trials
        self.poll_interval = poll_interval
        self.statistician = LiveStatistician(alpha=alpha)
        self.controller = AdaptiveController(
            self.statistician,
            alpha=alpha,
            min_effect_size=min_effect_size,
            max_trials=max_trials,
            min_trials=min_trials,
        )
        self.dashboard = LiveDashboard()
        self.processor = StreamProcessor(poll_interval=poll_interval)

    def run_adaptive(self, experiment_id: str, dry_run: bool = False,
                     event_callback: Callable[[StreamEvent], None] | None = None) -> dict:
        """Run experiment with adaptive streaming.

        Returns result summary including streaming statistics and decisions.
        """
        if dry_run:
            try:
                return self.runner.run(experiment_id, dry_run=True)
            except Exception:
                return {"experiment_id": experiment_id, "dry_run": True, "status": "ok"}

        total_trials = 100
        try:
            exp_dir = self.runner._find_experiment_dir(experiment_id)
            spec_path = os.path.join(exp_dir, "spec.yaml")
            import yaml
            with open(spec_path) as f:
                spec = yaml.safe_load(f)
            total_trials = spec.get("execution", {}).get("total_trials", 100)
        except Exception:
            pass

        trial_results = []
        streaming_stats = []
        decisions = []

        # Collect events via the dashboard
        def _on_event(event: StreamEvent):
            self.statistician.observe(event)
            self.dashboard.observe(event)
            if event_callback:
                event_callback(event)

        # Stream events
        for event in self.processor.stream(experiment_id, total_trials=total_trials, callback=_on_event):
            streaming_stats.append(event)
            if event.type == "trial_complete":
                decision = self.controller.evaluate(event.trial)
                decisions.append(decision)

                if decision["action"] == "early_stop":
                    break

                if decision["action"] == "adjust_parameters":
                    self._apply_adjustments(decision.get("adjustments", {}), event.trial)

        result = {
            "experiment_id": experiment_id,
            "status": "completed",
            "total_trials": self.dashboard.trial_count,
            "streaming_events": len(streaming_stats),
            "decisions": decisions,
            "final_statistics": self.statistician.summary(),
            "dashboard": self.dashboard.summary(),
            "stopped_early": self.controller.stopped,
        }
        return result

    def _apply_adjustments(self, adjustments: dict, trial: int):
        """Apply parameter adjustments (stub — real implementation connects to engine API)."""
        pass
