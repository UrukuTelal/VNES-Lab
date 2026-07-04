"""Tests for the LLM Reviewer module."""

import json
import pytest
from unittest.mock import patch, MagicMock

from rlaaer.review.llm_reviewer import (
    ROLE_PROMPTS,
    _build_spec_summary,
    _build_results_summary,
    _parse_llm_response,
    _stub_review,
    call_reviewer,
)
from rlaaer.review.council_wrapper import CouncilWrapper


SAMPLE_SPEC = {
    "experiment": {
        "id": "009",
        "title": "LLM Review Test",
        "hypothesis": "If coupling increases then coherence decreases.",
        "status": "draft",
        "author": "R-LAAER",
        "created": "2026-07-03",
        "tags": ["cognition"],
    },
    "systems": {"vnes_lab": {"enabled": True}},
    "data_sources": [{"source": "census", "tier": 1, "rationale": "Population baseline"}],
    "parameters": {
        "independent": [
            {"name": "coupling", "domain": [0.0, 2.0], "steps": 5, "target": "vnes_lab",
             "source": "census", "rationale": "Test coupling range"},
        ],
        "controlled": [{"name": "seed", "value": 42}],
    },
    "metrics": {
        "stability": [{"name": "coherence", "comparator": "approx", "tolerance": 0.15, "extractor": "extract"}],
        "invariants": [{"name": "count", "comparator": "eq", "threshold": 100, "extractor": "extract"}],
    },
    "statistics": {
        "alpha": 0.05, "power": 0.80, "minimum_effect_size": 0.30, "method": "independent_t",
    },
    "execution": {
        "trials_per_condition": 10, "total_trials": 50, "max_duration_minutes": 30,
    },
    "review": {
        "pre_registration_required": True, "approval_threshold": 12, "max_revision_rounds": 3,
    },
    "publication": {
        "format": "markdown", "license": "CC-BY-4.0", "authors": [{"name": "R-LAAER"}],
    },
}

SAMPLE_RESULTS = {
    "status": "completed",
    "trials_completed": 50,
    "trials_failed": 0,
    "duration_seconds": 12.5,
    "metrics": {"mean_coherence": 0.72, "entropy": 1.3},
    "statistical_analysis": {
        "p_value": 0.003,
        "effect_size": 0.85,
        "is_significant": True,
    },
}


class TestRolePrompts:
    def test_all_roles_have_prompts(self):
        assert len(ROLE_PROMPTS) == 9

    def test_each_prompt_contains_verdict(self):
        for role, prompt in ROLE_PROMPTS.items():
            assert "verdict" in prompt, f"{role} prompt missing verdict instruction"
            assert "accept" in prompt, f"{role} prompt missing accept option"
            assert "reject" in prompt, f"{role} prompt missing reject option"

    def test_security_mentions_veto(self):
        assert "HARD VETO" in ROLE_PROMPTS["security_researcher"]

    def test_reproducibility_mentions_veto(self):
        assert "HARD VETO" in ROLE_PROMPTS["reproducibility_officer"]


class TestSpecSummary:
    def test_summary_contains_title(self):
        s = _build_spec_summary(SAMPLE_SPEC)
        assert "LLM Review Test" in s
        assert "009" in s

    def test_summary_contains_hypothesis(self):
        s = _build_spec_summary(SAMPLE_SPEC)
        assert "If coupling increases" in s

    def test_summary_contains_data_sources(self):
        s = _build_spec_summary(SAMPLE_SPEC)
        assert "census" in s

    def test_summary_contains_stats(self):
        s = _build_spec_summary(SAMPLE_SPEC)
        assert "0.05" in s  # alpha
        assert "0.8" in s  # power

    def test_summary_contains_execution(self):
        s = _build_spec_summary(SAMPLE_SPEC)
        assert "50 trials" in s
        assert "30min" in s

    def test_summary_truncation(self):
        s = _build_spec_summary(SAMPLE_SPEC, max_chars=100)
        assert s.endswith("[truncated]")
        assert len(s) < len(_build_spec_summary(SAMPLE_SPEC))


class TestResultsSummary:
    def test_summary_contains_status(self):
        s = _build_results_summary(SAMPLE_RESULTS)
        assert "completed" in s

    def test_summary_contains_trials(self):
        s = _build_results_summary(SAMPLE_RESULTS)
        assert "50" in s

    def test_summary_contains_stats(self):
        s = _build_results_summary(SAMPLE_RESULTS)
        assert "0.003" in s  # p_value
        assert "0.85" in s  # effect_size

    def test_empty_results(self):
        s = _build_results_summary({})
        assert "N/A" in s

    def test_truncation(self):
        big_results = {"metrics": {f"m{i}": i for i in range(100)}}
        s = _build_results_summary(big_results, max_chars=200)
        assert s.endswith("[truncated]")
        assert len(s) < len(_build_results_summary(big_results))


class TestParseLLMResponse:
    def test_plain_json(self):
        text = '{"verdict": "accept", "confidence": 0.9, "issues": [], "suggestions": []}'
        parsed = _parse_llm_response(text)
        assert parsed is not None
        assert parsed["verdict"] == "accept"
        assert parsed["confidence"] == 0.9

    def test_json_in_code_fence(self):
        text = 'Here is my review:\n```json\n{"verdict": "reject", "confidence": 0.7}\n```'
        parsed = _parse_llm_response(text)
        assert parsed is not None
        assert parsed["verdict"] == "reject"

    def test_json_with_extra_text(self):
        text = 'Some text before {"verdict": "conditional", "confidence": 0.6} and after'
        parsed = _parse_llm_response(text)
        assert parsed is not None
        assert parsed["verdict"] == "conditional"

    def test_non_json_response(self):
        parsed = _parse_llm_response("I cannot review this experiment.")
        assert parsed is None

    def test_empty_response(self):
        assert _parse_llm_response("") is None
        assert _parse_llm_response(None) is None

    def test_malformed_json(self):
        parsed = _parse_llm_response('{"verdict": broken}')
        assert parsed is None


class TestStubReview:
    def test_stub_returns_expected_keys(self):
        review = _stub_review("methodologist", "009")
        assert review["role"] == "methodologist"
        assert review["experiment_id"] == "009"
        assert review["verdict"] == "conditional"
        assert review["confidence"] == 0.5
        assert len(review["issues"]) > 0

    def test_stub_has_llm_source(self):
        review = _stub_review("test", "009")
        assert review["llm_source"] == "stub_fallback"


class TestCallReviewer:
    def test_unknown_role_returns_reject(self):
        review = call_reviewer("nonexistent_role", "009", SAMPLE_SPEC, {})
        assert review["verdict"] == "reject"
        assert review["confidence"] == 1.0

    def test_ollama_unreachable_returns_stub(self):
        with patch("requests.post") as mock_post:
            import requests
            mock_post.side_effect = requests.ConnectionError("Connection refused")
            review = call_reviewer("methodologist", "009", SAMPLE_SPEC, SAMPLE_RESULTS,
                                   ollama_url="http://localhost:1")
            assert review["llm_source"] == "stub_fallback"

    def test_ollama_timeout_returns_stub(self):
        with patch("requests.post") as mock_post:
            import requests
            mock_post.side_effect = requests.Timeout("Timed out")
            review = call_reviewer("methodologist", "009", SAMPLE_SPEC, SAMPLE_RESULTS,
                                   ollama_url="http://localhost:1")
            assert review["llm_source"] == "stub_fallback"

    def test_ollama_bad_json_returns_stub(self):
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {"message": {"content": "I don't know how to do JSON"}}
            mock_response.status_code = 200
            mock_post.return_value = mock_response
            review = call_reviewer("methodologist", "009", SAMPLE_SPEC, SAMPLE_RESULTS,
                                   ollama_url="http://localhost:1")
            assert review["llm_source"] == "stub_fallback"

    def test_ollama_success(self):
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "message": {
                    "content": '{"verdict": "accept", "confidence": 0.85, "issues": [], "suggestions": ["Add more trials"]}'
                }
            }
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            review = call_reviewer("theoretician", "009", SAMPLE_SPEC, SAMPLE_RESULTS,
                                   ollama_url="http://localhost:1")
            assert review["verdict"] == "accept"
            assert review["confidence"] == 0.85
            assert "Add more trials" in review["suggestions"]
            assert review["llm_source"].startswith("ollama:")


class TestCouncilWrapperWithLLM:
    def test_council_wrapper_uses_llm_by_default(self):
        cw = CouncilWrapper(use_llm=True)
        with patch("rlaaer.review.llm_reviewer.call_reviewer") as mock_llm:
            mock_llm.return_value = {
                "role": "methodologist",
                "experiment_id": "009",
                "verdict": "accept",
                "confidence": 0.9,
                "issues": [],
                "suggestions": [],
                "llm_source": "ollama:test",
            }
            review = cw._call_reviewer("methodologist", "009", SAMPLE_SPEC, SAMPLE_RESULTS)
            assert review["llm_source"] == "ollama:test"
            mock_llm.assert_called_once()

    def test_council_wrapper_llm_fallback_to_stub(self):
        cw = CouncilWrapper(use_llm=True)
        with patch("rlaaer.review.llm_reviewer.call_reviewer") as mock_llm:
            mock_llm.side_effect = Exception("LLM unavailable")
            review = cw._call_reviewer("methodologist", "009", SAMPLE_SPEC, SAMPLE_RESULTS)
            assert review.get("llm_source") != "ollama:test" or review["verdict"] == "accept"

    def test_council_wrapper_disabled_llm(self):
        cw = CouncilWrapper(use_llm=False)
        review = cw._call_reviewer("methodologist", "009", SAMPLE_SPEC, SAMPLE_RESULTS)
        assert review["verdict"] == "accept"
        assert review["confidence"] == 0.8

    def test_submit_for_review_with_llm(self):
        cw = CouncilWrapper(use_llm=True)
        with patch("rlaaer.review.llm_reviewer.call_reviewer") as mock_llm:
            mock_llm.return_value = {
                "role": "methodologist",
                "experiment_id": "009",
                "verdict": "accept",
                "confidence": 0.9,
                "issues": [],
                "suggestions": [],
                "llm_source": "ollama:test",
            }
            result = cw.submit_for_review("009", SAMPLE_SPEC, SAMPLE_RESULTS)
            assert "experiment_id" in result
            assert "accepts" in result
            assert "reviews" in result
