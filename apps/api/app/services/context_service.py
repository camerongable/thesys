"""Context engineering helpers for bounded LLM prompts.

Context packs make prompt assembly inspectable: each item has a source,
priority, provenance, token estimate, and untrusted-content flag so workflows
can stay inside budget while preserving citation and safety boundaries.
"""

import json
import uuid
from dataclasses import dataclass
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


@dataclass(frozen=True)
class ContextProfile:
    """Workflow-specific context policy used by the shared compiler."""

    workflow_type: str
    token_budget_cap: int
    expected_item_types: tuple[str, ...]


CONTEXT_PROFILES: dict[str, ContextProfile] = {
    "assumption_extraction": ContextProfile(
        workflow_type="assumption_extraction",
        token_budget_cap=2200,
        expected_item_types=("project_summary", "memory", "context_summary"),
    ),
    "guide_chat": ContextProfile(
        workflow_type="guide_chat",
        token_budget_cap=3200,
        expected_item_types=("project_summary", "thesis", "memory", "evidence", "conversation_turn", "action"),
    ),
    "agentic_research": ContextProfile(
        workflow_type="agentic_research",
        token_budget_cap=4500,
        expected_item_types=("project_summary", "memory", "tool_output", "evidence", "gap"),
    ),
    "opportunity_brief": ContextProfile(
        workflow_type="opportunity_brief",
        token_budget_cap=4200,
        expected_item_types=("project_summary", "memory", "evidence", "safety_instruction"),
    ),
    "competitor_analysis": ContextProfile(
        workflow_type="competitor_analysis",
        token_budget_cap=3800,
        expected_item_types=("project_summary", "memory", "evidence", "tool_output"),
    ),
    "validation_plan": ContextProfile(
        workflow_type="validation_plan",
        token_budget_cap=3200,
        expected_item_types=("project_summary", "memory", "assumption", "risk"),
    ),
    "validation_result_interpretation": ContextProfile(
        workflow_type="validation_result_interpretation",
        token_budget_cap=3600,
        expected_item_types=("project_summary", "memory", "validation", "conversation_turn"),
    ),
    "decision_recommendation": ContextProfile(
        workflow_type="decision_recommendation",
        token_budget_cap=3600,
        expected_item_types=("project_summary", "memory", "assumption", "risk", "validation", "decision"),
    ),
}


class ContextCompiler:
    """Shared Sprint 51 context compiler for major AI workflows.

    Existing workflow-specific builders delegate to this compiler so prompt
    context, memory policy metadata, dropped item behavior, and safety metadata
    remain consistent across Ask Thesys, research, validation, and decision
    workflows.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def compile(
        self,
        *,
        workflow_type: str,
        project_id: uuid.UUID,
        query: str | None,
        items: list[ContextItem],
        prompt_version: str,
        expected_schema: str,
        metadata: dict[str, Any],
    ) -> ContextPack:
        profile = CONTEXT_PROFILES.get(
            workflow_type,
            ContextProfile(workflow_type, self.settings.retrieval_context_token_budget, tuple()),
        )
        token_budget = min(self.settings.retrieval_context_token_budget, profile.token_budget_cap)
        profile_metadata = {
            "context_profile": {
                "workflow_type": profile.workflow_type,
                "expected_item_types": list(profile.expected_item_types),
                "token_budget_cap": profile.token_budget_cap,
            }
        }
        return _pack(
            workflow_type=workflow_type,
            project_id=project_id,
            query=query,
            items=items,
            token_budget=token_budget,
            prompt_version=prompt_version,
            model_target=self.settings.litellm_model,
            expected_schema=expected_schema,
            metadata={**profile_metadata, **metadata},
        )

    def compile_workflow_context(
        self,
        *,
        workflow_type: str,
        project_id: uuid.UUID,
        query: str | None,
        domain_context: dict[str, Any],
        prompt_version: str,
        expected_schema: str,
        memory_selection: Any | None = None,
        evidence_results: list[Any] | None = None,
        untrusted_inputs: list[dict[str, Any]] | None = None,
        tool_outputs: dict[str, Any] | None = None,
    ) -> ContextPack:
        items: list[ContextItem] = [
            _item(
                f"{workflow_type}-domain-context",
                "project_summary",
                "Domain context",
                json.dumps(domain_context, default=str, ensure_ascii=True),
                source=f"{workflow_type}_domain_context",
                priority=10,
            )
        ]
        items.extend(_memory_items(memory_selection, base_priority=18))
        items.extend(_evidence_result_items(evidence_results or [], prefix=workflow_type, base_priority=30))
        for index, input_item in enumerate(untrusted_inputs or []):
            input_type = str(input_item.get("type") or "conversation_turn")
            if input_type not in {
                "project_summary",
                "thesis",
                "evidence",
                "assumption",
                "risk",
                "validation",
                "decision",
                "conversation_turn",
                "action",
                "gap",
                "memory",
                "context_summary",
                "safety_instruction",
                "conflict",
                "tool_output",
            }:
                input_type = "conversation_turn"
            items.append(
                _item(
                    f"{workflow_type}-untrusted-{index}",
                    input_type,
                    str(input_item.get("title") or "Untrusted input"),
                    str(input_item.get("content") or ""),
                    source=str(input_item.get("source") or f"{workflow_type}_input"),
                    metadata=dict(input_item.get("metadata") or {}),
                    untrusted=True,
                    priority=45 + index,
                )
            )
        for index, (name, output) in enumerate((tool_outputs or {}).items()):
            items.append(
                _item(
                    f"{workflow_type}-tool-{name}",
                    "tool_output",
                    name,
                    json.dumps(output, default=str, ensure_ascii=True),
                    source=f"{workflow_type}_tool_output",
                    metadata={"tool_name": name},
                    priority=55 + index,
                )
            )
        items.extend(_conflict_items(memory_selection, base_priority=65))
        return self.compile(
            workflow_type=workflow_type,
            project_id=project_id,
            query=query,
            items=items,
            prompt_version=prompt_version,
            expected_schema=expected_schema,
            metadata={
                "source": "context_service.ContextCompiler.compile_workflow_context",
                **_memory_metadata(memory_selection),
                "untrusted_input_count": len(untrusted_inputs or []),
                "evidence_count": len(evidence_results or []),
            },
        )


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
    memory_selection: Any | None = None,
) -> ContextPack:
    """Assemble bounded Ask Thesys prompt context from project state, tools, and evidence."""
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
    items.extend(_memory_items(memory_selection, base_priority=18))
    items.extend(_conflict_items(memory_selection, base_priority=70))

    return ContextCompiler(settings).compile(
        workflow_type="guide_chat",
        project_id=project_id,
        query=message,
        items=items,
        prompt_version=prompt_version,
        expected_schema=expected_schema,
        metadata={
            "source": "context_service.build_guide_context_pack",
            "recent_turn_count": len(recent_turns),
            "available_action_count": len(guide_context.available_actions),
            **_memory_metadata(memory_selection),
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
    memory_selection: Any | None = None,
) -> ContextPack:
    """Assemble bounded agentic-research context with explicit citation provenance."""
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
    items.extend(_memory_items(memory_selection, base_priority=18))
    items.extend(_conflict_items(memory_selection, base_priority=70))

    return ContextCompiler(settings).compile(
        workflow_type="agentic_research",
        project_id=project_id,
        query=objective,
        items=items,
        prompt_version=prompt_version,
        expected_schema=expected_schema,
        metadata={
            "source": "context_service.build_research_context_pack",
            "subquestion_count": len(subquestions),
            "evidence_count": len(selected_evidence),
            "gap_count": len(gaps),
            **_memory_metadata(memory_selection),
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
    """Apply token and item budgets, recording what was dropped and why."""

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


def _evidence_result_items(
    results: list[Any],
    *,
    prefix: str,
    base_priority: int,
) -> list[ContextItem]:
    items: list[ContextItem] = []
    for index, result in enumerate(results[:12]):
        source_id = _result_value(result, "source_id")
        chunk_id = _result_value(result, "chunk_id")
        citation_id = f"{source_id}:{chunk_id}" if source_id and chunk_id else None
        text = str(_result_value(result, "text") or "")[:900]
        items.append(
            _item(
                f"{prefix}-evidence-{chunk_id or index}",
                "evidence",
                str(_result_value(result, "title") or f"Retrieved evidence {index + 1}"),
                text,
                source=f"{prefix}_retrieval",
                entity_type="evidence_chunk" if chunk_id else "evidence_source",
                entity_id=str(chunk_id or source_id) if (chunk_id or source_id) else None,
                citation_id=citation_id,
                metadata={
                    "source_id": str(source_id) if source_id else None,
                    "chunk_id": str(chunk_id) if chunk_id else None,
                    "url": _result_value(result, "url"),
                    "score": _result_value(result, "score"),
                    "source_type": _result_value(result, "source_type"),
                },
                untrusted=True,
                priority=base_priority + index,
            )
        )
    return items


def _memory_items(memory_selection: Any | None, *, base_priority: int) -> list[ContextItem]:
    items: list[ContextItem] = []
    for index, memory in enumerate(_selected_memory(memory_selection)[:12]):
        memory_id = _memory_value(memory, "id")
        memory_type = str(_memory_value(memory, "memory_type") or "memory")
        status = str(_memory_value(memory, "status") or "unknown")
        write_policy = str(_memory_value(memory, "write_policy") or "unknown")
        provenance = _memory_value(memory, "provenance_metadata") or {}
        content = {
            "title": _memory_value(memory, "title"),
            "summary": _memory_value(memory, "summary"),
            "memory_type": memory_type,
            "status": status,
            "write_policy": write_policy,
            "content": _memory_value(memory, "content") or {},
        }
        items.append(
            _item(
                f"memory-{memory_id or index}",
                "memory",
                str(_memory_value(memory, "title") or f"{memory_type} memory"),
                json.dumps(content, default=str, ensure_ascii=True),
                source="memory_manager",
                entity_type="project_memory_item",
                entity_id=str(memory_id) if memory_id else None,
                metadata={
                    "memory_type": memory_type,
                    "status": status,
                    "write_policy": write_policy,
                    "provenance": provenance,
                },
                priority=base_priority + index,
            )
        )
    return items


def _conflict_items(memory_selection: Any | None, *, base_priority: int) -> list[ContextItem]:
    items: list[ContextItem] = []
    for index, conflict in enumerate(_memory_conflicts(memory_selection)):
        conflict_id = str(conflict.get("conflict_group_id") or index)
        items.append(
            _item(
                f"memory-conflict-{conflict_id}",
                "conflict",
                "Memory conflict",
                json.dumps(conflict, default=str, ensure_ascii=True),
                source="memory_manager",
                entity_type="memory_conflict",
                entity_id=conflict_id,
                metadata={"memory_item_ids": [str(item) for item in conflict.get("memory_item_ids", [])]},
                priority=base_priority + index,
            )
        )
    return items


def _memory_metadata(memory_selection: Any | None) -> dict[str, Any]:
    selected = _selected_memory(memory_selection)
    excluded = _excluded_memory(memory_selection)
    conflicts = _memory_conflicts(memory_selection)
    policy = _selection_value(memory_selection, "policy") or {}
    return {
        "memory_policy": policy,
        "selected_memory_count": len(selected),
        "excluded_memory_count": len(excluded),
        "memory_conflict_count": len(conflicts),
        "selected_memory_ids": [str(_memory_value(item, "id")) for item in selected],
        "excluded_memory": [
            {
                **item,
                "id": str(item.get("id")),
            }
            for item in excluded
            if isinstance(item, dict)
        ],
    }


def _selected_memory(memory_selection: Any | None) -> list[Any]:
    value = _selection_value(memory_selection, "selected")
    if value is None:
        value = _selection_value(memory_selection, "selected_memory")
    return list(value or [])


def _excluded_memory(memory_selection: Any | None) -> list[dict[str, Any]]:
    value = _selection_value(memory_selection, "excluded")
    if value is None:
        value = _selection_value(memory_selection, "excluded_memory")
    return list(value or [])


def _memory_conflicts(memory_selection: Any | None) -> list[dict[str, Any]]:
    value = _selection_value(memory_selection, "conflicts")
    return list(value or [])


def _selection_value(memory_selection: Any | None, key: str) -> Any:
    if memory_selection is None:
        return None
    if isinstance(memory_selection, dict):
        return memory_selection.get(key)
    return getattr(memory_selection, key, None)


def _memory_value(memory: Any, key: str) -> Any:
    if isinstance(memory, dict):
        return memory.get(key)
    return getattr(memory, key, None)


def _result_value(result: Any, key: str) -> Any:
    if isinstance(result, dict):
        return result.get(key)
    return getattr(result, key, None)


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
