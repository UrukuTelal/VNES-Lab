"""Tests for the Pre-Registration submission system."""

import os
import tempfile
import pytest
import yaml

from rlaaer.design.pre_registration import PreRegistration, PreRegistrationError
from rlaaer.config import SPEC_FILENAME


class TestPreRegistration:
    @pytest.fixture
    def prereg(self):
        temp_dir = tempfile.mkdtemp()
        return PreRegistration(experiments_dir=temp_dir), temp_dir

    def test_submit_creates_record(self, prereg):
        p, _ = prereg
        spec = {
            "experiment": {"id": "001", "title": "Test", "hypothesis": "If X then Y."},
            "parameters": {"independent": [{"name": "x", "domain": [0, 1], "steps": 2}]},
            "statistics": {"alpha": 0.05, "power": 0.80, "method": "independent_t"},
        }
        submission = p.submit(spec)
        assert submission["experiment_id"] == "001"
        assert submission["status"] == "pending"
        assert "submitted_at" in submission

    def test_register_with_sufficient_votes(self, prereg):
        p, temp_dir = prereg
        spec = {
            "experiment": {"id": "001", "title": "Test"},
            "systems": {"vnes_lab": {"enabled": True}},
            "parameters": {},
            "statistics": {},
            "metrics": {},
            "execution": {},
            "review": {},
            "publication": {},
        }
        exp_dir = p.register(spec, votes=12, total=16)
        assert os.path.exists(exp_dir)
        assert os.path.exists(os.path.join(exp_dir, SPEC_FILENAME))
        assert os.path.join(temp_dir, "001_Test") == exp_dir

    def test_register_insufficient_votes(self, prereg):
        p, _ = prereg
        spec = {"experiment": {"id": "001", "title": "Test"}}
        with pytest.raises(PreRegistrationError, match="Not enough votes"):
            p.register(spec, votes=5, total=16)

    def test_register_creates_pre_registration_file(self, prereg):
        import json
        p, _ = prereg
        spec = {
            "experiment": {"id": "001", "title": "Test"},
            "systems": {"vnes_lab": {"enabled": True}},
            "parameters": {},
            "statistics": {},
            "metrics": {},
            "execution": {},
            "review": {},
            "publication": {},
        }
        exp_dir = p.register(spec, votes=14, total=16)
        prereg_path = os.path.join(exp_dir, ".pre_registration.json")
        assert os.path.exists(prereg_path)
        with open(prereg_path) as f:
            record = json.load(f)
        assert record["status"] == "registered"
        assert record["votes"] == 14
        assert record["hash"] is not None

    def test_verify_lock_passes(self, prereg):
        p, _ = prereg
        spec = {
            "experiment": {"id": "001", "title": "Test"},
            "systems": {"vnes_lab": {"enabled": True}},
            "parameters": {},
            "statistics": {},
            "metrics": {},
            "execution": {},
            "review": {},
            "publication": {},
        }
        exp_dir = p.register(spec, votes=15, total=16)
        spec_path = os.path.join(exp_dir, SPEC_FILENAME)
        assert p.verify_lock(spec_path)

    def test_verify_lock_fails_on_modification(self, prereg):
        p, _ = prereg
        spec = {
            "experiment": {"id": "001", "title": "Test"},
            "systems": {"vnes_lab": {"enabled": True}},
            "parameters": {},
            "statistics": {},
            "metrics": {},
            "execution": {},
            "review": {},
            "publication": {},
        }
        exp_dir = p.register(spec, votes=15, total=16)

        # Modify the spec
        spec_path = os.path.join(exp_dir, SPEC_FILENAME)
        with open(spec_path) as f:
            modified = yaml.safe_load(f)
        modified["experiment"]["title"] = "Modified"
        with open(spec_path, "w") as f:
            yaml.dump(modified, f)

        assert not p.verify_lock(spec_path)

    def test_no_pre_registration_file(self, prereg):
        p, temp_dir = prereg
        path = os.path.join(temp_dir, "nonexistent.yaml")
        assert not p.verify_lock(path)
