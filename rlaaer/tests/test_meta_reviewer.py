"""Tests for the Meta-Reviewer."""

import pytest
from rlaaer.review.meta_reviewer import MetaReviewer


class TestMetaReviewer:
    @pytest.fixture
    def meta(self):
        return MetaReviewer(max_revision_rounds=3)

    def test_unanimous_accept_publishes(self, meta):
        review = {
            "accepts": 9,
            "rejects": 0,
            "conditionals": 0,
            "veto_triggered": False,
            "total_reviews": 9,
            "reviews": {},
        }
        spec = {"review": {"approval_threshold": 12, "max_revision_rounds": 3}}
        decision = meta.decide(review, spec)
        assert decision["decision"] == "publish"

    def test_veto_triggers_reject(self, meta):
        review = {
            "accepts": 8,
            "rejects": 1,
            "conditionals": 0,
            "veto_triggered": True,
            "veto_roles": ["security_researcher"],
            "reviews": {},
        }
        spec = {"review": {"approval_threshold": 12, "max_revision_rounds": 3}}
        decision = meta.decide(review, spec)
        assert decision["decision"] == "reject"

    def test_mixed_reviews_triggers_revise(self, meta):
        review = {
            "accepts": 5,
            "rejects": 2,
            "conditionals": 2,
            "veto_triggered": False,
            "reviews": {
                "role1": {"issues": ["Fix method"], "suggestions": ["Add control"]},
                "role2": {"issues": [], "suggestions": []},
            },
        }
        spec = {"review": {"approval_threshold": 12, "max_revision_rounds": 3}}
        decision = meta.decide(review, spec)
        assert decision["decision"] == "revise"
        assert len(decision["action_items"]) > 0

    def test_sufficient_accepts_with_conditionals(self, meta):
        review = {
            "accepts": 12,
            "rejects": 0,
            "conditionals": 2,
            "veto_triggered": False,
            "total_reviews": 14,
            "reviews": {},
        }
        spec = {"review": {"approval_threshold": 12, "max_revision_rounds": 3}}
        decision = meta.decide(review, spec)
        assert decision["decision"] == "publish"  # threshold met, publish

    def test_insufficient_accepts_rejects(self, meta):
        review = {
            "accepts": 3,
            "rejects": 6,
            "conditionals": 0,
            "veto_triggered": False,
            "reviews": {},
        }
        spec = {"review": {"approval_threshold": 12, "max_revision_rounds": 3}}
        decision = meta.decide(review, spec)
        assert decision["decision"] == "reject"

    def test_publish_unanimous_skips_threshold(self, meta):
        """Unanimous accept publishes even if below threshold."""
        review = {
            "accepts": 9,
            "rejects": 0,
            "conditionals": 0,
            "veto_triggered": False,
            "total_reviews": 9,
            "reviews": {},
        }
        spec = {"review": {"approval_threshold": 12, "max_revision_rounds": 3}}
        decision = meta.decide(review, spec)
        assert decision["decision"] == "publish"

    def test_revision_decision_has_action_items(self, meta):
        review = {
            "accepts": 5,
            "rejects": 2,
            "conditionals": 0,
            "veto_triggered": False,
            "reviews": {
                "role_x": {"issues": ["Missing control variable"], "suggestions": []},
                "role_y": {"issues": [], "suggestions": ["Increase sample size"]},
            },
        }
        spec = {"review": {"approval_threshold": 12, "max_revision_rounds": 3}}
        decision = meta.decide(review, spec)
        assert "[role_x] Missing control variable" in decision["action_items"]
        assert "[role_y] Suggestion: Increase sample size" in decision["action_items"]
