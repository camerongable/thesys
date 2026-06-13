import asyncio
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from temporalio import activity

from app.core.auth import AuthContext
from app.core.config import get_settings
from app.db.models import (
    Artifact,
    ArtifactVersion,
    DiscoveredSource,
    ResearchSprint,
    User,
    Workspace,
    WorkspaceMember,
)
from app.db.session import SessionLocal
from app.services import (
    agentic_research_service,
    competitor_discovery_service,
    eval_service,
    governance_service,
    source_discovery_service,
)

Payload = dict[str, Any]


@activity.defn(name="create_or_load_research_plan_activity")
async def create_or_load_research_plan_activity(payload: Payload) -> Payload:
    return await _run_db_activity(
        payload,
        "wait_for_research_plan_approval",
        lambda db, auth, settings, sprint: _mark_waiting_for_plan_approval(db, sprint),
    )


@activity.defn(name="create_approval_request_activity")
async def create_approval_request_activity(payload: Payload) -> Payload:
    approval_type = str(payload.get("approval_type") or "research_plan")
    step = (
        "wait_for_research_plan_approval"
        if approval_type == "research_plan"
        else "wait_for_memory_update_approval"
    )

    def _create(db: Session, auth: AuthContext, settings: Any, sprint: ResearchSprint) -> Payload:
        if approval_type == "memory_update":
            _update_sprint(
                sprint,
                status="waiting_for_memory_approval",
                current_step=step,
            )
        governance_service.record_audit_event(
            db,
            auth,
            event_type=f"temporal_{approval_type}_approval_wait",
            actor_type="system",
            project_id=sprint.project_id,
            entity_type="research_sprint",
            entity_id=sprint.id,
            risk_level="medium",
            summary=f"Temporal workflow is waiting for {approval_type.replace('_', ' ')} approval.",
            metadata={
                "temporal_workflow_id": sprint.temporal_workflow_id,
                "current_step": step,
            },
        )
        db.commit()
        return _activity_result(sprint, approval_type=approval_type)

    return await _run_db_activity(payload, step, _create)


@activity.defn(name="discover_sources_activity")
async def discover_sources_activity(payload: Payload) -> Payload:
    def _discover(db: Session, auth: AuthContext, settings: Any, sprint: ResearchSprint) -> Payload:
        result = source_discovery_service.discover_sources(
            db,
            auth,
            settings,
            sprint.project_id,
            sprint.id,
        )
        sprint = _get_sprint(db, sprint.id)
        _update_sprint(sprint, status="running", current_step="discover_sources")
        db.commit()
        return _activity_result(
            sprint,
            generated_count=result.generated_count,
            candidate_count=result.candidate_count,
        )

    return await _run_db_activity(payload, "discover_sources", _discover)


@activity.defn(name="discover_competitors_activity")
async def discover_competitors_activity(payload: Payload) -> Payload:
    def _discover(db: Session, auth: AuthContext, settings: Any, sprint: ResearchSprint) -> Payload:
        result = competitor_discovery_service.discover_competitors(
            db,
            auth,
            settings,
            sprint.project_id,
            sprint.id,
        )
        sprint = _get_sprint(db, sprint.id)
        _update_sprint(sprint, status="running", current_step="discover_competitors")
        db.commit()
        return _activity_result(
            sprint,
            generated_count=result.generated_count,
            candidate_count=result.candidate_count,
        )

    return await _run_db_activity(payload, "discover_competitors", _discover)


@activity.defn(name="wait_for_optional_source_competitor_review_activity")
async def wait_for_optional_source_competitor_review_activity(payload: Payload) -> Payload:
    return await _run_db_activity(
        payload,
        "optional_source_competitor_review",
        lambda db, auth, settings, sprint: _mark_running(
            db,
            sprint,
            "optional_source_competitor_review",
        ),
    )


@activity.defn(name="ingest_sources_activity")
async def ingest_sources_activity(payload: Payload) -> Payload:
    def _ingest(db: Session, auth: AuthContext, settings: Any, sprint: ResearchSprint) -> Payload:
        sources = list(
            db.scalars(
                select(DiscoveredSource)
                .where(
                    DiscoveredSource.workspace_id == sprint.workspace_id,
                    DiscoveredSource.project_id == sprint.project_id,
                    DiscoveredSource.research_sprint_id == sprint.id,
                    DiscoveredSource.status.in_(("candidate", "approved", "failed")),
                )
                .order_by(DiscoveredSource.relevance_score.desc())
            )
        )
        ingested = 0
        failed = 0
        for source in sources:
            updated = source_discovery_service.ingest_source_candidate(
                db,
                auth,
                settings,
                sprint.project_id,
                sprint.id,
                source.id,
            )
            if updated.status == "ingested":
                ingested += 1
            elif updated.status == "failed":
                failed += 1
        sprint = _get_sprint(db, sprint.id)
        _update_sprint(sprint, status="running", current_step="ingest_sources")
        db.commit()
        return _activity_result(sprint, ingested_count=ingested, failed_count=failed)

    return await _run_db_activity(payload, "ingest_sources", _ingest)


@activity.defn(name="embed_evidence_activity")
async def embed_evidence_activity(payload: Payload) -> Payload:
    def _embed(db: Session, auth: AuthContext, settings: Any, sprint: ResearchSprint) -> Payload:
        source_count = db.scalar(
            select(DiscoveredSource)
            .where(
                DiscoveredSource.workspace_id == sprint.workspace_id,
                DiscoveredSource.project_id == sprint.project_id,
                DiscoveredSource.research_sprint_id == sprint.id,
                DiscoveredSource.status == "ingested",
            )
            .limit(1)
        )
        _update_sprint(sprint, status="running", current_step="embed_evidence")
        db.commit()
        return _activity_result(sprint, has_ingested_sources=source_count is not None)

    return await _run_db_activity(payload, "embed_evidence", _embed)


@activity.defn(name="run_langgraph_research_activity")
async def run_langgraph_research_activity(payload: Payload) -> Payload:
    def _run(db: Session, auth: AuthContext, settings: Any, sprint: ResearchSprint) -> Payload:
        existing = _research_memo_for_sprint(db, sprint)
        if existing is None:
            result = agentic_research_service.run_agentic_research(
                db,
                auth,
                settings,
                sprint.project_id,
                sprint.id,
            )
            artifact_id = result.artifact.id
            version_id = result.version.id
        else:
            artifact_id = existing.id
            version_id = existing.current_version_id
        sprint = _get_sprint(db, sprint.id)
        _update_sprint(
            sprint,
            status="waiting_for_memory_approval",
            current_step="wait_for_memory_update_approval",
        )
        db.commit()
        return _activity_result(
            sprint,
            artifact_id=str(artifact_id),
            artifact_version_id=str(version_id) if version_id else None,
        )

    return await _run_db_activity(payload, "run_agentic_research_synthesis", _run)


@activity.defn(name="run_langsmith_eval_activity")
async def run_langsmith_eval_activity(payload: Payload) -> Payload:
    def _eval(db: Session, auth: AuthContext, settings: Any, sprint: ResearchSprint) -> Payload:
        evaluation = eval_service.run_v1_research_eval(db, auth, sprint.project_id)
        _update_sprint(sprint, current_step="run_eval_trust_checks")
        db.commit()
        return _activity_result(
            sprint,
            eval_passed=evaluation.passed,
            eval_score=evaluation.score,
            eval_total=evaluation.total,
        )

    return await _run_db_activity(payload, "run_eval_trust_checks", _eval)


@activity.defn(name="create_memory_update_proposals_activity")
async def create_memory_update_proposals_activity(payload: Payload) -> Payload:
    def _create(db: Session, auth: AuthContext, settings: Any, sprint: ResearchSprint) -> Payload:
        _update_sprint(
            sprint,
            status="waiting_for_memory_approval",
            current_step="create_memory_update_proposals",
        )
        db.commit()
        return _activity_result(sprint)

    return await _run_db_activity(payload, "create_memory_update_proposals", _create)


@activity.defn(name="persist_memory_update_activity")
async def persist_memory_update_activity(payload: Payload) -> Payload:
    decision = str(payload.get("decision") or "approved")

    def _persist(db: Session, auth: AuthContext, settings: Any, sprint: ResearchSprint) -> Payload:
        artifact = _research_memo_for_sprint(db, sprint)
        already_reviewed = False
        if artifact and artifact.current_version_id:
            version = db.get(ArtifactVersion, artifact.current_version_id)
            content = version.structured_content if version else {}
            already_reviewed = isinstance(content, dict) and content.get(
                "memory_update_status"
            ) in {"approved", "rejected"}

        if not already_reviewed and sprint.status != "completed":
            if decision == "approved":
                agentic_research_service.approve_research_memo(
                    db,
                    auth,
                    settings,
                    sprint.project_id,
                    sprint.id,
                )
            else:
                agentic_research_service.reject_research_memo(
                    db,
                    auth,
                    settings,
                    sprint.project_id,
                    sprint.id,
                )
        sprint = _get_sprint(db, sprint.id)
        _update_sprint(sprint, current_step="persist_approved_updates")
        db.commit()
        return _activity_result(sprint, decision=decision, already_reviewed=already_reviewed)

    return await _run_db_activity(payload, "persist_approved_updates", _persist)


@activity.defn(name="finalize_sprint_activity")
async def finalize_sprint_activity(payload: Payload) -> Payload:
    final_status = str(payload.get("status") or "completed")

    def _finalize(db: Session, auth: AuthContext, settings: Any, sprint: ResearchSprint) -> Payload:
        status = "cancelled" if final_status == "cancelled" else "completed"
        _update_sprint(
            sprint,
            status=status,
            current_step="finalize_research_sprint",
            completed=True,
        )
        if status == "completed" and sprint.plan.status != "completed":
            sprint.plan.status = "completed"
        db.commit()
        return _activity_result(sprint, finalized_status=status)

    return await _run_db_activity(payload, "finalize_research_sprint", _finalize)


async def _run_db_activity(
    payload: Payload,
    step_name: str,
    fn: Callable[[Session, AuthContext, Any, ResearchSprint], Payload],
) -> Payload:
    return await asyncio.to_thread(_run_db_activity_sync, payload, step_name, fn)


def _run_db_activity_sync(
    payload: Payload,
    step_name: str,
    fn: Callable[[Session, AuthContext, Any, ResearchSprint], Payload],
) -> Payload:
    settings = get_settings()
    with SessionLocal() as db:
        sprint: ResearchSprint | None = None
        try:
            sprint = _get_sprint(db, uuid.UUID(str(payload["research_sprint_id"])))
            auth = _auth_from_payload(db, payload)
            _update_sprint(sprint, status=sprint.status, current_step=step_name)
            db.commit()
            return fn(db, auth, settings, sprint)
        except Exception as exc:
            db.rollback()
            if sprint is not None:
                sprint = _get_sprint(db, sprint.id)
                _update_sprint(
                    sprint,
                    status="failed",
                    current_step=step_name,
                    failed_step=step_name,
                    failure_message=str(exc)[:2000],
                    completed=True,
                )
                db.commit()
            raise


def _auth_from_payload(db: Session, payload: Payload) -> AuthContext:
    user_id = uuid.UUID(str(payload["user_id"]))
    workspace_id = uuid.UUID(str(payload["workspace_id"]))
    user = db.get(User, user_id)
    workspace = db.get(Workspace, workspace_id)
    if user is None or workspace is None:
        raise RuntimeError("Temporal activity could not resolve workflow user/workspace.")
    membership = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.workspace_id == workspace_id,
        )
    )
    role = membership.role if membership else "owner"
    return AuthContext(user=user, workspace=workspace, role=role)


def _get_sprint(db: Session, sprint_id: uuid.UUID) -> ResearchSprint:
    sprint = db.scalar(
        select(ResearchSprint)
        .where(ResearchSprint.id == sprint_id)
        .options(selectinload(ResearchSprint.plan))
    )
    if sprint is None:
        raise RuntimeError("Research sprint not found.")
    return sprint


def _mark_waiting_for_plan_approval(db: Session, sprint: ResearchSprint) -> Payload:
    if sprint.plan.status == "approved":
        _update_sprint(sprint, status="approved", current_step="wait_for_research_plan_approval")
    else:
        _update_sprint(
            sprint,
            status="waiting_for_approval",
            current_step="wait_for_research_plan_approval",
        )
    db.commit()
    return _activity_result(sprint)


def _mark_running(db: Session, sprint: ResearchSprint, step: str) -> Payload:
    _update_sprint(sprint, status="running", current_step=step)
    db.commit()
    return _activity_result(sprint)


def _update_sprint(
    sprint: ResearchSprint,
    *,
    status: str | None = None,
    current_step: str | None = None,
    failed_step: str | None = None,
    failure_message: str | None = None,
    completed: bool = False,
) -> None:
    if status is not None:
        sprint.status = status
    if current_step is not None:
        sprint.current_step = current_step
    if failed_step is not None:
        sprint.failed_step = failed_step
    if failure_message is not None:
        sprint.failure_message = failure_message
    if sprint.started_at is None and sprint.status in {
        "running",
        "waiting_for_approval",
        "waiting_for_memory_approval",
    }:
        sprint.started_at = datetime.now(UTC)
    if completed:
        sprint.completed_at = sprint.completed_at or datetime.now(UTC)


def _activity_result(sprint: ResearchSprint, **extra: Any) -> Payload:
    return {
        "research_sprint_id": str(sprint.id),
        "project_id": str(sprint.project_id),
        "status": sprint.status,
        "current_step": sprint.current_step,
        "temporal_workflow_id": sprint.temporal_workflow_id,
        **extra,
    }


def _research_memo_for_sprint(db: Session, sprint: ResearchSprint) -> Artifact | None:
    artifacts = list(
        db.scalars(
            select(Artifact).where(
                Artifact.workspace_id == sprint.workspace_id,
                Artifact.project_id == sprint.project_id,
                Artifact.artifact_type == "research_memo",
            )
        )
    )
    for artifact in artifacts:
        versions = list(
            db.scalars(
                select(ArtifactVersion).where(ArtifactVersion.artifact_id == artifact.id)
            )
        )
        for version in versions:
            structured = version.structured_content
            if isinstance(structured, dict) and structured.get("research_sprint_id") == str(
                sprint.id
            ):
                return artifact
    return None
