"""Tests for the Provenance system."""

import json
import tempfile
import pytest
from rlaaer.provenance import ProvenanceTracker, spec_hash, git_commit, git_branch, git_dirty, cuda_version, compiler_version


class TestProvenanceHash:
    def test_spec_hash_deterministic(self):
        spec = {"experiment": {"id": "001", "title": "Test"}, "systems": {"vnes_lab": {"enabled": True}}}
        h1 = spec_hash(spec)
        h2 = spec_hash(spec)
        assert h1 == h2
        assert len(h1) == 64

    def test_spec_hash_changes_with_content(self):
        spec1 = {"experiment": {"id": "001"}}
        spec2 = {"experiment": {"id": "002"}}
        assert spec_hash(spec1) != spec_hash(spec2)


class TestProvenanceCapture:
    def test_capture_basic(self):
        tracker = ProvenanceTracker()
        prov = tracker.capture()
        assert "captured_at" in prov
        assert "git" in prov
        assert "platform" in prov
        assert "toolchain" in prov
        assert "engine" in prov
        assert prov["platform"]["python"].startswith("3.")

    def test_capture_with_spec(self):
        tracker = ProvenanceTracker()
        spec = {"experiment": {"id": "009", "title": "Provenance Test"}}
        prov = tracker.capture(spec)
        assert prov["spec"]["id"] == "009"
        assert prov["spec"]["hash"] == spec_hash(spec)

    def test_git_functions(self):
        commit = git_commit()
        assert isinstance(commit, str)
        assert commit == "unknown" or len(commit) == 40

        branch = git_branch()
        assert isinstance(branch, str)

        dirty = git_dirty()
        assert isinstance(dirty, bool)

    def test_toolchain_functions(self):
        cv = cuda_version()
        assert isinstance(cv, str)

        comp = compiler_version()
        assert isinstance(comp, str)

    def test_merge_dataset_hashes(self):
        tracker = ProvenanceTracker()
        prov = tracker.capture()
        hashes = [{"source": "census", "hash": "abc123"}]
        result = tracker.merge_dataset_hashes(prov, hashes)
        assert result["datasets"] == hashes

    def test_to_appendix(self):
        tracker = ProvenanceTracker()
        prov = tracker.capture()
        appendix = tracker.to_appendix(prov)
        assert "Provenance Appendix" in appendix
        assert "Git Commit" in appendix
        assert "|" in appendix  # table format
