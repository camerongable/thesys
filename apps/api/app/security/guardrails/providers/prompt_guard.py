"""Adapter seam for a separately configured Prompt Guard runtime."""

from app.security.guardrails.classifiers import (
    DetectionContext,
    DetectionResult,
    GuardrailDetectorUnavailableError,
    PromptAttackDetector,
)


class PromptGuardDetector(PromptAttackDetector):
    name = "prompt_guard"

    def classify(self, text: str, context: DetectionContext) -> DetectionResult:
        raise GuardrailDetectorUnavailableError("Prompt Guard classifier is not configured.")
