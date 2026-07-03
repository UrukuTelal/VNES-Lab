"""regression_review.py — Review and classify behavioral changes.

Compare current metrics against baselines and classify each delta.
Three outcomes:

  STABLE     — within tolerance, no action needed.
  CHANGED    — outside tolerance but expected (baseline update required).
  REGRESSION — outside tolerance and unexpected (investigate).

Usage:
    python regressions/regression_review.py                # interactive review
    python regressions/regression_review.py --classify      # auto-classify unchanged
    python regressions/regression_review.py --json report   # output report only
"""

import os, sys, json, datetime
sys.path.insert(0, os.path.dirname(__file__))
from metrics import EXPERIMENTS, extract_all, load_csv
from regression_suite import (VNES_LAB_DIR, BASELINES_DIR, EXPERIMENTS_DIR,
                              COMPARATORS, COMPARATOR_LABELS)


def load_baseline(name: str) -> dict | None:
    path = os.path.join(BASELINES_DIR, f"{name}.json")
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        return json.load(f)


def check_metric(baseline_entry: dict, actual_value: float) -> dict:
    tolerance = baseline_entry["tolerance"]
    comparator = baseline_entry["comparator"]
    expected = baseline_entry.get("threshold", baseline_entry["value"])

    fn = COMPARATORS.get(comparator)
    passed = fn(actual_value, expected, tolerance) if fn else False
    drift = actual_value - baseline_entry["value"]

    return {
        "name": baseline_entry["name"],
        "expected": expected,
        "baseline_value": baseline_entry["value"],
        "actual": round(actual_value, 12),
        "drift": round(drift, 12),
        "tolerance": tolerance,
        "comparator": comparator,
        "passed": passed,
        "classification": "STABLE" if passed else "PENDING",
    }


def run_diff() -> dict:
    diff = {
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "baselines": {},
        "summary": {"stable": 0, "changed": 0, "regression": 0, "error": 0, "pending": 0},
    }

    for name in sorted(EXPERIMENTS.keys()):
        baseline = load_baseline(name)
        if baseline is None:
            diff["baselines"][name] = {"status": "ERROR", "error": "No baseline"}
            diff["summary"]["error"] += 1
            continue

        csv_rel, extractor = EXPERIMENTS[name]
        csv_path = os.path.join(EXPERIMENTS_DIR, csv_rel)
        rows = load_csv(csv_path)
        current = extractor(rows)

        exp = {"status": "STABLE", "provenance": baseline.get("provenance", {}),
               "metrics": {}, "summary": {"stable": 0, "changed": 0, "regression": 0, "pending": 0}}

        for entry in baseline["metrics"]:
            mname = entry["name"]
            actual = current.get(mname)
            if actual is None:
                exp["metrics"][mname] = {"status": "ERROR", "error": "Not found"}
                continue

            check = check_metric(entry, actual["value"])
            exp["metrics"][mname] = check
            exp["summary"][check["classification"].lower()] += 1

        if exp["summary"]["regression"] > 0:
            exp["status"] = "REGRESSION"
        elif exp["summary"]["changed"] > 0:
            exp["status"] = "CHANGED"

        diff["baselines"][name] = exp
        for k in ("stable", "changed", "regression", "pending"):
            diff["summary"][k] += exp["summary"][k]

    for k in ("stable", "changed", "regression", "pending"):
        diff["summary"][k] = diff["summary"].get(k, 0)
    diff["summary"]["total"] = sum(diff["summary"][k] for k in ("stable", "changed", "regression", "pending"))
    return diff


def classify_changed(diff: dict, name: str, metric_names: list[str]):
    """Mark specific metrics in an experiment as CHANGED (expected drift)."""
    exp = diff["baselines"].get(name)
    if not exp:
        return
    for mname in metric_names:
        m = exp["metrics"].get(mname)
        if m and m["classification"] == "PENDING":
            m["classification"] = "CHANGED"
            exp["summary"]["changed"] += 1
            exp["summary"]["pending"] -= 1
            diff["summary"]["changed"] += 1
            diff["summary"]["pending"] -= 1
    # Recompute experiment status
    if exp["summary"]["regression"] <= 0:
        exp["status"] = "CHANGED" if exp["summary"]["changed"] > 0 else "STABLE"


def print_diff(diff: dict):
    s = diff["summary"]
    print(f"\n{'='*60}")
    print(f"  VNES-Lab Behavioral Diff")
    print(f"  {diff['timestamp']}")
    print(f"{'='*60}")

    for name, exp in sorted(diff["baselines"].items()):
        print(f"\n  [{exp['status']:>10}] {name}")
        prov = exp.get("provenance", {})
        if prov.get("git_commit"):
            print(f"       baseline commit: {prov['git_commit'][:12]}"
                  f"{' (DIRTY)' if prov.get('git_dirty') else ''}")
        es = exp["summary"]
        total_m = es["stable"] + es["changed"] + es["regression"] + es["pending"]
        if es["regression"] == 0 and es["changed"] == 0 and es["pending"] == 0:
            print(f"       {es['stable']}/{total_m} stable")
            continue

        print(f"       {es['stable']} stable, {es['changed']} changed, {es['regression']} regressions, {es['pending']} pending")

        for mname, m in exp["metrics"].items():
            if m.get("classification") in ("CHANGED", "REGRESSION", "PENDING") or m.get("status") == "ERROR":
                cls = m.get("classification", "ERROR")
                drift = m.get("drift", 0)
                desc = m.get("name", mname)
                print(f"         [{cls:<10}] {desc:<50} drift={drift:+.6g}")

    print(f"\n{'='*60}")
    print(f"  {s['stable']} stable | {s['changed']} changed | {s['regression']} regressions")
    print(f"{'='*60}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--classify", nargs="*", default=None,
                        help="Auto-classify all PENDING as CHANGED (expected)")
    parser.add_argument("--accept", nargs="+", metavar="EXPERIMENT:METRIC",
                        help="Accept specific metrics as expected (e.g., 001_homeostasis:drift_A0.1_R0.1)")
    parser.add_argument("--json", metavar="FILE", nargs="?", const="regression_diff.json",
                        help="Write JSON diff report")
    args = parser.parse_args()

    diff = run_diff()

    if args.classify is not None:
        # Mark all PENDING as CHANGED
        for name, exp in diff["baselines"].items():
            metrics_to_accept = [mname for mname, m in exp.get("metrics", {}).items()
                                 if m.get("classification") == "PENDING"]
            classify_changed(diff, name, metrics_to_accept)

    if args.accept:
        for token in args.accept:
            if ":" not in token:
                print(f"  [SKIP] invalid format: {token} (use EXPERIMENT:METRIC)")
                continue
            exp_name, metric = token.split(":", 1)
            classify_changed(diff, exp_name, [metric])

    print_diff(diff)

    if args.json:
        path = os.path.join(VNES_LAB_DIR, args.json)
        with open(path, "w") as f:
            json.dump(diff, f, indent=2)
        print(f"\nReport saved: {path}")

    # Exit code: 0 if no regressions, 1 if any
    return 1 if diff["summary"]["regression"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
