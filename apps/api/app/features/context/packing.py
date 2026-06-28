"""Context-pack budget and drop-reason helpers."""

import uuid
from typing import Any

from app.ai.prompts import UNTRUSTED_RETRIEVED_CONTENT_RULE
from app.schemas.context import (
    ContextItem,
    ContextPack,
    ContextPolicy,
    DroppedContextItem,
    PromptContextSpec,
)


def pack(
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
    dropped_items: list[DroppedContextItem] = []
    token_count = 0
    for item in sorted(items, key=lambda candidate: candidate.priority):
        if len(selected) >= 30:
            dropped_items.append(dropped(item, "max_items_exceeded"))
            continue
        if token_count + item.token_count > token_budget:
            dropped_items.append(dropped(item, "token_budget_exceeded"))
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
        dropped_items=dropped_items,
        token_count=token_count,
        available_citation_ids=[
            item.provenance.citation_id
            for item in selected
            if item.provenance.citation_id is not None
        ],
        metadata={**metadata, "untrusted_content_rule": UNTRUSTED_RETRIEVED_CONTENT_RULE},
    )


def dropped(item: ContextItem, reason: str) -> DroppedContextItem:
    return DroppedContextItem(
        id=item.id,
        type=item.type,
        title=item.title,
        token_count=item.token_count,
        reason=reason,
    )

