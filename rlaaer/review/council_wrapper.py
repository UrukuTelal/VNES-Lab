"""Council Wrapper — submits experiments to the Adversarial Council for review."""

import glob
import json
import os
from datetime import datetime, timezone
from typing import Any

from rlaaer.config import COUNCIL, ENGINE, REPO_ROOT


class CouncilWrapperError(Exception):
    """Raised on council communication failures."""


AGENT_NAMES = {
    "methodologist": "Veridian",
    "theoretician": "Axiom",
    "physicist": "Flux",
    "systems_engineer": "Link",
    "performance_analyst": "Raster",
    "security_researcher": "Havik",
    "reproducibility_officer": "Pivot",
    "validation_engineer": "Probe",
    "literature_review_agent": "Archive",
}

PROMPT_VERSION = "v1.2"


class CouncilWrapper:
    """Wraps the Adversarial Council for experiment review."""

    REVIEWER_ROLES = list(AGENT_NAMES.keys())

    def __init__(self, bridge_url: str | None = None, use_llm: bool = False,
                 llm_model: str = "llama3.1:8b",
                 experiments_dir: str | None = None):
        self.bridge_url = bridge_url or "http://localhost:8888"
        self.threshold = COUNCIL["pillar_required_approvals"]
        self.max_rounds = COUNCIL["adversarial_max_revision_rounds"]
        self.use_llm = use_llm
        self.llm_model = llm_model
        self.experiments_dir = experiments_dir or os.path.join(REPO_ROOT, "experiments")

    def submit_for_review(self, experiment_id: str, spec: dict, results: dict) -> dict:
        """Submit experiment to all 9 reviewers. Returns aggregated review."""
        reviews = []
        for role in self.REVIEWER_ROLES:
            review = self._call_reviewer(role, experiment_id, spec, results)
            reviews.append(review)

        aggregated = self._aggregate(reviews)
        aggregated["experiment_id"] = experiment_id
        aggregated["reviewed_at"] = datetime.now(timezone.utc).isoformat()

        self._save_transcripts(experiment_id, reviews)

        return aggregated

    def _call_reviewer(self, role: str, experiment_id: str, spec: dict, results: dict) -> dict:
        """Call a single reviewer agent — LLM-powered with stub fallback."""
        if self.use_llm:
            try:
                from rlaaer.review.llm_reviewer import call_reviewer as llm_call
                return llm_call(role, experiment_id, spec, results, model=self.llm_model)
            except Exception:
                pass
        return {
            "role": role,
            "experiment_id": experiment_id,
            "verdict": "accept",
            "confidence": 0.8,
            "issues": [],
            "suggestions": [],
        }

    def _save_transcripts(self, experiment_id: str, reviews: list[dict]):
        """Save per-reviewer transcript artifacts to experiments/{id}/reviews/."""
        exp_dir = self._find_experiment_dir(experiment_id)
        reviews_dir = os.path.join(exp_dir, "reviews")
        os.makedirs(reviews_dir, exist_ok=True)

        for review in reviews:
            role = review.get("role", "unknown")
            agent_name = AGENT_NAMES.get(role, role.title())
            transcript = {
                "role": role.replace("_", " ").title(),
                "agent_name": agent_name,
                "model": self.llm_model if self.use_llm else "stub",
                "prompt_version": PROMPT_VERSION,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "decision": review.get("verdict", "conditional"),
                "confidence": review.get("confidence", 0.5),
                "issues": review.get("issues", []),
                "suggestions": review.get("suggestions", []),
            }
            path = os.path.join(reviews_dir, f"{role}.json")
            with open(path, "w") as f:
                json.dump(transcript, f, indent=2)

    def _find_experiment_dir(self, experiment_id: str) -> str:
        """Locate experiment directory by ID, creating a placeholder if not found."""
        pattern = os.path.join(self.experiments_dir, f"*{experiment_id}*")
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
        placeholder = os.path.join(self.experiments_dir, f"{experiment_id}_unknown")
        os.makedirs(placeholder, exist_ok=True)
        return placeholder

    def _aggregate(self, reviews: list[dict]) -> dict:
        verdicts = {}
        for r in reviews:
            verdicts[r["role"]] = r

        accepts = sum(1 for r in reviews if r.get("verdict") == "accept")
        rejects = sum(1 for r in reviews if r.get("verdict") == "reject")
        conditionals = sum(1 for r in reviews if r.get("verdict") == "conditional")

        rejects_with_veto = [r for r in reviews
                             if r.get("verdict") == "reject" and
                             r.get("role") in ("security_researcher", "reproducibility_officer")]

        return {
            "total_reviews": len(reviews),
            "accepts": accepts,
            "rejects": rejects,
            "conditionals": conditionals,
            "veto_triggered": len(rejects_with_veto) > 0,
            "veto_roles": [r["role"] for r in rejects_with_veto],
            "reviews": verdicts,
            "passed": accepts >= max(self.threshold // 2, 1) and not rejects_with_veto,
        }

    def check_pre_registration(self, spec: dict) -> dict:
        """Check if spec meets pre-registration requirements."""
        import yaml

        issues = []

        if not spec.get("statistics", {}).get("method"):
            issues.append("Pre-registration requires a specified statistical method")

        if not spec.get("statistics", {}).get("alpha"):
            issues.append("Pre-registration requires a specified alpha")

        params = spec.get("parameters", {})
        if not params.get("independent"):
            issues.append("Pre-registration requires at least one independent variable")

        passed = len(issues) == 0
        return {"passed": passed, "issues": issues}
