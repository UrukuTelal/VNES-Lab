"""Pre-Registration — submits spec.yaml to Pillar Council and manages lock."""

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone

from rlaaer.config import (
    REPO_ROOT,
    COUNCIL,
    SPEC_FILENAME,
    STATUS_FLOW,
)


class PreRegistrationError(Exception):
    """Raised when pre-registration fails."""


class PreRegistration:
    """Handles the draft → registered transition via Pillar Council approval."""

    def __init__(self, experiments_dir: str | None = None):
        self.experiments_dir = experiments_dir or os.path.join(REPO_ROOT, "experiments")

    def _experiment_path(self, experiment_id: str) -> str:
        return os.path.join(self.experiments_dir, f"{int(experiment_id):03d}_{{}}")

    def submit(self, spec: dict) -> dict:
        """Wrap spec for Council submission. Returns submission record."""
        experiment = spec.get("experiment", {})
        eid = experiment.get("id", "unknown")

        submission = {
            "experiment_id": eid,
            "title": experiment.get("title", ""),
            "hypothesis": experiment.get("hypothesis", ""),
            "parameters": spec.get("parameters", {}),
            "statistics": spec.get("statistics", {}),
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "approval_threshold": COUNCIL["pillar_required_approvals"],
            "total_pillars": COUNCIL["pillar_total"],
            "status": "pending",
        }

        return submission

    def register(self, spec: dict, votes: int, total: int) -> str:
        """Lock spec.yaml after approval. Returns experiment directory path."""
        threshold = COUNCIL["pillar_required_approvals"]
        if votes < threshold:
            raise PreRegistrationError(
                f"Not enough votes ({votes}/{total} < {threshold})"
            )

        experiment = spec.get("experiment", {})
        eid = experiment.get("id", "unknown")
        exp_dir = os.path.join(self.experiments_dir, f"{int(eid):03d}_{experiment.get('title', 'untitled').replace(' ', '_')}")

        os.makedirs(exp_dir, exist_ok=True)

        # Write locked spec
        spec_path = os.path.join(exp_dir, SPEC_FILENAME)
        self._write_locked(spec, spec_path)

        # Write pre-registration with provenance
        from rlaaer.provenance import git_commit, git_branch, git_dirty, spec_hash
        spec_h = spec_hash(spec)
        prereg_path = os.path.join(exp_dir, ".pre_registration.json")
        prereg = {
            "experiment_id": eid,
            "hash": spec_h,
            "provenance": {
                "git_commit": git_commit(),
                "git_branch": git_branch(),
                "git_dirty": git_dirty(),
                "locked_at": datetime.now(timezone.utc).isoformat(),
            },
            "votes": votes,
            "total": total,
            "locked_at": datetime.now(timezone.utc).isoformat(),
            "status": "registered",
        }
        with open(prereg_path, "w", encoding="utf-8") as f:
            json.dump(prereg, f, indent=2)

        return exp_dir

    def verify_lock(self, spec_path: str) -> bool:
        """Verify spec.yaml hasn't changed since pre-registration."""
        import yaml
        prereg_path = os.path.join(os.path.dirname(spec_path), ".pre_registration.json")

        if not os.path.exists(prereg_path):
            return False  # not pre-registered

        with open(prereg_path, "r", encoding="utf-8") as f:
            prereg = json.load(f)

        with open(spec_path, "r", encoding="utf-8") as f:
            spec = yaml.safe_load(f)

        return self._hash_spec(spec) == prereg["hash"]

    def _write_locked(self, spec: dict, path: str):
        """Write spec with locked comment."""
        import yaml
        comment = "# LOCKED — pre-registered, do not modify\n"
        yaml_str = yaml.dump(spec, default_flow_style=False, sort_keys=False)
        with open(path, "w", encoding="utf-8") as f:
            f.write(comment + yaml_str)

    def _hash_spec(self, spec: dict) -> str:
        """Deterministic hash of spec for integrity checking."""
        import yaml
        canonical = yaml.dump(spec, default_flow_style=False, sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
