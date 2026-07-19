"""Durable, audited emergency capability controls."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import (
    AuthContext,
    require_workspace_owner,
    require_workspace_security_admin,
)
from app.core.config import Settings
from app.db.models import WorkspaceKillSwitchState
from app.schemas.security import KillSwitchName, KillSwitchStatusRead, KillSwitchUpdate
from app.services import governance_service

KILL_SWITCH_NAMES: tuple[KillSwitchName, ...] = (
    "disable_all_agent_writes",
    "disable_external_mcp",
    "disable_external_egress",
    "disable_model_provider",
    "disable_memory_writes",
    "disable_source_fetching",
)


@dataclass(frozen=True)
class KillSwitchState:
    switches: list[KillSwitchStatusRead]
    updated_at: datetime | None
    updated_by: uuid.UUID | None


def read_state(
    db: Session,
    auth: AuthContext,
    settings: Settings,
) -> KillSwitchState:
    require_workspace_security_admin(auth)
    return _state_from_record(_get_record(db, auth), settings)


def update_state(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    payload: KillSwitchUpdate,
) -> KillSwitchState:
    require_workspace_owner(auth)
    record = _get_record(db, auth)
    requested_changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    changed = {
        name: value
        for name, value in requested_changes.items()
        if bool(getattr(record, name, False)) != value
    }
    if not changed:
        return _state_from_record(record, settings)

    if record is None:
        record = WorkspaceKillSwitchState(workspace_id=auth.workspace_id, updated_by=auth.user_id)
        db.add(record)
    for name, value in changed.items():
        setattr(record, name, value)
    record.updated_by = auth.user_id
    db.flush()
    governance_service.record_audit_event(
        db,
        auth,
        event_type="security_kill_switch_changed",
        actor_type="user",
        entity_type="workspace_kill_switch_state",
        entity_id=record.id,
        risk_level="high",
        summary="Changed workspace emergency capability controls.",
        metadata={"changes": changed},
    )
    db.commit()
    db.refresh(record)
    return _state_from_record(record, settings)


def _get_record(db: Session, auth: AuthContext) -> WorkspaceKillSwitchState | None:
    return db.scalar(
        select(WorkspaceKillSwitchState).where(
            WorkspaceKillSwitchState.workspace_id == auth.workspace_id
        )
    )


def _state_from_record(
    record: WorkspaceKillSwitchState | None,
    settings: Settings,
) -> KillSwitchState:
    statuses = []
    for name in KILL_SWITCH_NAMES:
        workspace_enabled = bool(getattr(record, name, False))
        environment_enabled = bool(getattr(settings, name))
        statuses.append(
            KillSwitchStatusRead(
                name=name,
                enabled=workspace_enabled or environment_enabled,
                workspace_enabled=workspace_enabled,
                environment_enabled=environment_enabled,
            )
        )
    return KillSwitchState(
        switches=statuses,
        updated_at=record.updated_at if record is not None else None,
        updated_by=record.updated_by if record is not None else None,
    )
