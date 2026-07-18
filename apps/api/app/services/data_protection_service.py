"""Deterministic data classification and sanitization before external processing."""

import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from app.core.redaction import SECRET_VALUE_PATTERNS, redact_payload
from app.security.contracts import DataClassification

SANITIZATION_VERSION = "v1"

_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_PHONE_PATTERN = re.compile(
    r"(?<!\w)(?:\+?\d{1,3}[ .-]?)?(?:\(?\d{3}\)?[ .-]?)\d{3}[ .-]\d{4}(?!\w)"
)
_CARD_PATTERN = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_URL_CREDENTIAL_PATTERN = re.compile(r"https?://[^\s/:@]+:[^\s@/]+@[^\s/]+", re.IGNORECASE)
_PERSON_PATTERN = re.compile(r"\b(?:[A-Z][a-z]+\s+){1,2}[A-Z][a-z]+\b")
_NON_PERSON_NAME_WORDS = frozenset(
    {
        "Analysis",
        "Buyer",
        "Coach",
        "Coaching",
        "Customer",
        "Discovery",
        "Evidence",
        "Interview",
        "Market",
        "Notes",
        "Plan",
        "Price",
        "Pricing",
        "Pro",
        "Report",
        "Research",
        "Software",
        "Solo",
        "Starter",
        "Strategy",
        "Studio",
    }
)


@dataclass(frozen=True)
class PIIDetection:
    entity_type: str
    start: int
    end: int


@dataclass(frozen=True)
class SanitizedText:
    text: str
    data_classification: DataClassification
    pii_status: str
    pii_entity_types: tuple[str, ...]
    sanitization_version: str = SANITIZATION_VERSION


class DataProtectionService:
    """Provide deterministic first-pass protection before data leaves ingestion."""

    def classify_text(self, text: str) -> DataClassification:
        entity_types = {detection.entity_type for detection in self.detect_pii(text)}
        if entity_types & {"API_KEY", "ACCESS_TOKEN", "CREDIT_CARD", "URL_CREDENTIAL"}:
            return DataClassification.RESTRICTED
        if entity_types:
            return DataClassification.CONFIDENTIAL
        return DataClassification.INTERNAL

    def detect_pii(self, text: str) -> list[PIIDetection]:
        detections: list[PIIDetection] = []
        for pattern in SECRET_VALUE_PATTERNS:
            detections.extend(
                PIIDetection(self._secret_entity_type(match.group()), match.start(), match.end())
                for match in pattern.finditer(text)
            )
        for pattern, entity_type in (
            (_URL_CREDENTIAL_PATTERN, "URL_CREDENTIAL"),
            (_EMAIL_PATTERN, "EMAIL"),
            (_PHONE_PATTERN, "PHONE_NUMBER"),
            (_CARD_PATTERN, "CREDIT_CARD"),
            (_PERSON_PATTERN, "PERSON"),
        ):
            for match in pattern.finditer(text):
                if entity_type == "PERSON" and not self._is_person_name(match.group()):
                    continue
                detections.append(PIIDetection(entity_type, match.start(), match.end()))
        return self._non_overlapping(detections)

    def redact_for_model(self, text: str, *, project_id: uuid.UUID | None = None) -> str:
        return self.create_searchable_copy(text, project_id=project_id).text

    def redact_for_trace(self, value: object, *, project_id: uuid.UUID | None = None) -> object:
        return self._redact_trace_value(
            redact_payload(value, redact_emails=True, max_string_length=2000),
            project_id=project_id,
        )

    def create_searchable_copy(
        self,
        text: str,
        *,
        project_id: uuid.UUID | None = None,
    ) -> SanitizedText:
        del project_id  # Tokens intentionally remain project-local once encrypted mappings land.
        detections = self.detect_pii(text)
        replacements: dict[tuple[int, int], str] = {}
        token_counts: dict[str, int] = {}
        for detection in detections:
            token_counts[detection.entity_type] = token_counts.get(detection.entity_type, 0) + 1
            replacements[(detection.start, detection.end)] = self._replacement(
                detection.entity_type,
                token_counts[detection.entity_type],
            )
        sanitized = text
        for detection in reversed(detections):
            replacement = replacements[(detection.start, detection.end)]
            sanitized = sanitized[: detection.start] + replacement + sanitized[detection.end :]
        entity_types = tuple(sorted({detection.entity_type for detection in detections}))
        return SanitizedText(
            text=sanitized,
            data_classification=self.classify_text(text),
            pii_status="redacted" if detections else "none_detected",
            pii_entity_types=entity_types,
        )

    def tokenize_identifiers(self, text: str, *, project_id: uuid.UUID) -> str:
        return self.create_searchable_copy(text, project_id=project_id).text

    def authorize_reidentification(self, *_args: object, **_kwargs: object) -> bool:
        return False

    @staticmethod
    def is_source_approved(metadata: dict[str, object] | None) -> bool:
        security = (metadata or {}).get("security")
        if not isinstance(security, dict):
            return False
        return (
            security.get("security_status") == "approved"
            and security.get("classification_status") == "approved"
        )

    @staticmethod
    def is_chunk_retrievable(metadata: dict[str, object] | None) -> bool:
        security = (metadata or {}).get("security")
        if not isinstance(security, dict):
            return False
        return (
            security.get("retrieval_allowed") is True
            and security.get("source_security_status") == "approved"
        )

    @staticmethod
    def _secret_entity_type(value: str) -> str:
        lowered = value.casefold()
        return "ACCESS_TOKEN" if "token" in lowered or "bearer" in lowered else "API_KEY"

    @staticmethod
    def _replacement(entity_type: str, ordinal: int) -> str:
        if entity_type in {"API_KEY", "ACCESS_TOKEN", "CREDIT_CARD", "URL_CREDENTIAL"}:
            return "[REDACTED_SECRET]"
        return f"<{entity_type}_{ordinal:03d}>"

    @staticmethod
    def _is_person_name(value: str) -> bool:
        return not any(word in _NON_PERSON_NAME_WORDS for word in value.split())

    @staticmethod
    def _non_overlapping(detections: Iterable[PIIDetection]) -> list[PIIDetection]:
        selected: list[PIIDetection] = []
        ordered = sorted(detections, key=lambda item: (item.start, -(item.end - item.start)))
        for detection in ordered:
            if selected and detection.start < selected[-1].end:
                continue
            selected.append(detection)
        return selected

    def _redact_trace_value(self, value: object, *, project_id: uuid.UUID | None) -> object:
        if isinstance(value, dict):
            return {
                str(key): self._redact_trace_value(item, project_id=project_id)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._redact_trace_value(item, project_id=project_id) for item in value]
        if isinstance(value, str):
            return self.create_searchable_copy(value, project_id=project_id).text
        return value


data_protection_service = DataProtectionService()
