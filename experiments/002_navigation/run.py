"""002_navigation — Attractor state seeking.

Hypothesis: An entity converges toward its target PSV via proportional
correction. Higher Flux → faster convergence but overshoot risk.
"""

import sys, os, math, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from lib.psv_core import PillarState, Entity, MetricLogger, NUM_PILLARS, PI

SEED = 42
TIMESTEPS = 500
TRIALS_PER_FLUX = 20
FLUX_LEVELS = [0.1, 0.3, 0.5, 0.7, 0.9]
CONVERGE_THRESHOLD = 0.02


def run():
    random.seed(SEED)
    logger = MetricLogger(
        base_dir=os.path.join(os.path.dirname(__file__), "metrics"),
        columns=["flux", "trial", "initial_dist", "converge_time", "path_efficiency", "final_error"],
    )

    for flux in FLUX_LEVELS:
        for trial in range(TRIALS_PER_FLUX):
            start = PillarState.random(seed=SEED + trial + int(flux * 100))
            target = PillarState.random(seed=SEED + 1000 + trial)
            state = start.copy()
            state.theta[14] = flux  # Flux

            initial_dist = state.distance(target)
            path_length = 0.0
            prev = state.copy()
            converged = False
            converge_step = TIMESTEPS

            for t in range(TIMESTEPS):
                for i in range(NUM_PILLARS):
                    diff = target.theta[i] - state.theta[i]
                    rate = flux * 0.2 + 0.02  # base + flux contribution
                    state.theta[i] += diff * rate
                state.clamp()

                path_length += state.distance(prev)
                prev = state.copy()

                if not converged and state.distance(target) < CONVERGE_THRESHOLD:
                    converged = True
                    converge_step = t

            final_error = state.distance(target)
            efficiency = initial_dist / max(path_length, 1e-12)
            logger.log(flux, trial, initial_dist, converge_step, efficiency, final_error)

    path = logger.save("navigation.csv")
    print(f"Saved: {path}")

    print(f"\n=== NAVIGATION RESULTS ===")
    print(f"{'Flux':>6} {'Trials':>6} {'Avg Converge':>12} {'Avg Efficiency':>14} {'Avg Error':>10}")
    for flux in FLUX_LEVELS:
        sub = [r for r in logger.rows if r[0] == flux]
        avg_ct = sum(r[3] for r in sub) / len(sub)
        avg_eff = sum(r[4] for r in sub) / len(sub)
        avg_err = sum(r[5] for r in sub) / len(sub)
        print(f"{flux:>6.1f} {len(sub):>6} {avg_ct:>12.1f} {avg_eff:>14.4f} {avg_err:>10.4f}")

    # Verdict: all trials converge within TIMESTEPS
    failures = sum(1 for r in logger.rows if r[3] >= TIMESTEPS - 1)
    print(f"\nVerdict: {'FAIL' if failures > 0 else 'PASS'}")
    print(f"  {failures}/{len(logger.rows)} trials failed to converge")
    verdict = "FAIL" if failures > 0 else "PASS"

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        for flux in FLUX_LEVELS:
            sub = [r for r in logger.rows if r[0] == flux]
            axes[0].scatter([r[2] for r in sub], [r[3] for r in sub], label=f"Flux={flux}", alpha=0.6)
        axes[0].set_xlabel("Initial Distance")
        axes[0].set_ylabel("Convergence Time (steps)")
        axes[0].set_title("Convergence Time vs Initial Distance")
        axes[0].legend()
        axes[0].grid(True)

        means = []
        for flux in FLUX_LEVELS:
            sub = [r for r in logger.rows if r[0] == flux]
            means.append((flux, sum(r[4] for r in sub) / len(sub)))
        axes[1].plot([m[0] for m in means], [m[1] for m in means], marker="D", linewidth=2)
        axes[1].axhline(y=1.0, color="r", linestyle="--", alpha=0.5, label="Ideal efficiency")
        axes[1].set_xlabel("Flux Level")
        axes[1].set_ylabel("Avg Path Efficiency")
        axes[1].set_title("Path Efficiency vs Flux")
        axes[1].legend()
        axes[1].grid(True)

        plt.tight_layout()
        vis_path = os.path.join(os.path.dirname(__file__), "visualizations", "navigation.png")
        plt.savefig(vis_path, dpi=150)
        plt.close()
        print(f"Saved: {vis_path}")
    except ImportError:
        print("(matplotlib not available)")

    return verdict


if __name__ == "__main__":
    run()
