"""Static governed tool contracts shared by API, agents, guide, and MCP."""

from dataclasses import dataclass
from typing import Any, Literal

from fastapi import HTTPException, status

ToolAccessMode = Literal["read", "write", "proposal"]
ToolRiskLevel = Literal["low", "medium", "high", "critical"]
ApprovalPolicy = Literal["never_required", "required_for_write", "always_required"]
ToolDataClassification = Literal["public", "internal", "confidential", "restricted"]
ApprovalRequestType = Literal[
    "research_plan",
    "memory_update",
    "validation_plan",
    "decision",
    "tool_invocation",
]


@dataclass(frozen=True)
class ToolDefinition:
    """Static contract for one app-defined agent tool."""

    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    access_mode: ToolAccessMode
    risk_level: ToolRiskLevel
    approval_policy: ApprovalPolicy
    allowed_project_roles: list[str]
    version: str = "1.0.0"
    required_scopes: tuple[str, ...] = ()
    allowed_data_classifications: tuple[ToolDataClassification, ...] = (
        "public",
        "internal",
        "confidential",
    )
    allowed_network_destinations: tuple[str, ...] = ()
    timeout_seconds: int = 15
    max_output_bytes: int = 1_000_000
    max_affected_records: int | None = None
    reversible: bool = True
    owner: str = "thesys-core"

    def __post_init__(self) -> None:
        if not self.required_scopes:
            object.__setattr__(
                self,
                "required_scopes",
                ("project:read",) if self.access_mode == "read" else ("project:write",),
            )
        if self.max_affected_records is None:
            object.__setattr__(
                self,
                "max_affected_records",
                100 if self.access_mode == "read" else 1,
            )


PROJECT_READ_ROLES = ["owner", "admin", "editor", "viewer"]
PROJECT_MUTATION_ROLES = ["owner", "admin", "editor"]


TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "get_project_summary": ToolDefinition(
        name="get_project_summary",
        title="Get project summary",
        description="Read the structured thesis, customer segments, and problem hypotheses.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema={"type": "object", "properties": {"project": {"type": "object"}}},
        access_mode="read",
        risk_level="low",
        approval_policy="never_required",
        allowed_project_roles=PROJECT_READ_ROLES,
    ),
    "search_project_evidence": ToolDefinition(
        name="search_project_evidence",
        title="Search project evidence",
        description="Run scoped retrieval against project evidence chunks.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 500},
                "mode": {"type": "string", "enum": ["semantic", "keyword", "hybrid"]},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 25},
                "source_types": {"type": "array", "maxItems": 5},
                "competitor_id": {"type": ["string", "null"], "format": "uuid"},
                "assumption_id": {"type": ["string", "null"], "format": "uuid"},
                "research_sprint_id": {"type": ["string", "null"], "format": "uuid"},
                "created_after": {"type": ["string", "null"]},
                "created_before": {"type": ["string", "null"]},
                "freshness_days": {"type": ["integer", "null"], "minimum": 1, "maximum": 3650},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        output_schema={"type": "object", "properties": {"results": {"type": "array"}}},
        access_mode="read",
        risk_level="low",
        approval_policy="never_required",
        allowed_project_roles=PROJECT_READ_ROLES,
    ),
    "list_project_sources": ToolDefinition(
        name="list_project_sources",
        title="List project sources",
        description="List evidence sources and research source candidates for the project.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema={"type": "object", "properties": {"sources": {"type": "array"}}},
        access_mode="read",
        risk_level="low",
        approval_policy="never_required",
        allowed_project_roles=PROJECT_READ_ROLES,
    ),
    "list_competitors": ToolDefinition(
        name="list_competitors",
        title="List competitors",
        description="List approved competitors and research competitor candidates.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema={"type": "object", "properties": {"competitors": {"type": "array"}}},
        access_mode="read",
        risk_level="low",
        approval_policy="never_required",
        allowed_project_roles=PROJECT_READ_ROLES,
    ),
    "list_assumptions": ToolDefinition(
        name="list_assumptions",
        title="List assumptions",
        description="List current assumptions and risks.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema={
            "type": "object",
            "properties": {"assumptions": {"type": "array"}, "risks": {"type": "array"}},
        },
        access_mode="read",
        risk_level="low",
        approval_policy="never_required",
        allowed_project_roles=PROJECT_READ_ROLES,
    ),
    "list_validation_plans": ToolDefinition(
        name="list_validation_plans",
        title="List validation plans",
        description="List project experiments and validation-plan artifacts.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema={
            "type": "object",
            "properties": {"experiments": {"type": "array"}, "artifacts": {"type": "array"}},
        },
        access_mode="read",
        risk_level="low",
        approval_policy="never_required",
        allowed_project_roles=PROJECT_READ_ROLES,
    ),
    "list_decisions": ToolDefinition(
        name="list_decisions",
        title="List decisions",
        description="List recorded project decisions.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema={"type": "object", "properties": {"decisions": {"type": "array"}}},
        access_mode="read",
        risk_level="low",
        approval_policy="never_required",
        allowed_project_roles=PROJECT_READ_ROLES,
    ),
    "get_research_memo": ToolDefinition(
        name="get_research_memo",
        title="Get research memo",
        description="Read the latest research memo or the memo for a research sprint.",
        input_schema={
            "type": "object",
            "properties": {"research_sprint_id": {"type": "string", "format": "uuid"}},
            "additionalProperties": False,
        },
        output_schema={"type": "object", "properties": {"memo": {"type": ["object", "null"]}}},
        access_mode="read",
        risk_level="low",
        approval_policy="never_required",
        allowed_project_roles=PROJECT_READ_ROLES,
    ),
    "list_project_memory": ToolDefinition(
        name="list_project_memory",
        title="List project memory",
        description="List typed project memory items selected for a workflow or memory type.",
        input_schema={
            "type": "object",
            "properties": {
                "memory_type": {
                    "type": ["string", "null"],
                    "enum": [
                        "working",
                        "episodic",
                        "semantic",
                        "project",
                        "procedural",
                        "preference",
                        None,
                    ],
                },
                "workflow_type": {"type": ["string", "null"], "maxLength": 120},
                "include_stale": {"type": "boolean"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "additionalProperties": False,
        },
        output_schema={"type": "object", "properties": {"memory_items": {"type": "array"}}},
        access_mode="read",
        risk_level="low",
        approval_policy="never_required",
        allowed_project_roles=PROJECT_READ_ROLES,
    ),
    "propose_research_plan": ToolDefinition(
        name="propose_research_plan",
        title="Propose research plan",
        description="Create an auditable proposed research plan before user approval.",
        input_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string", "minLength": 1, "maxLength": 1000},
                "objective": {"type": "string", "minLength": 1, "maxLength": 2000},
            },
            "required": ["summary", "objective"],
            "additionalProperties": True,
        },
        output_schema={"type": "object", "properties": {"proposal": {"type": "object"}}},
        access_mode="proposal",
        risk_level="medium",
        approval_policy="always_required",
        allowed_project_roles=PROJECT_MUTATION_ROLES,
    ),
    "propose_memory_update": ToolDefinition(
        name="propose_memory_update",
        title="Propose memory update",
        description="Propose assumption, risk, and recommendation updates without mutating state.",
        input_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string", "minLength": 1, "maxLength": 1000},
                "research_sprint_id": {"type": "string", "format": "uuid"},
            },
            "required": ["summary"],
            "additionalProperties": True,
        },
        output_schema={"type": "object", "properties": {"proposal": {"type": "object"}}},
        access_mode="proposal",
        risk_level="medium",
        approval_policy="always_required",
        allowed_project_roles=PROJECT_MUTATION_ROLES,
    ),
    "propose_validation_plan": ToolDefinition(
        name="propose_validation_plan",
        title="Propose validation plan",
        description="Propose validation actions or experiments for human review.",
        input_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string", "minLength": 1, "maxLength": 1000},
                "actions": {"type": "array", "maxItems": 20},
                "research_sprint_id": {"type": "string", "format": "uuid"},
            },
            "required": ["summary"],
            "additionalProperties": True,
        },
        output_schema={"type": "object", "properties": {"proposal": {"type": "object"}}},
        access_mode="proposal",
        risk_level="medium",
        approval_policy="always_required",
        allowed_project_roles=PROJECT_MUTATION_ROLES,
    ),
    "propose_decision": ToolDefinition(
        name="propose_decision",
        title="Propose decision",
        description="Propose a decision record without writing it to the decision ledger.",
        input_schema={
            "type": "object",
            "properties": {
                "summary": {"type": "string", "minLength": 1, "maxLength": 1000},
                "decision": {"type": "object"},
                "research_sprint_id": {"type": "string", "format": "uuid"},
            },
            "required": ["summary"],
            "additionalProperties": True,
        },
        output_schema={"type": "object", "properties": {"proposal": {"type": "object"}}},
        access_mode="proposal",
        risk_level="high",
        approval_policy="always_required",
        allowed_project_roles=PROJECT_MUTATION_ROLES,
    ),
}


def list_tool_definitions() -> list[ToolDefinition]:
    """Return the stable tool registry exposed to UI, agents, and MCP clients."""

    definitions = list(TOOL_REGISTRY.values())
    for tool_definition in definitions:
        validate_tool_definition(tool_definition)
    return definitions


def definition(tool_name: str) -> ToolDefinition:
    tool_definition = TOOL_REGISTRY.get(tool_name)
    if tool_definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found.")
    try:
        validate_tool_definition(tool_definition)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tool manifest is unavailable.",
        ) from exc
    return tool_definition


def validate_tool_definition(tool_definition: ToolDefinition) -> None:
    """Reject malformed local manifests before tools are listed or invoked."""
    if (
        not tool_definition.name
        or not tool_definition.version
        or not tool_definition.description
        or not tool_definition.owner
    ):
        raise ValueError("Tool manifests require identity, version, description, and owner.")
    if (
        not isinstance(tool_definition.input_schema, dict)
        or not isinstance(tool_definition.output_schema, dict)
        or tool_definition.input_schema.get("type") != "object"
        or tool_definition.output_schema.get("type") != "object"
    ):
        raise ValueError("Tool manifests require object input and output schemas.")
    if not tool_definition.required_scopes:
        raise ValueError("Tool manifests require at least one scope.")
    if not tool_definition.allowed_data_classifications:
        raise ValueError("Tool manifests require allowed data classifications.")
    if (
        tool_definition.timeout_seconds < 1
        or tool_definition.timeout_seconds > 300
        or tool_definition.max_output_bytes < 1
        or tool_definition.max_output_bytes > 10_000_000
        or tool_definition.max_affected_records is None
        or tool_definition.max_affected_records < 1
        or tool_definition.max_affected_records > 10_000
    ):
        raise ValueError("Tool manifest bounds are invalid.")
    if (
        tool_definition.access_mode == "write"
        and tool_definition.approval_policy == "never_required"
    ):
        raise ValueError("Write tool manifests must define an approval policy.")


def approval_request_type_for_tool(tool_name: str) -> ApprovalRequestType:
    if tool_name == "propose_research_plan":
        return "research_plan"
    if tool_name == "propose_memory_update":
        return "memory_update"
    if tool_name == "propose_validation_plan":
        return "validation_plan"
    if tool_name == "propose_decision":
        return "decision"
    return "tool_invocation"


def summarize_output(tool_name: str, output: dict[str, Any]) -> str:
    if tool_name == "search_project_evidence":
        return f"Searched project evidence and returned {len(output.get('results', []))} result(s)."
    if tool_name == "list_project_sources":
        return (
            f"Listed {len(output.get('sources', []))} evidence source(s) and "
            f"{len(output.get('research_sources', []))} research source candidate(s)."
        )
    if tool_name == "list_competitors":
        return (
            f"Listed {len(output.get('competitors', []))} competitor(s) and "
            f"{len(output.get('competitor_candidates', []))} candidate(s)."
        )
    if tool_name == "list_assumptions":
        return (
            f"Listed {len(output.get('assumptions', []))} assumption(s) and "
            f"{len(output.get('risks', []))} risk(s)."
        )
    if tool_name.startswith("propose_"):
        proposal = output.get("proposal") or {}
        if isinstance(proposal, dict):
            return str(proposal.get("summary") or "Project update proposed.")[:1000]
        return "Project update proposed."
    if tool_name == "get_project_summary":
        project = output.get("project") or {}
        return f"Loaded project summary for {project.get('name', 'project')}."
    return f"Executed {tool_name}."
