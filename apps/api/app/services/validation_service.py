"""Validation, assumption memory, experiment results, and decision support.

The validation layer turns model-generated assumptions into testable missions,
captures real-world results, uses structured LLM interpretation to propose
project updates, and gates those updates behind approval records.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.ai.fallback_completion import fallback_completion
from app.ai.fallback_policy import (
    should_use_fallback_after_error,
    should_use_fallback_without_model,
)
from app.ai.litellm_client import ChatMessage, LLMCompletion
from app.ai.prompts import (
    ASSUMPTION_EXTRACTION_PROMPT_VERSION,
    VALIDATION_PLAN_PROMPT_VERSION,
    VALIDATION_RESULT_INTERPRETATION_PROMPT_VERSION,
)
from app.ai.structured_output import StructuredOutputError, generate_structured_output
from app.core.auth import AuthContext, require_permission
from app.core.config import Settings, get_settings
from app.db.models import (
    AIRun,
    AIStep,
    ApprovalRequest,
    Artifact,
    ArtifactVersion,
    Assumption,
    Competitor,
    Decision,
    DecisionLink,
    EvidenceSource,
    Experiment,
    ExperimentResult,
    Project,
    Risk,
    ThesisEvolutionEvent,
    ValidationMission,
    ValidationResultInterpretation,
)
from app.features.decisions import recommendation as decision_recommendation_feature
from app.features.validation import generation as validation_generation
from app.features.validation import plan_rendering, result_interpretation
from app.schemas.artifacts import AssumptionDraft, RiskDraft
from app.schemas.validation import (
    AssumptionExtractionDraft,
    AssumptionUpdate,
    DecisionCoachChatRead,
    DecisionCreate,
    DecisionRecommendationRead,
    ExperimentResultCreate,
    ValidationMissionRead,
    ValidationPlanDraft,
    ValidationPlanGenerateCreate,
    ValidationPlanSetDraft,
    ValidationResultInterpretationCreate,
    ValidationResultInterpretationDraft,
    ValidationResultInterpretationRead,
)
from app.services import (
    ai_run_service,
    context_service,
    governance_service,
    langsmith_observability_service,
    memory_service,
    project_service,
)


class ValidationWorkflowError(RuntimeError):
    """Raised when a validation workflow fails outside expected model errors."""

    pass


@dataclass(frozen=True)
class AssumptionExtractionResult:
    """Assumptions and risks extracted from project state with AI run metadata."""

    run: AIRun
    step: AIStep
    assumptions: list[Assumption]
    risks: list[Risk]
    model_provider: str
    model_name: str
    used_stub: bool
    total_tokens: int | None
    total_cost: Decimal | None


@dataclass(frozen=True)
class ValidationPlanResult:
    """Generated validation plans, persisted experiments, and mission records."""

    run: AIRun
    step: AIStep
    artifact: Artifact
    experiments: list[Experiment]
    missions: list[ValidationMissionRead]
    model_provider: str
    model_name: str
    used_stub: bool
    total_tokens: int | None
    total_cost: Decimal | None


@dataclass(frozen=True)
class ExperimentResultLogResult:
    """Logged result and the affected confidence state."""

    result: ExperimentResult
    experiment: Experiment
    assumption: Assumption | None
    project_confidence_score: Decimal | None


@dataclass(frozen=True)
class ValidationInterpretationResult:
    """Structured interpretation of results plus any approval request it created."""

    run: AIRun
    step: AIStep
    mission: ValidationMissionRead
    interpretation: ValidationResultInterpretationRead
    approval_request: ApprovalRequest | None
    model_provider: str
    model_name: str
    used_stub: bool
    total_tokens: int | None
    total_cost: Decimal | None


def list_assumptions(db: Session, auth: AuthContext, project_id: uuid.UUID) -> list[Assumption]:
    """List project assumptions sorted by importance and uncertainty."""

    project_service.get_project(db, auth, project_id)
    return _load_assumptions(db, auth, project_id)


def update_assumption(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    assumption_id: uuid.UUID,
    payload: AssumptionUpdate,
) -> Assumption:
    """Update assumption fields and recalculate project confidence."""

    assumption = get_assumption(db, auth, project_id, assumption_id)
    update_data = payload.model_dump(exclude_unset=True)
    if "text" in update_data and update_data["text"] is not None:
        assumption.text = update_data["text"].strip()
    for field in (
        "category",
        "importance",
        "uncertainty",
        "kill_risk",
        "status",
        "recommended_test",
    ):
        if field in update_data:
            setattr(assumption, field, update_data[field])
    if "confidence_score" in update_data:
        assumption.confidence_score = _decimal_score(update_data["confidence_score"])
    _recalculate_project_confidence(db, auth, project_id)
    db.commit()
    return get_assumption(db, auth, project_id, assumption.id)


def get_assumption(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    assumption_id: uuid.UUID,
) -> Assumption:
    """Load a workspace-scoped assumption by project and id."""

    assumption = db.scalar(
        select(Assumption).where(
            Assumption.id == assumption_id,
            Assumption.workspace_id == auth.workspace_id,
            Assumption.project_id == project_id,
        )
    )
    if assumption is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assumption not found.")
    return assumption


def list_risks(db: Session, auth: AuthContext, project_id: uuid.UUID) -> list[Risk]:
    """List current project risks."""

    project_service.get_project(db, auth, project_id)
    return _load_risks(db, auth, project_id)


def extract_assumptions_and_risks(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
) -> AssumptionExtractionResult:
    """Extract assumptions and risks with structured output from the project thesis."""

    require_permission(auth, "run_research")
    project = project_service.get_project(db, auth, project_id)
    run = ai_run_service.start_run(
        db,
        auth,
        workflow_type="assumption_extraction",
        prompt_version=ASSUMPTION_EXTRACTION_PROMPT_VERSION,
        input_summary=f"Extract assumptions and risks for {project.name}"[:500],
        project_id=project.id,
        model_provider="stub" if settings.should_use_llm_stub else "litellm",
        model_name=settings.litellm_model,
    )
    trace = langsmith_observability_service.ensure_run_trace(
        db,
        settings,
        run,
        metadata={
            "project_id": str(project.id),
            "workflow_version": ASSUMPTION_EXTRACTION_PROMPT_VERSION,
            "user_id": str(auth.user_id) if auth.user_id else None,
            "model_provider": run.model_provider,
            "model_name": run.model_name,
        },
    )
    step: AIStep | None = None
    try:
        project_state = _project_state(project)
        memory_selection = memory_service.select_memory_for_context(
            db,
            auth,
            project_id,
            workflow_type="assumption_extraction",
            limit=8,
        )
        context_pack = context_service.ContextCompiler(settings).compile_workflow_context(
            workflow_type="assumption_extraction",
            project_id=project_id,
            query="Extract risky assumptions and strategic risks.",
            domain_context={"project": project_state},
            prompt_version=ASSUMPTION_EXTRACTION_PROMPT_VERSION,
            expected_schema=AssumptionExtractionDraft.__name__,
            memory_selection=memory_selection,
        )
        step = ai_run_service.start_step(
            db,
            run,
            step_name="extract_assumptions_risks",
            input_json={
                "project_id": str(project.id),
                "context_pack": context_pack.prompt_metadata(),
            },
        )
        started = perf_counter()
        messages = _assumption_messages(project, project_state)
        if should_use_fallback_without_model(settings):
            draft = _fallback_assumption_extraction(project)
            completion = _fallback_completion(
                settings,
                messages,
                draft,
                "assumption_extraction_policy_always",
            )
        else:
            try:
                draft_result = generate_structured_output(
                    settings,
                    AssumptionExtractionDraft,
                    messages,
                    model=settings.litellm_model,
                    temperature=0.0,
                )
                draft = AssumptionExtractionDraft.model_validate(draft_result.parsed)
                completion = draft_result.completion
            except (StructuredOutputError, RuntimeError) as exc:
                if not should_use_fallback_after_error(settings):
                    raise
                draft = _fallback_assumption_extraction(project)
                completion = _fallback_completion(
                    settings,
                    messages,
                    draft,
                    "assumption_extraction_emergency",
                    exc,
                )
        assumptions = _upsert_assumptions(db, auth, project, draft.assumptions)
        risks = _upsert_risks(db, auth, project, draft.risks)
        _recalculate_project_confidence(db, auth, project.id)
        db.flush()
        completed_step = ai_run_service.complete_step(
            db,
            step,
            output_json={
                "assumption_ids": [str(item.id) for item in assumptions],
                "risk_ids": [str(item.id) for item in risks],
            },
            latency_ms=int((perf_counter() - started) * 1000),
            tokens=completion.total_tokens,
            cost=completion.total_cost,
        )
        langsmith_observability_service.record_step_span(
            db,
            settings,
            run=run,
            step=completed_step,
            trace=trace,
            span_name="assumption_extraction",
            input_json=step.input_json,
            output_json=completed_step.output_json,
            run_type="llm" if completion.model_provider != "stub" else "chain",
        )
    except (StructuredOutputError, RuntimeError, HTTPException) as exc:
        if step is not None:
            failed_step = ai_run_service.fail_step(db, step, error=str(exc))
            langsmith_observability_service.record_step_span(
                db,
                settings,
                run=run,
                step=failed_step,
                trace=trace,
                span_name="assumption_extraction",
                input_json=step.input_json,
                error=str(exc),
            )
        ai_run_service.fail_run(db, run, error=str(exc))
        langsmith_observability_service.complete_trace(settings, trace, error=str(exc))
        raise
    except Exception as exc:
        if step is not None:
            failed_step = ai_run_service.fail_step(db, step, error=str(exc))
            langsmith_observability_service.record_step_span(
                db,
                settings,
                run=run,
                step=failed_step,
                trace=trace,
                span_name="assumption_extraction",
                input_json=step.input_json,
                error=str(exc),
            )
        ai_run_service.fail_run(db, run, error=str(exc))
        langsmith_observability_service.complete_trace(settings, trace, error=str(exc))
        raise ValidationWorkflowError("Assumption extraction failed.") from exc

    run = ai_run_service.complete_run(
        db,
        run,
        output_summary=f"Created or updated {len(assumptions)} assumptions and {len(risks)} risks.",
        total_tokens=completion.total_tokens,
        total_cost=completion.total_cost,
        model_provider=completion.model_provider,
        model_name=completion.model_name,
    )
    langsmith_observability_service.attach_run_trace(db, run, trace.trace_id, trace.trace_url)
    langsmith_observability_service.complete_trace(
        settings,
        trace,
        output_summary=f"Created or updated {len(assumptions)} assumptions and {len(risks)} risks.",
        metrics={"assumption_count": len(assumptions), "risk_count": len(risks)},
    )
    db.commit()
    return AssumptionExtractionResult(
        run=run,
        step=completed_step,
        assumptions=_load_assumptions(db, auth, project.id),
        risks=_load_risks(db, auth, project.id),
        model_provider=completion.model_provider,
        model_name=completion.model_name,
        used_stub=completion.used_stub,
        total_tokens=completion.total_tokens,
        total_cost=completion.total_cost,
    )


def list_experiments(db: Session, auth: AuthContext, project_id: uuid.UUID) -> list[Experiment]:
    """List validation experiments newest-first."""

    project_service.get_project(db, auth, project_id)
    return list(
        db.scalars(
            select(Experiment)
            .where(
                Experiment.workspace_id == auth.workspace_id,
                Experiment.project_id == project_id,
            )
            .options(selectinload(Experiment.results))
            .order_by(Experiment.updated_at.desc(), Experiment.created_at.desc())
        )
    )


def get_experiment(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    experiment_id: uuid.UUID,
) -> Experiment:
    """Load one experiment scoped to the workspace and project."""

    experiment = db.scalar(
        select(Experiment)
        .where(
            Experiment.id == experiment_id,
            Experiment.workspace_id == auth.workspace_id,
            Experiment.project_id == project_id,
        )
        .options(selectinload(Experiment.results))
    )
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found.")
    return experiment


def list_validation_missions(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> list[ValidationMissionRead]:
    """List validation missions with result counts and latest interpretations."""

    project_service.get_project(db, auth, project_id)
    missions = list(
        db.scalars(
            select(ValidationMission)
            .where(
                ValidationMission.workspace_id == auth.workspace_id,
                ValidationMission.project_id == project_id,
            )
            .order_by(
                ValidationMission.status == "closed",
                ValidationMission.updated_at.desc(),
                ValidationMission.created_at.desc(),
            )
        )
    )
    return [_mission_to_read(db, mission) for mission in missions]


def get_current_validation_mission(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> ValidationMissionRead | None:
    """Return the most recently updated mission that is still actionable."""

    project_service.get_project(db, auth, project_id)
    mission = db.scalar(
        select(ValidationMission)
        .where(
            ValidationMission.workspace_id == auth.workspace_id,
            ValidationMission.project_id == project_id,
            ValidationMission.status != "closed",
        )
        .order_by(ValidationMission.updated_at.desc(), ValidationMission.created_at.desc())
        .limit(1)
    )
    if mission is None:
        mission = db.scalar(
            select(ValidationMission)
            .where(
                ValidationMission.workspace_id == auth.workspace_id,
                ValidationMission.project_id == project_id,
            )
            .order_by(ValidationMission.updated_at.desc(), ValidationMission.created_at.desc())
            .limit(1)
        )
    return _mission_to_read(db, mission) if mission is not None else None


def start_validation_mission(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    mission_id: uuid.UUID,
) -> ValidationMissionRead:
    """Mark a validation mission and its experiment as running."""

    require_permission(auth, "run_research")
    mission = _get_validation_mission(db, auth, project_id, mission_id)
    if mission.status == "planned":
        mission.status = "running"
    if mission.experiment_id is not None:
        experiment = get_experiment(db, auth, project_id, mission.experiment_id)
        if experiment.status == "planned":
            experiment.status = "running"
    governance_service.record_audit_event(
        db,
        auth,
        event_type="validation_mission_started",
        actor_type="user",
        project_id=project_id,
        entity_type="experiment",
        entity_id=mission.experiment_id or mission.id,
        risk_level="low",
        summary="Validation mission started.",
        metadata={"validation_mission_id": str(mission.id)},
    )
    db.commit()
    return _mission_to_read(db, mission)


def interpret_validation_mission(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    mission_id: uuid.UUID,
) -> ValidationInterpretationResult:
    """Interpret the current mission using previously logged result notes."""

    return interpret_validation_results(db, auth, settings, project_id, mission_id, None)


def interpret_validation_results(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    mission_id: uuid.UUID,
    payload: ValidationResultInterpretationCreate | None,
) -> ValidationInterpretationResult:
    """Turn validation notes into proposed memory updates behind approval."""

    require_permission(auth, "run_research")
    project = project_service.get_project(db, auth, project_id)
    mission = _get_validation_mission(db, auth, project_id, mission_id)
    raw_notes = _interpretation_notes(db, mission, payload)
    if not raw_notes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Paste validation notes or log mission results before interpreting them.",
        )
    run = ai_run_service.start_run(
        db,
        auth,
        workflow_type="validation_result_interpretation",
        prompt_version=VALIDATION_RESULT_INTERPRETATION_PROMPT_VERSION,
        input_summary=f"Interpret validation results for {project.name}"[:500],
        project_id=project.id,
        model_provider="stub" if settings.should_use_llm_stub else "litellm",
        model_name=settings.litellm_model,
    )
    trace = langsmith_observability_service.ensure_run_trace(
        db,
        settings,
        run,
        metadata={
            "project_id": str(project.id),
            "validation_mission_id": str(mission.id),
            "workflow_version": VALIDATION_RESULT_INTERPRETATION_PROMPT_VERSION,
            "user_id": str(auth.user_id) if auth.user_id else None,
            "model_provider": run.model_provider,
            "model_name": run.model_name,
        },
    )
    step: AIStep | None = None
    try:
        memory_selection = memory_service.select_memory_for_context(
            db,
            auth,
            project_id,
            workflow_type="validation_result_interpretation",
            limit=12,
        )
        context_pack = context_service.ContextCompiler(settings).compile_workflow_context(
            workflow_type="validation_result_interpretation",
            project_id=project_id,
            query=mission.mission_title,
            domain_context={
                "project": _project_state(project),
                "mission": _decision_mission_context(mission),
            },
            prompt_version=VALIDATION_RESULT_INTERPRETATION_PROMPT_VERSION,
            expected_schema=ValidationResultInterpretationDraft.__name__,
            memory_selection=memory_selection,
            untrusted_inputs=[
                {
                    "type": "validation",
                    "title": "Validation notes",
                    "content": raw_notes,
                    "source": "validation_result_notes",
                }
            ],
        )
        step = ai_run_service.start_step(
            db,
            run,
            step_name="interpret_validation_results",
            input_json={
                "project_id": str(project.id),
                "validation_mission_id": str(mission.id),
                "experiment_id": str(mission.experiment_id) if mission.experiment_id else None,
                "assumption_id": str(mission.assumption_id),
                "context_pack": context_pack.prompt_metadata(),
            },
        )
        started = perf_counter()
        messages = _validation_result_interpretation_messages(project, mission, raw_notes)
        if settings.should_use_llm_stub or should_use_fallback_without_model(settings):
            draft = _fallback_validation_interpretation(mission, raw_notes)
            completion = _fallback_completion(
                settings,
                messages,
                draft,
                "validation_result_interpretation_policy_always",
            )
        else:
            try:
                draft_result = generate_structured_output(
                    settings,
                    ValidationResultInterpretationDraft,
                    messages,
                    model=settings.litellm_model,
                    temperature=0.0,
                )
                draft = ValidationResultInterpretationDraft.model_validate(draft_result.parsed)
                completion = draft_result.completion
            except (StructuredOutputError, RuntimeError) as exc:
                if not should_use_fallback_after_error(settings):
                    raise
                draft = _fallback_validation_interpretation(mission, raw_notes)
                completion = _fallback_completion(
                    settings,
                    messages,
                    draft,
                    "validation_result_interpretation_emergency",
                    exc,
                )
        interpretation = _write_validation_interpretation(
            db,
            auth,
            mission,
            run,
            raw_notes,
            draft,
        )
        db.flush()
        # Interpretation can affect strategic memory, so it creates a proposal
        # record rather than mutating assumptions, risks, or thesis state inline.
        approval = _create_validation_interpretation_approval(db, auth, interpretation)
        interpretation.approval_request_id = approval.id
        if mission.status in {"planned", "running", "results_logged"}:
            mission.status = "interpreted"
        if mission.experiment_id is not None:
            experiment = get_experiment(db, auth, project_id, mission.experiment_id)
            if experiment.status in {"planned", "running"}:
                experiment.status = "completed"
        db.flush()
        completed_step = ai_run_service.complete_step(
            db,
            step,
            output_json={
                "validation_interpretation_id": str(interpretation.id),
                "approval_request_id": str(approval.id),
                "confidence_change": interpretation.confidence_change,
                "decision_recommendation": interpretation.decision_recommendation,
            },
            latency_ms=int((perf_counter() - started) * 1000),
            tokens=completion.total_tokens,
            cost=completion.total_cost,
        )
        langsmith_observability_service.record_step_span(
            db,
            settings,
            run=run,
            step=completed_step,
            trace=trace,
            span_name="validation_result_interpretation",
            input_json=step.input_json,
            output_json=completed_step.output_json,
            run_type="llm" if completion.model_provider != "stub" else "chain",
        )
    except (StructuredOutputError, RuntimeError, HTTPException) as exc:
        if step is not None:
            failed_step = ai_run_service.fail_step(db, step, error=str(exc))
            langsmith_observability_service.record_step_span(
                db,
                settings,
                run=run,
                step=failed_step,
                trace=trace,
                span_name="validation_result_interpretation",
                input_json=step.input_json,
                error=str(exc),
            )
        ai_run_service.fail_run(db, run, error=str(exc))
        langsmith_observability_service.complete_trace(settings, trace, error=str(exc))
        raise
    except Exception as exc:
        if step is not None:
            failed_step = ai_run_service.fail_step(db, step, error=str(exc))
            langsmith_observability_service.record_step_span(
                db,
                settings,
                run=run,
                step=failed_step,
                trace=trace,
                span_name="validation_result_interpretation",
                input_json=step.input_json,
                error=str(exc),
            )
        ai_run_service.fail_run(db, run, error=str(exc))
        langsmith_observability_service.complete_trace(settings, trace, error=str(exc))
        raise ValidationWorkflowError("Validation result interpretation failed.") from exc

    run = ai_run_service.complete_run(
        db,
        run,
        output_summary=interpretation.signal_summary[:1000],
        total_tokens=completion.total_tokens,
        total_cost=completion.total_cost,
        model_provider=completion.model_provider,
        model_name=completion.model_name,
    )
    interpretation.ai_run_id = run.id
    langsmith_observability_service.attach_run_trace(db, run, trace.trace_id, trace.trace_url)
    langsmith_observability_service.complete_trace(
        settings,
        trace,
        output_summary=interpretation.signal_summary[:1000],
        metrics={
            "proposed_confidence_delta": float(interpretation.proposed_confidence_delta),
            "decision_recommendation": interpretation.decision_recommendation,
        },
    )
    governance_service.record_audit_event(
        db,
        auth,
        event_type="validation_results_interpreted",
        actor_type="agent",
        project_id=project_id,
        entity_type="validation_interpretation",
        entity_id=interpretation.id,
        risk_level="medium",
        summary="Validation notes interpreted and project updates proposed.",
        metadata={
            "validation_mission_id": str(mission.id),
            "approval_request_id": str(approval.id),
        },
    )
    db.commit()
    db.refresh(interpretation)
    db.refresh(run)
    return ValidationInterpretationResult(
        run=run,
        step=completed_step,
        mission=_mission_to_read(db, mission),
        interpretation=ValidationResultInterpretationRead.model_validate(interpretation),
        approval_request=approval,
        model_provider=completion.model_provider,
        model_name=completion.model_name,
        used_stub=completion.used_stub,
        total_tokens=completion.total_tokens,
        total_cost=completion.total_cost,
    )


def generate_validation_plan(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    payload: ValidationPlanGenerateCreate,
) -> ValidationPlanResult:
    """Generate testable validation missions for selected high-risk assumptions."""

    require_permission(auth, "run_research")
    project = project_service.get_project(db, auth, project_id)
    assumptions = _selected_assumptions(db, auth, project_id, payload)
    if not assumptions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Create or extract assumptions before generating validation plans.",
        )
    run = ai_run_service.start_run(
        db,
        auth,
        workflow_type="validation_plan",
        prompt_version=VALIDATION_PLAN_PROMPT_VERSION,
        input_summary=f"Generate validation plans for {project.name}"[:500],
        project_id=project.id,
        model_provider="stub" if settings.should_use_llm_stub else "litellm",
        model_name=settings.litellm_model,
    )
    trace = langsmith_observability_service.ensure_run_trace(
        db,
        settings,
        run,
        metadata={
            "project_id": str(project.id),
            "workflow_version": VALIDATION_PLAN_PROMPT_VERSION,
            "user_id": str(auth.user_id) if auth.user_id else None,
            "model_provider": run.model_provider,
            "model_name": run.model_name,
        },
    )
    step: AIStep | None = None
    try:
        memory_selection = memory_service.select_memory_for_context(
            db,
            auth,
            project_id,
            workflow_type="validation_plan",
            limit=12,
        )
        context_pack = context_service.ContextCompiler(settings).compile_workflow_context(
            workflow_type="validation_plan",
            project_id=project_id,
            query="validation plan",
            domain_context={
                "project": _project_state(project),
                "assumptions": [
                    {
                        "id": str(assumption.id),
                        "text": assumption.text,
                        "category": assumption.category,
                        "importance": assumption.importance,
                        "uncertainty": assumption.uncertainty,
                    }
                    for assumption in assumptions
                ],
            },
            prompt_version=VALIDATION_PLAN_PROMPT_VERSION,
            expected_schema=ValidationPlanSetDraft.__name__,
            memory_selection=memory_selection,
        )
        step = ai_run_service.start_step(
            db,
            run,
            step_name="generate_validation_plan",
            input_json={
                "project_id": str(project.id),
                "assumption_ids": [str(item.id) for item in assumptions],
                "context_pack": context_pack.prompt_metadata(),
            },
        )
        started = perf_counter()
        messages = _validation_plan_messages(project, assumptions)
        if should_use_fallback_without_model(settings):
            draft = _fallback_validation_plan(project, assumptions)
            completion = _fallback_completion(
                settings,
                messages,
                draft,
                "validation_plan_policy_always",
            )
        else:
            try:
                draft_result = generate_structured_output(
                    settings,
                    ValidationPlanSetDraft,
                    messages,
                    model=settings.litellm_model,
                    temperature=0.0,
                )
                draft = ValidationPlanSetDraft.model_validate(draft_result.parsed)
                completion = draft_result.completion
            except (StructuredOutputError, RuntimeError) as exc:
                if not should_use_fallback_after_error(settings):
                    raise
                draft = _fallback_validation_plan(project, assumptions)
                completion = _fallback_completion(
                    settings,
                    messages,
                    draft,
                    "validation_plan_emergency",
                    exc,
                )
        artifact = _write_validation_plan_artifact(db, auth, run, project, draft, trace)
        experiments = _write_experiments(db, auth, project, assumptions, draft)
        db.flush()
        missions = _write_validation_missions(db, auth, project, assumptions, experiments, draft)
        db.flush()
        completed_step = ai_run_service.complete_step(
            db,
            step,
            output_json={
                "artifact_id": str(artifact.id),
                "experiment_ids": [str(item.id) for item in experiments],
                "validation_mission_ids": [str(item.id) for item in missions],
            },
            latency_ms=int((perf_counter() - started) * 1000),
            tokens=completion.total_tokens,
            cost=completion.total_cost,
        )
        langsmith_observability_service.record_step_span(
            db,
            settings,
            run=run,
            step=completed_step,
            trace=trace,
            span_name="validation_plan_generation",
            input_json=step.input_json,
            output_json=completed_step.output_json,
            run_type="llm" if completion.model_provider != "stub" else "chain",
        )
    except (StructuredOutputError, RuntimeError, HTTPException) as exc:
        if step is not None:
            failed_step = ai_run_service.fail_step(db, step, error=str(exc))
            langsmith_observability_service.record_step_span(
                db,
                settings,
                run=run,
                step=failed_step,
                trace=trace,
                span_name="validation_plan_generation",
                input_json=step.input_json,
                error=str(exc),
            )
        ai_run_service.fail_run(db, run, error=str(exc))
        langsmith_observability_service.complete_trace(settings, trace, error=str(exc))
        raise
    except Exception as exc:
        if step is not None:
            failed_step = ai_run_service.fail_step(db, step, error=str(exc))
            langsmith_observability_service.record_step_span(
                db,
                settings,
                run=run,
                step=failed_step,
                trace=trace,
                span_name="validation_plan_generation",
                input_json=step.input_json,
                error=str(exc),
            )
        ai_run_service.fail_run(db, run, error=str(exc))
        langsmith_observability_service.complete_trace(settings, trace, error=str(exc))
        raise ValidationWorkflowError("Validation plan generation failed.") from exc

    run = ai_run_service.complete_run(
        db,
        run,
        output_summary=draft.summary[:1000],
        total_tokens=completion.total_tokens,
        total_cost=completion.total_cost,
        model_provider=completion.model_provider,
        model_name=completion.model_name,
    )
    langsmith_observability_service.attach_run_trace(db, run, trace.trace_id, trace.trace_url)
    langsmith_observability_service.complete_trace(
        settings,
        trace,
        output_summary=draft.summary[:1000],
        metrics={"experiment_count": len(experiments)},
    )
    governance_service.record_audit_event(
        db,
        auth,
        event_type="validation_plan_created",
        actor_type="user",
        project_id=project.id,
        entity_type="artifact",
        entity_id=artifact.id,
        risk_level="medium",
        summary="Validation plan generated and experiments created.",
        metadata={
            "artifact_id": str(artifact.id),
            "experiment_ids": [str(item.id) for item in experiments],
            "validation_mission_ids": [str(item.id) for item in missions],
        },
    )
    db.commit()
    artifact = _get_artifact(db, auth, project.id, artifact.id)
    experiments = [
        get_experiment(db, auth, project.id, experiment.id) for experiment in experiments
    ]
    mission_reads = [_mission_to_read(db, mission) for mission in missions]
    return ValidationPlanResult(
        run=run,
        step=completed_step,
        artifact=artifact,
        experiments=experiments,
        missions=mission_reads,
        model_provider=completion.model_provider,
        model_name=completion.model_name,
        used_stub=completion.used_stub,
        total_tokens=completion.total_tokens,
        total_cost=completion.total_cost,
    )


def log_experiment_result(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    experiment_id: uuid.UUID,
    payload: ExperimentResultCreate,
) -> ExperimentResultLogResult:
    """Persist field notes for an experiment and update confidence heuristics."""

    require_permission(auth, "run_research")
    experiment = get_experiment(db, auth, project_id, experiment_id)
    delta = _result_delta(payload)
    result = ExperimentResult(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        experiment_id=experiment.id,
        result_summary=payload.result_summary.strip(),
        outcome=payload.outcome,
        confidence_delta=delta,
        raw_notes=payload.raw_notes,
        created_by=auth.user_id,
    )
    db.add(result)
    experiment.status = "completed"
    assumption = None
    if experiment.assumption_id is not None:
        assumption = get_assumption(db, auth, project_id, experiment.assumption_id)
        current_score = assumption.confidence_score or Decimal("0.5")
        assumption.confidence_score = _clamp_decimal(current_score + delta)
        assumption.status = _assumption_status_for_outcome(payload.outcome)
    mission = db.scalar(
        select(ValidationMission).where(
            ValidationMission.workspace_id == auth.workspace_id,
            ValidationMission.project_id == project_id,
            ValidationMission.experiment_id == experiment.id,
        )
    )
    if mission is not None and mission.status in {"planned", "running"}:
        mission.status = "results_logged"
    project_confidence = _recalculate_project_confidence(db, auth, project_id)
    governance_service.record_audit_event(
        db,
        auth,
        event_type="experiment_result_logged",
        actor_type="user",
        project_id=project_id,
        entity_type="experiment",
        entity_id=experiment.id,
        risk_level="low",
        summary="Experiment result logged and confidence updated.",
        metadata={
            "experiment_result_id": str(result.id),
            "outcome": payload.outcome,
            "confidence_delta": str(delta),
        },
    )
    db.commit()
    return ExperimentResultLogResult(
        result=result,
        experiment=get_experiment(db, auth, project_id, experiment.id),
        assumption=assumption,
        project_confidence_score=project_confidence,
    )


def list_decisions(db: Session, auth: AuthContext, project_id: uuid.UUID) -> list[Decision]:
    """List recorded strategic decisions for a project."""

    project_service.get_project(db, auth, project_id)
    return list(
        db.scalars(
            select(Decision)
            .where(Decision.workspace_id == auth.workspace_id, Decision.project_id == project_id)
            .options(selectinload(Decision.links))
            .order_by(Decision.created_at.desc())
        )
    )


def get_decision(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    decision_id: uuid.UUID,
) -> Decision:
    """Load one recorded decision and its linked evidence entities."""

    decision = db.scalar(
        select(Decision)
        .where(
            Decision.id == decision_id,
            Decision.workspace_id == auth.workspace_id,
            Decision.project_id == project_id,
        )
        .options(selectinload(Decision.links))
    )
    if decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found.")
    return decision


def create_decision(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    payload: DecisionCreate,
) -> Decision:
    """Record a user decision with validated links to evidence and experiments."""

    require_permission(auth, "record_decision")
    project_service.get_project(db, auth, project_id)
    links = _validated_decision_links(db, auth, project_id, payload)
    decision = Decision(
        workspace_id=auth.workspace_id,
        project_id=project_id,
        decision_type=payload.decision_type,
        title=payload.title.strip(),
        rationale=payload.rationale,
        expected_outcome=payload.expected_outcome,
        review_date=payload.review_date,
        created_by=auth.user_id,
    )
    db.add(decision)
    db.flush()
    for linked_type, linked_id in links:
        db.add(DecisionLink(decision_id=decision.id, linked_type=linked_type, linked_id=linked_id))
    governance_service.record_audit_event(
        db,
        auth,
        event_type="decision_recorded",
        actor_type="user",
        project_id=project_id,
        entity_type="decision",
        entity_id=decision.id,
        risk_level="medium",
        summary=f"Decision recorded: {decision.title}",
        metadata={
            "decision_type": decision.decision_type,
            "linked_count": len(links),
        },
    )
    db.commit()
    return get_decision(db, auth, project_id, decision.id)


def get_decision_recommendation(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> DecisionRecommendationRead:
    """Compute deterministic decision guidance from assumptions, results, and evidence."""

    project_service.get_project(db, auth, project_id)
    assumptions = _load_assumptions(db, auth, project_id)
    risks = _load_risks(db, auth, project_id)
    evidence_sources = _load_decision_evidence_sources(db, auth, project_id)
    experiments = _load_decision_experiments(db, auth, project_id)
    interpretation = _latest_project_validation_interpretation(db, auth, project_id)
    mission = _decision_validation_mission(db, auth, project_id, interpretation)
    recommendation = _decision_recommendation_value(
        assumptions=assumptions,
        experiments=experiments,
        interpretation=interpretation,
    )
    supporting_evidence = _decision_supporting_evidence(
        assumptions=assumptions,
        evidence_sources=evidence_sources,
        experiments=experiments,
        interpretation=interpretation,
    )
    missing_evidence = _decision_missing_evidence(
        assumptions=assumptions,
        evidence_sources=evidence_sources,
        experiments=experiments,
        interpretation=interpretation,
        mission=mission,
    )
    risk_texts = _decision_risks(assumptions, risks, interpretation)
    rationale = _decision_recommendation_rationale(
        recommendation=recommendation,
        supporting_evidence=supporting_evidence,
        missing_evidence=missing_evidence,
        interpretation=interpretation,
    )
    evidence_labels = _decision_evidence_labels(
        recommendation=recommendation,
        supporting_evidence=supporting_evidence,
        missing_evidence=missing_evidence,
        interpretation=interpretation,
    )
    suggested_record = _suggested_decision_record(
        recommendation=recommendation,
        rationale=rationale,
        supporting_evidence=supporting_evidence,
        missing_evidence=missing_evidence,
        risks=risk_texts,
        assumptions=assumptions,
        risks_rows=risks,
        evidence_sources=evidence_sources,
        experiments=experiments,
        interpretation=interpretation,
        mission=mission,
    )
    memory_selection = memory_service.select_memory_for_context(
        db,
        auth,
        project_id,
        workflow_type="decision_recommendation",
    )
    context_pack = context_service.ContextCompiler(get_settings()).compile_workflow_context(
        workflow_type="decision_recommendation",
        project_id=project_id,
        query="Recommend whether to proceed, pivot, pause, kill, or continue research.",
        domain_context=_decision_context_domain(
            assumptions=assumptions,
            risks=risks,
            evidence_sources=evidence_sources,
            experiments=experiments,
            interpretation=interpretation,
            mission=mission,
            recommendation=recommendation,
            supporting_evidence=supporting_evidence,
            missing_evidence=missing_evidence,
            risk_texts=risk_texts,
        ),
        prompt_version="decision-recommendation:deterministic:v1",
        expected_schema="DecisionRecommendationRead",
        memory_selection=memory_selection,
        untrusted_inputs=_decision_context_untrusted_inputs(
            evidence_sources=evidence_sources,
            interpretation=interpretation,
            experiments=experiments,
        ),
    )
    return DecisionRecommendationRead(
        recommendation=recommendation,
        rationale=rationale,
        supporting_evidence=supporting_evidence,
        missing_evidence=missing_evidence,
        risks=risk_texts,
        evidence_labels=evidence_labels,
        suggested_decision_record=suggested_record,
        action_cards=_decision_action_cards(project_id, recommendation, bool(mission)),
        context_pack=context_pack,
    )


def chat_decision_coach(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    message: str,
) -> DecisionCoachChatRead:
    """Return a bounded decision-coach answer over the deterministic recommendation."""

    recommendation = get_decision_recommendation(db, auth, project_id)
    normalized = message.casefold()
    missing = _format_bullets(recommendation.missing_evidence)
    supporting = _format_bullets(recommendation.supporting_evidence)
    risks = _format_bullets(recommendation.risks)

    if any(term in normalized for term in ("why not", "build", "proceed", "can i build")):
        if recommendation.recommendation == "proceed":
            answer = (
                "A narrow proceed decision is currently supportable, but only within the "
                "validated wedge. Keep the build scoped to the proof that was actually "
                f"supported. Supporting evidence: {supporting}"
            )
        else:
            answer = f"Do not proceed yet. {recommendation.rationale} Missing proof: {missing}"
    elif "pivot" in normalized:
        answer = (
            "A pivot is warranted when the validation signal weakens the current wedge "
            "but still reveals a different user, problem, or buying trigger worth testing. "
            "Current recommendation: "
            f"{_decision_recommendation_label(recommendation.recommendation)}. "
            f"Risks to consider: {risks}"
        )
    elif any(term in normalized for term in ("missing", "evidence", "proof")):
        answer = f"The missing proof is: {missing}"
    elif "kill" in normalized:
        answer = (
            "Killing the idea is appropriate only when the core pain, urgency, or "
            "willingness-to-pay signal is weak enough that another small test would not "
            f"change the decision. Current recommendation: "
            f"{_decision_recommendation_label(recommendation.recommendation)}."
        )
    elif any(term in normalized for term in ("summarize", "notes", "record")):
        record = recommendation.suggested_decision_record
        answer = (
            f"Suggested record: {record.title}. "
            f"Rationale: {record.rationale} "
            f"Expected outcome: {record.expected_outcome}"
        )
    else:
        answer = (
            f"Recommended decision: "
            f"{_decision_recommendation_label(recommendation.recommendation)}. "
            f"{recommendation.rationale}"
        )

    return DecisionCoachChatRead(
        answer=answer,
        recommendation=recommendation.recommendation,
        rationale=recommendation.rationale,
        supporting_evidence=recommendation.supporting_evidence,
        missing_evidence=recommendation.missing_evidence,
        evidence_labels=recommendation.evidence_labels,
        action_cards=recommendation.action_cards,
    )


def _load_decision_evidence_sources(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> list[EvidenceSource]:
    return list(
        db.scalars(
            select(EvidenceSource)
            .where(
                EvidenceSource.workspace_id == auth.workspace_id,
                EvidenceSource.project_id == project_id,
            )
            .order_by(EvidenceSource.created_at.desc())
        )
    )


def _load_decision_experiments(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> list[Experiment]:
    return list(
        db.scalars(
            select(Experiment)
            .where(
                Experiment.workspace_id == auth.workspace_id,
                Experiment.project_id == project_id,
            )
            .options(selectinload(Experiment.results))
            .order_by(Experiment.updated_at.desc())
        )
    )


def _latest_project_validation_interpretation(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> ValidationResultInterpretation | None:
    return db.scalar(
        select(ValidationResultInterpretation)
        .where(
            ValidationResultInterpretation.workspace_id == auth.workspace_id,
            ValidationResultInterpretation.project_id == project_id,
        )
        .order_by(ValidationResultInterpretation.created_at.desc())
        .limit(1)
    )


def _decision_validation_mission(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    interpretation: ValidationResultInterpretation | None,
) -> ValidationMission | None:
    if interpretation is not None:
        mission = db.scalar(
            select(ValidationMission).where(
                ValidationMission.id == interpretation.mission_id,
                ValidationMission.workspace_id == auth.workspace_id,
                ValidationMission.project_id == project_id,
            )
        )
        if mission is not None:
            return mission
    return db.scalar(
        select(ValidationMission)
        .where(
            ValidationMission.workspace_id == auth.workspace_id,
            ValidationMission.project_id == project_id,
        )
        .order_by(ValidationMission.updated_at.desc())
        .limit(1)
    )


_decision_context_domain = decision_recommendation_feature.decision_context_domain
_decision_interpretation_context = (
    decision_recommendation_feature.decision_interpretation_context
)
_decision_mission_context = decision_recommendation_feature.decision_mission_context
_decision_context_untrusted_inputs = (
    decision_recommendation_feature.decision_context_untrusted_inputs
)
_decision_recommendation_value = decision_recommendation_feature.decision_recommendation_value
_decision_supporting_evidence = decision_recommendation_feature.decision_supporting_evidence
_decision_missing_evidence = decision_recommendation_feature.decision_missing_evidence
_decision_risks = decision_recommendation_feature.decision_risks
_decision_recommendation_rationale = (
    decision_recommendation_feature.decision_recommendation_rationale
)
_decision_evidence_labels = decision_recommendation_feature.decision_evidence_labels
_suggested_decision_record = decision_recommendation_feature.suggested_decision_record
_decision_linked_assumption_ids = (
    decision_recommendation_feature.decision_linked_assumption_ids
)
_decision_linked_experiment_ids = (
    decision_recommendation_feature.decision_linked_experiment_ids
)
_decision_action_cards = decision_recommendation_feature.decision_action_cards
_decision_record_markdown = decision_recommendation_feature.decision_record_markdown
_decision_type_for_recommendation = (
    decision_recommendation_feature.decision_type_for_recommendation
)
_decision_title_for_recommendation = (
    decision_recommendation_feature.decision_title_for_recommendation
)
_decision_expected_outcome = decision_recommendation_feature.decision_expected_outcome
_decision_revisit_trigger = decision_recommendation_feature.decision_revisit_trigger
_decision_recommendation_label = decision_recommendation_feature.decision_recommendation_label
_format_bullets = decision_recommendation_feature.format_bullets
_dedupe_strings = decision_recommendation_feature.dedupe_strings
_dedupe_uuids = decision_recommendation_feature.dedupe_uuids
_validation_mission_context = result_interpretation.validation_mission_context
_validation_result_interpretation_prompt_messages = (
    result_interpretation.validation_result_interpretation_messages
)
_validation_interpretation_proposed_updates = (
    result_interpretation.validation_interpretation_proposed_updates
)


def current_version(artifact: Artifact) -> ArtifactVersion | None:
    if artifact.current_version_id is None:
        return None
    return next(
        (version for version in artifact.versions if version.id == artifact.current_version_id),
        None,
    )


def _project_state(project: Project) -> dict[str, Any]:
    thesis = project_service.current_thesis(project)
    return {
        "id": str(project.id),
        "name": project.name,
        "short_description": project.short_description,
        "current_thesis": thesis.thesis_text if thesis else None,
        "customer_segments": [segment.name for segment in project.customer_segments],
        "problem_hypotheses": [problem.description for problem in project.problems],
        "confidence_score": str(project.confidence_score) if project.confidence_score else None,
    }


def _assumption_messages(project: Project, project_state: dict[str, Any]) -> list[ChatMessage]:
    return validation_generation.assumption_messages(project.name, project_state)


def _validation_plan_messages(
    project: Project,
    assumptions: list[Assumption],
) -> list[ChatMessage]:
    return validation_generation.validation_plan_messages(
        project.name,
        _project_state(project),
        assumptions,
    )


def _validation_result_interpretation_messages(
    project: Project,
    mission: ValidationMission,
    raw_notes: str,
) -> list[ChatMessage]:
    return _validation_result_interpretation_prompt_messages(
        project_state=_project_state(project),
        mission_context=_validation_mission_context(mission),
        raw_notes=raw_notes,
    )


def _fallback_assumption_extraction(project: Project) -> AssumptionExtractionDraft:
    return validation_generation.fallback_assumption_extraction(project.name)


def _fallback_validation_plan(
    project: Project,
    assumptions: list[Assumption],
) -> ValidationPlanSetDraft:
    return validation_generation.fallback_validation_plan(project.name, assumptions)


def _fallback_validation_plan_item(assumption: Assumption) -> ValidationPlanDraft:
    return validation_generation.fallback_validation_plan_item(assumption)


def _fallback_completion(
    settings: Settings,
    messages: list[ChatMessage],
    draft: AssumptionExtractionDraft | ValidationPlanSetDraft | ValidationResultInterpretationDraft,
    fallback_name: str,
    error: BaseException | None = None,
) -> LLMCompletion:
    return fallback_completion(settings, messages, draft, fallback_name, error)


def _selected_assumptions(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    payload: ValidationPlanGenerateCreate,
) -> list[Assumption]:
    if payload.assumption_ids:
        assumptions = [
            get_assumption(db, auth, project_id, assumption_id)
            for assumption_id in payload.assumption_ids
        ]
        return assumptions[: payload.max_plans]
    return _load_assumptions(db, auth, project_id)[: payload.max_plans]


def _load_assumptions(db: Session, auth: AuthContext, project_id: uuid.UUID) -> list[Assumption]:
    importance_rank = case(
        (Assumption.importance == "critical", 0),
        (Assumption.importance == "high", 1),
        (Assumption.importance == "medium", 2),
        else_=3,
    )
    uncertainty_rank = case(
        (Assumption.uncertainty == "high", 0),
        (Assumption.uncertainty == "medium", 1),
        else_=2,
    )
    return list(
        db.scalars(
            select(Assumption)
            .where(
                Assumption.workspace_id == auth.workspace_id,
                Assumption.project_id == project_id,
            )
            .order_by(
                Assumption.kill_risk.desc(),
                importance_rank,
                uncertainty_rank,
                Assumption.created_at,
            )
        )
    )


def _load_risks(db: Session, auth: AuthContext, project_id: uuid.UUID) -> list[Risk]:
    severity_rank = case(
        (Risk.severity == "critical", 0),
        (Risk.severity == "high", 1),
        (Risk.severity == "medium", 2),
        else_=3,
    )
    return list(
        db.scalars(
            select(Risk)
            .where(Risk.workspace_id == auth.workspace_id, Risk.project_id == project_id)
            .order_by(severity_rank, Risk.created_at)
        )
    )


def _upsert_assumptions(
    db: Session,
    auth: AuthContext,
    project: Project,
    drafts: list[AssumptionDraft],
) -> list[Assumption]:
    existing = {
        _normalize_key(assumption.text): assumption
        for assumption in db.scalars(
            select(Assumption).where(
                Assumption.workspace_id == auth.workspace_id,
                Assumption.project_id == project.id,
            )
        )
    }
    assumptions: list[Assumption] = []
    for draft in drafts:
        key = _normalize_key(draft.text)
        assumption = existing.get(key)
        if assumption is None:
            assumption = Assumption(
                workspace_id=auth.workspace_id,
                project_id=project.id,
                text=draft.text.strip(),
                category=_optional_truncate(draft.category, 100),
                importance=draft.importance,
                uncertainty=draft.uncertainty,
                kill_risk=draft.kill_risk,
                confidence_score=_decimal_score(draft.confidence_score),
                status="untested",
                recommended_test=draft.recommended_test,
            )
            db.add(assumption)
            existing[key] = assumption
        else:
            assumption.category = _optional_truncate(draft.category, 100)
            assumption.importance = draft.importance
            assumption.uncertainty = draft.uncertainty
            assumption.kill_risk = draft.kill_risk
            assumption.confidence_score = _decimal_score(draft.confidence_score)
            assumption.recommended_test = draft.recommended_test
        assumptions.append(assumption)
    return assumptions


def _upsert_risks(
    db: Session,
    auth: AuthContext,
    project: Project,
    drafts: list[RiskDraft],
) -> list[Risk]:
    existing = {
        _normalize_key(risk.text): risk
        for risk in db.scalars(
            select(Risk).where(
                Risk.workspace_id == auth.workspace_id,
                Risk.project_id == project.id,
            )
        )
    }
    risks: list[Risk] = []
    for draft in drafts:
        key = _normalize_key(draft.text)
        risk = existing.get(key)
        if risk is None:
            risk = Risk(
                workspace_id=auth.workspace_id,
                project_id=project.id,
                text=draft.text.strip(),
                category=_optional_truncate(draft.category, 100),
                severity=draft.severity,
                likelihood=draft.likelihood,
                mitigation=draft.mitigation,
                status="open",
            )
            db.add(risk)
            existing[key] = risk
        else:
            risk.category = _optional_truncate(draft.category, 100)
            risk.severity = draft.severity
            risk.likelihood = draft.likelihood
            risk.mitigation = draft.mitigation
        risks.append(risk)
    return risks


def _write_validation_plan_artifact(
    db: Session,
    auth: AuthContext,
    run: AIRun,
    project: Project,
    draft: ValidationPlanSetDraft,
    trace: langsmith_observability_service.TraceContext,
) -> Artifact:
    artifact = db.scalar(
        select(Artifact).where(
            Artifact.workspace_id == auth.workspace_id,
            Artifact.project_id == project.id,
            Artifact.artifact_type == "validation_plan",
        )
    )
    if artifact is None:
        artifact = Artifact(
            workspace_id=auth.workspace_id,
            project_id=project.id,
            artifact_type="validation_plan",
            title=f"{project.name} Validation Plan",
            created_by=auth.user_id,
        )
        db.add(artifact)
        db.flush()
    version = ArtifactVersion(
        workspace_id=auth.workspace_id,
        artifact_id=artifact.id,
        version=_next_artifact_version(db, artifact.id),
        markdown_content=_render_validation_plan_markdown(project, draft),
        structured_content={
            **draft.model_dump(mode="json"),
            "citation_outcomes": [],
            "citation_verification_status": "not_applicable_no_claim_citations",
        },
        generated_by_ai_run_id=run.id,
        langsmith_trace_id=trace.trace_id,
        langsmith_trace_url=trace.trace_url,
        created_by=auth.user_id,
    )
    db.add(version)
    db.flush()
    artifact.current_version_id = version.id
    return artifact


def _write_experiments(
    db: Session,
    auth: AuthContext,
    project: Project,
    assumptions: list[Assumption],
    draft: ValidationPlanSetDraft,
) -> list[Experiment]:
    assumptions_by_id = {assumption.id: assumption for assumption in assumptions}
    experiments: list[Experiment] = []
    for plan in draft.plans:
        assumption = assumptions_by_id.get(plan.assumption_id)
        if assumption is None:
            continue
        experiment = Experiment(
            workspace_id=auth.workspace_id,
            project_id=project.id,
            assumption_id=assumption.id,
            name=f"Validate: {_shorten(assumption.text, 90)}",
            method=_optional_truncate(plan.method, 120),
            plan=_render_experiment_plan(plan.model_dump(mode="json")),
            success_criteria=plan.success_criteria,
            failure_threshold=plan.failure_threshold,
            status="planned",
        )
        db.add(experiment)
        assumption.status = "testing"
        experiments.append(experiment)
    return experiments


def _write_validation_missions(
    db: Session,
    auth: AuthContext,
    project: Project,
    assumptions: list[Assumption],
    experiments: list[Experiment],
    draft: ValidationPlanSetDraft,
) -> list[ValidationMission]:
    assumptions_by_id = {assumption.id: assumption for assumption in assumptions}
    experiments_by_assumption_id = {
        experiment.assumption_id: experiment
        for experiment in experiments
        if experiment.assumption_id is not None
    }
    missions: list[ValidationMission] = []
    for plan in draft.plans:
        assumption = assumptions_by_id.get(plan.assumption_id)
        experiment = experiments_by_assumption_id.get(plan.assumption_id)
        if assumption is None or experiment is None:
            continue
        mission = ValidationMission(
            workspace_id=auth.workspace_id,
            project_id=project.id,
            assumption_id=assumption.id,
            experiment_id=experiment.id,
            mission_title=f"Prove: {_shorten(assumption.text, 110)}",
            why_it_matters=_mission_why_it_matters(assumption),
            target_user=plan.target_respondent,
            test_type=_optional_truncate(plan.method, 120) or "validation_test",
            steps=_mission_steps(plan),
            success_criteria=plan.success_criteria,
            failure_criteria=plan.failure_threshold,
            assets=_mission_assets(plan),
            status="planned",
            created_by=auth.user_id,
        )
        db.add(mission)
        missions.append(mission)
    return missions


def _interpretation_notes(
    db: Session,
    mission: ValidationMission,
    payload: ValidationResultInterpretationCreate | None,
) -> str:
    parts: list[str] = []
    if payload and payload.raw_notes:
        parts.append(payload.raw_notes.strip())
    include_logged = payload.include_logged_results if payload is not None else True
    if include_logged and mission.experiment_id is not None:
        results = list(
            db.scalars(
                select(ExperimentResult)
                .where(
                    ExperimentResult.workspace_id == mission.workspace_id,
                    ExperimentResult.project_id == mission.project_id,
                    ExperimentResult.experiment_id == mission.experiment_id,
                )
                .order_by(ExperimentResult.created_at)
            )
        )
        for index, result in enumerate(results, start=1):
            parts.append(
                "\n".join(
                    item
                    for item in [
                        f"Logged result {index}: {result.result_summary}",
                        f"Outcome: {result.outcome}",
                        f"Confidence delta: {result.confidence_delta}",
                        f"Raw notes: {result.raw_notes}" if result.raw_notes else "",
                    ]
                    if item
                )
            )
    return "\n\n".join(part for part in parts if part).strip()


def _write_validation_interpretation(
    db: Session,
    auth: AuthContext,
    mission: ValidationMission,
    run: AIRun,
    raw_notes: str,
    draft: ValidationResultInterpretationDraft,
) -> ValidationResultInterpretation:
    signal = draft.signal
    proposed_updates = _validation_interpretation_proposed_updates(mission, draft)
    interpretation = ValidationResultInterpretation(
        workspace_id=auth.workspace_id,
        project_id=mission.project_id,
        mission_id=mission.id,
        experiment_id=mission.experiment_id,
        assumption_id=mission.assumption_id,
        ai_run_id=run.id,
        raw_notes=raw_notes,
        signal_summary=draft.signal_summary,
        what_strengthened=draft.what_strengthened,
        what_weakened=draft.what_weakened,
        pain_severity=signal.pain_severity,
        current_workaround=signal.current_workaround,
        urgency=signal.urgency,
        willingness_to_pay=signal.willingness_to_pay,
        switching_signal=signal.switching_signal,
        objections=signal.objections,
        quotes=signal.quotes,
        confidence_change=signal.confidence_change,
        confidence_rationale=draft.confidence_rationale,
        recommended_next_action=signal.recommended_next_action,
        decision_recommendation=draft.decision_recommendation,
        proposed_confidence_delta=_decimal_score(draft.proposed_confidence_delta) or Decimal("0"),
        proposed_assumption_status=draft.proposed_assumption_status,
        proposed_updates=proposed_updates,
        created_by=auth.user_id,
    )
    db.add(interpretation)
    return interpretation


def _create_validation_interpretation_approval(
    db: Session,
    auth: AuthContext,
    interpretation: ValidationResultInterpretation,
) -> ApprovalRequest:
    return governance_service.create_approval_request(
        db,
        auth,
        project_id=interpretation.project_id,
        request_type="memory_update",
        requested_by="agent",
        risk_level="medium",
        summary=(
            "Apply interpreted validation signal to assumption confidence, mission history, "
            "and the decision trail."
        ),
        proposed_change=interpretation.proposed_updates,
        entity_type="validation_interpretation",
        entity_id=interpretation.id,
    )


def apply_validation_interpretation_approval(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    approval_id: uuid.UUID,
) -> ApprovalRequest:
    approval = db.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.workspace_id == auth.workspace_id,
            ApprovalRequest.project_id == project_id,
            ApprovalRequest.entity_type == "validation_interpretation",
        )
    )
    if approval is None or approval.entity_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Validation interpretation approval not found.",
        )
    interpretation = _get_validation_interpretation(db, auth, project_id, approval.entity_id)
    approval = governance_service.approve_approval_request(db, auth, project_id, approval_id)
    project = project_service.get_project(db, auth, project_id)
    memory_item_id: uuid.UUID | None = None
    if interpretation.assumption_id is not None:
        assumption = get_assumption(db, auth, project_id, interpretation.assumption_id)
        current_score = assumption.confidence_score or Decimal("0.5")
        assumption.confidence_score = _clamp_decimal(
            current_score + interpretation.proposed_confidence_delta
        )
        if interpretation.proposed_assumption_status:
            assumption.status = interpretation.proposed_assumption_status
        memory_item = memory_service.upsert_from_assumption(
            db,
            auth,
            project_id,
            assumption,
            source_entity_type="validation_interpretation",
            source_entity_id=interpretation.id,
            source_metadata={
                "approval_request_id": str(approval.id),
                "validation_mission_id": str(interpretation.mission_id),
                "decision_recommendation": interpretation.decision_recommendation,
                "recommendation_source": "validation_result_interpretation",
                "ai_run_id": str(interpretation.ai_run_id)
                if interpretation.ai_run_id is not None
                else None,
            },
        )
        memory_item_id = memory_item.id
    mission = _get_validation_mission(db, auth, project_id, interpretation.mission_id)
    mission.status = "interpreted"
    _recalculate_project_confidence(db, auth, project_id)
    db.add(
        ThesisEvolutionEvent(
            workspace_id=auth.workspace_id,
            project_id=project_id,
            event_type="validation_blocker",
            title="Validation results interpreted",
            change_summary=interpretation.signal_summary,
            reason=interpretation.confidence_rationale,
            source_entity_type="validation_interpretation",
            source_entity_id=interpretation.id,
            origin="agent",
            created_by=auth.user_id,
        )
    )
    governance_service.record_audit_event(
        db,
        auth,
        event_type="validation_interpretation_updates_applied",
        actor_type="user",
        project_id=project.id,
        entity_type="validation_interpretation",
        entity_id=interpretation.id,
        risk_level="medium",
        summary="Approved validation interpretation updates were applied.",
        metadata={
            "approval_request_id": str(approval.id),
            "assumption_id": str(interpretation.assumption_id)
            if interpretation.assumption_id
            else None,
            "confidence_delta": str(interpretation.proposed_confidence_delta),
            "decision_recommendation": interpretation.decision_recommendation,
            "memory_item_id": str(memory_item_id) if memory_item_id is not None else None,
        },
    )
    db.commit()
    db.refresh(approval)
    return approval


def _get_validation_interpretation(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    interpretation_id: uuid.UUID,
) -> ValidationResultInterpretation:
    interpretation = db.scalar(
        select(ValidationResultInterpretation).where(
            ValidationResultInterpretation.id == interpretation_id,
            ValidationResultInterpretation.workspace_id == auth.workspace_id,
            ValidationResultInterpretation.project_id == project_id,
        )
    )
    if interpretation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Validation interpretation not found.",
        )
    return interpretation


def _get_validation_mission(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    mission_id: uuid.UUID,
) -> ValidationMission:
    mission = db.scalar(
        select(ValidationMission).where(
            ValidationMission.id == mission_id,
            ValidationMission.workspace_id == auth.workspace_id,
            ValidationMission.project_id == project_id,
        )
    )
    if mission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Validation mission not found.",
        )
    return mission


def _mission_to_read(db: Session, mission: ValidationMission) -> ValidationMissionRead:
    result_count = _mission_result_count(db, mission)
    display_status = mission.status
    if result_count > 0 and display_status in {"planned", "running"}:
        display_status = "results_logged"
    return ValidationMissionRead.model_validate(
        {
            "id": mission.id,
            "project_id": mission.project_id,
            "assumption_id": mission.assumption_id,
            "experiment_id": mission.experiment_id,
            "mission_title": mission.mission_title,
            "why_it_matters": mission.why_it_matters,
            "target_user": mission.target_user,
            "test_type": mission.test_type,
            "steps": mission.steps or [],
            "success_criteria": mission.success_criteria,
            "failure_criteria": mission.failure_criteria,
            "assets": mission.assets or [],
            "result_count": result_count,
            "status": display_status,
            "created_at": mission.created_at,
            "updated_at": mission.updated_at,
            "latest_interpretation": _latest_validation_interpretation(db, mission),
        }
    )


def _mission_result_count(db: Session, mission: ValidationMission) -> int:
    interpretation_count = int(
        db.scalar(
            select(func.count(ValidationResultInterpretation.id)).where(
                ValidationResultInterpretation.workspace_id == mission.workspace_id,
                ValidationResultInterpretation.project_id == mission.project_id,
                ValidationResultInterpretation.mission_id == mission.id,
            )
        )
        or 0
    )
    if mission.experiment_id is None:
        return interpretation_count
    experiment_result_count = int(
        db.scalar(
            select(func.count(ExperimentResult.id)).where(
                ExperimentResult.workspace_id == mission.workspace_id,
                ExperimentResult.project_id == mission.project_id,
                ExperimentResult.experiment_id == mission.experiment_id,
            )
        )
        or 0
    )
    return experiment_result_count + interpretation_count


def _latest_validation_interpretation(
    db: Session,
    mission: ValidationMission,
) -> ValidationResultInterpretationRead | None:
    interpretation = db.scalar(
        select(ValidationResultInterpretation)
        .where(
            ValidationResultInterpretation.workspace_id == mission.workspace_id,
            ValidationResultInterpretation.project_id == mission.project_id,
            ValidationResultInterpretation.mission_id == mission.id,
        )
        .order_by(ValidationResultInterpretation.created_at.desc())
        .limit(1)
    )
    if interpretation is None:
        return None
    return ValidationResultInterpretationRead.model_validate(interpretation)


def _mission_why_it_matters(assumption: Assumption) -> str:
    risk = "the current decision blocker"
    if assumption.kill_risk or assumption.importance in {"critical", "high"}:
        risk = "the highest-risk decision blocker"
    return (
        f"This is {risk}. Without this proof, building is risky because the project "
        "still depends on an unvalidated belief."
    )


_mission_steps = plan_rendering.mission_steps
_mission_assets = plan_rendering.mission_assets
_numbered_asset_lines = plan_rendering.numbered_asset_lines
_asset_content = plan_rendering.asset_content


def _get_artifact(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
) -> Artifact:
    artifact = db.scalar(
        select(Artifact)
        .where(
            Artifact.id == artifact_id,
            Artifact.workspace_id == auth.workspace_id,
            Artifact.project_id == project_id,
        )
        .options(selectinload(Artifact.versions))
    )
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found.")
    return artifact


def _next_artifact_version(db: Session, artifact_id: uuid.UUID) -> int:
    current_max = db.scalar(
        select(func.max(ArtifactVersion.version)).where(ArtifactVersion.artifact_id == artifact_id)
    )
    return int(current_max or 0) + 1


_render_validation_plan_markdown = plan_rendering.render_validation_plan_markdown
_render_experiment_plan = plan_rendering.render_experiment_plan
_markdown_list = plan_rendering.markdown_list


_fallback_validation_interpretation = result_interpretation.fallback_validation_interpretation
_result_delta = result_interpretation.result_delta
_extract_quotes = result_interpretation.extract_quotes
_extract_objections = result_interpretation.extract_objections
_fallback_current_workaround = result_interpretation.fallback_current_workaround
_assumption_status_for_outcome = result_interpretation.assumption_status_for_outcome


def _recalculate_project_confidence(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> Decimal | None:
    project = project_service.get_project(db, auth, project_id)
    scores = [
        assumption.confidence_score
        for assumption in db.scalars(
            select(Assumption).where(
                Assumption.workspace_id == auth.workspace_id,
                Assumption.project_id == project_id,
                Assumption.confidence_score.is_not(None),
            )
        )
        if assumption.confidence_score is not None
    ]
    if not scores:
        return project.confidence_score
    project.confidence_score = Decimal(str(round(sum(scores) / Decimal(len(scores)), 4)))
    return project.confidence_score


def _validated_decision_links(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    payload: DecisionCreate,
) -> list[tuple[str, uuid.UUID]]:
    candidates: list[tuple[str, uuid.UUID]] = [
        *[("assumption", item) for item in payload.linked_assumption_ids],
        *[("risk", item) for item in payload.linked_risk_ids],
        *[("evidence", item) for item in payload.linked_evidence_source_ids],
        *[("artifact", item) for item in payload.linked_artifact_ids],
        *[("competitor", item) for item in payload.linked_competitor_ids],
        *[("experiment", item) for item in payload.linked_experiment_ids],
    ]
    seen: set[tuple[str, uuid.UUID]] = set()
    links: list[tuple[str, uuid.UUID]] = []
    for linked_type, linked_id in candidates:
        key = (linked_type, linked_id)
        if key in seen:
            continue
        _assert_link_target_exists(db, auth, project_id, linked_type, linked_id)
        seen.add(key)
        links.append(key)
    return links


def _assert_link_target_exists(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    linked_type: str,
    linked_id: uuid.UUID,
) -> None:
    model_by_type = {
        "assumption": Assumption,
        "risk": Risk,
        "evidence": EvidenceSource,
        "artifact": Artifact,
        "competitor": Competitor,
        "experiment": Experiment,
    }
    model = model_by_type[linked_type]
    exists = db.scalar(
        select(model.id).where(
            model.id == linked_id,
            model.workspace_id == auth.workspace_id,
            model.project_id == project_id,
        )
    )
    if exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Linked {linked_type} not found.",
        )


def _decimal_score(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(round(value, 4)))


def _clamp_decimal(value: Decimal) -> Decimal:
    return max(Decimal("0"), min(Decimal("1"), Decimal(str(round(value, 4)))))


def _optional_truncate(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped[:max_length] or None


def _shorten(value: str, max_length: int) -> str:
    stripped = " ".join(value.split())
    return stripped if len(stripped) <= max_length else f"{stripped[: max_length - 3]}..."


def _normalize_key(value: str) -> str:
    return " ".join(value.casefold().split())
