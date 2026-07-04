"""LLM Reviewer — replaces the stub _call_reviewer with real Ollama agent calls.

Each of the 9 review roles gets a role-specific system prompt based on
the review checklists in AGENT_ROLES.md. Falls back to stub if Ollama
is unreachable or returns unparseable output.
"""

import json
import math
import re
from typing import Any

from rlaaer.config import ENGINE

# ── Role-Specific System Prompts ──────────────────────────

ROLE_PROMPTS = {
    "methodologist": """You are the Methodologist, auditing study design, confounding variables, and reproducibility.

Review checklist:
- Hypothesis is falsifiable
- Independent variables are truly independent
- Controlled variables are adequately controlled
- No obvious confounds between conditions
- Randomization is appropriate (seed handling)
- Reproducibility package is complete

Respond in JSON only: {"verdict":"accept|reject|conditional","confidence":0.0-1.0,"issues":[],"suggestions":[]}""",

    "theoretician": """You are the Theoretician, evaluating mathematical correctness and consistency with known theory.

Review checklist:
- Parameter ranges are mathematically valid (no domain errors)
- Metric formulas are correctly specified
- Predicted behavior is consistent with known theory
- Numerical precision is adequate for the expected range
- Edge cases are handled (division by zero, log of zero, etc.)

Respond in JSON only: {"verdict":"accept|reject|conditional","confidence":0.0-1.0,"issues":[],"suggestions":[]}""",

    "physicist": """You are the Physicist, reviewing physics-domain correctness.

Review checklist:
- Any physical model used is appropriate for the domain
- Energy/magnitude bounds are respected
- Coupling between variables is physically plausible
- Damping/convergence behavior is realistic
- Results are checked against conservation laws if applicable

Respond in JSON only: {"verdict":"accept|reject|conditional","confidence":0.0-1.0,"issues":[],"suggestions":[]}""",

    "systems_engineer": """You are the Systems Engineer, reviewing API contracts and resource management.

Review checklist:
- API calls match engine endpoint specifications
- Cross-language data formats are correct
- Resource cleanup is ensured (memory, file handles, network)
- Timeout and retry logic is adequate
- Error responses are handled gracefully

Respond in JSON only: {"verdict":"accept|reject|conditional","confidence":0.0-1.0,"issues":[],"suggestions":[]}""",

    "performance_analyst": """You are the Performance Analyst, evaluating throughput and scaling.

Review checklist:
- Experiment completes within stated max_duration_minutes
- Number of trials is feasible given system throughput
- Checkpoint interval is appropriate for recovery
- Engine startup/shutdown overhead is accounted for
- No O(N^2) or worse scaling in trial loops

Respond in JSON only: {"verdict":"accept|reject|conditional","confidence":0.0-1.0,"issues":[],"suggestions":[]}""",

    "security_researcher": """You are the Security Researcher, checking boundary conditions and injection vectors.

Review checklist:
- All external data is sanitized before entering simulation
- Parameter ranges are bounded (no overflows)
- Web-sourced data (Tier 3) is flagged and isolated
- Engine API is not exposed to unverified data
- No shell injection or command injection vectors in data paths

You have HARD VETO power. If you see a security issue, set verdict to "reject".

Respond in JSON only: {"verdict":"accept|reject|conditional","confidence":0.0-1.0,"issues":[],"suggestions":[]}""",

    "reproducibility_officer": """You are the Reproducibility Officer, ensuring experiments can be independently re-run.

Review checklist:
- spec.yaml is complete and self-describing
- README.md explains the experiment for a new reader
- Seeds are documented and deterministic
- All dependencies are pinned
- CI passes at the pinned commit
- A new agent could re-run this experiment without external knowledge

You have HARD VETO power. If reproducibility is impossible, set verdict to "reject".

Respond in JSON only: {"verdict":"accept|reject|conditional","confidence":0.0-1.0,"issues":[],"suggestions":[]}""",

    "validation_engineer": """You are the Validation Engineer, checking metric correctness and statistical validity.

Review checklist:
- Metric extractors match the spec.yaml definitions
- Statistical test is appropriate for the data distribution
- Sample size is adequate for the claimed effect size
- No p-hacking or post-hoc analysis selection
- Outliers are handled transparently

Respond in JSON only: {"verdict":"accept|reject|conditional","confidence":0.0-1.0,"issues":[],"suggestions":[]}""",

    "literature_review_agent": """You are the Literature Review Agent, checking for prior art and novelty.

Review checklist:
- No existing experiment tests the same hypothesis
- Citations are accurate and relevant
- The hypothesis is genuinely novel (not a replication without stating so)
- Related work section is comprehensive enough

Respond in JSON only: {"verdict":"accept|reject|conditional","confidence":0.0-1.0,"issues":[],"suggestions":[]}""",
}

DEFAULT_MODEL = "llama3.1:8b"


# ── LLM Reviewer ─────────────────────────────────────────

def _build_spec_summary(spec: dict, max_chars: int = 4000) -> str:
    """Build a concise text summary of the experiment spec."""
    exp = spec.get("experiment", {})
    lines = [
        f"Experiment: {exp.get('id', '?')} — {exp.get('title', 'Untitled')}",
        f"Hypothesis: {exp.get('hypothesis', 'N/A')}",
        f"Author: {exp.get('author', 'N/A')}",
        f"Status: {exp.get('status', 'N/A')}",
        f"Tags: {', '.join(exp.get('tags', []))}",
        f"Depends on: {', '.join(exp.get('depends_on', [])) or 'None'}",
    ]

    lines.append("\nSystems:")
    for sys_name, sys_config in spec.get("systems", {}).items():
        lines.append(f"  {sys_name}: enabled={sys_config.get('enabled', False)}")

    lines.append("\nData Sources:")
    for ds in spec.get("data_sources", []):
        lines.append(f"  {ds.get('source', '?')} (Tier {ds.get('tier', '?')}): {ds.get('rationale', '')[:100]}")

    params = spec.get("parameters", {})
    indep = params.get("independent", [])
    if indep:
        lines.append(f"\nIndependent Variables ({len(indep)}):")
        for p in indep:
            domain = p.get("domain", [])
            lines.append(f"  {p.get('name', '?')}: domain={domain}, steps={p.get('steps', '?')}")

    controlled = params.get("controlled", [])
    if controlled:
        lines.append(f"Controlled Variables ({len(controlled)}):")
        for p in controlled:
            lines.append(f"  {p.get('name', '?')}={p.get('value', '?')}")

    metrics = spec.get("metrics", {})
    lines.append("\nMetrics:")
    for cat in ("stability", "invariants", "exploratory"):
        items = metrics.get(cat, [])
        if items:
            lines.append(f"  {cat} ({len(items)}):")
            for m in items:
                lines.append(f"    {m.get('name', '?')} ({m.get('comparator', '?')}, tol={m.get('tolerance', '?')})")

    stats = spec.get("statistics", {})
    lines.append(f"\nStatistics: alpha={stats.get('alpha', '?')}, power={stats.get('power', '?')}, "
                 f"min_d={stats.get('minimum_effect_size', '?')}, method={stats.get('method', '?')}")

    exec_cfg = spec.get("execution", {})
    lines.append(f"\nExecution: {exec_cfg.get('total_trials', '?')} trials, "
                 f"{exec_cfg.get('max_duration_minutes', '?')}min max, "
                 f"checkpoint every {exec_cfg.get('checkpoint_interval_ticks', '?')} ticks")

    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n... [truncated]"
    return text


def _build_results_summary(results: dict, max_chars: int = 2000) -> str:
    """Build a concise text summary of experiment results."""
    lines = [
        f"Status: {results.get('status', 'N/A')}",
        f"Trials completed: {results.get('trials_completed', 0)}",
        f"Trials failed: {results.get('trials_failed', 0)}",
        f"Duration: {results.get('duration_seconds', 0):.1f}s",
    ]
    metrics = results.get("metrics", {})
    if metrics:
        lines.append("Metrics:")
        for k, v in list(metrics.items())[:20]:
            lines.append(f"  {k}: {v}")

    analysis = results.get("statistical_analysis", {})
    if analysis:
        lines.append(f"\nStatistical Analysis: p={analysis.get('p_value', 'N/A')}, "
                     f"d={analysis.get('effect_size', 'N/A')}")
        lines.append(f"Significant: {analysis.get('is_significant', 'N/A')}")

    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n... [truncated]"
    return text


def _parse_llm_response(text: str) -> dict | None:
    """Extract JSON from LLM response, handling markdown code fences and extra text."""
    if not text:
        return None

    # Try to extract JSON from markdown code block
    json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', text, re.DOTALL)
    if json_match:
        text = json_match.group(1)

    # Find JSON object boundaries
    brace_start = text.find('{')
    brace_end = text.rfind('}')
    if brace_start == -1 or brace_end == -1:
        return None

    json_str = text[brace_start:brace_end + 1]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def _stub_review(role: str, experiment_id: str) -> dict:
    """Fallback stub response when Ollama is unavailable."""
    return {
        "role": role,
        "experiment_id": experiment_id,
        "verdict": "conditional",
        "confidence": 0.5,
        "issues": ["LLM reviewer unavailable — defaulting to conditional accept"],
        "suggestions": ["Review manually if LLM integration is required"],
        "llm_source": "stub_fallback",
    }


def call_reviewer(role: str, experiment_id: str, spec: dict, results: dict,
                  model: str = DEFAULT_MODEL, ollama_url: str | None = None,
                  timeout_sec: int = 30) -> dict:
    """Call a single LLM reviewer agent via Ollama.

    Args:
        role: Reviewer role name (must be a key in ROLE_PROMPTS).
        experiment_id: The experiment being reviewed.
        spec: Full experiment spec dict.
        results: Experiment results dict (may be empty).
        model: Ollama model name.
        ollama_url: Ollama API base URL.
        timeout_sec: HTTP timeout per request.

    Returns:
        Review dict with verdict, confidence, issues, suggestions.
    """
    prompt = ROLE_PROMPTS.get(role)
    if not prompt:
        return {"role": role, "experiment_id": experiment_id, "verdict": "reject",
                "confidence": 1.0, "issues": [f"Unknown role: {role}"], "suggestions": []}

    ollama_url = ollama_url or ENGINE.get("llm_bridge", "http://localhost:11434")

    spec_summary = _build_spec_summary(spec)
    results_summary = _build_results_summary(results) if results else "No results available."

    user_message = (
        f"Review the following experiment and results.\n\n"
        f"=== SPEC ===\n{spec_summary}\n\n"
        f"=== RESULTS ===\n{results_summary}\n\n"
        f"Provide your verdict as JSON."
    )

    try:
        import requests
        resp = requests.post(
            f"{ollama_url}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_message},
                ],
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 1024},
            },
            timeout=timeout_sec,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data.get("message", {}).get("content", "")

        parsed = _parse_llm_response(content)
        if parsed:
            return {
                "role": role,
                "experiment_id": experiment_id,
                "verdict": parsed.get("verdict", "conditional"),
                "confidence": float(parsed.get("confidence", 0.5)),
                "issues": parsed.get("issues", []),
                "suggestions": parsed.get("suggestions", []),
                "llm_source": f"ollama:{model}",
            }

    except Exception:
        pass

    return _stub_review(role, experiment_id)
