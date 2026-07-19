from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.auth import AuthContextDep, SettingsDep
from app.db.session import get_db
from app.schemas.security import KillSwitchUpdate, WorkspaceKillSwitchStateRead
from app.services import kill_switch_service, security_metrics_service

router = APIRouter(prefix="/api/security", tags=["security"])
DbDep = Annotated[Session, Depends(get_db)]


@router.get("/metrics", include_in_schema=False)
def get_prometheus_metrics() -> Response:
    payload, content_type = security_metrics_service.render_metrics()
    return Response(content=payload, headers={"Content-Type": content_type})


def _serialize(state: kill_switch_service.KillSwitchState) -> WorkspaceKillSwitchStateRead:
    return WorkspaceKillSwitchStateRead(
        switches=state.switches,
        updated_at=state.updated_at,
        updated_by=state.updated_by,
    )


@router.get("/kill-switches", response_model=WorkspaceKillSwitchStateRead)
def get_kill_switches(
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> WorkspaceKillSwitchStateRead:
    return _serialize(kill_switch_service.read_state(db, auth, settings))


@router.patch("/kill-switches", response_model=WorkspaceKillSwitchStateRead)
def update_kill_switches(
    payload: KillSwitchUpdate,
    db: DbDep,
    auth: AuthContextDep,
    settings: SettingsDep,
) -> WorkspaceKillSwitchStateRead:
    return _serialize(kill_switch_service.update_state(db, auth, settings, payload))
