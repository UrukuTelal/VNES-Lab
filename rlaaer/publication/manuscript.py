"""Manuscript Generator — produces structured Markdown publications."""

from datetime import datetime, timezone
from typing import Any

from rlaaer.provenance import ProvenanceTracker


class ManuscriptGenerator:
    """Generates structured Markdown manuscripts from spec + results + reviews."""

    def generate(self, spec: dict, results: dict, reviews: dict, decision: dict,
                 transcripts: dict | None = None) -> str:
        """Generate full Markdown manuscript."""
        experiment = spec.get("experiment", {})
        publication = spec.get("publication", {})

        sections = [
            self._title_page(experiment, publication),
            self._abstract(spec),
            self._introduction(spec),
            self._methods(spec),
            self._results(results),
            self._statistical_analysis(results, spec),
            self._review_summary(reviews),
            self._discussion(spec),
            self._conclusion(spec),
            self._references(spec),
            self._appendix(spec, results, transcripts),
        ]

        return "\n\n---\n\n".join(sections)

    def _title_page(self, experiment: dict, publication: dict) -> str:
        authors = [a["name"] for a in publication.get("authors", [])]
        return (
            f"# {experiment.get('title', 'Untitled')}\n\n"
            f"**Experiment ID:** {experiment.get('id', 'unknown')}\n\n"
            f"**Authors:** {', '.join(authors)}\n\n"
            f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n\n"
            f"**License:** {publication.get('license', 'CC-BY-4.0')}\n"
        )

    def _abstract(self, spec: dict) -> str:
        experiment = spec.get("experiment", {})
        hypothesis = experiment.get("hypothesis", "No hypothesis stated.")
        data_sources = spec.get("data_sources", [])
        source_names = ", ".join(d["source"] for d in data_sources if "source" in d)

        return (
            "## Abstract\n\n"
            f"**Hypothesis:** {hypothesis}\n\n"
            f"**Data Sources:** {source_names or 'None'}\n\n"
            f"**Systems:** VNES-Lab (PSV layer)"
        )

    def _introduction(self, spec: dict) -> str:
        hypothesis = spec.get("experiment", {}).get("hypothesis", "")
        tags = spec.get("experiment", {}).get("tags", [])
        ds_list = spec.get("data_sources", [])

        citations = []
        for ds in ds_list:
            if "rationale" in ds:
                citations.append(f"- {ds['source']}: {ds['rationale']}")

        return (
            "## Introduction\n\n"
            f"**Domain:** {', '.join(tags) if tags else 'General'}\n\n"
            f"**Hypothesis:** {hypothesis}\n\n"
            f"**Grounding:**\n" + "\n".join(citations) + "\n"
        )

    def _methods(self, spec: dict) -> str:
        params = spec.get("parameters", {})
        indep = params.get("independent", [])
        controlled = params.get("controlled", [])
        stats = spec.get("statistics", {})
        execution = spec.get("execution", {})

        lines = ["## Methods\n\n### Parameters\n"]
        for p in indep:
            lines.append(f"- **{p.get('name')}**: domain={p.get('domain')}, "
                         f"steps={p.get('steps')}, source={p.get('source')}")
        for p in controlled:
            lines.append(f"- **{p.get('name')}** (controlled): {p.get('value')}")

        lines.append(f"\n### Statistical Design\n")
        lines.append(f"- Alpha: {stats.get('alpha')}")
        lines.append(f"- Power: {stats.get('power')}")
        lines.append(f"- Minimum effect size: {stats.get('minimum_effect_size')}")
        lines.append(f"- Method: {stats.get('method')}")

        lines.append(f"\n### Execution\n")
        lines.append(f"- Trials: {execution.get('total_trials')}")
        lines.append(f"- Max duration: {execution.get('max_duration_minutes')} min")
        lines.append(f"- Checkpoint interval: {execution.get('checkpoint_interval_ticks')} ticks")

        return "\n".join(lines)

    def _results(self, results: dict) -> str:
        if not results:
            return "## Results\n\n*No results available.*"

        return (
            "## Results\n\n"
            f"- **Trials completed:** {results.get('trials_completed', 0)}\n"
            f"- **Trials failed:** {results.get('trials_failed', 0)}\n"
            f"- **Duration:** {results.get('duration_seconds', 0):.1f}s\n"
            f"- **Status:** {results.get('status', 'unknown')}\n"
        )

    def _statistical_analysis(self, results: dict, spec: dict) -> str:
        stats = results.get("statistical_analysis", {})
        if not stats:
            return "## Statistical Analysis\n\n*Analysis pending.*"

        return (
            "## Statistical Analysis\n\n"
            f"- **Method:** {stats.get('method')}\n"
            f"- **Effect size (Cohen's d):** {stats.get('effect_size', 'N/A')}\n"
            f"- **P-value:** {stats.get('p_value', 'N/A')}\n"
            f"- **Significant:** {stats.get('significant', 'N/A')}\n"
            f"- **Sample size adequate:** {stats.get('sample_size_adequate', 'N/A')}\n"
        )

    def _review_summary(self, reviews: dict) -> str:
        if not reviews:
            return "## Peer Review\n\n*Not yet reviewed.*"

        # If reviews dict has aggregated keys, use them; otherwise treat as transcripts
        if "total_reviews" in reviews:
            return (
                "## Peer Review\n\n"
                f"- **Total reviews:** {reviews.get('total_reviews', 0)}\n"
                f"- **Accepts:** {reviews.get('accepts', 0)}\n"
                f"- **Rejects:** {reviews.get('rejects', 0)}\n"
                f"- **Conditionals:** {reviews.get('conditionals', 0)}\n"
                f"- **Veto triggered:** {reviews.get('veto_triggered', False)}\n"
            )
        return "## Peer Review\n\n*Transcripts loaded from review artifacts.*"

    def _discussion(self, spec: dict) -> str:
        return "## Discussion\n\n*Interpretation pending.*"

    def _conclusion(self, spec: dict) -> str:
        return "## Conclusion\n\n*Summary pending.*"

    def _references(self, spec: dict) -> str:
        citations = []
        for ds in spec.get("data_sources", []):
            if "rationale" in ds:
                citations.append(f"- [{ds['source']}] {ds['rationale']}")
        return "## References\n\n" + ("\n".join(citations) if citations else "*No references.*")

    def _appendix(self, spec: dict, results: dict, transcripts: dict | None = None) -> str:
        sections = ["## Appendix\n"]

        # Provenance
        provenance = results.get("provenance", {})
        if provenance:
            sections.append(ProvenanceTracker().to_appendix(provenance))
        else:
            sections.append("### Provenance\n\n*No provenance data available.*")

        # Review transcripts
        if transcripts:
            sections.append(self._transcript_section(transcripts))

        return "\n\n".join(sections)

    def _transcript_section(self, transcripts: dict) -> str:
        lines = ["### Review Transcripts\n"]
        roles_display = {
            "methodologist": "Methodologist (Veridian)",
            "theoretician": "Theoretician (Axiom)",
            "physicist": "Physicist (Flux)",
            "systems_engineer": "Systems Engineer (Link)",
            "performance_analyst": "Performance Analyst (Raster)",
            "security_researcher": "Security Researcher (Havik)",
            "reproducibility_officer": "Reproducibility Officer (Pivot)",
            "validation_engineer": "Validation Engineer (Probe)",
            "literature_review_agent": "Literature Review Agent (Archive)",
        }
        for role, t in sorted(transcripts.items()):
            display = roles_display.get(role, role.replace("_", " ").title())
            lines.append(f"#### {display}")
            lines.append(f"- **Decision:** {t.get('decision', 'N/A')}")
            lines.append(f"- **Confidence:** {t.get('confidence', 'N/A')}")
            lines.append(f"- **Model:** {t.get('model', 'N/A')}")
            lines.append(f"- **Prompt Version:** {t.get('prompt_version', 'N/A')}")
            lines.append(f"- **Timestamp:** {t.get('timestamp', 'N/A')}")
            issues = t.get("issues", [])
            if issues:
                lines.append(f"- **Issues:**")
                for i in issues:
                    lines.append(f"  - {i}")
            suggestions = t.get("suggestions", [])
            if suggestions:
                lines.append(f"- **Suggestions:**")
                for s in suggestions:
                    lines.append(f"  - {s}")
            lines.append("")
        return "\n".join(lines)
