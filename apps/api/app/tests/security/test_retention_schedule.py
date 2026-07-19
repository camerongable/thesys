import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session
from temporalio.client import ScheduleAlreadyRunningError, ScheduleIntervalSpec

from app.core.config import Settings
from app.db.models import (
    AuditEvent,
    ResearchSprint,
    SecurityAlert,
    SecurityEvent,
    User,
    Workspace,
    WorkspaceMember,
)
from app.security.workflow_budget import WorkflowSecurityBudget
from app.services import (
    retention_schedule_service,
    workflow_timeout_reconciliation_schedule_service,
)
from app.services.identity_service import ensure_dev_identity
from app.temporal.activities import (
    _reconcile_workspace_workflow_timeouts,
    _retention_cleanup_payloads,
)

REPO_ROOT = Path(__file__).resolve().parents[5]


def test_retention_cleanup_schedule_uses_configured_interval_and_skip_policy() -> None:
    settings = Settings(
        temporal_task_queue="retention-queue",
        temporal_workflow_timeout_seconds=600,
        retention_cleanup_interval_hours=12,
    )

    schedule = retention_schedule_service.retention_cleanup_schedule(settings)

    assert schedule.action.task_queue == "retention-queue"
    assert schedule.action.execution_timeout == timedelta(seconds=600)
    assert schedule.spec.intervals == [ScheduleIntervalSpec(every=timedelta(hours=12))]
    assert schedule.policy.overlap.name == "SKIP"


def test_enabled_retention_schedule_is_created_or_reconciled() -> None:
    settings = Settings(retention_cleanup_schedule_enabled=True)
    client = _ScheduleClient()

    asyncio.run(retention_schedule_service.ensure_retention_cleanup_schedule(client, settings))

    assert client.created == [retention_schedule_service.RETENTION_CLEANUP_SCHEDULE_ID]
    client.raise_already_running = True
    asyncio.run(retention_schedule_service.ensure_retention_cleanup_schedule(client, settings))
    assert client.handle.updated_schedule is not None
    assert client.handle.updated_schedule.spec.intervals == [
        ScheduleIntervalSpec(every=timedelta(hours=24))
    ]


def test_enabled_workflow_timeout_reconciliation_schedule_is_created_or_reconciled() -> None:
    settings = Settings(
        workflow_timeout_reconciliation_schedule_enabled=True,
        workflow_timeout_reconciliation_interval_minutes=3,
    )
    client = _ScheduleClient()

    asyncio.run(
        workflow_timeout_reconciliation_schedule_service.ensure_workflow_timeout_reconciliation_schedule(
            client,
            settings,
        )
    )

    assert client.created == [
        workflow_timeout_reconciliation_schedule_service.WORKFLOW_TIMEOUT_RECONCILIATION_SCHEDULE_ID
    ]
    client.raise_already_running = True
    asyncio.run(
        workflow_timeout_reconciliation_schedule_service.ensure_workflow_timeout_reconciliation_schedule(
            client,
            settings,
        )
    )
    assert client.handle.updated_schedule is not None
    assert client.handle.updated_schedule.spec.intervals == [
        ScheduleIntervalSpec(every=timedelta(minutes=3))
    ]


def test_disabled_retention_schedule_does_not_contact_temporal() -> None:
    client = _ScheduleClient()

    asyncio.run(retention_schedule_service.ensure_retention_cleanup_schedule(client, Settings()))

    assert client.created == []


def test_compose_enables_retention_schedule_for_temporal_worker() -> None:
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text())
    environment = compose["services"]["temporal-worker"]["environment"]

    assert environment["RETENTION_CLEANUP_SCHEDULE_ENABLED"].endswith(":-true}")
    assert environment["RETENTION_CLEANUP_INTERVAL_HOURS"].endswith(":-24}")
    assert environment["WORKFLOW_TIMEOUT_RECONCILIATION_SCHEDULE_ENABLED"].endswith(":-true}")
    assert environment["WORKFLOW_TIMEOUT_RECONCILIATION_INTERVAL_MINUTES"].endswith(":-5}")


def test_retention_cleanup_payloads_choose_one_active_principal_per_workspace(
    db_session: Session,
) -> None:
    active_owner = _user("owner@example.com")
    active_viewer = _user("viewer@example.com")
    disabled_owner = _user("disabled@example.com", status="disabled")
    active_workspace = Workspace(name="Active", created_by=active_owner.id)
    disabled_workspace = Workspace(name="Disabled", created_by=disabled_owner.id)
    db_session.add_all(
        (active_owner, active_viewer, disabled_owner, active_workspace, disabled_workspace)
    )
    db_session.flush()
    db_session.add_all(
        (
            WorkspaceMember(
                workspace_id=active_workspace.id,
                user_id=active_viewer.id,
                role="viewer",
            ),
            WorkspaceMember(
                workspace_id=active_workspace.id,
                user_id=active_owner.id,
                role="owner",
            ),
            WorkspaceMember(
                workspace_id=disabled_workspace.id,
                user_id=disabled_owner.id,
                role="owner",
            ),
        )
    )
    db_session.commit()

    assert _retention_cleanup_payloads(db_session) == [
        {"workspace_id": str(active_workspace.id), "user_id": str(active_owner.id)}
    ]


def test_workflow_timeout_reconciliation_marks_expired_sprint_once(
    client,
    db_session: Session,
) -> None:
    project_id = client.post("/api/projects", json={"name": "Timed out sprint"}).json()["id"]
    plan = client.post(
        f"/api/projects/{project_id}/research-sprints/plan",
        json={"objective": "Validate a duration-bound workflow."},
    ).json()["sprint"]
    sprint = db_session.get(ResearchSprint, uuid.UUID(plan["id"]))
    assert sprint is not None
    observed_at = datetime(2026, 7, 18, tzinfo=UTC)
    sprint.status = "running"
    sprint.started_at = observed_at - timedelta(seconds=121)
    sprint.temporal_workflow_id = "research-sprint-timeout"
    sprint.temporal_run_id = "temporal-run-timeout"
    sprint.workflow_security_budget = WorkflowSecurityBudget.from_settings(
        Settings(security_workflow_max_duration_seconds=120)
    ).as_payload()
    db_session.commit()
    auth = ensure_dev_identity(
        db_session,
        email="dev@thesys.local",
        display_name="Dev User",
    )

    assert (
        _reconcile_workspace_workflow_timeouts(
            db_session,
            auth,
            Settings(),
            now=observed_at,
        )
        == 1
    )
    db_session.commit()

    assert sprint.status == "failed"
    assert sprint.current_step == "workflow_duration_exceeded"
    assert sprint.failed_step == "workflow_duration_exceeded"
    audit_event = db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.entity_id == sprint.id,
            AuditEvent.event_type == "workflow_duration_exceeded",
        )
    )
    assert audit_event is not None
    assert audit_event.event_metadata["max_duration_seconds"] == 120
    assert audit_event.event_metadata["observed_duration_seconds"] == 121
    assert audit_event.event_metadata["temporal_workflow_id"] == "research-sprint-timeout"
    security_event = db_session.scalar(
        select(SecurityEvent).where(SecurityEvent.audit_event_id == audit_event.id)
    )
    assert security_event is not None
    assert security_event.source == "workflow"
    assert (
        db_session.scalar(
            select(SecurityAlert).where(SecurityAlert.security_event_id == security_event.id)
        )
        is not None
    )

    assert (
        _reconcile_workspace_workflow_timeouts(
            db_session,
            auth,
            Settings(),
            now=observed_at,
        )
        == 0
    )


class _ScheduleClient:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.raise_already_running = False
        self.handle = _ScheduleHandle()

    async def create_schedule(self, schedule_id, _schedule):
        self.created.append(schedule_id)
        if self.raise_already_running:
            raise ScheduleAlreadyRunningError()
        return self.handle

    def get_schedule_handle(self, _schedule_id):
        return self.handle


class _ScheduleHandle:
    def __init__(self) -> None:
        self.updated_schedule = None

    async def update(self, updater) -> None:
        self.updated_schedule = updater(None).schedule


def _user(email: str, *, status: str = "active") -> User:
    return User(
        id=uuid.uuid4(),
        external_auth_id=f"test:{email}",
        email=email,
        status=status,
    )
