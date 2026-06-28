import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import ApprovalRequest, Assumption, AuditEvent, ToolInvocation
from app.services import tool_service
from app.services.evidence_service import ParsedSource
from app.services.identity_service import ensure_dev_identity

REQUIRED_READ_TOOLS = {
    "get_project_summary",
    "search_project_evidence",
    "list_project_sources",
    "list_competitors",
    "list_assumptions",
    "list_validation_plans",
    "list_decisions",
    "get_research_memo",
}
REQUIRED_PROPOSAL_TOOLS = {
    "propose_research_plan",
    "propose_memory_update",
    "propose_validation_plan",
    "propose_decision",
}


def test_tool_registry_exposes_mcp_style_contracts(client: TestClient) -> None:
    response = client.get("/api/tools")

    assert response.status_code == 200
    tools = {tool["name"]: tool for tool in response.json()["tools"]}
    assert REQUIRED_READ_TOOLS.issubset(tools)
    assert REQUIRED_PROPOSAL_TOOLS.issubset(tools)
    assert len([tool for tool in tools.values() if tool["access_mode"] == "read"]) >= 8
    assert len([tool for tool in tools.values() if tool["access_mode"] == "proposal"]) >= 3
    assert tools["search_project_evidence"]["approval_policy"] == "never_required"
    assert tools["propose_memory_update"]["approval_policy"] == "always_required"
    assert tools["propose_memory_update"]["risk_level"] == "medium"


def test_read_tools_return_declared_output_schema_keys(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = uuid.UUID(_create_project(client))
    auth = _dev_auth(db_session)
    tool_inputs = {
        "search_project_evidence": {"query": "pricing", "top_k": 3},
        "get_research_memo": {},
        "list_project_memory": {"limit": 5},
    }

    for definition in tool_service.list_tool_definitions():
        if definition.access_mode != "read":
            continue
        result = tool_service.execute_tool(
            db_session,
            auth,
            get_settings(),
            project_id,
            definition.name,
            tool_inputs.get(definition.name, {}),
            requested_by="agent",
        )
        expected_keys = set(definition.output_schema.get("properties", {}))

        assert expected_keys, f"{definition.name} must declare output properties"
        assert expected_keys.issubset(result.output), definition.name


def test_research_plan_proposal_is_audited_and_approvable(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = _create_project(client)

    plan_response = client.post(
        f"/api/projects/{project_id}/research-sprints/plan",
        json={"objective": "Investigate the market and validation risks."},
    )
    assert plan_response.status_code == 200
    sprint_id = plan_response.json()["sprint"]["id"]

    activity_response = client.get(
        f"/api/projects/{project_id}/tool-invocations",
        params={"research_sprint_id": sprint_id},
    )

    assert activity_response.status_code == 200
    invocations = activity_response.json()["invocations"]
    proposal = next(item for item in invocations if item["tool_name"] == "propose_research_plan")
    assert proposal["access_mode"] == "proposal"
    assert proposal["status"] == "requested"
    assert proposal["requested_by"] == "agent"
    assert proposal["output_json"]["proposal"]["research_sprint_id"] == sprint_id

    approve_response = client.post(
        f"/api/projects/{project_id}/tool-invocations/{proposal['id']}/approve"
    )

    assert approve_response.status_code == 200
    approved = approve_response.json()["invocation"]
    assert approved["status"] == "approved"
    assert approved["approved_by_user_id"] is not None
    stored = db_session.scalar(
        select(ToolInvocation).where(ToolInvocation.id == uuid.UUID(proposal["id"]))
    )
    assert stored is not None
    assert stored.status == "approved"


def test_tool_proposal_rejection_resolves_approval_and_writes_audit_event(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = _create_project(client)

    plan_response = client.post(
        f"/api/projects/{project_id}/research-sprints/plan",
        json={"objective": "Investigate customer pain before building."},
    )
    assert plan_response.status_code == 200
    sprint_id = plan_response.json()["sprint"]["id"]

    activity_response = client.get(
        f"/api/projects/{project_id}/tool-invocations",
        params={"research_sprint_id": sprint_id},
    )
    assert activity_response.status_code == 200
    proposal = next(
        item
        for item in activity_response.json()["invocations"]
        if item["tool_name"] == "propose_research_plan"
    )
    invocation_id = uuid.UUID(proposal["id"])
    approval = db_session.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.entity_type == "tool_invocation",
            ApprovalRequest.entity_id == invocation_id,
        )
    )
    assert approval is not None
    assert approval.status == "pending"
    assert approval.proposed_change["tool_name"] == "propose_research_plan"
    assert approval.proposed_change["tool_invocation_id"] == str(invocation_id)
    assert approval.proposed_change["proposal"]["research_sprint_id"] == sprint_id

    reject_response = client.post(
        f"/api/projects/{project_id}/approvals/{approval.id}/reject"
    )

    assert reject_response.status_code == 200
    assert reject_response.json()["approval"]["status"] == "rejected"
    stored_invocation = db_session.scalar(
        select(ToolInvocation).where(ToolInvocation.id == invocation_id)
    )
    assert stored_invocation is not None
    assert stored_invocation.status == "rejected"
    assert stored_invocation.approved_by_user_id is None
    db_session.refresh(approval)
    assert approval.status == "rejected"
    assert approval.resolved_at is not None
    audit_event = db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.event_type == "tool_invocation_denied",
            AuditEvent.entity_type == "tool_invocation",
            AuditEvent.entity_id == invocation_id,
        )
    )
    assert audit_event is not None
    assert audit_event.risk_level == "medium"
    assert audit_event.event_metadata == {
        "tool_name": "propose_research_plan",
        "status": "rejected",
    }


def test_agentic_research_tools_audit_reads_and_gate_memory_updates(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    project_id, sprint_id = _approved_research_sprint_with_evidence(client, monkeypatch)

    run_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/agentic-rag/run"
    )

    assert run_response.status_code == 200
    assert db_session.scalar(select(Assumption)) is None
    activity_response = client.get(
        f"/api/projects/{project_id}/tool-invocations",
        params={"research_sprint_id": sprint_id},
    )
    assert activity_response.status_code == 200
    invocations = activity_response.json()["invocations"]
    names = {item["tool_name"] for item in invocations}
    assert REQUIRED_READ_TOOLS.issubset(names)
    assert {"propose_memory_update", "propose_validation_plan", "propose_decision"}.issubset(
        names
    )
    assert all(
        item["status"] == "executed"
        for item in invocations
        if item["access_mode"] == "read"
    )
    pending_proposals = [
        item
        for item in invocations
        if item["tool_name"]
        in {"propose_memory_update", "propose_validation_plan", "propose_decision"}
    ]
    assert pending_proposals
    assert {item["status"] for item in pending_proposals} == {"requested"}

    approve_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/agentic-rag/approve"
    )

    assert approve_response.status_code == 200
    assert db_session.scalar(select(Assumption)) is not None
    approved_activity_response = client.get(
        f"/api/projects/{project_id}/tool-invocations",
        params={"research_sprint_id": sprint_id},
    )
    assert approved_activity_response.status_code == 200
    approved_proposals = [
        item
        for item in approved_activity_response.json()["invocations"]
        if item["tool_name"]
        in {"propose_memory_update", "propose_validation_plan", "propose_decision"}
    ]
    assert {item["status"] for item in approved_proposals} == {"approved"}


def _create_project(client: TestClient) -> str:
    project_response = client.post(
        "/api/projects",
        json={
            "name": "Fitness coach OS",
            "short_description": "AI workspace for independent fitness coaches.",
            "initial_thesis": "Coaches need faster check-in synthesis before client calls.",
        },
    )
    assert project_response.status_code == 201
    return project_response.json()["id"]


def _dev_auth(db_session: Session):
    settings = get_settings()
    return ensure_dev_identity(
        db_session,
        email=settings.dev_auth_default_email,
        display_name=settings.dev_auth_default_name,
        role="owner",
    )


def _approved_research_sprint_with_evidence(
    client: TestClient,
    monkeypatch,
) -> tuple[str, str]:
    project_id = _create_project(client)
    plan_response = client.post(
        f"/api/projects/{project_id}/research-sprints/plan",
        json={
            "objective": (
                "Investigate competitors, substitutes, customer pain, and validation "
                "risks for online fitness coaches."
            )
        },
    )
    assert plan_response.status_code == 200
    sprint_id = plan_response.json()["sprint"]["id"]
    approve_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/approve",
        json={},
    )
    assert approve_response.status_code == 200

    monkeypatch.setattr(
        "app.services.evidence_service._fetch_url",
        lambda settings, url: ParsedSource(
            title="Fetched research source",
            text=(
                "Independent fitness coaches spend hours reviewing client check-ins, "
                "workout logs, wearable data, pricing pages, and competitor reviews. "
                "Many coaches pay for coaching software but still use manual notes and "
                "spreadsheets for synthesis before client calls."
            ),
            content_type="text/html",
        ),
    )
    sources_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/sources/discover"
    )
    assert sources_response.status_code == 200
    source_id = sources_response.json()["sources"][0]["id"]
    source_approval = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/sources/{source_id}/approve"
    )
    assert source_approval.status_code == 200
    competitors_response = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates/discover"
    )
    assert competitors_response.status_code == 200
    candidate_id = competitors_response.json()["candidates"][0]["id"]
    candidate_approval = client.post(
        f"/api/projects/{project_id}/research-sprints/{sprint_id}/competitor-candidates/{candidate_id}/approve"
    )
    assert candidate_approval.status_code == 200
    return project_id, sprint_id
