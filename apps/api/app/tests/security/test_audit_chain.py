import subprocess
import sys
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import AuditEvent
from app.services import audit_chain_service, governance_service
from app.services.identity_service import ensure_dev_identity

REPO_ROOT = Path(__file__).resolve().parents[5]


def test_audit_events_form_a_per_workspace_tamper_evident_chain(
    client: TestClient,
    db_session: Session,
) -> None:
    project = client.post("/api/projects", json={"name": "Audit chain"}).json()
    project_id = uuid.UUID(project["id"])
    auth = ensure_dev_identity(
        db_session,
        email="dev@thesys.local",
        display_name="Dev User",
    )

    first = governance_service.record_audit_event(
        db_session,
        auth,
        event_type="security_policy_denied",
        actor_type="user",
        project_id=project_id,
        summary="Denied an unsafe external request.",
    )
    second = governance_service.record_audit_event(
        db_session,
        auth,
        event_type="tool_invocation_executed",
        actor_type="agent",
        project_id=project_id,
        entity_type="tool_invocation",
        entity_id=uuid.uuid4(),
        summary="Recorded a tool invocation.",
    )
    db_session.commit()

    assert first.previous_event_hash is None
    assert first.event_hash == audit_chain_service.calculate_event_hash(first, None)
    assert second.previous_event_hash == first.event_hash
    assert second.event_hash == audit_chain_service.calculate_event_hash(second, first.event_hash)
    assert first.actor_identity == f"user:{auth.user_id}"
    assert first.policy_decision == "denied"
    assert first.resource_identifier == f"project:{project_id}"
    assert second.actor_identity == "agent:service"
    assert second.policy_decision == "recorded"
    assert second.resource_identifier.startswith("tool_invocation:")

    results = audit_chain_service.verify_audit_chains(db_session, workspace_id=auth.workspace_id)

    assert results == [
        audit_chain_service.AuditChainVerificationResult(
            workspace_id=auth.workspace_id,
            event_count=2,
            valid=True,
        )
    ]


def test_audit_chain_verifier_detects_event_mutation(
    client: TestClient,
    db_session: Session,
) -> None:
    project = client.post("/api/projects", json={"name": "Audit tampering"}).json()
    project_id = uuid.UUID(project["id"])
    auth = ensure_dev_identity(
        db_session,
        email="dev@thesys.local",
        display_name="Dev User",
    )
    event = governance_service.record_audit_event(
        db_session,
        auth,
        event_type="project_created",
        actor_type="user",
        project_id=project_id,
        summary="Created a project.",
    )
    db_session.commit()

    db_session.execute(
        AuditEvent.__table__.update()
        .where(AuditEvent.id == event.id)
        .values(summary="Modified audit record.")
    )
    db_session.commit()

    results = audit_chain_service.verify_audit_chains(db_session, workspace_id=auth.workspace_id)

    assert len(results) == 1
    assert results[0].valid is False
    assert results[0].error == f"event {event.id} hash does not match its content"


def test_verify_audit_chain_script_exposes_a_standalone_command() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verify_audit_chain.py", "--help"],
        cwd=REPO_ROOT / "apps/api",
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Verify the tamper-evident audit chain" in result.stdout
    assert "--workspace-id" in result.stdout
