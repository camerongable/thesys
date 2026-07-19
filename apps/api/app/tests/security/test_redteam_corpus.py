from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from app.core.config import Settings
from app.features.evidence.source_provenance import assess_source_trust
from app.security.guardrails import GuardrailGateway
from app.services.data_protection_service import data_protection_service

REPO_ROOT = Path(__file__).resolve().parents[5]
REDTEAM_ROOT = REPO_ROOT / "security" / "redteam"
REQUIRED_SUITES = {
    "direct_injection.yaml",
    "indirect_injection.yaml",
    "memory_poisoning.yaml",
    "retrieval_poisoning.yaml",
    "tool_misuse.yaml",
    "mcp_tool_poisoning.yaml",
    "pii_exfiltration.yaml",
    "cross_tenant.yaml",
    "encoded_attacks.yaml",
    "multimodal_injection.yaml",
    "unbounded_consumption.yaml",
    "output_injection.yaml",
}


def _suite_documents() -> list[tuple[Path, dict[str, Any]]]:
    documents: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(REDTEAM_ROOT.glob("*.yaml")):
        loaded = yaml.safe_load(path.read_text())
        assert isinstance(loaded, dict), path
        documents.append((path, loaded))
    return documents


def _deterministic_cases() -> list[tuple[Path, dict[str, Any]]]:
    return [
        (path, case)
        for path, document in _suite_documents()
        for case in document["cases"]
        if case["execution"] == "deterministic"
    ]


def test_redteam_corpus_declares_all_required_suites_and_case_contracts() -> None:
    documents = _suite_documents()

    assert {path.name for path, _ in documents} == REQUIRED_SUITES
    assert (REDTEAM_ROOT / "indirect_injection_documents" / "malicious_webpage.txt").is_file()
    for path, document in documents:
        assert document["version"] == 1, path
        assert document["suite"] == path.stem
        assert isinstance(document["cases"], list) and document["cases"], path
        for case in document["cases"]:
            assert case["id"]
            assert case["execution"] in {"deterministic", "integration"}
            assert case["handler"]
            assert isinstance(case["input"], dict)
            assert isinstance(case["expect"], dict) and case["expect"]


@pytest.mark.parametrize(
    ("path", "case"),
    _deterministic_cases(),
    ids=lambda value: value.stem if isinstance(value, Path) else value["id"],
)
def test_redteam_deterministic_cases_hold_at_their_security_boundary(
    path: Path,
    case: dict[str, Any],
) -> None:
    handler = case["handler"]
    payload = case["input"]
    expected = case["expect"]

    if handler == "guardrail_user":
        decision = GuardrailGateway(Settings()).evaluate_user_input(payload["text"])
        assert decision.detection.category == expected["category"], path
        assert decision.should_block is expected["blocked"], path
        normalized_excludes = expected.get("normalized_excludes")
        if normalized_excludes:
            assert normalized_excludes not in decision.detection.normalized_text
        return

    if handler == "source_trust":
        text = payload.get("text")
        if text is None:
            text = (REDTEAM_ROOT / payload["document"]).read_text()
        trust = assess_source_trust(
            source_type=payload["source_type"],
            text=text,
            metadata=payload.get("metadata", {}),
            approved_by=None,
            duplicate_source_count=payload.get("duplicate_source_count", 0),
        )
        assert trust.security_status == expected["security_status"], path
        assert expected["signal"] in trust.signals, path
        return

    if handler == "data_protection":
        protected = data_protection_service.create_searchable_copy(payload["text"])
        assert protected.data_classification.value == expected["data_classification"], path
        for raw_value in expected["redacts"]:
            assert raw_value not in protected.text
        return

    if handler == "output_sanitization":
        output = GuardrailGateway(Settings()).sanitize_rendered_output(payload["text"])
        for unsafe_value in expected["excludes"]:
            assert unsafe_value not in output
        return

    raise AssertionError(f"Unsupported deterministic handler {handler!r} in {path}")
