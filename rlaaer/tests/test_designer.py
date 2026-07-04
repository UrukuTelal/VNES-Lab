"""Tests for the Designer spec.yaml assembler."""

import os
import tempfile
import pytest
import yaml

from rlaaer.design.designer import Designer
from rlaaer.design.hypothesis import Hypothesis


class TestDesigner:
    @pytest.fixture
    def designer(self):
        return Designer()

    def test_assemble_basic(self, designer):
        h = Hypothesis(
            statement="If coupling increases then coherence decreases, because attractor competition destabilizes consensus.",
            effect_direction="negative",
            minimal_detectable_effect=0.3,
            citations=["arxiv:2304.12345"],
        )
        spec = designer.assemble(
            hypothesis=h,
            data_sources=[{"source": "census", "tier": 1, "rationale": "Population prior"}],
            independent_params=[{"name": "coupling", "domain": [0, 2], "steps": 11, "target": "vnes_lab", "source": "census", "rationale": "test"}],
            controlled_params=[{"name": "seed", "value": 42}],
            stability_metrics=[{"name": "coherence", "comparator": "approx", "tolerance": 0.15, "extractor": "extract_coherence"}],
            invariant_metrics=[{"name": "count", "comparator": "eq", "threshold": 100, "extractor": "extract_count"}],
            exploratory_metrics=[{"name": "peak_freq", "extractor": "extract_peak"}],
            existing_ids={"001", "002"},
        )

        assert spec["experiment"]["title"] == "Experiment Title"
        assert spec["experiment"]["hypothesis"] == h.statement
        assert spec["experiment"]["status"] == "draft"
        assert spec["data_sources"][0]["source"] == "census"
        assert spec["parameters"]["independent"][0]["name"] == "coupling"
        assert spec["parameters"]["controlled"][0]["name"] == "seed"
        assert spec["metrics"]["stability"][0]["name"] == "coherence"
        assert spec["metrics"]["invariants"][0]["name"] == "count"

    def test_assemble_with_systems_override(self, designer):
        h = Hypothesis(
            statement="If noise increases then entropy increases, because stochastic forcing broadens the distribution.",
            effect_direction="positive",
            minimal_detectable_effect=0.3,
        )
        spec = designer.assemble(
            hypothesis=h,
            data_sources=[],
            independent_params=[],
            controlled_params=[],
            stability_metrics=[],
            invariant_metrics=[],
            systems_config={
                "vnes_lab": {"overrides": {"n_pillars": 32}},
                "engine": {"enabled": True},
            },
        )
        assert spec["systems"]["vnes_lab"]["enabled"] is True
        assert spec["systems"]["engine"]["enabled"] is True
        assert spec["systems"]["engine"]["headless"] is True  # default from template

    def test_write(self, designer):
        h = Hypothesis(
            statement="If X then Y, because Z.",
            effect_direction="positive",
            minimal_detectable_effect=0.3,
        )
        spec = designer.assemble(h, [], [], [], [], [])
        with tempfile.TemporaryDirectory() as tmpdir:
            path = designer.write(spec, tmpdir)
            assert os.path.exists(path)
            with open(path) as f:
                loaded = yaml.safe_load(f)
            assert loaded["experiment"]["hypothesis"] == "If X then Y, because Z."

    def test_next_id(self, designer):
        assert designer._next_id({"001", "002"}) == "003"
        assert designer._next_id(set()) == "001"
        assert designer._next_id({"005", "010"}) == "011"
