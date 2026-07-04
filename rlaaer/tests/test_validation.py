"""Tests for spec.yaml validation."""

import pytest
from rlaaer.validation import validate, SpecValidationError

MINIMAL_VALID_SPEC = {
    "experiment": {
        "id": "999",
        "title": "Test",
        "hypothesis": "If X then Y, because Z.",
        "status": "draft",
        "author": "test",
        "created": "2026-07-03",
        "tags": ["test"],
    },
    "systems": {
        "vnes_lab": {"enabled": True},
    },
    "data_sources": [
        {"source": "census", "tier": 1, "rationale": "test"},
    ],
    "parameters": {
        "independent": [
            {"name": "x", "domain": [0, 1], "steps": 5, "target": "vnes_lab", "source": "census", "rationale": "test"},
        ],
        "controlled": [
            {"name": "seed", "value": 42},
        ],
    },
    "metrics": {
        "stability": [
            {"name": "mean_coherence", "comparator": "approx", "tolerance": 0.15, "extractor": "metrics.extract"},
        ],
        "invariants": [
            {"name": "count", "comparator": "eq", "threshold": 100, "extractor": "metrics.extract"},
        ],
    },
    "statistics": {
        "alpha": 0.05,
        "power": 0.80,
        "minimum_effect_size": 0.30,
        "correction": "bonferroni",
        "method": "independent_t",
        "sample_size_justification": "n=10, power 80%",
    },
    "execution": {
        "trials_per_condition": 10,
        "total_trials": 100,
        "max_duration_minutes": 30,
        "checkpoint_interval_ticks": 1000,
        "rollback_on_failure": True,
    },
    "review": {
        "pre_registration_required": True,
        "approval_threshold": 12,
        "max_revision_rounds": 3,
    },
    "publication": {
        "format": "markdown",
        "license": "CC-BY-4.0",
        "authors": [{"name": "Test"}],
    },
}


class TestValidation:
    def test_valid_spec_passes(self):
        errors = validate(MINIMAL_VALID_SPEC)
        assert errors == []

    def test_missing_top_level(self):
        spec = MINIMAL_VALID_SPEC.copy()
        del spec["experiment"]
        errors = validate(spec)
        assert len(errors) == 1
        assert "experiment" in errors[0]

    def test_missing_experiment_fields(self):
        spec = MINIMAL_VALID_SPEC.copy()
        spec["experiment"] = {"id": "999"}
        errors = validate(spec)
        assert any("experiment" in e for e in errors)

    def test_invalid_status(self):
        spec = MINIMAL_VALID_SPEC.copy()
        spec["experiment"]["status"] = "invalid_status"
        errors = validate(spec)
        assert any("status" in e for e in errors)

    def test_hypothesis_no_period(self):
        spec = MINIMAL_VALID_SPEC.copy()
        spec["experiment"]["hypothesis"] = "No period"
        errors = validate(spec)
        assert any("period" in e for e in errors)

    def test_hypothesis_too_short(self):
        spec = MINIMAL_VALID_SPEC.copy()
        spec["experiment"]["hypothesis"] = "Hi."
        errors = validate(spec)
        assert any("short" in e for e in errors)

    def test_missing_systems(self):
        spec = MINIMAL_VALID_SPEC.copy()
        del spec["systems"]
        errors = validate(spec)
        assert any("systems" in e for e in errors)

    def test_missing_vnes_lab(self):
        spec = MINIMAL_VALID_SPEC.copy()
        spec["systems"] = {"engine": {"enabled": True}}
        errors = validate(spec)
        assert any("vnes_lab" in e for e in errors)

    def test_invalid_data_source_tier(self):
        spec = MINIMAL_VALID_SPEC.copy()
        spec["data_sources"][0]["tier"] = 4
        errors = validate(spec)
        assert any("tier" in e for e in errors)

    def test_missing_data_source_rationale(self):
        spec = MINIMAL_VALID_SPEC.copy()
        spec["data_sources"][0] = {"source": "test"}
        errors = validate(spec)
        assert any("rationale" in e for e in errors)

    def test_independent_param_no_domain(self):
        spec = MINIMAL_VALID_SPEC.copy()
        spec["parameters"]["independent"][0] = {"name": "x"}
        errors = validate(spec)
        assert any("domain" in e for e in errors)

    def test_controlled_param_no_value(self):
        spec = MINIMAL_VALID_SPEC.copy()
        spec["parameters"]["controlled"][0] = {"name": "seed"}
        errors = validate(spec)
        assert any("value" in e for e in errors)

    def test_stability_metric_wrong_comparator(self):
        spec = MINIMAL_VALID_SPEC.copy()
        spec["metrics"]["stability"][0]["comparator"] = "eq"
        errors = validate(spec)
        assert any("comparator" in e for e in errors)

    def test_invariant_metric_missing_threshold(self):
        spec = MINIMAL_VALID_SPEC.copy()
        spec["metrics"]["invariants"][0] = {"name": "count", "comparator": "eq", "extractor": "extract"}
        errors = validate(spec)
        assert any("threshold" in e for e in errors)

    def test_statistics_missing_alpha(self):
        spec = MINIMAL_VALID_SPEC.copy()
        del spec["statistics"]["alpha"]
        errors = validate(spec)
        assert any("alpha" in e for e in errors)

    def test_statistics_invalid_alpha(self):
        spec = MINIMAL_VALID_SPEC.copy()
        spec["statistics"]["alpha"] = 1.5
        errors = validate(spec)
        assert any("alpha" in e for e in errors)

    def test_statistics_invalid_power(self):
        spec = MINIMAL_VALID_SPEC.copy()
        spec["statistics"]["power"] = 0.0
        errors = validate(spec)
        assert any("power" in e for e in errors)

    def test_execution_missing_trials(self):
        spec = MINIMAL_VALID_SPEC.copy()
        del spec["execution"]["total_trials"]
        errors = validate(spec)
        assert any("total_trials" in e for e in errors)

    def test_review_missing_threshold(self):
        spec = MINIMAL_VALID_SPEC.copy()
        del spec["review"]["approval_threshold"]
        errors = validate(spec)
        assert any("approval_threshold" in e for e in errors)

    def test_publication_missing_license(self):
        spec = MINIMAL_VALID_SPEC.copy()
        del spec["publication"]["license"]
        errors = validate(spec)
        assert any("license" in e for e in errors)

    def test_publication_invalid_format(self):
        spec = MINIMAL_VALID_SPEC.copy()
        spec["publication"]["format"] = "html"
        errors = validate(spec)
        assert any("format" in e for e in errors)

    def test_empty_spec(self):
        errors = validate({})
        assert errors
        assert any("experiment" in e for e in errors)
