"""Tests for the Statistician."""

import pytest
from rlaaer.review.statistician import Statistician


class TestStatistician:
    @pytest.fixture
    def stat(self):
        return Statistician()

    def test_independent_t_significant(self, stat):
        data = {
            "control": [1.0, 1.1, 0.9, 1.0, 1.0, 1.1, 0.9, 1.0, 1.0, 1.1],
            "treatment": [2.0, 2.1, 1.9, 2.0, 2.0, 2.1, 1.9, 2.0, 2.0, 2.1],
        }
        results = {"results": [{"params": {"condition": "control"}, "result": 1.0}]}
        # Override data extraction for test
        stat._extract_data = lambda r: data

        spec = {"statistics": {"method": "independent_t", "alpha": 0.05, "power": 0.80}}
        analysis = stat.analyze(results, spec)
        assert analysis["significant"] is True
        assert analysis["p_value"] < 0.05

    def test_independent_t_not_significant(self, stat):
        data = {
            "control": [1.0, 1.01, 0.99, 1.0, 1.0],
            "treatment": [1.0, 1.02, 0.98, 1.0, 1.01],
        }
        stat._extract_data = lambda r: data

        spec = {"statistics": {"method": "independent_t", "alpha": 0.05, "power": 0.80}}
        analysis = stat.analyze({}, spec)
        assert analysis["significant"] is False

    def test_cohens_d_large(self, stat):
        data = {
            "control": [1.0, 1.1, 0.9, 1.0, 1.0, 1.1, 0.9, 1.0, 1.0, 1.1],
            "treatment": [3.0, 3.1, 2.9, 3.0, 3.0, 3.1, 2.9, 3.0, 3.0, 3.1],
        }
        d = stat._cohens_d(data)
        assert abs(d) > 1.0  # large effect

    def test_cohens_d_zero(self, stat):
        data = {
            "control": [1.0, 1.0, 1.0],
            "treatment": [1.0, 1.0, 1.0],
        }
        d = stat._cohens_d(data)
        assert abs(d) < 0.01

    def test_unknown_method(self, stat):
        spec = {"statistics": {"method": "bayesian_magic", "alpha": 0.05}}
        with pytest.raises(Exception):
            stat.analyze({}, spec)

    def test_sample_size_check(self, stat):
        stat._extract_data = lambda r: {"a": [1, 2, 3, 4, 5], "b": [6, 7, 8, 9, 10]}
        spec = {"statistics": {"method": "independent_t", "alpha": 0.05, "power": 0.80}}
        analysis = stat.analyze({}, spec)
        assert analysis["sample_size_adequate"] is True
