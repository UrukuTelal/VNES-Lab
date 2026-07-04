"""Tests for the Council Wrapper."""

import json
import os

import pytest
from rlaaer.review.council_wrapper import AGENT_NAMES, PROMPT_VERSION, CouncilWrapper


class TestCouncilWrapper:
    @pytest.fixture
    def council(self):
        return CouncilWrapper(bridge_url="http://localhost:9999")

    @pytest.fixture
    def council_with_dir(self, tmp_path):
        return CouncilWrapper(bridge_url="http://localhost:9999",
                             experiments_dir=str(tmp_path))

    def test_submit_for_review_all_accept(self, council):
        spec = {"experiment": {"id": "001"}}
        results = {}
        review = council.submit_for_review("001", spec, results)

        assert review["total_reviews"] == 9
        assert review["accepts"] == 9
        assert review["passed"] is True
        assert "reviews" in review
        assert len(review["reviews"]) == 9

    def test_all_reviewer_roles_present(self, council):
        assert len(council.REVIEWER_ROLES) == 9
        assert "methodologist" in council.REVIEWER_ROLES
        assert "security_researcher" in council.REVIEWER_ROLES
        assert "reproducibility_officer" in council.REVIEWER_ROLES

    def test_agent_names_all_roles_present(self):
        assert len(AGENT_NAMES) == 9
        assert AGENT_NAMES["methodologist"] == "Veridian"
        assert AGENT_NAMES["security_researcher"] == "Havik"
        assert AGENT_NAMES["reproducibility_officer"] == "Pivot"
        assert AGENT_NAMES["literature_review_agent"] == "Archive"
        # Verify every REVIEWER_ROLE has a mapping
        for role in CouncilWrapper.REVIEWER_ROLES:
            assert role in AGENT_NAMES, f"Missing AGENT_NAMES mapping for {role}"

    def test_prompt_version_is_string(self):
        assert isinstance(PROMPT_VERSION, str)
        assert PROMPT_VERSION.startswith("v")

    def test_transcripts_created_on_submit(self, council_with_dir):
        spec = {"experiment": {"id": "999"}}
        results = {}
        council_with_dir.submit_for_review("999", spec, results)

        exp_dir = council_with_dir._find_experiment_dir("999")
        reviews_dir = os.path.join(exp_dir, "reviews")
        assert os.path.isdir(reviews_dir)

        for role in CouncilWrapper.REVIEWER_ROLES:
            path = os.path.join(reviews_dir, f"{role}.json")
            assert os.path.isfile(path), f"Missing transcript: {path}"

    def test_transcript_schema(self, council_with_dir):
        spec = {"experiment": {"id": "999"}}
        results = {}
        council_with_dir.submit_for_review("999", spec, results)

        exp_dir = council_with_dir._find_experiment_dir("999")
        transcript_path = os.path.join(exp_dir, "reviews", "methodologist.json")
        with open(transcript_path) as f:
            t = json.load(f)

        assert t["role"] == "Methodologist"
        assert t["agent_name"] == "Veridian"
        assert t["model"] == "stub"
        assert t["prompt_version"] == PROMPT_VERSION
        assert "timestamp" in t
        assert t["decision"] == "accept"
        assert isinstance(t["confidence"], float)
        assert isinstance(t["issues"], list)
        assert isinstance(t["suggestions"], list)

    def test_pre_registration_passes(self, council):
        spec = {
            "statistics": {"method": "independent_t", "alpha": 0.05},
            "parameters": {"independent": [{"name": "x"}]},
        }
        check = council.check_pre_registration(spec)
        assert check["passed"] is True

    def test_pre_registration_no_method(self, council):
        spec = {
            "statistics": {"alpha": 0.05},
            "parameters": {"independent": [{"name": "x"}]},
        }
        check = council.check_pre_registration(spec)
        assert check["passed"] is False
        assert any("method" in i.lower() for i in check["issues"])

    def test_pre_registration_no_independent(self, council):
        spec = {
            "statistics": {"method": "independent_t", "alpha": 0.05},
            "parameters": {},
        }
        check = council.check_pre_registration(spec)
        assert check["passed"] is False
        assert any("independent" in i.lower() for i in check["issues"])
