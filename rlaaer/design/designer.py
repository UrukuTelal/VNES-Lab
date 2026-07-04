"""Designer — assembles spec.yaml from hypothesis + data source + metric templates."""

import os
from datetime import datetime, timezone
from typing import Any

import yaml

from rlaaer.config import REPO_ROOT, SPEC_FILENAME, COUNCIL
from rlaaer.design.hypothesis import Hypothesis


class Designer:
    """Assembles a complete spec.yaml from components."""

    def __init__(self):
        self.template_path = os.path.join(REPO_ROOT, "rlaaer", "spec_template.yaml")
        self._template = self._load_template()

    def _load_template(self) -> dict:
        with open(self.template_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def assemble(
        self,
        hypothesis: Hypothesis,
        data_sources: list[dict],
        independent_params: list[dict],
        controlled_params: list[dict],
        stability_metrics: list[dict],
        invariant_metrics: list[dict],
        exploratory_metrics: list[dict] | None = None,
        systems_config: dict | None = None,
        existing_ids: set[str] | None = None,
    ) -> dict:
        """Assemble a spec.yaml from components."""
        existing_ids = existing_ids or set()
        next_id = self._next_id(existing_ids)

        spec = self._template.copy()
        spec["experiment"]["id"] = next_id
        spec["experiment"]["status"] = "draft"
        spec["experiment"]["created"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        spec["experiment"]["hypothesis"] = hypothesis.statement

        # Data sources
        spec["data_sources"] = data_sources

        # Parameters
        spec["parameters"]["independent"] = independent_params
        spec["parameters"]["controlled"] = controlled_params

        # Metrics
        metrics = {}
        if stability_metrics:
            metrics["stability"] = stability_metrics
        if invariant_metrics:
            metrics["invariants"] = invariant_metrics
        if exploratory_metrics:
            metrics["exploratory"] = exploratory_metrics
        if metrics:
            spec["metrics"] = metrics

        # Systems overrides
        if systems_config:
            for sys_name, sys_cfg in systems_config.items():
                if sys_name in spec["systems"]:
                    spec["systems"][sys_name].update(sys_cfg)

        return spec

    def write(self, spec: dict, output_dir: str) -> str:
        """Write spec.yaml to directory."""
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, SPEC_FILENAME)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(spec, f, default_flow_style=False, sort_keys=False)
        return path

    def _next_id(self, existing_ids: set[str]) -> str:
        existing_nums = {int(eid) for eid in existing_ids if eid.isdigit()}
        return f"{max(existing_nums) + 1 if existing_nums else 1:03d}"
