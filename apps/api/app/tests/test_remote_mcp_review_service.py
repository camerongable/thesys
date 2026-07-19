import uuid

import pytest

from app.core.config import Settings
from app.db.models import MCPServerRegistration
from app.services import remote_mcp_review_service


class _Response:
    def __init__(self, payload: dict[str, object], headers: dict[str, str] | None = None) -> None:
        self._payload = payload
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


class _Client:
    def __init__(self, responses: list[_Response]) -> None:
        self._responses = responses
        self.requests: list[dict[str, object]] = []

    def __enter__(self) -> "_Client":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def post(self, _url: str, **kwargs: object) -> _Response:
        self.requests.append(kwargs)
        return self._responses.pop(0)


def _registration() -> MCPServerRegistration:
    input_schema = {"type": "object", "properties": {"query": {"type": "string"}}}
    output_schema = {"type": "object", "properties": {"result": {"type": "string"}}}
    return MCPServerRegistration(
        workspace_id=uuid.uuid4(),
        name="Reviewed server",
        base_url="https://mcp.example.test/v1",
        transport="streamable_http",
        server_fingerprint="a" * 64,
        approved_version="1.2.3",
        allowed_tools=["search_project_evidence"],
        tool_schema_snapshot={
            "search_project_evidence": {
                "version": "1.0.0",
                "input_schema": input_schema,
                "output_schema": output_schema,
            }
        },
        oauth_issuer=None,
        enabled=False,
        reviewed_by=uuid.uuid4(),
    )


def test_review_registration_verifies_tls_version_and_full_manifest(monkeypatch) -> None:
    registration = _registration()
    client = _Client(
        [
            _Response(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"serverInfo": {"name": "remote", "version": "1.2.3"}},
                },
                {"Mcp-Session-Id": "session-1"},
            ),
            _Response(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {
                        "tools": [
                            {
                                "name": "search_project_evidence",
                                "inputSchema": registration.tool_schema_snapshot[
                                    "search_project_evidence"
                                ]["input_schema"],
                                "outputSchema": registration.tool_schema_snapshot[
                                    "search_project_evidence"
                                ]["output_schema"],
                                "annotations": {"manifestVersion": "1.0.0"},
                            }
                        ]
                    },
                }
            ),
        ]
    )
    monkeypatch.setattr(
        remote_mcp_review_service,
        "_certificate_fingerprint",
        lambda *_args, **_kwargs: "a" * 64,
    )
    monkeypatch.setattr(remote_mcp_review_service.httpx, "Client", lambda **_kwargs: client)

    review = remote_mcp_review_service.review_registration(Settings(), registration)

    assert review.server_name == "remote"
    assert review.server_version == "1.2.3"
    assert review.tool_count == 1
    assert client.requests[1]["headers"] == {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "Mcp-Session-Id": "session-1",
    }


def test_review_registration_rejects_live_schema_drift(monkeypatch) -> None:
    registration = _registration()
    client = _Client(
        [
            _Response(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {"serverInfo": {"name": "remote", "version": "1.2.3"}},
                }
            ),
            _Response(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "result": {
                        "tools": [
                            {
                                "name": "search_project_evidence",
                                "inputSchema": {"type": "object", "properties": {}},
                                "outputSchema": registration.tool_schema_snapshot[
                                    "search_project_evidence"
                                ]["output_schema"],
                                "annotations": {"manifestVersion": "1.0.0"},
                            }
                        ]
                    },
                }
            ),
        ]
    )
    monkeypatch.setattr(
        remote_mcp_review_service,
        "_certificate_fingerprint",
        lambda *_args, **_kwargs: "a" * 64,
    )
    monkeypatch.setattr(remote_mcp_review_service.httpx, "Client", lambda **_kwargs: client)

    with pytest.raises(remote_mcp_review_service.RemoteMcpReviewError) as exc_info:
        remote_mcp_review_service.review_registration(Settings(), registration)

    assert exc_info.value.reason_code == "tool_schema_drift"
