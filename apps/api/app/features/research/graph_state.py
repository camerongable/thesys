"""Pure serialization helpers for agentic research graph state."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


def to_jsonable(value: Any) -> Any:
    """Convert graph step output into JSON-compatible primitives."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, uuid.UUID | datetime | Decimal):
        return str(value)
    return value


def json_safe(value: Any) -> dict[str, Any]:
    """Return graph step output as a dictionary suitable for AI step storage."""
    converted = to_jsonable(value)
    if isinstance(converted, list):
        return {"items": converted}
    if isinstance(converted, dict):
        return converted
    return {"value": converted}
