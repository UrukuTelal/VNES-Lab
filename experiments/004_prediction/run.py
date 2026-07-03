"""004_prediction — Hopf-PID trajectory forecasting.

Hypothesis: Hopf-PID predicts periodic PSV trajectories within
MSE < 0.01 for horizon < 20 steps. Error grows super-linearly.
"""

import sys, os, math, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from lib.psv_core import PillarState, HopfPID, MetricLogger, NUM_PILLARS, PI, TAU

SEED = 42
TRAJECTORY_LENGTH = 200
TRAIN_SPLIT = 100
PREDICTION_HORIZONS = [5, 10, 20, 50, 100]
KP_VALUES = [0.1, 0.3, 0.5, 0.7, 0.9]
NUM_TRAJECTORIES = 5


def generate_trajectory(seed: int, length: int) -> list[PillarState]:
    """Generate a periodic PSV trajectory with coupled oscillators."""
    random.seed(seed)
    trajectory = []
    freqs = [0.01 + random.random() * 0.05 for _ in range(NUM_PILLARS)]
    phases = [random.random() * TAU for _ in range(NUM_PILLARS)]
    coupling = [[random.random() * 0.1 for _ in range(NUM_PILLARS)] for _ in range(NUM_PILLARS)]

    for t in range(length):
        theta = [PI / 2] * NUM_PILLARS
        for i in range(NUM_PILLARS):
            base = math.sin(freqs[i] * t + phases[i]) * 0.4 + 0.5
            for j in range(NUM_PILLARS):
                if i != j:
                    base += coupling[i][j] * math.sin(freqs[j] * t + phases[j])
            theta[i] = max(0.0, min(PI, theta[i] + base * 0.5))
        trajectory.append(PillarState.from_values(theta=theta))
    return trajectory


def compute_mse(predicted: list[PillarState], actual: list[PillarState]) -> float:
    if not predicted or not actual:
        return float("inf")
    n = min(len(predicted), len(actual))
    total = 0.0
    for i in range(n):
        for j in range(NUM_PILLARS):
            diff = predicted[i].theta[j] - actual[i].theta[j]
            total += diff * diff
    return total / (n * NUM_PILLARS)


def run():
    random.seed(SEED)
    logger = MetricLogger(
        base_dir=os.path.join(os.path.dirname(__file__), "metrics"),
        columns=["kp", "horizon", "mse", "trajectory_id"],
    )

    for traj_id in range(NUM_TRAJECTORIES):
        traj = generate_trajectory(SEED + traj_id, TRAJECTORY_LENGTH)
        train = traj[:TRAIN_SPLIT]
        test = traj[TRAIN_SPLIT:]

        for kp in KP_VALUES:
            pid = HopfPID(kp=kp, ki=kp * 0.2, kd=kp * 0.1)
            current = train[-1].copy()
            target = train[-1].copy()

            # Train PID on training data
            for step in train:
                _ = pid.compute(current, step)
                current = step.copy()

            for horizon in PREDICTION_HORIZONS:
                predictions = []
                pred_state = current.copy()
                for h in range(horizon):
                    correction = pid.compute(pred_state, target)
                    for i in range(NUM_PILLARS):
                        pred_state.theta[i] += (correction.theta[i] - pred_state.theta[i]) * 0.1
                    pred_state.clamp()
                    predictions.append(pred_state.copy())

                actual = test[:horizon]
                mse = compute_mse(predictions, actual)
                logger.log(kp, horizon, mse, traj_id)

    path = logger.save("prediction.csv")
    print(f"Saved: {path}")

    print(f"\n=== PREDICTION RESULTS ===")
    print(f"{'KP':>6} {'Horizon':>8} {'Avg MSE':>10}")
    for kp in KP_VALUES:
        sub = [r for r in logger.rows if abs(r[0] - kp) < 0.01]
        by_horizon = {}
        for r in sub:
            by_horizon.setdefault(int(r[1]), []).append(r[2])
        for h in PREDICTION_HORIZONS:
            if h in by_horizon:
                avg_mse = sum(by_horizon[h]) / len(by_horizon[h])
                print(f"{kp:>6.1f} {h:>8} {avg_mse:>10.6f}")

    # Check best kp at horizon=20
    h20_rows = [r for r in logger.rows if int(r[1]) == 20]
    best_kp = min(KP_VALUES, key=lambda kp: sum(
        r[2] for r in h20_rows if abs(r[0] - kp) < 0.01
    ) / max(1, sum(1 for r in h20_rows if abs(r[0] - kp) < 0.01)))

    h5_rows = [r for r in logger.rows if int(r[1]) == 5]
    mse_5 = sum(r[2] for r in h5_rows) / len(h5_rows) if h5_rows else 1.0
    verdict = "PASS" if mse_5 < 0.01 else "FAIL"
    print(f"\nVerdict: {verdict}")
    print(f"  Best kp at horizon=20: {best_kp}")
    print(f"  Avg MSE at horizon=5: {mse_5:.6f} (threshold: 0.01)")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 5))
        for kp in KP_VALUES:
            sub = [r for r in logger.rows if abs(r[0] - kp) < 0.01]
            by_h = {}
            for r in sub:
                by_h.setdefault(int(r[1]), []).append(r[2])
            horizons = sorted(by_h.keys())
            means = [sum(by_h[h]) / len(by_h[h]) for h in horizons]
            ax.plot(horizons, means, marker="o", label=f"kp={kp}")
        ax.set_xlabel("Prediction Horizon (steps)")
        ax.set_ylabel("MSE")
        ax.set_title("Prediction Error vs Horizon")
        ax.set_yscale("log")
        ax.legend()
        ax.grid(True)

        plt.tight_layout()
        vis_path = os.path.join(os.path.dirname(__file__), "visualizations", "prediction.png")
        plt.savefig(vis_path, dpi=150)
        plt.close()
        print(f"Saved: {vis_path}")
    except ImportError:
        print("(matplotlib not available)")

    return verdict


if __name__ == "__main__":
    run()
