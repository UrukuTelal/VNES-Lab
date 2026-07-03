"""007_tool_use — PSV manipulation of environment.

Hypothesis: Higher Awareness → higher manipulation efficiency.
Higher Resistance on target → lower effect at same cost.
Optimal ratio ~2:1.
"""

import sys, os, math, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from lib.psv_core import PillarState, MetricLogger, NUM_PILLARS, PI

SEED = 42
TIMESTEPS = 50
AWARENESS_LEVELS = [0.1, 0.3, 0.5, 0.7, 0.9]
RESISTANCE_LEVELS = [0.1, 0.3, 0.5]
TARGET_PILLAR = 2  # Force (the pillar to manipulate)
TRIALS_PER_CONFIG = 10


def run():
    random.seed(SEED)
    logger = MetricLogger(
        base_dir=os.path.join(os.path.dirname(__file__), "metrics"),
        columns=["awareness", "resistance", "effect_mag", "energy_cost", "efficiency"],
    )

    for awareness in AWARENESS_LEVELS:
        for resistance in RESISTANCE_LEVELS:
            for trial in range(TRIALS_PER_CONFIG):
                actor = PillarState.from_values(theta=[PI / 2] * NUM_PILLARS)
                actor.theta[0] = awareness  # Awareness
                actor.theta[2] = 0.5         # Force
                actor.theta[3] = 0.5         # Influence

                target = PillarState.from_values(theta=[PI / 2] * NUM_PILLARS)
                target.theta[4] = resistance  # Resistance

                initial_target = target.copy()
                initial_actor = actor.copy()

                for t in range(TIMESTEPS):
                    action_precision = awareness + random.gauss(0, 0.1 * (1 - awareness))
                    action_precision = max(0.0, min(1.0, action_precision))

                    pull = 0.05 * action_precision * (1 - target.theta[4])
                    target.theta[TARGET_PILLAR] += pull
                    target.theta[3] -= pull * 0.3  # Influence drain
                    target.clamp()

                    cost = 0.02 * action_precision
                    actor.theta[2] -= cost
                    actor.theta[9] -= cost * 0.5  # Warmth cost
                    actor.clamp()

                effect_mag = abs(target.theta[TARGET_PILLAR] - initial_target.theta[TARGET_PILLAR])
                energy_cost = sum(abs(actor.theta[i] - initial_actor.theta[i]) for i in range(NUM_PILLARS))
                efficiency = effect_mag / max(energy_cost, 1e-6)

                logger.log(awareness, resistance, effect_mag, energy_cost, efficiency)

    path = logger.save("tool_use.csv")
    print(f"Saved: {path}")

    print(f"\n=== TOOL USE RESULTS ===")
    print(f"{'Awareness':>10} {'Resistance':>10} {'Effect':>8} {'Cost':>8} {'Efficiency':>12}")
    for row in logger.rows:
        a, r, em, ec, eff = row
        print(f"{a:>10.2f} {r:>10.2f} {em:>8.4f} {ec:>8.4f} {eff:>12.4f}")

    # Check: awareness=0.7, resistance=0.1 should have high efficiency
    high_eff_rows = [r for r in logger.rows if r[0] >= 0.7 and r[1] <= 0.2]
    low_eff_rows = [r for r in logger.rows if r[0] <= 0.2 and r[1] >= 0.3]
    high_eff = sum(r[4] for r in high_eff_rows) / len(high_eff_rows) if high_eff_rows else 0
    low_eff = sum(r[4] for r in low_eff_rows) / len(low_eff_rows) if low_eff_rows else 0

    verdict = "PASS" if high_eff > low_eff * 1.5 else "FAIL"
    print(f"\nVerdict: {verdict}")
    print(f"  High Awareness/Low Resistance avg efficiency: {high_eff:.4f}")
    print(f"  Low Awareness/High Resistance avg efficiency: {low_eff:.4f}")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 5))
        for res in RESISTANCE_LEVELS:
            sub = [r for r in logger.rows if abs(r[1] - res) < 0.01]
            aware_levels = sorted(set(r[0] for r in sub))
            efficiencies = [
                sum(rr[4] for rr in sub if abs(rr[0] - a) < 0.01) /
                max(1, sum(1 for rr in sub if abs(rr[0] - a) < 0.01))
                for a in aware_levels
            ]
            ax.plot(aware_levels, efficiencies, marker="s", label=f"Resistance={res}")
        ax.set_xlabel("Awareness Level")
        ax.set_ylabel("Efficiency")
        ax.set_title("Tool Use Efficiency vs Awareness")
        ax.legend()
        ax.grid(True)

        plt.tight_layout()
        vis_path = os.path.join(os.path.dirname(__file__), "visualizations", "tool_use.png")
        plt.savefig(vis_path, dpi=150)
        plt.close()
        print(f"Saved: {vis_path}")
    except ImportError:
        print("(matplotlib not available)")

    return verdict


if __name__ == "__main__":
    run()
