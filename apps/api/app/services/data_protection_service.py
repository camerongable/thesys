"""Deterministic data classification and sanitization before external processing."""

import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.core.redaction import SECRET_VALUE_PATTERNS, redact_payload
from app.security.contracts import DataClassification

SANITIZATION_VERSION = "v1"

_PRESIDIO_ENTITY_TYPES = (
    "CREDIT_CARD",
    "EMAIL_ADDRESS",
    "IBAN_CODE",
    "IP_ADDRESS",
    "PHONE_NUMBER",
    "US_BANK_NUMBER",
    "US_DRIVER_LICENSE",
    "US_PASSPORT",
    "US_SSN",
)
_PRESIDIO_ENTITY_MAP = {
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE_NUMBER",
}
_RESTRICTED_ENTITY_TYPES = frozenset(
    {
        "ACCESS_TOKEN",
        "API_KEY",
        "CREDIT_CARD",
        "IBAN_CODE",
        "URL_CREDENTIAL",
        "US_BANK_NUMBER",
        "US_DRIVER_LICENSE",
        "US_PASSPORT",
        "US_SSN",
    }
)

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


class PresidioPIIAdapter:
    """Run Presidio's local rule recognizers without an implicit model download."""

    def __init__(self) -> None:
        self._analyzer: Any | None = None
        self._anonymizer: Any | None = None
        self._analyzer_unavailable = False
        self._anonymizer_unavailable = False

    def detect(self, text: str) -> list[PIIDetection]:
        analyzer = self._get_analyzer()
        if analyzer is None:
            return []
        try:
            results = analyzer.analyze(
                text=text,
                language="en",
                entities=list(_PRESIDIO_ENTITY_TYPES),
            )
        except Exception:
            return []
        return [
            PIIDetection(
                entity_type=_PRESIDIO_ENTITY_MAP.get(result.entity_type, result.entity_type),
                start=result.start,
                end=result.end,
            )
            for result in results
        ]

    def anonymize(
        self,
        text: str,
        *,
        detections: list[PIIDetection],
        replacements: dict[tuple[int, int], str],
    ) -> str | None:
        anonymizer = self._get_anonymizer()
        if anonymizer is None:
            return None
        try:
            from presidio_analyzer import RecognizerResult
            from presidio_anonymizer.entities import OperatorConfig
        except ImportError:
            return None

        sanitized = text
        for detection in reversed(detections):
            result = RecognizerResult(
                entity_type=detection.entity_type,
                start=detection.start,
                end=detection.end,
                score=1.0,
            )
            sanitized = anonymizer.anonymize(
                text=sanitized,
                analyzer_results=[result],
                operators={
                    detection.entity_type: OperatorConfig(
                        "replace",
                        {"new_value": replacements[(detection.start, detection.end)]},
                    )
                },
            ).text
        return sanitized

    def _get_analyzer(self) -> Any | None:
        if self._analyzer_unavailable:
            return None
        if self._analyzer is not None:
            return self._analyzer
        try:
            import spacy
            from presidio_analyzer import AnalyzerEngine
            from presidio_analyzer.nlp_engine import NlpArtifacts, NlpEngine
            from presidio_analyzer.recognizer_registry import RecognizerRegistry

            class RuleOnlyNlpEngine(NlpEngine):
                def __init__(self) -> None:
                    self._nlp = spacy.blank("en")

                def load(self) -> None:
                    return None

                def is_loaded(self) -> bool:
                    return True

                def process_text(self, value: str, language: str) -> NlpArtifacts:
                    document = self._nlp(value)
                    return NlpArtifacts(
                        entities=[],
                        tokens=document,
                        tokens_indices=[token.idx for token in document],
                        lemmas=[token.lower_ for token in document],
                        nlp_engine=self,
                        language=language,
                    )

                def process_batch(
                    self,
                    values: Iterable[str],
                    language: str,
                    batch_size: int = 1,
                    n_process: int = 1,
                    **_kwargs: object,
                ):
                    del batch_size, n_process
                    for value in values:
                        yield value, self.process_text(value, language)

                def is_stopword(self, word: str, language: str) -> bool:
                    del word, language
                    return False

                def is_punct(self, word: str, language: str) -> bool:
                    del word, language
                    return False

                def get_supported_entities(self) -> list[str]:
                    return []

                def get_supported_languages(self) -> list[str]:
                    return ["en"]

            nlp_engine = RuleOnlyNlpEngine()
            registry = RecognizerRegistry(supported_languages=["en"])
            registry.load_predefined_recognizers(languages=["en"], nlp_engine=nlp_engine)
            self._analyzer = AnalyzerEngine(
                registry=registry,
                nlp_engine=nlp_engine,
                supported_languages=["en"],
            )
        except Exception:
            self._analyzer_unavailable = True
            return None
        return self._analyzer

    def _get_anonymizer(self) -> Any | None:
        if self._anonymizer_unavailable:
            return None
        if self._anonymizer is not None:
            return self._anonymizer
        try:
            from presidio_anonymizer import AnonymizerEngine

            self._anonymizer = AnonymizerEngine()
        except Exception:
            self._anonymizer_unavailable = True
            return None
        return self._anonymizer


class DataProtectionService:
    """Provide deterministic first-pass protection before data leaves ingestion."""

    def __init__(self, presidio: PresidioPIIAdapter | None = None) -> None:
        self._presidio = presidio or PresidioPIIAdapter()

    def classify_text(self, text: str) -> DataClassification:
        entity_types = {detection.entity_type for detection in self.detect_pii(text)}
        if entity_types & _RESTRICTED_ENTITY_TYPES:
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
        detections.extend(self._presidio.detect(text))
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
        del project_id  # Non-ingestion callers redact without persisting a reversible mapping.
        detections = self.detect_pii(text)
        replacements: dict[tuple[int, int], str] = {}
        token_counts: dict[str, int] = {}
        for detection in detections:
            token_counts[detection.entity_type] = token_counts.get(detection.entity_type, 0) + 1
            replacements[(detection.start, detection.end)] = self._replacement(
                detection.entity_type,
                token_counts[detection.entity_type],
            )
        sanitized = self._presidio.anonymize(
            text,
            detections=detections,
            replacements=replacements,
        )
        if sanitized is None:
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

    def authorize_reidentification(self, auth: object) -> bool:
        return getattr(auth, "role", None) == "owner"

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
        if entity_type in _RESTRICTED_ENTITY_TYPES:
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
