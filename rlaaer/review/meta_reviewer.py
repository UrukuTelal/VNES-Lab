"""Meta-Reviewer — aggregates all reviews and decides publish/reject/revise."""

from datetime import datetime, timezone
from typing import Any


class MetaReviewerError(Exception):
    """Raised on meta-review failures."""


class MetaReviewer:
    """Collects all reviews and makes the editorial decision."""

    def __init__(self, max_revision_rounds: int = 3):
        self.max_rounds = max_revision_rounds

    def decide(self, council_review: dict, spec: dict) -> dict:
        """Decide on an experiment. Returns publication decision."""
        review_config = spec.get("review", {})
        max_rounds = review_config.get("max_revision_rounds", self.max_rounds)

        accepts = council_review.get("accepts", 0)
        rejects = council_review.get("rejects", 0)
        total = council_review.get("total_reviews", len(council_review.get("reviews", {})))
        threshold = review_config.get("approval_threshold", 12)

        # Check for vetos
        if council_review.get("veto_triggered"):
            return self._reject(
                council_review,
                reason=f"Veto triggered: {', '.join(council_review.get('veto_roles', []))}",
            )

        # Unanimous accept — publish regardless of threshold
        if total > 0 and accepts == total:
            return self._publish(council_review)

        # Accepts meet threshold — publish
        if accepts >= threshold:
            return self._publish(council_review)

        # More rejects than accepts — reject
        if rejects > accepts:
            return self._reject(council_review, f"Rejects ({rejects}) exceed accepts ({accepts})")

        # Mixed — route to revise
        return self._revise(council_review, "Mixed reviews — revise and resubmit")

    def _publish(self, review: dict) -> dict:
        return {
            "decision": "publish",
            "review": review,
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }

    def _reject(self, review: dict, reason: str) -> dict:
        return {
            "decision": "reject",
            "reason": reason,
            "review": review,
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }

    def _revise(self, review: dict, reason: str) -> dict:
        return {
            "decision": "revise",
            "reason": reason,
            "action_items": self._extract_action_items(review),
            "review": review,
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }

    def _extract_action_items(self, review: dict) -> list[str]:
        items = []
        for role, r in review.get("reviews", {}).items():
            for issue in r.get("issues", []):
                items.append(f"[{role}] {issue}")
            for suggestion in r.get("suggestions", []):
                items.append(f"[{role}] Suggestion: {suggestion}")
        return items
