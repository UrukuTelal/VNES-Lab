"""Hypothesis Generator — validates and proposes falsifiable hypotheses."""

import re
from dataclasses import dataclass, field


@dataclass
class Hypothesis:
    statement: str
    effect_direction: str          # "positive" | "negative" | "nonlinear" | "null"
    minimal_detectable_effect: float
    citations: list[str] = field(default_factory=list)
    grounding_source: str = ""     # Tier-1 data source or literature reference


class HypothesisGenerator:
    """Validates and generates hypotheses against existing registry."""

    MIN_LENGTH = 20
    MAX_LENGTH = 500

    def __init__(self, existing_ids: set[str] | None = None):
        self.existing_ids = existing_ids or set()

    def validate(self, h: Hypothesis) -> list[str]:
        """Return list of validation errors (empty = valid)."""
        errors = []

        if not h.statement.endswith("."):
            errors.append("Hypothesis must end with a period")
        if len(h.statement) < self.MIN_LENGTH:
            errors.append(f"Hypothesis too short ({len(h.statement)} < {self.MIN_LENGTH})")
        if len(h.statement) > self.MAX_LENGTH:
            errors.append(f"Hypothesis too long ({len(h.statement)} > {self.MAX_LENGTH})")

        valid_directions = {"positive", "negative", "nonlinear", "null"}
        if h.effect_direction not in valid_directions:
            errors.append(f"effect_direction must be one of {valid_directions}")

        if h.minimal_detectable_effect <= 0:
            errors.append("minimal_detectable_effect must be > 0")

        if not isinstance(h.citations, list):
            errors.append("citations must be a list")
        else:
            for c in h.citations:
                if not c.startswith("arxiv:") and not c.startswith("doi:"):
                    errors.append(f"Citation '{c}' must start with 'arxiv:' or 'doi:'")

        # Falsifiability heuristic: must contain a measurable relationship
        has_if = "if" in h.statement.lower()
        has_then = "then" in h.statement.lower()
        if not (has_if and has_then):
            errors.append("Hypothesis must contain 'if...then...' structure for falsifiability")

        # Must contain a quantifiable term
        quant_pattern = re.compile(
            r'\b(increase|decrease|greater|less|higher|lower|correlate|proportional|'
            r'exponent|linear|logarithmic|threshold|bound|limit)\b',
            re.IGNORECASE
        )
        if not quant_pattern.search(h.statement):
            errors.append("Hypothesis must contain a quantifiable relationship term")

        return errors

    def is_novel(self, h: Hypothesis, existing_hypotheses: list[str]) -> bool:
        """Check if hypothesis is sufficiently different from existing ones."""
        # Simple overlap check — can be improved with embeddings later
        words_h = set(h.statement.lower().split())
        for existing in existing_hypotheses:
            words_e = set(existing.lower().split())
            overlap = len(words_h & words_e) / max(len(words_h), len(words_e))
            if overlap >= 0.5:
                return False
        return True
