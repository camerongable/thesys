import json
import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, AuthContextDep
from app.db.models import AIRun
from app.db.session import get_db
from app.schemas.workflows import WorkflowRunListRead, WorkflowRunRead
from app.services import workflow_service

router = APIRouter(prefix="/api", tags=["workflows"])
DbDep = Annotated[Session, Depends(get_db)]
LimitQuery = Annotated[int, Query(ge=1, le=25)]

TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


@router.get("/projects/{project_id}/workflows", response_model=WorkflowRunListRead)
def list_project_workflows(
    project_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
    limit: LimitQuery = 10,
) -> WorkflowRunListRead:
    runs = workflow_service.list_project_runs(db, auth, project_id, limit)
    return WorkflowRunListRead(runs=[_serialize_run(run) for run in runs])


@router.get("/workflows/{run_id}", response_model=WorkflowRunRead)
def get_workflow_run(
    run_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> WorkflowRunRead:
    return _serialize_run(workflow_service.get_run(db, auth, run_id))


@router.get("/workflows/{run_id}/events")
def stream_workflow_events(
    run_id: uuid.UUID,
    db: DbDep,
    auth: AuthContextDep,
) -> StreamingResponse:
    return StreamingResponse(
        _event_stream(db, auth, run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _event_stream(db: Session, auth: AuthContext, run_id: uuid.UUID):
    last_payload: str | None = None
    deadline = time.monotonic() + 30
    while True:
        db.expire_all()
        run = workflow_service.get_run(db, auth, run_id)
        payload = _serialize_run(run).model_dump(mode="json")
        encoded = json.dumps(payload, separators=(",", ":"))
        if encoded != last_payload:
            yield f"data: {encoded}\n\n"
            last_payload = encoded
        if run.status in TERMINAL_STATUSES:
            break
        if time.monotonic() > deadline:
            yield ": workflow stream timeout\n\n"
            break
        time.sleep(0.75)


def _serialize_run(run: AIRun) -> WorkflowRunRead:
    return WorkflowRunRead.model_validate({**run.__dict__, "steps": list(run.steps)})
