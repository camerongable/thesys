"""Adapter seam for an optional Llama Guard runtime."""

from app.security.guardrails.classifiers import (
    DetectionContext,
    DetectionResult,
    GuardrailDetectorUnavailableError,
    PromptAttackDetector,
)


class LlamaGuardAdapter(PromptAttackDetector):
    name = "llama_guard"

    def classify(self, text: str, context: DetectionContext) -> DetectionResult:
        raise GuardrailDetectorUnavailableError("Llama Guard adapter is not configured.")
