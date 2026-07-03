"""correlate.py -- Cross-experiment correlation analysis for behavioral diffs.

Takes a diff produced by regression_review.py and surfaces patterns:
  - Which experiments moved directionally
  - Which metrics co-varied across experiments
  - Potential trade-offs vs synergistic improvements

Usage:
    python regressions/correlate.py                          # read regression_diff.json
    python regressions/correlate.py --diff some_diff.json
    python regressions/correlate.py --history diffs/*.json   # multi-diff correlation
"""

import os, sys, json, math, itertools
from collections import defaultdict


def relative_drift(drift: float, baseline: float) -> float:
    """Compute relative change, handling zero baselines."""
    if baseline == 0:
        return drift  # absolute drift when baseline is zero
    return drift / abs(baseline)


def load_diff(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def analyze_diff(diff: dict) -> dict:
    """Extract per-experiment and cross-experiment change patterns from a single diff."""
    result = {
        "timestamp": diff.get("timestamp", "unknown"),
        "experiments": {},
        "cross_experiment": {},
        "summary": {"total_drift": 0, "significant_changes": 0, "trade_offs": []},
    }

    all_significant = {}  # metric_name -> (rel_drift, experiment)

    for exp_name, exp_data in sorted(diff.get("baselines", {}).items()):
        if "metrics" not in exp_data:
            continue

        metrics_detail = []
        exp_pos = 0.0
        exp_neg = 0.0
        exp_count = 0
        sig_pos = 0
        sig_neg = 0

        for mname, m in exp_data["metrics"].items():
            if "drift" not in m or "baseline_value" not in m:
                continue
            drift = m["drift"]
            baseline = m["baseline_value"]
            tol = m.get("tolerance", 0)
            passed = m.get("passed", True)
            rel = relative_drift(drift, baseline)

            is_significant = not passed and abs(drift) > tol * 0.5

            metrics_detail.append({
                "name": mname,
                "drift": drift,
                "relative_drift": rel,
                "baseline": baseline,
                "tolerance": tol,
                "passed": passed,
                "significant": is_significant,
            })

            if drift > 0.0:
                exp_pos += rel
            elif drift < 0.0:
                exp_neg += rel
            exp_count += 1

            if is_significant:
                all_significant[mname] = (rel, exp_name)
                if drift > 0:
                    sig_pos += 1
                else:
                    sig_neg += 1

        # Compute experiment-level direction
        net_drift = exp_pos + exp_neg
        direction = "~~"
        if sig_pos > sig_neg and sig_pos >= 2:
            direction = "++"
        elif sig_neg > sig_pos and sig_neg >= 2:
            direction = "--"
        elif sig_pos >= 1 and sig_neg >= 1:
            direction = "<>"

        experiment_report = {
            "direction": direction,
            "net_relative_drift": round(net_drift / max(exp_count, 1), 6),
            "positve_changes": sig_pos,
            "negative_changes": sig_neg,
            "significant_changes": len([m for m in metrics_detail if m["significant"]]),
            "stable_count": len([m for m in metrics_detail if m["passed"]]),
            "metrics": metrics_detail,
        }
        result["experiments"][exp_name] = experiment_report

    # Cross-experiment correlation
    if len(all_significant) >= 2:
        # Group by direction
        pos_metrics = [(n, r, e) for n, (r, e) in sorted(all_significant.items()) if r > 0]
        neg_metrics = [(n, r, e) for n, (r, e) in sorted(all_significant.items()) if r < 0]

        # Find cross-experiment co-movements
        exp_direction = defaultdict(lambda: {"pos": 0, "neg": 0})
        for (r, e) in all_significant.values():
            if r > 0:
                exp_direction[e]["pos"] += 1
            else:
                exp_direction[e]["neg"] += 1

        # Identify experiments that co-moved
        improving = sorted([e for e, d in exp_direction.items() if d["pos"] > d["neg"] and d["pos"] >= 2])
        declining = sorted([e for e, d in exp_direction.items() if d["neg"] > d["pos"] and d["neg"] >= 2])
        mixed = sorted([e for e, d in exp_direction.items() if d["pos"] > 0 and d["neg"] > 0])

        # Trade-offs: pair an improving metric with a declining one
        if pos_metrics and neg_metrics:
            for (n1, r1, e1), (n2, r2, e2) in itertools.product(pos_metrics[:5], neg_metrics[:5]):
                if e1 != e2:
                    result["summary"]["trade_offs"].append({
                        "improving": n1, "experiment": e1, "rel_drift": round(r1, 4),
                        "declining": n2, "experiment_opposite": e2, "rel_drift_opposite": round(r2, 4),
                    })

        result["cross_experiment"] = {
            "co_improving": improving,
            "co_declining": declining,
            "mixed": mixed,
            "improving_count": len(pos_metrics),
            "declining_count": len(neg_metrics),
        }
        result["summary"]["significant_changes"] = len(all_significant)

    return result


def print_correlation_report(result: dict):
    """Print a human-readable correlation report."""
    print(f"\n{'='*60}")
    print(f"  Behavioral Correlation Report")
    print(f"  {result['timestamp']}")
    print(f"{'='*60}")

    # Experiment overview
    print(f"\n  --- Experiment Overview ---")
    for exp_name, exp in sorted(result["experiments"].items()):
        d = exp["direction"]
        sig = exp["significant_changes"]
        stable = exp["stable_count"]
        print(f"  {d:>2} {exp_name:<25} "
              f"{'stable' if sig == 0 else f'{sig} metric(s) changed'}")

    # Significant changes detail
    sig_total = result["summary"]["significant_changes"]
    if sig_total == 0:
        print(f"\n  No significant changes detected.")
        print(f"\n{'='*60}")
        print(f"  VERDICT: All stable -- no behavioral drift")
        print(f"{'='*60}")
        return

    print(f"\n  --- Significant Changes ({sig_total} total) ---")
    for exp_name, exp in sorted(result["experiments"].items()):
        sig_metrics = [m for m in exp["metrics"] if m["significant"]]
        if not sig_metrics:
            continue
        print(f"\n  [{exp_name}]")
        for m in sorted(sig_metrics, key=lambda x: abs(x["drift"]), reverse=True):
            arrow = "++" if m["drift"] > 0 else "--"
            rel_pct = m["relative_drift"] * 100
            print(f"    {arrow} {m['name']:<45} {rel_pct:>+7.2f}%  "
                  f"(drift={m['drift']:+.6g}, tol={m['tolerance']:.6g})")

    # Cross-experiment co-movements
    ce = result.get("cross_experiment", {})
    if ce.get("co_improving"):
        print(f"\n  --- Co-Improving Clusters ---")
        print(f"  Experiments improving together: {', '.join(ce['co_improving'])}")
    if ce.get("co_declining"):
        print(f"\n  --- Co-Declining Clusters ---")
        print(f"  Experiments declining together: {', '.join(ce['co_declining'])}")

    trade_offs = result["summary"].get("trade_offs", [])
    if trade_offs:
        print(f"\n  --- Potential Trade-offs ---")
        for t in trade_offs[:5]:
            print(f"    {t['experiment']}.{t['improving']} ++{t['rel_drift']:.1%}  vs  "
                  f"{t['experiment_opposite']}.{t['declining']} --{abs(t['rel_drift_opposite']):.1%}")

    print(f"\n{'='*60}")
    print(f"  {sig_total} significant changes | "
          f"{len(set(n for n,_,_ in [(m['name'], m['drift'], e) for e, ex in result['experiments'].items() for m in ex['metrics'] if m['significant']]))} metrics affected")
    print(f"{'='*60}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--diff", default=None,
                        help="Path to diff JSON (default: regression_diff.json in project root)")
    parser.add_argument("--history", nargs="+", default=None,
                        help="Multiple diffs for cumulative correlation analysis")
    parser.add_argument("--json", metavar="FILE", nargs="?", const="correlation_report.json",
                        help="Write JSON output")
    args = parser.parse_args()

    if args.history:
        print("Multi-diff correlation not yet implemented -- requires commit history.")
        print("Use --diff for single-diff analysis.")
        return 1

    # Locate diff file
    diff_path = args.diff
    if diff_path is None:
        vnes_root = os.path.dirname(os.path.dirname(__file__))
        diff_path = os.path.join(vnes_root, "regression_diff.json")
    if not os.path.isfile(diff_path):
        diff_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "regression_diff.json")
    if not os.path.isfile(diff_path):
        print(f"Error: diff file not found at {diff_path}")
        return 1

    print(f"Reading diff: {diff_path}")
    diff = load_diff(diff_path)
    result = analyze_diff(diff)
    print_correlation_report(result)

    if args.json:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), args.json)
        with open(path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nReport saved: {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
