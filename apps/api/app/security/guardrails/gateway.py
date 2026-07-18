"""Single security gateway for model prompts, retrieved content, and outputs."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.security.guardrails.classifiers import (
    DetectionContext,
    DetectionResult,
    DeterministicHeuristicDetector,
    PromptAttackDetector,
)
from app.security.guardrails.output_checks import OutputEvaluation, sanitize_markdown
from app.security.guardrails.policies import GUARDRAIL_SYSTEM_INSTRUCTION, GuardrailDecision, decide


class GuardrailBlockedError(RuntimeError):
    """Raised before a blocked payload can cross a model-provider boundary."""


@dataclass(frozen=True)
class RetrievedContentEvaluation:
    decision: GuardrailDecision
    wrapped_content: str


class GuardrailGateway:
    """Apply one deterministic policy before and after every model invocation."""

    def __init__(
        self,
        settings: Settings,
        *,
        detector: PromptAttackDetector | None = None,
    ) -> None:
        self._settings = settings
        self._detector = detector or DeterministicHeuristicDetector()

    def evaluate_user_input(self, text: str, *, workflow: str = "model_call") -> GuardrailDecision:
        return self._evaluate(text, DetectionContext(source="user_input", workflow=workflow))

    def evaluate_retrieved_content(
        self,
        text: str,
        *,
        source_id: str,
        source_type: str,
        trust_score: float,
        workflow: str = "model_call",
    ) -> RetrievedContentEvaluation:
        decision = self._evaluate(
            text,
            DetectionContext(
                source="retrieved_content",
                workflow=workflow,
                source_id=source_id,
            ),
        )
        escaped = decision.detection.normalized_text.replace("</untrusted_retrieved_content>", "")
        wrapped = (
            f'<untrusted_retrieved_content source_id="{source_id}" '
            f'source_type="{source_type}" trust_score="{trust_score:.3f}">\n'
            f"{escaped}\n</untrusted_retrieved_content>"
        )
        return RetrievedContentEvaluation(decision=decision, wrapped_content=wrapped)

    def build_secure_prompt(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        workflow: str = "model_call",
    ) -> list[dict[str, str]]:
        """Normalize user content and prepend the non-secret trusted security boundary."""
        secured: list[dict[str, str]] = [
            {"role": "system", "content": GUARDRAIL_SYSTEM_INSTRUCTION}
        ]
        for message in messages:
            role = str(message.get("role") or "user")
            content = str(message.get("content") or "")
            if role == "user":
                decision = self.evaluate_user_input(content, workflow=workflow)
                if decision.should_block:
                    raise GuardrailBlockedError(_blocked_detail(decision.detection))
                content = decision.detection.normalized_text
            secured.append({"role": role, "content": content})
        return secured

    def evaluate_model_output(self, text: str, *, workflow: str = "model_call") -> OutputEvaluation:
        decision = self._evaluate(text, DetectionContext(source="model_output", workflow=workflow))
        if decision.should_block:
            raise GuardrailBlockedError(_blocked_detail(decision.detection))
        return OutputEvaluation(
            text=sanitize_markdown(
                decision.detection.normalized_text,
                allow_http=_allow_http(self._settings),
            ),
            detection=decision.detection,
        )

    def validate_citations(
        self,
        citations: Iterable[dict[str, Any]],
        *,
        retrieved_source_ids: set[str],
        retrieved_chunk_ids: set[str],
    ) -> bool:
        """Allow only citations to sources and chunks actually supplied to the model."""
        for citation in citations:
            source_id = str(citation.get("source_id") or "")
            chunk_id = str(citation.get("chunk_id") or "")
            if source_id not in retrieved_source_ids or chunk_id not in retrieved_chunk_ids:
                return False
        return True

    def sanitize_rendered_output(self, markdown: str) -> str:
        return sanitize_markdown(markdown, allow_http=_allow_http(self._settings))

    def _evaluate(self, text: str, context: DetectionContext) -> GuardrailDecision:
        return decide(self._detector.classify(text, context))


def _blocked_detail(detection: DetectionResult) -> str:
    return f"Guardrail blocked {detection.category}: {', '.join(detection.reasons)}"


def _allow_http(settings: Settings) -> bool:
    return settings.environment.casefold() in {"local", "development", "test"}
