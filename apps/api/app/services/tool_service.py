"""Governed project tool registry used by agents, guide chat, and MCP clients."""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.auth import (
    AuthContext,
    normalized_role,
    record_cross_tenant_access_attempt,
    require_permission,
)
from app.core.config import Settings, get_settings
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
from app.features.policy.opa import (
    OpaPolicyClient,
    OpaPolicyDecision,
    OpaPolicyUnavailableError,
    opa_policy_enforced,
    require_opa_decision,
    unavailable_opa_policy_denial,
)
from app.schemas.evidence import EvidenceRetrieveCreate
from app.security.workflow_budget import (
    WORKFLOW_BUDGET_EXHAUSTED_DETAIL,
    WorkflowSecurityBudget,
)
from app.services import (
    evidence_service,
    governance_service,
    memory_service,
    project_service,
    retrieval_service,
    security_policy_service,
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
    remote_mcp_server_id: uuid.UUID | None = None,
) -> ToolExecutionResult:
    """Execute a read/write tool after schema, role, scope, and output guards."""
    definition = _definition(tool_name)
    project = project_service.get_project(db, auth, project_id)
    _authorize_tool_invocation(db, auth, project_id, definition)
    _enforce_workflow_tool_budget(
        db,
        auth,
        settings,
        project_id=project_id,
        research_sprint_id=research_sprint_id,
        requested_by=requested_by,
    )
    _enforce_agent_write_kill_switch(
        db,
        auth,
        settings,
        project_id=project_id,
        definition=definition,
        requested_by=requested_by,
    )
    try:
        guarded_input = _guard_tool_input(
            definition,
            tool_input or {},
            research_sprint_id=research_sprint_id,
            requested_by=requested_by,
        )
        _guard_tool_manifest_input(definition, guarded_input)
    except ToolGuardViolation as exc:
        _audit_tool_denial(db, auth, project_id, definition, exc.reason, detail=exc.detail)
        db.commit()
        raise HTTPException(status_code=422, detail=exc.detail) from exc
    guarded_input, retrieved_chunk_limit = _cap_workflow_retrieval_input(
        db,
        auth,
        settings,
        project_id=project_id,
        definition=definition,
        tool_input=guarded_input,
        research_sprint_id=research_sprint_id,
        requested_by=requested_by,
    )
    _enforce_workflow_memory_proposal_budget(
        db,
        auth,
        settings=settings,
        project_id=project_id,
        definition=definition,
        research_sprint_id=research_sprint_id,
        requested_by=requested_by,
    )
    policy_decision = _authorize_opa_tool_invocation(
        db,
        auth,
        settings,
        project,
        definition,
        requested_by=requested_by,
        research_sprint_id=research_sprint_id,
        allow_required_approval=(
            remote_mcp_server_id is not None and definition.access_mode == "write"
        ),
    )
    clean_input = redact_payload(guarded_input, redact_emails=True)
    _enforce_repeated_tool_invocation_limit(
        db,
        auth,
        settings,
        project_id=project_id,
        definition=definition,
        input_json=clean_input,
        research_sprint_id=research_sprint_id,
        requested_by=requested_by,
    )
    if remote_mcp_server_id is not None:
        from app.services import mcp_registry_service

        if definition.access_mode == "write":
            mcp_registry_service.prepare_remote_write_request(
                db,
                auth,
                settings,
                project_id=project_id,
                registration_id=remote_mcp_server_id,
                tool_name=definition.name,
            )
        else:
            mcp_registry_service.prepare_tool_invocation(
                db,
                auth,
                settings,
                project_id=project_id,
                registration_id=remote_mcp_server_id,
                tool_name=definition.name,
            )
    if remote_mcp_server_id is not None and definition.access_mode == "write":
        return _request_remote_write(
            db,
            auth,
            project_id,
            definition,
            clean_input,
            research_sprint_id=research_sprint_id,
            requested_by=requested_by,
            remote_mcp_server_id=remote_mcp_server_id,
            policy_decision=policy_decision,
        )
    invocation = ToolInvocation(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        research_sprint_id=research_sprint_id,
        remote_mcp_server_id=remote_mcp_server_id,
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
            policy_decision=_opa_decision_metadata(policy_decision),
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
            invocation_id=invocation.id,
            remote_mcp_server_id=remote_mcp_server_id,
        )
    except Exception as exc:
        invocation.status = "failed"
        invocation.output_summary = str(exc)[:1000]
        invocation.executed_at = datetime.now(UTC)
        db.commit()
        raise
    output = _limit_retrieved_chunk_output(definition, output, retrieved_chunk_limit)
    try:
        _guard_tool_output(definition, output)
        _guard_tool_manifest_output(definition, output)
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


def _request_remote_write(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    definition: ToolDefinition,
    clean_input: dict[str, Any],
    *,
    research_sprint_id: uuid.UUID | None,
    requested_by: RequestedBy,
    remote_mcp_server_id: uuid.UUID,
    policy_decision: OpaPolicyDecision | None,
) -> ToolExecutionResult:
    preview = {
        "summary": f"{definition.title} will run against the reviewed remote MCP server.",
        "max_affected_records": definition.max_affected_records,
        "reversible": definition.reversible,
    }
    invocation = ToolInvocation(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        research_sprint_id=research_sprint_id,
        remote_mcp_server_id=remote_mcp_server_id,
        idempotency_key=uuid.uuid4().hex,
        tool_name=definition.name,
        access_mode=definition.access_mode,
        risk_level=definition.risk_level,
        input_json=clean_input,
        output_json={"preview": preview},
        output_summary=preview["summary"],
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
            include_approval_policy=True,
            policy_decision=_opa_decision_metadata(policy_decision),
        ),
    )
    _create_tool_approval_request(
        db,
        auth,
        project_id,
        definition,
        invocation,
        requested_by=requested_by,
        proposal={
            "preview": preview,
            "arguments": clean_input,
            "remote_mcp_server_id": str(remote_mcp_server_id),
        },
    )
    db.commit()
    db.refresh(invocation)
    return ToolExecutionResult(invocation=invocation, output={"preview": preview})


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
    settings: Settings | None = None,
) -> ToolInvocation:
    """Create an approval-gated proposal tool invocation without mutating state."""
    definition = _definition(tool_name)
    if definition.access_mode != "proposal":
        raise ValueError(f"{tool_name} is not a proposal tool.")
    project = project_service.get_project(db, auth, project_id)
    _authorize_tool_invocation(db, auth, project_id, definition)
    effective_settings = settings or get_settings()
    _enforce_workflow_tool_budget(
        db,
        auth,
        effective_settings,
        project_id=project_id,
        research_sprint_id=research_sprint_id,
        requested_by=requested_by,
    )
    _enforce_agent_write_kill_switch(
        db,
        auth,
        effective_settings,
        project_id=project_id,
        definition=definition,
        requested_by=requested_by,
    )
    try:
        guarded_proposal = _guard_proposal_payload(
            definition,
            proposal,
            research_sprint_id=research_sprint_id,
            requested_by=requested_by,
        )
        _guard_tool_manifest_input(definition, guarded_proposal)
        guarded_input = _guard_tool_metadata(input_json or {})
    except ToolGuardViolation as exc:
        _audit_tool_denial(db, auth, project_id, definition, exc.reason, detail=exc.detail)
        db.commit()
        raise HTTPException(status_code=422, detail=exc.detail) from exc
    _enforce_workflow_memory_proposal_budget(
        db,
        auth,
        settings=effective_settings,
        project_id=project_id,
        definition=definition,
        research_sprint_id=research_sprint_id,
        requested_by=requested_by,
    )
    policy_decision = _authorize_opa_tool_invocation(
        db,
        auth,
        effective_settings,
        project,
        definition,
        requested_by=requested_by,
        research_sprint_id=research_sprint_id,
    )
    clean_input = redact_payload(guarded_input, redact_emails=True)
    clean_proposal = redact_payload(guarded_proposal, redact_emails=True)
    _enforce_repeated_tool_invocation_limit(
        db,
        auth,
        effective_settings,
        project_id=project_id,
        definition=definition,
        input_json=clean_input,
        proposal=clean_proposal,
        research_sprint_id=research_sprint_id,
        requested_by=requested_by,
    )
    invocation = ToolInvocation(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        research_sprint_id=research_sprint_id,
        tool_name=definition.name,
        access_mode=definition.access_mode,
        risk_level=definition.risk_level,
        input_json=clean_input,
        output_json={"proposal": clean_proposal},
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
            policy_decision=_opa_decision_metadata(policy_decision),
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
    settings: Settings,
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
    if invocation.idempotency_key is not None and invocation.access_mode == "write":
        if invocation.remote_mcp_server_id is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The remote MCP write target is no longer available.",
            )
        return _approve_and_execute_remote_write(db, auth, settings, invocation)
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


def _approve_and_execute_remote_write(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    invocation: ToolInvocation,
) -> ToolInvocation:
    if invocation.status != "requested" or invocation.idempotency_key is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending remote write requests can be approved.",
        )
    definition = _definition(invocation.tool_name)
    project = project_service.get_project(db, auth, invocation.project_id)
    _enforce_agent_write_kill_switch(
        db,
        auth,
        settings,
        project_id=invocation.project_id,
        definition=definition,
        requested_by=invocation.requested_by,
    )
    _authorize_opa_tool_invocation(
        db,
        auth,
        settings,
        project,
        definition,
        requested_by=invocation.requested_by,
        research_sprint_id=invocation.research_sprint_id,
        allow_required_approval=True,
    )
    from app.services import mcp_registry_service

    mcp_registry_service.prepare_remote_write_request(
        db,
        auth,
        settings,
        project_id=invocation.project_id,
        registration_id=invocation.remote_mcp_server_id,
        tool_name=invocation.tool_name,
    )
    invocation.status = "approved"
    invocation.approved_by_user_id = auth.user_id
    governance_service.resolve_pending_approvals_for_entity(
        db,
        auth,
        project_id=invocation.project_id,
        entity_type="tool_invocation",
        entity_id=invocation.id,
        status_value="approved",
    )
    governance_service.record_audit_event(
        db,
        auth,
        event_type="tool_invocation_approved",
        actor_type="user",
        project_id=invocation.project_id,
        entity_type="tool_invocation",
        entity_id=invocation.id,
        risk_level=invocation.risk_level,
        summary=f"Approved remote write {invocation.tool_name} for execution.",
        metadata=_tool_invocation_status_metadata(invocation.tool_name, "approved"),
    )
    db.commit()

    try:
        output = mcp_registry_service.invoke_approved_write_tool(
            db,
            auth,
            settings,
            project_id=invocation.project_id,
            invocation_id=invocation.id,
            registration_id=invocation.remote_mcp_server_id,
            tool_name=invocation.tool_name,
            arguments=invocation.input_json,
            idempotency_key=invocation.idempotency_key,
        )
        _guard_tool_output(definition, output)
        _guard_tool_manifest_output(definition, output)
    except Exception:
        invocation.status = "failed"
        invocation.output_summary = "Approved remote write did not complete."
        invocation.executed_at = datetime.now(UTC)
        governance_service.record_audit_event(
            db,
            auth,
            event_type="tool_invocation_failed",
            actor_type="user",
            project_id=invocation.project_id,
            entity_type="tool_invocation",
            entity_id=invocation.id,
            risk_level=invocation.risk_level,
            summary=f"Approved remote write {invocation.tool_name} failed.",
            metadata=_tool_invocation_status_metadata(invocation.tool_name, "failed"),
        )
        db.commit()
        raise

    invocation.status = "executed"
    invocation.output_json = redact_payload(output, redact_emails=True)
    invocation.output_summary = redact_text(
        _summarize_output(definition.name, output),
        redact_emails=True,
    )
    invocation.executed_at = datetime.now(UTC)
    governance_service.record_audit_event(
        db,
        auth,
        event_type="tool_invocation_executed",
        actor_type="user",
        project_id=invocation.project_id,
        entity_type="tool_invocation",
        entity_id=invocation.id,
        risk_level=invocation.risk_level,
        summary=f"Executed approved remote write {invocation.tool_name}.",
        metadata=_tool_invocation_executed_metadata(definition),
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


def _enforce_workflow_tool_budget(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    *,
    project_id: uuid.UUID,
    research_sprint_id: uuid.UUID | None,
    requested_by: RequestedBy,
) -> None:
    budget_context = _workflow_security_budget(
        db,
        auth,
        settings,
        project_id=project_id,
        research_sprint_id=research_sprint_id,
    )
    if budget_context is None:
        return
    sprint, budget = budget_context
    observed_tool_calls = int(
        db.scalar(
            select(func.count())
            .select_from(ToolInvocation)
            .where(
                ToolInvocation.workspace_id == auth.workspace_id,
                ToolInvocation.project_id == project_id,
                ToolInvocation.research_sprint_id == research_sprint_id,
            )
        )
        or 0
    )
    if observed_tool_calls < budget.max_tool_calls:
        return

    governance_service.record_audit_event(
        db,
        auth,
        event_type="workflow_tool_budget_exceeded",
        actor_type=requested_by,
        project_id=project_id,
        entity_type="research_sprint",
        entity_id=research_sprint_id,
        risk_level="high",
        summary="Workflow tool-call budget was exhausted before tool execution.",
        metadata={
            "max_tool_calls": budget.max_tool_calls,
            "observed_tool_calls": observed_tool_calls,
            "temporal_workflow_id": sprint.temporal_workflow_id,
        },
    )
    db.commit()
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=WORKFLOW_BUDGET_EXHAUSTED_DETAIL,
    )


def _workflow_security_budget(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    *,
    project_id: uuid.UUID,
    research_sprint_id: uuid.UUID | None,
) -> tuple[ResearchSprint, WorkflowSecurityBudget] | None:
    if research_sprint_id is None:
        return None
    sprint = db.scalar(
        select(ResearchSprint)
        .where(
            ResearchSprint.id == research_sprint_id,
            ResearchSprint.workspace_id == auth.workspace_id,
            ResearchSprint.project_id == project_id,
        )
        .with_for_update()
    )
    if sprint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research sprint not found.",
        )
    if not sprint.workflow_security_budget:
        sprint.workflow_security_budget = WorkflowSecurityBudget.from_settings(
            settings
        ).as_payload()
        db.flush()
    return sprint, WorkflowSecurityBudget.from_payload(sprint.workflow_security_budget)


def _enforce_repeated_tool_invocation_limit(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    *,
    project_id: uuid.UUID,
    definition: ToolDefinition,
    input_json: dict[str, Any],
    research_sprint_id: uuid.UUID | None,
    requested_by: RequestedBy,
    proposal: dict[str, Any] | None = None,
) -> None:
    budget_context = _workflow_security_budget(
        db,
        auth,
        settings,
        project_id=project_id,
        research_sprint_id=research_sprint_id,
    )
    if budget_context is None:
        return
    sprint, budget = budget_context
    candidate_digest = _tool_invocation_input_digest(input_json, proposal=proposal)
    existing_invocations = db.execute(
        select(ToolInvocation.input_json, ToolInvocation.output_json).where(
            ToolInvocation.workspace_id == auth.workspace_id,
            ToolInvocation.project_id == project_id,
            ToolInvocation.research_sprint_id == research_sprint_id,
            ToolInvocation.tool_name == definition.name,
        )
    )
    observed_identical_invocations = sum(
        _tool_invocation_input_digest(
            stored_input,
            proposal=_stored_tool_proposal(stored_output) if proposal is not None else None,
        )
        == candidate_digest
        for stored_input, stored_output in existing_invocations
    )
    if observed_identical_invocations < budget.max_identical_tool_invocations:
        return

    governance_service.record_audit_event(
        db,
        auth,
        event_type="workflow_repeated_tool_invocation_detected",
        actor_type=requested_by,
        project_id=project_id,
        entity_type="research_sprint",
        entity_id=research_sprint_id,
        risk_level="high",
        summary="Workflow stopped before repeating an identical tool invocation.",
        metadata={
            "tool_name": definition.name,
            "input_sha256": candidate_digest,
            "max_identical_tool_invocations": budget.max_identical_tool_invocations,
            "observed_identical_invocations": observed_identical_invocations,
            "temporal_workflow_id": sprint.temporal_workflow_id,
        },
    )
    db.commit()
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=WORKFLOW_BUDGET_EXHAUSTED_DETAIL,
    )


def _tool_invocation_input_digest(
    input_json: dict[str, Any],
    *,
    proposal: dict[str, Any] | None = None,
) -> str:
    payload: dict[str, Any] = {"input": input_json}
    if proposal is not None:
        payload["proposal"] = proposal
    canonical_payload = json.dumps(
        payload,
        default=str,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def _stored_tool_proposal(output_json: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(output_json, dict):
        return None
    proposal = output_json.get("proposal")
    return proposal if isinstance(proposal, dict) else None


def _enforce_workflow_memory_proposal_budget(
    db: Session,
    auth: AuthContext,
    *,
    settings: Settings,
    project_id: uuid.UUID,
    definition: ToolDefinition,
    research_sprint_id: uuid.UUID | None,
    requested_by: RequestedBy,
) -> None:
    if definition.name != "propose_memory_update":
        return
    budget_context = _workflow_security_budget(
        db,
        auth,
        settings,
        project_id=project_id,
        research_sprint_id=research_sprint_id,
    )
    if budget_context is None:
        return
    sprint, budget = budget_context
    observed_memory_proposals = int(
        db.scalar(
            select(func.count())
            .select_from(ToolInvocation)
            .where(
                ToolInvocation.workspace_id == auth.workspace_id,
                ToolInvocation.project_id == project_id,
                ToolInvocation.research_sprint_id == research_sprint_id,
                ToolInvocation.tool_name == definition.name,
            )
        )
        or 0
    )
    if observed_memory_proposals < budget.max_memory_proposals:
        return
    governance_service.record_audit_event(
        db,
        auth,
        event_type="workflow_memory_proposal_budget_exceeded",
        actor_type=requested_by,
        project_id=project_id,
        entity_type="research_sprint",
        entity_id=research_sprint_id,
        risk_level="high",
        summary="Workflow memory-proposal budget was exhausted before proposal creation.",
        metadata={
            "max_memory_proposals": budget.max_memory_proposals,
            "observed_memory_proposals": observed_memory_proposals,
            "temporal_workflow_id": sprint.temporal_workflow_id,
        },
    )
    db.commit()
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=WORKFLOW_BUDGET_EXHAUSTED_DETAIL,
    )


def _cap_workflow_retrieval_input(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    *,
    project_id: uuid.UUID,
    definition: ToolDefinition,
    tool_input: dict[str, Any],
    research_sprint_id: uuid.UUID | None,
    requested_by: RequestedBy,
) -> tuple[dict[str, Any], int | None]:
    if definition.name != "search_project_evidence" or research_sprint_id is None:
        return tool_input, None

    budget_context = _workflow_security_budget(
        db,
        auth,
        settings,
        project_id=project_id,
        research_sprint_id=research_sprint_id,
    )
    assert budget_context is not None
    sprint, budget = budget_context
    observed_retrieved_chunks = sum(
        _retrieved_chunk_count(output)
        for output in db.scalars(
            select(ToolInvocation.output_json).where(
                ToolInvocation.workspace_id == auth.workspace_id,
                ToolInvocation.project_id == project_id,
                ToolInvocation.research_sprint_id == research_sprint_id,
                ToolInvocation.tool_name == definition.name,
            )
        )
    )
    if observed_retrieved_chunks >= budget.max_retrieved_chunks:
        governance_service.record_audit_event(
            db,
            auth,
            event_type="workflow_retrieved_chunk_budget_exceeded",
            actor_type=requested_by,
            project_id=project_id,
            entity_type="research_sprint",
            entity_id=research_sprint_id,
            risk_level="high",
            summary="Workflow retrieved-chunk budget was exhausted before retrieval.",
            metadata={
                "max_retrieved_chunks": budget.max_retrieved_chunks,
                "observed_retrieved_chunks": observed_retrieved_chunks,
                "temporal_workflow_id": sprint.temporal_workflow_id,
            },
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=WORKFLOW_BUDGET_EXHAUSTED_DETAIL,
        )
    remaining_chunks = budget.max_retrieved_chunks - observed_retrieved_chunks
    requested_top_k = int(tool_input.get("top_k", 8))
    return {**tool_input, "top_k": min(requested_top_k, remaining_chunks)}, remaining_chunks


def _limit_retrieved_chunk_output(
    definition: ToolDefinition,
    output: dict[str, Any],
    maximum_chunks: int | None,
) -> dict[str, Any]:
    if maximum_chunks is None or definition.name != "search_project_evidence":
        return output
    results = output.get("results")
    if not isinstance(results, list):
        return output
    return {**output, "results": results[:maximum_chunks]}


def _retrieved_chunk_count(output: dict[str, Any] | None) -> int:
    if not isinstance(output, dict):
        return 0
    results = output.get("results")
    return len(results) if isinstance(results, list) else 0


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
    *,
    invocation_id: uuid.UUID,
    remote_mcp_server_id: uuid.UUID | None,
) -> dict[str, Any]:
    if remote_mcp_server_id is not None:
        from app.services import mcp_registry_service

        return mcp_registry_service.invoke_tool(
            db,
            auth,
            settings,
            project_id=project_id,
            invocation_id=invocation_id,
            registration_id=remote_mcp_server_id,
            tool_name=definition.name,
            arguments=tool_input,
        )
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
_guard_tool_manifest_input = schema_guard.guard_tool_manifest_input
_guard_tool_manifest_output = schema_guard.guard_tool_manifest_output
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


def _enforce_agent_write_kill_switch(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    *,
    project_id: uuid.UUID,
    definition: ToolDefinition,
    requested_by: RequestedBy,
) -> None:
    if requested_by == "agent" and definition.access_mode != "read":
        security_policy_service.enforce_agent_writes_allowed(
            db,
            auth,
            settings,
            project_id=project_id,
            operation=definition.name,
        )


def _authorize_opa_tool_invocation(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project: Any,
    definition: ToolDefinition,
    *,
    requested_by: RequestedBy,
    research_sprint_id: uuid.UUID | None,
    allow_required_approval: bool = False,
) -> OpaPolicyDecision | None:
    """Evaluate tool policy after deterministic scope and schema guards pass."""
    if not opa_policy_enforced(settings):
        return None

    policy_input = {
        "principal": {
            "user_id": str(auth.user_id),
            "workspace_id": str(auth.workspace_id),
            "role": normalized_role(auth.role),
            "authentication_method": auth.principal.authentication_method,
        },
        "project": {
            "id": str(project.id),
            "workspace_id": str(project.workspace_id),
        },
        "tool": {
            "name": definition.name,
            "version": definition.version,
            "access_mode": definition.access_mode,
            "risk_level": definition.risk_level,
            "approval_policy": definition.approval_policy,
            "required_scopes": list(definition.required_scopes),
            "allowed_data_classifications": list(definition.allowed_data_classifications),
            "allowed_network_destinations": list(definition.allowed_network_destinations),
            "timeout_seconds": definition.timeout_seconds,
            "max_output_bytes": definition.max_output_bytes,
            "max_affected_records": definition.max_affected_records,
            "reversible": definition.reversible,
            "owner": definition.owner,
        },
        "request": {
            "requested_by": requested_by,
            "research_sprint_id": (
                str(research_sprint_id) if research_sprint_id is not None else None
            ),
        },
    }
    try:
        decision = OpaPolicyClient(settings).evaluate("tool_access", policy_input)
    except OpaPolicyUnavailableError as exc:
        denial = unavailable_opa_policy_denial(exc)
        _audit_tool_denial(
            db,
            auth,
            project.id,
            definition,
            "opa_policy_unavailable",
            detail=denial.detail,
        )
        db.commit()
        raise denial from exc
    try:
        approved_decision = require_opa_decision(decision)
    except HTTPException as exc:
        _audit_tool_denial(
            db,
            auth,
            project.id,
            definition,
            "opa_policy_denied",
            detail=str(exc.detail),
            policy_decision=_opa_decision_metadata(decision),
        )
        db.commit()
        raise
    if (
        approved_decision.requires_approval
        and definition.access_mode != "proposal"
        and not allow_required_approval
    ):
        detail = "Policy requires approval before this tool can execute."
        _audit_tool_denial(
            db,
            auth,
            project.id,
            definition,
            "opa_approval_required",
            detail=detail,
            policy_decision=_opa_decision_metadata(approved_decision),
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    return approved_decision


def _audit_tool_denial(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    definition: ToolDefinition,
    reason: str,
    *,
    detail: str | None = None,
    policy_decision: dict[str, Any] | None = None,
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
            policy_decision=policy_decision,
        ),
    )


def _opa_decision_metadata(decision: OpaPolicyDecision | None) -> dict[str, Any] | None:
    if decision is None:
        return None
    return {
        "allow": decision.allow,
        "requires_approval": decision.requires_approval,
        "reason": decision.reason,
        "allowed_scopes": list(decision.allowed_scopes),
        "max_records": decision.max_records,
    }


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
        select(ToolInvocation)
        .where(
            ToolInvocation.id == invocation_id,
            ToolInvocation.workspace_id == auth.workspace_id,
            ToolInvocation.project_id == project_id,
        )
        .with_for_update()
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
