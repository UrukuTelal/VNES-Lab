"""005_multi_agent — Agent interaction dynamics.

Hypothesis: Two coupled PSV entities synchronize over time.
Sync_index > 0.9 when coupling > 0.3 and Willpower diff < 0.2.
"""

import sys, os, math, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from lib.psv_core import PillarState, MetricLogger, NUM_PILLARS, PI

SEED = 42
TIMESTEPS = 300
COUPLING_LEVELS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
WILLPOWER_DIFFS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
SYNC_THRESHOLD = 0.9


def run():
    random.seed(SEED)
    logger = MetricLogger(
        base_dir=os.path.join(os.path.dirname(__file__), "metrics"),
        columns=["coupling", "willpower_diff", "sync_index", "convergence_time", "energy_transfer"],
    )

    for coupling in COUPLING_LEVELS:
        for wp_diff in WILLPOWER_DIFFS:
            a = PillarState.random(seed=SEED)
            b = PillarState.random(seed=SEED + 100)
            b.theta[1] = min(PI, max(0, a.theta[1] + wp_diff))  # Willpower offset

            sync_over_time = []
            converged = False
            converge_step = TIMESTEPS

            for t in range(TIMESTEPS):
                for i in range(NUM_PILLARS):
                    influence = coupling * (a.theta[3] - b.theta[3]) * 0.01
                    pull = (a.theta[i] - b.theta[i]) * coupling * 0.05
                    a.theta[i] -= pull
                    b.theta[i] += pull
                    a.theta[3] += influence  # Influence
                    b.theta[3] -= influence
                a.clamp()
                b.clamp()

                sync = a.similarity(b)
                sync_over_time.append(sync)

                if not converged and sync > SYNC_THRESHOLD:
                    converged = True
                    converge_step = t

            final_sync = sync_over_time[-1] if sync_over_time else 0.0
            energy = sum(abs(a.theta[i] - b.theta[i]) for i in range(NUM_PILLARS)) / NUM_PILLARS
            logger.log(coupling, wp_diff, final_sync, converge_step, energy)

    path = logger.save("multi_agent.csv")
    print(f"Saved: {path}")

    print(f"\n=== MULTI-AGENT RESULTS ===")
    print(f"{'Coupling':>10} {'WillDiff':>10} {'Sync':>8} {'Converge':>10}")
    for row in logger.rows:
        c, w, s, ct, _ = row
        marker = " [SYNC]" if s > SYNC_THRESHOLD else ""
        print(f"{c:>10.1f} {w:>10.1f} {s:>8.4f} {ct:>10.0f}{marker}")

    sync_03 = [r for r in logger.rows if abs(r[0] - 0.3) < 0.01 and abs(r[1] - 0.2) < 0.01]
    sync_high = sum(1 for r in logger.rows if r[2] > SYNC_THRESHOLD)
    total = len(logger.rows)
    print(f"\nVerdict: {'PASS' if sync_high > total * 0.3 else 'FAIL'}")
    print(f"  {sync_high}/{total} conditions achieved sync > {SYNC_THRESHOLD}")
    verdict = "PASS" if sync_high > total * 0.3 else "FAIL"

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 6))
        im = ax.scatter(
            [r[0] for r in logger.rows], [r[1] for r in logger.rows],
            c=[r[2] for r in logger.rows], cmap="viridis", s=80, vmin=0, vmax=1,
        )
        ax.set_xlabel("Coupling Strength")
        ax.set_ylabel("Willpower Difference")
        ax.set_title("Final Sync Index")
        plt.colorbar(im, ax=ax, label="Sync Index")
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        vis_path = os.path.join(os.path.dirname(__file__), "visualizations", "multi_agent.png")
        plt.savefig(vis_path, dpi=150)
        plt.close()
        print(f"Saved: {vis_path}")
    except ImportError:
        print("(matplotlib not available)")

    return verdict


if __name__ == "__main__":
    run()
