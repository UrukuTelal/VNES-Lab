"""Data Scientist — transforms real-world data to VNES parameter space."""

import csv
import json
import os
from typing import Any

from rlaaer.config import REPO_ROOT, PIPELINE


class TransformationError(Exception):
    """Raised on transformation failure."""


class Transformer:
    """Transforms raw scraped data into VNES-compatible parameters."""

    def __init__(self):
        self.transformed_dir = os.path.join(os.path.dirname(PIPELINE["cache_dir"]), "transformed")
        os.makedirs(self.transformed_dir, exist_ok=True)

    def transform(self, dataset: dict, config: dict) -> dict:
        """Transform a dataset according to config. Returns transformation record."""
        source = dataset.get("source", "unknown")
        method = config.get("method", "identity")

        raw_data = dataset.get("data", {})
        transformed = self._apply_method(raw_data, method, config.get("params", {}))

        # Quality checks
        quality = self._assess_quality(transformed, method)

        record = {
            "source": source,
            "method": method,
            "input_rows": len(raw_data) if isinstance(raw_data, list) else 1,
            "output_rows": len(transformed) if isinstance(transformed, list) else 1,
            "quality_flags": quality["flags"],
            "quality_score": quality["score"],
            "transformed": transformed,
            "transformation_log": quality.get("log", []),
        }

        # Write transformed CSV
        self._write_csv(source, config.get("experiment_id", "unknown"), record)

        return record

    def _apply_method(self, data: Any, method: str, params: dict) -> Any:
        if method == "identity":
            return data
        elif method == "log_normalize":
            import math
            if isinstance(data, list):
                vals = [float(v) for v in data if v is not None]
                log_vals = [math.log(v + 1) for v in vals]
                m = sum(log_vals) / len(log_vals)
                s = (sum((v - m) ** 2 for v in log_vals) / len(log_vals)) ** 0.5 or 1
                return [(v - m) / s for v in log_vals]
            return data
        elif method == "min_max":
            if isinstance(data, list):
                vals = [float(v) for v in data if v is not None]
                lo, hi = min(vals), max(vals)
                if hi == lo:
                    return [0.0] * len(vals)
                return [(v - lo) / (hi - lo) for v in vals]
            return data
        elif method == "extract_field":
            field = params.get("field", "")
            if isinstance(data, dict):
                return data.get(field, {})
            return data
        else:
            raise TransformationError(f"Unknown transformation method: {method}")

    def _assess_quality(self, data: Any, method: str) -> dict:
        flags = []
        log = []

        if isinstance(data, list):
            if not data:
                flags.append("empty_result")
                log.append("Transformation produced empty list")

            n_none = sum(1 for v in data if v is None)
            if n_none > 0:
                msg = f"{n_none}/{len(data)} values are None"
                flags.append("null_values")
                log.append(msg)

            n_inf = sum(1 for v in data if isinstance(v, (int, float)) and v == float("inf"))
            if n_inf > 0:
                flags.append("infinite_values")
                log.append(f"{n_inf} infinite values detected")

        score = 1.0
        if "empty_result" in flags:
            score -= 0.5
        if "null_values" in flags:
            score -= 0.2
        if "infinite_values" in flags:
            score -= 0.3

        return {"flags": flags, "score": max(0.0, score), "log": log}

    def _write_csv(self, source: str, experiment_id: str, record: dict):
        path = os.path.join(self.transformed_dir, f"{experiment_id}_{source}.csv")
        data = record.get("transformed", [])

        if isinstance(data, list) and data:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["value"])
                for v in data:
                    writer.writerow([v])
        elif isinstance(data, dict):
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["key", "value"])
                for k, v in data.items():
                    writer.writerow([k, v])
