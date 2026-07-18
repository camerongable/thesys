"""Adapter seam for a separately configured Prompt Guard runtime."""

from app.security.guardrails.classifiers import (
    DetectionContext,
    DetectionResult,
    PromptAttackDetector,
)


class PromptGuardDetector(PromptAttackDetector):
    def classify(self, text: str, context: DetectionContext) -> DetectionResult:
        raise RuntimeError("Prompt Guard classifier is not configured.")
