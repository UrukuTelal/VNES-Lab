"""001_homeostasis — Pillar equilibrium under sinusoidal perturbation.

Hypothesis: Higher Resistance → faster settling, lower overshoot.
Amplitudes exceeding Willpower cause permanent drift.
"""

import sys, os, math, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from lib.psv_core import (
    PillarState, Entity, MetricLogger, NUM_PILLARS, PI, rotate_pillar,
)

SEED = 42
TIMESTEPS = 200
AMPLITUDES = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
RESISTANCE_LEVELS = [0.1, 0.5, 0.9]
TARGET_PILLAR = 2  # Force
BASELINE = PI / 2
SETTLE_THRESHOLD = 0.05  # 5% of PI


def run():
    random.seed(SEED)
    logger = MetricLogger(
        base_dir=os.path.join(os.path.dirname(__file__), "metrics"),
        columns=["amplitude", "resistance", "settling_time", "overshoot", "final_drift"],
    )

    for res in RESISTANCE_LEVELS:
        for amp in AMPLITUDES:
            state = PillarState.from_values(theta=[PI / 2] * NUM_PILLARS)
            state.theta[4] = res  # Resistance

            overshoot = 0.0
            settled = False
            settle_step = TIMESTEPS
            baseline_val = BASELINE

            for t in range(TIMESTEPS):
                perturbation = amp * math.sin(2 * math.pi * t / 30)
                state.theta[TARGET_PILLAR] += perturbation
                state.clamp()

                restore = perturbation * (1 - state.theta[4]) * 0.1
                state.theta[TARGET_PILLAR] -= restore
                state.clamp()

                deviation = abs(state.theta[TARGET_PILLAR] - baseline_val)
                overshoot = max(overshoot, deviation)

                if not settled and deviation < SETTLE_THRESHOLD:
                    settled = True
                    settle_step = t

            final_drift = abs(state.theta[TARGET_PILLAR] - baseline_val)
            logger.log(amp, res, settle_step, overshoot, final_drift)

    path = logger.save("homeostasis.csv")
    print(f"Saved: {path}")

    # Summary
    print(f"\n=== HOMEOSTASIS RESULTS ===")
    print(f"{'Amplitude':>10} {'Resistance':>10} {'Settle':>8} {'Overshoot':>10} {'Drift':>8}")
    for row in logger.rows:
        a, r, s, o, d = row
        marker = " [DRIFT]" if d > SETTLE_THRESHOLD else ""
        print(f"{a:>10.2f} {r:>10.2f} {s:>8.0f} {o:>10.4f} {d:>8.4f}{marker}")

    # Generate visualization
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        for res in RESISTANCE_LEVELS:
            sub = [r for r in logger.rows if r[1] == res]
            axes[0].plot([r[0] for r in sub], [r[2] for r in sub], marker="o", label=f"Res={res}")
        axes[0].set_xlabel("Perturbation Amplitude")
        axes[0].set_ylabel("Settling Time (steps)")
        axes[0].set_title("Settling Time vs Amplitude")
        axes[0].legend()
        axes[0].grid(True)

        for res in RESISTANCE_LEVELS:
            sub = [r for r in logger.rows if r[1] == res]
            axes[1].plot([r[0] for r in sub], [r[3] for r in sub], marker="s", label=f"Res={res}")
        axes[1].axhline(y=SETTLE_THRESHOLD, color="r", linestyle="--", alpha=0.5, label="Drift threshold")
        axes[1].set_xlabel("Perturbation Amplitude")
        axes[1].set_ylabel("Final Drift")
        axes[1].set_title("Permanent Drift vs Amplitude")
        axes[1].legend()
        axes[1].grid(True)

        plt.tight_layout()
        vis_path = os.path.join(os.path.dirname(__file__), "visualizations", "homeostasis.png")
        plt.savefig(vis_path, dpi=150)
        plt.close()
        print(f"Saved: {vis_path}")
    except ImportError:
        print("(matplotlib not available, skipping visualization)")

    # Verdict
    drifts = [r[4] for r in logger.rows]
    high_drift = sum(1 for d in drifts if d > SETTLE_THRESHOLD)
    print(f"\nVerdict: {'FAIL' if high_drift > 0 else 'PASS'}")
    print(f"  {high_drift}/{len(drifts)} conditions show permanent drift")
    return "FAIL" if high_drift > 0 else "PASS"


if __name__ == "__main__":
    run()
