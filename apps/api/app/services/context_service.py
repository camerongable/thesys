"""Context engineering helpers for bounded LLM prompts.

Context packs make prompt assembly inspectable: each item has a source,
priority, provenance, token estimate, and untrusted-content flag so workflows
can stay inside budget while preserving citation and safety boundaries.
"""

import json
import uuid
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.features.context import evidence_items as context_evidence_items
from app.features.context import packing as context_packing
from app.features.memory import context_pack as memory_context_pack
from app.schemas.context import (
    ContextItem,
    ContextPack,
)
from app.schemas.evidence import EvidenceRetrievalResultRead
from app.schemas.guide import GuideContextRead


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
        expected_item_types=(
            "project_summary",
            "thesis",
            "memory",
            "evidence",
            "conversation_turn",
            "action",
        ),
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
        expected_item_types=(
            "project_summary",
            "memory",
            "assumption",
            "risk",
            "validation",
            "decision",
        ),
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
        return context_packing.pack(
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
        items.extend(
            context_evidence_items.evidence_result_items(
                evidence_results or [],
                prefix=workflow_type,
                base_priority=30,
            )
        )
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
    for item in context_evidence_items.evidence_items(evidence_output):
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


_pack = context_packing.pack
_item = memory_context_pack.context_item
_evidence_items = context_evidence_items.evidence_items
_evidence_result_items = context_evidence_items.evidence_result_items
_memory_items = memory_context_pack.memory_items
_conflict_items = memory_context_pack.conflict_items
_memory_metadata = memory_context_pack.memory_metadata
_selected_memory = memory_context_pack.selected_memory
_excluded_memory = memory_context_pack.excluded_memory
_memory_conflicts = memory_context_pack.memory_conflicts
_selection_value = memory_context_pack.selection_value
_memory_value = memory_context_pack.memory_value
_result_value = context_evidence_items.result_value
_estimate_tokens = memory_context_pack.estimate_tokens
_dropped = context_packing.dropped
