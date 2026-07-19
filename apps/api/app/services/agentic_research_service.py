"""LangGraph-powered agentic research workflow.

This service owns the bounded agent loop for research sprints: gather project
context, select retrieval/tool strategies, synthesize a cited memo, critique the
citations, then stop for human approval before strategic memory is updated.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any, Literal, TypedDict

from fastapi import HTTPException, status
from langgraph.graph import END, StateGraph
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.ai.fallback_completion import fallback_completion
from app.ai.fallback_policy import (
    should_use_fallback_after_error,
    should_use_fallback_without_model,
)
from app.ai.litellm_client import ChatMessage, LLMCompletion
from app.ai.prompts import AGENTIC_RESEARCH_PROMPT_VERSION
from app.ai.structured_output import StructuredOutputError, generate_structured_output
from app.core.auth import AuthContext, require_permission
from app.core.config import Settings
from app.db.models import (
    AIRun,
    AIStep,
    Artifact,
    ArtifactVersion,
    Assumption,
    AssumptionEvidenceLink,
    Claim,
    ClaimEvidenceLink,
    Competitor,
    CompetitorCandidate,
    Decision,
    DiscoveredSource,
    EvidenceSource,
    Project,
    ResearchSprint,
    Risk,
)
from app.features.research import citation_audit, graph_state, memo_prompting, memo_rendering
from app.features.research import proposals as research_proposals
from app.features.research import strategy as research_strategy
from app.schemas.artifacts import Citation, ClaimDraft
from app.schemas.evidence import EvidenceRetrievalResultRead, EvidenceRetrieveCreate
from app.schemas.research import (
    AgenticResearchMemoDraft,
    ResearchAssumptionDraft,
    ResearchFindingDraft,
    ResearchRiskDraft,
)
from app.services import (
    ai_run_service,
    citation_verifier_service,
    context_service,
    evidence_service,
    governance_service,
    langsmith_observability_service,
    memory_service,
    project_service,
    retrieval_service,
    security_event_service,
    source_provenance_service,
    tool_service,
    workflow_budget_service,
)


class AgenticResearchWorkflowError(RuntimeError):
    pass


ResearchTool = Literal[
    "semantic_search",
    "keyword_search",
    "source_reader",
    "competitor_lookup",
    "project_memory_lookup",
    "artifact_lookup",
    "assumption_lookup",
]


class ResearchToolCall(TypedDict, total=False):
    tool: ResearchTool
    query: str
    mode: Literal["semantic", "keyword", "hybrid"]
    top_k: int
    reason: str
    result_count: int


class AgenticResearchState(TypedDict, total=False):
    project_context: dict[str, Any]
    subquestions: list[str]
    tool_calls: list[ResearchToolCall]
    retrieval_diagnostics: list[dict[str, Any]]
    retrieval_results: list[EvidenceRetrievalResultRead]
    selected_evidence: list[EvidenceRetrievalResultRead]
    context_diagnostics: dict[str, Any]
    gaps: list[str]
    follow_up_results: list[EvidenceRetrievalResultRead]
    memo: AgenticResearchMemoDraft
    critic: dict[str, Any]
    context_pack: dict[str, Any]
    artifact: Artifact
    version: ArtifactVersion
    claims: list[Claim]
    citations: list[Citation]
    unsupported_claims: list[str]
    final_step: AIStep


@dataclass(frozen=True)
class AgenticResearchResult:
    """Return object for a research memo that is ready for human review."""

    run: AIRun
    step: AIStep
    artifact: Artifact
    version: ArtifactVersion
    claims: list[Claim]
    citations: list[Citation]
    unsupported_claims: list[str]
    retrieval_tool_call_count: int
    additional_retrieval_passes: int
    evidence_gap_count: int
    model_provider: str
    model_name: str
    used_stub: bool
    total_tokens: int | None
    total_cost: Decimal | None


@dataclass(frozen=True)
class AgenticResearchApprovalResult:
    run: AIRun
    step: AIStep
    sprint: ResearchSprint
    artifact: Artifact
    version: ArtifactVersion


MAX_SUBQUESTIONS = 6
INITIAL_TOP_K = 4
FOLLOW_UP_TOP_K = 5
SELECTED_EVIDENCE_LIMIT = 10
EVIDENCE_TEXT_LIMIT = 900
MEMO_MAX_TOKENS = 4500


def run_agentic_research(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> AgenticResearchResult:
    """Run a bounded agentic RAG workflow for an approved research sprint."""
    require_permission(auth, "run_research")
    project = project_service.get_project(db, auth, project_id)
    sprint = _get_sprint(db, auth, project_id, sprint_id)
    if sprint.status not in {"approved", "running", "needs_review"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approve the research plan before running agentic research.",
        )

    run = ai_run_service.start_run(
        db,
        auth,
        workflow_type="agentic_research",
        prompt_version=AGENTIC_RESEARCH_PROMPT_VERSION,
        input_summary=sprint.plan.objective[:500],
        project_id=project_id,
        model_provider="stub" if settings.should_use_llm_stub else "litellm",
        model_name=settings.litellm_model,
    )
    trace = langsmith_observability_service.ensure_research_sprint_trace(
        db,
        auth,
        settings,
        project,
        sprint,
        workflow_version=AGENTIC_RESEARCH_PROMPT_VERSION,
        model_provider=run.model_provider,
        model_name=run.model_name,
        run=run,
    )
    completion_holder: dict[str, LLMCompletion] = {}

    def load_context(_: AgenticResearchState) -> AgenticResearchState:
        return {
            "project_context": _step(
                db,
                run,
                "load_research_context",
                {"project_id": str(project_id), "research_sprint_id": str(sprint_id)},
                lambda: _research_context(db, auth, settings, project, sprint),
                settings=settings,
                trace=trace,
                span_name="load_project_context",
            )
        }

    def research_planner(state: AgenticResearchState) -> AgenticResearchState:
        subquestions = _step(
            db,
            run,
            "research_planner",
            {
                "objective": sprint.plan.objective,
                "research_question_count": len(sprint.plan.research_questions),
            },
            lambda: _plan_subquestions(sprint),
            settings=settings,
            trace=trace,
            span_name="research_plan_generation",
        )
        return {"subquestions": subquestions}

    def retrieval_strategy_selector(state: AgenticResearchState) -> AgenticResearchState:
        tool_calls = _step(
            db,
            run,
            "retrieval_strategy_selector",
            {"subquestions": state["subquestions"]},
            lambda: _select_tool_calls(sprint, state["subquestions"]),
            settings=settings,
            trace=trace,
            span_name="retrieval_strategy_selection",
        )
        return {"tool_calls": tool_calls}

    def tool_executor(state: AgenticResearchState) -> AgenticResearchState:
        results = _step(
            db,
            run,
            "tool_executor",
            {"tool_calls": state["tool_calls"]},
            lambda: _execute_tool_calls(
                db,
                auth,
                settings,
                project_id,
                sprint_id,
                state["project_context"],
                state["tool_calls"],
            ),
            settings=settings,
            trace=trace,
            span_name="retrieval",
        )
        return {
            "tool_calls": results["tool_calls"],
            "retrieval_diagnostics": results["retrieval_diagnostics"],
            "retrieval_results": results["retrieval_results"],
        }

    def evidence_selector(state: AgenticResearchState) -> AgenticResearchState:
        selection = _step(
            db,
            run,
            "evidence_selector",
            {"retrieval_result_count": len(state["retrieval_results"])},
            lambda: _select_evidence(settings, state["retrieval_results"]),
            settings=settings,
            trace=trace,
            span_name="evidence_ingestion_summary",
        )
        return {
            "selected_evidence": selection["selected_evidence"],
            "context_diagnostics": selection["context_diagnostics"],
        }

    def gap_detector(state: AgenticResearchState) -> AgenticResearchState:
        gaps = _step(
            db,
            run,
            "gap_detector",
            {
                "subquestions": state["subquestions"],
                "selected_evidence_count": len(state["selected_evidence"]),
            },
            lambda: _detect_gaps(state["subquestions"], state["selected_evidence"]),
            settings=settings,
            trace=trace,
            span_name="evidence_gap_detection",
        )
        return {"gaps": gaps}

    def follow_up_retriever(state: AgenticResearchState) -> AgenticResearchState:
        follow_up = _step(
            db,
            run,
            "follow_up_retriever",
            {"gaps": state["gaps"]},
            lambda: _follow_up_retrieval(
                db,
                auth,
                settings,
                project_id,
                sprint_id,
                state["gaps"],
            ),
            settings=settings,
            trace=trace,
            span_name="retrieval",
        )
        selection = _select_evidence(settings, [*state["selected_evidence"], *follow_up])
        return {
            "follow_up_results": follow_up,
            "selected_evidence": selection["selected_evidence"],
            "context_diagnostics": selection["context_diagnostics"],
        }

    def synthesizer(state: AgenticResearchState) -> AgenticResearchState:
        memo, completion, memo_context_pack = _generate_memo(
            db,
            auth,
            settings,
            run,
            project_id,
            sprint.id,
            state["project_context"],
            state["subquestions"],
            state["selected_evidence"],
            state["gaps"],
            trace,
        )
        completion_holder["completion"] = completion
        return {"memo": memo, "context_pack": memo_context_pack}

    def critic(state: AgenticResearchState) -> AgenticResearchState:
        with workflow_budget_service.workflow_budget_scope(
            db,
            auth,
            settings,
            project_id=project_id,
            research_sprint_id=sprint.id,
        ):
            workflow_budget_service.reserve_critique_loop()
            audited, critique = _step(
                db,
                run,
                "critic",
                {
                    "claim_count": len(state["memo"].claims),
                    "selected_evidence_count": len(state["selected_evidence"]),
                },
                lambda: _critic_review(state["memo"], state["selected_evidence"], state["gaps"]),
                settings=settings,
                trace=trace,
                span_name="critique",
            )
        return {"memo": audited, "critic": critique}

    def final_memo_writer(state: AgenticResearchState) -> AgenticResearchState:
        write_result = _write_research_memo_step(
            db,
            auth,
            settings,
            run,
            project,
            sprint,
            state["memo"],
            state["project_context"],
            state["subquestions"],
            state["tool_calls"],
            state.get("retrieval_diagnostics", []),
            state["selected_evidence"],
            state.get("context_diagnostics", {}),
            state["gaps"],
            state["critic"],
            state["context_pack"],
            trace,
        )
        return write_result

    def human_approval_interrupt(state: AgenticResearchState) -> AgenticResearchState:
        step = ai_run_service.start_step(
            db,
            run,
            step_name="human_approval_interrupt",
            input_json={"artifact_version_id": str(state["version"].id)},
        )
        started = perf_counter()
        output = {
            "status": "waiting_for_human",
            "message": (
                "Research memo is ready for review. Major project memory updates "
                "are intentionally paused until the user approves them."
            ),
            "memory_updates_written": False,
        }
        final_step = ai_run_service.complete_step(
            db,
            step,
            output_json=output,
            latency_ms=int((perf_counter() - started) * 1000),
            tokens=None,
            cost=Decimal("0"),
        )
        langsmith_observability_service.record_step_span(
            db,
            settings,
            run=run,
            step=final_step,
            trace=trace,
            span_name="memory_update_proposal",
            input_json=step.input_json,
            output_json=final_step.output_json,
        )
        sprint.status = "needs_review"
        db.commit()
        return {"final_step": final_step}

    # LangGraph coordinates reasoning state only. Persistence, retrieval,
    # approval gates, and external effects remain in app services so the agent
    # cannot bypass project permissions or mutate memory directly.
    graph = StateGraph(AgenticResearchState)
    graph.add_node("load_research_context", load_context)
    graph.add_node("research_planner", research_planner)
    graph.add_node("retrieval_strategy_selector", retrieval_strategy_selector)
    graph.add_node("tool_executor", tool_executor)
    graph.add_node("evidence_selector", evidence_selector)
    graph.add_node("gap_detector", gap_detector)
    graph.add_node("follow_up_retriever", follow_up_retriever)
    graph.add_node("synthesizer", synthesizer)
    graph.add_node("critic", critic)
    graph.add_node("final_memo_writer", final_memo_writer)
    graph.add_node("human_approval_interrupt", human_approval_interrupt)
    graph.set_entry_point("load_research_context")
    graph.add_edge("load_research_context", "research_planner")
    graph.add_edge("research_planner", "retrieval_strategy_selector")
    graph.add_edge("retrieval_strategy_selector", "tool_executor")
    graph.add_edge("tool_executor", "evidence_selector")
    graph.add_edge("evidence_selector", "gap_detector")
    graph.add_edge("gap_detector", "follow_up_retriever")
    graph.add_edge("follow_up_retriever", "synthesizer")
    graph.add_edge("synthesizer", "critic")
    graph.add_edge("critic", "final_memo_writer")
    graph.add_edge("final_memo_writer", "human_approval_interrupt")
    graph.add_edge("human_approval_interrupt", END)

    try:
        if sprint.status == "approved":
            sprint.status = "running"
            sprint.started_at = sprint.started_at or datetime.now(UTC)
            db.commit()
        state = graph.compile().invoke({})
    except (StructuredOutputError, RuntimeError, HTTPException):
        sprint.status = "failed"
        db.commit()
        ai_run_service.fail_run(db, run, error="Agentic research failed.")
        langsmith_observability_service.complete_trace(
            settings,
            trace,
            error="Agentic research failed.",
        )
        raise
    except Exception as exc:
        sprint.status = "failed"
        db.commit()
        ai_run_service.fail_run(db, run, error=str(exc))
        langsmith_observability_service.complete_trace(settings, trace, error=str(exc))
        raise AgenticResearchWorkflowError("Agentic research failed.") from exc

    completion = completion_holder.get("completion")
    if completion is None:
        raise AgenticResearchWorkflowError("Agentic research did not record model completion.")

    run = ai_run_service.wait_for_human(
        db,
        run,
        output_summary=state["memo"].executive_verdict[:1000],
        total_tokens=completion.total_tokens,
        total_cost=completion.total_cost,
        model_provider=completion.model_provider,
        model_name=completion.model_name,
    )
    langsmith_observability_service.attach_run_trace(db, run, trace.trace_id, trace.trace_url)
    db.commit()
    return AgenticResearchResult(
        run=run,
        step=state["final_step"],
        artifact=_load_artifact(db, auth, project_id, state["artifact"].id),
        version=state["version"],
        claims=state["claims"],
        citations=state["citations"],
        unsupported_claims=state["unsupported_claims"],
        retrieval_tool_call_count=sum(
            1
            for call in state["tool_calls"]
            if call["tool"] in {"semantic_search", "keyword_search"}
        ),
        additional_retrieval_passes=1 if state["follow_up_results"] else 0,
        evidence_gap_count=len(state["gaps"]),
        model_provider=completion.model_provider,
        model_name=completion.model_name,
        used_stub=completion.used_stub,
        total_tokens=completion.total_tokens,
        total_cost=completion.total_cost,
    )


def approve_research_memo(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> AgenticResearchApprovalResult:
    require_permission(auth, "approve_memory_updates")
    sprint = _get_sprint(db, auth, project_id, sprint_id)
    if sprint.status not in {"needs_review", "waiting_for_memory_approval"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only research memos awaiting review can be approved.",
        )

    artifact = _research_memo_for_sprint(db, auth, project_id, sprint_id)
    version = _current_artifact_version(db, artifact)
    run = _memo_ai_run(db, auth, project_id, version)
    trace = _trace_from_sprint(settings, sprint, run)
    step = ai_run_service.start_step(
        db,
        run,
        step_name="approve_research_memo",
        input_json={
            "research_sprint_id": str(sprint.id),
            "artifact_id": str(artifact.id),
            "artifact_version_id": str(version.id),
        },
    )
    started = perf_counter()

    project = project_service.get_project(db, auth, project_id)
    memory_summary = _write_approved_memory_updates(db, auth, project, sprint, version)
    approved_tool_invocations = tool_service.approve_pending_proposals_for_sprint(
        db,
        auth,
        project_id,
        sprint.id,
        {"propose_memory_update", "propose_validation_plan", "propose_decision"},
    )
    content = dict(version.structured_content)
    content["memory_update_status"] = "approved"
    content["memory_update_approved_at"] = datetime.now(UTC).isoformat()
    content["memory_update_approved_by"] = str(auth.user_id)
    content["memory_updates_written"] = True
    content["memory_update_summary"] = memory_summary
    content["approved_tool_invocation_ids"] = [
        str(invocation.id) for invocation in approved_tool_invocations
    ]
    version.structured_content = content
    flag_modified(version, "structured_content")

    sprint.status = "completed"
    sprint.completed_at = datetime.now(UTC)
    sprint.plan.status = "completed"
    completed_step = ai_run_service.complete_step(
        db,
        step,
        output_json={
            "status": "approved",
            "research_sprint_status": "completed",
            "memory_update_status": "approved",
            "memory_updates_written": True,
            "memory_update_summary": memory_summary,
        },
        latency_ms=int((perf_counter() - started) * 1000),
        tokens=None,
        cost=Decimal("0"),
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
    )
    run = ai_run_service.complete_run(
        db,
        run,
        output_summary="Research memo approved by human reviewer.",
        total_tokens=run.total_tokens,
        total_cost=run.total_cost,
        model_provider=run.model_provider or "unknown",
        model_name=run.model_name or "unknown",
    )
    langsmith_observability_service.attach_run_trace(db, run, trace.trace_id, trace.trace_url)
    langsmith_observability_service.complete_trace(
        settings,
        trace,
        output_summary="Research memo approved and memory updates written.",
        metrics={
            "assumptions_written": len(memory_summary.get("assumption_ids", [])),
            "risks_written": len(memory_summary.get("risk_ids", [])),
        },
    )
    governance_service.resolve_pending_approvals_for_entity(
        db,
        auth,
        project_id=project_id,
        entity_type="artifact_version",
        entity_id=version.id,
        status_value="approved",
        request_types={"memory_update", "validation_plan", "decision"},
    )
    governance_service.record_audit_event(
        db,
        auth,
        event_type="memory_update_approved",
        actor_type="user",
        project_id=project_id,
        entity_type="artifact_version",
        entity_id=version.id,
        risk_level="medium",
        summary="Approved research memo memory updates.",
        metadata=memory_summary,
    )
    db.refresh(sprint)
    version = _load_version(db, version.id)
    artifact = _load_artifact(db, auth, project_id, artifact.id)
    return AgenticResearchApprovalResult(
        run=run,
        step=completed_step,
        sprint=sprint,
        artifact=artifact,
        version=version,
    )


def reject_research_memo(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> AgenticResearchApprovalResult:
    require_permission(auth, "approve_memory_updates")
    sprint = _get_sprint(db, auth, project_id, sprint_id)
    if sprint.status not in {"needs_review", "waiting_for_memory_approval"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only research memos awaiting review can be rejected.",
        )

    artifact = _research_memo_for_sprint(db, auth, project_id, sprint_id)
    version = _current_artifact_version(db, artifact)
    run = _memo_ai_run(db, auth, project_id, version)
    trace = _trace_from_sprint(settings, sprint, run)
    step = ai_run_service.start_step(
        db,
        run,
        step_name="reject_research_memo",
        input_json={
            "research_sprint_id": str(sprint.id),
            "artifact_id": str(artifact.id),
            "artifact_version_id": str(version.id),
        },
    )
    started = perf_counter()

    content = dict(version.structured_content)
    rejected_tool_invocations = tool_service.reject_pending_proposals_for_sprint(
        db,
        auth,
        project_id,
        sprint.id,
        {"propose_memory_update", "propose_validation_plan", "propose_decision"},
    )
    content["memory_update_status"] = "rejected"
    content["memory_update_rejected_at"] = datetime.now(UTC).isoformat()
    content["memory_update_rejected_by"] = str(auth.user_id)
    content["memory_updates_written"] = False
    content["rejected_tool_invocation_ids"] = [
        str(invocation.id) for invocation in rejected_tool_invocations
    ]
    version.structured_content = content
    flag_modified(version, "structured_content")

    sprint.status = "completed"
    sprint.completed_at = datetime.now(UTC)
    sprint.plan.status = "completed"
    completed_step = ai_run_service.complete_step(
        db,
        step,
        output_json={
            "status": "rejected",
            "research_sprint_status": "completed",
            "memory_update_status": "rejected",
            "memory_updates_written": False,
        },
        latency_ms=int((perf_counter() - started) * 1000),
        tokens=None,
        cost=Decimal("0"),
    )
    langsmith_observability_service.record_step_span(
        db,
        settings,
        run=run,
        step=completed_step,
        trace=trace,
        span_name="memory_update_proposal",
        input_json=step.input_json,
        output_json=completed_step.output_json,
    )
    run = ai_run_service.complete_run(
        db,
        run,
        output_summary="Research memo memory updates rejected by human reviewer.",
        total_tokens=run.total_tokens,
        total_cost=run.total_cost,
        model_provider=run.model_provider or "unknown",
        model_name=run.model_name or "unknown",
    )
    langsmith_observability_service.attach_run_trace(db, run, trace.trace_id, trace.trace_url)
    langsmith_observability_service.complete_trace(
        settings,
        trace,
        output_summary="Research memo memory updates rejected by human reviewer.",
        metrics={"memory_updates_written": 0},
    )
    governance_service.resolve_pending_approvals_for_entity(
        db,
        auth,
        project_id=project_id,
        entity_type="artifact_version",
        entity_id=version.id,
        status_value="rejected",
        request_types={"memory_update", "validation_plan", "decision"},
    )
    governance_service.record_audit_event(
        db,
        auth,
        event_type="memory_update_rejected",
        actor_type="user",
        project_id=project_id,
        entity_type="artifact_version",
        entity_id=version.id,
        risk_level="medium",
        summary="Rejected research memo memory updates.",
        metadata={"research_sprint_id": str(sprint.id)},
    )
    db.refresh(sprint)
    version = _load_version(db, version.id)
    artifact = _load_artifact(db, auth, project_id, artifact.id)
    return AgenticResearchApprovalResult(
        run=run,
        step=completed_step,
        sprint=sprint,
        artifact=artifact,
        version=version,
    )


def _write_approved_memory_updates(
    db: Session,
    auth: AuthContext,
    project: Project,
    sprint: ResearchSprint,
    version: ArtifactVersion,
) -> dict[str, Any]:
    content = dict(version.structured_content or {})
    memo = AgenticResearchMemoDraft.model_validate(content.get("memo") or {})
    assumptions = _upsert_research_assumptions(db, auth, project, memo)
    risks = _upsert_research_risks(db, auth, project, memo)
    _link_assumptions_to_research_evidence(db, assumptions, memo)
    _refresh_project_confidence_from_research(project, assumptions)
    memory_items = [
        memory_service.upsert_from_assumption(
            db,
            auth,
            project.id,
            assumption,
            source_entity_type="artifact_version",
            source_entity_id=version.id,
            source_metadata={
                "research_sprint_id": str(sprint.id),
                "decision_recommendation": memo.decision_recommendation,
                "recommendation_source": "agentic_research_memo",
            },
        )
        for assumption in assumptions
    ]
    memory_items.extend(
        memory_service.upsert_from_risk(
            db,
            auth,
            project.id,
            risk,
            source_entity_type="artifact_version",
            source_entity_id=version.id,
            source_metadata={
                "research_sprint_id": str(sprint.id),
                "decision_recommendation": memo.decision_recommendation,
                "recommendation_source": "agentic_research_memo",
            },
        )
        for risk in risks
    )
    db.flush()
    return {
        "research_sprint_id": str(sprint.id),
        "assumption_ids": [str(assumption.id) for assumption in assumptions],
        "risk_ids": [str(risk.id) for risk in risks],
        "memory_item_ids": [str(item.id) for item in memory_items],
        "recommended_validation_actions": memo.recommended_validation_actions,
        "first_validation_target_assumption_id": str(assumptions[0].id) if assumptions else None,
    }


def _upsert_research_assumptions(
    db: Session,
    auth: AuthContext,
    project: Project,
    memo: AgenticResearchMemoDraft,
) -> list[Assumption]:
    drafts = memo.riskiest_assumptions or _fallback_research_assumptions(memo)
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
        confidence = _assumption_confidence_from_research(draft)
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
                confidence_score=confidence,
                status="untested",
                recommended_test=draft.recommended_test
                or _first_recommended_validation_action(memo),
            )
            db.add(assumption)
            db.flush()
            existing[key] = assumption
        else:
            assumption.category = _optional_truncate(draft.category, 100)
            assumption.importance = draft.importance
            assumption.uncertainty = draft.uncertainty
            assumption.kill_risk = draft.kill_risk
            assumption.confidence_score = confidence
            assumption.recommended_test = (
                draft.recommended_test
                or assumption.recommended_test
                or _first_recommended_validation_action(memo)
            )
        assumptions.append(assumption)
    return assumptions


def _upsert_research_risks(
    db: Session,
    auth: AuthContext,
    project: Project,
    memo: AgenticResearchMemoDraft,
) -> list[Risk]:
    drafts = memo.key_risks or _fallback_research_risks(memo)
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


def _link_assumptions_to_research_evidence(
    db: Session,
    assumptions: list[Assumption],
    memo: AgenticResearchMemoDraft,
) -> None:
    citations_by_text = {
        _normalize_key(draft.text): draft.citations
        for draft in memo.riskiest_assumptions
        if draft.citations
    }
    fallback_citations = memo.citations[:3]
    for assumption in assumptions:
        citations = citations_by_text.get(_normalize_key(assumption.text)) or fallback_citations
        for citation in citations[:3]:
            exists = db.scalar(
                select(AssumptionEvidenceLink.id).where(
                    AssumptionEvidenceLink.assumption_id == assumption.id,
                    AssumptionEvidenceLink.evidence_source_id == citation.source_id,
                    AssumptionEvidenceLink.evidence_chunk_id == citation.chunk_id,
                )
            )
            if exists is not None:
                continue
            db.add(
                AssumptionEvidenceLink(
                    assumption_id=assumption.id,
                    evidence_source_id=citation.source_id,
                    evidence_chunk_id=citation.chunk_id,
                    relevance_score=_decimal_score(citation.relevance_score),
                    quote=citation.quote,
                )
            )


def _refresh_project_confidence_from_research(
    project: Project,
    assumptions: list[Assumption],
) -> None:
    scores = [
        assumption.confidence_score
        for assumption in assumptions
        if assumption.confidence_score is not None
    ]
    if scores:
        project.confidence_score = Decimal(str(round(sum(scores) / Decimal(len(scores)), 4)))


_fallback_research_assumptions = memo_rendering.fallback_research_assumptions
_fallback_research_risks = memo_rendering.fallback_research_risks


def _assumption_confidence_from_research(draft: ResearchAssumptionDraft) -> Decimal | None:
    if draft.confidence_score is not None:
        return _decimal_score(draft.confidence_score)
    defaults = {
        "strong": Decimal("0.65"),
        "medium": Decimal("0.45"),
        "weak": Decimal("0.25"),
    }
    return defaults[draft.evidence_strength]


_first_recommended_validation_action = memo_rendering.first_recommended_validation_action


def _step(
    db: Session,
    run: AIRun,
    step_name: str,
    input_json: dict[str, Any],
    operation,
    *,
    settings: Settings | None = None,
    trace: langsmith_observability_service.TraceContext | None = None,
    span_name: str | None = None,
):
    step = ai_run_service.start_step(db, run, step_name=step_name, input_json=input_json)
    started = perf_counter()
    try:
        result = operation()
    except Exception as exc:
        failed_step = ai_run_service.fail_step(
            db,
            step,
            error=str(exc),
            latency_ms=int((perf_counter() - started) * 1000),
        )
        if settings is not None and trace is not None:
            langsmith_observability_service.record_step_span(
                db,
                settings,
                run=run,
                step=failed_step,
                trace=trace,
                span_name=span_name or step_name,
                input_json=input_json,
                error=str(exc),
            )
        raise
    completed_step = ai_run_service.complete_step(
        db,
        step,
        output_json=_json_safe(result),
        latency_ms=int((perf_counter() - started) * 1000),
        tokens=None,
        cost=Decimal("0"),
    )
    if settings is not None and trace is not None:
        langsmith_observability_service.record_step_span(
            db,
            settings,
            run=run,
            step=completed_step,
            trace=trace,
            span_name=span_name or step_name,
            input_json=input_json,
            output_json=completed_step.output_json,
        )
    return result


def _get_sprint(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> ResearchSprint:
    sprint = db.scalar(
        select(ResearchSprint)
        .where(
            ResearchSprint.id == sprint_id,
            ResearchSprint.workspace_id == auth.workspace_id,
            ResearchSprint.project_id == project_id,
        )
        .options(selectinload(ResearchSprint.plan))
    )
    if sprint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research sprint not found.",
        )
    return sprint


def _trace_from_sprint(
    settings: Settings,
    sprint: ResearchSprint,
    run: AIRun,
) -> langsmith_observability_service.TraceContext:
    trace_id = sprint.langsmith_trace_id or run.langsmith_trace_id or str(uuid.uuid4())
    trace_url = (
        sprint.langsmith_trace_url
        or run.langsmith_trace_url
        or f"{settings.langsmith_public_url_base.rstrip('/')}/o/default/projects/p/"
        f"{settings.langsmith_project}/r/{trace_id}"
    )
    metadata = {
        "project_id": str(sprint.project_id),
        "research_sprint_id": str(sprint.id),
        "project_stage": "research",
        "workflow_version": AGENTIC_RESEARCH_PROMPT_VERSION,
        "user_id": str(run.created_by) if run.created_by else None,
        "model_provider": run.model_provider,
        "model_name": run.model_name,
        "started_at": (sprint.started_at or run.started_at or datetime.now(UTC)).isoformat(),
    }
    return langsmith_observability_service.TraceContext(
        trace_id=trace_id,
        trace_url=trace_url,
        enabled=langsmith_observability_service.langsmith_enabled(settings),
        metadata=metadata,
    )


def _research_context(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project: Project,
    sprint: ResearchSprint,
) -> dict[str, Any]:
    project_summary = tool_service.execute_tool(
        db,
        auth,
        settings,
        project.id,
        "get_project_summary",
        {},
        research_sprint_id=sprint.id,
        requested_by="agent",
    ).output
    source_summary = tool_service.execute_tool(
        db,
        auth,
        settings,
        project.id,
        "list_project_sources",
        {},
        research_sprint_id=sprint.id,
        requested_by="agent",
    ).output
    competitor_summary = tool_service.execute_tool(
        db,
        auth,
        settings,
        project.id,
        "list_competitors",
        {},
        research_sprint_id=sprint.id,
        requested_by="agent",
    ).output
    assumption_summary = tool_service.execute_tool(
        db,
        auth,
        settings,
        project.id,
        "list_assumptions",
        {},
        research_sprint_id=sprint.id,
        requested_by="agent",
    ).output
    validation_summary = tool_service.execute_tool(
        db,
        auth,
        settings,
        project.id,
        "list_validation_plans",
        {},
        research_sprint_id=sprint.id,
        requested_by="agent",
    ).output
    decision_summary = tool_service.execute_tool(
        db,
        auth,
        settings,
        project.id,
        "list_decisions",
        {},
        research_sprint_id=sprint.id,
        requested_by="agent",
    ).output
    memo_summary = tool_service.execute_tool(
        db,
        auth,
        settings,
        project.id,
        "get_research_memo",
        {"research_sprint_id": str(sprint.id)},
        research_sprint_id=sprint.id,
        requested_by="agent",
    ).output
    memory_summary = tool_service.execute_tool(
        db,
        auth,
        settings,
        project.id,
        "list_project_memory",
        {"workflow_type": "agentic_research", "limit": 20},
        research_sprint_id=sprint.id,
        requested_by="agent",
    ).output
    project_payload = project_summary.get("project") or {}
    return {
        "project": project_payload,
        "research_plan": {
            "id": str(sprint.plan.id),
            "objective": sprint.plan.objective,
            "target_customer_hypotheses": sprint.plan.target_customer_hypotheses,
            "research_questions": sprint.plan.research_questions,
            "competitor_queries": sprint.plan.competitor_queries,
            "market_queries": sprint.plan.market_queries,
            "substitute_queries": sprint.plan.substitute_queries,
            "assumptions_to_test": sprint.plan.assumptions_to_test,
            "expected_outputs": sprint.plan.expected_outputs,
        },
        "research_sources": source_summary.get("research_sources", []),
        "evidence_sources": source_summary.get("sources", []),
        "competitors": competitor_summary.get("competitors", []),
        "competitor_candidates": competitor_summary.get("competitor_candidates", []),
        "artifacts": validation_summary.get("artifacts", []),
        "assumptions": assumption_summary.get("assumptions", []),
        "risks": assumption_summary.get("risks", []),
        "validation_plans": validation_summary,
        "decisions": decision_summary.get("decisions", []),
        "project_memory": memory_summary.get("memory_items", []),
        "latest_research_memo": memo_summary.get("memo"),
    }


def _plan_subquestions(sprint: ResearchSprint) -> list[str]:
    return research_strategy.plan_subquestions(sprint, max_subquestions=MAX_SUBQUESTIONS)


def _select_tool_calls(
    sprint: ResearchSprint,
    subquestions: list[str],
) -> list[ResearchToolCall]:
    return research_strategy.select_tool_calls(
        sprint,
        subquestions,
        max_subquestions=MAX_SUBQUESTIONS,
        initial_top_k=INITIAL_TOP_K,
    )


def _execute_tool_calls(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    project_context: dict[str, Any],
    tool_calls: list[ResearchToolCall],
) -> dict[str, Any]:
    retrieval_results: list[EvidenceRetrievalResultRead] = []
    retrieval_diagnostics: list[dict[str, Any]] = []
    completed_calls: list[ResearchToolCall] = []
    for call in tool_calls:
        tool = call["tool"]
        if tool in {"semantic_search", "keyword_search"}:
            tool_result = tool_service.execute_tool(
                db,
                auth,
                settings,
                project_id,
                "search_project_evidence",
                {
                    "query": call["query"],
                    "mode": call["mode"],
                    "top_k": int(call.get("top_k") or INITIAL_TOP_K),
                },
                research_sprint_id=sprint_id,
                requested_by="agent",
            )
            results = [
                EvidenceRetrievalResultRead.model_validate(result)
                for result in tool_result.output.get("results", [])
            ]
            diagnostics = tool_result.output.get("diagnostics")
            if isinstance(diagnostics, dict):
                retrieval_diagnostics.append(diagnostics)
            retrieval_results.extend(results)
            completed_calls.append({**call, "result_count": len(results)})
        elif tool == "source_reader":
            tool_service.execute_tool(
                db,
                auth,
                settings,
                project_id,
                "list_project_sources",
                {},
                research_sprint_id=sprint_id,
                requested_by="agent",
            )
            source_results = _source_reader_results(db, auth, settings, project_id)
            retrieval_results.extend(source_results)
            completed_calls.append({**call, "result_count": len(source_results)})
        else:
            lookup_tool_name = _lookup_tool_name(tool)
            if lookup_tool_name is not None:
                tool_service.execute_tool(
                    db,
                    auth,
                    settings,
                    project_id,
                    lookup_tool_name,
                    {},
                    research_sprint_id=sprint_id,
                    requested_by="agent",
                )
            lookup_count = len(_lookup_tool_payload(project_context, tool))
            completed_calls.append({**call, "result_count": lookup_count})
    return {
        "tool_calls": completed_calls,
        "retrieval_diagnostics": retrieval_diagnostics,
        "retrieval_results": retrieval_results,
    }


_lookup_tool_name = research_strategy.lookup_tool_name


_lookup_tool_payload = research_strategy.lookup_tool_payload


def _source_reader_results(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
) -> list[EvidenceRetrievalResultRead]:
    return retrieval_service.read_recent_evidence_results(
        db,
        auth,
        settings,
        project_id,
        limit=8,
    )


def _select_evidence(
    settings: Settings,
    results: list[EvidenceRetrievalResultRead],
) -> dict[str, Any]:
    by_chunk: dict[uuid.UUID, EvidenceRetrievalResultRead] = {}
    for result in results:
        existing = by_chunk.get(result.chunk_id)
        if existing is None or result.score > existing.score:
            by_chunk[result.chunk_id] = result
    selected = sorted(
        by_chunk.values(),
        key=lambda result: result.rerank_score if result.rerank_score is not None else result.score,
        reverse=True,
    )
    assembled, diagnostics = retrieval_service.assemble_context_results(
        settings,
        selected,
        top_k=SELECTED_EVIDENCE_LIMIT,
    )
    return {
        "selected_evidence": assembled,
        "context_diagnostics": diagnostics.model_dump(mode="json"),
    }


def _detect_gaps(
    subquestions: list[str],
    selected_evidence: list[EvidenceRetrievalResultRead],
) -> list[str]:
    return research_strategy.detect_gaps(
        subquestions,
        selected_evidence,
        min_evidence_count=3,
        max_gaps=6,
    )


def _follow_up_retrieval(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    gaps: list[str],
) -> list[EvidenceRetrievalResultRead]:
    if not gaps:
        return []
    results: list[EvidenceRetrievalResultRead] = []
    for gap in gaps[:3]:
        payload = EvidenceRetrieveCreate(
            query=f"{gap} customer pain pricing competitor substitute validation evidence",
            mode="hybrid",
            top_k=FOLLOW_UP_TOP_K,
        )
        tool_result = tool_service.execute_tool(
            db,
            auth,
            settings,
            project_id,
            "search_project_evidence",
            payload.model_dump(mode="json"),
            research_sprint_id=sprint_id,
            requested_by="agent",
        )
        results.extend(
            EvidenceRetrievalResultRead.model_validate(result)
            for result in tool_result.output.get("results", [])
        )
    return results


def _generate_memo(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    run: AIRun,
    project_id: uuid.UUID,
    research_sprint_id: uuid.UUID,
    project_context: dict[str, Any],
    subquestions: list[str],
    selected_evidence: list[EvidenceRetrievalResultRead],
    gaps: list[str],
    trace: langsmith_observability_service.TraceContext,
) -> tuple[AgenticResearchMemoDraft, LLMCompletion, dict[str, Any]]:
    memory_selection = memory_service.select_memory_for_context(
        db,
        auth,
        project_id,
        workflow_type="agentic_research",
        limit=20,
    )
    context_pack = context_service.build_research_context_pack(
        settings,
        project_id=project_id,
        objective=str((project_context.get("research_plan") or {}).get("objective") or ""),
        project_context=project_context,
        subquestions=subquestions,
        selected_evidence=selected_evidence,
        gaps=gaps,
        prompt_version=AGENTIC_RESEARCH_PROMPT_VERSION,
        expected_schema=AgenticResearchMemoDraft.__name__,
        memory_selection=memory_selection,
    )
    context_pack_payload = context_pack.model_dump(mode="json")
    messages = _memo_messages(context_pack)
    step = ai_run_service.start_step(
        db,
        run,
        step_name="synthesizer",
        input_json={
            "schema": AgenticResearchMemoDraft.__name__,
            "subquestions": subquestions,
            "evidence_count": len(selected_evidence),
            "gap_count": len(gaps),
            "context_pack": context_pack.prompt_metadata(),
            "messages": [message.model_dump() for message in messages],
        },
    )
    started = perf_counter()
    try:
        if settings.should_use_llm_stub or should_use_fallback_without_model(settings):
            memo = _fallback_memo(project_context, subquestions, selected_evidence, gaps)
            completion = _fallback_completion(
                settings,
                messages,
                memo,
                "stub" if settings.should_use_llm_stub else "policy_always",
            )
        else:
            try:
                with workflow_budget_service.workflow_budget_scope(
                    db,
                    auth,
                    settings,
                    project_id=project_id,
                    research_sprint_id=research_sprint_id,
                ):
                    result = generate_structured_output(
                        settings,
                        AgenticResearchMemoDraft,
                        messages,
                        model=settings.litellm_model,
                        temperature=0.0,
                        max_tokens=MEMO_MAX_TOKENS,
                    )
                memo = AgenticResearchMemoDraft.model_validate(result.parsed)
                completion = result.completion
            except (StructuredOutputError, RuntimeError) as exc:
                if not should_use_fallback_after_error(settings):
                    raise
                memo = _fallback_memo(project_context, subquestions, selected_evidence, gaps)
                completion = _fallback_completion(settings, messages, memo, "emergency", exc)
    except Exception as exc:
        failed_step = ai_run_service.fail_step(
            db,
            step,
            error=str(exc),
            latency_ms=int((perf_counter() - started) * 1000),
        )
        langsmith_observability_service.record_step_span(
            db,
            settings,
            run=run,
            step=failed_step,
            trace=trace,
            span_name="synthesis",
            input_json=step.input_json,
            error=str(exc),
            run_type="llm",
        )
        raise
    completed_step = ai_run_service.complete_step(
        db,
        step,
        output_json=memo.model_dump(mode="json"),
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
        span_name="synthesis",
        input_json=step.input_json,
        output_json=completed_step.output_json,
        run_type="llm" if completion.model_provider != "stub" else "chain",
    )
    return memo, completion, context_pack_payload


_memo_messages = memo_prompting.memo_messages


def _critic_review(
    memo: AgenticResearchMemoDraft,
    selected_evidence: list[EvidenceRetrievalResultRead],
    gaps: list[str],
) -> tuple[AgenticResearchMemoDraft, dict[str, Any]]:
    audited = _audit_citations(memo, selected_evidence)
    weak_claims = [
        claim.text
        for claim in audited.claims
        if claim.support_level in {"unsupported", "inference"} or not claim.citations
    ]
    critique = {
        "weak_claim_count": len(weak_claims),
        "weak_claims": weak_claims[:8],
        "evidence_gap_count": len(gaps),
        "requires_human_approval_before_memory_write": True,
    }
    unsupported = list(dict.fromkeys([*audited.unsupported_claims, *weak_claims]))
    return audited.model_copy(update={"unsupported_claims": unsupported[:12]}), critique


def _write_research_memo_step(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    run: AIRun,
    project: Project,
    sprint: ResearchSprint,
    memo: AgenticResearchMemoDraft,
    project_context: dict[str, Any],
    subquestions: list[str],
    tool_calls: list[ResearchToolCall],
    retrieval_diagnostics: list[dict[str, Any]],
    selected_evidence: list[EvidenceRetrievalResultRead],
    context_diagnostics: dict[str, Any],
    gaps: list[str],
    critic: dict[str, Any],
    context_pack: dict[str, Any],
    trace: langsmith_observability_service.TraceContext,
) -> AgenticResearchState:
    step = ai_run_service.start_step(
        db,
        run,
        step_name="final_memo_writer",
        input_json={
            "artifact_type": "research_memo",
            "research_sprint_id": str(sprint.id),
            "claim_count": len(memo.claims),
        },
    )
    started = perf_counter()
    try:
        artifact = _get_or_create_research_memo_artifact(db, auth, project)
        claim_conflict = _single_source_claim_conflict(
            db,
            auth,
            project.id,
            memo.claims,
            selected_evidence,
        )
        if claim_conflict.detected:
            for source_id in claim_conflict.controlling_source_ids:
                source = db.get(EvidenceSource, uuid.UUID(source_id))
                if source is not None:
                    evidence_service.quarantine_source_for_conflicting_claim(db, auth, source)
            memo = _suppress_conflicting_claim(memo, claim_conflict)
        version_number = _next_artifact_version(db, artifact.id)
        version = ArtifactVersion(
            workspace_id=auth.workspace_id,
            artifact_id=artifact.id,
            version=version_number,
            markdown_content=_render_markdown_memo(project, memo),
            structured_content={
                "research_sprint_id": str(sprint.id),
                "research_plan_id": str(sprint.plan.id),
                "langsmith_trace_id": trace.trace_id,
                "langsmith_trace_url": trace.trace_url,
                "memo": memo.model_dump(mode="json"),
                "project_context": project_context,
                "subquestions": subquestions,
                "tool_calls": tool_calls,
                "retrieval_diagnostics": retrieval_diagnostics,
                "retrieval_context": context_diagnostics,
                "context_pack": context_pack,
                "selected_evidence": [
                    result.model_dump(mode="json") for result in selected_evidence
                ],
                "citation_outcomes": citation_verifier_service.claim_outcome_records(
                    citation_verifier_service.verify_claims(memo.claims, selected_evidence)
                ),
                "evidence_gaps": gaps,
                "critic": critic,
                "memory_update_status": "pending_human_approval",
                "memory_update_preview": _memory_update_preview(memo),
            },
            generated_by_ai_run_id=run.id,
            langsmith_trace_id=trace.trace_id,
            langsmith_trace_url=trace.trace_url,
            created_by=auth.user_id,
        )
        db.add(version)
        db.flush()
        artifact.current_version_id = version.id
        security_event_service.record_artifact_claim_verification_failure(
            db,
            auth,
            project_id=project.id,
            ai_run_id=run.id,
            artifact_type="research_memo",
            unverified_claim_count=len(memo.unsupported_claims),
            temporal_workflow_id=sprint.temporal_workflow_id,
        )
        claims = _write_claims(db, auth, project, version, memo.claims)
        if claim_conflict.detected:
            content = dict(version.structured_content)
            content["conflicting_claim"] = {
                "proposed_claim": claim_conflict.proposed_claim,
                "existing_claim": claim_conflict.existing_claim,
                "controlling_source_ids": list(claim_conflict.controlling_source_ids),
                "action": "source_quarantined_pending_independent_corroboration",
            }
            version.structured_content = content
            flag_modified(version, "structured_content")
            governance_service.record_audit_event(
                db,
                auth,
                event_type="conflicting_claim_detected",
                actor_type="system",
                project_id=project.id,
                entity_type="artifact_version",
                entity_id=version.id,
                risk_level="high",
                summary=(
                    "A single newly added source introduced a claim that conflicts with "
                    "existing supported evidence."
                ),
                metadata={
                    "proposed_claim": claim_conflict.proposed_claim,
                    "existing_claim": claim_conflict.existing_claim,
                    "controlling_source_ids": list(claim_conflict.controlling_source_ids),
                },
            )
        recommendation_shift = _recommendation_shift(
            db,
            auth,
            project.id,
            memo.decision_recommendation,
            selected_evidence,
        )
        if recommendation_shift.detected:
            for source_id in recommendation_shift.controlling_source_ids:
                source = db.get(EvidenceSource, uuid.UUID(source_id))
                if source is not None:
                    evidence_service.quarantine_source_for_recommendation_shift(db, auth, source)
            content = dict(version.structured_content)
            content["recommendation_shift"] = {
                "previous_recommendation": recommendation_shift.previous_recommendation,
                "proposed_recommendation": recommendation_shift.proposed_recommendation,
                "controlling_source_ids": list(recommendation_shift.controlling_source_ids),
                "action": "source_quarantined_pending_independent_corroboration",
            }
            version.structured_content = content
            flag_modified(version, "structured_content")
            governance_service.record_audit_event(
                db,
                auth,
                event_type="recommendation_shift_detected",
                actor_type="system",
                project_id=project.id,
                entity_type="artifact_version",
                entity_id=version.id,
                risk_level="high",
                summary=(
                    "A single newly added source attempted to reverse a decision recommendation."
                ),
                metadata={
                    "previous_recommendation": recommendation_shift.previous_recommendation,
                    "proposed_recommendation": recommendation_shift.proposed_recommendation,
                    "controlling_source_ids": list(recommendation_shift.controlling_source_ids),
                },
            )
        proposal_payloads = _research_memo_proposal_payloads(
            memo,
            research_sprint_id=sprint.id,
            artifact_version_id=version.id,
        )
        if claim_conflict.detected:
            proposal_payloads = _replace_conflicting_claim_proposals(
                proposal_payloads,
                claim_conflict,
            )
        if recommendation_shift.detected:
            proposal_payloads = _replace_recommendation_shift_proposals(
                proposal_payloads,
                recommendation_shift,
            )
        memory_update_invocation = tool_service.create_proposal(
            db,
            auth,
            project.id,
            "propose_memory_update",
            proposal_payloads.memory_update,
            research_sprint_id=sprint.id,
            requested_by="agent",
            input_json=proposal_payloads.memory_update_input,
        )
        validation_invocation = tool_service.create_proposal(
            db,
            auth,
            project.id,
            "propose_validation_plan",
            proposal_payloads.validation_plan,
            research_sprint_id=sprint.id,
            requested_by="agent",
            input_json=proposal_payloads.validation_plan_input,
        )
        decision_invocation = tool_service.create_proposal(
            db,
            auth,
            project.id,
            "propose_decision",
            proposal_payloads.decision,
            research_sprint_id=sprint.id,
            requested_by="agent",
            input_json=proposal_payloads.decision_input,
        )
        content = dict(version.structured_content)
        content["proposal_tool_invocation_ids"] = [
            str(memory_update_invocation.id),
            str(validation_invocation.id),
            str(decision_invocation.id),
        ]
        version.structured_content = content
        flag_modified(version, "structured_content")
        sprint.status = "needs_review"
        governance_service.record_audit_event(
            db,
            auth,
            event_type="memory_update_proposed",
            actor_type="agent",
            project_id=project.id,
            entity_type="artifact_version",
            entity_id=version.id,
            risk_level="medium",
            summary="Research memo proposed memory, validation, and decision updates.",
            metadata={
                "research_sprint_id": str(sprint.id),
                "tool_invocation_ids": content["proposal_tool_invocation_ids"],
            },
        )
        db.commit()
        artifact = _load_artifact(db, auth, project.id, artifact.id)
        version = _load_version(db, version.id)
        claims = _load_claims_for_version(db, version.id)
    except Exception as exc:
        db.rollback()
        failed_step = ai_run_service.fail_step(
            db,
            step,
            error=str(exc),
            latency_ms=int((perf_counter() - started) * 1000),
        )
        langsmith_observability_service.record_step_span(
            db,
            run=run,
            settings=settings,
            step=failed_step,
            trace=trace,
            span_name="research_memo_generation",
            input_json=step.input_json,
            error=str(exc),
        )
        raise
    completed_step = ai_run_service.complete_step(
        db,
        step,
        output_json={
            "artifact_id": str(artifact.id),
            "artifact_version_id": str(version.id),
            "version": version.version,
            "claim_ids": [str(claim.id) for claim in claims],
            "memory_update_status": "pending_human_approval",
        },
        latency_ms=int((perf_counter() - started) * 1000),
        tokens=None,
        cost=Decimal("0"),
    )
    langsmith_observability_service.record_step_span(
        db,
        settings,
        run=run,
        step=completed_step,
        trace=trace,
        span_name="research_memo_generation",
        input_json=step.input_json,
        output_json=completed_step.output_json,
    )
    return {
        "artifact": artifact,
        "version": version,
        "claims": claims,
        "citations": memo.citations,
        "unsupported_claims": memo.unsupported_claims,
        "final_step": completed_step,
    }


def _get_or_create_research_memo_artifact(
    db: Session,
    auth: AuthContext,
    project: Project,
) -> Artifact:
    artifact = db.scalar(
        select(Artifact).where(
            Artifact.workspace_id == auth.workspace_id,
            Artifact.project_id == project.id,
            Artifact.artifact_type == "research_memo",
        )
    )
    if artifact is not None:
        return artifact
    artifact = Artifact(
        workspace_id=auth.workspace_id,
        project_id=project.id,
        artifact_type="research_memo",
        title=f"{project.name} Research Memo",
        created_by=auth.user_id,
    )
    db.add(artifact)
    db.flush()
    return artifact


def _next_artifact_version(db: Session, artifact_id: uuid.UUID) -> int:
    current_max = db.scalar(
        select(func.max(ArtifactVersion.version)).where(ArtifactVersion.artifact_id == artifact_id)
    )
    return int(current_max or 0) + 1


def _load_artifact(
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
        .options(
            selectinload(Artifact.versions)
            .selectinload(ArtifactVersion.claims)
            .selectinload(Claim.evidence_links)
        )
    )
    if artifact is None:
        raise AgenticResearchWorkflowError("Research memo artifact was not created.")
    return artifact


def _research_memo_for_sprint(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> Artifact:
    artifact = db.scalar(
        select(Artifact)
        .join(ArtifactVersion, ArtifactVersion.artifact_id == Artifact.id)
        .where(
            Artifact.workspace_id == auth.workspace_id,
            Artifact.project_id == project_id,
            Artifact.artifact_type == "research_memo",
            Artifact.current_version_id == ArtifactVersion.id,
            ArtifactVersion.structured_content["research_sprint_id"].as_string() == str(sprint_id),
        )
        .options(
            selectinload(Artifact.versions)
            .selectinload(ArtifactVersion.claims)
            .selectinload(Claim.evidence_links)
        )
    )
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research memo for this sprint was not found.",
        )
    return artifact


def _current_artifact_version(db: Session, artifact: Artifact) -> ArtifactVersion:
    if artifact.current_version_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Research memo has no current version.",
        )
    return _load_version(db, artifact.current_version_id)


def _memo_ai_run(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    version: ArtifactVersion,
) -> AIRun:
    if version.generated_by_ai_run_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Research memo is not linked to an AI run.",
        )
    run = db.scalar(
        select(AIRun).where(
            AIRun.id == version.generated_by_ai_run_id,
            AIRun.workspace_id == auth.workspace_id,
            AIRun.project_id == project_id,
        )
    )
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Research memo AI run was not found.",
        )
    if run.status != "waiting_for_human":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Research memo has already been reviewed.",
        )
    return run


def _load_version(db: Session, version_id: uuid.UUID) -> ArtifactVersion:
    version = db.scalar(
        select(ArtifactVersion)
        .where(ArtifactVersion.id == version_id)
        .options(selectinload(ArtifactVersion.claims).selectinload(Claim.evidence_links))
    )
    if version is None:
        raise AgenticResearchWorkflowError("Research memo version was not created.")
    return version


def _write_claims(
    db: Session,
    auth: AuthContext,
    project: Project,
    version: ArtifactVersion,
    drafts: list[ClaimDraft],
) -> list[Claim]:
    claims: list[Claim] = []
    for draft in drafts:
        claim = Claim(
            workspace_id=auth.workspace_id,
            project_id=project.id,
            artifact_version_id=version.id,
            text=draft.text.strip(),
            claim_type=_optional_truncate(draft.claim_type, 80),
            confidence_score=_decimal_score(draft.confidence_score),
            support_level=draft.support_level,
        )
        db.add(claim)
        db.flush()
        for citation in draft.citations:
            db.add(
                ClaimEvidenceLink(
                    claim_id=claim.id,
                    evidence_source_id=citation.source_id,
                    evidence_chunk_id=citation.chunk_id,
                    relevance_score=_decimal_score(citation.relevance_score),
                    quote=citation.quote,
                )
            )
        claims.append(claim)
    return claims


def _load_claims_for_version(db: Session, version_id: uuid.UUID) -> list[Claim]:
    return list(
        db.scalars(
            select(Claim)
            .where(Claim.artifact_version_id == version_id)
            .options(selectinload(Claim.evidence_links))
            .order_by(Claim.created_at)
        )
    )


_render_markdown_memo = memo_rendering.render_markdown_memo


def _fallback_memo(
    project_context: dict[str, Any],
    subquestions: list[str],
    selected_evidence: list[EvidenceRetrievalResultRead],
    gaps: list[str],
) -> AgenticResearchMemoDraft:
    project = project_context.get("project") or {}
    project_name = str(project.get("name") or "This idea")
    target_users = project.get("customer_segments") or []
    target = str(target_users[0]) if target_users else "the first target customer segment"
    citations = _fallback_citations(selected_evidence)
    findings = [
        ResearchFindingDraft(
            subquestion=question,
            finding=(
                "Available project evidence provides a partial answer, but the strongest "
                "next step is still direct validation with the target user."
            ),
            evidence_strength="medium" if citations else "weak",
            citations=citations[:2],
        )
        for question in subquestions[:4]
    ]
    claims = [
        ClaimDraft(
            text=(
                f"{project_name} has enough project context to run a bounded research "
                "memo, but confidence depends on the quality of ingested evidence."
            ),
            claim_type="research_summary",
            confidence_score=0.55,
            support_level="inference",
            citations=[],
        )
    ]
    if citations:
        claims.append(
            ClaimDraft(
                text="The research sprint retrieved project-scoped evidence for synthesis.",
                claim_type="retrieval",
                confidence_score=0.7,
                support_level="supported",
                citations=citations[:1],
            )
        )
    unsupported = list(gaps) or ["Validated willingness-to-pay evidence remains limited."]
    riskiest_assumptions = [
        ResearchAssumptionDraft(
            text=(f"{target} has urgent, repeated pain and will make time for a new workflow."),
            category="demand",
            importance="critical",
            uncertainty="high",
            kill_risk=True,
            confidence_score=0.35 if citations else 0.25,
            recommended_test=(
                f"Interview five {target} users about recent examples, current "
                "workarounds, and switching triggers."
            ),
            evidence_strength="medium" if citations else "weak",
            citations=citations[:2],
        ),
        ResearchAssumptionDraft(
            text="The willingness-to-pay signal is strong enough to justify building.",
            category="business_model",
            importance="critical",
            uncertainty="high",
            kill_risk=True,
            confidence_score=0.25,
            recommended_test=(
                "Use pricing-sensitivity questions and a pilot signup ask during discovery."
            ),
            evidence_strength="weak",
            citations=citations[:1],
        ),
    ]
    key_risks = [
        ResearchRiskDraft(
            text="The research evidence may show workflow pain but not budget or urgency.",
            category="demand",
            severity="high",
            likelihood="high" if not citations else "medium",
            mitigation=(
                "Prioritize willingness-to-pay and urgency questions in the first validation pass."
            ),
            citations=citations[:2],
        ),
        ResearchRiskDraft(
            text=(
                "Existing tools or manual workflows may already be good enough for the "
                "narrow wedge."
            ),
            category="competition",
            severity="high",
            likelihood="unknown",
            mitigation=(
                "Ask users to compare the concept against their current workaround and named tools."
            ),
            citations=citations[:2],
        ),
    ]
    return AgenticResearchMemoDraft(
        executive_verdict=(
            f"Continue researching {project_name}, but keep the validation focus narrow: "
            f"prove that {target} has urgent, repeated pain before expanding scope."
        ),
        best_wedge=(
            "The best current wedge is the narrowest workflow where evidence shows repeated "
            "pain, visible current workarounds, and an obvious reason to switch."
        ),
        market_landscape=(
            "The market should be evaluated around the specific repeated workflow rather than "
            "the broad category. The available evidence is enough to define initial questions, "
            "but not enough to make a confident market-size claim."
        ),
        customer_pain_signals=(
            "The strongest pain signal is time spent stitching together scattered inputs before "
            "making a decision. Direct customer evidence is still needed."
        ),
        competitor_landscape=(
            "Approved competitors and substitutes should be treated as positioning pressure, "
            "especially where they already own the customer workflow."
        ),
        substitute_behaviors=(
            "Manual notes, spreadsheets, generic AI prompts, and lightweight current tools are "
            "the default substitutes to test against."
        ),
        pricing_business_model_signals=(
            "Pricing evidence is weak. The next validation step should test whether the target "
            "user has enough urgency and budget to pay."
        ),
        findings=findings,
        key_risks=key_risks,
        riskiest_assumptions=riskiest_assumptions,
        evidence_summary=(
            f"The sprint selected {len(selected_evidence)} evidence chunks and identified "
            f"{len(unsupported)} weak or unsupported areas."
        ),
        evidence_gaps=unsupported[:8],
        what_we_still_do_not_know=unsupported[:8],
        recommended_validation_actions=[
            f"Interview five {target} users about their current workaround.",
            "Ask for recent examples, time spent, current alternatives, and switching triggers.",
            "Test willingness to pay before building deeper automation.",
        ],
        decision_recommendation=(
            "Do not commit to a broad build yet. Run validation against the riskiest "
            "assumption and update project memory after human review."
        ),
        comparison_to_mvp_brief=(
            "Compared with a static opportunity brief, this research memo emphasizes current "
            "evidence gaps, competitor pressure, and the next validation action."
        ),
        claims=claims,
        citations=citations,
        unsupported_claims=unsupported[:8],
    )


def _fallback_completion(
    settings: Settings,
    messages: list[ChatMessage],
    memo: AgenticResearchMemoDraft,
    fallback_name: str,
    error: BaseException | None = None,
) -> LLMCompletion:
    return fallback_completion(
        settings,
        messages,
        memo,
        fallback_name,
        error,
        fallback_prefix="agentic_research",
        use_stub_provider=True,
    )


_audit_citations = citation_audit.audit_citations


_citation_is_valid = citation_verifier_service.citation_has_retrieved_id


def _fallback_citations(results: list[EvidenceRetrievalResultRead]) -> list[Citation]:
    citations: list[Citation] = []
    for result in results[:5]:
        citations.append(
            citation_verifier_service.citation_from_evidence(result).model_copy(
                update={"retrieved_at": datetime.now(UTC)}
            )
        )
    return _dedupe_citations(citations)


_dedupe_citations = citation_verifier_service.dedupe_citations


def _evidence_bundles(results: list[EvidenceRetrievalResultRead]) -> list[dict[str, Any]]:
    return memo_rendering.evidence_bundles(results, text_limit=EVIDENCE_TEXT_LIMIT)


_memory_update_preview = memo_rendering.memory_update_preview
_research_memo_proposal_payloads = research_proposals.research_memo_proposal_payloads


def _recommendation_shift(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    proposed_recommendation: str,
    selected_evidence: list[EvidenceRetrievalResultRead],
):
    latest_decision = db.scalar(
        select(Decision)
        .where(
            Decision.workspace_id == auth.workspace_id,
            Decision.project_id == project_id,
        )
        .order_by(Decision.created_at.desc())
        .limit(1)
    )
    selected_source_ids = {result.source_id for result in selected_evidence}
    newly_added_source_ids: set[object] = set()
    if latest_decision is not None and selected_source_ids:
        newly_added_source_ids = set(
            db.scalars(
                select(EvidenceSource.id).where(
                    EvidenceSource.workspace_id == auth.workspace_id,
                    EvidenceSource.project_id == project_id,
                    EvidenceSource.id.in_(selected_source_ids),
                    EvidenceSource.created_at > latest_decision.created_at,
                )
            )
        )
    return source_provenance_service.assess_recommendation_shift(
        previous_recommendation=latest_decision.decision_type if latest_decision else None,
        proposed_recommendation=proposed_recommendation,
        selected_source_ids=selected_source_ids,
        newly_added_source_ids=newly_added_source_ids,
    )


def _single_source_claim_conflict(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    proposed_claims: list[ClaimDraft],
    selected_evidence: list[EvidenceRetrievalResultRead],
):
    existing_claims = list(
        db.scalars(
            select(Claim)
            .join(ClaimEvidenceLink, ClaimEvidenceLink.claim_id == Claim.id)
            .where(
                Claim.workspace_id == auth.workspace_id,
                Claim.project_id == project_id,
                Claim.support_level.in_(("supported", "partial")),
            )
            .distinct()
            .order_by(Claim.created_at.desc())
        )
    )
    if not existing_claims:
        return source_provenance_service.ClaimConflict(
            detected=False,
            proposed_claim=None,
            existing_claim=None,
            controlling_source_ids=(),
        )

    selected_source_ids = {result.source_id for result in selected_evidence}
    proposed_claim_sources = [
        (draft.text, {citation.source_id for citation in draft.citations})
        for draft in proposed_claims
    ]
    cited_source_ids = {
        source_id
        for _, source_ids in proposed_claim_sources
        for source_id in source_ids
        if source_id in selected_source_ids
    }
    newest_existing_claim = max(claim.created_at for claim in existing_claims)
    newly_added_source_ids = set(
        db.scalars(
            select(EvidenceSource.id).where(
                EvidenceSource.workspace_id == auth.workspace_id,
                EvidenceSource.project_id == project_id,
                EvidenceSource.id.in_(cited_source_ids),
                EvidenceSource.created_at > newest_existing_claim,
                EvidenceSource.ingestion_status == "ready",
            )
        )
    )
    return source_provenance_service.assess_single_source_claim_conflict(
        proposed_claims=proposed_claim_sources,
        existing_claims=[claim.text for claim in existing_claims],
        newly_added_source_ids=newly_added_source_ids,
    )


def _suppress_conflicting_claim(
    memo: AgenticResearchMemoDraft,
    claim_conflict: source_provenance_service.ClaimConflict,
) -> AgenticResearchMemoDraft:
    controlling_source_ids = {
        uuid.UUID(source_id) for source_id in claim_conflict.controlling_source_ids
    }
    claims = [
        claim.model_copy(update={"support_level": "unsupported", "citations": []})
        if claim.text == claim_conflict.proposed_claim
        and {citation.source_id for citation in claim.citations} == controlling_source_ids
        else claim
        for claim in memo.claims
    ]
    unsupported_claims = list(
        dict.fromkeys([*memo.unsupported_claims, claim_conflict.proposed_claim])
    )
    return memo.model_copy(update={"claims": claims, "unsupported_claims": unsupported_claims[:12]})


def _replace_recommendation_shift_proposals(proposal_payloads, recommendation_shift):
    abstention = (
        "Do not change the decision from this source alone. Collect independent "
        "corroborating evidence before making a recommendation."
    )
    shift_metadata = {
        "previous_recommendation": recommendation_shift.previous_recommendation,
        "proposed_recommendation": recommendation_shift.proposed_recommendation,
        "controlling_source_ids": list(recommendation_shift.controlling_source_ids),
        "requires_independent_corroboration": True,
    }
    return research_proposals.ResearchMemoProposalPayloads(
        memory_update={
            **proposal_payloads.memory_update,
            "decision_recommendation": abstention,
            "recommendation_shift": shift_metadata,
        },
        validation_plan=proposal_payloads.validation_plan,
        decision={
            **proposal_payloads.decision,
            "decision_recommendation": abstention,
            "recommendation_shift": shift_metadata,
        },
        memory_update_input=proposal_payloads.memory_update_input,
        validation_plan_input=proposal_payloads.validation_plan_input,
        decision_input=proposal_payloads.decision_input,
    )


def _replace_conflicting_claim_proposals(proposal_payloads, claim_conflict):
    abstention = (
        "Do not make a decision from a claim introduced by one source that conflicts "
        "with existing evidence. Collect independent corroboration first."
    )
    conflict_metadata = {
        "proposed_claim": claim_conflict.proposed_claim,
        "existing_claim": claim_conflict.existing_claim,
        "controlling_source_ids": list(claim_conflict.controlling_source_ids),
        "requires_independent_corroboration": True,
    }
    return research_proposals.ResearchMemoProposalPayloads(
        memory_update={
            **proposal_payloads.memory_update,
            "decision_recommendation": abstention,
            "conflicting_claim": conflict_metadata,
        },
        validation_plan=proposal_payloads.validation_plan,
        decision={
            **proposal_payloads.decision,
            "decision_recommendation": abstention,
            "conflicting_claim": conflict_metadata,
        },
        memory_update_input=proposal_payloads.memory_update_input,
        validation_plan_input=proposal_payloads.validation_plan_input,
        decision_input=proposal_payloads.decision_input,
    )


def _research_sources(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> list[DiscoveredSource]:
    return list(
        db.scalars(
            select(DiscoveredSource)
            .where(
                DiscoveredSource.workspace_id == auth.workspace_id,
                DiscoveredSource.project_id == project_id,
                DiscoveredSource.research_sprint_id == sprint_id,
            )
            .order_by(DiscoveredSource.relevance_score.desc())
        )
    )


def _project_competitors(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> list[Competitor]:
    return list(
        db.scalars(
            select(Competitor)
            .where(
                Competitor.workspace_id == auth.workspace_id,
                Competitor.project_id == project_id,
            )
            .order_by(Competitor.created_at.desc())
            .limit(12)
        )
    )


def _competitor_candidates(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
) -> list[CompetitorCandidate]:
    return list(
        db.scalars(
            select(CompetitorCandidate)
            .where(
                CompetitorCandidate.workspace_id == auth.workspace_id,
                CompetitorCandidate.project_id == project_id,
                CompetitorCandidate.research_sprint_id == sprint_id,
            )
            .order_by(CompetitorCandidate.relevance_score.desc())
            .limit(12)
        )
    )


def _project_artifacts(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> list[Artifact]:
    return list(
        db.scalars(
            select(Artifact)
            .where(Artifact.workspace_id == auth.workspace_id, Artifact.project_id == project_id)
            .order_by(Artifact.updated_at.desc())
            .limit(8)
        )
    )


def _project_assumptions(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> list[Assumption]:
    return list(
        db.scalars(
            select(Assumption)
            .where(
                Assumption.workspace_id == auth.workspace_id,
                Assumption.project_id == project_id,
            )
            .order_by(Assumption.kill_risk.desc(), Assumption.created_at)
            .limit(12)
        )
    )


_to_jsonable = graph_state.to_jsonable
_json_safe = graph_state.json_safe


def _decimal_score(value: float | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(round(value, 4)))


def _optional_truncate(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped[:max_length] or None


_clean_list = research_strategy.clean_list
_term_set = research_strategy.term_set


def _normalize_key(value: str) -> str:
    return " ".join(value.casefold().split())
