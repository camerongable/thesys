"""Shared authorization and source-trust controls for evidence retrieval."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from app.db.models import EvidenceChunk, EvidenceSource
from app.security.contracts import DataClassification

if TYPE_CHECKING:
    from app.core.auth import AuthContext


RETRIEVAL_SECURITY_POLICY_VERSION = "v2"

_CLASSIFICATION_RANK = {
    DataClassification.PUBLIC: 0,
    DataClassification.INTERNAL: 1,
    DataClassification.CONFIDENTIAL: 2,
    DataClassification.RESTRICTED: 3,
}
_ROLE_CLEARANCE = {
    "viewer": DataClassification.INTERNAL,
    "editor": DataClassification.CONFIDENTIAL,
    "admin": DataClassification.RESTRICTED,
    "owner": DataClassification.RESTRICTED,
}


@dataclass(frozen=True)
class RetrievalSecurityPolicy:
    """Pre-ranking access policy shared by vector and fallback retrieval paths."""

    workspace_id: uuid.UUID
    principal_clearance: DataClassification
    minimum_source_trust_score: float

    @classmethod
    def for_auth(
        cls,
        auth: AuthContext,
        *,
        minimum_source_trust_score: float,
    ) -> RetrievalSecurityPolicy:
        return cls(
            workspace_id=auth.workspace_id,
            principal_clearance=_ROLE_CLEARANCE.get(
                auth.role,
                DataClassification.INTERNAL,
            ),
            minimum_source_trust_score=minimum_source_trust_score,
        )

    @property
    def allowed_classifications(self) -> tuple[str, ...]:
        return tuple(
            classification.value
            for classification, rank in _CLASSIFICATION_RANK.items()
            if rank <= _CLASSIFICATION_RANK[self.principal_clearance]
        )

    def sql_conditions(self, project_id: uuid.UUID) -> list[object]:
        """Return database predicates that must execute before ranking."""
        return [
            EvidenceChunk.workspace_id == self.workspace_id,
            EvidenceChunk.project_id == project_id,
            EvidenceSource.workspace_id == self.workspace_id,
            EvidenceSource.project_id == project_id,
            EvidenceSource.ingestion_status == "ready",
            EvidenceSource.source_metadata["security"]["security_status"].as_string()
            == "approved",
            EvidenceSource.source_metadata["security"]["classification_status"].as_string()
            == "approved",
            EvidenceSource.source_metadata["security"]["data_classification"]
            .as_string()
            .in_(self.allowed_classifications),
            EvidenceSource.source_metadata["source_trust"]["security_status"].as_string()
            == "approved",
            EvidenceSource.source_metadata["source_trust"]["trust_score"].as_float()
            >= self.minimum_source_trust_score,
            EvidenceChunk.chunk_metadata["security"]["data_classification"]
            .as_string()
            .in_(self.allowed_classifications),
            EvidenceChunk.chunk_metadata["security"]["retrieval_allowed"].as_boolean().is_(
                True
            ),
            EvidenceChunk.chunk_metadata["security"]["source_security_status"].as_string()
            == "approved",
            EvidenceSource.credibility_score >= Decimal(str(self.minimum_source_trust_score)),
        ]

    def allows(self, *, source: EvidenceSource, chunk: EvidenceChunk) -> bool:
        """Mirror SQL eligibility checks for candidates handled in Python."""
        source_security = _security_metadata(source.source_metadata)
        source_trust = _source_trust_metadata(source.source_metadata)
        chunk_security = _security_metadata(chunk.chunk_metadata)
        if source.workspace_id != self.workspace_id or chunk.workspace_id != self.workspace_id:
            return False
        if source.project_id != chunk.project_id or source.ingestion_status != "ready":
            return False
        if source_security.get("security_status") != "approved":
            return False
        if source_security.get("classification_status") != "approved":
            return False
        if not self._classification_allowed(source_security.get("data_classification")):
            return False
        if source_trust.get("security_status") != "approved":
            return False
        try:
            trust_score = float(source_trust["trust_score"])
        except (KeyError, TypeError, ValueError):
            return False
        if trust_score < self.minimum_source_trust_score:
            return False
        if not self._classification_allowed(chunk_security.get("data_classification")):
            return False
        if chunk_security.get("retrieval_allowed") is not True:
            return False
        if chunk_security.get("source_security_status") != "approved":
            return False
        if source.credibility_score is None:
            return False
        return float(source.credibility_score) >= self.minimum_source_trust_score

    def _classification_allowed(self, value: object) -> bool:
        try:
            classification = DataClassification(str(value))
        except ValueError:
            return False
        return _CLASSIFICATION_RANK[classification] <= _CLASSIFICATION_RANK[
            self.principal_clearance
        ]


def _security_metadata(metadata: object) -> dict[str, object]:
    if not isinstance(metadata, dict):
        return {}
    security = metadata.get("security")
    return security if isinstance(security, dict) else {}


def _source_trust_metadata(metadata: object) -> dict[str, object]:
    if not isinstance(metadata, dict):
        return {}
    source_trust = metadata.get("source_trust")
    return source_trust if isinstance(source_trust, dict) else {}
