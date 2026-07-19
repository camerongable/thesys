from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.features.policy.opa import (
    OpaPolicyClient,
    OpaPolicyUnavailableError,
    require_opa_decision,
    unavailable_opa_policy_denial,
)

REPO_ROOT = Path(__file__).resolve().parents[5]


def test_opa_policy_bundle_has_every_required_default_deny_package() -> None:
    required_policies = {
        "tool_access",
        "memory_write",
        "model_routing",
        "data_access",
        "approval",
        "egress",
    }

    for policy_name in required_policies:
        policy = (REPO_ROOT / "policies" / f"{policy_name}.rego").read_text()
        assert f"package thesys.{policy_name}" in policy
        assert "default decision" in policy


def test_opa_policy_client_parses_a_typed_allow_decision() -> None:
    client = OpaPolicyClient(
        Settings(opa_policy_url="http://opa.test"),
        client_factory=lambda: httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "result": {
                            "allow": True,
                            "requires_approval": False,
                            "reason": "Read access is allowed.",
                            "allowed_scopes": ["project"],
                            "max_records": 25,
                        }
                    },
                    request=request,
                )
            )
        ),
    )

    decision = client.evaluate("tool_access", {"principal": {"role": "viewer"}})

    assert decision.allow is True
    assert decision.allowed_scopes == ("project",)
    assert decision.max_records == 25


@pytest.mark.parametrize(
    "response",
    [
        {"result": {"allow": True}},
        {
            "result": {
                "allow": "true",
                "requires_approval": False,
                "reason": "x",
                "allowed_scopes": [],
                "max_records": 1,
            }
        },
    ],
)
def test_opa_policy_client_rejects_malformed_decisions(response: dict[str, object]) -> None:
    client = OpaPolicyClient(
        Settings(opa_policy_url="http://opa.test"),
        client_factory=lambda: httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json=response, request=request)
            )
        ),
    )

    with pytest.raises(OpaPolicyUnavailableError):
        client.evaluate("tool_access", {})


def test_opa_transport_failure_denies_privileged_execution() -> None:
    def unavailable(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("OPA is offline")

    client = OpaPolicyClient(
        Settings(opa_policy_url="http://opa.test"),
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(unavailable)),
    )

    with pytest.raises(OpaPolicyUnavailableError) as exc_info:
        client.evaluate("memory_write", {})

    denial = unavailable_opa_policy_denial(exc_info.value)
    assert denial.status_code == 503
    assert denial.detail == "Policy authorization is temporarily unavailable."


def test_opa_denial_is_not_executable() -> None:
    client = OpaPolicyClient(
        Settings(opa_policy_url="http://opa.test"),
        client_factory=lambda: httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={
                        "result": {
                            "allow": False,
                            "requires_approval": True,
                            "reason": "High-risk mutation requires approval.",
                            "allowed_scopes": [],
                            "max_records": 0,
                        }
                    },
                    request=request,
                )
            )
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        require_opa_decision(client.evaluate("tool_access", {}))

    assert exc_info.value.status_code == 403
