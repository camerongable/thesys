"""Governed project tool registry used by agents, guide chat, and MCP clients."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, normalized_role, require_permission
from app.core.config import Settings
from app.core.redaction import redact_payload
from app.db.models import (
    Artifact,
    ArtifactVersion,
    Assumption,
    Competitor,
    CompetitorCandidate,
    Decision,
    EvidenceSource,
    Experiment,
    ResearchSprint,
    Risk,
    ToolInvocation,
)
from app.schemas.evidence import EvidenceRetrieveCreate
from app.services import governance_service, memory_service, project_service, retrieval_service

ToolAccessMode = Literal["read", "write", "proposal"]
ToolRiskLevel = Literal["low", "medium", "high"]
ApprovalPolicy = Literal["never_required", "required_for_write", "always_required"]
RequestedBy = Literal["agent", "user", "system"]
VALID_REQUESTED_BY: set[str] = {"agent", "user", "system"}
MAX_TOOL_STRING_LENGTH = 4000
MAX_TOOL_ARRAY_LENGTH = 100


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


@dataclass(frozen=True)
class ToolExecutionResult:
    invocation: ToolInvocation
    output: dict[str, Any]


class ToolGuardViolation(ValueError):
    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


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
    return list(TOOL_REGISTRY.values())


def list_tool_invocations(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    research_sprint_id: uuid.UUID | None = None,
    limit: int = 50,
) -> list[ToolInvocation]:
    project_service.get_project(db, auth, project_id)
    stmt = select(ToolInvocation).where(
        ToolInvocation.workspace_id == auth.workspace_id,
        ToolInvocation.project_id == project_id,
    )
    if research_sprint_id is not None:
        stmt = stmt.where(ToolInvocation.research_sprint_id == research_sprint_id)
    return list(db.scalars(stmt.order_by(ToolInvocation.created_at.desc()).limit(min(limit, 100))))


def execute_tool(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    tool_name: str,
    tool_input: dict[str, Any] | None = None,
    *,
    research_sprint_id: uuid.UUID | None = None,
    requested_by: RequestedBy = "agent",
) -> ToolExecutionResult:
    """Execute a read/write tool after schema, role, scope, and output guards."""
    definition = _definition(tool_name)
    project_service.get_project(db, auth, project_id)
    _authorize_tool_invocation(db, auth, project_id, definition)
    try:
        guarded_input = _guard_tool_input(
            definition,
            tool_input or {},
            research_sprint_id=research_sprint_id,
            requested_by=requested_by,
        )
    except ToolGuardViolation as exc:
        _audit_tool_denial(db, auth, project_id, definition, exc.reason, detail=exc.detail)
        db.commit()
        raise HTTPException(status_code=422, detail=exc.detail) from exc
    clean_input = redact_payload(guarded_input, redact_emails=True)
    invocation = ToolInvocation(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        research_sprint_id=research_sprint_id,
        tool_name=definition.name,
        access_mode=definition.access_mode,
        risk_level=definition.risk_level,
        input_json=clean_input,
        status="requested" if definition.access_mode == "proposal" else "executed",
        requested_by=requested_by,
        executed_at=None if definition.access_mode == "proposal" else datetime.now(UTC),
    )
    db.add(invocation)
    db.flush()
    governance_service.record_audit_event(
        db,
        auth,
        event_type="tool_invocation_requested",
        actor_type=requested_by,
        project_id=project_id,
        entity_type="tool_invocation",
        entity_id=invocation.id,
        risk_level=definition.risk_level,
        summary=f"{definition.title} requested.",
        metadata={
            "tool_name": definition.name,
            "access_mode": definition.access_mode,
            "approval_policy": definition.approval_policy,
        },
    )
    try:
        output = _run_tool(
            db,
            auth,
            settings,
            project_id,
            definition,
            guarded_input,
            research_sprint_id,
        )
    except Exception as exc:
        invocation.status = "failed"
        invocation.output_summary = str(exc)[:1000]
        invocation.executed_at = datetime.now(UTC)
        db.commit()
        raise
    try:
        _guard_tool_output(definition, output)
    except ToolGuardViolation as exc:
        invocation.status = "failed"
        invocation.output_summary = "Tool output failed guard validation."
        invocation.executed_at = datetime.now(UTC)
        _audit_tool_denial(db, auth, project_id, definition, exc.reason, detail=exc.detail)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.detail,
        ) from exc
    invocation.output_json = redact_payload(output, redact_emails=True)
    invocation.output_summary = _summarize_output(definition.name, output)
    if definition.access_mode != "proposal":
        invocation.status = "executed"
        invocation.executed_at = datetime.now(UTC)
        governance_service.record_audit_event(
            db,
            auth,
            event_type="tool_invocation_executed",
            actor_type=requested_by,
            project_id=project_id,
            entity_type="tool_invocation",
            entity_id=invocation.id,
            risk_level=definition.risk_level,
            summary=f"{definition.title} executed.",
            metadata={"tool_name": definition.name, "access_mode": definition.access_mode},
        )
    else:
        _create_tool_approval_request(
            db,
            auth,
            project_id,
            definition,
            invocation,
            requested_by=requested_by,
            proposal=output.get("proposal") if isinstance(output, dict) else None,
        )
    db.commit()
    db.refresh(invocation)
    return ToolExecutionResult(invocation=invocation, output=output)


def create_proposal(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    tool_name: str,
    proposal: dict[str, Any],
    *,
    research_sprint_id: uuid.UUID | None = None,
    requested_by: RequestedBy = "agent",
    input_json: dict[str, Any] | None = None,
) -> ToolInvocation:
    """Create an approval-gated proposal tool invocation without mutating state."""
    definition = _definition(tool_name)
    if definition.access_mode != "proposal":
        raise ValueError(f"{tool_name} is not a proposal tool.")
    project_service.get_project(db, auth, project_id)
    _authorize_tool_invocation(db, auth, project_id, definition)
    try:
        guarded_proposal = _guard_proposal_payload(
            definition,
            proposal,
            research_sprint_id=research_sprint_id,
            requested_by=requested_by,
        )
        guarded_input = _guard_tool_metadata(input_json or {})
    except ToolGuardViolation as exc:
        _audit_tool_denial(db, auth, project_id, definition, exc.reason, detail=exc.detail)
        db.commit()
        raise HTTPException(status_code=422, detail=exc.detail) from exc
    invocation = ToolInvocation(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        research_sprint_id=research_sprint_id,
        tool_name=definition.name,
        access_mode=definition.access_mode,
        risk_level=definition.risk_level,
        input_json=redact_payload(guarded_input, redact_emails=True),
        output_json=redact_payload({"proposal": guarded_proposal}, redact_emails=True),
        output_summary=_summarize_output(definition.name, {"proposal": guarded_proposal}),
        status="requested",
        requested_by=requested_by,
    )
    db.add(invocation)
    db.flush()
    governance_service.record_audit_event(
        db,
        auth,
        event_type="tool_invocation_requested",
        actor_type=requested_by,
        project_id=project_id,
        entity_type="tool_invocation",
        entity_id=invocation.id,
        risk_level=definition.risk_level,
        summary=f"{definition.title} requested.",
        metadata={"tool_name": definition.name, "access_mode": definition.access_mode},
    )
    _create_tool_approval_request(
        db,
        auth,
        project_id,
        definition,
        invocation,
        requested_by=requested_by,
        proposal=guarded_proposal,
    )
    db.commit()
    db.refresh(invocation)
    return invocation


def approve_tool_invocation(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    invocation_id: uuid.UUID,
) -> ToolInvocation:
    """Approve a pending tool proposal and resolve its associated approval record."""
    invocation = _get_invocation(db, auth, project_id, invocation_id)
    if invocation.access_mode == "read":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Read tool invocations do not require approval.",
        )
    if invocation.status not in {"requested", "executed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending tool proposals can be approved.",
        )
    if invocation.risk_level == "high":
        require_permission(auth, "approve_high_risk_tools")
    else:
        require_permission(auth, "approve_memory_updates")
    invocation.status = "approved"
    invocation.approved_by_user_id = auth.user_id
    invocation.executed_at = invocation.executed_at or datetime.now(UTC)
    governance_service.resolve_pending_approvals_for_entity(
        db,
        auth,
        project_id=project_id,
        entity_type="tool_invocation",
        entity_id=invocation.id,
        status_value="approved",
    )
    governance_service.record_audit_event(
        db,
        auth,
        event_type="tool_invocation_executed",
        actor_type="user",
        project_id=project_id,
        entity_type="tool_invocation",
        entity_id=invocation.id,
        risk_level=invocation.risk_level,
        summary=f"Approved tool proposal {invocation.tool_name}.",
        metadata={"tool_name": invocation.tool_name, "status": "approved"},
    )
    db.commit()
    db.refresh(invocation)
    return invocation


def reject_tool_invocation(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    invocation_id: uuid.UUID,
) -> ToolInvocation:
    """Reject a pending tool proposal and preserve the denial in audit history."""
    invocation = _get_invocation(db, auth, project_id, invocation_id)
    if invocation.access_mode == "read":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Read tool invocations do not require rejection.",
        )
    if invocation.status not in {"requested", "executed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending tool proposals can be rejected.",
        )
    if invocation.risk_level == "high":
        require_permission(auth, "approve_high_risk_tools")
    else:
        require_permission(auth, "approve_memory_updates")
    invocation.status = "rejected"
    invocation.executed_at = invocation.executed_at or datetime.now(UTC)
    governance_service.resolve_pending_approvals_for_entity(
        db,
        auth,
        project_id=project_id,
        entity_type="tool_invocation",
        entity_id=invocation.id,
        status_value="rejected",
    )
    governance_service.record_audit_event(
        db,
        auth,
        event_type="tool_invocation_denied",
        actor_type="user",
        project_id=project_id,
        entity_type="tool_invocation",
        entity_id=invocation.id,
        risk_level=invocation.risk_level,
        summary=f"Rejected tool proposal {invocation.tool_name}.",
        metadata={"tool_name": invocation.tool_name, "status": "rejected"},
    )
    db.commit()
    db.refresh(invocation)
    return invocation


def approve_pending_proposals_for_sprint(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    research_sprint_id: uuid.UUID,
    tool_names: set[str],
) -> list[ToolInvocation]:
    proposals = list(
        db.scalars(
            select(ToolInvocation).where(
                ToolInvocation.workspace_id == auth.workspace_id,
                ToolInvocation.project_id == project_id,
                ToolInvocation.research_sprint_id == research_sprint_id,
                ToolInvocation.tool_name.in_(tool_names),
                ToolInvocation.status == "requested",
                ToolInvocation.access_mode == "proposal",
            )
        )
    )
    now = datetime.now(UTC)
    for proposal in proposals:
        proposal.status = "approved"
        proposal.approved_by_user_id = auth.user_id
        proposal.executed_at = proposal.executed_at or now
        governance_service.resolve_pending_approvals_for_entity(
            db,
            auth,
            project_id=project_id,
            entity_type="tool_invocation",
            entity_id=proposal.id,
            status_value="approved",
        )
    db.flush()
    return proposals


def reject_pending_proposals_for_sprint(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    research_sprint_id: uuid.UUID,
    tool_names: set[str],
) -> list[ToolInvocation]:
    proposals = list(
        db.scalars(
            select(ToolInvocation).where(
                ToolInvocation.workspace_id == auth.workspace_id,
                ToolInvocation.project_id == project_id,
                ToolInvocation.research_sprint_id == research_sprint_id,
                ToolInvocation.tool_name.in_(tool_names),
                ToolInvocation.status == "requested",
                ToolInvocation.access_mode == "proposal",
            )
        )
    )
    now = datetime.now(UTC)
    for proposal in proposals:
        proposal.status = "rejected"
        proposal.executed_at = proposal.executed_at or now
        governance_service.resolve_pending_approvals_for_entity(
            db,
            auth,
            project_id=project_id,
            entity_type="tool_invocation",
            entity_id=proposal.id,
            status_value="rejected",
        )
    db.flush()
    return proposals


def _run_tool(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    definition: ToolDefinition,
    tool_input: dict[str, Any],
    research_sprint_id: uuid.UUID | None,
) -> dict[str, Any]:
    if definition.name == "get_project_summary":
        return _get_project_summary(db, auth, project_id)
    if definition.name == "search_project_evidence":
        payload = EvidenceRetrieveCreate.model_validate(tool_input)
        search = retrieval_service.retrieve_evidence_search(
            db,
            auth,
            settings,
            project_id,
            payload,
        )
        return {
            "results": [result.model_dump(mode="json") for result in search.results],
            "diagnostics": search.diagnostics.model_dump(mode="json"),
        }
    if definition.name == "list_project_sources":
        return _list_project_sources(db, auth, project_id, research_sprint_id)
    if definition.name == "list_competitors":
        return _list_competitors(db, auth, project_id, research_sprint_id)
    if definition.name == "list_assumptions":
        return _list_assumptions(db, auth, project_id)
    if definition.name == "list_validation_plans":
        return _list_validation_plans(db, auth, project_id)
    if definition.name == "list_decisions":
        return _list_decisions(db, auth, project_id)
    if definition.name == "get_research_memo":
        return _get_research_memo(db, auth, project_id, tool_input, research_sprint_id)
    if definition.name == "list_project_memory":
        return _list_project_memory(db, auth, project_id, tool_input)
    if definition.access_mode == "proposal":
        return {"proposal": tool_input, "requires_human_approval": True}
    raise ValueError(f"Unsupported tool: {definition.name}")


def _get_project_summary(db: Session, auth: AuthContext, project_id: uuid.UUID) -> dict[str, Any]:
    project = project_service.get_project(db, auth, project_id)
    thesis = project_service.current_thesis(project)
    return {
        "project": {
            "id": str(project.id),
            "name": project.name,
            "short_description": project.short_description,
            "current_thesis": thesis.thesis_text if thesis else None,
            "confidence_score": _decimal_to_float(project.confidence_score),
            "customer_segments": [segment.name for segment in project.customer_segments],
            "problem_hypotheses": [problem.description for problem in project.problems],
        }
    }


def _list_project_sources(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    research_sprint_id: uuid.UUID | None,
) -> dict[str, Any]:
    evidence_sources = list(
        db.scalars(
            select(EvidenceSource)
            .where(
                EvidenceSource.workspace_id == auth.workspace_id,
                EvidenceSource.project_id == project_id,
            )
            .order_by(EvidenceSource.created_at.desc())
            .limit(20)
        )
    )
    sprint_sources = []
    if research_sprint_id is not None:
        sprint = db.scalar(
            select(ResearchSprint).where(
                ResearchSprint.workspace_id == auth.workspace_id,
                ResearchSprint.project_id == project_id,
                ResearchSprint.id == research_sprint_id,
            )
        )
        if sprint is not None:
            sprint_sources = [
                {
                    "id": str(source.id),
                    "evidence_source_id": str(source.evidence_source_id)
                    if source.evidence_source_id
                    else None,
                    "title": source.title,
                    "url": source.url,
                    "source_type": source.source_type,
                    "status": source.status,
                    "associated_research_question": source.associated_research_question,
                }
                for source in sprint.discovered_sources
            ]
    return {
        "sources": [
            {
                "id": str(source.id),
                "title": source.title,
                "url": source.url,
                "source_type": source.source_type,
                "classification": source.classification,
                "ingestion_status": source.ingestion_status,
                "summary": source.summary,
            }
            for source in evidence_sources
        ],
        "research_sources": sprint_sources,
    }


def _list_competitors(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    research_sprint_id: uuid.UUID | None,
) -> dict[str, Any]:
    competitors = list(
        db.scalars(
            select(Competitor)
            .where(
                Competitor.workspace_id == auth.workspace_id,
                Competitor.project_id == project_id,
            )
            .order_by(Competitor.updated_at.desc())
            .limit(30)
        )
    )
    candidates = []
    if research_sprint_id is not None:
        candidates = list(
            db.scalars(
                select(CompetitorCandidate)
                .where(
                    CompetitorCandidate.workspace_id == auth.workspace_id,
                    CompetitorCandidate.project_id == project_id,
                    CompetitorCandidate.research_sprint_id == research_sprint_id,
                )
                .order_by(CompetitorCandidate.relevance_score.desc())
            )
        )
    return {
        "competitors": [
            {
                "id": str(competitor.id),
                "name": competitor.name,
                "category": competitor.category,
                "target_user": competitor.target_user,
                "positioning": competitor.positioning,
                "pricing_summary": competitor.pricing_summary,
                "threat_level": competitor.threat_level,
            }
            for competitor in competitors
        ],
        "competitor_candidates": [
            {
                "id": str(candidate.id),
                "name": candidate.name,
                "category": candidate.category,
                "status": candidate.status,
                "target_user": candidate.target_user,
                "positioning": candidate.positioning,
                "why_it_matters": candidate.why_it_matters,
                "threat_level": candidate.threat_level,
            }
            for candidate in candidates
        ],
    }


def _list_assumptions(db: Session, auth: AuthContext, project_id: uuid.UUID) -> dict[str, Any]:
    assumptions = list(
        db.scalars(
            select(Assumption)
            .where(
                Assumption.workspace_id == auth.workspace_id,
                Assumption.project_id == project_id,
            )
            .order_by(Assumption.kill_risk.desc(), Assumption.updated_at.desc())
            .limit(30)
        )
    )
    risks = list(
        db.scalars(
            select(Risk)
            .where(Risk.workspace_id == auth.workspace_id, Risk.project_id == project_id)
            .order_by(Risk.updated_at.desc())
            .limit(20)
        )
    )
    return {
        "assumptions": [
            {
                "id": str(assumption.id),
                "text": assumption.text,
                "importance": assumption.importance,
                "uncertainty": assumption.uncertainty,
                "kill_risk": assumption.kill_risk,
                "status": assumption.status,
                "confidence_score": _decimal_to_float(assumption.confidence_score),
            }
            for assumption in assumptions
        ],
        "risks": [
            {
                "id": str(risk.id),
                "text": risk.text,
                "severity": risk.severity,
                "likelihood": risk.likelihood,
                "status": risk.status,
            }
            for risk in risks
        ],
    }


def _list_validation_plans(db: Session, auth: AuthContext, project_id: uuid.UUID) -> dict[str, Any]:
    experiments = list(
        db.scalars(
            select(Experiment)
            .where(
                Experiment.workspace_id == auth.workspace_id,
                Experiment.project_id == project_id,
            )
            .order_by(Experiment.updated_at.desc())
            .limit(20)
        )
    )
    artifacts = list(
        db.scalars(
            select(Artifact)
            .where(
                Artifact.workspace_id == auth.workspace_id,
                Artifact.project_id == project_id,
                Artifact.artifact_type == "validation_plan",
            )
            .order_by(Artifact.updated_at.desc())
            .limit(10)
        )
    )
    return {
        "experiments": [
            {
                "id": str(experiment.id),
                "name": experiment.name,
                "method": experiment.method,
                "status": experiment.status,
                "success_criteria": experiment.success_criteria,
            }
            for experiment in experiments
        ],
        "artifacts": [
            {
                "id": str(artifact.id),
                "title": artifact.title,
                "current_version_id": str(artifact.current_version_id)
                if artifact.current_version_id
                else None,
            }
            for artifact in artifacts
        ],
    }


def _list_decisions(db: Session, auth: AuthContext, project_id: uuid.UUID) -> dict[str, Any]:
    decisions = list(
        db.scalars(
            select(Decision)
            .where(Decision.workspace_id == auth.workspace_id, Decision.project_id == project_id)
            .order_by(Decision.created_at.desc())
            .limit(20)
        )
    )
    return {
        "decisions": [
            {
                "id": str(decision.id),
                "decision_type": decision.decision_type,
                "title": decision.title,
                "rationale": decision.rationale,
                "review_date": decision.review_date.isoformat() if decision.review_date else None,
                "created_at": decision.created_at.isoformat(),
            }
            for decision in decisions
        ]
    }


def _get_research_memo(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    tool_input: dict[str, Any],
    research_sprint_id: uuid.UUID | None,
) -> dict[str, Any]:
    sprint_filter = tool_input.get("research_sprint_id") or (
        str(research_sprint_id) if research_sprint_id else None
    )
    versions = list(
        db.scalars(
            select(ArtifactVersion)
            .join(Artifact, Artifact.id == ArtifactVersion.artifact_id)
            .where(
                Artifact.workspace_id == auth.workspace_id,
                Artifact.project_id == project_id,
                Artifact.artifact_type == "research_memo",
            )
            .order_by(ArtifactVersion.created_at.desc())
            .limit(20)
        )
    )
    for version in versions:
        content = version.structured_content or {}
        if sprint_filter and content.get("research_sprint_id") != sprint_filter:
            continue
        return {
            "memo": {
                "artifact_version_id": str(version.id),
                "version": version.version,
                "research_sprint_id": content.get("research_sprint_id"),
                "memory_update_status": content.get("memory_update_status"),
                "summary": _truncate(version.markdown_content, 1200),
            }
        }
    return {"memo": None}


def _list_project_memory(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    workflow_type = tool_input.get("workflow_type")
    limit = int(tool_input.get("limit") or 50)
    if workflow_type:
        items = memory_service.select_memory_for_workflow(
            db,
            auth,
            project_id,
            workflow_type=str(workflow_type),
            limit=limit,
        )
    else:
        items = memory_service.list_memory(
            db,
            auth,
            project_id,
            memory_type=tool_input.get("memory_type"),
            include_stale=bool(tool_input.get("include_stale")),
            limit=limit,
        )
    return {"memory_items": [memory_service.serialize_memory_item(item) for item in items]}


def _guard_tool_input(
    definition: ToolDefinition,
    tool_input: dict[str, Any],
    *,
    research_sprint_id: uuid.UUID | None,
    requested_by: RequestedBy,
) -> dict[str, Any]:
    """Validate model/client input before any tool logic sees it."""
    _guard_requested_by(requested_by)
    guarded = _validate_schema_payload(
        definition.input_schema,
        tool_input,
        label=f"{definition.name} input",
    )
    _guard_research_sprint_scope(definition, guarded, research_sprint_id)
    return guarded


def _guard_proposal_payload(
    definition: ToolDefinition,
    proposal: dict[str, Any],
    *,
    research_sprint_id: uuid.UUID | None,
    requested_by: RequestedBy,
) -> dict[str, Any]:
    _guard_requested_by(requested_by)
    guarded = _validate_schema_payload(
        definition.input_schema,
        proposal,
        label=f"{definition.name} proposal",
    )
    _guard_research_sprint_scope(definition, guarded, research_sprint_id)
    if research_sprint_id is not None and "research_sprint_id" not in guarded:
        raise ToolGuardViolation(
            "scope_guard_failed",
            f"{definition.name} proposal must include the scoped research_sprint_id.",
        )
    return guarded


def _guard_tool_metadata(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ToolGuardViolation("input_guard_failed", "Tool metadata must be a JSON object.")
    _validate_json_value(value, "tool metadata")
    return value


def _guard_tool_output(definition: ToolDefinition, output: dict[str, Any]) -> None:
    _validate_schema_payload(
        definition.output_schema,
        output,
        label=f"{definition.name} output",
    )


def _guard_requested_by(requested_by: str) -> None:
    if requested_by not in VALID_REQUESTED_BY:
        raise ToolGuardViolation(
            "requested_by_guard_failed",
            "Tool requested_by must be agent, user, or system.",
        )


def _guard_research_sprint_scope(
    definition: ToolDefinition,
    payload: dict[str, Any],
    research_sprint_id: uuid.UUID | None,
) -> None:
    raw_sprint_id = payload.get("research_sprint_id")
    if raw_sprint_id is None:
        return
    try:
        payload_sprint_id = uuid.UUID(str(raw_sprint_id))
    except ValueError as exc:
        raise ToolGuardViolation(
            "scope_guard_failed",
            f"{definition.name} research_sprint_id must be a valid UUID.",
        ) from exc
    if research_sprint_id is not None and payload_sprint_id != research_sprint_id:
        raise ToolGuardViolation(
            "scope_guard_failed",
            f"{definition.name} research_sprint_id does not match the scoped sprint.",
        )


def _validate_schema_payload(
    schema: dict[str, Any],
    value: Any,
    *,
    label: str,
) -> dict[str, Any]:
    _validate_schema_value(schema, value, label)
    if not isinstance(value, dict):
        raise ToolGuardViolation("input_guard_failed", f"{label} must be a JSON object.")
    return value


def _validate_schema_value(schema: dict[str, Any], value: Any, path: str) -> None:
    expected_type = schema.get("type")
    if isinstance(expected_type, list):
        if value is None and "null" in expected_type:
            return
        non_null_types = [item for item in expected_type if item != "null"]
        expected_type = non_null_types[0] if non_null_types else None
    if "enum" in schema and value not in schema["enum"]:
        raise ToolGuardViolation("input_guard_failed", f"{path} must be one of {schema['enum']}.")
    if expected_type == "object":
        _validate_object_schema(schema, value, path)
    elif expected_type == "array":
        _validate_array_schema(schema, value, path)
    elif expected_type == "string":
        _validate_string_schema(schema, value, path)
    elif expected_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ToolGuardViolation("input_guard_failed", f"{path} must be an integer.")
        if "minimum" in schema and value < schema["minimum"]:
            raise ToolGuardViolation("input_guard_failed", f"{path} is below the minimum.")
        if "maximum" in schema and value > schema["maximum"]:
            raise ToolGuardViolation("input_guard_failed", f"{path} is above the maximum.")
    elif expected_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ToolGuardViolation("input_guard_failed", f"{path} must be a number.")
    elif expected_type == "boolean":
        if not isinstance(value, bool):
            raise ToolGuardViolation("input_guard_failed", f"{path} must be a boolean.")
    else:
        _validate_json_value(value, path)


def _validate_object_schema(schema: dict[str, Any], value: Any, path: str) -> None:
    if not isinstance(value, dict):
        raise ToolGuardViolation("input_guard_failed", f"{path} must be a JSON object.")
    _validate_json_value(value, path)
    properties = schema.get("properties") or {}
    for required_key in schema.get("required", []):
        if required_key not in value:
            raise ToolGuardViolation(
                "input_guard_failed",
                f"{path} is missing required field {required_key}.",
            )
    if schema.get("additionalProperties") is False:
        unknown_keys = sorted(set(value) - set(properties))
        if unknown_keys:
            raise ToolGuardViolation(
                "input_guard_failed",
                f"{path} has unsupported field {unknown_keys[0]}.",
            )
    for key, property_schema in properties.items():
        if key in value:
            _validate_schema_value(property_schema, value[key], f"{path}.{key}")


def _validate_array_schema(schema: dict[str, Any], value: Any, path: str) -> None:
    if not isinstance(value, list):
        raise ToolGuardViolation("input_guard_failed", f"{path} must be an array.")
    max_items = min(int(schema.get("maxItems", MAX_TOOL_ARRAY_LENGTH)), MAX_TOOL_ARRAY_LENGTH)
    if len(value) > max_items:
        raise ToolGuardViolation("input_guard_failed", f"{path} has too many items.")
    item_schema = schema.get("items")
    for index, item in enumerate(value):
        if isinstance(item_schema, dict):
            _validate_schema_value(item_schema, item, f"{path}[{index}]")
        else:
            _validate_json_value(item, f"{path}[{index}]")


def _validate_string_schema(schema: dict[str, Any], value: Any, path: str) -> None:
    if not isinstance(value, str):
        raise ToolGuardViolation("input_guard_failed", f"{path} must be a string.")
    min_length = int(schema.get("minLength", 0))
    max_length = min(int(schema.get("maxLength", MAX_TOOL_STRING_LENGTH)), MAX_TOOL_STRING_LENGTH)
    if len(value) < min_length:
        raise ToolGuardViolation("input_guard_failed", f"{path} is too short.")
    if len(value) > max_length:
        raise ToolGuardViolation("input_guard_failed", f"{path} is too long.")
    if schema.get("format") == "uuid":
        try:
            uuid.UUID(value)
        except ValueError as exc:
            raise ToolGuardViolation(
                "input_guard_failed",
                f"{path} must be a valid UUID.",
            ) from exc


def _validate_json_value(value: Any, path: str) -> None:
    if isinstance(value, dict):
        if len(value) > MAX_TOOL_ARRAY_LENGTH:
            raise ToolGuardViolation("input_guard_failed", f"{path} has too many fields.")
        for key, item in value.items():
            if not isinstance(key, str):
                raise ToolGuardViolation("input_guard_failed", f"{path} keys must be strings.")
            _validate_json_value(item, f"{path}.{key}")
        return
    if isinstance(value, list):
        if len(value) > MAX_TOOL_ARRAY_LENGTH:
            raise ToolGuardViolation("input_guard_failed", f"{path} has too many items.")
        for index, item in enumerate(value):
            _validate_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, str):
        if len(value) > MAX_TOOL_STRING_LENGTH:
            raise ToolGuardViolation("input_guard_failed", f"{path} is too long.")
        return
    if isinstance(value, (int, float, bool)) or value is None:
        return
    raise ToolGuardViolation("input_guard_failed", f"{path} must be JSON serializable.")


def _definition(tool_name: str) -> ToolDefinition:
    definition = TOOL_REGISTRY.get(tool_name)
    if definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found.")
    return definition


def _authorize_tool_invocation(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    definition: ToolDefinition,
) -> None:
    """Enforce role and risk policy independently of caller type."""
    role = normalized_role(auth.role)
    if role not in definition.allowed_project_roles:
        _audit_tool_denial(db, auth, project_id, definition, "role_not_allowed")
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This role cannot use the requested project tool.",
        )
    if definition.access_mode == "read":
        return
    if definition.risk_level == "high" and definition.access_mode == "write":
        try:
            require_permission(auth, "approve_high_risk_tools")
        except HTTPException:
            _audit_tool_denial(db, auth, project_id, definition, "high_risk_write_denied")
            db.commit()
            raise
        return
    try:
        require_permission(auth, "run_research")
    except HTTPException:
        _audit_tool_denial(db, auth, project_id, definition, "mutating_tool_denied")
        db.commit()
        raise


def _audit_tool_denial(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    definition: ToolDefinition,
    reason: str,
    *,
    detail: str | None = None,
) -> None:
    governance_service.record_audit_event(
        db,
        auth,
        event_type="tool_invocation_denied",
        actor_type="user",
        project_id=project_id,
        entity_type="tool",
        entity_id=None,
        risk_level=definition.risk_level,
        summary=f"Denied {definition.title}.",
        metadata={
            "tool_name": definition.name,
            "access_mode": definition.access_mode,
            "approval_policy": definition.approval_policy,
            "role": normalized_role(auth.role),
            "reason": reason,
            "detail": detail,
        },
    )


def _create_tool_approval_request(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    definition: ToolDefinition,
    invocation: ToolInvocation,
    *,
    requested_by: RequestedBy,
    proposal: Any,
) -> None:
    if definition.approval_policy == "never_required":
        return
    governance_service.create_approval_request(
        db,
        auth,
        project_id=project_id,
        request_type=_approval_request_type_for_tool(definition.name),
        requested_by=requested_by,
        risk_level=definition.risk_level,
        summary=invocation.output_summary or f"{definition.title} requires approval.",
        proposed_change={
            "tool_name": definition.name,
            "tool_invocation_id": str(invocation.id),
            "proposal": proposal or {},
        },
        entity_type="tool_invocation",
        entity_id=invocation.id,
    )


def _approval_request_type_for_tool(tool_name: str) -> governance_service.ApprovalRequestType:
    if tool_name == "propose_research_plan":
        return "research_plan"
    if tool_name == "propose_memory_update":
        return "memory_update"
    if tool_name == "propose_validation_plan":
        return "validation_plan"
    if tool_name == "propose_decision":
        return "decision"
    return "tool_invocation"


def _get_invocation(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    invocation_id: uuid.UUID,
) -> ToolInvocation:
    invocation = db.scalar(
        select(ToolInvocation).where(
            ToolInvocation.id == invocation_id,
            ToolInvocation.workspace_id == auth.workspace_id,
            ToolInvocation.project_id == project_id,
        )
    )
    if invocation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool invocation not found.",
        )
    return invocation


def _summarize_output(tool_name: str, output: dict[str, Any]) -> str:
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


def _decimal_to_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _truncate(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value if len(value) <= limit else f"{value[: limit - 1]}..."
