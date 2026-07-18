"""Adapter seam for an optional Llama Guard runtime."""

from app.security.guardrails.classifiers import (
    DetectionContext,
    DetectionResult,
    PromptAttackDetector,
)


class LlamaGuardAdapter(PromptAttackDetector):
    def classify(self, text: str, context: DetectionContext) -> DetectionResult:
        raise RuntimeError("Llama Guard adapter is not configured.")
