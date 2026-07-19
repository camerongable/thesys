"""Fail-closed Open Policy Agent decision client."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import Settings


class OpaPolicyUnavailableError(RuntimeError):
    """Raised when OPA cannot return a valid authorization decision."""


@dataclass(frozen=True)
class OpaPolicyDecision:
    allow: bool
    requires_approval: bool
    reason: str
    allowed_scopes: tuple[str, ...]
    max_records: int


class OpaPolicyClient:
    """Evaluate named policy packages through OPA's REST data API."""

    def __init__(
        self,
        settings: Settings,
        *,
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        self._base_url = settings.opa_policy_url.rstrip("/")
        self._timeout_seconds = settings.opa_policy_timeout_seconds
        self._client_factory = client_factory or (
            lambda: httpx.Client(timeout=self._timeout_seconds)
        )

    def evaluate(self, policy_name: str, policy_input: dict[str, Any]) -> OpaPolicyDecision:
        if not policy_name or any(
            character not in "abcdefghijklmnopqrstuvwxyz_" for character in policy_name
        ):
            raise ValueError("OPA policy names must use lowercase letters and underscores.")
        try:
            with self._client_factory() as client:
                response = client.post(
                    f"{self._base_url}/v1/data/thesys/{policy_name}/decision",
                    json={"input": policy_input},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OpaPolicyUnavailableError("OPA policy evaluation is unavailable.") from exc
        return _parse_decision(payload)


def require_opa_decision(decision: OpaPolicyDecision) -> OpaPolicyDecision:
    """Translate an OPA decision into the fail-closed API authorization contract."""
    if not decision.allow:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=decision.reason)
    return decision


def unavailable_opa_policy_denial(_exc: OpaPolicyUnavailableError) -> HTTPException:
    """Return the non-bypassable denial used by privileged callers when OPA fails."""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Policy authorization is temporarily unavailable.",
    )


def _parse_decision(payload: object) -> OpaPolicyDecision:
    if not isinstance(payload, dict) or not isinstance(payload.get("result"), dict):
        raise OpaPolicyUnavailableError("OPA returned no policy decision.")
    result = payload["result"]
    allow = result.get("allow")
    requires_approval = result.get("requires_approval")
    reason = result.get("reason")
    allowed_scopes = result.get("allowed_scopes")
    max_records = result.get("max_records")
    if (
        not isinstance(allow, bool)
        or not isinstance(requires_approval, bool)
        or not isinstance(reason, str)
        or not reason.strip()
        or not isinstance(allowed_scopes, list)
        or not all(isinstance(scope, str) and scope.strip() for scope in allowed_scopes)
        or isinstance(max_records, bool)
        or not isinstance(max_records, int)
        or max_records < 0
    ):
        raise OpaPolicyUnavailableError("OPA returned an invalid policy decision.")
    return OpaPolicyDecision(
        allow=allow,
        requires_approval=requires_approval,
        reason=reason,
        allowed_scopes=tuple(allowed_scopes),
        max_records=max_records,
    )
