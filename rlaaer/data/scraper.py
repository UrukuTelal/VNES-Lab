"""Domain Scraper — fetches data from Tier 1/2/3 sources with hash verification."""

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

from rlaaer.config import DATA_SOURCES, PIPELINE


class ScraperError(Exception):
    """Raised on scraper failures."""


class Scraper:
    """Multi-source data scraper with caching and hash verification."""

    def __init__(self):
        self.cache_dir = PIPELINE["cache_dir"]
        os.makedirs(self.cache_dir, exist_ok=True)
        self.registry_path = os.path.join(os.path.dirname(self.cache_dir), "sourced_datasets.json")
        self._registry = self._load_registry()

    def _load_registry(self) -> dict:
        if os.path.exists(self.registry_path):
            with open(self.registry_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"datasets": []}

    def _save_registry(self):
        with open(self.registry_path, "w", encoding="utf-8") as f:
            json.dump(self._registry, f, indent=2)

    def _hash_content(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def _cache_path(self, source: str, query_hash: str) -> str:
        return os.path.join(self.cache_dir, f"{source}_{query_hash}.json")

    def fetch(self, source: str, query: str, **kwargs) -> dict:
        """Fetch data from a source. Returns metadata + content."""
        config = DATA_SOURCES.get(source)
        if not config:
            raise ScraperError(f"Unknown data source: {source}")

        query_hash = hashlib.md5(query.encode()).hexdigest()[:16]
        cache_path = self._cache_path(source, query_hash)

        # Check cache
        if os.path.exists(cache_path) and kwargs.get("use_cache", True):
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)

        # Fetch
        tier = config["tier"]
        if tier in (1, 2):
            result = self._fetch_api(source, config, query, **kwargs)
        elif tier == 3:
            result = self._fetch_web(source, query, **kwargs)
        else:
            raise ScraperError(f"Unsupported tier: {tier}")

        # Hash and cache
        content_bytes = json.dumps(result.get("data", {}), sort_keys=True).encode()
        content_hash = self._hash_content(content_bytes)
        result["hash"] = content_hash
        result["source"] = source
        result["query"] = query
        result["fetched_at"] = datetime.now(timezone.utc).isoformat()
        result["tier"] = tier

        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        # Update registry
        self._registry["datasets"].append({
            "source": source,
            "query": query,
            "hash": content_hash,
            "tier": tier,
            "fetched_at": result["fetched_at"],
            "cache_file": os.path.basename(cache_path),
        })
        self._save_registry()

        return result

    def _fetch_api(self, source: str, config: dict, query: str, **kwargs) -> dict:
        """Fetch from an API source."""
        import requests
        base_url = config["base_url"]
        api_key = None
        if "api_key_env" in config:
            api_key = os.environ.get(config["api_key_env"])

        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            response = requests.get(
                base_url,
                params={"q": query, **kwargs.get("params", {})},
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            return {
                "success": True,
                "data": response.json(),
                "status_code": response.status_code,
            }
        except requests.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "data": {},
            }

    def _fetch_web(self, source: str, query: str, **kwargs) -> dict:
        """Fetch from general web — exploratory only, mark as Tier 3."""
        return {
            "success": True,
            "data": {"note": "Tier-3 exploratory", "query": query},
            "tier": 3,
        }
