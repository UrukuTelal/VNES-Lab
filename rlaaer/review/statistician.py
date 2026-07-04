"""Statistician — effect sizes, confidence intervals, significance testing."""

import math
from typing import Any


class StatisticianError(Exception):
    """Raised on statistical computation failures."""


class Statistician:
    """Computes statistics on experiment results using pre-registered methods."""

    def analyze(self, results: dict, spec: dict) -> dict:
        """Run statistical analysis. Returns analysis record."""
        statistics = spec.get("statistics", {})
        method = statistics.get("method", "independent_t")
        alpha = statistics.get("alpha", 0.05)

        data = self._extract_data(results)

        if method == "independent_t":
            analysis = self._independent_t(data, alpha)
        elif method == "paired_t":
            analysis = self._paired_t(data, alpha)
        elif method == "anova":
            analysis = self._anova(data, alpha)
        elif method == "mann_whitney":
            analysis = self._mann_whitney(data, alpha)
        elif method == "correlation":
            analysis = self._correlation(data, alpha)
        else:
            raise StatisticianError(f"Unknown statistical method: {method}")

        # Effect size
        analysis["effect_size"] = self._cohens_d(data)
        analysis["power"] = statistics.get("power", 0.80)
        analysis["sample_size_adequate"] = self._check_sample_size(data, analysis["effect_size"], analysis["power"])
        analysis["alpha"] = alpha
        analysis["method"] = method

        return analysis

    def _extract_data(self, results: dict) -> dict:
        """Extract numerical data from results. Returns {condition: [values]}."""
        extracted = {}
        trials = results.get("trials", results.get("results", []))

        for trial in trials:
            params = trial.get("params", {})
            condition = str(params.get("coupling_strength", params.get("condition", "default")))
            value = trial.get("metric", trial.get("result", 0))

            if isinstance(value, dict):
                value = value.get("mean_coherence",
                         value.get("entropy_rate",
                         value.get("final_value", 0)))

            if condition not in extracted:
                extracted[condition] = []
            extracted[condition].append(float(value))

        return extracted

    def _independent_t(self, data: dict, alpha: float) -> dict:
        """Two-sample independent t-test."""
        groups = list(data.values())
        if len(groups) < 2:
            return {"significant": False, "error": "Need at least 2 groups"}

        # Welch's t-test approximation
        n1, n2 = len(groups[0]), len(groups[1])
        m1 = sum(groups[0]) / n1 if n1 else 0
        m2 = sum(groups[1]) / n2 if n2 else 0
        v1 = sum((x - m1) ** 2 for x in groups[0]) / (n1 - 1) if n1 > 1 else 0
        v2 = sum((x - m2) ** 2 for x in groups[1]) / (n2 - 1) if n2 > 1 else 0

        se = math.sqrt(v1 / n1 + v2 / n2) if n1 and n2 else 0
        t_stat = (m1 - m2) / se if se > 0 else 0

        # Degrees of freedom (Welch-Satterthwaite)
        df_num = (v1 / n1 + v2 / n2) ** 2 if n1 and n2 else 0
        df_den = (v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1) if n1 > 1 and n2 > 1 else 1
        df = df_num / df_den if df_den > 0 else 1

        # Normal approximation for p-value (accurate for df > 5)
        from math import erfc, sqrt
        def norm_cdf(z):
            return 0.5 * erfc(-z / sqrt(2))
        p_value = 2 * (1 - norm_cdf(abs(t_stat))) if df >= 1 and abs(t_stat) < 1e6 else 0.0

        return {
            "test": "independent_t",
            "t_statistic": t_stat,
            "degrees_freedom": df,
            "p_value": p_value,
            "significant": p_value < alpha,
            "group_means": [m1, m2],
            "group_sizes": [n1, n2],
        }

    def _paired_t(self, data: dict, alpha: float) -> dict:
        return {"test": "paired_t", "note": "Not implemented — stub"}

    def _anova(self, data: dict, alpha: float) -> dict:
        return {"test": "anova", "note": "Not implemented — stub"}

    def _mann_whitney(self, data: dict, alpha: float) -> dict:
        return {"test": "mann_whitney", "note": "Not implemented — stub"}

    def _correlation(self, data: dict, alpha: float) -> dict:
        return {"test": "correlation", "note": "Not implemented — stub"}

    def _cohens_d(self, data: dict) -> float:
        groups = list(data.values())
        if len(groups) < 2:
            return 0.0
        n1, n2 = len(groups[0]), len(groups[1])
        m1 = sum(groups[0]) / n1 if n1 else 0
        m2 = sum(groups[1]) / n2 if n2 else 0
        v1 = sum((x - m1) ** 2 for x in groups[0]) / (n1 - 1) if n1 > 1 else 0
        v2 = sum((x - m2) ** 2 for x in groups[1]) / (n2 - 1) if n2 > 1 else 0
        s_pooled = math.sqrt(((n1 - 1) * v1 + (n2 - 1) * v2) / (n1 + n2 - 2)) if (n1 + n2) > 2 else 1
        return (m1 - m2) / s_pooled if s_pooled > 0 else 0

    def _check_sample_size(self, data: dict, effect_size: float, power: float) -> bool:
        groups = list(data.values())
        if len(groups) < 2:
            return False
        return len(groups[0]) >= 5 and len(groups[1]) >= 5
