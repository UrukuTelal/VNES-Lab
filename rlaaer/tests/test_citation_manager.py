"""Tests for the Citation Manager."""

import pytest
from rlaaer.publication.citation_manager import CitationManager, CitationManagerError


class TestCitationManager:
    @pytest.fixture
    def cm(self):
        return CitationManager()

    def test_extract_citations_from_data_sources(self, cm):
        spec = {
            "data_sources": [
                {"source": "census", "rationale": "Population prior", "query": "population by county", "endpoint": "https://api.census.gov", "year": 2020},
                {"source": "nasa", "rationale": "Solar activity baseline", "query": "solar flux", "tier": 1},
            ],
            "experiment": {"hypothesis": "If X then Y [cite: arxiv:2304.12345]."},
        }
        citations = cm.extract_citations(spec)
        assert len(citations) == 3  # 2 data sources + 1 inline
        assert any(c["source"] == "census" for c in citations)
        assert any(c["source"] == "nasa" for c in citations)
        assert any(c["source"] == "arxiv:2304.12345" for c in citations)

    def test_ieee_format(self, cm):
        citations = [
            {"source": "Census", "title": "ACS 2020", "year": 2020, "url": "https://census.gov"},
            {"source": "NASA", "title": "OMNIWeb", "year": 2023},
        ]
        formatted = cm.format_citations(citations, "ieee")
        assert len(formatted) == 2
        assert "[1]" in formatted[0]
        assert "[2]" in formatted[1]

    def test_apa_format(self, cm):
        citations = [
            {"source": "Census Bureau", "year": 2020, "title": "ACS Survey"},
        ]
        formatted = cm.format_citations(citations, "apa")
        assert "Census Bureau" in formatted[0]
        assert "2020" in formatted[0]
        assert "ACS Survey" in formatted[0]

    def test_unknown_style(self, cm):
        with pytest.raises(CitationManagerError, match="Unknown citation style"):
            cm.format_citations([], "vancouver")

    def test_bibliography_section(self, cm):
        citations = [{"source": "Test", "title": "Test Title", "year": 2020}]
        bib = cm.bibliography_section(citations, "ieee")
        assert "## References" in bib
        assert "[1]" in bib
