#!/usr/bin/env python3
"""Expose the deterministic guardrail as a local Promptfoo target."""

from __future__ import annotations

import json
import sys
from typing import Any

from app.core.config import Settings
from app.security.guardrails import GuardrailGateway


def evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a single red-team prompt without exposing prompt content in output."""
    channel = str(payload.get("channel") or "user_input")
    if channel != "user_input":
        raise ValueError("Unsupported red-team channel.")
    decision = GuardrailGateway(Settings()).evaluate_user_input(str(payload.get("prompt") or ""))
    return {
        "category": decision.detection.category,
        "blocked": decision.should_block,
        "tools_allowed": decision.tools_allowed,
        "memory_writes_allowed": decision.memory_writes_allowed,
    }


def main() -> int:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        raise ValueError("Expected a red-team request object.")
    print(json.dumps(evaluate(payload), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
