import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter
from typing import Any, TypedDict

from fastapi import HTTPException, status
from langgraph.graph import END, StateGraph
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.fallback_policy import (
    should_use_fallback_after_error,
    should_use_fallback_without_model,
)
from app.ai.litellm_client import ChatMessage, LLMCompletion
from app.ai.prompts import (
    STRUCTURED_INTAKE_FINALIZE_PROMPT_VERSION,
    STRUCTURED_INTAKE_PROMPT_VERSION,
)
from app.ai.structured_output import StructuredOutputError, generate_structured_output
from app.core.auth import AuthContext
from app.core.config import Settings
from app.db.models import (
    AIRun,
    AIStep,
    CustomerSegment,
    Problem,
    Project,
    ProjectIntake,
    ProjectThesis,
)
from app.schemas.intake import (
    StructuredIntakeAnalyzeCreate,
    StructuredIntakeAnswerCreate,
    StructuredIntakeFinalizeCreate,
    StructuredProjectIntake,
)
from app.services import ai_run_service, project_service


class IntakeWorkflowError(RuntimeError):
    pass


class IntakeGenerationState(TypedDict, total=False):
    raw_idea: str
    user_background: str | None
    target_market_guess: str | None
    constraints: str | None
    project_context: dict[str, Any]
    initial_intake: dict[str, Any] | None
    answers: list[dict[str, str]]
    intake: StructuredProjectIntake


class IntakeFinalizeState(TypedDict, total=False):
    intake: StructuredProjectIntake
    raw_idea: str | None
    answers: list[dict[str, str]]
    result: dict[str, Any]


@dataclass(frozen=True)
class IntakeRunResult:
    run: AIRun
    step: AIStep
    intake: StructuredProjectIntake
    model_provider: str
    model_name: str
    used_stub: bool
    total_tokens: int | None
    total_cost: Decimal | None


@dataclass(frozen=True)
class FinalizedIntakeResult:
    run: AIRun
    step: AIStep
    project: Project
    intake_record: ProjectIntake
    customer_segments: list[CustomerSegment]
    problems: list[Problem]


def analyze_intake(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    payload: StructuredIntakeAnalyzeCreate,
) -> IntakeRunResult:
    project = project_service.get_project(db, auth, project_id)
    return _run_generation_graph(
        db,
        auth,
        settings,
        project,
        raw_idea=payload.raw_idea,
        input_summary=payload.raw_idea,
        user_background=payload.user_background,
        target_market_guess=payload.target_market_guess,
        constraints=payload.constraints,
        initial_intake=None,
        answers=[],
        step_name="analyze_idea",
    )


def answer_intake(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    payload: StructuredIntakeAnswerCreate,
) -> IntakeRunResult:
    project = project_service.get_project(db, auth, project_id)
    answers = [answer.model_dump() for answer in payload.answers]
    return _run_generation_graph(
        db,
        auth,
        settings,
        project,
        raw_idea=payload.raw_idea,
        input_summary=f"{payload.raw_idea}\nAnswers: {_compact_json(answers)}",
        user_background=None,
        target_market_guess=None,
        constraints=None,
        initial_intake=(
            payload.initial_intake.model_dump(mode="json") if payload.initial_intake else None
        ),
        answers=answers,
        step_name="apply_user_answers",
    )


def finalize_intake(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    payload: StructuredIntakeFinalizeCreate,
) -> FinalizedIntakeResult:
    project = project_service.get_project(db, auth, project_id)
    run = ai_run_service.start_run(
        db,
        auth,
        workflow_type="structured_intake_finalize",
        prompt_version=STRUCTURED_INTAKE_FINALIZE_PROMPT_VERSION,
        input_summary=payload.structured_intake.one_sentence_summary[:500],
        project_id=project.id,
        model_provider="internal",
        model_name="structured-intake-finalizer",
    )
    step = ai_run_service.start_step(
        db,
        run,
        step_name="write_project_fields",
        input_json={
            "structured_intake": payload.structured_intake.model_dump(mode="json"),
            "answers": [answer.model_dump() for answer in payload.answers],
        },
    )

    started = perf_counter()
    try:
        graph = StateGraph(IntakeFinalizeState)
        graph.add_node(
            "write_project_fields",
            lambda state: _write_project_fields(db, auth, project, run, state),
        )
        graph.set_entry_point("write_project_fields")
        graph.add_edge("write_project_fields", END)
        state = graph.compile().invoke(
            {
                "intake": payload.structured_intake,
                "raw_idea": payload.raw_idea,
                "answers": [answer.model_dump() for answer in payload.answers],
            }
        )
    except Exception as exc:
        db.rollback()
        latency_ms = int((perf_counter() - started) * 1000)
        ai_run_service.fail_step(db, step, error=str(exc), latency_ms=latency_ms)
        ai_run_service.fail_run(db, run, error=str(exc))
        raise IntakeWorkflowError("Structured intake finalization failed.") from exc

    latency_ms = int((perf_counter() - started) * 1000)
    result = state["result"]
    step = ai_run_service.complete_step(
        db,
        step,
        output_json={
            "project_id": str(project.id),
            "intake_record_id": str(result["intake_record"].id),
            "customer_segment_ids": [str(segment.id) for segment in result["customer_segments"]],
            "problem_ids": [str(problem.id) for problem in result["problems"]],
        },
        latency_ms=latency_ms,
        tokens=None,
        cost=None,
    )
    run = ai_run_service.complete_run(
        db,
        run,
        output_summary=payload.structured_intake.one_sentence_summary,
        total_tokens=None,
        total_cost=None,
        model_provider="internal",
        model_name="structured-intake-finalizer",
    )

    return FinalizedIntakeResult(
        run=run,
        step=step,
        project=project_service.get_project(db, auth, project.id),
        intake_record=result["intake_record"],
        customer_segments=result["customer_segments"],
        problems=result["problems"],
    )


def _run_generation_graph(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project: Project,
    *,
    raw_idea: str,
    input_summary: str,
    user_background: str | None,
    target_market_guess: str | None,
    constraints: str | None,
    initial_intake: dict[str, Any] | None,
    answers: list[dict[str, str]],
    step_name: str,
) -> IntakeRunResult:
    run = ai_run_service.start_run(
        db,
        auth,
        workflow_type="structured_intake",
        prompt_version=STRUCTURED_INTAKE_PROMPT_VERSION,
        input_summary=input_summary[:500],
        project_id=project.id,
        model_provider="stub" if settings.should_use_llm_stub else "litellm",
        model_name=settings.litellm_model,
    )
    step_holder: dict[str, AIStep | None] = {"step": None}
    completion_holder: dict[str, Any] = {}

    def load_project_context(_: IntakeGenerationState) -> IntakeGenerationState:
        current = project_service.current_thesis(project)
        return {
            "project_context": {
                "project_id": str(project.id),
                "name": project.name,
                "short_description": project.short_description,
                "current_thesis": current.thesis_text if current else None,
            }
        }

    def generate_intake(state: IntakeGenerationState) -> IntakeGenerationState:
        messages = _generation_messages(
            project_context=state["project_context"],
            raw_idea=state["raw_idea"],
            user_background=state.get("user_background"),
            target_market_guess=state.get("target_market_guess"),
            constraints=state.get("constraints"),
            initial_intake=state.get("initial_intake"),
            answers=state.get("answers", []),
        )
        step = ai_run_service.start_step(
            db,
            run,
            step_name=step_name,
            input_json={
                "schema": StructuredProjectIntake.__name__,
                "messages": [message.model_dump() for message in messages],
            },
        )
        step_holder["step"] = step

        started = perf_counter()
        try:
            if should_use_fallback_without_model(settings):
                intake = _fallback_intake(state)
                completion = _fallback_completion(
                    settings,
                    messages,
                    intake,
                    "structured_intake_policy_always",
                )
            else:
                result = generate_structured_output(
                    settings,
                    StructuredProjectIntake,
                    messages,
                    model=settings.litellm_model,
                    temperature=0.0,
                )
                intake = StructuredProjectIntake.model_validate(result.parsed)
                completion = result.completion
        except (StructuredOutputError, RuntimeError) as exc:
            if not should_use_fallback_after_error(settings):
                raise
            intake = _fallback_intake(state)
            completion = _fallback_completion(
                settings,
                messages,
                intake,
                "structured_intake_emergency",
                exc,
            )
        latency_ms = int((perf_counter() - started) * 1000)
        completed_step = ai_run_service.complete_step(
            db,
            step,
            output_json=intake.model_dump(mode="json"),
            latency_ms=latency_ms,
            tokens=completion.total_tokens,
            cost=completion.total_cost,
        )
        step_holder["step"] = completed_step
        completion_holder["completion"] = completion
        return {"intake": intake}

    graph = StateGraph(IntakeGenerationState)
    graph.add_node("load_project_context", load_project_context)
    graph.add_node("generate_structured_intake", generate_intake)
    graph.set_entry_point("load_project_context")
    graph.add_edge("load_project_context", "generate_structured_intake")
    graph.add_edge("generate_structured_intake", END)

    try:
        state = graph.compile().invoke(
            {
                "raw_idea": raw_idea,
                "user_background": user_background,
                "target_market_guess": target_market_guess,
                "constraints": constraints,
                "initial_intake": initial_intake,
                "answers": answers,
            }
        )
    except (StructuredOutputError, RuntimeError) as exc:
        _fail_generation(db, run, step_holder["step"], exc)
        raise IntakeWorkflowError("Structured intake generation failed.") from exc

    completion = completion_holder["completion"]
    run = ai_run_service.complete_run(
        db,
        run,
        output_summary=state["intake"].one_sentence_summary,
        total_tokens=completion.total_tokens,
        total_cost=completion.total_cost,
        model_provider=completion.model_provider,
        model_name=completion.model_name,
    )

    if step_holder["step"] is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Structured intake workflow did not record a step.",
        )

    return IntakeRunResult(
        run=run,
        step=step_holder["step"],
        intake=state["intake"],
        model_provider=completion.model_provider,
        model_name=completion.model_name,
        used_stub=completion.used_stub,
        total_tokens=completion.total_tokens,
        total_cost=completion.total_cost,
    )


def _write_project_fields(
    db: Session,
    auth: AuthContext,
    project: Project,
    run: AIRun,
    state: IntakeFinalizeState,
) -> IntakeFinalizeState:
    intake = state["intake"]
    answers = state.get("answers", [])
    project.name = _truncate(intake.project_name.strip(), 255) or project.name
    project.short_description = intake.one_sentence_summary.strip()

    thesis = ProjectThesis(
        workspace_id=auth.workspace_id,
        project_id=project.id,
        version=_next_thesis_version(db, project.id),
        thesis_text=_thesis_text(intake),
        rationale=_thesis_rationale(intake),
        created_by=auth.user_id,
    )
    db.add(thesis)
    db.flush()
    project.current_thesis_id = thesis.id

    intake_record = ProjectIntake(
        workspace_id=auth.workspace_id,
        project_id=project.id,
        ai_run_id=run.id,
        project_name=project.name,
        one_sentence_summary=intake.one_sentence_summary.strip(),
        target_users=_clean_list(intake.target_users),
        buyer_type=intake.buyer_type,
        problem_hypotheses=_clean_list(intake.problem_hypotheses),
        proposed_solution=intake.proposed_solution.strip(),
        market_category=_optional_strip(intake.market_category),
        business_model_guess=_optional_strip(intake.business_model_guess),
        suspected_competitors=_clean_list(intake.suspected_competitors),
        key_uncertainties=_clean_list(intake.key_uncertainties),
        clarifying_questions=_clean_list(intake.clarifying_questions),
        user_answers=answers,
        raw_idea=state.get("raw_idea"),
        created_by=auth.user_id,
    )
    db.add(intake_record)
    db.flush()

    customer_segments = _ensure_customer_segments(db, auth, project, intake)
    problems = _ensure_problems(db, auth, project, intake, customer_segments)

    db.commit()
    db.refresh(intake_record)
    for segment in customer_segments:
        db.refresh(segment)
    for problem in problems:
        db.refresh(problem)

    return {
        "result": {
            "intake_record": intake_record,
            "customer_segments": customer_segments,
            "problems": problems,
        }
    }


def _generation_messages(
    *,
    project_context: dict[str, Any],
    raw_idea: str,
    user_background: str | None,
    target_market_guess: str | None,
    constraints: str | None,
    initial_intake: dict[str, Any] | None,
    answers: list[dict[str, str]],
) -> list[ChatMessage]:
    payload = {
        "project_context": project_context,
        "raw_idea": raw_idea,
        "user_background": user_background,
        "target_market_guess": target_market_guess,
        "constraints": constraints,
        "initial_intake": initial_intake,
        "clarifying_answers": answers,
    }
    return [
        ChatMessage(
            role="system",
            content=(
                "You convert rough founder ideas into structured strategic project state. "
                "Be direct, specific, skeptical, and non-hype. Ask 3 to 7 clarifying "
                "questions when important fields are ambiguous. Use 'unknown' for buyer_type "
                "when the buyer is unclear. Do not invent evidence or factual market claims."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                "Create or refine the structured intake for this project. Return only the "
                "requested JSON fields.\n\n"
                f"{json.dumps(payload, indent=2, sort_keys=True)}"
            ),
        ),
    ]


def _fallback_intake(state: IntakeGenerationState) -> StructuredProjectIntake:
    if state.get("initial_intake"):
        return _fallback_answer_intake(state)

    raw_idea = state.get("raw_idea") or "the project idea"
    project_context = state.get("project_context") or {}
    project_name = _fallback_project_name(project_context, raw_idea)
    target_market = state.get("target_market_guess")
    target_users = [target_market] if target_market else ["Initial target users"]
    return StructuredProjectIntake(
        project_name=project_name,
        one_sentence_summary=(
            f"{project_name} needs validation around whether the target user has an urgent, "
            "repeated problem."
        ),
        target_users=target_users,
        buyer_type="unknown",
        problem_hypotheses=[
            "The target user currently relies on fragmented or manual workarounds.",
            "The pain may not yet be frequent or expensive enough to motivate switching.",
        ],
        proposed_solution=(
            "A focused workflow that helps the target user make progress faster while "
            "keeping assumptions and evidence visible."
        ),
        market_category=None,
        business_model_guess=None,
        suspected_competitors=["Manual workflow", "Generic AI tools"],
        key_uncertainties=[
            "Which target user segment has the strongest repeated pain?",
            "What current workaround is painful enough to replace?",
            "What evidence would make this opportunity worth pursuing?",
        ],
        clarifying_questions=[
            "Who is the first target user segment?",
            "What recent workflow pain should be validated first?",
            "What current alternative does the user rely on today?",
        ],
    )


def _fallback_answer_intake(state: IntakeGenerationState) -> StructuredProjectIntake:
    initial = state.get("initial_intake") or {}
    intake = StructuredProjectIntake.model_validate(initial)
    answers = state.get("answers", [])
    answer_text = " ".join(
        str(answer.get("answer", "")).strip()
        for answer in answers
        if isinstance(answer, dict)
    )
    target_users = list(intake.target_users)
    if answer_text and not target_users:
        target_users.append(_truncate(answer_text, 255))
    key_uncertainties = list(intake.key_uncertainties)
    for answer in answers:
        question = str(answer.get("question", "")).strip() if isinstance(answer, dict) else ""
        if question and len(key_uncertainties) < 7:
            key_uncertainties.append(f"Validate answer to: {question}")

    return intake.model_copy(
        update={
            "target_users": _clean_list(target_users),
            "key_uncertainties": _clean_list(key_uncertainties),
            "clarifying_questions": [],
        }
    )


def _fallback_completion(
    settings: Settings,
    messages: list[ChatMessage],
    intake: StructuredProjectIntake,
    fallback_name: str,
    error: BaseException | None = None,
) -> LLMCompletion:
    content = intake.model_dump_json()
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


def _fallback_project_name(project_context: dict[str, Any], raw_idea: str) -> str:
    existing_name = str(project_context.get("name") or "").strip()
    if existing_name:
        return _truncate(existing_name, 255)
    words = [word.strip(".,:;!?()[]{}") for word in raw_idea.split()[:5]]
    name = " ".join(word.capitalize() for word in words if word)
    return _truncate(name or "Untitled Opportunity", 255)


def _fail_generation(db: Session, run: AIRun, step: AIStep | None, exc: BaseException) -> None:
    if step is not None:
        ai_run_service.fail_step(db, step, error=str(exc))
    ai_run_service.fail_run(db, run, error=str(exc))


def _ensure_customer_segments(
    db: Session,
    auth: AuthContext,
    project: Project,
    intake: StructuredProjectIntake,
) -> list[CustomerSegment]:
    existing_segments = list(
        db.scalars(
            select(CustomerSegment).where(
                CustomerSegment.workspace_id == auth.workspace_id,
                CustomerSegment.project_id == project.id,
            )
        )
    )
    existing_by_name = {_normalize_key(segment.name): segment for segment in existing_segments}
    segments: list[CustomerSegment] = []
    target_users = _clean_list(intake.target_users) or ["Unknown target user"]

    for index, target_user in enumerate(target_users):
        key = _normalize_key(target_user)
        segment = existing_by_name.get(key)
        if segment is None:
            segment = CustomerSegment(
                workspace_id=auth.workspace_id,
                project_id=project.id,
                name=_truncate(target_user, 255),
                description=f"Structured intake target segment for {project.name}.",
                buyer_type=intake.buyer_type,
                priority="primary" if index == 0 else "secondary",
            )
            db.add(segment)
            db.flush()
            existing_by_name[key] = segment
        else:
            segment.buyer_type = intake.buyer_type
            segment.priority = segment.priority or ("primary" if index == 0 else "secondary")
        segments.append(segment)

    return segments


def _ensure_problems(
    db: Session,
    auth: AuthContext,
    project: Project,
    intake: StructuredProjectIntake,
    segments: list[CustomerSegment],
) -> list[Problem]:
    existing_problems = list(
        db.scalars(
            select(Problem).where(
                Problem.workspace_id == auth.workspace_id,
                Problem.project_id == project.id,
            )
        )
    )
    existing_by_description = {
        _normalize_key(problem.description): problem for problem in existing_problems
    }
    problems: list[Problem] = []
    primary_segment_id = segments[0].id if segments else None
    problem_hypotheses = _clean_list(intake.problem_hypotheses) or [
        "The target user has an unresolved workflow pain worth validating."
    ]

    for problem_text in problem_hypotheses:
        key = _normalize_key(problem_text)
        problem = existing_by_description.get(key)
        if problem is None:
            problem = Problem(
                workspace_id=auth.workspace_id,
                project_id=project.id,
                segment_id=primary_segment_id,
                description=problem_text,
                severity="unknown",
            )
            db.add(problem)
            db.flush()
            existing_by_description[key] = problem
        elif problem.segment_id is None:
            problem.segment_id = primary_segment_id
        problems.append(problem)

    return problems


def _next_thesis_version(db: Session, project_id: uuid.UUID) -> int:
    current_max = db.scalar(
        select(func.max(ProjectThesis.version)).where(ProjectThesis.project_id == project_id)
    )
    return int(current_max or 0) + 1


def _thesis_text(intake: StructuredProjectIntake) -> str:
    return intake.one_sentence_summary.strip()


def _thesis_rationale(intake: StructuredProjectIntake) -> str:
    parts = [
        f"Target users: {', '.join(_clean_list(intake.target_users)) or 'unknown'}.",
        f"Proposed solution: {intake.proposed_solution.strip()}",
    ]
    uncertainties = _clean_list(intake.key_uncertainties)
    if uncertainties:
        parts.append(f"Key uncertainties: {', '.join(uncertainties)}.")
    return " ".join(parts)


def _clean_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        text = " ".join(value.split())
        key = _normalize_key(text)
        if text and key not in seen:
            cleaned.append(text)
            seen.add(key)
    return cleaned


def _optional_strip(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _truncate(value: str, max_length: int) -> str:
    return value[:max_length]


def _normalize_key(value: str) -> str:
    return " ".join(value.casefold().split())


def _compact_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)
