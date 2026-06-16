import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.ai.fallback_policy import (
    should_use_fallback_after_error,
    should_use_fallback_without_model,
)
from app.ai.litellm_client import ChatMessage, LLMCompletion
from app.ai.prompts import (
    ASSUMPTION_EXTRACTION_PROMPT_VERSION,
    UNTRUSTED_RETRIEVED_CONTENT_RULE,
    VALIDATION_PLAN_PROMPT_VERSION,
    VALIDATION_RESULT_INTERPRETATION_PROMPT_VERSION,
)
from app.ai.structured_output import StructuredOutputError, generate_structured_output
from app.core.auth import AuthContext, require_permission
from app.core.config import Settings
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
from app.schemas.artifacts import AssumptionDraft, RiskDraft
from app.schemas.validation import (
    AssumptionExtractionDraft,
    AssumptionUpdate,
    DecisionCreate,
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
    governance_service,
    langsmith_observability_service,
    project_service,
)


class ValidationWorkflowError(RuntimeError):
    pass


@dataclass(frozen=True)
class AssumptionExtractionResult:
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
    result: ExperimentResult
    experiment: Experiment
    assumption: Assumption | None
    project_confidence_score: Decimal | None


@dataclass(frozen=True)
class ValidationInterpretationResult:
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
    project_service.get_project(db, auth, project_id)
    return _load_assumptions(db, auth, project_id)


def update_assumption(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    assumption_id: uuid.UUID,
    payload: AssumptionUpdate,
) -> Assumption:
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
    project_service.get_project(db, auth, project_id)
    return _load_risks(db, auth, project_id)


def extract_assumptions_and_risks(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
) -> AssumptionExtractionResult:
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
        step = ai_run_service.start_step(
            db,
            run,
            step_name="extract_assumptions_risks",
            input_json={"project_id": str(project.id)},
        )
        started = perf_counter()
        messages = _assumption_messages(project, _project_state(project))
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
    return interpret_validation_results(db, auth, settings, project_id, mission_id, None)


def interpret_validation_results(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    mission_id: uuid.UUID,
    payload: ValidationResultInterpretationCreate | None,
) -> ValidationInterpretationResult:
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
        step = ai_run_service.start_step(
            db,
            run,
            step_name="interpret_validation_results",
            input_json={
                "project_id": str(project.id),
                "validation_mission_id": str(mission.id),
                "experiment_id": str(mission.experiment_id) if mission.experiment_id else None,
                "assumption_id": str(mission.assumption_id),
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
        step = ai_run_service.start_step(
            db,
            run,
            step_name="generate_validation_plan",
            input_json={
                "project_id": str(project.id),
                "assumption_ids": [str(item.id) for item in assumptions],
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
    payload = {"project_state": project_state}
    return [
        ChatMessage(
            role="system",
            content=(
                "Extract concrete, testable founder assumptions and risks. Prioritize "
                "kill-risk assumptions, uncertainty, and validation usefulness. Avoid vague "
                "startup advice. "
                f"{UNTRUSTED_RETRIEVED_CONTENT_RULE}"
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                f"Return structured assumptions and risks for {project.name} as JSON only.\n\n"
                f"{json.dumps(payload, indent=2, sort_keys=True)}"
            ),
        ),
    ]


def _validation_plan_messages(
    project: Project,
    assumptions: list[Assumption],
) -> list[ChatMessage]:
    payload = {
        "project_state": _project_state(project),
        "assumptions": [
            {
                "id": str(assumption.id),
                "text": assumption.text,
                "category": assumption.category,
                "importance": assumption.importance,
                "uncertainty": assumption.uncertainty,
                "kill_risk": assumption.kill_risk,
                "confidence_score": str(assumption.confidence_score)
                if assumption.confidence_score is not None
                else None,
            }
            for assumption in assumptions
        ],
    }
    return [
        ChatMessage(
            role="system",
            content=(
                "Generate validation experiments for founder assumptions. Echo each provided "
                "assumption id exactly. Plans must be operational: target respondent, steps, "
                "screener questions, interview questions, survey questions, landing page copy, "
                "outreach copy, note-taking template, interpretation rubric, success criteria, "
                "failure threshold, and expected signal strength. Make the first test specific "
                "enough to run this week. Prefer willingness-to-pay or switching-behavior tests "
                "when the business risk is unclear. State what should not be built until the "
                "test result is known. "
                f"{UNTRUSTED_RETRIEVED_CONTENT_RULE}"
            ),
        ),
        ChatMessage(
            role="user",
            content=f"Return validation plans as JSON only.\n\n{json.dumps(payload, indent=2)}",
        ),
    ]


def _validation_result_interpretation_messages(
    project: Project,
    mission: ValidationMission,
    raw_notes: str,
) -> list[ChatMessage]:
    payload = {
        "project_state": _project_state(project),
        "validation_mission": {
            "id": str(mission.id),
            "mission_title": mission.mission_title,
            "why_it_matters": mission.why_it_matters,
            "target_user": mission.target_user,
            "test_type": mission.test_type,
            "success_criteria": mission.success_criteria,
            "failure_criteria": mission.failure_criteria,
        },
        "raw_validation_notes": raw_notes,
    }
    return [
        ChatMessage(
            role="system",
            content=(
                "Interpret founder validation results skeptically. Extract only signals "
                "supported by the notes. Focus on pain severity, current workaround, urgency, "
                "willingness to pay, switching intent, objections, confidence change, and the "
                "next decision. Do not overstate weak evidence. Recommend proceed only when "
                "pain, urgency, and willingness-to-pay or switching signals are all strong. "
                "Return JSON only. "
                f"{UNTRUSTED_RETRIEVED_CONTENT_RULE}"
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                "Return a validation result interpretation as JSON only.\n\n"
                f"{json.dumps(payload, indent=2, sort_keys=True)}"
            ),
        ),
    ]


def _fallback_assumption_extraction(project: Project) -> AssumptionExtractionDraft:
    project_label = project.name or "this project"
    return AssumptionExtractionDraft(
        assumptions=[
            AssumptionDraft(
                text=(
                    "Target users experience the problem frequently enough to seek a new "
                    "tool."
                ),
                category="demand",
                importance="critical",
                uncertainty="high",
                kill_risk=True,
                confidence_score=0.35,
                recommended_test=(
                    "Interview target users and ask them to reconstruct the last three "
                    "times they handled this workflow."
                ),
            ),
            AssumptionDraft(
                text=(
                    f"Target users understand the value of {project_label} quickly enough "
                    "to try a lightweight prototype."
                ),
                category="activation",
                importance="high",
                uncertainty="high",
                kill_risk=True,
                confidence_score=0.35,
                recommended_test=(
                    "Run a concept test with a clickable prototype and ask users to explain "
                    "what they would use it for."
                ),
            ),
            AssumptionDraft(
                text=(
                    "The product can create a differentiated experience beyond generic "
                    "search, notes, or one-off AI answers."
                ),
                category="differentiation",
                importance="high",
                uncertainty="medium",
                kill_risk=True,
                confidence_score=0.3,
                recommended_test=(
                    "Compare the prototype against current alternatives and ask users which "
                    "workflow they would repeat weekly."
                ),
            ),
        ],
        risks=[
            RiskDraft(
                text=(
                    "The current evidence base may be too thin to support confident "
                    "prioritization."
                ),
                category="evidence",
                severity="high",
                likelihood="high",
                mitigation="Add direct user interviews and source-backed competitor evidence.",
            ),
            RiskDraft(
                text="Users may treat the product as nice-to-have educational content.",
                category="adoption",
                severity="high",
                likelihood="unknown",
                mitigation="Validate a repeated urgent workflow before broadening scope.",
            ),
        ],
    )


def _fallback_validation_interpretation(
    mission: ValidationMission,
    raw_notes: str,
) -> ValidationResultInterpretationDraft:
    lowered = raw_notes.casefold()
    positive_terms = (
        "pay",
        "paid",
        "pilot",
        "urgent",
        "pain",
        "painful",
        "switch",
        "trial",
        "yes",
        "interested",
    )
    negative_terms = (
        "free",
        "not pay",
        "no budget",
        "not urgent",
        "happy with",
        "declined",
        "wouldn't",
        "would not",
    )
    positive_count = sum(1 for term in positive_terms if term in lowered)
    negative_count = sum(1 for term in negative_terms if term in lowered)

    if positive_count >= negative_count + 3:
        pain = "high"
        urgency = "high"
        willingness = "strong" if "pay" in lowered or "paid" in lowered else "medium"
        switching = "strong" if "switch" in lowered or "pilot" in lowered else "medium"
        confidence_change = "increase"
        confidence_delta = 0.18
        status_value = "validated"
        decision = "continue_research" if willingness != "strong" else "proceed"
        signal_summary = "Strong validation signal with meaningful pain and action intent."
        strengthened = [
            "Target users appear to experience the problem with enough urgency to keep testing.",
            "The notes contain a concrete signal that the mission assumption may be true.",
        ]
        weakened = [
            "The result still needs more evidence before expanding beyond this wedge.",
        ]
        next_action = (
            "If willingness-to-pay was explicit, prepare a narrow pilot. Otherwise run a "
            "pricing-specific follow-up test before building."
        )
    elif negative_count > positive_count:
        pain = "low"
        urgency = "low"
        willingness = "weak"
        switching = "weak"
        confidence_change = "decrease"
        confidence_delta = -0.18
        status_value = "invalidated"
        decision = "pivot"
        signal_summary = "Weak validation signal; the notes do not support the current mission."
        strengthened = ["The test clarified where the current thesis is weak."]
        weakened = [
            "The notes suggest low urgency, weak willingness to pay, or satisfaction "
            "with existing alternatives.",
        ]
        next_action = (
            "Do not build the current version. Revisit the wedge or run a sharper test with "
            "a better-qualified respondent profile."
        )
    else:
        pain = "medium" if positive_count > 0 else "low"
        urgency = "medium" if positive_count > 0 else "low"
        willingness = "weak"
        switching = "weak"
        confidence_change = "no_change"
        confidence_delta = 0.0
        status_value = "inconclusive"
        decision = "continue_research"
        signal_summary = "Mixed or incomplete validation signal."
        strengthened = [
            "The notes contain some useful learning about the target user or current workaround.",
        ]
        weakened = [
            "The result does not yet prove willingness to pay or a strong switching trigger.",
        ]
        next_action = (
            "Run a tighter follow-up test focused on willingness to pay, switching behavior, "
            "or the clearest objection."
        )

    quotes = _extract_quotes(raw_notes)
    objections = _extract_objections(raw_notes)
    return ValidationResultInterpretationDraft(
        signal_summary=signal_summary,
        what_strengthened=strengthened,
        what_weakened=weakened,
        signal={
            "pain_severity": pain,
            "current_workaround": _fallback_current_workaround(raw_notes),
            "urgency": urgency,
            "willingness_to_pay": willingness,
            "switching_signal": switching,
            "objections": objections,
            "quotes": quotes,
            "confidence_change": confidence_change,
            "recommended_next_action": next_action,
        },
        confidence_rationale=(
            "This interpretation is based on the validation notes and mission criteria, not "
            "on general market assumptions."
        ),
        proposed_confidence_delta=confidence_delta,
        proposed_assumption_status=status_value,
        decision_recommendation=decision,
    )


def _fallback_validation_plan(
    project: Project,
    assumptions: list[Assumption],
) -> ValidationPlanSetDraft:
    project_label = project.name or "this project"
    return ValidationPlanSetDraft(
        summary=(
            f"Validate {project_label} by testing the highest-risk assumptions with direct "
            "target-user conversations and lightweight prototype tasks."
        ),
        plans=[_fallback_validation_plan_item(assumption) for assumption in assumptions],
    )


def _fallback_validation_plan_item(assumption: Assumption) -> ValidationPlanDraft:
    return ValidationPlanDraft(
        assumption_id=assumption.id,
        assumption_text=assumption.text,
        method="customer_discovery_interviews",
        target_respondent=(
            "People who match the target user profile and recently tried to solve this "
            "problem."
        ),
        screener_questions=[
            "Are you part of the target customer segment for this workflow?",
            "Have you experienced this problem in the last 30 days?",
            "Did you use a tool, spreadsheet, person, or workaround to solve it?",
        ],
        steps=[
            "Recruit five target users with recent experience of the problem.",
            "Ask each participant to describe the last time the problem occurred.",
            "Show a low-fidelity workflow or concept and ask what they would do next.",
            "Capture current alternatives, switching triggers, objections, and willingness to try.",
        ],
        interview_questions=[
            "When did this problem last happen, and what did you do?",
            "What tools, people, or workarounds did you use?",
            "What made the current solution frustrating or acceptable?",
            "What would make this workflow worth trying again next week?",
        ],
        survey_questions=[
            "How often does this problem occur?",
            "How satisfied are you with your current workaround?",
            "How likely would you be to try this workflow in the next month?",
        ],
        landing_page_copy=(
            "Turn a messy, repeated workflow into a clear next action. Join the validation "
            "pilot if this problem is already costing you time each week."
        ),
        outreach_message=(
            "I am testing a focused workflow for people who recently dealt with this problem. "
            "Could I ask you 20 minutes of questions about how you handle it today? No sales "
            "pitch; I am trying to learn whether this is painful enough to solve."
        ),
        note_taking_template=(
            "Recent example:\nCurrent workaround:\nTime or money spent:\nTrigger to switch:\n"
            "Objections:\nWillingness-to-pay signal:\nFollow-up permission:"
        ),
        result_interpretation_rubric=(
            "Proceed if users describe recent painful examples, name repeated current "
            "workarounds, and ask for access. Pivot if pain exists but the proposed workflow "
            "does not match their buying trigger. Kill or pause if the problem is rare, "
            "low-stakes, or fully satisfied by existing alternatives."
        ),
        success_criteria=(
            "At least three of five participants describe a recent painful example and ask "
            "to try or see the workflow again."
        ),
        failure_threshold=(
            "Fewer than two participants report recent pain, or most prefer their current "
            "workaround after seeing the concept."
        ),
        expected_signal_strength="medium",
    )


def _fallback_completion(
    settings: Settings,
    messages: list[ChatMessage],
    draft: AssumptionExtractionDraft | ValidationPlanSetDraft | ValidationResultInterpretationDraft,
    fallback_name: str,
    error: BaseException | None = None,
) -> LLMCompletion:
    content = draft.model_dump_json()
    prompt_tokens = sum(len(message.content.split()) for message in messages)
    completion_tokens = len(content.split())
    return LLMCompletion(
        content=content,
        model_provider="local-fallback",
        model_name=settings.litellm_model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        total_cost=Decimal("0"),
        raw_response={
            "fallback": fallback_name,
            "error": str(error)[:500] if error is not None else None,
        },
        used_stub=True,
    )


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
        structured_content=draft.model_dump(mode="json"),
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


def _validation_interpretation_proposed_updates(
    mission: ValidationMission,
    draft: ValidationResultInterpretationDraft,
) -> dict[str, Any]:
    return {
        "validation_mission_id": str(mission.id),
        "experiment_id": str(mission.experiment_id) if mission.experiment_id else None,
        "assumption_id": str(mission.assumption_id),
        "confidence_change": draft.signal.confidence_change,
        "proposed_confidence_delta": round(draft.proposed_confidence_delta, 4),
        "proposed_assumption_status": draft.proposed_assumption_status,
        "decision_recommendation": draft.decision_recommendation,
        "recommended_next_action": draft.signal.recommended_next_action,
        "signal_summary": draft.signal_summary,
        "thesis_evolution_event": {
            "event_type": "validation_blocker",
            "title": "Validation results interpreted",
            "change_summary": draft.signal_summary,
            "reason": draft.confidence_rationale,
        },
    }


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
    if interpretation.assumption_id is not None:
        assumption = get_assumption(db, auth, project_id, interpretation.assumption_id)
        current_score = assumption.confidence_score or Decimal("0.5")
        assumption.confidence_score = _clamp_decimal(
            current_score + interpretation.proposed_confidence_delta
        )
        if interpretation.proposed_assumption_status:
            assumption.status = interpretation.proposed_assumption_status
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


def _mission_steps(plan: ValidationPlanDraft) -> list[str]:
    if plan.steps:
        return plan.steps[:12]
    return [
        f"Recruit target respondents: {plan.target_respondent}.",
        "Run the interview or test script.",
        "Ask about the current workaround and urgency.",
        "Test willingness to pay or switching intent.",
        "Log the result and raw notes.",
        "Review the decision recommendation.",
    ]


def _mission_assets(plan: ValidationPlanDraft) -> list[dict[str, str]]:
    return [
        {
            "type": "interview_script",
            "title": "Interview script",
            "content": _asset_content(
                [
                    f"Target respondent: {plan.target_respondent}",
                    "Interview questions:",
                    *_numbered_asset_lines(plan.interview_questions),
                ]
            ),
        },
        {
            "type": "screener_questions",
            "title": "Screener questions",
            "content": _asset_content(_numbered_asset_lines(plan.screener_questions)),
        },
        {
            "type": "survey_questions",
            "title": "Survey questions",
            "content": _asset_content(_numbered_asset_lines(plan.survey_questions)),
        },
        {
            "type": "outreach_message",
            "title": "Outreach message",
            "content": plan.outreach_message
            or (
                f"I am testing {plan.assumption_text.lower()} and looking for quick "
                "feedback from people who have dealt with this recently. Would you be "
                "open to a short conversation?"
            ),
        },
        {
            "type": "landing_page_copy",
            "title": "Landing page copy",
            "content": plan.landing_page_copy
            or f"Validate demand for this workflow before building: {plan.assumption_text}",
        },
        {
            "type": "note_taking_template",
            "title": "Note-taking template",
            "content": plan.note_taking_template
            or "Pain observed:\nCurrent workaround:\nUrgency:\nWillingness to pay:\nObjections:",
        },
        {
            "type": "results_rubric",
            "title": "Result interpretation rubric",
            "content": plan.result_interpretation_rubric
            or (
                f"Success: {plan.success_criteria}\n\nFailure: {plan.failure_threshold}"
            ),
        },
    ]


def _numbered_asset_lines(values: list[str]) -> list[str]:
    if not values:
        return ["Not generated yet."]
    return [f"{index}. {value}" for index, value in enumerate(values, start=1)]


def _asset_content(parts: list[str]) -> str:
    return "\n".join(part for part in parts if part).strip() or "Not generated yet."


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


def _render_validation_plan_markdown(project: Project, draft: ValidationPlanSetDraft) -> str:
    sections = [f"# Validation Plan: {project.name}", f"## Summary\n{draft.summary}"]
    for index, plan in enumerate(draft.plans, start=1):
        sections.append(
            "\n\n".join(
                [
                    f"## Experiment {index}: {plan.assumption_text}",
                    f"**Method:** {plan.method}",
                    f"**Target respondent:** {plan.target_respondent}",
                    "### Screener Questions\n" + _markdown_list(plan.screener_questions),
                    "### Steps\n" + _markdown_list(plan.steps),
                    "### Interview Questions\n" + _markdown_list(plan.interview_questions),
                    "### Survey Questions\n" + _markdown_list(plan.survey_questions),
                    f"### Landing Page Copy\n{plan.landing_page_copy or 'Not generated.'}",
                    f"### Outreach Message\n{plan.outreach_message or 'Not generated.'}",
                    f"### Note-Taking Template\n{plan.note_taking_template or 'Not generated.'}",
                    "### Result Interpretation Rubric\n"
                    + (plan.result_interpretation_rubric or "Not generated."),
                    f"### Success Criteria\n{plan.success_criteria}",
                    f"### Failure Threshold\n{plan.failure_threshold}",
                    f"### Expected Signal Strength\n{plan.expected_signal_strength}",
                ]
            )
        )
    return "\n\n".join(sections)


def _render_experiment_plan(plan: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            f"Target respondent: {plan.get('target_respondent')}",
            "Screener questions:\n" + _markdown_list(plan.get("screener_questions") or []),
            "Steps:\n" + _markdown_list(plan.get("steps") or []),
            "Interview questions:\n" + _markdown_list(plan.get("interview_questions") or []),
            "Survey questions:\n" + _markdown_list(plan.get("survey_questions") or []),
            f"Landing page copy: {plan.get('landing_page_copy') or 'Not generated.'}",
            f"Outreach message: {plan.get('outreach_message') or 'Not generated.'}",
            f"Note-taking template: {plan.get('note_taking_template') or 'Not generated.'}",
            "Result interpretation rubric: "
            + str(plan.get("result_interpretation_rubric") or "Not generated."),
            f"Expected signal strength: {plan.get('expected_signal_strength')}",
        ]
    )


def _markdown_list(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values) or "- None"


def _result_delta(payload: ExperimentResultCreate) -> Decimal:
    if payload.confidence_delta is not None:
        return Decimal(str(round(payload.confidence_delta, 4)))
    defaults = {
        "positive": Decimal("0.15"),
        "negative": Decimal("-0.20"),
        "mixed": Decimal("0.05"),
        "inconclusive": Decimal("0.00"),
    }
    return defaults[payload.outcome]


def _extract_quotes(raw_notes: str) -> list[str]:
    quoted: list[str] = []
    fragments = raw_notes.replace("“", '"').replace("”", '"').split('"')
    for index, fragment in enumerate(fragments):
        if index % 2 == 1:
            stripped = fragment.strip()
            if stripped:
                quoted.append(_shorten(stripped, 240))
    if quoted:
        return quoted[:5]
    lines = [
        _shorten(line.strip("-• \t"), 240)
        for line in raw_notes.splitlines()
        if len(line.strip()) >= 20
    ]
    return lines[:3]


def _extract_objections(raw_notes: str) -> list[str]:
    objections: list[str] = []
    for line in raw_notes.splitlines():
        lowered = line.casefold()
        if any(term in lowered for term in ("objection", "concern", "worried", "but ", "however")):
            objections.append(_shorten(line.strip("-• \t"), 240))
    if objections:
        return objections[:5]
    lowered = raw_notes.casefold()
    defaults: list[str] = []
    if "free" in lowered:
        defaults.append("Existing free alternatives may cap willingness to pay.")
    if "budget" in lowered:
        defaults.append("Budget ownership or willingness to pay is unclear.")
    if "switch" in lowered and "not" in lowered:
        defaults.append("Switching from the current workaround may be difficult.")
    return defaults[:5]


def _fallback_current_workaround(raw_notes: str) -> str:
    for line in raw_notes.splitlines():
        lowered = line.casefold()
        if "workaround" in lowered or "today" in lowered or "currently" in lowered:
            return _shorten(line.strip("-• \t"), 500)
    return "The current workaround was not clearly isolated in the notes."


def _assumption_status_for_outcome(outcome: str) -> str:
    if outcome == "positive":
        return "validated"
    if outcome == "negative":
        return "invalidated"
    return "inconclusive"


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
