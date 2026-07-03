"""generate_baselines.py — Run all experiments, extract metrics, lock baselines.

Usage:
    python regressions/generate_baselines.py
"""

import os, sys, json, subprocess, datetime
sys.path.insert(0, os.path.dirname(__file__))
from metrics import EXPERIMENTS, extract_all

VNES_LAB_DIR = os.path.dirname(os.path.dirname(__file__))
BASELINES_DIR = os.path.join(os.path.dirname(__file__), "baselines")
EXPERIMENTS_DIR = os.path.join(VNES_LAB_DIR, "experiments")


def run_experiment(name: str) -> bool:
    script = os.path.join(EXPERIMENTS_DIR, name, "run.py")
    if not os.path.isfile(script):
        print(f"  [SKIP] {name}: no run.py at {script}")
        return False

    print(f"  Running {name}...", end=" ", flush=True)
    result = subprocess.run(
        [sys.executable, script],
        cwd=VNES_LAB_DIR,
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("FAILED")
        print(result.stderr[-500:])
        return False
    print("OK")
    return True


def to_baseline_dict(name: str, metrics: dict) -> dict:
    entries = []
    for key, m in sorted(metrics.items()):
        entry = {
            "name": key,
            "value": round(m["value"], 12),
            "tolerance": m["tolerance"],
            "comparator": m["comparator"],
            "description": m["description"],
            "unit": m["unit"],
        }
        if "threshold" in m:
            entry["threshold"] = m["threshold"]
        entries.append(entry)
    return {
        "experiment": name,
        "generated": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "version": "1.0",
        "metric_count": len(entries),
        "metrics": entries,
    }


def main():
    os.makedirs(BASELINES_DIR, exist_ok=True)
    results = {}

    for name in sorted(EXPERIMENTS.keys()):
        print(f"\n{'='*50}")
        print(f"  {name}")
        print(f"{'='*50}")
        success = run_experiment(name)
        results[name] = "RUN_OK" if success else "RUN_FAILED"

    print(f"\n{'='*50}")
    print("  Extracting metrics...")
    print(f"{'='*50}")

    all_metrics = extract_all(EXPERIMENTS_DIR)
    for name, metrics in all_metrics.items():
        baseline = to_baseline_dict(name, metrics)
        out_path = os.path.join(BASELINES_DIR, f"{name}.json")
        with open(out_path, "w") as f:
            json.dump(baseline, f, indent=2)
        print(f"  {name}: {baseline['metric_count']} metrics -> {out_path}")

    # Summary
    total_metrics = sum(len(m) for m in all_metrics.values())
    print(f"\n{'='*50}")
    print(f"  Generated {total_metrics} metrics across {len(all_metrics)} experiments")
    print(f"  Baselines: {BASELINES_DIR}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
