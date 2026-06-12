import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any, TypedDict

from fastapi import HTTPException, status
from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.fallback_policy import (
    should_use_fallback_after_error,
    should_use_fallback_without_model,
)
from app.ai.litellm_client import ChatMessage, LLMCompletion
from app.ai.prompts import (
    RESEARCH_SPRINT_PLANNING_PROMPT_VERSION,
    UNTRUSTED_RETRIEVED_CONTENT_RULE,
)
from app.ai.structured_output import StructuredOutputError, generate_structured_output
from app.core.auth import AuthContext, require_permission
from app.core.config import Settings
from app.db.models import (
    AIRun,
    AIStep,
    Artifact,
    Assumption,
    Competitor,
    EvidenceSource,
    Project,
    ResearchPlan,
    ResearchSprint,
)
from app.schemas.research import (
    ResearchPlanDraft,
    ResearchPlanUpdate,
    ResearchSprintPlanCreate,
)
from app.services import (
    ai_run_service,
    governance_service,
    langsmith_observability_service,
    project_service,
    tool_service,
)


class ResearchSprintWorkflowError(RuntimeError):
    pass


class ResearchPlanState(TypedDict, total=False):
    project_context: dict[str, Any]
    objective: str | None
    plan: ResearchPlanDraft
    result: dict[str, Any]


@dataclass(frozen=True)
class ResearchPlanRunResult:
    run: AIRun
    step: AIStep
    sprint: ResearchSprint
    model_provider: str
    model_name: str
    used_stub: bool
    total_tokens: int | None
    total_cost: Decimal | None


def list_research_sprints(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> list[ResearchSprint]:
    project_service.get_project(db, auth, project_id)
    return list(
        db.scalars(
            select(ResearchSprint)
            .where(
                ResearchSprint.workspace_id == auth.workspace_id,
                ResearchSprint.project_id == project_id,
            )
            .options(selectinload(ResearchSprint.plan))
            .order_by(ResearchSprint.created_at.desc())
        )
    )


def start_research_sprint_plan(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    payload: ResearchSprintPlanCreate,
) -> ResearchPlanRunResult:
    require_permission(auth, "run_research")
    project = project_service.get_project(db, auth, project_id)
    input_summary = payload.objective or _default_objective(project)
    run = ai_run_service.start_run(
        db,
        auth,
        workflow_type="research_sprint_planning",
        prompt_version=RESEARCH_SPRINT_PLANNING_PROMPT_VERSION,
        input_summary=input_summary[:500],
        project_id=project.id,
        model_provider="stub" if settings.should_use_llm_stub else "litellm",
        model_name=settings.litellm_model,
    )
    step_holder: dict[str, AIStep | None] = {"step": None}
    completion_holder: dict[str, LLMCompletion] = {}

    def load_project_context(_: ResearchPlanState) -> ResearchPlanState:
        return {"project_context": _project_context(db, auth, project)}

    def generate_plan(state: ResearchPlanState) -> ResearchPlanState:
        messages = _planning_messages(state["project_context"], state.get("objective"))
        step = ai_run_service.start_step(
            db,
            run,
            step_name="generate_research_plan",
            input_json={
                "schema": ResearchPlanDraft.__name__,
                "messages": [message.model_dump() for message in messages],
            },
        )
        step_holder["step"] = step
        started = perf_counter()
        try:
            if should_use_fallback_without_model(settings):
                plan = _fallback_research_plan(state["project_context"], state.get("objective"))
                completion = _fallback_completion(settings, messages, plan, "policy_always")
            else:
                result = generate_structured_output(
                    settings,
                    ResearchPlanDraft,
                    messages,
                    model=settings.litellm_model,
                    temperature=0.0,
                )
                plan = ResearchPlanDraft.model_validate(result.parsed)
                completion = result.completion
        except (StructuredOutputError, RuntimeError) as exc:
            if not should_use_fallback_after_error(settings):
                raise
            plan = _fallback_research_plan(state["project_context"], state.get("objective"))
            completion = _fallback_completion(settings, messages, plan, "emergency", exc)

        latency_ms = int((perf_counter() - started) * 1000)
        completed_step = ai_run_service.complete_step(
            db,
            step,
            output_json=plan.model_dump(mode="json"),
            latency_ms=latency_ms,
            tokens=completion.total_tokens,
            cost=completion.total_cost,
        )
        step_holder["step"] = completed_step
        completion_holder["completion"] = completion
        return {"plan": plan}

    def persist_plan(state: ResearchPlanState) -> ResearchPlanState:
        plan = state["plan"]
        research_plan = ResearchPlan(
            workspace_id=auth.workspace_id,
            project_id=project.id,
            ai_run_id=run.id,
            objective=plan.objective,
            target_customer_hypotheses=_clean_list(plan.target_customer_hypotheses),
            research_questions=_clean_list(plan.research_questions),
            competitor_queries=_clean_list(plan.competitor_queries),
            market_queries=_clean_list(plan.market_queries),
            substitute_queries=_clean_list(plan.substitute_queries),
            source_types=_clean_list(plan.source_types),
            assumptions_to_test=_clean_list(plan.assumptions_to_test),
            expected_outputs=_clean_list(plan.expected_outputs),
            status="draft",
            created_by=auth.user_id,
        )
        db.add(research_plan)
        db.flush()
        sprint = ResearchSprint(
            workspace_id=auth.workspace_id,
            project_id=project.id,
            research_plan_id=research_plan.id,
            ai_run_id=run.id,
            status="planned",
            created_by=auth.user_id,
        )
        db.add(sprint)
        db.flush()
        tool_service.create_proposal(
            db,
            auth,
            project.id,
            "propose_research_plan",
            {
                "summary": "Research plan proposed for user approval.",
                "research_plan_id": str(research_plan.id),
                "research_sprint_id": str(sprint.id),
                "objective": research_plan.objective,
                "research_questions": research_plan.research_questions,
                "competitor_queries": research_plan.competitor_queries,
                "market_queries": research_plan.market_queries,
                "expected_outputs": research_plan.expected_outputs,
            },
            research_sprint_id=sprint.id,
            requested_by="agent",
            input_json={"objective": research_plan.objective},
        )
        governance_service.record_audit_event(
            db,
            auth,
            event_type="research_sprint_started",
            actor_type="user",
            project_id=project.id,
            entity_type="research_sprint",
            entity_id=sprint.id,
            risk_level="medium",
            summary="Research sprint plan generated and queued for approval.",
            metadata={
                "research_plan_id": str(research_plan.id),
                "objective": research_plan.objective,
            },
        )
        db.commit()
        db.refresh(research_plan)
        db.refresh(sprint)
        sprint.plan = research_plan
        return {"result": {"research_plan": research_plan, "sprint": sprint}}

    graph = StateGraph(ResearchPlanState)
    graph.add_node("load_project_context", load_project_context)
    graph.add_node("generate_research_plan", generate_plan)
    graph.add_node("persist_research_plan", persist_plan)
    graph.set_entry_point("load_project_context")
    graph.add_edge("load_project_context", "generate_research_plan")
    graph.add_edge("generate_research_plan", "persist_research_plan")
    graph.add_edge("persist_research_plan", END)

    try:
        state = graph.compile().invoke({"objective": payload.objective})
    except (StructuredOutputError, RuntimeError) as exc:
        _fail_generation(db, run, step_holder["step"], exc)
        raise ResearchSprintWorkflowError("Research sprint planning failed.") from exc

    completion = completion_holder["completion"]
    run = ai_run_service.wait_for_human(
        db,
        run,
        output_summary="Research plan generated and waiting for approval.",
        total_tokens=completion.total_tokens,
        total_cost=completion.total_cost,
        model_provider=completion.model_provider,
        model_name=completion.model_name,
    )
    step = step_holder["step"]
    if step is None:
        raise ResearchSprintWorkflowError("Research sprint planning did not record a step.")
    sprint = _get_sprint(db, auth, state["result"]["sprint"].id)
    trace = langsmith_observability_service.ensure_research_sprint_trace(
        db,
        auth,
        settings,
        project,
        sprint,
        workflow_version=RESEARCH_SPRINT_PLANNING_PROMPT_VERSION,
        model_provider=completion.model_provider,
        model_name=completion.model_name,
        run=run,
    )
    langsmith_observability_service.record_step_span(
        db,
        settings,
        run=run,
        step=step,
        trace=trace,
        span_name="research_plan_generation",
        input_json=step.input_json,
        output_json=step.output_json,
        run_type="llm" if completion.model_provider != "stub" else "chain",
    )
    db.commit()
    return ResearchPlanRunResult(
        run=run,
        step=step,
        sprint=_get_sprint(db, auth, state["result"]["sprint"].id),
        model_provider=completion.model_provider,
        model_name=completion.model_name,
        used_stub=completion.used_stub,
        total_tokens=completion.total_tokens,
        total_cost=completion.total_cost,
    )


def update_research_plan(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    payload: ResearchPlanUpdate,
) -> ResearchPlan:
    require_permission(auth, "run_research")
    plan = _get_plan(db, auth, project_id, plan_id)
    if plan.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only draft research plans can be edited.",
        )
    _apply_plan_update(plan, payload)
    db.commit()
    db.refresh(plan)
    return plan


def approve_research_sprint(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    payload: ResearchPlanUpdate,
) -> ResearchSprint:
    require_permission(auth, "approve_memory_updates")
    sprint = _get_sprint(db, auth, sprint_id, project_id)
    if sprint.status not in {"planned", "needs_review"} or sprint.plan.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only planned research sprints with draft plans can be approved.",
        )
    _apply_plan_update(sprint.plan, payload)
    tool_service.approve_pending_proposals_for_sprint(
        db,
        auth,
        project_id,
        sprint.id,
        {"propose_research_plan"},
    )
    sprint.plan.status = "approved"
    sprint.plan.approved_at = datetime.now(UTC)
    sprint.status = "approved"
    sprint.started_at = datetime.now(UTC)
    if sprint.ai_run_id is not None:
        run = db.get(AIRun, sprint.ai_run_id)
        if run is not None:
            step = ai_run_service.start_step(
                db,
                run,
                step_name="approve_research_plan",
                input_json={"research_plan_id": str(sprint.plan.id)},
            )
            ai_run_service.complete_step(
                db,
                step,
                output_json={"status": "approved"},
                latency_ms=0,
                tokens=None,
                cost=None,
            )
            ai_run_service.complete_run(
                db,
                run,
                output_summary=(
                    "Research plan approved. Autonomous research execution is V1 Sprint 2+."
                ),
                total_tokens=run.total_tokens,
                total_cost=run.total_cost,
                model_provider=run.model_provider or "internal",
                model_name=run.model_name or "research-sprint-planner",
            )
    governance_service.resolve_pending_approvals_for_entity(
        db,
        auth,
        project_id=project_id,
        entity_type="research_sprint",
        entity_id=sprint.id,
        status_value="approved",
        request_types={"research_plan"},
    )
    governance_service.record_audit_event(
        db,
        auth,
        event_type="research_plan_approved",
        actor_type="user",
        project_id=project_id,
        entity_type="research_sprint",
        entity_id=sprint.id,
        risk_level="medium",
        summary="Approved research sprint plan.",
        metadata={"research_plan_id": str(sprint.plan.id)},
    )
    db.commit()
    return _get_sprint(db, auth, sprint.id, project_id)


def reject_research_sprint(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> ResearchSprint:
    require_permission(auth, "approve_memory_updates")
    sprint = _get_sprint(db, auth, sprint_id, project_id)
    if sprint.status not in {"planned", "needs_review"} or sprint.plan.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only planned research sprints with draft plans can be rejected.",
        )
    tool_service.reject_pending_proposals_for_sprint(
        db,
        auth,
        project_id,
        sprint.id,
        {"propose_research_plan"},
    )
    sprint.plan.status = "rejected"
    sprint.plan.rejected_at = datetime.now(UTC)
    sprint.status = "rejected"
    sprint.completed_at = datetime.now(UTC)
    if sprint.ai_run_id is not None:
        run = db.get(AIRun, sprint.ai_run_id)
        if run is not None:
            step = ai_run_service.start_step(
                db,
                run,
                step_name="reject_research_plan",
                input_json={"research_plan_id": str(sprint.plan.id)},
            )
            ai_run_service.complete_step(
                db,
                step,
                output_json={"status": "rejected"},
                latency_ms=0,
                tokens=None,
                cost=None,
            )
            ai_run_service.cancel_run(db, run, output_summary="Research plan rejected by user.")
    governance_service.resolve_pending_approvals_for_entity(
        db,
        auth,
        project_id=project_id,
        entity_type="research_sprint",
        entity_id=sprint.id,
        status_value="rejected",
        request_types={"research_plan"},
    )
    governance_service.record_audit_event(
        db,
        auth,
        event_type="research_plan_rejected",
        actor_type="user",
        project_id=project_id,
        entity_type="research_sprint",
        entity_id=sprint.id,
        risk_level="medium",
        summary="Rejected research sprint plan.",
        metadata={"research_plan_id": str(sprint.plan.id)},
    )
    db.commit()
    return _get_sprint(db, auth, sprint.id, project_id)


def _get_plan(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
) -> ResearchPlan:
    plan = db.scalar(
        select(ResearchPlan).where(
            ResearchPlan.id == plan_id,
            ResearchPlan.workspace_id == auth.workspace_id,
            ResearchPlan.project_id == project_id,
        )
    )
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research plan not found.",
        )
    return plan


def _get_sprint(
    db: Session,
    auth: AuthContext,
    sprint_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
) -> ResearchSprint:
    filters = [
        ResearchSprint.id == sprint_id,
        ResearchSprint.workspace_id == auth.workspace_id,
    ]
    if project_id is not None:
        filters.append(ResearchSprint.project_id == project_id)
    sprint = db.scalar(
        select(ResearchSprint).where(*filters).options(selectinload(ResearchSprint.plan))
    )
    if sprint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research sprint not found.",
        )
    return sprint


def _apply_plan_update(plan: ResearchPlan, payload: ResearchPlanUpdate) -> None:
    update_data = payload.model_dump(exclude_unset=True)
    if "objective" in update_data and update_data["objective"] is not None:
        plan.objective = update_data["objective"].strip()
    for field in (
        "target_customer_hypotheses",
        "research_questions",
        "competitor_queries",
        "market_queries",
        "substitute_queries",
        "source_types",
        "assumptions_to_test",
        "expected_outputs",
    ):
        if field in update_data and update_data[field] is not None:
            setattr(plan, field, _clean_list(update_data[field]))


def _project_context(db: Session, auth: AuthContext, project: Project) -> dict[str, Any]:
    current_thesis = project_service.current_thesis(project)
    evidence_count = int(
        db.scalar(
            select(EvidenceSource)
            .where(
                EvidenceSource.workspace_id == auth.workspace_id,
                EvidenceSource.project_id == project.id,
            )
            .limit(1)
        )
        is not None
    )
    competitor_names = [
        competitor.name
        for competitor in db.scalars(
            select(Competitor)
            .where(
                Competitor.workspace_id == auth.workspace_id,
                Competitor.project_id == project.id,
            )
            .limit(8)
        )
    ]
    assumption_texts = [
        assumption.text
        for assumption in db.scalars(
            select(Assumption)
            .where(
                Assumption.workspace_id == auth.workspace_id,
                Assumption.project_id == project.id,
            )
            .limit(8)
        )
    ]
    artifact_types = [
        artifact.artifact_type
        for artifact in db.scalars(
            select(Artifact)
            .where(Artifact.workspace_id == auth.workspace_id, Artifact.project_id == project.id)
            .limit(8)
        )
    ]
    return {
        "project_id": str(project.id),
        "name": project.name,
        "short_description": project.short_description,
        "current_thesis": current_thesis.thesis_text if current_thesis else None,
        "target_users": [segment.name for segment in project.customer_segments],
        "problem_hypotheses": [problem.description for problem in project.problems],
        "existing_competitors": competitor_names,
        "existing_assumptions": assumption_texts,
        "existing_artifact_types": artifact_types,
        "has_evidence": evidence_count > 0,
    }


def _planning_messages(
    project_context: dict[str, Any],
    objective: str | None,
) -> list[ChatMessage]:
    payload = {"project_context": project_context, "objective": objective}
    return [
        ChatMessage(
            role="system",
            content=(
                "You plan bounded strategic research sprints for solo founders. Produce a "
                "specific, approval-ready research plan. Do not browse, claim sources were "
                "found, or perform research. The plan should identify what to investigate, "
                "which sources to inspect later, which competitors/substitutes to look for, "
                "and which assumptions the research should test. "
                f"{UNTRUSTED_RETRIEVED_CONTENT_RULE}"
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                "Create a research sprint plan for this project. Return only the requested "
                "JSON fields.\n\n"
                f"{json.dumps(payload, indent=2, sort_keys=True)}"
            ),
        ),
    ]


def _fallback_research_plan(
    project_context: dict[str, Any],
    objective: str | None,
) -> ResearchPlanDraft:
    project_name = str(project_context.get("name") or "the opportunity").strip()
    target_users = [
        str(user).strip()
        for user in project_context.get("target_users", [])
        if str(user).strip()
    ]
    primary_user = target_users[0] if target_users else "the first target customer segment"
    plan_objective = objective or (
        f"Investigate whether {project_name} has a specific, evidence-backed wedge for "
        f"{primary_user}."
    )
    return ResearchPlanDraft(
        objective=plan_objective,
        target_customer_hypotheses=[
            primary_user,
            "Adjacent users currently solving this through manual work or generic AI tools.",
        ],
        research_questions=[
            f"What urgent, repeated pain does {primary_user} have?",
            "Which current alternatives are users already paying for or tolerating?",
            "Which competitor or substitute creates the biggest positioning risk?",
            "What evidence would make this opportunity worth validating next?",
        ],
        competitor_queries=[
            f"{project_name} competitors",
            f"{primary_user} software alternatives",
            f"{primary_user} AI workflow tools",
        ],
        market_queries=[
            f"{primary_user} pain points",
            f"{primary_user} market trends",
            f"{project_name} market landscape",
        ],
        substitute_queries=[
            f"how {primary_user} solves this manually",
            f"{primary_user} spreadsheet workflow",
            f"{primary_user} using ChatGPT for this workflow",
        ],
        source_types=[
            "company websites",
            "pricing pages",
            "product pages",
            "reviews",
            "forums",
            "blog posts",
            "directories",
        ],
        assumptions_to_test=[
            f"{primary_user} has frequent enough pain to switch tools.",
            "The market has a narrow wedge that direct competitors do not already own.",
            "Public evidence can identify credible validation targets.",
        ],
        expected_outputs=[
            "cited research memo",
            "competitor candidate list",
            "ranked assumptions and risks",
            "recommended validation actions",
        ],
    )


def _fallback_completion(
    settings: Settings,
    messages: list[ChatMessage],
    plan: ResearchPlanDraft,
    fallback_name: str,
    error: BaseException | None = None,
) -> LLMCompletion:
    content = plan.model_dump_json()
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
            "fallback": f"research_sprint_planning_{fallback_name}",
            "error": str(error)[:500] if error is not None else None,
        },
        used_stub=True,
    )


def _default_objective(project: Project) -> str:
    current_thesis = project_service.current_thesis(project)
    thesis = current_thesis.thesis_text if current_thesis else project.short_description
    if thesis:
        return f"Investigate whether this thesis is worth validating next: {thesis}"
    return f"Investigate the market, competitors, and validation risks for {project.name}."


def _fail_generation(db: Session, run: AIRun, step: AIStep | None, exc: BaseException) -> None:
    if step is not None:
        ai_run_service.fail_step(db, step, error=str(exc))
    ai_run_service.fail_run(db, run, error=str(exc))


def _clean_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        text = " ".join(str(value).split())
        key = text.casefold()
        if text and key not in seen:
            cleaned.append(text)
            seen.add(key)
    return cleaned
