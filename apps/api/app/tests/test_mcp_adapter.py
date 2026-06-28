import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ApprovalRequest, AuditEvent, ToolInvocation


def test_mcp_lists_governed_tool_schemas(client: TestClient) -> None:
    response = client.get("/api/mcp/tools", params={"include_proposals": "false"})

    assert response.status_code == 200
    body = response.json()
    assert body["protocol"] == "mcp"
    assert body["adapter_version"] == "thesys-mcp-adapter:v1"
    tool_names = {tool["name"] for tool in body["tools"]}
    assert "get_project_summary" in tool_names
    assert "list_project_memory" in tool_names
    assert "propose_memory_update" not in tool_names
    assert all(tool["access_mode"] == "read" for tool in body["tools"])


def test_mcp_read_tool_uses_existing_governance_and_audit(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = _create_project(client)

    response = client.post(
        f"/api/mcp/projects/{project_id}/tools/get_project_summary/call",
        json={"client_id": "codex-ide", "arguments": {}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tool_name"] == "get_project_summary"
    assert body["status"] == "executed"
    assert body["approval_required"] is False
    assert body["output"]["project"]["id"] == project_id

    invocation = db_session.scalar(
        select(ToolInvocation).where(ToolInvocation.id == uuid.UUID(body["invocation_id"]))
    )
    assert invocation is not None
    assert invocation.input_json["mcp"]["client_id"] == "codex-ide"
    assert invocation.input_json["mcp"]["adapter_version"] == "thesys-mcp-adapter:v1"
    audit = db_session.scalar(
        select(AuditEvent)
        .where(AuditEvent.event_type == "mcp_tool_invocation")
        .order_by(AuditEvent.created_at.desc())
    )
    assert audit is not None
    assert audit.event_metadata["client_id"] == "codex-ide"


def test_mcp_proposal_tool_creates_approval_request(
    client: TestClient,
    db_session: Session,
) -> None:
    project_id = _create_project(client)

    response = client.post(
        f"/api/mcp/projects/{project_id}/tools/propose_memory_update/call",
        json={
            "client_id": "eval-harness",
            "arguments": {
                "summary": "Remember that coach check-in triage is the current wedge.",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tool_name"] == "propose_memory_update"
    assert body["status"] == "requested"
    assert body["approval_required"] is True
    assert body["approval_request_id"]
    approval = db_session.scalar(
        select(ApprovalRequest).where(ApprovalRequest.id == uuid.UUID(body["approval_request_id"]))
    )
    assert approval is not None
    assert approval.request_type == "memory_update"
    invocation = db_session.scalar(
        select(ToolInvocation).where(ToolInvocation.id == uuid.UUID(body["invocation_id"]))
    )
    assert invocation is not None
    assert invocation.input_json["mcp"]["client_id"] == "eval-harness"


def test_mcp_proposal_tool_preserves_role_denial(
    client: TestClient,
) -> None:
    project_id = _create_project(client)

    response = client.post(
        f"/api/mcp/projects/{project_id}/tools/propose_memory_update/call",
        headers={"X-Dev-User-Role": "viewer"},
        json={
            "client_id": "viewer-client",
            "arguments": {"summary": "Viewer should not propose memory writes."},
        },
    )

    assert response.status_code == 403


def _create_project(client: TestClient) -> str:
    response = client.post(
        "/api/projects",
        json={"name": "MCP adapter project"},
    )
    assert response.status_code == 201
    return response.json()["id"]
