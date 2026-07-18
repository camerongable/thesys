"""Deterministic prompt-attack classification contracts and baseline detector."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol

from app.security.guardrails.input_checks import InputInspection, inspect_text

AttackCategory = Literal[
    "benign",
    "direct_prompt_injection",
    "indirect_prompt_injection",
    "jailbreak",
    "system_prompt_extraction",
    "tool_manipulation",
    "data_exfiltration_attempt",
]
GuardrailAction = Literal["allow", "allow_with_restrictions", "block", "require_review"]

_IGNORE_INSTRUCTIONS = re.compile(
    r"\b(?:ignore|disregard|override|bypass)\b.{0,80}\b(?:previous|prior|system|developer)"
    r".{0,80}\b(?:instruction|rule|policy|prompt)s?\b",
    re.IGNORECASE | re.DOTALL,
)
_JAILBREAK = re.compile(
    r"\b(?:jailbreak|do anything now|DAN mode|unrestricted mode|safety filters?)\b",
    re.IGNORECASE,
)
_PROMPT_EXTRACTION = re.compile(
    r"\b(?:reveal|show|print|repeat|expose|dump)\b.{0,80}"
    r"\b(?:system|developer|hidden)\s+(?:prompt|instruction|message|policy)\b",
    re.IGNORECASE | re.DOTALL,
)
_TOOL_MANIPULATION = re.compile(
    r"\b(?:call|invoke|run|use|select)\b.{0,80}\b(?:tool|function|plugin|MCP)\b"
    r".{0,100}\b(?:without|bypass|ignore|override|secret|hidden)\b",
    re.IGNORECASE | re.DOTALL,
)
_EXFILTRATION = re.compile(
    r"\b(?:send|upload|post|exfiltrate|transmit)\b.{0,100}https?://",
    re.IGNORECASE | re.DOTALL,
)
_ROLE_REASSIGNMENT = re.compile(
    r"\b(?:you are now|act as|roleplay as|new system message|developer message)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DetectionContext:
    """Origin and workflow metadata required for an explainable policy decision."""

    source: Literal["user_input", "retrieved_content", "model_output"]
    workflow: str = "unspecified"
    source_id: str | None = None


@dataclass(frozen=True)
class DetectionResult:
    category: AttackCategory
    score: float
    action: GuardrailAction
    detector: str
    detector_version: str
    reasons: tuple[str, ...]
    normalized_text: str


class PromptAttackDetector(Protocol):
    def classify(self, text: str, context: DetectionContext) -> DetectionResult: ...


class DeterministicHeuristicDetector:
    """Conservative local detector for known prompt-attack and exfiltration patterns."""

    name = "deterministic_heuristic"
    version = "v1"

    def classify(self, text: str, context: DetectionContext) -> DetectionResult:
        inspection = inspect_text(text)
        category, score, reasons = self._classify(inspection, context)
        return DetectionResult(
            category=category,
            score=score,
            action=_action_for_score(score, context.source),
            detector=self.name,
            detector_version=self.version,
            reasons=tuple(reasons),
            normalized_text=inspection.normalized_text,
        )

    def _classify(
        self,
        inspection: InputInspection,
        context: DetectionContext,
    ) -> tuple[AttackCategory, float, list[str]]:
        text = inspection.normalized_text
        reasons = list(inspection.reasons)
        if _PROMPT_EXTRACTION.search(text):
            return "system_prompt_extraction", 0.98, [*reasons, "system_prompt_extraction_pattern"]
        if _EXFILTRATION.search(text):
            return "data_exfiltration_attempt", 0.96, [*reasons, "outbound_exfiltration_pattern"]
        if _TOOL_MANIPULATION.search(text):
            return "tool_manipulation", 0.94, [*reasons, "tool_manipulation_pattern"]
        if _JAILBREAK.search(text):
            return "jailbreak", 0.92, [*reasons, "jailbreak_pattern"]
        if _IGNORE_INSTRUCTIONS.search(text):
            category: AttackCategory = (
                "indirect_prompt_injection"
                if context.source == "retrieved_content"
                else "direct_prompt_injection"
            )
            return category, 0.9, [*reasons, "instruction_override_pattern"]
        if _ROLE_REASSIGNMENT.search(text):
            category = (
                "indirect_prompt_injection"
                if context.source == "retrieved_content"
                else "direct_prompt_injection"
            )
            return category, 0.72, [*reasons, "role_reassignment_pattern"]
        if inspection.has_encoded_payload:
            return "direct_prompt_injection", 0.55, [*reasons, "encoded_instruction_payload"]
        if inspection.has_credential_like_content:
            return "benign", 0.45, [*reasons, "credential_like_content"]
        if reasons:
            return "benign", 0.2, reasons
        return "benign", 0.0, []


def _action_for_score(score: float, source: str) -> GuardrailAction:
    if score >= 0.85:
        return "block"
    if score >= 0.65:
        return "require_review" if source == "model_output" else "allow_with_restrictions"
    if score >= 0.4:
        return "allow_with_restrictions"
    return "allow"
