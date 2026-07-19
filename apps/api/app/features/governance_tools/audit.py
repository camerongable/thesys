"""Pure audit/proposal payload builders for governed tool orchestration."""

from typing import Any


def invocation_requested_metadata(
    definition: Any,
    *,
    include_approval_policy: bool,
    policy_decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Shape metadata for a tool-invocation request audit event."""

    metadata: dict[str, Any] = {
        "tool_name": definition.name,
        "access_mode": definition.access_mode,
    }
    if include_approval_policy:
        metadata["approval_policy"] = definition.approval_policy
    if policy_decision is not None:
        metadata["policy_decision"] = policy_decision
    return metadata


def invocation_executed_metadata(definition: Any) -> dict[str, Any]:
    return {"tool_name": definition.name, "access_mode": definition.access_mode}


def invocation_status_metadata(tool_name: str, status: str) -> dict[str, Any]:
    return {"tool_name": tool_name, "status": status}


def denial_metadata(
    definition: Any,
    *,
    role: str,
    reason: str,
    detail: str | None,
    policy_decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = {
        "tool_name": definition.name,
        "access_mode": definition.access_mode,
        "approval_policy": definition.approval_policy,
        "role": role,
        "reason": reason,
        "detail": detail,
    }
    if policy_decision is not None:
        metadata["policy_decision"] = policy_decision
    return metadata


def approval_summary(definition: Any, output_summary: str | None) -> str:
    return output_summary or f"{definition.title} requires approval."


def approval_proposed_change(
    definition: Any,
    *,
    invocation_id: Any,
    proposal: Any,
) -> dict[str, Any]:
    return {
        "tool_name": definition.name,
        "tool_invocation_id": str(invocation_id),
        "proposal": proposal or {},
    }
