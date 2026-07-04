"""Tests for the Domain Scraper."""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from rlaaer.data.scraper import Scraper, ScraperError


class TestScraper:
    @pytest.fixture
    def scraper(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            s = Scraper()
            s.cache_dir = os.path.join(tmpdir, "cache")
            s.registry_path = os.path.join(tmpdir, "sourced_datasets.json")
            s._registry = {"datasets": []}
            os.makedirs(s.cache_dir, exist_ok=True)
            yield s

    def test_unknown_source(self, scraper):
        with pytest.raises(ScraperError, match="Unknown data source"):
            scraper.fetch("nonexistent", "test")

    def test_cache_hit(self, scraper):
        source = "census"
        query = "test_query"
        cached = {"source": source, "data": {"key": "value"}, "hash": "abc123"}
        import hashlib
        qh = hashlib.md5(query.encode()).hexdigest()[:16]
        cache_path = os.path.join(scraper.cache_dir, f"{source}_{qh}.json")
        import json
        with open(cache_path, "w") as f:
            json.dump(cached, f)

        result = scraper.fetch(source, query, use_cache=True)
        assert result["data"]["key"] == "value"
        assert result["hash"] == "abc123"

    def test_cache_miss_fetches_api(self, scraper):
        source = "census"
        query = "test"

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"population": 1000}
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            result = scraper.fetch(source, query, use_cache=False)
            assert result["source"] == source
            assert result["data"]["population"] == 1000
            assert "hash" in result
            assert "fetched_at" in result

    def test_api_error_returns_error_dict(self, scraper):
        source = "census"
        query = "test"

        with patch("requests.get") as mock_get:
            import requests
            mock_get.side_effect = requests.RequestException("Connection error")

            result = scraper.fetch(source, query, use_cache=False)
            assert result["success"] is False
            assert "error" in result

    def test_tier_3_no_api_call(self, scraper):
        source = "web"
        query = "test"
        result = scraper.fetch(source, query)
        assert result["tier"] == 3
        assert result["data"]["note"] == "Tier-3 exploratory"

    def test_registry_updated_on_fetch(self, scraper):
        source = "census"
        query = "test"

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = {"data": 1}
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            scraper.fetch(source, query, use_cache=False)
            assert len(scraper._registry["datasets"]) == 1
            assert scraper._registry["datasets"][0]["source"] == source

    def test_api_key_from_env(self, scraper):
        from rlaaer.config import DATA_SOURCES
        config = DATA_SOURCES["nasa"]
        assert config["api_key_env"] == "NASA_API_KEY"
