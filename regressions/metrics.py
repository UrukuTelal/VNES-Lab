"""metrics.py — Metric extractors for VNES-Lab scientific regression suite.

Each extractor returns {name: metric_dict} where metric_dict has:
  value:      float — the measured value (what the model actually produces)
  tolerance:  float — acceptable drift from baseline (for stability) or
                     epsilon for invariant comparisons
  comparator: str   — "approx" (stability, |actual - expected| <= tol)
                     "lt"/"gt"/"gte"/"lte" (invariant, actual [op] expected ± tol)
  description:str
  unit:       str
"""

import csv, math, os
from collections import defaultdict


def load_csv(path: str) -> list[dict[str, float]]:
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        return [{k: float(v) for k, v in row.items()} for row in reader]


def M(value, tolerance, comparator, description, unit):
    """Shorthand for metric dict construction."""
    return {
        "value": value,
        "tolerance": tolerance,
        "comparator": comparator,
        "description": description,
        "unit": unit,
    }


# ──────────────────────────────────────────────
# 001_homeostasis — Stability
# ──────────────────────────────────────────────
def extract_homeostasis(rows: list[dict]) -> dict:
    metrics = {}
    # STABILITY: drift values should stay close to baseline
    for row in rows:
        a, r, d = row["amplitude"], row["resistance"], row["final_drift"]
        metrics[f"drift_A{a}_R{r}"] = M(
            d, max(0.01, d * 0.15), "approx",
            f"Drift at amplitude={a}, resistance={r}",
            "radians"
        )

    # STABILITY: overshoot diffs between consecutive amplitudes (tracked as approx)
    overshoots = defaultdict(list)
    for row in rows:
        overshoots[row["resistance"]].append((row["amplitude"], row["overshoot"]))
    for res, vals in overshoots.items():
        vals.sort()
        for i in range(1, len(vals)):
            diff = vals[i][1] - vals[i-1][1]
            metrics[f"overshoot_diff_R{res}_A{vals[i][0]}"] = M(
                diff, max(0.0005, abs(diff) * 0.1), "approx",
                f"Overshoot change at R={res} from A={vals[i-1][0]} to A={vals[i][0]}",
                "radians"
            )
    return metrics


# ──────────────────────────────────────────────
# 002_navigation — Adaptation speed
# ──────────────────────────────────────────────
def extract_navigation(rows: list[dict]) -> dict:
    metrics = {}
    # STABILITY: mean convergence time per flux level
    by_flux = defaultdict(list)
    for row in rows:
        by_flux[row["flux"]].append(row["converge_time"])
    for flux, times in by_flux.items():
        mean_t = sum(times) / len(times)
        metrics[f"converge_time_Flux{flux}"] = M(
            mean_t, max(5.0, mean_t * 0.15), "approx",
            f"Mean convergence time at Flux={flux}",
            "steps"
        )
    # INVARIANT: all trials must converge to near-zero error
    max_err = max(row["final_error"] for row in rows)
    metrics["max_final_error"] = M(
        round(max_err, 12), 5e-13, "lt",
        "Maximum final error across all trials",
        "distance"
    )
    return metrics


# ──────────────────────────────────────────────
# 003_memory — Retention and decay
# ──────────────────────────────────────────────
def extract_memory(rows: list[dict]) -> dict:
    metrics = {}
    # STABILITY: recall precision at key noise levels (no overwrite)
    for target_noise in [0.0, 0.3, 0.5, 0.7, 0.9]:
        matches = [r for r in rows
                   if abs(r["overwrite_count"] - 0.0) < 0.01
                   and abs(r["noise_level"] - target_noise) < 0.01]
        if matches:
            metrics[f"recall_noise{target_noise}"] = M(
                matches[0]["recall_precision"], 0.05, "approx",
                f"Recall precision at noise={target_noise}",
                "ratio"
            )
    # STABILITY: memory fidelity after overwrites
    for target_ow in [1, 5, 10, 20]:
        matches = [r for r in rows
                   if abs(r["noise_level"] - 0.1) < 0.01
                   and int(r["overwrite_count"]) == target_ow]
        if matches:
            metrics[f"fidelity_after_{target_ow}writes"] = M(
                matches[0]["memory_fidelity"], 0.05, "approx",
                f"Memory fidelity after {target_ow} overwrites",
                "ratio"
            )
    return metrics


# ──────────────────────────────────────────────
# 004_prediction — Forecasting accuracy
# ──────────────────────────────────────────────
def extract_prediction(rows: list[dict]) -> dict:
    metrics = {}
    # STABILITY: MSE per horizon (averaged across all kp and trajectories)
    by_horizon = defaultdict(list)
    for row in rows:
        by_horizon[int(row["horizon"])].append(row["mse"])
    for horiz in sorted(by_horizon.keys()):
        mean_mse = sum(by_horizon[horiz]) / len(by_horizon[horiz])
        metrics[f"MSE_horizon{horiz}"] = M(
            mean_mse, max(mean_mse * 0.2, 0.001), "approx",
            f"Mean MSE at horizon={horiz}",
            "squared_radians"
        )

    # INVARIANT: MSE must grow super-linearly with horizon
    h5 = sum(by_horizon.get(5, [1])) / max(1, len(by_horizon.get(5, [1])))
    h20 = sum(by_horizon.get(20, [1])) / max(1, len(by_horizon.get(20, [1])))
    ratio = h20 / max(h5, 1e-10)
    metrics["MSE_superlinear_invariant"] = dict(
        M(ratio, 1e-6, "gt",
          f"MSE(h20)/MSE(h5) = {ratio:.4f} (must be > 2)",
          "boolean"),
        threshold=2.0,
    )
    return metrics


# ──────────────────────────────────────────────
# 005_multi_agent — Synchronization
# ──────────────────────────────────────────────
def extract_multi_agent(rows: list[dict]) -> dict:
    metrics = {}
    # STABILITY: sync index at each configuration
    for row in rows:
        c, w, s = row["coupling"], row["willpower_diff"], row["sync_index"]
        metrics[f"sync_C{c}_W{w}"] = M(
            s, 0.01, "approx",
            f"Sync index at coupling={c}, willpower_diff={w}",
            "cosine_sim"
        )
    # INVARIANT: zero-coupling should have highest energy transfer
    by_coupling = defaultdict(list)
    for row in rows:
        by_coupling[row["coupling"]].append(row["energy_transfer"])
    e0 = sum(by_coupling[0.0]) / len(by_coupling[0.0]) if 0.0 in by_coupling else 0
    for coupling in [c for c in by_coupling if c > 0]:
        ec = sum(by_coupling[coupling]) / len(by_coupling[coupling])
        metrics[f"energy_C0_gte_C{coupling}"] = dict(
            M(e0 - ec, 1e-10, "gte",
              f"Energy transfer: C=0 ({e0:.4f}) >= C={coupling} ({ec:.4f})",
              "boolean"),
            threshold=0.0,
        )
    return metrics


# ──────────────────────────────────────────────
# 006_self_repair — Recovery
# ──────────────────────────────────────────────
def extract_self_repair(rows: list[dict]) -> dict:
    metrics = {}
    # STABILITY: recovery time and residual at each config
    for row in rows:
        d, h, rt, re, im = (
            row["initial_depth"], row["harm_mag"],
            row["recovery_time"], row["residual_error"], row["integrity_min"]
        )
        metrics[f"recovery_time_D{d}_H{h}"] = M(
            rt, max(20.0, rt * 0.3), "approx",
            f"Recovery time at depth={d}, harm={h}",
            "steps"
        )
        metrics[f"residual_D{d}_H{h}"] = M(
            re, max(1e-6, re * 0.5), "approx",
            f"Residual error at depth={d}, harm={h}",
            "distance"
        )
    # INVARIANT: integrity must never drop below 0.5
    min_int = min(row["integrity_min"] for row in rows)
    metrics["min_integrity_invariant"] = dict(
        M(min_int, 1e-6, "gte",
          f"Minimum integrity = {min_int:.6f} across all trials (must be >= 0.5)",
          "boolean"),
        threshold=0.5,
    )
    return metrics


# ──────────────────────────────────────────────
# 007_tool_use — Energy efficiency
# ──────────────────────────────────────────────
def extract_tool_use(rows: list[dict]) -> dict:
    metrics = {}
    # STABILITY: mean efficiency per awareness/resistance combination
    by_config = defaultdict(list)
    for row in rows:
        key = (round(row["awareness"], 2), round(row["resistance"], 2))
        by_config[key].append(row["efficiency"])
    for (a, r), effs in by_config.items():
        mean_eff = sum(effs) / len(effs)
        metrics[f"efficiency_A{a}_R{r}"] = M(
            mean_eff, max(0.05, mean_eff * 0.1), "approx",
            f"Mean efficiency at awareness={a}, resistance={r}",
            "ratio"
        )
    return metrics


# ──────────────────────────────────────────────
# 008_emergence — Organization
# ──────────────────────────────────────────────
def extract_emergence(rows: list[dict]) -> dict:
    metrics = {}
    for row in rows:
        pop = int(row["population"])
        ratio = row["intra_sim"] / max(row["inter_sim"], 1e-10)
        metrics[f"cluster_count_P{pop}"] = M(
            row["cluster_count"], 0.5, "approx",
            f"Cluster count at population={pop}",
            "clusters"
        )
        metrics[f"modularity_P{pop}"] = M(
            row["modularity"], 0.05, "approx",
            f"Modularity at population={pop}",
            "score"
        )
        metrics[f"intra_inter_ratio_P{pop}"] = M(
            ratio, 0.1, "approx",
            f"Intra/inter similarity ratio at population={pop}",
            "ratio"
        )
    return metrics


# ──────────────────────────────────────────────
# Registry
# ──────────────────────────────────────────────
EXPERIMENTS = {
    "001_homeostasis": ("001_homeostasis/metrics/homeostasis.csv", extract_homeostasis),
    "002_navigation":  ("002_navigation/metrics/navigation.csv", extract_navigation),
    "003_memory":      ("003_memory/metrics/memory.csv", extract_memory),
    "004_prediction":  ("004_prediction/metrics/prediction.csv", extract_prediction),
    "005_multi_agent": ("005_multi_agent/metrics/multi_agent.csv", extract_multi_agent),
    "006_self_repair": ("006_self_repair/metrics/self_repair.csv", extract_self_repair),
    "007_tool_use":    ("007_tool_use/metrics/tool_use.csv", extract_tool_use),
    "008_emergence":   ("008_emergence/metrics/emergence.csv", extract_emergence),
}


def extract_all(experiments_dir: str) -> dict[str, dict]:
    results = {}
    for name, (csv_rel, extractor) in EXPERIMENTS.items():
        csv_path = os.path.join(experiments_dir, csv_rel)
        if not os.path.isfile(csv_path):
            print(f"  [SKIP] {name}: {csv_path} not found")
            continue
        rows = load_csv(csv_path)
        results[name] = extractor(rows)
    return results


if __name__ == "__main__":
    import os, json
    experiments_dir = os.path.join(os.path.dirname(__file__), "..", "experiments")
    all_metrics = extract_all(experiments_dir)
    for name, metrics in all_metrics.items():
        print(f"\n{name}:")
        for key, m in sorted(metrics.items()):
            print(f"  {key:<50} = {m['value']:>12.6f} ±{m['tolerance']} [{m['comparator']}]  ({m['description']})")
