import json
import uuid
from typing import Any

from app.ai.prompts import UNTRUSTED_RETRIEVED_CONTENT_RULE
from app.core.config import Settings
from app.schemas.context import (
    ContextItem,
    ContextPack,
    ContextPolicy,
    ContextProvenance,
    DroppedContextItem,
    PromptContextSpec,
)
from app.schemas.evidence import EvidenceRetrievalResultRead
from app.schemas.guide import GuideContextRead

APPROX_CHARS_PER_TOKEN = 4


def build_guide_context_pack(
    settings: Settings,
    *,
    project_id: uuid.UUID,
    message: str,
    guide_context: GuideContextRead,
    evidence_output: dict[str, Any],
    recent_turns: list[dict[str, str]],
    prompt_version: str,
    expected_schema: str,
) -> ContextPack:
    items: list[ContextItem] = [
        _item(
            "guide-project-state",
            "project_summary",
            "Project state",
            guide_context.model_dump_json(),
            source="guide_context",
            priority=10,
        )
    ]
    if guide_context.current_thesis:
        items.append(
            _item(
                "guide-current-thesis",
                "thesis",
                "Current thesis",
                guide_context.current_thesis,
                source="guide_context",
                priority=8,
            )
        )
    for index, turn in enumerate(recent_turns[-6:]):
        items.append(
            _item(
                f"guide-turn-{index}",
                "conversation_turn",
                f"Recent {turn.get('role', 'turn')}",
                str(turn.get("content") or ""),
                source="recent_turns",
                priority=35 + index,
            )
        )
    for index, action in enumerate(guide_context.available_actions[:8]):
        items.append(
            _item(
                f"guide-action-{action.id}",
                "action",
                action.label,
                action.model_dump_json(),
                source="guide_actions",
                entity_type="guide_action",
                entity_id=action.id,
                priority=45 + index,
            )
        )
    for item in _evidence_items(evidence_output):
        items.append(item)

    return _pack(
        workflow_type="guide_chat",
        project_id=project_id,
        query=message,
        items=items,
        token_budget=min(settings.retrieval_context_token_budget, 3200),
        prompt_version=prompt_version,
        model_target=settings.litellm_model,
        expected_schema=expected_schema,
        metadata={
            "source": "context_service.build_guide_context_pack",
            "recent_turn_count": len(recent_turns),
            "available_action_count": len(guide_context.available_actions),
        },
    )


def build_research_context_pack(
    settings: Settings,
    *,
    project_id: uuid.UUID,
    objective: str,
    project_context: dict[str, Any],
    subquestions: list[str],
    selected_evidence: list[EvidenceRetrievalResultRead],
    gaps: list[str],
    prompt_version: str,
    expected_schema: str,
) -> ContextPack:
    items: list[ContextItem] = [
        _item(
            "research-project-context",
            "project_summary",
            "Project context",
            json.dumps(project_context, default=str, ensure_ascii=True),
            source="research_context_tools",
            priority=10,
        ),
        _item(
            "research-subquestions",
            "tool_output",
            "Research subquestions",
            json.dumps(subquestions, ensure_ascii=True),
            source="research_planner",
            priority=20,
        ),
    ]
    for index, result in enumerate(selected_evidence):
        citation_id = f"{result.source_id}:{result.chunk_id}"
        items.append(
            _item(
                f"research-evidence-{result.chunk_id}",
                "evidence",
                result.title or f"Evidence chunk {index + 1}",
                result.text[:900],
                source="selected_evidence",
                entity_type="evidence_chunk",
                entity_id=str(result.chunk_id),
                citation_id=citation_id,
                metadata={
                    "source_id": str(result.source_id),
                    "chunk_id": str(result.chunk_id),
                    "score": result.score,
                    "url": result.url,
                    "source_type": result.source_type,
                },
                untrusted=True,
                priority=25 + index,
            )
        )
    for index, gap in enumerate(gaps):
        items.append(
            _item(
                f"research-gap-{index}",
                "gap",
                "Detected evidence gap",
                gap,
                source="gap_detector",
                priority=60 + index,
            )
        )

    return _pack(
        workflow_type="agentic_research",
        project_id=project_id,
        query=objective,
        items=items,
        token_budget=min(settings.retrieval_context_token_budget, 4500),
        prompt_version=prompt_version,
        model_target=settings.litellm_model,
        expected_schema=expected_schema,
        metadata={
            "source": "context_service.build_research_context_pack",
            "subquestion_count": len(subquestions),
            "evidence_count": len(selected_evidence),
            "gap_count": len(gaps),
        },
    )


def _pack(
    *,
    workflow_type: str,
    project_id: uuid.UUID,
    query: str | None,
    items: list[ContextItem],
    token_budget: int,
    prompt_version: str,
    model_target: str,
    expected_schema: str,
    metadata: dict[str, Any],
) -> ContextPack:
    selected: list[ContextItem] = []
    dropped: list[DroppedContextItem] = []
    token_count = 0
    for item in sorted(items, key=lambda candidate: candidate.priority):
        if len(selected) >= 30:
            dropped.append(_dropped(item, "max_items_exceeded"))
            continue
        if token_count + item.token_count > token_budget:
            dropped.append(_dropped(item, "token_budget_exceeded"))
            continue
        selected.append(item)
        token_count += item.token_count

    return ContextPack(
        workflow_type=workflow_type,
        project_id=project_id,
        query=query,
        policy=ContextPolicy(token_budget=token_budget),
        prompt=PromptContextSpec(
            prompt_version=prompt_version,
            context_pack_version="context-pack:v1",
            model_target=model_target,
            expected_schema=expected_schema,
            safety_rules=["untrusted_retrieved_content"],
        ),
        items=selected,
        dropped_items=dropped,
        token_count=token_count,
        available_citation_ids=[
            item.provenance.citation_id
            for item in selected
            if item.provenance.citation_id is not None
        ],
        metadata={**metadata, "untrusted_content_rule": UNTRUSTED_RETRIEVED_CONTENT_RULE},
    )


def _item(
    item_id: str,
    item_type: str,
    title: str,
    content: str,
    *,
    source: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    citation_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    untrusted: bool = False,
    priority: int = 100,
) -> ContextItem:
    return ContextItem(
        id=item_id,
        type=item_type,  # type: ignore[arg-type]
        title=title[:200],
        content=content,
        token_count=_estimate_tokens(content),
        provenance=ContextProvenance(
            source=source,
            entity_type=entity_type,
            entity_id=entity_id,
            citation_id=citation_id,
            metadata=metadata or {},
        ),
        untrusted=untrusted,
        priority=priority,
    )


def _evidence_items(output: dict[str, Any]) -> list[ContextItem]:
    results = output.get("results")
    if not isinstance(results, list):
        return []
    items: list[ContextItem] = []
    for index, result in enumerate(results[:10]):
        if not isinstance(result, dict):
            continue
        source_id = str(result.get("source_id") or "")
        chunk_id = str(result.get("chunk_id") or "")
        citation_id = f"{source_id}:{chunk_id}" if source_id and chunk_id else None
        text = str(result.get("text") or "")[:900]
        items.append(
            _item(
                f"guide-evidence-{chunk_id or index}",
                "evidence",
                str(result.get("title") or f"Retrieved evidence {index + 1}"),
                text,
                source="search_project_evidence",
                entity_type="evidence_chunk" if chunk_id else "evidence_source",
                entity_id=chunk_id or source_id or None,
                citation_id=citation_id,
                metadata={
                    "source_id": source_id,
                    "chunk_id": chunk_id,
                    "url": result.get("url"),
                    "score": result.get("score"),
                    "source_type": result.get("source_type"),
                },
                untrusted=True,
                priority=20 + index,
            )
        )
    return items


def _estimate_tokens(content: str) -> int:
    return max(1, len(content) // APPROX_CHARS_PER_TOKEN)


def _dropped(item: ContextItem, reason: str) -> DroppedContextItem:
    return DroppedContextItem(
        id=item.id,
        type=item.type,
        title=item.title,
        token_count=item.token_count,
        reason=reason,
    )
