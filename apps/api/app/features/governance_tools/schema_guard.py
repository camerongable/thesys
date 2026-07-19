"""Schema and scope guards for governed agent/tool inputs."""

import json
import uuid
from typing import Any

VALID_REQUESTED_BY: set[str] = {"agent", "user", "system"}
MAX_TOOL_STRING_LENGTH = 4000
MAX_TOOL_ARRAY_LENGTH = 100


class ToolGuardViolation(ValueError):
    """Raised when a tool input, output, proposal, or metadata payload is invalid."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


def guard_tool_input(
    definition: Any,
    tool_input: dict[str, Any],
    *,
    research_sprint_id: uuid.UUID | None,
    requested_by: str,
) -> dict[str, Any]:
    """Validate model/client input before any tool logic sees it."""

    guard_requested_by(requested_by)
    guarded = validate_schema_payload(
        definition.input_schema,
        tool_input,
        label=f"{definition.name} input",
    )
    guard_research_sprint_scope(definition, guarded, research_sprint_id)
    return guarded


def guard_proposal_payload(
    definition: Any,
    proposal: dict[str, Any],
    *,
    research_sprint_id: uuid.UUID | None,
    requested_by: str,
) -> dict[str, Any]:
    guard_requested_by(requested_by)
    guarded = validate_schema_payload(
        definition.input_schema,
        proposal,
        label=f"{definition.name} proposal",
    )
    guard_research_sprint_scope(definition, guarded, research_sprint_id)
    if research_sprint_id is not None and "research_sprint_id" not in guarded:
        raise ToolGuardViolation(
            "scope_guard_failed",
            f"{definition.name} proposal must include the scoped research_sprint_id.",
        )
    return guarded


def guard_tool_metadata(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ToolGuardViolation("input_guard_failed", "Tool metadata must be a JSON object.")
    validate_json_value(value, "tool metadata")
    return value


def guard_tool_output(definition: Any, output: dict[str, Any]) -> None:
    validate_schema_payload(
        definition.output_schema,
        output,
        label=f"{definition.name} output",
    )


def guard_tool_manifest_input(definition: Any, tool_input: dict[str, Any]) -> None:
    """Apply the local manifest's record limit after schema validation."""
    for key in ("limit", "top_k"):
        value = tool_input.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            if value > definition.max_affected_records:
                raise ToolGuardViolation(
                    "manifest_record_limit_exceeded",
                    f"{definition.name} exceeds its approved record limit.",
                )


def guard_tool_manifest_output(definition: Any, output: dict[str, Any]) -> None:
    payload_size = len(json.dumps(output, default=str, sort_keys=True).encode("utf-8"))
    if payload_size > definition.max_output_bytes:
        raise ToolGuardViolation(
            "manifest_output_limit_exceeded",
            f"{definition.name} output exceeds its approved size limit.",
        )


def guard_requested_by(requested_by: str) -> None:
    if requested_by not in VALID_REQUESTED_BY:
        raise ToolGuardViolation(
            "requested_by_guard_failed",
            "Tool requested_by must be agent, user, or system.",
        )


def guard_research_sprint_scope(
    definition: Any,
    payload: dict[str, Any],
    research_sprint_id: uuid.UUID | None,
) -> None:
    raw_sprint_id = payload.get("research_sprint_id")
    if raw_sprint_id is None:
        return
    try:
        payload_sprint_id = uuid.UUID(str(raw_sprint_id))
    except ValueError as exc:
        raise ToolGuardViolation(
            "scope_guard_failed",
            f"{definition.name} research_sprint_id must be a valid UUID.",
        ) from exc
    if research_sprint_id is not None and payload_sprint_id != research_sprint_id:
        raise ToolGuardViolation(
            "scope_guard_failed",
            f"{definition.name} research_sprint_id does not match the scoped sprint.",
        )


def validate_schema_payload(
    schema: dict[str, Any],
    value: Any,
    *,
    label: str,
) -> dict[str, Any]:
    validate_schema_value(schema, value, label)
    if not isinstance(value, dict):
        raise ToolGuardViolation("input_guard_failed", f"{label} must be a JSON object.")
    return value


def validate_schema_value(schema: dict[str, Any], value: Any, path: str) -> None:
    expected_type = schema.get("type")
    if isinstance(expected_type, list):
        if value is None and "null" in expected_type:
            return
        non_null_types = [item for item in expected_type if item != "null"]
        expected_type = non_null_types[0] if non_null_types else None
    if "enum" in schema and value not in schema["enum"]:
        raise ToolGuardViolation("input_guard_failed", f"{path} must be one of {schema['enum']}.")
    if expected_type == "object":
        validate_object_schema(schema, value, path)
    elif expected_type == "array":
        validate_array_schema(schema, value, path)
    elif expected_type == "string":
        validate_string_schema(schema, value, path)
    elif expected_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ToolGuardViolation("input_guard_failed", f"{path} must be an integer.")
        if "minimum" in schema and value < schema["minimum"]:
            raise ToolGuardViolation("input_guard_failed", f"{path} is below the minimum.")
        if "maximum" in schema and value > schema["maximum"]:
            raise ToolGuardViolation("input_guard_failed", f"{path} is above the maximum.")
    elif expected_type == "number":
        if not isinstance(value, int | float) or isinstance(value, bool):
            raise ToolGuardViolation("input_guard_failed", f"{path} must be a number.")
    elif expected_type == "boolean":
        if not isinstance(value, bool):
            raise ToolGuardViolation("input_guard_failed", f"{path} must be a boolean.")
    else:
        validate_json_value(value, path)


def validate_object_schema(schema: dict[str, Any], value: Any, path: str) -> None:
    if not isinstance(value, dict):
        raise ToolGuardViolation("input_guard_failed", f"{path} must be a JSON object.")
    validate_json_value(value, path)
    properties = schema.get("properties") or {}
    for required_key in schema.get("required", []):
        if required_key not in value:
            raise ToolGuardViolation(
                "input_guard_failed",
                f"{path} is missing required field {required_key}.",
            )
    if schema.get("additionalProperties") is False:
        unknown_keys = sorted(set(value) - set(properties))
        if unknown_keys:
            raise ToolGuardViolation(
                "input_guard_failed",
                f"{path} has unsupported field {unknown_keys[0]}.",
            )
    for key, property_schema in properties.items():
        if key in value:
            validate_schema_value(property_schema, value[key], f"{path}.{key}")


def validate_array_schema(schema: dict[str, Any], value: Any, path: str) -> None:
    if not isinstance(value, list):
        raise ToolGuardViolation("input_guard_failed", f"{path} must be an array.")
    max_items = min(int(schema.get("maxItems", MAX_TOOL_ARRAY_LENGTH)), MAX_TOOL_ARRAY_LENGTH)
    if len(value) > max_items:
        raise ToolGuardViolation("input_guard_failed", f"{path} has too many items.")
    item_schema = schema.get("items")
    for index, item in enumerate(value):
        if isinstance(item_schema, dict):
            validate_schema_value(item_schema, item, f"{path}[{index}]")
        else:
            validate_json_value(item, f"{path}[{index}]")


def validate_string_schema(schema: dict[str, Any], value: Any, path: str) -> None:
    if not isinstance(value, str):
        raise ToolGuardViolation("input_guard_failed", f"{path} must be a string.")
    min_length = int(schema.get("minLength", 0))
    max_length = min(int(schema.get("maxLength", MAX_TOOL_STRING_LENGTH)), MAX_TOOL_STRING_LENGTH)
    if len(value) < min_length:
        raise ToolGuardViolation("input_guard_failed", f"{path} is too short.")
    if len(value) > max_length:
        raise ToolGuardViolation("input_guard_failed", f"{path} is too long.")
    fmt = schema.get("format")
    if fmt == "uuid":
        try:
            uuid.UUID(value)
        except ValueError as exc:
            raise ToolGuardViolation(
                "input_guard_failed",
                f"{path} must be a valid UUID.",
            ) from exc


def validate_json_value(value: Any, path: str) -> None:
    if isinstance(value, dict):
        if len(value) > MAX_TOOL_ARRAY_LENGTH:
            raise ToolGuardViolation("input_guard_failed", f"{path} has too many fields.")
        for key, item in value.items():
            if not isinstance(key, str):
                raise ToolGuardViolation("input_guard_failed", f"{path} keys must be strings.")
            validate_json_value(item, f"{path}.{key}")
        return
    if isinstance(value, list):
        if len(value) > MAX_TOOL_ARRAY_LENGTH:
            raise ToolGuardViolation("input_guard_failed", f"{path} has too many items.")
        for index, item in enumerate(value):
            validate_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, str):
        if len(value) > MAX_TOOL_STRING_LENGTH:
            raise ToolGuardViolation("input_guard_failed", f"{path} is too long.")
        return
    if value is None or isinstance(value, bool | int | float):
        return
    raise ToolGuardViolation("input_guard_failed", f"{path} must be JSON serializable.")
