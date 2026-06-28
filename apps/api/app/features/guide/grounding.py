"""Grounded answer DTO shaping for Ask Thesys."""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.features.guide import routing
from app.schemas.guide import GuideChatResponseRead, GuideConfidenceLevel, GuideContextRead


class GroundedGuideAnswerDraft(BaseModel):
    answer: str
    cited_evidence_ids: list[str] = Field(default_factory=list)
    assumption_ids: list[str] = Field(default_factory=list)
    confidence_level: GuideConfidenceLevel = "unknown"
    unsupported_or_missing_evidence: list[str] = Field(default_factory=list)
    suggested_action_ids: list[str] = Field(default_factory=list)


class GuideEvidenceSearchLike(Protocol):
    cited_evidence_ids: list[str]
    retrieval_diagnostics: dict[str, Any] | None


def evidence_context_for_prompt(output: dict[str, Any]) -> list[dict[str, object]]:
    results = output.get("results")
    if not isinstance(results, list):
        return []
    context: list[dict[str, object]] = []
    for item in results[:5]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "")
        context.append(
            {
                "source_id": item.get("source_id"),
                "chunk_id": item.get("chunk_id"),
                "title": item.get("title"),
                "url": item.get("url"),
                "score": item.get("score"),
                "quote": text[:700],
            }
        )
    return context


def response_from_grounded_draft(
    context: GuideContextRead,
    draft: GroundedGuideAnswerDraft,
    search: GuideEvidenceSearchLike,
    run_id: uuid.UUID,
) -> GuideChatResponseRead:
    allowed_sources = set(search.cited_evidence_ids)
    cited_evidence_ids = [
        source_id for source_id in draft.cited_evidence_ids if source_id in allowed_sources
    ]
    actions = routing.actions_from_ids(context, draft.suggested_action_ids)
    if not actions:
        actions = routing.support_actions(context)[:3] or context.available_actions[:3]
    recommended_action = actions[0] if actions else context.available_actions[0]
    unsupported = draft.unsupported_or_missing_evidence[:4]
    if not cited_evidence_ids and not unsupported:
        unsupported = ["No retrieved source directly supports this answer."]
    return GuideChatResponseRead(
        answer=draft.answer,
        recommended_action=recommended_action,
        action_cards=actions[:4],
        related_entities=routing.related_entities_with_evidence(context, cited_evidence_ids),
        cited_evidence_ids=cited_evidence_ids,
        assumption_ids=draft.assumption_ids[:8],
        confidence_level=draft.confidence_level,
        unsupported_or_missing_evidence=unsupported,
        used_llm=True,
        retrieval_diagnostics=search.retrieval_diagnostics,
        ai_run_id=run_id,
    )
