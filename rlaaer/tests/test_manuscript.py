"""Tests for the Manuscript Generator."""

import pytest
from rlaaer.publication.manuscript import ManuscriptGenerator


class TestManuscript:
    @pytest.fixture
    def gen(self):
        return ManuscriptGenerator()

    def test_generates_all_sections(self, gen):
        spec = {
            "experiment": {"id": "009", "title": "Test", "hypothesis": "If X then Y.", "tags": ["test"]},
            "publication": {"format": "markdown", "license": "CC-BY-4.0", "authors": [{"name": "Test Author"}]},
            "data_sources": [{"source": "census", "rationale": "Population prior"}],
            "parameters": {"independent": [{"name": "x", "domain": [0, 1], "steps": 2, "source": "test", "rationale": "test"}], "controlled": [{"name": "seed", "value": 42}]},
            "statistics": {"alpha": 0.05, "power": 0.80, "minimum_effect_size": 0.30, "method": "t-test"},
            "execution": {"total_trials": 100, "max_duration_minutes": 30, "checkpoint_interval_ticks": 1000},
            "metrics": {"stability": [], "invariants": []},
            "review": {},
        }
        results = {"trials_completed": 100, "trials_failed": 0, "duration_seconds": 120, "status": "completed"}
        md = gen.generate(spec, results, {}, {})

        assert "# Test" in md
        assert "**Experiment ID:** 009" in md
        assert "Test Author" in md
        assert "Abstract" in md
        assert "Introduction" in md
        assert "Methods" in md
        assert "Results" in md
        assert "Peer Review" in md
        assert "Discussion" in md
        assert "Conclusion" in md
        assert "References" in md
        assert "Appendix" in md

    def test_empty_results(self, gen):
        spec = {
            "experiment": {"id": "001", "title": "Empty", "hypothesis": "If X then Y.", "tags": []},
            "publication": {"format": "markdown", "license": "CC", "authors": []},
            "data_sources": [],
            "parameters": {},
            "statistics": {},
            "execution": {},
            "metrics": {},
            "review": {},
        }
        md = gen.generate(spec, {}, {}, {})
        assert "No results available" in md

    def test_review_summary_empty(self, gen):
        spec = {
            "experiment": {"id": "001", "title": "Test", "hypothesis": "If X then Y.", "tags": []},
            "publication": {"format": "markdown", "license": "CC", "authors": []},
            "data_sources": [],
            "parameters": {},
            "statistics": {},
            "execution": {},
            "metrics": {},
            "review": {},
        }
        md = gen.generate(spec, {}, {}, {})
        assert "Not yet reviewed" in md

    def test_license_in_title_page(self, gen):
        spec = {
            "experiment": {"id": "001", "title": "Test", "hypothesis": "If X then Y.", "tags": []},
            "publication": {"format": "markdown", "license": "MIT", "authors": [{"name": "A"}]},
            "data_sources": [],
            "parameters": {},
            "statistics": {},
            "execution": {},
            "metrics": {},
            "review": {},
        }
        md = gen.generate(spec, {}, {}, {})
        assert "MIT" in md

    def test_transcripts_in_appendix(self, gen):
        spec = {
            "experiment": {"id": "009", "title": "Transcript Test", "hypothesis": "If X then Y.", "tags": []},
            "publication": {"format": "markdown", "license": "CC", "authors": []},
            "data_sources": [],
            "parameters": {},
            "statistics": {},
            "execution": {},
            "metrics": {},
            "review": {},
        }
        transcripts = {
            "methodologist": {
                "role": "Methodologist",
                "agent_name": "Veridian",
                "model": "llama3.1:8b",
                "prompt_version": "v1.2",
                "timestamp": "2026-07-03T12:00:00",
                "decision": "accept",
                "confidence": 0.85,
                "issues": [],
                "suggestions": ["Add more trials"],
            },
            "security_researcher": {
                "role": "Security Researcher",
                "agent_name": "Havik",
                "model": "stub",
                "prompt_version": "v1.2",
                "timestamp": "2026-07-03T12:00:01",
                "decision": "conditional",
                "confidence": 0.6,
                "issues": ["No Tier 1 data used"],
                "suggestions": ["Add Census data"],
            },
        }
        md = gen.generate(spec, {}, {}, {}, transcripts)
        assert "Review Transcripts" in md
        assert "Veridian" in md
        assert "Havik" in md
        assert "llama3.1:8b" in md
        assert "0.85" in md
        assert "Add more trials" in md
        assert "No Tier 1 data used" in md
