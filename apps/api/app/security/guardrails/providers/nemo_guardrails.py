"""Adapter seam for an optional NeMo Guardrails runtime."""

from app.security.guardrails.classifiers import (
    DetectionContext,
    DetectionResult,
    GuardrailDetectorUnavailableError,
    PromptAttackDetector,
)


class NeMoGuardrailsAdapter(PromptAttackDetector):
    name = "nemo_guardrails"

    def classify(self, text: str, context: DetectionContext) -> DetectionResult:
        raise GuardrailDetectorUnavailableError("NeMo Guardrails adapter is not configured.")
