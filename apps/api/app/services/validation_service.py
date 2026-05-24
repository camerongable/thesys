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
from app.ai.prompts import ASSUMPTION_EXTRACTION_PROMPT_VERSION, VALIDATION_PLAN_PROMPT_VERSION
from app.ai.structured_output import StructuredOutputError, generate_structured_output
from app.core.auth import AuthContext
from app.core.config import Settings
from app.db.models import (
    AIRun,
    AIStep,
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
)
from app.schemas.artifacts import AssumptionDraft, RiskDraft
from app.schemas.validation import (
    AssumptionExtractionDraft,
    AssumptionUpdate,
    DecisionCreate,
    ExperimentResultCreate,
    ValidationPlanDraft,
    ValidationPlanGenerateCreate,
    ValidationPlanSetDraft,
)
from app.services import ai_run_service, project_service


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
    except (StructuredOutputError, RuntimeError, HTTPException) as exc:
        if step is not None:
            ai_run_service.fail_step(db, step, error=str(exc))
        ai_run_service.fail_run(db, run, error=str(exc))
        raise
    except Exception as exc:
        if step is not None:
            ai_run_service.fail_step(db, step, error=str(exc))
        ai_run_service.fail_run(db, run, error=str(exc))
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


def generate_validation_plan(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    payload: ValidationPlanGenerateCreate,
) -> ValidationPlanResult:
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
        artifact = _write_validation_plan_artifact(db, auth, run, project, draft)
        experiments = _write_experiments(db, auth, project, assumptions, draft)
        db.flush()
        completed_step = ai_run_service.complete_step(
            db,
            step,
            output_json={
                "artifact_id": str(artifact.id),
                "experiment_ids": [str(item.id) for item in experiments],
            },
            latency_ms=int((perf_counter() - started) * 1000),
            tokens=completion.total_tokens,
            cost=completion.total_cost,
        )
    except (StructuredOutputError, RuntimeError, HTTPException) as exc:
        if step is not None:
            ai_run_service.fail_step(db, step, error=str(exc))
        ai_run_service.fail_run(db, run, error=str(exc))
        raise
    except Exception as exc:
        if step is not None:
            ai_run_service.fail_step(db, step, error=str(exc))
        ai_run_service.fail_run(db, run, error=str(exc))
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
    artifact = _get_artifact(db, auth, project.id, artifact.id)
    experiments = [
        get_experiment(db, auth, project.id, experiment.id) for experiment in experiments
    ]
    return ValidationPlanResult(
        run=run,
        step=completed_step,
        artifact=artifact,
        experiments=experiments,
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
    project_confidence = _recalculate_project_confidence(db, auth, project_id)
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
                "startup advice."
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
                "questions, success criteria, failure threshold, and expected signal strength."
            ),
        ),
        ChatMessage(
            role="user",
            content=f"Return validation plans as JSON only.\n\n{json.dumps(payload, indent=2)}",
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
    draft: AssumptionExtractionDraft | ValidationPlanSetDraft,
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
                    "### Steps\n" + _markdown_list(plan.steps),
                    "### Interview Questions\n" + _markdown_list(plan.interview_questions),
                    "### Survey Questions\n" + _markdown_list(plan.survey_questions),
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
            "Steps:\n" + _markdown_list(plan.get("steps") or []),
            "Interview questions:\n" + _markdown_list(plan.get("interview_questions") or []),
            "Survey questions:\n" + _markdown_list(plan.get("survey_questions") or []),
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
