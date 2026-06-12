import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import ApprovalRequest, AuditEvent, ToolInvocation
from app.services import tool_service
from app.services.identity_service import ensure_dev_identity


def test_role_permissions_block_viewer_research_and_admin_delete(
    client: TestClient,
) -> None:
    project_id = _create_project(client)

    viewer_plan_response = client.post(
        f"/api/projects/{project_id}/research-sprints/plan",
        headers={"X-Dev-User-Role": "viewer"},
        json={"objective": "Investigate the market."},
    )
    assert viewer_plan_response.status_code == 403

    admin_delete_response = client.delete(
        f"/api/projects/{project_id}",
        headers={"X-Dev-User-Role": "admin"},
    )
    assert admin_delete_response.status_code == 403

    owner_delete_response = client.delete(
        f"/api/projects/{project_id}",
        headers={"X-Dev-User-Role": "owner"},
    )
    assert owner_delete_response.status_code == 204


def test_tool_denial_is_audited_and_persisted_proposals_are_redacted(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    secret = "sk-testsecret123456789"
    bearer = "Bearer abcdefghijklmnopqrstuvwxyz0123456789"

    viewer_auth = _dev_auth(db_session, "viewer")
    with pytest.raises(HTTPException) as exc_info:
        tool_service.create_proposal(
            db_session,
            viewer_auth,
            project_id,
            "propose_memory_update",
            {
                "summary": "Update project memory",
                "api_key": secret,
                "contact": "founder@example.com",
            },
        )
    assert exc_info.value.status_code == 403

    denial = db_session.scalar(
        select(AuditEvent).where(AuditEvent.event_type == "tool_invocation_denied")
    )
    assert denial is not None
    assert denial.risk_level == "medium"
    assert denial.event_metadata["role"] == "viewer"

    owner_auth = _dev_auth(db_session, "owner")
    invocation = tool_service.create_proposal(
        db_session,
        owner_auth,
        project_id,
        "propose_memory_update",
        {
            "summary": f"Use {secret} for founder@example.com",
            "api_key": secret,
            "notes": f"Authorization: {bearer} contact founder@example.com",
        },
        input_json={"Authorization": bearer},
    )

    db_session.refresh(invocation)
    approval = db_session.scalar(
        select(ApprovalRequest).where(ApprovalRequest.entity_id == invocation.id)
    )
    assert approval is not None
    persisted_text = f"{invocation.input_json} {invocation.output_json} {approval.proposed_change}"
    assert secret not in persisted_text
    assert bearer not in persisted_text
    assert "founder@example.com" not in persisted_text
    assert "[redacted]" in persisted_text


def test_high_risk_tool_approval_requires_admin_or_owner(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    owner_auth = _dev_auth(db_session, "owner")
    invocation = tool_service.create_proposal(
        db_session,
        owner_auth,
        project_id,
        "propose_decision",
        {
            "summary": "Record a kill decision.",
            "decision_type": "kill",
            "title": "Kill the idea",
            "rationale": "The evidence does not support the wedge.",
        },
    )
    approval = db_session.scalar(
        select(ApprovalRequest).where(ApprovalRequest.entity_id == invocation.id)
    )
    assert approval is not None
    assert approval.request_type == "decision"
    assert approval.risk_level == "high"

    editor_response = client.post(
        f"/api/projects/{project_id}/approvals/{approval.id}/approve",
        headers={"X-Dev-User-Role": "editor"},
    )
    assert editor_response.status_code == 403
    db_session.refresh(invocation)
    assert invocation.status == "requested"

    admin_response = client.post(
        f"/api/projects/{project_id}/approvals/{approval.id}/approve",
        headers={"X-Dev-User-Role": "admin"},
    )
    assert admin_response.status_code == 200
    db_session.refresh(invocation)
    db_session.refresh(approval)
    assert invocation.status == "approved"
    assert approval.status == "approved"


def test_research_plan_creates_approval_request_and_audit_events(
    client: TestClient,
) -> None:
    project_id = _create_project(client)

    plan_response = client.post(
        f"/api/projects/{project_id}/research-sprints/plan",
        headers={"X-Dev-User-Role": "owner"},
        json={"objective": "Evaluate competitor pressure and validation risks."},
    )
    assert plan_response.status_code == 200

    approvals_response = client.get(
        f"/api/projects/{project_id}/approvals",
        headers={"X-Dev-User-Role": "owner"},
        params={"status_filter": "pending"},
    )
    assert approvals_response.status_code == 200
    approvals = approvals_response.json()["approvals"]
    assert any(approval["request_type"] == "research_plan" for approval in approvals)

    audit_response = client.get(
        f"/api/projects/{project_id}/audit-events",
        headers={"X-Dev-User-Role": "owner"},
    )
    assert audit_response.status_code == 200
    event_types = {event["event_type"] for event in audit_response.json()["events"]}
    assert "research_sprint_started" in event_types
    assert "tool_invocation_requested" in event_types


def test_tool_input_guard_rejects_unsupported_fields_and_audits_denial(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    owner_auth = _dev_auth(db_session, "owner")

    with pytest.raises(HTTPException) as exc_info:
        tool_service.execute_tool(
            db_session,
            owner_auth,
            get_settings(),
            project_id,
            "list_assumptions",
            {"query": "ignored by this read tool"},
            requested_by="agent",
        )

    assert exc_info.value.status_code == 422
    assert db_session.scalar(
        select(ToolInvocation).where(ToolInvocation.tool_name == "list_assumptions")
    ) is None
    denial = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "tool_invocation_denied")
        .order_by(AuditEvent.created_at.desc())
    )
    assert denial is not None
    assert denial.event_metadata["reason"] == "input_guard_failed"
    assert "unsupported field" in denial.event_metadata["detail"]


def test_tool_scope_guard_rejects_conflicting_research_sprint_ids(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    owner_auth = _dev_auth(db_session, "owner")
    scoped_sprint_id = uuid.uuid4()
    other_sprint_id = uuid.uuid4()

    with pytest.raises(HTTPException) as exc_info:
        tool_service.execute_tool(
            db_session,
            owner_auth,
            get_settings(),
            project_id,
            "get_research_memo",
            {"research_sprint_id": str(other_sprint_id)},
            research_sprint_id=scoped_sprint_id,
            requested_by="agent",
        )

    assert exc_info.value.status_code == 422
    denial = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "tool_invocation_denied")
        .order_by(AuditEvent.created_at.desc())
    )
    assert denial is not None
    assert denial.event_metadata["reason"] == "scope_guard_failed"


def test_scoped_proposal_guard_requires_matching_research_sprint_id(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    owner_auth = _dev_auth(db_session, "owner")

    with pytest.raises(HTTPException) as exc_info:
        tool_service.create_proposal(
            db_session,
            owner_auth,
            project_id,
            "propose_memory_update",
            {"summary": "Missing scoped sprint id."},
            research_sprint_id=uuid.uuid4(),
            requested_by="agent",
        )

    assert exc_info.value.status_code == 422
    denial = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "tool_invocation_denied")
        .order_by(AuditEvent.created_at.desc())
    )
    assert denial is not None
    assert denial.event_metadata["reason"] == "scope_guard_failed"


def _create_project(client: TestClient) -> str:
    response = client.post(
        "/api/projects",
        headers={"X-Dev-User-Role": "owner"},
        json={
            "name": "Governed research workspace",
            "short_description": "AI workspace for governed founder research.",
            "initial_thesis": "Founders need evidence before committing to a wedge.",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _dev_auth(db_session: Session, role: str):
    settings = get_settings()
    return ensure_dev_identity(
        db_session,
        email=settings.dev_auth_default_email,
        display_name=settings.dev_auth_default_name,
        role=role,
    )
