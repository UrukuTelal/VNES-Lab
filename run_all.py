"""run_all.py — Batch runner for all PSV experiments.

Usage:
    python run_all.py              # Run all experiments
    python run_all.py 001 003 005  # Run specific experiments
"""

import sys, os, subprocess, time

EXPERIMENTS = [
    "001_homeostasis",
    "002_navigation",
    "003_memory",
    "004_prediction",
    "005_multi_agent",
    "006_self_repair",
    "007_tool_use",
    "008_emergence",
]


def main():
    if len(sys.argv) > 1:
        selected = [s for s in sys.argv[1:] if s in [e[:3] for e in EXPERIMENTS] or s in EXPERIMENTS]
        if not selected:
            print(f"Usage: {sys.argv[0]} [experiment_id ...]")
            print(f"Available: {', '.join(e[:3] for e in EXPERIMENTS)}")
            sys.exit(1)
        to_run = [e for e in EXPERIMENTS if any(e.startswith(s) for s in selected)]
    else:
        to_run = EXPERIMENTS

    base_dir = os.path.dirname(__file__)
    results = []

    print("=" * 60)
    print("VNES-Lab: Batch Experiment Runner")
    print("=" * 60)

    for exp in to_run:
        exp_dir = os.path.join(base_dir, "experiments", exp)
        script = os.path.join(exp_dir, "run.py")
        if not os.path.isfile(script):
            print(f"\n[SKIP] {exp} — no run.py found")
            continue

        print(f"\n[{'-'*50}]")
        print(f"[RUNNING] {exp}")
        print(f"[{'-'*50}]")

        start = time.time()
        proc = subprocess.run(
            [sys.executable, script],
            cwd=base_dir,
            capture_output=False,
            text=True,
        )
        elapsed = time.time() - start
        verdict = "PASS" if proc.returncode == 0 else "FAIL"
        results.append((exp, verdict, elapsed))
        print(f"\n[{'-'*50}]")
        print(f"[DONE] {exp} — {verdict} ({elapsed:.2f}s)")
        print(f"[{'-'*50}]")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for exp, verdict, elapsed in results:
        print(f"  {exp:<25} {verdict:>5}  ({elapsed:.2f}s)")
    print("=" * 60)


if __name__ == "__main__":
    main()
