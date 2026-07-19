#!/usr/bin/env python3
"""Expose the deterministic guardrail as a local Promptfoo target."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

from app.core.config import Settings
from app.features.evidence.source_provenance import assess_source_trust
from app.security.guardrails import GuardrailGateway
from app.services.data_protection_service import data_protection_service

REDTEAM_ROOT = Path(__file__).resolve().parents[3] / "security" / "redteam"


def evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a single red-team prompt without exposing prompt content in output."""
    case_id = payload.get("source_case_id")
    if isinstance(case_id, str) and case_id:
        return _evaluate_corpus_case(case_id)
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


def _evaluate_corpus_case(case_id: str) -> dict[str, Any]:
    case = _corpus_case(case_id)
    if case["execution"] != "deterministic":
        raise ValueError("Promptfoo full suite only accepts deterministic corpus cases.")
    passed = _case_passed(case)
    return {"case_id": case_id, "passed": passed}


def _corpus_case(case_id: str) -> dict[str, Any]:
    for path in sorted(REDTEAM_ROOT.glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            continue
        for case in document.get("cases", []):
            if isinstance(case, dict) and case.get("id") == case_id:
                return case
    raise ValueError(f"Unknown red-team corpus case: {case_id}")


def _case_passed(case: dict[str, Any]) -> bool:
    payload = case["input"]
    expected = case["expect"]
    handler = case["handler"]
    if handler == "guardrail_user":
        decision = GuardrailGateway(Settings()).evaluate_user_input(payload["text"])
        return (
            decision.detection.category == expected["category"]
            and decision.should_block is expected["blocked"]
            and (
                not expected.get("normalized_excludes")
                or expected["normalized_excludes"] not in decision.detection.normalized_text
            )
        )
    if handler == "source_trust":
        text = payload.get("text")
        if text is None:
            text = (REDTEAM_ROOT / payload["document"]).read_text(encoding="utf-8")
        trust = assess_source_trust(
            source_type=payload["source_type"],
            text=text,
            metadata=payload.get("metadata", {}),
            approved_by=None,
            duplicate_source_count=payload.get("duplicate_source_count", 0),
        )
        return (
            trust.security_status == expected["security_status"]
            and expected["signal"] in trust.signals
        )
    if handler == "data_protection":
        protected = data_protection_service.create_searchable_copy(payload["text"])
        return (
            protected.data_classification.value == expected["data_classification"]
            and all(raw_value not in protected.text for raw_value in expected["redacts"])
        )
    if handler == "output_sanitization":
        output = GuardrailGateway(Settings()).sanitize_rendered_output(payload["text"])
        return all(unsafe_value not in output for unsafe_value in expected["excludes"])
    raise ValueError(f"Unsupported deterministic handler: {handler}")


def main() -> int:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        raise ValueError("Expected a red-team request object.")
    print(json.dumps(evaluate(payload), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
