"""Rendering and serialization helpers for agentic research memos."""

from typing import Any

from app.schemas.evidence import EvidenceRetrievalResultRead
from app.schemas.research import (
    AgenticResearchMemoDraft,
    ResearchAssumptionDraft,
    ResearchRiskDraft,
)


def render_markdown_memo(project: Any, memo: AgenticResearchMemoDraft) -> str:
    findings = (
        "\n".join(
            f"- **{finding.subquestion}**: {finding.finding} ({finding.evidence_strength} evidence)"
            for finding in memo.findings
        )
        or "- No findings generated."
    )
    risks = (
        "\n".join(
            f"- **{risk.severity}**: {risk.text}"
            + (f" Mitigation: {risk.mitigation}" if risk.mitigation else "")
            for risk in memo.key_risks
        )
        or "- No research-derived risks generated."
    )
    assumptions = (
        "\n".join(
            f"- **{assumption.importance} / {assumption.uncertainty} uncertainty**: "
            f"{assumption.text}"
            + (f" Test: {assumption.recommended_test}" if assumption.recommended_test else "")
            for assumption in memo.riskiest_assumptions
        )
        or "- No research-derived assumptions generated."
    )
    gaps = "\n".join(f"- {gap}" for gap in memo.evidence_gaps) or "- None"
    unknowns = "\n".join(f"- {unknown}" for unknown in memo.what_we_still_do_not_know) or gaps
    actions = "\n".join(f"- {action}" for action in memo.recommended_validation_actions) or "- None"
    citations = (
        "\n".join(
            f"- {citation.title or citation.source_id}: {citation.quote or 'No quote captured.'}"
            for citation in memo.citations
        )
        or "- No cited evidence available."
    )
    unsupported = "\n".join(f"- {claim}" for claim in memo.unsupported_claims) or "- None"
    return "\n\n".join(
        [
            f"# Research Memo: {project.name}",
            f"## Executive Verdict\n{memo.executive_verdict}",
            f"## Best Wedge\n{memo.best_wedge}",
            f"## Market Landscape\n{memo.market_landscape or 'Not enough evidence yet.'}",
            f"## Customer Pain Signals\n{memo.customer_pain_signals or 'Not enough evidence yet.'}",
            f"## Competitor Landscape\n{memo.competitor_landscape or 'Not enough evidence yet.'}",
            f"## Substitute Behaviors\n{memo.substitute_behaviors or 'Not enough evidence yet.'}",
            "## Pricing / Business Model Signals\n"
            + (memo.pricing_business_model_signals or "Not enough evidence yet."),
            f"## Key Risks\n{risks}",
            f"## Riskiest Assumptions\n{assumptions}",
            f"## Evidence Summary\n{memo.evidence_summary or 'No evidence summary generated.'}",
            f"## Findings\n{findings}",
            f"## What We Still Do Not Know\n{unknowns}",
            f"## Recommended Validation Actions\n{actions}",
            f"## Decision Recommendation\n{memo.decision_recommendation}",
            "## MVP Brief Comparison\n"
            + (memo.comparison_to_mvp_brief or "No prior opportunity brief comparison generated."),
            f"## Evidence Appendix\n{citations}",
            f"## Unsupported Claims / Open Questions\n{unsupported}",
        ]
    )


def evidence_bundles(
    results: list[EvidenceRetrievalResultRead],
    *,
    text_limit: int,
) -> list[dict[str, Any]]:
    return [
        {
            "source_id": str(result.source_id),
            "chunk_id": str(result.chunk_id),
            "title": result.title,
            "url": result.url,
            "source_type": result.source_type,
            "text": result.text[:text_limit],
            "score": result.score,
            "metadata": result.metadata,
        }
        for result in results
    ]


def first_recommended_validation_action(memo: AgenticResearchMemoDraft) -> str:
    return (
        memo.recommended_validation_actions[0]
        if memo.recommended_validation_actions
        else "Run five target-customer interviews focused on the riskiest assumption."
    )


def fallback_research_assumptions(
    memo: AgenticResearchMemoDraft,
) -> list[ResearchAssumptionDraft]:
    assumption_text = (
        memo.unsupported_claims[0]
        if memo.unsupported_claims
        else "The target user has urgent enough pain to try a focused validation workflow."
    )
    return [
        ResearchAssumptionDraft(
            text=assumption_text,
            category="validation",
            importance="critical",
            uncertainty="high",
            kill_risk=True,
            confidence_score=0.3,
            recommended_test=first_recommended_validation_action(memo),
            evidence_strength="weak",
            citations=memo.citations[:2],
        )
    ]


def fallback_research_risks(memo: AgenticResearchMemoDraft) -> list[ResearchRiskDraft]:
    risk_text = (
        memo.evidence_gaps[0]
        if memo.evidence_gaps
        else "The evidence base may still be too weak to justify a build decision."
    )
    return [
        ResearchRiskDraft(
            text=risk_text,
            category="evidence",
            severity="high",
            likelihood="high",
            mitigation=first_recommended_validation_action(memo),
            citations=memo.citations[:2],
        )
    ]


def memory_update_preview(memo: AgenticResearchMemoDraft) -> dict[str, Any]:
    assumptions = memo.riskiest_assumptions or fallback_research_assumptions(memo)
    risks = memo.key_risks or fallback_research_risks(memo)
    return {
        "assumptions": [
            {
                "text": assumption.text,
                "importance": assumption.importance,
                "uncertainty": assumption.uncertainty,
                "kill_risk": assumption.kill_risk,
                "evidence_strength": assumption.evidence_strength,
            }
            for assumption in assumptions
        ],
        "risks": [
            {
                "text": risk.text,
                "severity": risk.severity,
                "likelihood": risk.likelihood,
            }
            for risk in risks
        ],
        "recommended_validation_actions": memo.recommended_validation_actions,
    }
