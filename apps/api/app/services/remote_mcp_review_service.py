"""Fail-closed review of a remote MCP server before it can be enabled."""

import hashlib
import json
import socket
import ssl
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import SecretStr

from app.core.config import Settings
from app.db.models import MCPServerRegistration
from app.features.mcp.protocol import MCP_PROTOCOL_VERSION

REVIEW_CLIENT_INFO = {"name": "thesys-security-review", "version": "v1"}


class RemoteMcpReviewError(RuntimeError):
    """A remote server could not satisfy the approved review contract."""

    def __init__(self, reason_code: str) -> None:
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True)
class RemoteMcpReview:
    server_name: str
    server_version: str
    certificate_fingerprint: str
    tool_count: int


def review_registration(
    settings: Settings,
    registration: MCPServerRegistration,
    *,
    authorization: SecretStr | None = None,
) -> RemoteMcpReview:
    """Verify the pinned identity and reviewed tool contract of a remote server."""
    if registration.transport != "streamable_http":
        raise RemoteMcpReviewError("unsupported_transport")
    certificate_fingerprint = _certificate_fingerprint(
        registration.base_url,
        timeout_seconds=settings.mcp_remote_review_timeout_seconds,
    )
    if certificate_fingerprint != registration.server_fingerprint.casefold():
        raise RemoteMcpReviewError("server_identity_mismatch")

    try:
        with httpx.Client(
            timeout=settings.mcp_remote_review_timeout_seconds,
            follow_redirects=False,
            verify=True,
        ) as client:
            initialize_result, session_id = _rpc_call(
                client,
                registration.base_url,
                request_id=1,
                method="initialize",
                params={
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": REVIEW_CLIENT_INFO,
                },
                authorization=authorization,
            )
            server_info = initialize_result.get("serverInfo")
            if not isinstance(server_info, dict):
                raise RemoteMcpReviewError("invalid_server_info")
            server_name = server_info.get("name")
            server_version = server_info.get("version")
            if not isinstance(server_name, str) or not server_name.strip():
                raise RemoteMcpReviewError("invalid_server_info")
            if server_version != registration.approved_version:
                raise RemoteMcpReviewError("server_version_drift")

            tools_result, _ = _rpc_call(
                client,
                registration.base_url,
                request_id=2,
                method="tools/list",
                params={},
                session_id=session_id,
                authorization=authorization,
            )
    except RemoteMcpReviewError:
        raise
    except (httpx.HTTPError, ValueError, OSError, ssl.SSLError) as exc:
        raise RemoteMcpReviewError("remote_review_unavailable") from exc

    tools = tools_result.get("tools")
    if not isinstance(tools, list):
        raise RemoteMcpReviewError("invalid_tool_catalog")
    _verify_tool_catalog(registration, tools)
    return RemoteMcpReview(
        server_name=server_name.strip(),
        server_version=server_version,
        certificate_fingerprint=certificate_fingerprint,
        tool_count=len(tools),
    )


def _certificate_fingerprint(base_url: str, *, timeout_seconds: float) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise RemoteMcpReviewError("invalid_server_url")
    context = ssl.create_default_context()
    with socket.create_connection(
        (parsed.hostname, parsed.port or 443), timeout=timeout_seconds
    ) as connection:
        with context.wrap_socket(connection, server_hostname=parsed.hostname) as tls_connection:
            certificate = tls_connection.getpeercert(binary_form=True)
    if not certificate:
        raise RemoteMcpReviewError("server_identity_unavailable")
    return hashlib.sha256(certificate).hexdigest()


def _rpc_call(
    client: httpx.Client,
    base_url: str,
    *,
    request_id: int,
    method: str,
    params: dict[str, object],
    session_id: str | None = None,
    authorization: SecretStr | None = None,
) -> tuple[dict[str, Any], str | None]:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    if authorization is not None:
        headers["Authorization"] = f"Bearer {authorization.get_secret_value()}"
    response = client.post(
        base_url,
        headers=headers,
        json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("id") != request_id:
        raise RemoteMcpReviewError("invalid_jsonrpc_response")
    if payload.get("error") is not None:
        raise RemoteMcpReviewError("remote_protocol_error")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise RemoteMcpReviewError("invalid_jsonrpc_response")
    return result, response.headers.get("Mcp-Session-Id")


def _verify_tool_catalog(
    registration: MCPServerRegistration,
    tools: list[Any],
) -> None:
    remote_tools: dict[str, dict[str, Any]] = {}
    for tool in tools:
        if not isinstance(tool, dict) or not isinstance(tool.get("name"), str):
            raise RemoteMcpReviewError("invalid_tool_catalog")
        name = tool["name"]
        if name in remote_tools:
            raise RemoteMcpReviewError("tool_schema_drift")
        remote_tools[name] = tool

    if set(remote_tools) != set(registration.allowed_tools):
        raise RemoteMcpReviewError("tool_schema_drift")
    for name in registration.allowed_tools:
        snapshot = registration.tool_schema_snapshot.get(name)
        if not isinstance(snapshot, dict) or not _tool_matches_snapshot(
            remote_tools[name], snapshot
        ):
            raise RemoteMcpReviewError("tool_schema_drift")


def _tool_matches_snapshot(tool: dict[str, Any], snapshot: dict[str, Any]) -> bool:
    annotations = tool.get("annotations")
    input_schema_matches = _canonical_json(tool.get("inputSchema")) == _canonical_json(
        snapshot.get("input_schema")
    )
    output_schema_matches = _canonical_json(tool.get("outputSchema")) == _canonical_json(
        snapshot.get("output_schema")
    )
    return (
        isinstance(annotations, dict)
        and annotations.get("manifestVersion") == snapshot.get("version")
        and input_schema_matches
        and output_schema_matches
    )


def _canonical_json(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
