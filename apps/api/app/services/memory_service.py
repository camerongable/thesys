"""Typed project-memory management for AI workflows.

Memory is modeled as inspectable domain data rather than chat transcript text.
Items can be semantic, episodic, procedural, preference, working, or project
memory, and each workflow selects only the memory types it is allowed to use.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, normalized_role, require_permission
from app.core.config import Settings, get_settings
from app.core.redaction import redact_payload, redact_text
from app.db.models import Assumption, ProjectMemoryItem, Risk
from app.features.memory import compaction as memory_compaction
from app.features.memory import inspection as memory_inspection
from app.features.memory import review as memory_review
from app.features.memory import security_policy as memory_security_policy
from app.features.memory import selection_policy as memory_selection_policy
from app.features.policy.opa import (
    OpaPolicyClient,
    OpaPolicyDecision,
    OpaPolicyUnavailableError,
    opa_policy_enforced,
    require_opa_decision,
    unavailable_opa_policy_denial,
)
from app.features.retrieval.security_policy import RetrievalSecurityPolicy
from app.schemas.memory import MemoryType, MemoryWritePolicy
from app.security.contracts import DataClassification
from app.services import governance_service, project_service
from app.services.data_protection_service import data_protection_service

WORKING_MEMORY_TTL = timedelta(hours=8)
EPISODIC_MEMORY_TTL = timedelta(days=30)
WORKFLOW_MEMORY_TYPES: dict[str, set[str]] = {
    "assumption_extraction": {"semantic", "project", "preference"},
    "guide_chat": {"working", "semantic", "project", "preference"},
    "agentic_research": {"episodic", "semantic", "project", "procedural"},
    "opportunity_brief": {"semantic", "project", "episodic", "preference"},
    "competitor_analysis": {"semantic", "project", "episodic"},
    "validation_plan": {"semantic", "project", "procedural", "preference"},
    "validation_planning": {"semantic", "project", "procedural", "preference"},
    "validation_result_interpretation": {"episodic", "semantic", "project", "preference"},
    "decision_recommendation": {"episodic", "semantic", "project", "preference"},
}
WORKFLOW_STALE_HISTORY_ALLOWED = {
    "agentic_research",
    "validation_result_interpretation",
    "decision_recommendation",
}
_CLASSIFICATION_RANK = {
    DataClassification.PUBLIC: 0,
    DataClassification.INTERNAL: 1,
    DataClassification.CONFIDENTIAL: 2,
    DataClassification.RESTRICTED: 3,
}
_MEMORY_TYPE_BASE_CLASSIFICATION = {
    "working": DataClassification.INTERNAL,
    "preference": DataClassification.INTERNAL,
    "episodic": DataClassification.CONFIDENTIAL,
    "semantic": DataClassification.CONFIDENTIAL,
    "project": DataClassification.CONFIDENTIAL,
    "procedural": DataClassification.CONFIDENTIAL,
}
_TRUSTED_DERIVED_PROJECTION = object()
MemoryPolicySource = Literal["user", "agent", "system"]
MemoryPolicyOperation = Literal[
    "content_write",
    "approve",
    "reject",
    "mark_stale",
    "archive",
    "merge_duplicates",
    "resolve_conflict",
]

MemorySelection = memory_selection_policy.MemorySelection
_memory_exclusion_reason = memory_selection_policy.memory_exclusion_reason
_excluded = memory_selection_policy.excluded
_conflict_key = memory_selection_policy.conflict_key
_normalize_text = memory_selection_policy.normalize_text
serialize_memory_item = memory_inspection.serialize_memory_item
_compacted_memory_payload = memory_compaction.compacted_memory_payload
_reviewed_memory_metadata = memory_review.reviewed_memory_metadata
_memory_review_audit_metadata = memory_review.memory_review_audit_metadata


def list_memory(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    memory_type: MemoryType | None = None,
    include_stale: bool = False,
    limit: int = 50,
) -> list[ProjectMemoryItem]:
    """List typed project memory with stale/expired records hidden by default."""
    project_service.get_project(db, auth, project_id)
    session_scope = _working_memory_session_scope(auth)
    allowed_data_classifications = _allowed_memory_data_classifications(auth)
    stmt = select(ProjectMemoryItem).where(
        ProjectMemoryItem.workspace_id == auth.workspace_id,
        ProjectMemoryItem.project_id == project_id,
    )
    if memory_type is not None:
        stmt = stmt.where(ProjectMemoryItem.memory_type == memory_type)
    if not include_stale:
        stmt = stmt.where(
            *memory_security_policy.memory_recall_sql_conditions(
                now=datetime.now(UTC),
                working_memory_session_scope=session_scope,
                allowed_data_classifications=allowed_data_classifications,
            )
        )
    items = db.scalars(
        stmt.order_by(ProjectMemoryItem.updated_at.desc()).limit(min(limit, 100))
    )
    if include_stale:
        return [
            item
            for item in items
            if memory_security_policy.working_memory_visible_to_session(
                item,
                session_scope=session_scope,
            )
            and memory_security_policy.memory_visible_to_clearance(
                item,
                allowed_data_classifications=allowed_data_classifications,
            )
        ]
    return [
        item
        for item in items
        if memory_security_policy.memory_recall_exclusion_reason(
            item,
            now=datetime.now(UTC),
            working_memory_session_scope=session_scope,
            allowed_data_classifications=allowed_data_classifications,
        )
        is None
    ]


def select_memory_for_workflow(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    workflow_type: str,
    limit: int = 20,
) -> list[ProjectMemoryItem]:
    """Select memory types that are relevant for a specific AI workflow."""
    allowed_types = WORKFLOW_MEMORY_TYPES.get(
        workflow_type,
        {"semantic", "project", "episodic", "preference"},
    )
    project_service.get_project(db, auth, project_id)
    session_scope = _working_memory_session_scope(auth)
    allowed_data_classifications = _allowed_memory_data_classifications(auth)
    items = list(
        db.scalars(
            select(ProjectMemoryItem)
            .where(
                ProjectMemoryItem.workspace_id == auth.workspace_id,
                ProjectMemoryItem.project_id == project_id,
                ProjectMemoryItem.memory_type.in_(allowed_types),
                *memory_security_policy.memory_recall_sql_conditions(
                    now=datetime.now(UTC),
                    working_memory_session_scope=session_scope,
                    allowed_data_classifications=allowed_data_classifications,
                ),
            )
            .order_by(ProjectMemoryItem.updated_at.desc())
            .limit(min(limit, 100))
        )
    )
    return [
        item
        for item in items
        if memory_security_policy.memory_recall_exclusion_reason(
            item,
            now=datetime.now(UTC),
            working_memory_session_scope=session_scope,
            allowed_data_classifications=allowed_data_classifications,
        )
        is None
    ]


def select_memory_for_context(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    workflow_type: str,
    limit: int = 20,
) -> MemorySelection:
    """Select workflow memory and explain exclusions for context inspection."""
    allowed_types = WORKFLOW_MEMORY_TYPES.get(
        workflow_type,
        {"semantic", "project", "episodic", "preference"},
    )
    include_stale_history = workflow_type in WORKFLOW_STALE_HISTORY_ALLOWED
    now = datetime.now(UTC)
    project_service.get_project(db, auth, project_id)
    session_scope = _working_memory_session_scope(auth)
    allowed_data_classifications = _allowed_memory_data_classifications(auth)
    all_items = list(
        db.scalars(
            select(ProjectMemoryItem)
            .where(
                ProjectMemoryItem.workspace_id == auth.workspace_id,
                ProjectMemoryItem.project_id == project_id,
            )
            .order_by(ProjectMemoryItem.updated_at.desc())
            .limit(200)
        )
    )
    all_items = [
        item
        for item in all_items
        if memory_security_policy.working_memory_visible_to_session(
            item,
            session_scope=session_scope,
        )
    ]
    eligible_items = list(
        db.scalars(
            select(ProjectMemoryItem)
            .where(
                ProjectMemoryItem.workspace_id == auth.workspace_id,
                ProjectMemoryItem.project_id == project_id,
                ProjectMemoryItem.memory_type.in_(allowed_types),
                *memory_security_policy.memory_recall_sql_conditions(
                    now=now,
                    working_memory_session_scope=session_scope,
                    allowed_data_classifications=allowed_data_classifications,
                ),
            )
            .order_by(ProjectMemoryItem.updated_at.desc())
            .limit(min(limit, 100))
        )
    )
    conflicts = detect_memory_conflicts(db, auth, project_id, mark=True, commit=False)
    selected = [
        item
        for item in eligible_items
        if _memory_exclusion_reason(
            item,
            allowed_types=allowed_types,
            include_stale_history=include_stale_history,
            now=now,
            working_memory_session_scope=session_scope,
            allowed_data_classifications=allowed_data_classifications,
        )
        is None
    ]
    excluded: list[dict[str, Any]] = []
    for item in all_items:
        reason = _memory_exclusion_reason(
            item,
            allowed_types=allowed_types,
            include_stale_history=include_stale_history,
            now=now,
            working_memory_session_scope=session_scope,
            allowed_data_classifications=allowed_data_classifications,
        )
        if reason is not None:
            excluded.append(_excluded(item, reason))
    return MemorySelection(
        selected=selected,
        excluded=excluded,
        conflicts=conflicts,
        policy={
            "workflow_type": workflow_type,
            "allowed_memory_types": sorted(allowed_types),
            "include_stale_history": include_stale_history,
            "limit": min(limit, 100),
        },
    )


def inspect_memory(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    workflow_type: str = "guide_chat",
) -> dict[str, Any]:
    """Return memory selected, excluded, proposed, and conflicted for Inspect."""
    selection = select_memory_for_context(
        db,
        auth,
        project_id,
        workflow_type=workflow_type,
        limit=50,
    )
    proposed = [
        item
        for item in list_memory(db, auth, project_id, include_stale=True, limit=100)
        if item.status == "proposed"
    ]
    return memory_inspection.inspect_payload(
        workflow_type=workflow_type,
        selection=selection,
        proposed=proposed,
    )


def explain_memory(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    memory_id: uuid.UUID,
) -> dict[str, Any]:
    """Return an inspectable explanation of why a memory item exists."""
    item = get_memory_item(db, auth, project_id, memory_id)
    return memory_inspection.explanation_payload(item)


def get_memory_item(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    memory_id: uuid.UUID,
) -> ProjectMemoryItem:
    item = db.scalar(
        select(ProjectMemoryItem).where(
            ProjectMemoryItem.workspace_id == auth.workspace_id,
            ProjectMemoryItem.project_id == project_id,
            ProjectMemoryItem.id == memory_id,
        )
    )
    if item is None or not memory_security_policy.working_memory_visible_to_session(
        item,
        session_scope=_working_memory_session_scope(auth),
    ) or not memory_security_policy.memory_visible_to_clearance(
        item,
        allowed_data_classifications=_allowed_memory_data_classifications(auth),
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory item not found.")
    return item


def upsert_memory_item(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    memory_type: MemoryType,
    write_policy: MemoryWritePolicy,
    title: str,
    summary: str,
    content: dict[str, Any],
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    source_entity_type: str | None = None,
    source_entity_id: uuid.UUID | None = None,
    provenance_metadata: dict[str, Any] | None = None,
    confidence_score: Decimal | None = None,
    status_value: str = "active",
    expires_at: datetime | None = None,
    _trusted_projection: object | None = None,
    settings: Settings | None = None,
) -> ProjectMemoryItem:
    """Create or update a typed memory item under the project's governance model."""
    project_service.get_project(db, auth, project_id)
    expires_at = _effective_memory_expiry(memory_type, expires_at)
    data_classification = _memory_data_classification(memory_type, title, summary, content)
    safe_title = redact_text(title, redact_emails=True)
    safe_summary = redact_text(summary, redact_emails=True)
    safe_content = redact_payload(content, redact_emails=True)
    safe_provenance = memory_security_policy.secure_memory_metadata(
        redact_payload(provenance_metadata or {}, redact_emails=True),
        content=safe_content,
        summary=safe_summary,
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        write_policy=write_policy,
        expires_at=expires_at,
        data_classification=data_classification,
        trusted_derived_projection=_trusted_projection is _TRUSTED_DERIVED_PROJECTION,
    )
    if memory_type == "working":
        if not memory_security_policy.working_memory_write_allowed(write_policy):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Working memory requires the transient write policy.",
            )
        session_scope = _working_memory_session_scope(auth)
        if session_scope is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Working memory requires an authenticated session.",
            )
        safe_provenance[memory_security_policy.WORKING_MEMORY_SESSION_SCOPE_KEY] = session_scope
    if memory_type == "episodic":
        if not memory_security_policy.episodic_memory_write_allowed(
            safe_provenance,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Episodic memory requires source provenance and a timezone-aware "
                    "event timestamp."
                ),
            )
        safe_provenance["event_at"] = memory_security_policy.normalized_episodic_event_timestamp(
            safe_provenance
        )
    if memory_type == "semantic" and not memory_security_policy.semantic_memory_write_allowed(
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        confidence_score=confidence_score,
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Semantic memory requires source provenance and confidence from zero to one.",
        )
    if memory_type == "preference" and not memory_security_policy.preference_memory_write_allowed(
        safe_provenance,
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        confirmed_user_id=str(auth.user_id),
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Preference memory requires explicit confirmation from the authenticated user.",
        )
    if memory_type == "procedural" and not memory_security_policy.procedural_memory_write_allowed(
        safe_provenance,
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        write_policy=write_policy,
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Procedural memory must be code-owned and versioned.",
        )
    policy_decision = _authorize_opa_memory_write(
        db,
        auth,
        settings or get_settings(),
        project_id,
        memory_type=memory_type,
        write_policy=write_policy,
        status_value=status_value,
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        provenance_metadata=safe_provenance,
        operation="content_write",
    )
    if policy_decision is not None and policy_decision.requires_approval:
        status_value = "proposed"
    if memory_security_policy.requires_memory_proposal(
        safe_provenance,
        source_entity_type=source_entity_type,
        status_value=status_value,
    ):
        status_value = "proposed"
    existing = None
    conflicting_active: ProjectMemoryItem | None = None
    if entity_type and entity_id:
        existing = db.scalar(
            select(ProjectMemoryItem).where(
                ProjectMemoryItem.workspace_id == auth.workspace_id,
                ProjectMemoryItem.project_id == project_id,
                ProjectMemoryItem.entity_type == entity_type,
                ProjectMemoryItem.entity_id == entity_id,
                ProjectMemoryItem.memory_type == memory_type,
            )
        )
    if existing is not None and not memory_security_policy.memory_visible_to_clearance(
        existing,
        allowed_data_classifications=_allowed_memory_data_classifications(auth),
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory item not found.")
    if existing is not None and status_value == "proposed" and existing.status == "active":
        if (existing.provenance_metadata or {}).get("content_hash") == safe_provenance[
            "content_hash"
        ]:
            return existing
        conflicting_active = existing
        existing = None
    if existing is None:
        existing = ProjectMemoryItem(
            workspace_id=auth.workspace_id,
            project_id=project_id,
            memory_type=memory_type,
            write_policy=write_policy,
            entity_type=entity_type,
            entity_id=entity_id,
            source_entity_type=source_entity_type,
            source_entity_id=source_entity_id,
            title=safe_title[:255],
            summary=safe_summary,
            content=safe_content,
            provenance_metadata=safe_provenance,
            confidence_score=confidence_score,
            status=status_value,
            expires_at=expires_at,
            created_by=auth.user_id,
        )
        db.add(existing)
    else:
        existing.write_policy = write_policy
        existing.source_entity_type = source_entity_type or existing.source_entity_type
        existing.source_entity_id = source_entity_id or existing.source_entity_id
        existing.title = safe_title[:255]
        existing.summary = safe_summary
        existing.content = safe_content
        existing.provenance_metadata = safe_provenance or existing.provenance_metadata
        existing.confidence_score = confidence_score
        existing.status = status_value
        existing.expires_at = expires_at
    db.flush()
    _record_opa_memory_authorization(
        db,
        auth,
        project_id=project_id,
        item=existing,
        operation="content_write",
        affected_records=1,
        policy_decision=policy_decision,
    )
    if conflicting_active is not None:
        _link_memory_proposal_conflict(
            project_id=project_id,
            active=conflicting_active,
            proposal=existing,
        )
    return existing


def _authorize_opa_memory_write(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    *,
    memory_type: MemoryType,
    write_policy: MemoryWritePolicy,
    status_value: str,
    source_entity_type: str | None,
    source_entity_id: uuid.UUID | None,
    provenance_metadata: dict[str, Any],
    operation: MemoryPolicyOperation,
    affected_records: int = 1,
    request_source: MemoryPolicySource | None = None,
    memory_id: uuid.UUID | None = None,
) -> OpaPolicyDecision | None:
    """Authorize memory content changes before a record is created or updated."""
    if not opa_policy_enforced(settings):
        return None

    origin = str(provenance_metadata.get("origin") or "agent")
    source = request_source or _opa_memory_request_source(
        origin,
        trusted_projection=bool(provenance_metadata.get("trusted_projection")),
    )
    data_classification = str(
        provenance_metadata.get("data_classification", DataClassification.CONFIDENTIAL.value)
    )
    policy_input = {
        "principal": {
            "user_id": str(auth.user_id),
            "workspace_id": str(auth.workspace_id),
            "role": normalized_role(auth.role),
            "authentication_method": auth.principal.authentication_method,
        },
        "project": {
            "id": str(project_id),
            "workspace_id": str(auth.workspace_id),
            "classification": data_classification,
        },
        "memory": {
            "memory_type": memory_type,
            "write_policy": write_policy,
            "requested_status": status_value,
            "operation": operation,
            "affected_records": affected_records,
            "source_entity_type": source_entity_type,
            "source_entity_id": str(source_entity_id) if source_entity_id is not None else None,
            "trusted_projection": bool(provenance_metadata.get("trusted_projection")),
        },
        "request": {
            "source": source,
            "workflow_id": provenance_metadata.get("workflow_id"),
            "data_classification": data_classification,
        },
    }
    try:
        decision = OpaPolicyClient(settings).evaluate("memory_write", policy_input)
    except OpaPolicyUnavailableError as exc:
        denial = unavailable_opa_policy_denial(exc)
        _audit_opa_memory_denial(
            db,
            auth,
            project_id=project_id,
            memory_type=memory_type,
            write_policy=write_policy,
            operation=operation,
            affected_records=affected_records,
            memory_id=memory_id,
            actor_type=source,
            reason="opa_policy_unavailable",
            detail=denial.detail,
            provenance_metadata=provenance_metadata,
        )
        db.commit()
        raise denial from exc
    try:
        approved_decision = require_opa_decision(decision)
    except HTTPException as exc:
        _audit_opa_memory_denial(
            db,
            auth,
            project_id=project_id,
            memory_type=memory_type,
            write_policy=write_policy,
            operation=operation,
            affected_records=affected_records,
            memory_id=memory_id,
            actor_type=source,
            reason="opa_policy_denied",
            detail=str(exc.detail),
            provenance_metadata=provenance_metadata,
            policy_decision=decision,
        )
        db.commit()
        raise
    if affected_records > approved_decision.max_records:
        detail = "Policy record limit does not permit this memory mutation."
        _audit_opa_memory_denial(
            db,
            auth,
            project_id=project_id,
            memory_type=memory_type,
            write_policy=write_policy,
            operation=operation,
            affected_records=affected_records,
            memory_id=memory_id,
            actor_type=source,
            reason="opa_record_limit_exceeded",
            detail=detail,
            provenance_metadata=provenance_metadata,
            policy_decision=approved_decision,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
    return approved_decision


def _opa_memory_request_source(
    origin: str,
    *,
    trusted_projection: bool,
) -> MemoryPolicySource:
    if origin == "user":
        return "user"
    if origin == "system" or (origin == "derived" and trusted_projection):
        return "system"
    return "agent"


def _memory_audit_actor_type(
    provenance_metadata: dict[str, Any],
) -> MemoryPolicySource:
    return _opa_memory_request_source(
        str(provenance_metadata.get("origin") or "agent"),
        trusted_projection=bool(provenance_metadata.get("trusted_projection")),
    )


def _audit_opa_memory_denial(
    db: Session,
    auth: AuthContext,
    *,
    project_id: uuid.UUID,
    memory_type: MemoryType,
    write_policy: MemoryWritePolicy,
    operation: MemoryPolicyOperation,
    affected_records: int,
    memory_id: uuid.UUID | None,
    actor_type: MemoryPolicySource,
    reason: str,
    detail: str | None,
    provenance_metadata: dict[str, Any],
    policy_decision: OpaPolicyDecision | None = None,
) -> None:
    governance_service.record_audit_event(
        db,
        auth,
        event_type="memory_write_denied",
        actor_type=actor_type,
        project_id=project_id,
        entity_type="project_memory_item",
        entity_id=memory_id,
        risk_level="medium",
        summary=f"Denied {memory_type} memory write.",
        metadata={
            "memory_type": memory_type,
            "write_policy": write_policy,
            "operation": operation,
            "affected_records": affected_records,
            "reason": reason,
            "detail": detail,
            "policy_decision": _opa_decision_metadata(policy_decision),
        },
    )


def _record_opa_memory_authorization(
    db: Session,
    auth: AuthContext,
    *,
    project_id: uuid.UUID,
    item: ProjectMemoryItem,
    operation: MemoryPolicyOperation,
    affected_records: int,
    policy_decision: OpaPolicyDecision | None,
    actor_type: MemoryPolicySource | None = None,
) -> None:
    if policy_decision is None:
        return
    governance_service.record_audit_event(
        db,
        auth,
        event_type="memory_write_authorized",
        actor_type=actor_type or _memory_audit_actor_type(item.provenance_metadata or {}),
        project_id=project_id,
        entity_type="project_memory_item",
        entity_id=item.id,
        risk_level="medium",
        summary=f"Authorized {operation} for {item.memory_type} memory.",
        metadata={
            "memory_type": item.memory_type,
            "write_policy": item.write_policy,
            "status": item.status,
            "operation": operation,
            "affected_records": affected_records,
            "policy_decision": _opa_decision_metadata(policy_decision),
        },
    )


def _authorize_opa_memory_lifecycle(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    item: ProjectMemoryItem,
    *,
    operation: MemoryPolicyOperation,
    affected_records: int = 1,
    settings: Settings | None = None,
) -> OpaPolicyDecision | None:
    return _authorize_opa_memory_write(
        db,
        auth,
        settings or get_settings(),
        project_id,
        memory_type=item.memory_type,
        write_policy=item.write_policy,
        status_value=item.status,
        source_entity_type=item.source_entity_type,
        source_entity_id=item.source_entity_id,
        provenance_metadata=item.provenance_metadata or {},
        operation=operation,
        affected_records=affected_records,
        request_source="user",
        memory_id=item.id,
    )


def _opa_decision_metadata(decision: OpaPolicyDecision | None) -> dict[str, Any] | None:
    if decision is None:
        return None
    return {
        "allow": decision.allow,
        "requires_approval": decision.requires_approval,
        "reason": decision.reason,
        "allowed_scopes": list(decision.allowed_scopes),
        "max_records": decision.max_records,
    }


def propose_preference_memory(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    title: str,
    summary: str,
    content: dict[str, Any],
    source: str = "user_preference",
) -> ProjectMemoryItem:
    """Create an approval-gated preference memory proposal."""
    require_permission(auth, "run_research")
    item = upsert_memory_item(
        db,
        auth,
        project_id,
        memory_type="preference",
        write_policy="approval_required",
        title=title,
        summary=summary,
        content=content or {"preference": summary},
        source_entity_type="user_preference",
        source_entity_id=auth.user_id,
        provenance_metadata={
            "source": source,
            "origin": "user",
            "proposal_kind": "preference_capture",
            "requires_human_approval": True,
            "explicit_user_confirmation": True,
            "confirmed_by_user_id": str(auth.user_id),
            "confirmed_at": datetime.now(UTC).isoformat(),
        },
        status_value="proposed",
    )
    db.commit()
    db.refresh(item)
    return item


def propose_compacted_memory(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    workflow_type: str,
    memory_type: MemoryType = "semantic",
    source_memory_ids: list[uuid.UUID] | None = None,
    title: str | None = None,
) -> ProjectMemoryItem:
    """Create an approval-gated compacted-memory candidate with provenance."""
    require_permission(auth, "run_research")
    source_items = _compaction_source_items(
        db,
        auth,
        project_id,
        workflow_type=workflow_type,
        source_memory_ids=source_memory_ids or [],
    )
    if not source_items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No source memory items are eligible for compaction.",
        )
    compacted = memory_compaction.compacted_memory_payload(
        workflow_type=workflow_type,
        source_items=source_items,
        title=title,
    )
    item = upsert_memory_item(
        db,
        auth,
        project_id,
        memory_type=memory_type,
        write_policy="approval_required",
        title=compacted.title,
        summary=compacted.summary,
        content=compacted.content,
        source_entity_type="project_memory_item",
        source_entity_id=source_items[0].id,
        provenance_metadata=compacted.provenance_metadata,
        confidence_score=min(
            (item.confidence_score or Decimal("0") for item in source_items),
            default=Decimal("0"),
        ),
        status_value="proposed",
    )
    db.commit()
    db.refresh(item)
    return item


def approve_memory_proposal(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    memory_id: uuid.UUID,
    *,
    settings: Settings | None = None,
) -> ProjectMemoryItem:
    """Promote proposed memory to active memory after human review."""
    require_permission(auth, "approve_memory_updates")
    item = get_memory_item(db, auth, project_id, memory_id)
    if item.status != "proposed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only proposed memory can be approved.",
        )
    conflicting_active_items = _conflicting_active_memory_items(db, auth, project_id, item)
    affected_records = 1 + len(conflicting_active_items)
    policy_decision = _authorize_opa_memory_lifecycle(
        db,
        auth,
        project_id,
        item,
        operation="approve",
        affected_records=affected_records,
        settings=settings,
    )
    item.status = "active"
    reviewed_at = datetime.now(UTC)
    item.provenance_metadata = _reviewed_memory_metadata(
        item.provenance_metadata,
        status="approved",
        user_id=auth.user_id,
        reviewed_at=reviewed_at,
    )
    item.provenance_metadata = memory_security_policy.secure_memory_metadata(
        item.provenance_metadata,
        content=item.content,
        summary=item.summary,
        source_entity_type=item.source_entity_type,
        source_entity_id=item.source_entity_id,
        write_policy=item.write_policy,
        expires_at=item.expires_at,
    )
    resolution_metadata = {
        "conflict_resolved_by_user_id": str(auth.user_id),
        "conflict_resolved_at": reviewed_at.isoformat(),
    }
    item.provenance_metadata = {**item.provenance_metadata, **resolution_metadata}
    for active_item in conflicting_active_items:
        active_item.status = "superseded"
        active_item.superseded_by_id = item.id
        active_item.provenance_metadata = {
            **(active_item.provenance_metadata or {}),
            **resolution_metadata,
        }
    _record_opa_memory_authorization(
        db,
        auth,
        project_id=project_id,
        item=item,
        operation="approve",
        affected_records=affected_records,
        policy_decision=policy_decision,
        actor_type="user",
    )
    governance_service.record_audit_event(
        db,
        auth,
        event_type="memory_update_approved",
        actor_type="user",
        project_id=project_id,
        entity_type="project_memory_item",
        entity_id=item.id,
        risk_level="medium",
        summary=f"Approved proposed {item.memory_type} memory.",
        metadata=_memory_review_audit_metadata(item, status="approved"),
    )
    db.commit()
    db.refresh(item)
    return item


def reject_memory_proposal(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    memory_id: uuid.UUID,
    *,
    settings: Settings | None = None,
) -> ProjectMemoryItem:
    """Archive proposed memory after human rejection while preserving auditability."""
    require_permission(auth, "approve_memory_updates")
    item = get_memory_item(db, auth, project_id, memory_id)
    if item.status != "proposed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only proposed memory can be rejected.",
        )
    policy_decision = _authorize_opa_memory_lifecycle(
        db,
        auth,
        project_id,
        item,
        operation="reject",
        settings=settings,
    )
    item.status = "archived"
    reviewed_at = datetime.now(UTC)
    item.provenance_metadata = _reviewed_memory_metadata(
        item.provenance_metadata,
        status="rejected",
        user_id=auth.user_id,
        reviewed_at=reviewed_at,
    )
    _record_opa_memory_authorization(
        db,
        auth,
        project_id=project_id,
        item=item,
        operation="reject",
        affected_records=1,
        policy_decision=policy_decision,
        actor_type="user",
    )
    governance_service.record_audit_event(
        db,
        auth,
        event_type="memory_update_rejected",
        actor_type="user",
        project_id=project_id,
        entity_type="project_memory_item",
        entity_id=item.id,
        risk_level="medium",
        summary=f"Rejected proposed {item.memory_type} memory.",
        metadata=_memory_review_audit_metadata(item, status="rejected"),
    )
    db.commit()
    db.refresh(item)
    return item


def upsert_from_assumption(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    assumption: Assumption,
    *,
    source_entity_type: str,
    source_entity_id: uuid.UUID,
    source_metadata: dict[str, Any] | None = None,
) -> ProjectMemoryItem:
    """Mirror an assumption into semantic memory with approval provenance."""

    provenance_metadata = {
        "source": source_entity_type,
        "source_entity_id": str(source_entity_id),
        "approval_required": True,
        "origin": "derived",
    }
    provenance_metadata.update(source_metadata or {})
    return upsert_memory_item(
        db,
        auth,
        project_id,
        memory_type="semantic",
        write_policy="approval_required",
        entity_type="assumption",
        entity_id=assumption.id,
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        title="Assumption memory",
        summary=assumption.text,
        content={
            "text": assumption.text,
            "category": assumption.category,
            "importance": assumption.importance,
            "uncertainty": assumption.uncertainty,
            "kill_risk": assumption.kill_risk,
            "status": assumption.status,
        },
        provenance_metadata=provenance_metadata,
        confidence_score=assumption.confidence_score,
        _trusted_projection=_TRUSTED_DERIVED_PROJECTION,
    )


def upsert_from_risk(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    risk: Risk,
    *,
    source_entity_type: str,
    source_entity_id: uuid.UUID,
    source_metadata: dict[str, Any] | None = None,
) -> ProjectMemoryItem:
    """Mirror a risk into semantic memory with approval provenance."""

    provenance_metadata = {
        "source": source_entity_type,
        "source_entity_id": str(source_entity_id),
        "approval_required": True,
        "origin": "derived",
    }
    provenance_metadata.update(source_metadata or {})
    return upsert_memory_item(
        db,
        auth,
        project_id,
        memory_type="semantic",
        write_policy="approval_required",
        entity_type="risk",
        entity_id=risk.id,
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        title="Risk memory",
        summary=risk.text,
        content={
            "text": risk.text,
            "category": risk.category,
            "severity": risk.severity,
            "likelihood": risk.likelihood,
            "mitigation": risk.mitigation,
            "status": risk.status,
        },
        provenance_metadata=provenance_metadata,
        # Risk likelihood is not evidence confidence, so preserve uncertainty explicitly.
        confidence_score=Decimal("0"),
        _trusted_projection=_TRUSTED_DERIVED_PROJECTION,
    )


def mark_stale(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    memory_id: uuid.UUID,
    *,
    settings: Settings | None = None,
) -> ProjectMemoryItem:
    require_permission(auth, "approve_memory_updates")
    item = get_memory_item(db, auth, project_id, memory_id)
    policy_decision = _authorize_opa_memory_lifecycle(
        db,
        auth,
        project_id,
        item,
        operation="mark_stale",
        settings=settings,
    )
    item.status = "stale"
    _record_opa_memory_authorization(
        db,
        auth,
        project_id=project_id,
        item=item,
        operation="mark_stale",
        affected_records=1,
        policy_decision=policy_decision,
        actor_type="user",
    )
    db.commit()
    db.refresh(item)
    return item


def archive_memory(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    memory_id: uuid.UUID,
    *,
    settings: Settings | None = None,
) -> ProjectMemoryItem:
    require_permission(auth, "approve_memory_updates")
    item = get_memory_item(db, auth, project_id, memory_id)
    policy_decision = _authorize_opa_memory_lifecycle(
        db,
        auth,
        project_id,
        item,
        operation="archive",
        settings=settings,
    )
    item.status = "archived"
    _record_opa_memory_authorization(
        db,
        auth,
        project_id=project_id,
        item=item,
        operation="archive",
        affected_records=1,
        policy_decision=policy_decision,
        actor_type="user",
    )
    db.commit()
    db.refresh(item)
    return item


def merge_duplicates(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    keeper_id: uuid.UUID,
    duplicate_ids: list[uuid.UUID],
    settings: Settings | None = None,
) -> ProjectMemoryItem:
    require_permission(auth, "approve_memory_updates")
    keeper = get_memory_item(db, auth, project_id, keeper_id)
    duplicates = [
        get_memory_item(db, auth, project_id, duplicate_id)
        for duplicate_id in duplicate_ids
        if duplicate_id != keeper_id
    ]
    policy_decision = _authorize_opa_memory_lifecycle(
        db,
        auth,
        project_id,
        keeper,
        operation="merge_duplicates",
        affected_records=1 + len(duplicates),
        settings=settings,
    )
    for duplicate in duplicates:
        duplicate.status = "superseded"
        duplicate.superseded_by_id = keeper.id
    _record_opa_memory_authorization(
        db,
        auth,
        project_id=project_id,
        item=keeper,
        operation="merge_duplicates",
        affected_records=1 + len(duplicates),
        policy_decision=policy_decision,
        actor_type="user",
    )
    db.commit()
    db.refresh(keeper)
    return keeper


def detect_memory_conflicts(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    mark: bool = True,
    commit: bool = False,
) -> list[dict[str, Any]]:
    """Detect active memory records that conflict on the same durable subject."""
    project_service.get_project(db, auth, project_id)
    items = list(
        db.scalars(
            select(ProjectMemoryItem).where(
                ProjectMemoryItem.workspace_id == auth.workspace_id,
                ProjectMemoryItem.project_id == project_id,
                ProjectMemoryItem.status == "active",
                ProjectMemoryItem.memory_type.in_(("semantic", "project", "preference")),
            )
        )
    )
    allowed_data_classifications = _allowed_memory_data_classifications(auth)
    items = [
        item
        for item in items
        if memory_security_policy.memory_visible_to_clearance(
            item,
            allowed_data_classifications=allowed_data_classifications,
        )
    ]
    groups: dict[str, list[ProjectMemoryItem]] = {}
    for item in items:
        groups.setdefault(_conflict_key(item), []).append(item)
    conflicts: list[dict[str, Any]] = []
    for key, candidates in groups.items():
        summaries = {_normalize_text(item.summary) for item in candidates}
        if len(candidates) < 2 or len(summaries) < 2:
            continue
        conflict_id = str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"thesys:memory-conflict:{project_id}:{key}")
        )
        if mark:
            for item in candidates:
                metadata = dict(item.provenance_metadata or {})
                metadata["conflict_group_id"] = conflict_id
                metadata["conflict_detected_at"] = metadata.get(
                    "conflict_detected_at",
                    datetime.now(UTC).isoformat(),
                )
                item.provenance_metadata = metadata
        conflicts.append(
            {
                "conflict_group_id": conflict_id,
                "reason": "Active memory records make different claims about the same subject.",
                "memory_item_ids": [item.id for item in candidates],
                "titles": [item.title for item in candidates],
            }
        )
    conflicts.extend(_proposal_conflicts(db, auth, project_id))
    if mark:
        db.flush()
        if commit:
            db.commit()
    return conflicts


def resolve_memory_conflict(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    conflict_group_id: str,
    keeper_id: uuid.UUID,
    supersede_ids: list[uuid.UUID],
    archive_ids: list[uuid.UUID],
    reason: str,
    settings: Settings | None = None,
) -> ProjectMemoryItem:
    """Resolve a memory conflict through explicit human-approved state changes."""
    require_permission(auth, "approve_memory_updates")
    keeper = get_memory_item(db, auth, project_id, keeper_id)
    affected_records = len({keeper_id, *supersede_ids, *archive_ids})
    policy_decision = _authorize_opa_memory_lifecycle(
        db,
        auth,
        project_id,
        keeper,
        operation="resolve_conflict",
        affected_records=affected_records,
        settings=settings,
    )
    detect_memory_conflicts(db, auth, project_id, mark=True, commit=False)
    _ensure_conflict_member(keeper, conflict_group_id)
    resolution_metadata = {
        "conflict_group_id": conflict_group_id,
        "resolved_by_user_id": str(auth.user_id),
        "resolved_at": datetime.now(UTC).isoformat(),
        "resolution_reason": reason,
    }
    keeper.status = "active"
    keeper.provenance_metadata = {**(keeper.provenance_metadata or {}), **resolution_metadata}
    for item_id in supersede_ids:
        item = get_memory_item(db, auth, project_id, item_id)
        _ensure_conflict_member(item, conflict_group_id)
        item.status = "superseded"
        item.superseded_by_id = keeper.id
        item.provenance_metadata = {**(item.provenance_metadata or {}), **resolution_metadata}
    for item_id in archive_ids:
        item = get_memory_item(db, auth, project_id, item_id)
        _ensure_conflict_member(item, conflict_group_id)
        item.status = "archived"
        item.provenance_metadata = {**(item.provenance_metadata or {}), **resolution_metadata}
    _record_opa_memory_authorization(
        db,
        auth,
        project_id=project_id,
        item=keeper,
        operation="resolve_conflict",
        affected_records=affected_records,
        policy_decision=policy_decision,
        actor_type="user",
    )
    db.commit()
    db.refresh(keeper)
    return keeper


def _compaction_source_items(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    *,
    workflow_type: str,
    source_memory_ids: list[uuid.UUID],
) -> list[ProjectMemoryItem]:
    if source_memory_ids:
        return [get_memory_item(db, auth, project_id, memory_id) for memory_id in source_memory_ids]
    selection = select_memory_for_context(
        db,
        auth,
        project_id,
        workflow_type=workflow_type,
        limit=12,
    )
    return [
        item
        for item in selection.selected
        if item.status in {"active", "stale"}
        and (item.source_entity_type or item.provenance_metadata.get("source"))
    ][:8]


def _ensure_conflict_member(item: ProjectMemoryItem, conflict_group_id: str) -> None:
    try:
        memory_selection_policy.ensure_conflict_member(item, conflict_group_id)
    except memory_selection_policy.MemoryConflictMembershipError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Memory item is not part of the requested conflict group.",
        ) from exc


def _link_memory_proposal_conflict(
    *,
    project_id: uuid.UUID,
    active: ProjectMemoryItem,
    proposal: ProjectMemoryItem,
) -> None:
    conflict_group_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"thesys:memory-proposal-conflict:{project_id}:{active.id}:{proposal.id}",
        )
    )
    detected_at = datetime.now(UTC).isoformat()
    active_metadata = dict(active.provenance_metadata or {})
    active_conflicts = _metadata_id_list(active_metadata.get("contradicts_memory_ids"))
    active_metadata.update(
        {
            "conflict_group_id": conflict_group_id,
            "conflict_detected_at": detected_at,
            "contradicts_memory_ids": sorted({*active_conflicts, str(proposal.id)}),
        }
    )
    proposal_metadata = dict(proposal.provenance_metadata or {})
    proposal_conflicts = _metadata_id_list(proposal_metadata.get("contradicts_memory_ids"))
    proposal_metadata.update(
        {
            "conflict_group_id": conflict_group_id,
            "conflict_detected_at": detected_at,
            "contradicts_memory_ids": sorted({*proposal_conflicts, str(active.id)}),
        }
    )
    active.provenance_metadata = active_metadata
    proposal.provenance_metadata = proposal_metadata


def _effective_memory_expiry(
    memory_type: MemoryType,
    expires_at: datetime | None,
) -> datetime | None:
    ttl = {
        "working": WORKING_MEMORY_TTL,
        "episodic": EPISODIC_MEMORY_TTL,
    }.get(memory_type)
    if ttl is None:
        return expires_at
    latest_expiry = datetime.now(UTC) + ttl
    if expires_at is None:
        return latest_expiry
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return min(expires_at, latest_expiry)


def _working_memory_session_scope(auth: AuthContext) -> str | None:
    session_identifier = auth.principal.session_id or auth.principal.token_id
    return memory_security_policy.working_memory_session_scope(session_identifier)


def _allowed_memory_data_classifications(auth: AuthContext) -> set[str]:
    return set(
        RetrievalSecurityPolicy.for_auth(
            auth,
            minimum_source_trust_score=0.0,
        ).allowed_classifications
    )


def _memory_data_classification(
    memory_type: MemoryType,
    title: str,
    summary: str,
    content: dict[str, Any],
) -> str:
    classifications = [
        _MEMORY_TYPE_BASE_CLASSIFICATION[memory_type],
        data_protection_service.classify_text(title),
        data_protection_service.classify_text(summary),
        data_protection_service.classify_text(json.dumps(content, default=str, sort_keys=True)),
    ]
    return max(classifications, key=_CLASSIFICATION_RANK.__getitem__).value


def _conflicting_active_memory_items(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    proposal: ProjectMemoryItem,
) -> list[ProjectMemoryItem]:
    conflicting_ids = _metadata_id_list(
        (proposal.provenance_metadata or {}).get("contradicts_memory_ids")
    )
    if not conflicting_ids:
        return []
    parsed_ids = [uuid.UUID(value) for value in conflicting_ids if _is_uuid(value)]
    if not parsed_ids:
        return []
    items = list(
        db.scalars(
            select(ProjectMemoryItem).where(
                ProjectMemoryItem.workspace_id == auth.workspace_id,
                ProjectMemoryItem.project_id == project_id,
                ProjectMemoryItem.id.in_(parsed_ids),
                ProjectMemoryItem.status == "active",
            )
        )
    )
    return [
        item
        for item in items
        if memory_security_policy.memory_visible_to_clearance(
            item,
            allowed_data_classifications=_allowed_memory_data_classifications(auth),
        )
    ]


def _proposal_conflicts(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> list[dict[str, Any]]:
    proposals = list(
        db.scalars(
            select(ProjectMemoryItem).where(
                ProjectMemoryItem.workspace_id == auth.workspace_id,
                ProjectMemoryItem.project_id == project_id,
                ProjectMemoryItem.status == "proposed",
            )
        )
    )
    allowed_data_classifications = _allowed_memory_data_classifications(auth)
    conflicts: list[dict[str, Any]] = []
    for proposal in proposals:
        if not memory_security_policy.memory_visible_to_clearance(
            proposal,
            allowed_data_classifications=allowed_data_classifications,
        ):
            continue
        metadata = proposal.provenance_metadata or {}
        conflict_group_id = metadata.get("conflict_group_id")
        conflicting_ids = _metadata_id_list(metadata.get("contradicts_memory_ids"))
        if not isinstance(conflict_group_id, str) or not conflicting_ids:
            continue
        conflicting_item_ids = [
            uuid.UUID(value) for value in conflicting_ids if _is_uuid(value)
        ]
        item_ids = [proposal.id, *conflicting_item_ids]
        conflicting_items = {
            item.id: item
            for item in db.scalars(
                select(ProjectMemoryItem).where(
                    ProjectMemoryItem.workspace_id == auth.workspace_id,
                    ProjectMemoryItem.project_id == project_id,
                    ProjectMemoryItem.id.in_(conflicting_item_ids),
                )
            )
        }
        if any(
            not memory_security_policy.memory_visible_to_clearance(
                item,
                allowed_data_classifications=allowed_data_classifications,
            )
            for item in conflicting_items.values()
        ):
            continue
        conflicts.append(
            {
                "conflict_group_id": conflict_group_id,
                "reason": "Proposed memory conflicts with active memory and requires review.",
                "memory_item_ids": item_ids,
                "titles": [
                    proposal.title,
                    *[
                        conflicting_items[item_id].title
                        for item_id in conflicting_item_ids
                        if item_id in conflicting_items
                    ],
                ],
            }
        )
    return conflicts


def _metadata_id_list(value: object) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True
