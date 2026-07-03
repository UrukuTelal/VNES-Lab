"""regression_suite.py — Scientific regression tests for VNES-Lab.

Compares current experiment metrics against locked-in baselines.
Equivalent of software regression tests for system behavior.

Usage:
    python regressions/regression_suite.py
    python regressions/regression_suite.py --fast          # skip experiment runs (use existing CSV)
    python regressions/regression_suite.py --json          # JSON report only
"""

import os, sys, json, subprocess, datetime
sys.path.insert(0, os.path.dirname(__file__))
from metrics import EXPERIMENTS, extract_all, load_csv

VNES_LAB_DIR = os.path.dirname(os.path.dirname(__file__))
BASELINES_DIR = os.path.join(os.path.dirname(__file__), "baselines")
EXPERIMENTS_DIR = os.path.join(VNES_LAB_DIR, "experiments")

# Comparator functions
COMPARATORS = {
    "lt": lambda actual, expected, tol: actual < expected + tol,
    "gt": lambda actual, expected, tol: actual > expected - tol,
    "gte": lambda actual, expected, tol: actual >= expected - tol,
    "lte": lambda actual, expected, tol: actual <= expected + tol,
    "approx": lambda actual, expected, tol: abs(actual - expected) <= tol,
}

COMPARATOR_LABELS = {
    "lt": "should be <",
    "gt": "should be >",
    "gte": "should be >=",
    "lte": "should be <=",
    "approx": "should be ≈",
}


def run_experiment(name: str) -> bool:
    script = os.path.join(EXPERIMENTS_DIR, name, "run.py")
    if not os.path.isfile(script):
        return False
    result = subprocess.run(
        [sys.executable, script],
        cwd=VNES_LAB_DIR,
        capture_output=True, text=True,
    )
    return result.returncode == 0


def load_baseline(name: str) -> dict | None:
    path = os.path.join(BASELINES_DIR, f"{name}.json")
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        return json.load(f)


def check_metric(name: str, baseline_entry: dict, actual_value: float) -> dict:
    tolerance = baseline_entry["tolerance"]
    comparator = baseline_entry["comparator"]
    description = baseline_entry.get("description", name)
    unit = baseline_entry.get("unit", "")

    # For invariant checks, compare against the stored threshold (e.g., 0.0, 2.0, 0.5).
    # For stability checks ("approx"), compare against the stored measured value.
    if baseline_entry.get("threshold") is not None:
        expected = baseline_entry["threshold"]
    else:
        expected = baseline_entry["value"]

    fn = COMPARATORS.get(comparator)
    if fn is None:
        passed = False
        reason = f"Unknown comparator: {comparator}"
    else:
        passed = fn(actual_value, expected, tolerance)

    result = {
        "name": name,
        "description": description,
        "unit": unit,
        "expected": expected,
        "actual": round(actual_value, 12),
        "tolerance": tolerance,
        "comparator": comparator,
        "passed": passed,
        "drift": round(actual_value - expected, 12),
    }
    if not passed:
        if comparator == "approx":
            result["reason"] = (
                f"|actual - expected| = {abs(actual_value - expected):.6g} "
                f"> tolerance={tolerance}"
            )
        else:
            result["reason"] = (
                f"actual={actual_value:.6g} {COMPARATOR_LABELS.get(comparator, '?')} "
                f"expected±tol={expected:.6g}±{tolerance}"
            )
    return result


def run_suite(fast: bool = False) -> dict:
    suite_result = {
        "suite": "VNES-Lab Scientific Regression Suite",
        "version": "1.0",
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "experiments": {},
        "summary": {"total": 0, "passed": 0, "failed": 0, "error": 0},
    }

    for name in sorted(EXPERIMENTS.keys()):
        baseline = load_baseline(name)
        if baseline is None:
            suite_result["experiments"][name] = {
                "status": "ERROR",
                "error": f"No baseline found at baselines/{name}.json",
            }
            suite_result["summary"]["error"] += 1
            continue

        # Run experiment if not in fast mode
        if not fast:
            print(f"  Running {name}...", end=" ", flush=True)
            ok = run_experiment(name)
            if not ok:
                print("FAILED")
                suite_result["experiments"][name] = {
                    "status": "ERROR",
                    "error": "Experiment run failed (exit code != 0)",
                }
                suite_result["summary"]["error"] += 1
                continue
            print("OK")
        else:
            print(f"  Skipping run for {name} (--fast)")

        # Extract metrics
        csv_rel, extractor = EXPERIMENTS[name]
        csv_path = os.path.join(EXPERIMENTS_DIR, csv_rel)
        rows = load_csv(csv_path)
        current_metrics = extractor(rows)

        exp_result = {
            "status": "PASS",
            "metrics": {},
            "summary": {"total": 0, "passed": 0, "failed": 0},
        }

        for entry in baseline["metrics"]:
            mname = entry["name"]
            actual = current_metrics.get(mname)
            if actual is None:
                exp_result["metrics"][mname] = {
                    "status": "ERROR",
                    "error": "Metric not found in current run",
                }
                suite_result["summary"]["error"] += 1
                continue

            check = check_metric(mname, entry, actual["value"])
            exp_result["metrics"][mname] = check
            exp_result["summary"]["total"] += 1

            if check["passed"]:
                exp_result["summary"]["passed"] += 1
            else:
                exp_result["summary"]["failed"] += 1
                exp_result["status"] = "FAIL"

        suite_result["experiments"][name] = exp_result
        suite_result["summary"]["total"] += exp_result["summary"]["total"]
        suite_result["summary"]["passed"] += exp_result["summary"]["passed"]
        suite_result["summary"]["failed"] += exp_result["summary"]["failed"]

    suite_result["summary"]["verdict"] = (
        "PASS" if suite_result["summary"]["failed"] == 0 else "FAIL"
    )
    return suite_result


def print_report(result: dict):
    s = result["summary"]
    print(f"\n{'='*60}")
    print(f"  VNES-Lab Scientific Regression Suite")
    print(f"  {result['timestamp']}")
    print(f"{'='*60}")

    for exp_name, exp in result["experiments"].items():
        print(f"\n  [{exp.get('status', '?')}] {exp_name}")
        if "error" in exp:
            print(f"         {exp['error']}")
            continue
        es = exp["summary"]
        if es["failed"] == 0:
            print(f"       {es['passed']}/{es['total']} passed")
        else:
            print(f"       {es['passed']}/{es['total']} passed, {es['failed']} FAILED")
            for mname, m in exp["metrics"].items():
                if isinstance(m, dict) and m.get("passed") == False:
                    reason = m.get("reason", "")
                    print(f"         FAIL {mname:<35} {reason}")

    print(f"\n{'='*60}")
    verdict = s["verdict"]
    print(f"  VERDICT: {verdict}")
    print(f"  {s['passed']}/{s['total']} passed, {s['failed']} failed, {s['error']} errors")
    print(f"{'='*60}")
    return verdict


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--fast", action="store_true", help="Skip experiment runs")
    parser.add_argument("--json", metavar="FILE", nargs="?", const="regression_report.json",
                        help="Write JSON report")
    args = parser.parse_args()

    result = run_suite(fast=args.fast)
    verdict = print_report(result)

    if args.json:
        path = os.path.join(VNES_LAB_DIR, args.json)
        with open(path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nReport saved: {path}")

    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
