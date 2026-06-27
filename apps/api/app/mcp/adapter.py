import uuid
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext
from app.core.config import Settings
from app.core.redaction import redact_payload
from app.db.models import ApprovalRequest, ToolInvocation
from app.schemas.mcp import MCPToolCallRead, MCPToolRead
from app.services import governance_service, project_service, tool_service

ADAPTER_VERSION = "thesys-mcp-adapter:v1"
READ_TOOL_LIMIT = 100


@dataclass(frozen=True)
class MCPCallContext:
    client_id: str
    duration_ms: int


def list_tools(*, include_proposals: bool = True) -> list[MCPToolRead]:
    """Expose governed app tools in an MCP-shaped schema without bypassing policy."""
    definitions = tool_service.list_tool_definitions()
    if not include_proposals:
        definitions = [definition for definition in definitions if definition.access_mode == "read"]
    return [
        MCPToolRead(
            name=definition.name,
            title=definition.title,
            description=definition.description,
            input_schema=definition.input_schema,
            output_schema=definition.output_schema,
            access_mode=definition.access_mode,
            risk_level=definition.risk_level,
            approval_policy=definition.approval_policy,
        )
        for definition in definitions[:READ_TOOL_LIMIT]
    ]


def call_tool(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    *,
    tool_name: str,
    arguments: dict[str, Any],
    client_id: str,
) -> MCPToolCallRead:
    """Invoke a governed tool for an MCP client, preserving approvals and audit logs."""
    project_service.get_project(db, auth, project_id)
    definition = _definition(tool_name)
    started = perf_counter()
    if definition.access_mode == "proposal":
        invocation = tool_service.create_proposal(
            db,
            auth,
            project_id,
            tool_name,
            arguments,
            requested_by="agent",
            input_json={"mcp": {"client_id": client_id, "adapter_version": ADAPTER_VERSION}},
        )
        duration_ms = int((perf_counter() - started) * 1000)
        _attach_mcp_metadata(db, auth, project_id, invocation, client_id, duration_ms)
        approval = _approval_for_invocation(db, invocation)
        output = invocation.output_json or {}
        return _read(
            invocation,
            duration_ms=duration_ms,
            approval_request_id=str(approval.id) if approval else None,
            output=output,
        )

    result = tool_service.execute_tool(
        db,
        auth,
        settings,
        project_id,
        tool_name,
        arguments,
        requested_by="agent",
    )
    duration_ms = int((perf_counter() - started) * 1000)
    _attach_mcp_metadata(db, auth, project_id, result.invocation, client_id, duration_ms)
    return _read(
        result.invocation,
        duration_ms=duration_ms,
        approval_request_id=None,
        output=result.output,
    )


def _attach_mcp_metadata(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    invocation: ToolInvocation,
    client_id: str,
    duration_ms: int,
) -> None:
    mcp_metadata = {
        "client_id": client_id,
        "adapter_version": ADAPTER_VERSION,
        "duration_ms": duration_ms,
    }
    invocation.input_json = redact_payload(
        {
            "tool_input": invocation.input_json or {},
            "mcp": mcp_metadata,
        },
        redact_emails=True,
    )
    governance_service.record_audit_event(
        db,
        auth,
        event_type="mcp_tool_invocation",
        actor_type="agent",
        project_id=project_id,
        entity_type="tool_invocation",
        entity_id=invocation.id,
        risk_level=invocation.risk_level,
        summary=f"MCP client invoked {invocation.tool_name}.",
        metadata={"tool_name": invocation.tool_name, **mcp_metadata},
    )
    db.commit()
    db.refresh(invocation)


def _read(
    invocation: ToolInvocation,
    *,
    duration_ms: int,
    approval_request_id: str | None,
    output: dict[str, Any],
) -> MCPToolCallRead:
    return MCPToolCallRead(
        tool_name=invocation.tool_name,
        access_mode=invocation.access_mode,  # type: ignore[arg-type]
        risk_level=invocation.risk_level,  # type: ignore[arg-type]
        status=invocation.status,
        invocation_id=str(invocation.id),
        approval_required=invocation.access_mode == "proposal",
        approval_request_id=approval_request_id,
        duration_ms=duration_ms,
        output=output,
        trace={
            "tool_invocation_id": str(invocation.id),
            "requested_by": invocation.requested_by,
            "mcp_adapter_version": ADAPTER_VERSION,
        },
    )


def _approval_for_invocation(db: Session, invocation: ToolInvocation) -> ApprovalRequest | None:
    return db.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.entity_type == "tool_invocation",
            ApprovalRequest.entity_id == invocation.id,
            ApprovalRequest.status == "pending",
        )
    )


def _definition(tool_name: str):
    for definition in tool_service.list_tool_definitions():
        if definition.name == tool_name:
            return definition
    raise ValueError(f"Unsupported MCP tool: {tool_name}")
