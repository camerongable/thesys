"""Adapter seam for an optional NeMo Guardrails runtime."""

from app.security.guardrails.classifiers import (
    DetectionContext,
    DetectionResult,
    PromptAttackDetector,
)


class NeMoGuardrailsAdapter(PromptAttackDetector):
    def classify(self, text: str, context: DetectionContext) -> DetectionResult:
        raise RuntimeError("NeMo Guardrails adapter is not configured.")
