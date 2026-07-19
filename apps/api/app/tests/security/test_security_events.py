import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.db.models import AuditEvent, SecurityEvent
from app.services import governance_service, security_event_service
from app.services.identity_service import ensure_dev_identity


def test_high_risk_audit_event_creates_redacted_normalized_security_event(
    client: TestClient,
    db_session: Session,
) -> None:
    project = client.post("/api/projects", json={"name": "Security events"}).json()
    project_id = uuid.UUID(project["id"])
    auth = ensure_dev_identity(
        db_session,
        email="dev@thesys.local",
        display_name="Dev User",
    )

    audit = governance_service.record_audit_event(
        db_session,
        auth,
        event_type="mcp_server_review_failed",
        actor_type="user",
        project_id=project_id,
        risk_level="high",
        summary="MCP review included operator@example.com.",
        metadata={
            "authorization": "Bearer sensitive-token",
            "langsmith_trace_id": "trace-123",
            "request_id": "request-456",
        },
    )
    db_session.commit()

    event = db_session.scalar(select(SecurityEvent).where(SecurityEvent.audit_event_id == audit.id))

    assert event is not None
    assert event.workspace_id == auth.workspace_id
    assert event.project_id == project_id
    assert event.event_type == "mcp_server_review_failed"
    assert event.severity == "high"
    assert event.source == "mcp"
    assert event.langsmith_trace_id == "trace-123"
    assert event.request_id == "request-456"
    assert event.attributes["authorization"] == "[redacted]"
    assert "operator@example.com" not in event.summary
    assert event.attributes["audit_event_id"] == str(audit.id)
    assert db_session.get(AuditEvent, audit.id) is not None

    response = client.get(f"/api/projects/{project_id}/security-events")

    assert response.status_code == 200
    assert response.json()["events"] == [
        {
            "id": str(event.id),
            "project_id": str(project_id),
            "user_id": str(auth.user_id),
            "audit_event_id": str(audit.id),
            "ai_run_id": None,
            "tool_invocation_id": None,
            "approval_request_id": None,
            "session_id": None,
            "request_id": "request-456",
            "langsmith_trace_id": "trace-123",
            "temporal_workflow_id": None,
            "event_type": "mcp_server_review_failed",
            "severity": "high",
            "source": "mcp",
            "summary": "MCP review included [redacted-email].",
            "attributes": {
                "authorization": "[redacted]",
                "langsmith_trace_id": "trace-123",
                "request_id": "request-456",
                "audit_event_id": str(audit.id),
                "risk_level": "high",
                "entity_type": None,
                "entity_id": None,
            },
            "detected_at": event.detected_at.isoformat().replace("+00:00", "Z"),
            "containment_status": None,
        }
    ]


def test_security_event_query_requires_workspace_security_admin(
    client: TestClient,
    db_session: Session,
) -> None:
    project = client.post("/api/projects", json={"name": "Security role"}).json()
    project_id = uuid.UUID(project["id"])
    owner = ensure_dev_identity(
        db_session,
        email="dev@thesys.local",
        display_name="Dev User",
    )
    viewer = AuthContext.from_identity(
        user=owner.user,
        workspace=owner.workspace,
        role="viewer",
        authentication_method="dev",
    )

    with pytest.raises(HTTPException) as exc_info:
        security_event_service.list_project_security_events(db_session, viewer, project_id)

    assert exc_info.value.status_code == 403
