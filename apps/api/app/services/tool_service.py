"""Governed project tool registry used by agents, guide chat, and MCP clients."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import (
    AuthContext,
    normalized_role,
    record_cross_tenant_access_attempt,
    require_permission,
)
from app.core.config import Settings
from app.core.redaction import redact_payload, redact_text
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
from app.features.governance_tools import audit as tool_audit
from app.features.governance_tools import registry as tool_registry
from app.features.governance_tools import schema_guard
from app.schemas.evidence import EvidenceRetrieveCreate
from app.services import (
    evidence_service,
    governance_service,
    memory_service,
    project_service,
    retrieval_service,
)

RequestedBy = Literal["agent", "user", "system"]
ToolDefinition = tool_registry.ToolDefinition
TOOL_REGISTRY = tool_registry.TOOL_REGISTRY
PROJECT_READ_ROLES = tool_registry.PROJECT_READ_ROLES
PROJECT_MUTATION_ROLES = tool_registry.PROJECT_MUTATION_ROLES
list_tool_definitions = tool_registry.list_tool_definitions
ToolGuardViolation = schema_guard.ToolGuardViolation


@dataclass(frozen=True)
class ToolExecutionResult:
    invocation: ToolInvocation
    output: dict[str, Any]


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
        metadata=_tool_invocation_requested_metadata(
            definition,
            include_approval_policy=True,
        ),
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
    invocation.output_summary = redact_text(
        _summarize_output(definition.name, output),
        redact_emails=True,
    )
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
            metadata=_tool_invocation_executed_metadata(definition),
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
        output_summary=redact_text(
            _summarize_output(definition.name, {"proposal": guarded_proposal}),
            redact_emails=True,
        ),
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
        metadata=_tool_invocation_requested_metadata(
            definition,
            include_approval_policy=False,
        ),
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
        metadata=_tool_invocation_status_metadata(invocation.tool_name, "approved"),
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
        metadata=_tool_invocation_status_metadata(invocation.tool_name, "rejected"),
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
        return _list_project_sources(db, auth, settings, project_id, research_sprint_id)
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
    settings: Settings,
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
            .options(selectinload(EvidenceSource.chunks))
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
                "summary": (
                    source.summary
                    if evidence_service.source_content_is_eligible(auth, settings, source)
                    else None
                ),
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


_guard_tool_input = schema_guard.guard_tool_input
_guard_proposal_payload = schema_guard.guard_proposal_payload
_guard_tool_metadata = schema_guard.guard_tool_metadata
_guard_tool_output = schema_guard.guard_tool_output
_guard_requested_by = schema_guard.guard_requested_by
_guard_research_sprint_scope = schema_guard.guard_research_sprint_scope
_validate_schema_payload = schema_guard.validate_schema_payload
_validate_schema_value = schema_guard.validate_schema_value
_validate_object_schema = schema_guard.validate_object_schema
_validate_array_schema = schema_guard.validate_array_schema
_validate_string_schema = schema_guard.validate_string_schema
_validate_json_value = schema_guard.validate_json_value


_definition = tool_registry.definition


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
        metadata=_tool_denial_metadata(
            definition,
            role=normalized_role(auth.role),
            reason=reason,
            detail=detail,
        ),
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
        summary=_tool_approval_summary(definition, invocation.output_summary),
        proposed_change=_tool_approval_proposed_change(
            definition,
            invocation_id=invocation.id,
            proposal=proposal,
        ),
        entity_type="tool_invocation",
        entity_id=invocation.id,
    )


_approval_request_type_for_tool = tool_registry.approval_request_type_for_tool
_tool_invocation_requested_metadata = tool_audit.invocation_requested_metadata
_tool_invocation_executed_metadata = tool_audit.invocation_executed_metadata
_tool_invocation_status_metadata = tool_audit.invocation_status_metadata
_tool_denial_metadata = tool_audit.denial_metadata
_tool_approval_summary = tool_audit.approval_summary
_tool_approval_proposed_change = tool_audit.approval_proposed_change


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
        record_cross_tenant_access_attempt(
            db,
            auth,
            reason_code="tool_invocation_scope_denied",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool invocation not found.",
        )
    return invocation


_summarize_output = tool_registry.summarize_output


def _decimal_to_float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _truncate(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value if len(value) <= limit else f"{value[: limit - 1]}..."
