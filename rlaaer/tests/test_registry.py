"""Tests for the Experiment Registry."""

import os
import json
import tempfile
import pytest

from rlaaer.registry import ExperimentRegistry, ExperimentRegistryError


@pytest.fixture
def registry():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)
    reg = ExperimentRegistry(db_path=db_path)
    yield reg
    reg.close()
    os.unlink(db_path)


SAMPLE_SPEC = {
    "experiment": {"id": "009", "title": "Registry Test", "hypothesis": "If X then Y.", "status": "draft", "author": "R-LAAER", "tags": ["cognition", "physics"], "created": "2026-07-03"},
    "systems": {"vnes_lab": {"enabled": True}},
    "data_sources": [{"source": "census", "tier": 1, "rationale": "pop"}],
    "parameters": {},
    "metrics": {},
    "statistics": {},
    "execution": {},
    "review": {},
    "publication": {},
}


class TestRegistry:
    def test_register_and_get(self, registry):
        registry.register(SAMPLE_SPEC, path="/tmp/009_test")
        exp = registry.get("009")
        assert exp is not None
        assert exp["id"] == "009"
        assert exp["title"] == "Registry Test"
        assert exp["status"] == "draft"

    def test_register_update(self, registry):
        registry.register(SAMPLE_SPEC)
        spec2 = SAMPLE_SPEC.copy()
        spec2["experiment"] = spec2["experiment"].copy()
        spec2["experiment"]["title"] = "Updated"
        registry.register(spec2)
        exp = registry.get("009")
        assert exp["title"] == "Updated"

    def test_get_nonexistent(self, registry):
        assert registry.get("999") is None

    def test_list_all(self, registry):
        spec_a = SAMPLE_SPEC.copy()
        spec_a["experiment"] = {"id": "001", "title": "A", "status": "draft", "author": "test", "tags": [], "created": "2026-01-01"}
        spec_b = SAMPLE_SPEC.copy()
        spec_b["experiment"] = {"id": "002", "title": "B", "status": "published", "author": "test", "tags": [], "created": "2026-02-01"}
        registry.register(spec_a)
        registry.register(spec_b)
        all_exps = registry.list_all()
        assert len(all_exps) == 2

    def test_update_status(self, registry):
        registry.register(SAMPLE_SPEC)
        registry.update_status("009", "registered", from_status="draft")
        exp = registry.get("009")
        assert exp["status"] == "registered"

    def test_lifecycle_events(self, registry):
        registry.register(SAMPLE_SPEC)
        registry.update_status("009", "registered", from_status="draft")
        registry.update_status("009", "executing", from_status="registered")
        history = registry.history("009")
        assert len(history) == 2
        assert history[0]["to_status"] == "registered"
        assert history[1]["to_status"] == "executing"

    def test_update_outcome(self, registry):
        registry.register(SAMPLE_SPEC)
        registry.update_outcome("009", outcome="published", significance=0.01, effect_size=1.5)
        exp = registry.get("009")
        assert exp["outcome"] == "published"
        assert exp["significance"] == 0.01
        assert exp["effect_size"] == 1.5

    def test_search_by_status(self, registry):
        spec_a = SAMPLE_SPEC.copy()
        spec_a["experiment"] = {"id": "001", "title": "A", "status": "draft", "author": "test", "tags": [], "created": "2026-01-01"}
        spec_b = SAMPLE_SPEC.copy()
        spec_b["experiment"] = {"id": "002", "title": "B", "status": "published", "author": "test", "tags": [], "created": "2026-02-01"}
        registry.register(spec_a)
        registry.register(spec_b)

        results = registry.search(status="draft")
        assert len(results) == 1
        assert results[0]["id"] == "001"

        results = registry.search(status="published")
        assert len(results) == 1
        assert results[0]["id"] == "002"

    def test_search_by_tag(self, registry):
        registry.register(SAMPLE_SPEC)
        results = registry.search(tag="cognition")
        assert len(results) == 1
        assert results[0]["id"] == "009"

        results = registry.search(tag="nonexistent")
        assert len(results) == 0

    def test_search_by_data_source(self, registry):
        registry.register(SAMPLE_SPEC)
        results = registry.search(data_source="census")
        assert len(results) == 1

    def test_search_by_author(self, registry):
        registry.register(SAMPLE_SPEC)
        results = registry.search(author="R-LAAER")
        assert len(results) == 1

    def test_search_bad_key(self, registry):
        with pytest.raises(ExperimentRegistryError, match="Unknown search key"):
            registry.search(nonexistent="foo")

    def test_stats(self, registry):
        spec_a = SAMPLE_SPEC.copy()
        spec_a["experiment"] = {"id": "001", "title": "A", "status": "draft", "author": "test", "tags": [], "created": "2026-01-01"}
        spec_b = SAMPLE_SPEC.copy()
        spec_b["experiment"] = {"id": "002", "title": "B", "status": "published", "author": "test", "tags": [], "created": "2026-02-01"}
        registry.register(spec_a)
        registry.register(spec_b)
        s = registry.stats()
        assert s["total"] == 2
        assert s["by_status"]["draft"] == 1
        assert s["by_status"]["published"] == 1
