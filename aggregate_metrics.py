"""aggregate_metrics.py — Collect all experiment metrics into summary CSVs."""

import os, csv, glob
from collections import defaultdict


def load_csv(path: str) -> list[list[str]]:
    with open(path, "r", newline="") as f:
        reader = csv.reader(f)
        return list(reader)


def main():
    base_dir = os.path.dirname(__file__)
    experiments_dir = os.path.join(base_dir, "experiments")
    out_dir = os.path.join(base_dir, "metrics")
    os.makedirs(out_dir, exist_ok=True)

    all_csvs = glob.glob(os.path.join(experiments_dir, "*", "metrics", "*.csv"))
    print(f"Found {len(all_csvs)} metric files")
    for csv_path in all_csvs:
        rel = os.path.relpath(csv_path, experiments_dir)
        exp_name = rel.split(os.sep)[0]
        out_name = f"{exp_name}.csv"
        out_path = os.path.join(out_dir, out_name)
        data = load_csv(csv_path)
        with open(out_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(data)
        print(f"  {csv_path} → {out_path}")

    # Cross-experiment summary
    summary_path = os.path.join(out_dir, "summary.csv")
    with open(summary_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["experiment", "file", "rows", "columns"])
        for csv_path in all_csvs:
            rel = os.path.relpath(csv_path, experiments_dir)
            exp_name = rel.split(os.sep)[0]
            data = load_csv(csv_path)
            writer.writerow([exp_name, rel, len(data) - 1, len(data[0]) if data else 0])
    print(f"\nSummary: {summary_path}")


if __name__ == "__main__":
    main()
