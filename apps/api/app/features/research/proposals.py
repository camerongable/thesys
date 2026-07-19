"""Proposal payload shaping for agentic research memo review."""

from dataclasses import dataclass
from typing import Any

from app.schemas.research import AgenticResearchMemoDraft


@dataclass(frozen=True)
class ResearchMemoProposalPayloads:
    memory_update: dict[str, Any]
    validation_plan: dict[str, Any]
    decision: dict[str, Any]
    memory_update_input: dict[str, Any]
    validation_plan_input: dict[str, Any]
    decision_input: dict[str, Any]


def research_memo_proposal_payloads(
    memo: AgenticResearchMemoDraft,
    *,
    research_sprint_id: object,
    artifact_version_id: object,
) -> ResearchMemoProposalPayloads:
    sprint_id = str(research_sprint_id)
    version_id = str(artifact_version_id)
    return ResearchMemoProposalPayloads(
        memory_update={
            "summary": "Research memo proposes assumption, risk, and validation priority updates.",
            "research_sprint_id": sprint_id,
            "artifact_version_id": version_id,
            "assumptions": [
                draft.model_dump(mode="json") for draft in memo.riskiest_assumptions
            ],
            "risks": [draft.model_dump(mode="json") for draft in memo.key_risks],
            "recommended_validation_actions": memo.recommended_validation_actions,
            "decision_recommendation": memo.decision_recommendation,
        },
        validation_plan={
            "summary": "Research memo proposes validation actions for the riskiest assumptions.",
            "research_sprint_id": sprint_id,
            "artifact_version_id": version_id,
            "actions": memo.recommended_validation_actions,
        },
        decision={
            "summary": "Research memo proposes a decision recommendation for review.",
            "research_sprint_id": sprint_id,
            "artifact_version_id": version_id,
            "decision_recommendation": memo.decision_recommendation,
        },
        memory_update_input={"artifact_version_id": version_id},
        validation_plan_input={"action_count": len(memo.recommended_validation_actions)},
        decision_input={"artifact_version_id": version_id},
    )
