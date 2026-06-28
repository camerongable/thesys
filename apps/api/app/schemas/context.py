import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ContextItemType = Literal[
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
    "tool_output",
]


class ContextProvenance(BaseModel):
    source: str
    entity_type: str | None = None
    entity_id: str | None = None
    citation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContextItem(BaseModel):
    id: str
    type: ContextItemType
    title: str
    content: str
    token_count: int
    provenance: ContextProvenance
    untrusted: bool = False
    priority: int = 100


class DroppedContextItem(BaseModel):
    id: str
    type: ContextItemType
    title: str
    token_count: int
    reason: str


class ContextPolicy(BaseModel):
    token_budget: int
    max_items: int = 30
    source_diversity_required: bool = True
    include_untrusted_content_rule: bool = True
    dropped_item_tracking: bool = True


class PromptContextSpec(BaseModel):
    prompt_version: str
    context_pack_version: str
    model_target: str
    expected_schema: str | None = None
    safety_rules: list[str] = Field(default_factory=list)


class ContextPack(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: str = "context-pack:v1"
    workflow_type: str
    project_id: uuid.UUID
    query: str | None = None
    policy: ContextPolicy
    prompt: PromptContextSpec
    items: list[ContextItem] = Field(default_factory=list)
    dropped_items: list[DroppedContextItem] = Field(default_factory=list)
    token_count: int = 0
    available_citation_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def prompt_metadata(self) -> dict[str, Any]:
        return {
            "context_pack_id": self.id,
            "context_pack_version": self.version,
            "workflow_type": self.workflow_type,
            "token_budget": self.policy.token_budget,
            "token_count": self.token_count,
            "item_count": len(self.items),
            "dropped_count": len(self.dropped_items),
            "available_citation_ids": self.available_citation_ids,
            "prompt": self.prompt.model_dump(mode="json"),
        }
