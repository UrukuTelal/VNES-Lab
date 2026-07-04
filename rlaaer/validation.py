"""spec.yaml validation — entry-point-agnostic schema checker."""

import os
import re

REQUIRED_TOP_LEVEL = {"experiment", "systems", "parameters", "metrics", "statistics", "execution", "review", "publication"}

REQUIRED_EXPERIMENT = {"id", "title", "hypothesis", "status", "author", "created", "tags"}
OPTIONAL_EXPERIMENT = {"depends_on"}
REQUIRED_SYSTEMS = {"vnes_lab"}
OPTIONAL_SYSTEMS = {"engine", "api"}
REQUIRED_DATA_SOURCE = {"source", "tier", "rationale"}
REQUIRED_INDEPENDENT = {"name", "domain", "steps", "target", "source", "rationale"}
REQUIRED_CONTROLLED = {"name", "value"}
REQUIRED_STABILITY_METRIC = {"name", "comparator", "tolerance", "extractor"}
REQUIRED_INVARIANT_METRIC = {"name", "comparator", "threshold", "extractor"}
REQUIRED_STATISTICS = {"alpha", "power", "minimum_effect_size", "method"}
REQUIRED_EXECUTION = {"trials_per_condition", "total_trials", "max_duration_minutes"}
REQUIRED_REVIEW = {"pre_registration_required", "approval_threshold", "max_revision_rounds"}
REQUIRED_PUBLICATION = {"format", "license", "authors"}

VALID_COMPARATORS = {"approx", "eq", "ne", "lt", "gt", "lte", "gte"}
VALID_STATUSES = {"draft", "registered", "executing", "review", "published", "rejected"}
VALID_TIERS = {1, 2, 3}
VALID_FORMATS = {"markdown", "latex", "both"}


class SpecValidationError(Exception):
    """Raised when a spec.yaml fails validation."""


def validate(spec: dict, filepath: str | None = None) -> list[str]:
    """Validate a parsed spec.yaml dict. Returns list of error strings (empty = valid)."""
    errors = []

    # ── top-level keys ──
    missing_top = REQUIRED_TOP_LEVEL - set(spec.keys())
    if missing_top:
        errors.append(f"Missing top-level sections: {', '.join(sorted(missing_top))}")
        return errors  # can't continue without these

    # ── experiment ──
    exp = spec.get("experiment", {})
    missing_exp = REQUIRED_EXPERIMENT - set(exp.keys())
    if missing_exp:
        errors.append(f"experiment: missing {', '.join(sorted(missing_exp))}")

    # Validate depends_on if present
    depends_on = exp.get("depends_on", [])
    if not isinstance(depends_on, list):
        errors.append("experiment.depends_on: must be a list of experiment IDs")
    elif depends_on:
        for dep in depends_on:
            if not isinstance(dep, str) or not dep.strip():
                errors.append(f"experiment.depends_on: invalid entry '{dep}'")

    if exp.get("status", "") not in VALID_STATUSES:
        errors.append(f"experiment.status: must be one of {VALID_STATUSES}, got '{exp.get('status')}'")

    # Hypothesis must end with a period and be at least 10 chars
    hyp = exp.get("hypothesis", "")
    if not hyp.endswith("."):
        errors.append("experiment.hypothesis: must end with a period")
    if len(hyp.strip()) < 10:
        errors.append("experiment.hypothesis: too short (min 10 chars)")

    # ── systems ──
    sys = spec.get("systems", {})
    missing_sys = REQUIRED_SYSTEMS - set(sys.keys())
    if missing_sys:
        errors.append(f"systems: missing {', '.join(sorted(missing_sys))}")

    for sys_name, sys_config in sys.items():
        if not isinstance(sys_config, dict):
            errors.append(f"systems.{sys_name}: must be a dict")
        elif "enabled" not in sys_config:
            errors.append(f"systems.{sys_name}: must have 'enabled' field")

    # ── data_sources ──
    ds_list = spec.get("data_sources", [])
    if not isinstance(ds_list, list):
        errors.append("data_sources: must be a list")
    else:
        for i, ds in enumerate(ds_list):
            missing_ds = REQUIRED_DATA_SOURCE - set(ds.keys())
            if missing_ds:
                errors.append(f"data_sources[{i}]: missing {', '.join(sorted(missing_ds))}")
            tier = ds.get("tier")
            if tier is not None and tier not in VALID_TIERS:
                errors.append(f"data_sources[{i}].tier: must be 1, 2, or 3, got {tier}")

    # ── parameters ──
    params = spec.get("parameters", {})
    indep = params.get("independent", [])
    if not isinstance(indep, list):
        errors.append("parameters.independent: must be a list")
    else:
        for i, p in enumerate(indep):
            missing_p = REQUIRED_INDEPENDENT - set(p.keys())
            if missing_p:
                errors.append(f"parameters.independent[{i}]: missing {', '.join(sorted(missing_p))}")
            dom = p.get("domain")
            if dom is not None and not (isinstance(dom, list) and len(dom) == 2):
                errors.append(f"parameters.independent[{i}].domain: must be [low, high]")

    controlled = params.get("controlled", [])
    if not isinstance(controlled, list):
        errors.append("parameters.controlled: must be a list")
    else:
        for i, p in enumerate(controlled):
            missing_c = REQUIRED_CONTROLLED - set(p.keys())
            if missing_c:
                errors.append(f"parameters.controlled[{i}]: missing {', '.join(sorted(missing_c))}")

    # ── metrics ──
    metrics = spec.get("metrics", {})
    stability = metrics.get("stability", [])
    if not isinstance(stability, list):
        errors.append("metrics.stability: must be a list")
    else:
        for i, m in enumerate(stability):
            missing_m = REQUIRED_STABILITY_METRIC - set(m.keys())
            if missing_m:
                errors.append(f"metrics.stability[{i}]: missing {', '.join(sorted(missing_m))}")
            if m.get("comparator") not in {"approx"}:
                errors.append(f"metrics.stability[{i}].comparator: must be 'approx', got '{m.get('comparator')}'")

    invariants = metrics.get("invariants", [])
    if not isinstance(invariants, list):
        errors.append("metrics.invariants: must be a list")
    else:
        for i, m in enumerate(invariants):
            missing_i = REQUIRED_INVARIANT_METRIC - set(m.keys())
            if missing_i:
                errors.append(f"metrics.invariants[{i}]: missing {', '.join(sorted(missing_i))}")
            if m.get("comparator") not in VALID_COMPARATORS - {"approx"}:
                errors.append(f"metrics.invariants[{i}].comparator: must be one of eq/ne/lt/gt/lte/gte, got '{m.get('comparator')}'")

    # ── statistics ──
    stats = spec.get("statistics", {})
    missing_stats = REQUIRED_STATISTICS - set(stats.keys())
    if missing_stats:
        errors.append(f"statistics: missing {', '.join(sorted(missing_stats))}")

    alpha = stats.get("alpha")
    if alpha is not None and not (0 < alpha < 1):
        errors.append(f"statistics.alpha: must be between 0 and 1, got {alpha}")

    power = stats.get("power")
    if power is not None and not (0 < power < 1):
        errors.append(f"statistics.power: must be between 0 and 1, got {power}")

    # ── execution ──
    ex = spec.get("execution", {})
    missing_ex = REQUIRED_EXECUTION - set(ex.keys())
    if missing_ex:
        errors.append(f"execution: missing {', '.join(sorted(missing_ex))}")

    # ── review ──
    rev = spec.get("review", {})
    missing_rev = REQUIRED_REVIEW - set(rev.keys())
    if missing_rev:
        errors.append(f"review: missing {', '.join(sorted(missing_rev))}")

    # ── publication ──
    pub = spec.get("publication", {})
    missing_pub = REQUIRED_PUBLICATION - set(pub.keys())
    if missing_pub:
        errors.append(f"publication: missing {', '.join(sorted(missing_pub))}")

    fmt = pub.get("format")
    if fmt is not None and fmt not in VALID_FORMATS:
        errors.append(f"publication.format: must be one of {VALID_FORMATS}, got '{fmt}'")

    return errors


def validate_file(filepath: str) -> list[str]:
    """Load and validate a spec.yaml file."""
    try:
        import yaml
        with open(filepath, "r", encoding="utf-8") as f:
            spec = yaml.safe_load(f)
    except FileNotFoundError:
        return [f"File not found: {filepath}"]
    except yaml.YAMLError as e:
        return [f"YAML parse error: {e}"]
    except ImportError:
        return ["PyYAML required: pip install pyyaml"]

    if not isinstance(spec, dict):
        return [f"Top-level structure must be a dict, got {type(spec).__name__}"]

    return validate(spec, filepath)
