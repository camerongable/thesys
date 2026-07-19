"""Fail-closed review of a remote MCP server before it can be enabled."""

import hashlib
import json
import socket
import ssl
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from pydantic import SecretStr

from app.core.config import Settings
from app.db.models import MCPServerRegistration
from app.features.governance_tools import schema_guard
from app.features.mcp.protocol import MCP_PROTOCOL_VERSION

REVIEW_CLIENT_INFO = {"name": "thesys-security-review", "version": "v1"}
MAX_SSE_EVENT_BYTES = 1_000_000


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


@dataclass(frozen=True)
class RemoteMcpInvocation:
    review: RemoteMcpReview
    tool_name: str
    output: dict[str, Any]


class _SseSession:
    """One legacy MCP HTTP+SSE session bound to a reviewed server origin."""

    def __init__(
        self,
        client: httpx.Client,
        *,
        base_url: str,
        authorization: SecretStr | None,
    ) -> None:
        self._client = client
        self._base_url = base_url
        self._authorization = authorization
        self._stream_context: Any = None
        self._lines: Iterator[str | bytes] | None = None
        self._post_url: str | None = None

    def __enter__(self) -> "_SseSession":
        headers = {"Accept": "text/event-stream", "Cache-Control": "no-cache"}
        if self._authorization is not None:
            headers["Authorization"] = f"Bearer {self._authorization.get_secret_value()}"
        self._stream_context = self._client.stream("GET", self._base_url, headers=headers)
        try:
            response = self._stream_context.__enter__()
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].casefold()
            if content_type != "text/event-stream":
                raise RemoteMcpReviewError("invalid_sse_stream")
            self._lines = response.iter_lines()
            event_name, endpoint = self._next_event()
            if event_name != "endpoint":
                raise RemoteMcpReviewError("invalid_sse_endpoint")
            self._post_url = _validated_sse_endpoint(self._base_url, endpoint)
            return self
        except BaseException:
            self._stream_context.__exit__(None, None, None)
            self._stream_context = None
            raise

    def __exit__(self, *args: object) -> None:
        if self._stream_context is not None:
            self._stream_context.__exit__(*args)

    def rpc_call(
        self,
        *,
        request_id: int,
        method: str,
        params: dict[str, object],
    ) -> dict[str, Any]:
        if self._post_url is None:
            raise RemoteMcpReviewError("invalid_sse_endpoint")
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self._authorization is not None:
            headers["Authorization"] = f"Bearer {self._authorization.get_secret_value()}"
        response = self._client.post(
            self._post_url,
            headers=headers,
            json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
        )
        response.raise_for_status()
        return self._next_response(request_id)

    def _next_response(self, request_id: int) -> dict[str, Any]:
        while True:
            event_name, data = self._next_event()
            if event_name != "message":
                raise RemoteMcpReviewError("invalid_sse_message")
            try:
                payload = json.loads(data)
            except json.JSONDecodeError as exc:
                raise RemoteMcpReviewError("invalid_jsonrpc_response") from exc
            if not isinstance(payload, dict) or payload.get("jsonrpc") != "2.0":
                raise RemoteMcpReviewError("invalid_jsonrpc_response")
            if "id" not in payload:
                if isinstance(payload.get("method"), str):
                    continue
                raise RemoteMcpReviewError("invalid_jsonrpc_response")
            if payload.get("id") != request_id:
                raise RemoteMcpReviewError("unexpected_jsonrpc_response")
            if payload.get("error") is not None:
                raise RemoteMcpReviewError("remote_protocol_error")
            result = payload.get("result")
            if not isinstance(result, dict):
                raise RemoteMcpReviewError("invalid_jsonrpc_response")
            return result

    def _next_event(self) -> tuple[str, str]:
        if self._lines is None:
            raise RemoteMcpReviewError("invalid_sse_stream")
        event_name = "message"
        data_lines: list[str] = []
        event_size = 0
        for raw_line in self._lines:
            line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
            event_size += len(line.encode("utf-8"))
            if event_size > MAX_SSE_EVENT_BYTES:
                raise RemoteMcpReviewError("sse_event_too_large")
            if not line:
                if data_lines:
                    return event_name, "\n".join(data_lines)
                event_name = "message"
                continue
            if line.startswith(":"):
                continue
            field, separator, value = line.partition(":")
            if not separator:
                value = ""
            elif value.startswith(" "):
                value = value[1:]
            if field == "event":
                event_name = value
            elif field == "data":
                data_lines.append(value)
        raise RemoteMcpReviewError("sse_stream_ended")


def review_registration(
    settings: Settings,
    registration: MCPServerRegistration,
    *,
    authorization: SecretStr | None = None,
) -> RemoteMcpReview:
    """Verify the pinned identity and reviewed tool contract of a remote server."""
    try:
        with httpx.Client(
            timeout=settings.mcp_remote_review_timeout_seconds,
            follow_redirects=False,
            verify=True,
        ) as client:
            if registration.transport == "streamable_http":
                review, _ = _review_with_client(
                    settings,
                    registration,
                    client,
                    authorization=authorization,
                )
            elif registration.transport == "sse":
                review = _review_with_sse_client(
                    settings,
                    registration,
                    client,
                    authorization=authorization,
                )
            else:
                raise RemoteMcpReviewError("unsupported_transport")
    except RemoteMcpReviewError:
        raise
    except (httpx.HTTPError, ValueError, OSError, ssl.SSLError) as exc:
        raise RemoteMcpReviewError("remote_review_unavailable") from exc
    return review


def invoke_registration(
    settings: Settings,
    registration: MCPServerRegistration,
    *,
    tool_name: str,
    arguments: dict[str, Any],
    authorization: SecretStr | None = None,
    idempotency_key: str | None = None,
) -> RemoteMcpInvocation:
    """Call one approved remote tool after a fresh review on the same MCP session."""
    if not registration.enabled:
        raise RemoteMcpReviewError("server_not_enabled")
    if tool_name not in registration.allowed_tools:
        raise RemoteMcpReviewError("tool_not_approved")
    snapshot = registration.tool_schema_snapshot.get(tool_name)
    if not isinstance(snapshot, dict):
        raise RemoteMcpReviewError("tool_schema_drift")
    _validate_schema_payload(snapshot.get("input_schema"), arguments, "input")

    try:
        with httpx.Client(
            timeout=settings.mcp_remote_review_timeout_seconds,
            follow_redirects=False,
            verify=True,
        ) as client:
            call_params: dict[str, object] = {"name": tool_name, "arguments": arguments}
            if idempotency_key is not None:
                call_params["_meta"] = {"thesys/idempotencyKey": idempotency_key}
            if registration.transport == "streamable_http":
                review, session_id = _review_with_client(
                    settings,
                    registration,
                    client,
                    authorization=authorization,
                )
                call_result, _ = _rpc_call(
                    client,
                    registration.base_url,
                    request_id=3,
                    method="tools/call",
                    params=call_params,
                    session_id=session_id,
                    authorization=authorization,
                )
            elif registration.transport == "sse":
                certificate_fingerprint = _certificate_fingerprint(
                    registration.base_url,
                    timeout_seconds=settings.mcp_remote_review_timeout_seconds,
                )
                if certificate_fingerprint != registration.server_fingerprint.casefold():
                    raise RemoteMcpReviewError("server_identity_mismatch")
                with _SseSession(
                    client,
                    base_url=registration.base_url,
                    authorization=authorization,
                ) as session:
                    review = _review_with_sse_session(
                        registration,
                        session,
                        certificate_fingerprint=certificate_fingerprint,
                    )
                    call_result = session.rpc_call(
                        request_id=3,
                        method="tools/call",
                        params=call_params,
                    )
            else:
                raise RemoteMcpReviewError("unsupported_transport")
    except RemoteMcpReviewError:
        raise
    except (httpx.HTTPError, ValueError, OSError, ssl.SSLError) as exc:
        raise RemoteMcpReviewError("remote_invocation_unavailable") from exc

    if call_result.get("isError") is True:
        raise RemoteMcpReviewError("remote_tool_failed")
    output = call_result.get("structuredContent")
    _validate_schema_payload(snapshot.get("output_schema"), output, "output")
    return RemoteMcpInvocation(review=review, tool_name=tool_name, output=output)


def _review_with_client(
    settings: Settings,
    registration: MCPServerRegistration,
    client: httpx.Client,
    *,
    authorization: SecretStr | None,
) -> tuple[RemoteMcpReview, str | None]:
    if registration.transport != "streamable_http":
        raise RemoteMcpReviewError("unsupported_transport")
    certificate_fingerprint = _certificate_fingerprint(
        registration.base_url,
        timeout_seconds=settings.mcp_remote_review_timeout_seconds,
    )
    if certificate_fingerprint != registration.server_fingerprint.casefold():
        raise RemoteMcpReviewError("server_identity_mismatch")
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
    tools = tools_result.get("tools")
    if not isinstance(tools, list):
        raise RemoteMcpReviewError("invalid_tool_catalog")
    _verify_tool_catalog(registration, tools)
    return (
        RemoteMcpReview(
            server_name=server_name.strip(),
            server_version=server_version,
            certificate_fingerprint=certificate_fingerprint,
            tool_count=len(tools),
        ),
        session_id,
    )


def _review_with_sse_client(
    settings: Settings,
    registration: MCPServerRegistration,
    client: httpx.Client,
    *,
    authorization: SecretStr | None,
) -> RemoteMcpReview:
    certificate_fingerprint = _certificate_fingerprint(
        registration.base_url,
        timeout_seconds=settings.mcp_remote_review_timeout_seconds,
    )
    if certificate_fingerprint != registration.server_fingerprint.casefold():
        raise RemoteMcpReviewError("server_identity_mismatch")
    with _SseSession(
        client,
        base_url=registration.base_url,
        authorization=authorization,
    ) as session:
        return _review_with_sse_session(
            registration,
            session,
            certificate_fingerprint=certificate_fingerprint,
        )


def _review_with_sse_session(
    registration: MCPServerRegistration,
    session: _SseSession,
    *,
    certificate_fingerprint: str,
) -> RemoteMcpReview:
    initialize_result = session.rpc_call(
        request_id=1,
        method="initialize",
        params={
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": REVIEW_CLIENT_INFO,
        },
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
    tools_result = session.rpc_call(request_id=2, method="tools/list", params={})
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


def _validated_sse_endpoint(base_url: str, endpoint: str) -> str:
    if not endpoint or endpoint != endpoint.strip():
        raise RemoteMcpReviewError("invalid_sse_endpoint")
    base = urlparse(base_url)
    resolved = urlparse(urljoin(base_url, endpoint))
    if (
        resolved.scheme != "https"
        or not resolved.hostname
        or resolved.username is not None
        or resolved.password is not None
        or resolved.fragment
        or resolved.hostname.casefold() != base.hostname.casefold()
        or (resolved.port or 443) != (base.port or 443)
    ):
        raise RemoteMcpReviewError("sse_endpoint_url_invalid")
    return resolved.geturl()


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


def _validate_schema_payload(schema: Any, value: Any, value_type: str) -> dict[str, Any]:
    if not isinstance(schema, dict):
        raise RemoteMcpReviewError("tool_schema_drift")
    try:
        return schema_guard.validate_schema_payload(
            schema,
            value,
            label=f"remote MCP tool {value_type}",
        )
    except schema_guard.ToolGuardViolation as exc:
        raise RemoteMcpReviewError(f"tool_{value_type}_invalid") from exc


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
