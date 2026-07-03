"""status.py — Single source of truth for VNES-Lab project status.

Fully derived from ground truth (regression_suite.py). No stored blocked
items — every invocation recomputes from current baselines + experiment
outputs.

AUTHORITATIVENESS RULE:
  Every status label (blocked, fixed, pending, regression) MUST trace to one of:
    1. regression_suite.py output   — ground truth test results
    2. status.py computation        — derived from the suite output
    3. commit-pinned artifact       — persistent file with specific commit hash
  Anything else must be explicitly labeled "non-authoritative interpretation".

Usage:
    python regressions/status.py              # print human-readable status
    python regressions/status.py --json        # machine-readable JSON
    python regressions/status.py --commits     # show last known commit per experiment
"""

import os, sys, json, subprocess, datetime

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
BASELINES_DIR = os.path.join(os.path.dirname(__file__), "baselines")


def git_commit(path: str = REPO_ROOT) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=path, capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def git_dirty(path: str = REPO_ROOT) -> bool:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=path, capture_output=True, text=True, timeout=10,
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def load_baseline(name: str) -> dict | None:
    path = os.path.join(BASELINES_DIR, f"{name}.json")
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        return json.load(f)


def run_suite() -> dict:
    """Run regression suite in fast mode and read JSON report."""
    tmp = os.path.join(REPO_ROOT, ".tmp_suite_report.json")
    result = subprocess.run(
        [sys.executable, "regressions/regression_suite.py", "--fast", "--json", tmp],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    if os.path.isfile(tmp):
        with open(tmp) as f:
            data = json.load(f)
        os.remove(tmp)
        return data
    return {"error": f"suite failed (exit {result.returncode})", "stdout": result.stdout, "stderr": result.stderr}


def build_status(suite_result: dict) -> dict:
    """Build derived status from suite result and baseline provenance."""
    commit = git_commit()
    dirty = git_dirty()

    status = {
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": commit,
        "git_dirty": dirty,
        "suite": suite_result.get("summary", {}).get("verdict", "UNKNOWN"),
        "summary": {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
        },
        "experiments": {},
        "blocked": [],
    }

    if "error" in suite_result:
        status["error"] = suite_result["error"]
        return status

    s = suite_result.get("summary", {})
    status["summary"]["total"] = s.get("total", 0)
    status["summary"]["passed"] = s.get("passed", 0)
    status["summary"]["failed"] = s.get("failed", 0)
    status["summary"]["errors"] = s.get("error", 0)

    for name, exp in suite_result.get("experiments", {}).items():
        baseline = load_baseline(name)
        prov = (baseline or {}).get("provenance", {})
        es = exp.get("summary", {})
        exp_status = {
            "status": exp.get("status", "UNKNOWN"),
            "passed": es.get("passed", 0),
            "total": es.get("total", 0),
            "baseline_commit": prov.get("git_commit", None),
            "baseline_dirty": prov.get("git_dirty", False),
        }
        status["experiments"][name] = exp_status

        # Blocked = any experiment with FAIL status
        if exp_status["status"] == "FAIL":
            for mname, m in exp.get("metrics", {}).items():
                if isinstance(m, dict) and m.get("passed") == False:
                    status["blocked"].append({
                        "experiment": name,
                        "metric": mname,
                        "reason": m.get("reason", ""),
                        "introduced_at_commit": prov.get("git_commit"),
                        "last_verified_commit": commit,
                    })

    status["blocked_count"] = len(status["blocked"])
    return status


def print_status(status: dict):
    print(f"\n{'='*60}")
    print(f"  VNES-Lab Project Status (derived)")
    print(f"  {status['timestamp']}")
    print(f"  git: {status['git_commit'][:12] if status['git_commit'] else 'N/A'}"
          f"{' (DIRTY)' if status.get('git_dirty') else ''}")
    print(f"{'='*60}")
    print(f"  Suite verdict: {status.get('suite', 'UNKNOWN')}")
    print(f"  {status['summary']['passed']}/{status['summary']['total']} passed"
          f"  |  {status['summary']['failed']} failed"
          f"  |  {status['summary']['errors']} errors")
    print(f"  Blocked: {status['blocked_count']}")
    for b in status["blocked"]:
        print(f"    [{b['experiment']}] {b['metric']}: {b['reason']}")
    if not status["blocked"]:
        print(f"    (none — all experiments passing)")
    print(f"{'='*60}\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Derive VNES-Lab project status from ground truth")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args()

    suite_result = run_suite()
    status = build_status(suite_result)

    if args.json:
        print(json.dumps(status, indent=2))
    else:
        print_status(status)

    return 1 if status["blocked_count"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
