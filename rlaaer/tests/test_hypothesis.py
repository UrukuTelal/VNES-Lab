"""Tests for the Hypothesis Generator."""

import pytest
from rlaaer.design.hypothesis import Hypothesis, HypothesisGenerator


class TestHypothesis:
    def test_valid_hypothesis(self):
        h = Hypothesis(
            statement="If coupling strength increases then population coherence will decrease, because competing attractors destabilize consensus.",
            effect_direction="negative",
            minimal_detectable_effect=0.3,
            citations=["arxiv:2304.12345"],
        )
        gen = HypothesisGenerator()
        errors = gen.validate(h)
        assert errors == []

    def test_missing_period(self):
        h = Hypothesis(
            statement="If X then Y because Z",
            effect_direction="positive",
            minimal_detectable_effect=0.3,
        )
        gen = HypothesisGenerator()
        errors = gen.validate(h)
        assert any("period" in e for e in errors)

    def test_too_short(self):
        h = Hypothesis(
            statement="Hi.",
            effect_direction="positive",
            minimal_detectable_effect=0.3,
        )
        gen = HypothesisGenerator()
        errors = gen.validate(h)
        assert any("short" in e for e in errors)

    def test_too_long(self):
        h = Hypothesis(
            statement="If X then Y." + "x" * 500,
            effect_direction="positive",
            minimal_detectable_effect=0.3,
        )
        gen = HypothesisGenerator()
        errors = gen.validate(h)
        assert any("long" in e for e in errors)

    def test_invalid_effect_direction(self):
        h = Hypothesis(
            statement="If X then Y because Z.",
            effect_direction="sideways",
            minimal_detectable_effect=0.3,
        )
        gen = HypothesisGenerator()
        errors = gen.validate(h)
        assert any("effect_direction" in e for e in errors)

    def test_zero_effect_size(self):
        h = Hypothesis(
            statement="If X then Y because Z.",
            effect_direction="positive",
            minimal_detectable_effect=0.0,
        )
        gen = HypothesisGenerator()
        errors = gen.validate(h)
        assert any("minimal_detectable_effect" in e for e in errors)

    def test_invalid_citations(self):
        h = Hypothesis(
            statement="If X then Y because Z.",
            effect_direction="positive",
            minimal_detectable_effect=0.3,
            citations=["not_a_valid_citation"],
        )
        gen = HypothesisGenerator()
        errors = gen.validate(h)
        assert any("Citation" in e for e in errors)

    def test_no_if_then(self):
        h = Hypothesis(
            statement="This is a statement without a conditional structure.",
            effect_direction="positive",
            minimal_detectable_effect=0.3,
        )
        gen = HypothesisGenerator()
        errors = gen.validate(h)
        assert any("if" in e.lower() for e in errors)

    def test_missing_quantifiable_term(self):
        h = Hypothesis(
            statement="If X then Y because Z.",
            effect_direction="positive",
            minimal_detectable_effect=0.3,
        )
        gen = HypothesisGenerator()
        errors = gen.validate(h)
        assert any("quantifiable" in e for e in errors)

    def test_novelty_check(self):
        gen = HypothesisGenerator(existing_ids={"001", "002"})
        h = Hypothesis(
            statement="If coupling increases then coherence decreases.",
            effect_direction="negative",
            minimal_detectable_effect=0.3,
        )
        existing = ["Phase transition in coupled oscillators."]
        assert gen.is_novel(h, existing)

    def test_duplicate_detection(self):
        gen = HypothesisGenerator()
        h = Hypothesis(
            statement="If coupling increases then coherence decreases.",
            effect_direction="negative",
            minimal_detectable_effect=0.3,
        )
        existing = ["If coupling increases then coherence decreases, due to attractor crowding."]
        assert not gen.is_novel(h, existing)
