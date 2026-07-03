"""006_self_repair — Recovery from Harm/distortion.

Hypothesis: Depth > 0.3 enables full recovery. Depth < 0.1 causes
permanent drift. Recovery time scales inversely with Integrity.
"""

import sys, os, math, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from lib.psv_core import (
    PillarState, apply_harm, MetricLogger, NUM_PILLARS, PI,
)

SEED = 42
TIMESTEPS = 500
DEPTH_LEVELS = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]
HARM_MAGNITUDES = [0.1, 0.3, 0.5, 0.7, 0.9]
TRIALS_PER_CONFIG = 5
RECOVERY_THRESHOLD = 0.02


def run():
    random.seed(SEED)
    logger = MetricLogger(
        base_dir=os.path.join(os.path.dirname(__file__), "metrics"),
        columns=["initial_depth", "harm_mag", "recovery_time", "residual_error", "integrity_min"],
    )

    for depth in DEPTH_LEVELS:
        for harm_mag in HARM_MAGNITUDES:
            for trial in range(TRIALS_PER_CONFIG):
                state = PillarState.from_values(theta=[PI / 2] * NUM_PILLARS)
                state.theta[15] = depth  # Depth
                state.theta[5] = 0.7     # Integrity
                state.theta[4] = 0.3     # Resistance

                baseline = state.copy()
                actor = PillarState.from_values(theta=[PI / 2] * NUM_PILLARS)
                actor.theta[12] = harm_mag  # Harm
                actor.theta[3] = 0.5        # Influence

                apply_harm(actor, state, random.randint(0, NUM_PILLARS - 1))

                recovered = False
                recovery_time = TIMESTEPS
                integrity_min = state.theta[5]

                for t in range(TIMESTEPS):
                    # Natural drift toward baseline
                    for i in range(NUM_PILLARS):
                        drift = (baseline.theta[i] - state.theta[i]) * 0.02
                        state.theta[i] += drift

                    # Depth slowly restores
                    if state.theta[15] < depth:
                        state.theta[15] += 0.001
                    state.clamp()

                    integrity_min = min(integrity_min, state.theta[5])
                    deviation = state.distance(baseline)

                    if not recovered and deviation < RECOVERY_THRESHOLD:
                        recovered = True
                        recovery_time = t

                residual = state.distance(baseline)
                logger.log(depth, harm_mag, recovery_time, residual, integrity_min)

    path = logger.save("self_repair.csv")
    print(f"Saved: {path}")

    print(f"\n=== SELF-REPAIR RESULTS ===")
    for depth in DEPTH_LEVELS:
        sub = [r for r in logger.rows if abs(r[0] - depth) < 0.001]
        avg_residual = sum(r[3] for r in sub) / len(sub) if sub else 0
        marker = " [OK]" if avg_residual < RECOVERY_THRESHOLD else " [WARN]"
        print(f"Depth={depth:>5.2f}: avg residual={avg_residual:.4f}{marker}")

    deep_rows = [r for r in logger.rows if r[0] >= 0.3]
    shallow_rows = [r for r in logger.rows if r[0] <= 0.1]
    deep_residual = sum(r[3] for r in deep_rows) / len(deep_rows) if deep_rows else 1.0
    shallow_residual = sum(r[3] for r in shallow_rows) / len(shallow_rows) if shallow_rows else 1.0

    verdict = "PASS" if deep_residual < RECOVERY_THRESHOLD and shallow_residual > 0.01 else "FAIL"
    print(f"\nVerdict: {verdict}")
    print(f"  Deep residual (Depth>=0.3): {deep_residual:.4f} (should be < {RECOVERY_THRESHOLD})")
    print(f"  Shallow residual (Depth<=0.1): {shallow_residual:.4f} (should be > 0.01)")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 5))
        for depth in DEPTH_LEVELS:
            sub = [r for r in logger.rows if abs(r[0] - depth) < 0.001]
            hmags = sorted(set(r[1] for r in sub))
            residuals = [
                sum(rr[3] for rr in sub if abs(rr[1] - hm) < 0.001) /
                max(1, sum(1 for rr in sub if abs(rr[1] - hm) < 0.001))
                for hm in hmags
            ]
            ax.plot(hmags, residuals, marker="o", label=f"Depth={depth:.2f}")
        ax.axhline(y=RECOVERY_THRESHOLD, color="r", linestyle="--", alpha=0.5, label="Recovery threshold")
        ax.set_xlabel("Harm Magnitude")
        ax.set_ylabel("Residual Error")
        ax.set_title("Self-Repair: Residual Error vs Harm Magnitude")
        ax.legend()
        ax.grid(True)

        plt.tight_layout()
        vis_path = os.path.join(os.path.dirname(__file__), "visualizations", "self_repair.png")
        plt.savefig(vis_path, dpi=150)
        plt.close()
        print(f"Saved: {vis_path}")
    except ImportError:
        print("(matplotlib not available)")

    return verdict


if __name__ == "__main__":
    run()
