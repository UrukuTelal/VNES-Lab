"""Citation Manager — extracts, validates, and formats citations."""

import json
import os
import re
from typing import Any

from rlaaer.config import REPO_ROOT


class CitationManagerError(Exception):
    """Raised on citation management failures."""


class CitationManager:
    """Manages citations from spec.yaml data sources and inline references."""

    STYLES = {"ieee", "apa", "mla", "chicago"}

    def __init__(self):
        self.cache_path = os.path.join(REPO_ROOT, "rlaaer", "data", "citation_cache.json")
        self._cache = self._load_cache()

    def _load_cache(self) -> dict:
        if os.path.exists(self.cache_path):
            with open(self.cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"citations": []}

    def _save_cache(self):
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, indent=2)

    def extract_citations(self, spec: dict) -> list[dict]:
        """Extract citations from data sources and inline references."""
        citations = []

        for ds in spec.get("data_sources", []):
            source = ds.get("source", "unknown")
            rationale = ds.get("rationale", "")
            query = ds.get("query", "")

            citation = {
                "source": source,
                "type": "dataset",
                "title": f"{source}: {query[:80]}" if query else source,
                "rationale": rationale,
                "url": ds.get("endpoint", ""),
                "year": ds.get("year"),
            }
            citations.append(citation)

        # Inline citations from hypothesis
        hypothesis = spec.get("experiment", {}).get("hypothesis", "")
        for match in re.finditer(r'\[cite:\s*([^\]]+)\]', hypothesis):
            ref = match.group(1).strip()
            citation = {
                "source": ref,
                "type": "inline_reference",
                "title": ref,
            }
            citations.append(citation)

        return citations

    def format_citations(self, citations: list[dict], style: str = "ieee") -> list[str]:
        """Format citations in the requested style."""
        if style not in self.STYLES:
            raise CitationManagerError(f"Unknown citation style: {style}. Use one of {self.STYLES}")

        if style == "ieee":
            return self._format_ieee(citations)
        elif style == "apa":
            return self._format_apa(citations)
        else:
            return self._format_generic(citations, style)

    def _format_ieee(self, citations: list[dict]) -> list[str]:
        formatted = []
        for i, c in enumerate(citations, 1):
            source = c.get("source", "Unknown")
            title = c.get("title", "")
            year = c.get("year", "n.d.")
            url = c.get("url", "")
            parts = [f"[{i}] {source}"]
            if title:
                parts.append(f'"{title}"')
            if url:
                parts.append(url)
            parts.append(f"({year})")
            formatted.append(". ".join(parts))
        return formatted

    def _format_apa(self, citations: list[dict]) -> list[str]:
        formatted = []
        for c in citations:
            source = c.get("source", "Unknown")
            year = c.get("year", "n.d.")
            title = c.get("title", "")
            url = c.get("url", "")
            parts = [f"{source} ({year})."]
            if title:
                parts.append(f"*{title}*.")
            if url:
                parts.append(f"Retrieved from {url}")
            formatted.append(" ".join(parts))
        return formatted

    def _format_generic(self, citations: list[dict], style: str) -> list[str]:
        return [f"[{c.get('source', '?')}] {c.get('title', '')}" for c in citations]

    def bibliography_section(self, citations: list[dict], style: str = "ieee") -> str:
        """Generate a formatted bibliography section."""
        formatted = self.format_citations(citations, style)
        lines = ["## References\n"]
        lines.extend(f"- {c}" for c in formatted)
        return "\n".join(lines)
