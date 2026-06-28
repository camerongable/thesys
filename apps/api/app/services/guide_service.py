"""Ask Thesys guide service.

The guide is a bounded project copilot: it can retrieve evidence, explain the
next action, and create approval-gated proposals, but it does not silently
mutate strategic project state from chat.
"""

import json
import uuid
from collections.abc import Generator, Iterator
from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.litellm_client import ChatMessage, LiteLLMClient
from app.ai.prompts import GUIDE_CHAT_PROMPT_VERSION, UNTRUSTED_RETRIEVED_CONTENT_RULE
from app.ai.structured_output import generate_structured_output
from app.core.auth import AuthContext
from app.core.config import Settings, get_settings
from app.db.models import ApprovalRequest, Artifact, Experiment, ResearchSprint, ValidationMission
from app.schemas.guide import (
    GuideActionRead,
    GuideChatResponseRead,
    GuideChatTurnRead,
    GuideCitationDetailRead,
    GuideContextRead,
    GuideEvidenceSummaryRead,
    GuideRelatedEntityRead,
    GuideResponseRead,
)
from app.schemas.overview import NextBestActionRead, ProjectOverviewRead
from app.schemas.validation import DecisionCoachActionRead
from app.services import (
    ai_run_service,
    context_service,
    memory_service,
    project_overview_service,
    thesis_service,
    tool_service,
    validation_service,
    wedge_service,
)


class GuideActionNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class _StageGuideCopy:
    focus: str
    why: str
    summary: str


class _GroundedGuideAnswerDraft(BaseModel):
    answer: str
    cited_evidence_ids: list[str] = Field(default_factory=list)
    assumption_ids: list[str] = Field(default_factory=list)
    confidence_level: Literal["unknown", "low", "medium", "high"] = "unknown"
    unsupported_or_missing_evidence: list[str] = Field(default_factory=list)
    suggested_action_ids: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class _GuideEvidenceSearch:
    output: dict
    cited_evidence_ids: list[str]
    retrieval_diagnostics: dict | None
    context_pack: dict | None = None


_STAGE_GUIDE_COPY: dict[str, _StageGuideCopy] = {
    "draft_idea": _StageGuideCopy(
        focus="Shape the rough idea into a testable thesis.",
        why=(
            "The project does not yet have enough customer, problem, and proof context "
            "to make a strategic recommendation."
        ),
        summary=(
            "This idea is still rough. Start by clarifying who it is for and what must be true."
        ),
    ),
    "structured_intake": _StageGuideCopy(
        focus="Run the first research pass.",
        why=(
            "The thesis has structure, but it still needs evidence, substitutes, and "
            "competitor pressure before validation can be trusted."
        ),
        summary="The idea has a first shape. The next move is to ground it in research.",
    ),
    "brief_generated": _StageGuideCopy(
        focus="Pressure-test the thesis against competitors and substitutes.",
        why=(
            "A brief exists, but the wedge is not credible until the user understands "
            "what direct competitors, substitutes, and manual alternatives already solve."
        ),
        summary="Research exists. Now compare the opportunity against the market.",
    ),
    "competitors_analyzed": _StageGuideCopy(
        focus="Find the biggest unknown.",
        why=(
            "Competitor context is available. The leverage point is identifying the "
            "belief that could kill the idea before spending more time building."
        ),
        summary="The market has been mapped. Turn it into a clear validation blocker.",
    ),
    "assumptions_identified": _StageGuideCopy(
        focus="Turn the biggest unknown into a test.",
        why=(
            "Ranked assumptions are only useful when the riskiest one becomes a concrete "
            "validation plan with success and failure criteria."
        ),
        summary="The blocker is visible. Create the first proof to reduce uncertainty.",
    ),
    "validation_plan_created": _StageGuideCopy(
        focus="Run the blocker test.",
        why=(
            "A validation plan exists, but confidence should only change after real user "
            "evidence is logged."
        ),
        summary="The proof is planned. Run it and capture what happened.",
    ),
    "experiment_running": _StageGuideCopy(
        focus="Log real validation evidence.",
        why=(
            "The project is in validation. The next useful state change comes from "
            "recording outcomes, objections, and willingness-to-pay signals."
        ),
        summary="Validation is underway. Capture results before deciding.",
    ),
    "decision_ready": _StageGuideCopy(
        focus="Interpret the proof and record the decision.",
        why=(
            "Validation results exist. The app should help turn those results into a "
            "proceed, pivot, pause, kill, or continue-research decision."
        ),
        summary="There is enough signal to review the decision path.",
    ),
    "paused": _StageGuideCopy(
        focus="Decide whether this idea deserves another proof.",
        why="Paused ideas should stay parked unless there is a specific new learning goal.",
        summary="This idea is paused. Reopen it only around a concrete next proof.",
    ),
    "killed": _StageGuideCopy(
        focus="Preserve the learning trail.",
        why="Killed ideas are still useful when the evidence and rationale stay easy to revisit.",
        summary="This idea is closed unless new evidence changes the thesis.",
    ),
    "proceeding": _StageGuideCopy(
        focus="Set the next milestone from the validated wedge.",
        why=(
            "A proceed-style decision should stay tied to the evidence that justified it "
            "and the next proof that could change the plan."
        ),
        summary="A decision has been recorded. Use it to define the next milestone.",
    ),
}


def get_guide_context(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> GuideContextRead:
    """Build the project state snapshot used by guide recommendations and chat."""
    overview = project_overview_service.get_project_overview(db, auth, project_id)
    return _guide_context_from_overview(db, auth, overview)


def recommend(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> GuideResponseRead:
    """Return deterministic next-action guidance for the current project stage."""
    context = get_guide_context(db, auth, project_id)
    stage_copy = _STAGE_GUIDE_COPY.get(context.stage, _fallback_stage_copy(context.stage))
    recommended_action = context.available_actions[0]
    return GuideResponseRead(
        summary=stage_copy.summary,
        current_focus=stage_copy.focus,
        why_this_matters=stage_copy.why,
        after_that=_after_that_for_action(context, recommended_action),
        recommended_action=recommended_action,
        secondary_actions=context.available_actions[1:4],
        suggested_questions=_suggested_questions(context),
    )


def execute_action(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    action_id: str,
) -> GuideActionRead:
    context = get_guide_context(db, auth, project_id)
    for action in context.available_actions:
        if action.id == action_id:
            return action
    canonical_action_id = _canonical_action_id(action_id)
    for action in context.available_actions:
        if action.id == canonical_action_id:
            return action
    raise GuideActionNotFoundError(action_id)


def chat(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    message: str,
    recent_turns: list[GuideChatTurnRead] | None = None,
) -> GuideChatResponseRead:
    """Answer a bounded project question with retrieval grounding when needed."""
    settings = get_settings()
    context = get_guide_context(db, auth, project_id)
    normalized = message.strip().lower()
    bounded_recent_turns = _bounded_recent_turns(recent_turns or [])
    run = ai_run_service.start_run(
        db,
        auth,
        workflow_type="guide_chat",
        prompt_version=GUIDE_CHAT_PROMPT_VERSION,
        input_summary=message[:500],
        project_id=project_id,
        model_provider="stub" if settings.should_use_llm_stub else "litellm",
        model_name=settings.litellm_model,
    )
    total_tokens: int | None = None
    total_cost: Decimal | None = Decimal("0")
    model_provider = "stub" if settings.should_use_llm_stub else "litellm"
    model_name = settings.litellm_model

    try:
        intent_step = ai_run_service.start_step(
            db,
            run,
            step_name="guide_intent_guardrail",
            input_json={
                "message": message[:1000],
                "stage": context.stage,
                "recent_turn_count": len(bounded_recent_turns),
            },
        )
        in_scope = _is_in_scope(normalized)
        ai_run_service.complete_step(
            db,
            intent_step,
            output_json={
                "in_scope": in_scope,
                "used_llm": not settings.should_use_llm_stub and in_scope,
            },
            latency_ms=0,
            tokens=None,
            cost=Decimal("0"),
        )

        # State-changing guide intents are routed to proposal tools. The chat
        # response can surface an approval request, but it cannot write memory,
        # validation plans, or decisions directly.
        proposal_tool = _proposal_tool_for_message(normalized)
        if not in_scope:
            response = _out_of_scope_chat_response(context)
        elif proposal_tool is not None:
            response = _proposal_chat_response(
                db,
                auth,
                project_id,
                message,
                context,
                proposal_tool,
            )
        elif settings.should_use_llm_stub:
            response = _deterministic_chat_response(db, auth, project_id, message, context)
            response = _attach_grounding_metadata(
                db,
                auth,
                settings,
                project_id,
                run,
                message,
                response,
                context,
                used_llm=False,
            )
        else:
            (
                response,
                total_tokens,
                total_cost,
                model_provider,
                model_name,
            ) = _grounded_chat_response(
                db,
                auth,
                settings,
                project_id,
                message,
                context,
                run,
                bounded_recent_turns,
            )

        response.ai_run_id = run.id
        ai_run_service.complete_run(
            db,
            run,
            output_summary=response.answer[:500],
            total_tokens=total_tokens,
            total_cost=total_cost,
            model_provider=model_provider,
            model_name=model_name,
        )
        return response
    except Exception as exc:
        ai_run_service.fail_run(db, run, error=str(exc))
        raise


def stream_chat_events(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    message: str,
    recent_turns: list[GuideChatTurnRead] | None = None,
    *,
    timeout_seconds: float | None = None,
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield Ask Thesys SSE events while preserving the normal guide contract."""
    settings = get_settings()
    context = get_guide_context(db, auth, project_id)
    normalized = message.strip().lower()
    bounded_recent_turns = _bounded_recent_turns(recent_turns or [])
    model_provider = "stub" if settings.should_use_llm_stub else "litellm"
    model_name = settings.litellm_model
    timeout = (
        timeout_seconds
        if timeout_seconds is not None
        else settings.guide_chat_stream_timeout_seconds
    )
    started_at = perf_counter()
    run = ai_run_service.start_run(
        db,
        auth,
        workflow_type="guide_chat",
        prompt_version=GUIDE_CHAT_PROMPT_VERSION,
        input_summary=message[:500],
        project_id=project_id,
        model_provider=model_provider,
        model_name=model_name,
    )
    total_tokens: int | None = None
    total_cost: Decimal | None = Decimal("0")
    answer_streamed = False

    try:
        yield (
            "message_started",
            {
                "ai_run_id": str(run.id),
                "project_id": str(project_id),
                "stage": context.stage,
                "model_provider": model_provider,
                "model_name": model_name,
            },
        )
        if _stream_timed_out(started_at, timeout):
            yield from _timeout_stream_events(db, run, context, timeout)
            return

        intent_step = ai_run_service.start_step(
            db,
            run,
            step_name="guide_intent_guardrail",
            input_json={
                "message": message[:1000],
                "stage": context.stage,
                "recent_turn_count": len(bounded_recent_turns),
                "streaming": True,
            },
        )
        in_scope = _is_in_scope(normalized)
        ai_run_service.complete_step(
            db,
            intent_step,
            output_json={
                "in_scope": in_scope,
                "used_llm": not settings.should_use_llm_stub and in_scope,
            },
            latency_ms=0,
            tokens=None,
            cost=Decimal("0"),
        )
        yield (
            "metadata",
            {
                "phase": "intent_guardrail",
                "in_scope": in_scope,
                "recent_turn_count": len(bounded_recent_turns),
            },
        )
        if _stream_timed_out(started_at, timeout):
            yield from _timeout_stream_events(db, run, context, timeout)
            return

        proposal_tool = _proposal_tool_for_message(normalized)
        if not in_scope:
            response = _out_of_scope_chat_response(context)
        elif proposal_tool is not None:
            yield (
                "tool_call_started",
                {
                    "tool_name": proposal_tool,
                    "access_mode": "proposal",
                    "risk_level": "medium",
                },
            )
            response = _proposal_chat_response(
                db,
                auth,
                project_id,
                message,
                context,
                proposal_tool,
            )
            yield (
                "proposal_created",
                {
                    "tool_name": proposal_tool,
                    "tool_invocation_id": str(response.proposal_invocation_id)
                    if response.proposal_invocation_id
                    else None,
                    "approval_request_id": str(response.approval_request_id)
                    if response.approval_request_id
                    else None,
                },
            )
            yield (
                "tool_call_completed",
                {
                    "tool_name": proposal_tool,
                    "status": "proposal_created",
                    "tool_invocation_id": str(response.proposal_invocation_id)
                    if response.proposal_invocation_id
                    else None,
                },
            )
        elif settings.should_use_llm_stub:
            response = _deterministic_chat_response(db, auth, project_id, message, context)
            yield from _retrieval_started_events(message)
            response = _attach_grounding_metadata(
                db,
                auth,
                settings,
                project_id,
                run,
                message,
                response,
                context,
                used_llm=False,
            )
            yield from _retrieval_completed_events(response)
        else:
            (
                response,
                total_tokens,
                total_cost,
                model_provider,
                model_name,
                answer_streamed,
            ) = yield from _stream_grounded_chat_response(
                db,
                auth,
                settings,
                project_id,
                message,
                context,
                run,
                bounded_recent_turns,
            )

        response.ai_run_id = run.id
        if _stream_timed_out(started_at, timeout):
            yield from _timeout_stream_events(db, run, context, timeout)
            return

        if not answer_streamed:
            for index, chunk in enumerate(_answer_delta_chunks(response.answer)):
                yield ("answer_delta", {"index": index, "text": chunk})

        ai_run_service.complete_run(
            db,
            run,
            output_summary=response.answer[:500],
            total_tokens=total_tokens,
            total_cost=total_cost,
            model_provider=model_provider,
            model_name=model_name,
        )
        yield ("metadata", _final_stream_metadata(response))
        yield ("final", response.model_dump(mode="json"))
    except GeneratorExit:
        if getattr(run, "status", None) == "running":
            ai_run_service.cancel_run(db, run, output_summary="Guide stream cancelled by client.")
        raise
    except Exception as exc:
        ai_run_service.fail_run(db, run, error=str(exc))
        yield (
            "error",
            {
                "ai_run_id": str(run.id),
                "message": "Ask Thesys could not finish the streamed answer.",
            },
        )


def _stream_timed_out(started_at: float, timeout_seconds: float) -> bool:
    return perf_counter() - started_at >= timeout_seconds


def _timeout_stream_events(
    db: Session,
    run,
    context: GuideContextRead,
    timeout_seconds: float,
) -> Iterator[tuple[str, dict[str, Any]]]:
    response = _timeout_chat_response(context, run.id, timeout_seconds)
    ai_run_service.fail_run(
        db,
        run,
        error=f"Guide stream timed out after {timeout_seconds:.1f} seconds.",
    )
    yield (
        "timeout",
        {
            "ai_run_id": str(run.id),
            "timeout_seconds": timeout_seconds,
            "message": "Ask Thesys timed out before it could safely finish.",
        },
    )
    for index, chunk in enumerate(_answer_delta_chunks(response.answer)):
        yield ("answer_delta", {"index": index, "text": chunk})
    yield ("metadata", _final_stream_metadata(response))
    yield ("final", response.model_dump(mode="json"))


def _timeout_chat_response(
    context: GuideContextRead,
    run_id: uuid.UUID,
    timeout_seconds: float,
) -> GuideChatResponseRead:
    return GuideChatResponseRead(
        answer=(
            "Ask Thesys took too long to finish. No project state was changed. "
            "Try a narrower question or use the recommended next action."
        ),
        recommended_action=context.available_actions[0] if context.available_actions else None,
        action_cards=context.available_actions[:3],
        related_entities=_related_entities(context),
        confidence_level="unknown",
        unsupported_or_missing_evidence=[
            f"The streamed guide response exceeded the {timeout_seconds:.1f}s timeout."
        ],
        ai_run_id=run_id,
    )


def _retrieval_started_events(message: str) -> Iterator[tuple[str, dict[str, Any]]]:
    payload = {"query": message[:500], "mode": "hybrid", "top_k": 5}
    yield ("retrieval_started", payload)
    yield (
        "tool_call_started",
        {
            "tool_name": "search_project_evidence",
            "access_mode": "read",
            "risk_level": "low",
            "input": payload,
        },
    )


def _retrieval_completed_events(
    response: GuideChatResponseRead,
) -> Iterator[tuple[str, dict[str, Any]]]:
    diagnostics = response.retrieval_diagnostics or {}
    result_count = _retrieval_result_count(response)
    yield (
        "tool_call_completed",
        {
            "tool_name": "search_project_evidence",
            "status": "succeeded",
            "result_count": result_count,
            "cited_evidence_ids": response.cited_evidence_ids,
        },
    )
    yield (
        "retrieval_result",
        {
            "result_count": result_count,
            "cited_evidence_ids": response.cited_evidence_ids,
            "citation_details": [
                detail.model_dump(mode="json") for detail in response.citation_details
            ],
            "diagnostics": diagnostics,
        },
    )
    if response.context_pack:
        yield (
            "context_compiled",
            {
                "context_pack_id": response.context_pack.get("id"),
                "workflow_type": response.context_pack.get("workflow_type"),
                "item_count": len(response.context_pack.get("items") or []),
                "dropped_count": len(response.context_pack.get("dropped_items") or []),
                "available_citation_ids": response.context_pack.get("available_citation_ids")
                or [],
                "selected_memory_ids": (
                    response.context_pack.get("metadata", {}).get("selected_memory_ids", [])
                    if isinstance(response.context_pack.get("metadata"), dict)
                    else []
                ),
            },
        )


def _retrieval_result_count(response: GuideChatResponseRead) -> int:
    diagnostics = response.retrieval_diagnostics or {}
    context_diagnostics = diagnostics.get("context") if isinstance(diagnostics, dict) else None
    if isinstance(context_diagnostics, dict):
        selected_count = context_diagnostics.get("selected_count")
        if isinstance(selected_count, int):
            return selected_count
    return len(response.cited_evidence_ids)


def _answer_delta_chunks(answer: str, *, max_chars: int = 96) -> list[str]:
    words = answer.split()
    if not words:
        return [answer]
    chunks: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current + " ")
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _final_stream_metadata(response: GuideChatResponseRead) -> dict[str, Any]:
    context_pack = response.context_pack or {}
    return {
        "ai_run_id": str(response.ai_run_id) if response.ai_run_id else None,
        "used_llm": response.used_llm,
        "confidence_level": response.confidence_level,
        "cited_evidence_ids": response.cited_evidence_ids,
        "citation_count": len(response.citation_details),
        "proposal_invocation_id": str(response.proposal_invocation_id)
        if response.proposal_invocation_id
        else None,
        "approval_request_id": str(response.approval_request_id)
        if response.approval_request_id
        else None,
        "context_pack_id": context_pack.get("id") if isinstance(context_pack, dict) else None,
    }


def _stream_grounded_chat_response(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    message: str,
    context: GuideContextRead,
    run,
    recent_turns: list[dict[str, str]],
) -> Generator[
    tuple[str, dict[str, Any]],
    None,
    tuple[GuideChatResponseRead, int | None, Decimal | None, str, str, bool],
]:
    yield from _retrieval_started_events(message)
    search = _search_guide_evidence(db, auth, settings, project_id, run, message)
    memory_selection = memory_service.select_memory_for_context(
        db,
        auth,
        project_id,
        workflow_type="guide_chat",
        limit=12,
    )
    context_pack = context_service.build_guide_context_pack(
        settings,
        project_id=project_id,
        message=message,
        guide_context=context,
        evidence_output=search.output,
        recent_turns=recent_turns,
        prompt_version=GUIDE_CHAT_PROMPT_VERSION,
        expected_schema=_GroundedGuideAnswerDraft.__name__,
        memory_selection=memory_selection,
    )
    retrieval_response = GuideChatResponseRead(
        answer="",
        related_entities=_related_entities_with_evidence(context, search.cited_evidence_ids),
        cited_evidence_ids=search.cited_evidence_ids,
        citation_details=_citation_details_from_search(
            search.output,
            context_pack.model_dump(mode="json"),
            search.cited_evidence_ids,
        ),
        confidence_level=_grounded_confidence(context, bool(search.cited_evidence_ids)),
        retrieval_diagnostics=search.retrieval_diagnostics,
        context_pack=context_pack.model_dump(mode="json"),
    )
    yield from _retrieval_completed_events(retrieval_response)

    generation_step = ai_run_service.start_step(
        db,
        run,
        step_name="guide_grounded_answer_generation",
        input_json={
            "message": message[:1000],
            "stage": context.stage,
            "retrieved_source_ids": search.cited_evidence_ids,
            "available_action_ids": [action.id for action in context.available_actions],
            "recent_turn_count": len(recent_turns),
            "context_pack": context_pack.prompt_metadata(),
            "streaming": True,
        },
    )
    started = perf_counter()
    raw_content = ""
    emitted_answer_chars = 0
    delta_index = 0
    answer_streamed = False
    try:
        messages = [
            _schema_instruction_for_stream(_GroundedGuideAnswerDraft),
            *_grounded_guide_messages(message, context_pack),
        ]
        for delta in LiteLLMClient(settings).stream_complete(
            messages,
            temperature=0.1,
            response_format_json=True,
            max_tokens=900,
        ):
            raw_content += delta
            partial_answer = _partial_answer_from_json(raw_content)
            if len(partial_answer) <= emitted_answer_chars:
                continue
            new_text = partial_answer[emitted_answer_chars:]
            emitted_answer_chars = len(partial_answer)
            answer_streamed = True
            yield (
                "answer_delta",
                {"index": delta_index, "text": new_text, "source": "provider"},
            )
            delta_index += 1

        draft = _GroundedGuideAnswerDraft.model_validate_json(raw_content)
        response = _response_from_grounded_draft(context, draft, search, run.id)
        response.context_pack = context_pack.model_dump(mode="json")
        response.citation_details = _citation_details_from_search(
            search.output,
            response.context_pack,
            response.cited_evidence_ids,
        )
        if answer_streamed and emitted_answer_chars < len(response.answer):
            for chunk in _answer_delta_chunks(response.answer[emitted_answer_chars:]):
                yield (
                    "answer_delta",
                    {"index": delta_index, "text": chunk, "source": "validated_final"},
                )
                delta_index += 1
        ai_run_service.complete_step(
            db,
            generation_step,
            output_json=response.model_dump(mode="json"),
            latency_ms=int((perf_counter() - started) * 1000),
            tokens=None,
            cost=None,
        )
        return response, None, None, "litellm", settings.litellm_model, answer_streamed
    except Exception as exc:
        fallback = _deterministic_chat_response(db, auth, project_id, message, context)
        fallback.used_llm = False
        fallback.cited_evidence_ids = search.cited_evidence_ids
        fallback.retrieval_diagnostics = search.retrieval_diagnostics
        fallback.context_pack = context_pack.model_dump(mode="json")
        fallback.citation_details = _citation_details_from_search(
            search.output,
            fallback.context_pack,
            fallback.cited_evidence_ids,
        )
        fallback.confidence_level = _grounded_confidence(
            context,
            bool(search.cited_evidence_ids),
        )
        fallback.related_entities = _related_entities_with_evidence(
            context,
            search.cited_evidence_ids,
        )
        fallback.unsupported_or_missing_evidence = [
            *fallback.unsupported_or_missing_evidence,
            "Provider streaming could not be safely used, so the deterministic guide answered.",
        ][:4]
        ai_run_service.complete_step(
            db,
            generation_step,
            output_json={
                "fallback_used": True,
                "reason": str(exc),
                "response": fallback.model_dump(mode="json"),
            },
            latency_ms=int((perf_counter() - started) * 1000),
            tokens=None,
            cost=Decimal("0"),
        )
        return fallback, None, Decimal("0"), "local-fallback", settings.litellm_model, False


def _schema_instruction_for_stream(output_schema: type[BaseModel]) -> ChatMessage:
    return ChatMessage(
        role="system",
        content=(
            "Return only valid JSON. The JSON must match the required fields exactly and "
            "validate against this JSON Schema: "
            f"{json.dumps(output_schema.model_json_schema(), separators=(',', ':'))}"
        ),
    )


def _partial_answer_from_json(raw_content: str) -> str:
    key_index = raw_content.find('"answer"')
    if key_index < 0:
        return ""
    colon_index = raw_content.find(":", key_index)
    if colon_index < 0:
        return ""
    quote_index = raw_content.find('"', colon_index)
    if quote_index < 0:
        return ""
    chars: list[str] = []
    escaped = False
    for character in raw_content[quote_index + 1 :]:
        if escaped:
            chars.append(_json_escape_character(character))
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character == '"':
            break
        chars.append(character)
    return "".join(chars)


def _json_escape_character(character: str) -> str:
    escapes = {
        '"': '"',
        "\\": "\\",
        "/": "/",
        "b": "\b",
        "f": "\f",
        "n": "\n",
        "r": "\r",
        "t": "\t",
    }
    return escapes.get(character, character)


def _deterministic_chat_response(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    message: str,
    context: GuideContextRead,
) -> GuideChatResponseRead:
    normalized = message.strip().lower()
    if any(
        term in normalized
        for term in (
            "next proof",
            "what proof",
            "proof next",
            "proof should",
            "test next",
        )
    ):
        story = thesis_service.get_idea_story(db, auth, project_id)
        answer = (
            f"The next proof is: {story.next_proof} "
            f"It matters because the current blocker is: {story.current_blocker}"
        )
        return _chat_response(
            answer,
            context,
            [
                _action_by_id(context, "open_validation_mission"),
                _action_by_id(context, "show_idea_story"),
            ],
        )

    if any(
        term in normalized
        for term in (
            "what next",
            "next",
            "do now",
            "should i do",
            "open the right form",
            "right form",
            "open form",
        )
    ):
        action = context.available_actions[0]
        answer = (
            f"Do this next: {action.label}. {action.why_it_matters} "
            f"After that: {_after_that_for_action(context, action)}"
        )
        return _chat_response(answer, context, [action, *_support_actions(context)])

    if any(
        term in normalized
        for term in (
            "research sprint",
            "research plan",
            "plan research",
            "evidence review",
            "propose research",
        )
    ):
        answer = (
            "I can route you to a scoped evidence review plan, but I should not run "
            "or apply broad research directly from chat. Use the research plan action "
            "to define the question, evidence needed, and approval boundary first."
        )
        return _chat_response(
            answer,
            context,
            [
                _action_by_id(context, "plan_research_sprint"),
                _action_by_id(context, "show_blocker_evidence"),
            ],
        )

    if any(term in normalized for term in ("blocked", "blocker", "unknown", "risk", "missing")):
        unknown = context.biggest_unknown or "the strongest untested belief"
        missing_context = _join_list(context.missing_context) or (
            "none of the core context is missing"
        )
        answer = f"The idea is blocked by this: {unknown}. Missing context: {missing_context}."
        return _chat_response(answer, context, _support_actions(context))

    if any(term in normalized for term in ("evidence", "research", "sources", "findings")):
        evidence = context.evidence_summary
        answer = (
            f"The project has {evidence.sources} evidence sources, {evidence.competitors} "
            f"competitors or substitutes, {evidence.supported_findings} supported findings, "
            f"and {evidence.open_questions} open questions."
        )
        return _chat_response(
            answer,
            context,
            [_action_by_id(context, "show_blocker_evidence")],
        )

    if any(
        term in normalized
        for term in (
            "broad",
            "changed",
            "evolved",
            "evolution",
            "reject",
            "rejected",
            "directions",
            "history",
        )
    ):
        story = thesis_service.get_idea_story(db, auth, project_id)
        rejected = _join_list(story.rejected_directions) or "No rejected directions yet."
        answer = (
            f"The idea started as: {story.original_idea} "
            f"The current thesis is: {story.current_thesis} "
            f"Selected wedge: {story.selected_wedge} "
            f"Why it changed: {story.why_it_changed} "
            f"Rejected directions: {rejected}"
        )
        return _chat_response(
            answer,
            context,
            [
                _action_by_id(context, "show_idea_story"),
                _action_by_id(context, "rewrite_thesis_with_wedge"),
            ],
        )

    if any(term in normalized for term in ("thesis", "improve", "sharper", "shape")):
        thesis = context.current_thesis or "No thesis has been structured yet."
        answer = (
            f"Current thesis: {thesis} "
            "A sharper thesis should name one target user, one painful moment, the current "
            "workaround, and the proof that would change the decision."
        )
        return _chat_response(
            answer,
            context,
            [_action_by_id(context, "rewrite_thesis_with_wedge")],
        )

    if any(term in normalized for term in ("wedge", "compare", "alternative", "become")):
        story = thesis_service.get_idea_story(db, auth, project_id)
        wedges = wedge_service.list_wedge_options(db, auth, project_id)
        recommended = next(
            (wedge for wedge in wedges.wedges if str(wedge.id) == str(wedges.recommended_wedge_id)),
            None,
        )
        if recommended:
            rejected = _join_list(story.rejected_directions)
            answer = (
                f"Recommended wedge: {recommended.name}. "
                f"Why it might work: {recommended.why_it_might_work} "
                f"Main risk: {recommended.main_risk} "
                f"First test: {recommended.validation_test} "
                f"{'Avoid for now: ' + rejected if rejected else ''}"
            )
        else:
            answer = (
                f"Current wedge: {story.selected_wedge} "
                "Open Wedge Explorer to compare possible directions before committing "
                "to a validation path."
            )
        return _chat_response(answer, context, [_action_by_id(context, "compare_wedge_options")])

    if any(term in normalized for term in ("outreach", "draft", "interview", "message")):
        target = context.target_user or "the target user"
        unknown = context.biggest_unknown or "the key assumption"
        answer = (
            f"Draft outreach: I am testing whether {target} has a painful enough problem "
            f"around {unknown}. Would you be open to a 20-minute conversation about how "
            "you handle this today?"
        )
        return _chat_response(
            answer,
            context,
            [_action_by_id(context, "draft_validation_outreach")],
        )

    if any(term in normalized for term in ("interpret", "result", "notes", "validate")):
        answer = (
            "Paste validation notes into the current mission, then compare the signal "
            "against the mission's success and failure criteria before changing confidence."
        )
        return _chat_response(
            answer,
            context,
            [_action_by_id(context, "interpret_validation_notes")],
        )

    if any(
        term in normalized for term in ("build", "decision", "proceed", "pivot", "pause", "kill")
    ):
        coach = validation_service.chat_decision_coach(db, auth, project_id, message)
        return GuideChatResponseRead(
            answer=coach.answer,
            recommended_action=_guide_action_from_decision_coach(
                project_id,
                coach.action_cards[0],
            )
            if coach.action_cards
            else context.available_actions[0],
            action_cards=[
                _guide_action_from_decision_coach(project_id, action)
                for action in coach.action_cards
            ],
            related_entities=_related_entities(context),
        )

    stage_copy = _STAGE_GUIDE_COPY.get(context.stage, _fallback_stage_copy(context.stage))
    return _chat_response(stage_copy.summary, context, context.available_actions[:3])


def _out_of_scope_chat_response(context: GuideContextRead) -> GuideChatResponseRead:
    return GuideChatResponseRead(
        answer=(
            "I can help with this idea's thesis, evidence, blockers, validation, "
            "and decisions. Try asking what to validate next or why the current "
            "verdict is blocked."
        ),
        recommended_action=_action_by_id(context, "explain_current_focus"),
        action_cards=[_action_by_id(context, "explain_current_focus")],
        related_entities=_related_entities(context),
        confidence_level=context.confidence_level,
        unsupported_or_missing_evidence=context.missing_context[:3],
    )


def _proposal_chat_response(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
    message: str,
    context: GuideContextRead,
    tool_name: str,
) -> GuideChatResponseRead:
    invocation = tool_service.create_proposal(
        db,
        auth,
        project_id,
        tool_name,
        _proposal_payload(tool_name, message, context),
        requested_by="agent",
        input_json={"source": "ask_thesys", "message": message[:1000]},
    )
    approval = db.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.entity_type == "tool_invocation",
            ApprovalRequest.entity_id == invocation.id,
            ApprovalRequest.status == "pending",
        )
    )
    action = _proposal_action(context, tool_name)
    return GuideChatResponseRead(
        answer=(
            "I created an approval-gated proposal. It will not change project state "
            "unless you approve it in the governance queue."
        ),
        recommended_action=action,
        action_cards=[action, *_support_actions(context)[:2]],
        related_entities=_related_entities(context),
        confidence_level=context.confidence_level,
        proposal_invocation_id=invocation.id,
        approval_request_id=approval.id if approval else None,
    )


def _proposal_tool_for_message(normalized: str) -> str | None:
    if not any(term in normalized for term in ("create", "propose", "draft", "record")):
        return None
    if "research" in normalized and ("plan" in normalized or "sprint" in normalized):
        return "propose_research_plan"
    if "validation" in normalized and ("plan" in normalized or "test" in normalized):
        return "propose_validation_plan"
    if "memory" in normalized or "remember" in normalized:
        return "propose_memory_update"
    if "decision" in normalized or any(
        term in normalized for term in ("proceed", "pivot", "pause", "kill")
    ):
        return "propose_decision"
    return None


def _proposal_payload(
    tool_name: str,
    message: str,
    context: GuideContextRead,
) -> dict[str, object]:
    summary = message[:1000]
    if tool_name == "propose_research_plan":
        return {
            "summary": summary,
            "objective": message[:2000],
            "project_stage": context.stage,
        }
    if tool_name == "propose_validation_plan":
        return {
            "summary": summary,
            "actions": [
                {
                    "type": "validation_plan",
                    "target_assumption": context.biggest_unknown,
                    "suggested_test": context.next_action,
                }
            ],
        }
    if tool_name == "propose_decision":
        return {
            "summary": summary,
            "decision": {
                "requested_from_chat": True,
                "stage": context.stage,
                "verdict": context.verdict,
            },
        }
    return {"summary": summary}


def _proposal_action(context: GuideContextRead, tool_name: str) -> GuideActionRead:
    preferred = {
        "propose_research_plan": "plan_research_sprint",
        "propose_validation_plan": "create_validation_plan",
        "propose_memory_update": "show_project_history",
        "propose_decision": "use_suggested_decision",
    }
    return _action_by_id(context, preferred.get(tool_name, "explain_current_focus"))


def _attach_grounding_metadata(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    run,
    message: str,
    response: GuideChatResponseRead,
    context: GuideContextRead,
    *,
    used_llm: bool,
) -> GuideChatResponseRead:
    search = _search_guide_evidence(db, auth, settings, project_id, run, message)
    memory_selection = memory_service.select_memory_for_context(
        db,
        auth,
        project_id,
        workflow_type="guide_chat",
        limit=12,
    )
    context_pack = context_service.build_guide_context_pack(
        settings,
        project_id=project_id,
        message=message,
        guide_context=context,
        evidence_output=search.output,
        recent_turns=[],
        prompt_version=GUIDE_CHAT_PROMPT_VERSION,
        expected_schema=_GroundedGuideAnswerDraft.__name__,
        memory_selection=memory_selection,
    )
    response.used_llm = used_llm
    response.cited_evidence_ids = search.cited_evidence_ids
    response.retrieval_diagnostics = search.retrieval_diagnostics
    response.context_pack = context_pack.model_dump(mode="json")
    response.citation_details = _citation_details_from_search(
        search.output,
        context_pack.model_dump(mode="json"),
        response.cited_evidence_ids,
    )
    response.confidence_level = _grounded_confidence(context, bool(search.cited_evidence_ids))
    response.related_entities = _related_entities_with_evidence(context, search.cited_evidence_ids)
    if not search.cited_evidence_ids and not response.unsupported_or_missing_evidence:
        response.unsupported_or_missing_evidence = [
            "No project evidence was retrieved for this guide answer."
        ]
    return response


def _grounded_chat_response(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    message: str,
    context: GuideContextRead,
    run,
    recent_turns: list[dict[str, str]],
) -> tuple[GuideChatResponseRead, int | None, Decimal | None, str, str]:
    search = _search_guide_evidence(db, auth, settings, project_id, run, message)
    memory_selection = memory_service.select_memory_for_context(
        db,
        auth,
        project_id,
        workflow_type="guide_chat",
        limit=12,
    )
    context_pack = context_service.build_guide_context_pack(
        settings,
        project_id=project_id,
        message=message,
        guide_context=context,
        evidence_output=search.output,
        recent_turns=recent_turns,
        prompt_version=GUIDE_CHAT_PROMPT_VERSION,
        expected_schema=_GroundedGuideAnswerDraft.__name__,
        memory_selection=memory_selection,
    )
    generation_step = ai_run_service.start_step(
        db,
        run,
        step_name="guide_grounded_answer_generation",
        input_json={
            "message": message[:1000],
            "stage": context.stage,
            "retrieved_source_ids": search.cited_evidence_ids,
            "available_action_ids": [action.id for action in context.available_actions],
            "recent_turn_count": len(recent_turns),
            "context_pack": context_pack.prompt_metadata(),
        },
    )
    started = perf_counter()
    try:
        result = generate_structured_output(
            settings,
            _GroundedGuideAnswerDraft,
            _grounded_guide_messages(message, context_pack),
            temperature=0.1,
            max_tokens=900,
        )
        draft = _GroundedGuideAnswerDraft.model_validate(result.parsed)
        response = _response_from_grounded_draft(context, draft, search, run.id)
        response.context_pack = context_pack.model_dump(mode="json")
        response.citation_details = _citation_details_from_search(
            search.output,
            response.context_pack,
            response.cited_evidence_ids,
        )
        completion = result.completion
        ai_run_service.complete_step(
            db,
            generation_step,
            output_json=response.model_dump(mode="json"),
            latency_ms=int((perf_counter() - started) * 1000),
            tokens=completion.total_tokens,
            cost=completion.total_cost,
        )
        return (
            response,
            completion.total_tokens,
            completion.total_cost,
            completion.model_provider,
            completion.model_name,
        )
    except Exception as exc:
        fallback = _deterministic_chat_response(db, auth, project_id, message, context)
        fallback = _attach_grounding_metadata(
            db,
            auth,
            settings,
            project_id,
            run,
            message,
            fallback,
            context,
            used_llm=False,
        )
        fallback.unsupported_or_missing_evidence = [
            *fallback.unsupported_or_missing_evidence,
            "LLM guide output could not be safely used, so the deterministic guide answered.",
        ][:4]
        fallback.context_pack = context_pack.model_dump(mode="json")
        fallback.citation_details = _citation_details_from_search(
            search.output,
            fallback.context_pack,
            fallback.cited_evidence_ids,
        )
        ai_run_service.complete_step(
            db,
            generation_step,
            output_json={
                "fallback_used": True,
                "reason": str(exc),
                "response": fallback.model_dump(mode="json"),
            },
            latency_ms=int((perf_counter() - started) * 1000),
            tokens=None,
            cost=Decimal("0"),
        )
        return fallback, None, Decimal("0"), "local-fallback", settings.litellm_model


def _search_guide_evidence(
    db: Session,
    auth: AuthContext,
    settings: Settings,
    project_id: uuid.UUID,
    run,
    message: str,
) -> _GuideEvidenceSearch:
    evidence_query = message[:500]
    step = ai_run_service.start_step(
        db,
        run,
        step_name="guide_retrieval_context",
        input_json={"query": evidence_query, "mode": "hybrid", "top_k": 5},
    )
    started = perf_counter()
    try:
        result = tool_service.execute_tool(
            db,
            auth,
            settings,
            project_id,
            "search_project_evidence",
            {"query": evidence_query, "mode": "hybrid", "top_k": 5},
            requested_by="agent",
        )
        output = result.output
        results = output.get("results") if isinstance(output, dict) else []
        cited_evidence_ids = _unique_strings(
            str(item.get("source_id"))
            for item in results
            if isinstance(item, dict) and item.get("source_id")
        )
        diagnostics = output.get("diagnostics") if isinstance(output, dict) else None
        ai_run_service.complete_step(
            db,
            step,
            output_json={
                "result_count": len(results) if isinstance(results, list) else 0,
                "cited_evidence_ids": cited_evidence_ids,
                "diagnostics": diagnostics,
            },
            latency_ms=int((perf_counter() - started) * 1000),
            tokens=None,
            cost=Decimal("0"),
        )
        return _GuideEvidenceSearch(
            output=output if isinstance(output, dict) else {},
            cited_evidence_ids=cited_evidence_ids,
            retrieval_diagnostics=diagnostics if isinstance(diagnostics, dict) else None,
        )
    except Exception as exc:
        ai_run_service.fail_step(
            db,
            step,
            error=str(exc),
            latency_ms=int((perf_counter() - started) * 1000),
        )
        raise


def _grounded_guide_messages(
    message: str,
    context_pack,
) -> list[ChatMessage]:
    trusted_items = [
        item.model_dump(mode="json") for item in context_pack.items if not item.untrusted
    ]
    untrusted_items = [
        item.model_dump(mode="json") for item in context_pack.items if item.untrusted
    ]
    return [
        ChatMessage(
            role="system",
            content=(
                "You are Ask Thesys, a bounded strategic guide for one project. "
                "Answer only about this project's thesis, evidence, wedges, assumptions, "
                "validation, and decisions. "
                f"{UNTRUSTED_RETRIEVED_CONTENT_RULE} "
                "Do not claim to mutate project state. If a user asks for a "
                "change, propose an existing action ID instead. Cite only source IDs from "
                "the retrieved evidence list. Keep the answer concise and practical."
            ),
        ),
        ChatMessage(
            role="user",
            content=(
                "User question:\n"
                f"{message}\n\n"
                "Context pack metadata JSON:\n"
                f"{json.dumps(context_pack.prompt_metadata(), default=str)}\n\n"
                "Trusted context JSON:\n"
                f"{json.dumps(trusted_items, default=str)}\n\n"
                "<untrusted_retrieved_content>\n"
                f"{json.dumps(untrusted_items, default=str)}\n"
                "</untrusted_retrieved_content>"
            ),
        ),
    ]


def _evidence_context_for_prompt(output: dict) -> list[dict[str, object]]:
    results = output.get("results")
    if not isinstance(results, list):
        return []
    context: list[dict[str, object]] = []
    for item in results[:5]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "")
        context.append(
            {
                "source_id": item.get("source_id"),
                "chunk_id": item.get("chunk_id"),
                "title": item.get("title"),
                "url": item.get("url"),
                "score": item.get("score"),
                "quote": text[:700],
            }
        )
    return context


def _response_from_grounded_draft(
    context: GuideContextRead,
    draft: _GroundedGuideAnswerDraft,
    search: _GuideEvidenceSearch,
    run_id: uuid.UUID,
) -> GuideChatResponseRead:
    allowed_sources = set(search.cited_evidence_ids)
    cited_evidence_ids = [
        source_id for source_id in draft.cited_evidence_ids if source_id in allowed_sources
    ]
    actions = _actions_from_ids(context, draft.suggested_action_ids)
    if not actions:
        actions = _support_actions(context)[:3] or context.available_actions[:3]
    recommended_action = actions[0] if actions else context.available_actions[0]
    unsupported = draft.unsupported_or_missing_evidence[:4]
    if not cited_evidence_ids and not unsupported:
        unsupported = ["No retrieved source directly supports this answer."]
    return GuideChatResponseRead(
        answer=draft.answer,
        recommended_action=recommended_action,
        action_cards=actions[:4],
        related_entities=_related_entities_with_evidence(context, cited_evidence_ids),
        cited_evidence_ids=cited_evidence_ids,
        assumption_ids=draft.assumption_ids[:8],
        confidence_level=draft.confidence_level,
        unsupported_or_missing_evidence=unsupported,
        used_llm=True,
        retrieval_diagnostics=search.retrieval_diagnostics,
        ai_run_id=run_id,
    )


def _actions_from_ids(context: GuideContextRead, action_ids: list[str]) -> list[GuideActionRead]:
    actions: list[GuideActionRead] = []
    seen: set[str] = set()
    for action_id in action_ids:
        action = _find_action_by_id(context, action_id)
        if action is None:
            continue
        if action.id in seen:
            continue
        seen.add(action.id)
        actions.append(action)
    return actions


def _find_action_by_id(
    context: GuideContextRead,
    action_id: str,
) -> GuideActionRead | None:
    for action in context.available_actions:
        if action.id == action_id:
            return action
    canonical_action_id = _canonical_action_id(action_id)
    for action in context.available_actions:
        if action.id == canonical_action_id:
            return action
    return None


def _related_entities_with_evidence(
    context: GuideContextRead,
    evidence_ids: list[str],
) -> list[GuideRelatedEntityRead]:
    entities = _related_entities(context)
    for source_id in evidence_ids[:3]:
        entities.append(
            GuideRelatedEntityRead(
                type="evidence",
                id=source_id,
                label="Retrieved evidence",
            )
        )
    return entities


def _grounded_confidence(context: GuideContextRead, has_citations: bool) -> str:
    if not has_citations:
        return "low" if context.confidence_level != "unknown" else "unknown"
    return context.confidence_level if context.confidence_level != "unknown" else "medium"


def _citation_details_from_search(
    search_output: dict[str, Any],
    context_pack: dict[str, Any] | None,
    cited_evidence_ids: list[str],
) -> list[GuideCitationDetailRead]:
    results = search_output.get("results")
    if not isinstance(results, list):
        return []
    cited = set(cited_evidence_ids)
    context_item_ids = _context_item_ids_by_source(context_pack)
    memory_ids = _memory_ids_from_context_pack(context_pack)
    details: list[GuideCitationDetailRead] = []
    seen_sources: set[str] = set()
    for result in results:
        if not isinstance(result, dict):
            continue
        source_id = str(result.get("source_id") or "")
        if not source_id or source_id not in cited or source_id in seen_sources:
            continue
        seen_sources.add(source_id)
        text = str(result.get("text") or "")
        details.append(
            GuideCitationDetailRead(
                source_id=source_id,
                chunk_id=str(result.get("chunk_id")) if result.get("chunk_id") else None,
                title=str(result.get("title")) if result.get("title") else None,
                url=str(result.get("url")) if result.get("url") else None,
                source_type=str(result.get("source_type")) if result.get("source_type") else None,
                excerpt=text[:600] if text else None,
                score=_optional_float(result.get("rerank_score") or result.get("score")),
                verifier_status="supported",
                context_item_ids=context_item_ids.get(source_id, []),
                memory_ids=memory_ids,
            )
        )
    return details


def _context_item_ids_by_source(context_pack: dict[str, Any] | None) -> dict[str, list[str]]:
    if not context_pack:
        return {}
    items = context_pack.get("items")
    if not isinstance(items, list):
        return {}
    result: dict[str, list[str]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        provenance = item.get("provenance")
        if not isinstance(provenance, dict):
            continue
        metadata = provenance.get("metadata")
        if not isinstance(metadata, dict):
            continue
        source_id = str(metadata.get("source_id") or "")
        item_id = str(item.get("id") or "")
        if source_id and item_id:
            result.setdefault(source_id, []).append(item_id)
    return result


def _memory_ids_from_context_pack(context_pack: dict[str, Any] | None) -> list[str]:
    if not context_pack:
        return []
    metadata = context_pack.get("metadata")
    if isinstance(metadata, dict):
        selected_ids = metadata.get("selected_memory_ids")
        if isinstance(selected_ids, list):
            return _unique_strings(str(item) for item in selected_ids if item)
    items = context_pack.get("items")
    if not isinstance(items, list):
        return []
    memory_ids: list[str] = []
    for item in items:
        if not isinstance(item, dict) or item.get("type") != "memory":
            continue
        provenance = item.get("provenance")
        if isinstance(provenance, dict) and provenance.get("entity_id"):
            memory_ids.append(str(provenance["entity_id"]))
    return _unique_strings(memory_ids)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bounded_recent_turns(recent_turns: list[GuideChatTurnRead]) -> list[dict[str, str]]:
    return [{"role": turn.role, "content": turn.content[:500]} for turn in recent_turns[-6:]]


def _unique_strings(values) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _guide_context_from_overview(
    db: Session,
    auth: AuthContext,
    overview: ProjectOverviewRead,
) -> GuideContextRead:
    snapshot = overview.strategic_snapshot
    project = overview.project
    actions = _available_actions(overview)
    return GuideContextRead(
        project_id=project.id,
        project_name=project.name,
        stage=snapshot.current_stage,
        verdict=overview.current_recommendation.recommendation,
        next_action=overview.next_best_action.label,
        risk_level=_risk_level(overview),
        confidence_level=(
            "unknown"
            if snapshot.current_stage == "draft_idea" and overview.evidence_health.source_count == 0
            else snapshot.current_confidence
        ),
        current_thesis=snapshot.current_thesis,
        target_user=snapshot.target_user,
        primary_problem=snapshot.primary_problem,
        current_wedge=snapshot.proposed_wedge,
        biggest_unknown=_biggest_unknown(overview),
        active_validation_plan_id=_active_validation_plan_id(db, auth, project.id),
        latest_research_sprint_id=_latest_research_sprint_id(db, auth, project.id),
        evidence_summary=GuideEvidenceSummaryRead(
            sources=overview.evidence_health.source_count,
            competitors=overview.evidence_health.competitor_count,
            supported_findings=overview.evidence_health.cited_claim_count,
            open_questions=overview.evidence_health.unsupported_claim_count
            + len(overview.idea_readiness.missing_items),
            validated_assumptions=overview.evidence_health.validated_assumption_count,
        ),
        missing_context=[item.label for item in overview.idea_readiness.missing_items],
        available_actions=actions,
    )


def _available_actions(overview: ProjectOverviewRead) -> list[GuideActionRead]:
    actions = [_guide_action_from_next_best(overview.next_best_action)]
    actions.extend(_guide_action_from_next_best(action) for action in overview.secondary_actions)
    actions.extend(_support_actions_for_overview(overview))

    deduped: list[GuideActionRead] = []
    seen: set[str] = set()
    for action in actions:
        if action.id in seen:
            continue
        seen.add(action.id)
        deduped.append(action)
    return deduped


def _guide_action_from_next_best(action: NextBestActionRead) -> GuideActionRead:
    label, description = _router_copy_for_next_best(action)
    return GuideActionRead(
        id=action.action_type,
        type=_action_type_for_next_best(action.action_type),
        label=label,
        description=description,
        why_it_matters=action.why_it_matters,
        target_route=action.target_route,
        target_modal=_target_modal_for_next_best(action.action_type),
        payload={"related_stage": action.related_stage},
        risk_level=_action_risk(action.action_type),
        requires_confirmation=action.action_type in {"use_suggested_decision", "resume_or_archive"},
    )


def _guide_action_from_decision_coach(
    project_id: uuid.UUID,
    action: DecisionCoachActionRead,
) -> GuideActionRead:
    return GuideActionRead(
        id=action.id,
        type="record_decision" if "record" in action.id else "navigate",
        label=action.label,
        description=action.description,
        why_it_matters=(
            "Decision actions keep the recommendation tied to evidence, missing proof, "
            "and a durable record."
        ),
        target_route=action.target_route or f"/projects/{project_id}#decisions",
        target_modal=action.target_modal,
        risk_level="high" if "record" in action.id else "low",
        requires_confirmation=False,
    )


def _support_actions_for_overview(overview: ProjectOverviewRead) -> list[GuideActionRead]:
    project_id = overview.project.id
    stage = overview.strategic_snapshot.current_stage
    actions = [
        GuideActionRead(
            id="explain_current_focus",
            type="explain",
            label="Explain why this is next",
            description="Show why this is the highest-leverage move right now.",
            why_it_matters=(
                "A clear reason helps the next step feel intentional instead of procedural."
            ),
            target_route=f"/projects/{project_id}#overview",
            risk_level="low",
            requires_confirmation=False,
        ),
        GuideActionRead(
            id="show_idea_story",
            type="navigate",
            label="Show idea story",
            description="Open the compact story from original idea to current proof.",
            why_it_matters=(
                "Seeing the original idea, selected wedge, rejected directions, blocker, "
                "and next proof makes the validation path easier to trust."
            ),
            target_route=f"/projects/{project_id}#current-step",
            risk_level="low",
            requires_confirmation=False,
        ),
        GuideActionRead(
            id="show_blocker_evidence",
            type="navigate",
            label="Show evidence behind the blocker",
            description="Open the research details that support the current blocker.",
            why_it_matters=(
                "The decision should stay tied to the evidence behind the current blocker."
            ),
            target_route=f"/projects/{project_id}#evidence",
            risk_level="low",
            requires_confirmation=False,
        ),
        GuideActionRead(
            id="plan_research_sprint",
            type="run_workflow",
            label="Plan evidence review",
            description=(
                "Open the research area to draft a scoped evidence review before running it."
            ),
            why_it_matters=(
                "Research plans keep investigation bounded and require approval before broader "
                "evidence work starts."
            ),
            target_route=f"/projects/{project_id}#research-sprint",
            target_modal="research-sprint",
            risk_level="medium",
            requires_confirmation=False,
        ),
        GuideActionRead(
            id="rewrite_thesis_with_wedge",
            type="update_thesis",
            label="Rewrite thesis with current wedge",
            description="Open the thesis canvas to tighten the idea around the selected wedge.",
            why_it_matters=(
                "A sharper thesis makes research, validation, and decisions more useful."
            ),
            target_route=f"/projects/{project_id}#thesis-canvas",
            target_modal="thesis-canvas",
            risk_level="medium",
            requires_confirmation=False,
        ),
        GuideActionRead(
            id="show_project_history",
            type="navigate",
            label="Show project history",
            description="Open the idea evolution timeline and decision trail.",
            why_it_matters=("The idea is easier to trust when you can see what changed and why."),
            target_route=f"/projects/{project_id}#history",
            risk_level="low",
            requires_confirmation=False,
        ),
    ]
    if stage in {
        "structured_intake",
        "brief_generated",
        "competitors_analyzed",
        "assumptions_identified",
        "validation_plan_created",
        "experiment_running",
        "decision_ready",
        "proceeding",
    }:
        actions.append(
            GuideActionRead(
                id="compare_wedge_options",
                type="compare_wedges",
                label="Compare wedge options",
                description="Open Wedge Explorer to compare possible strategic directions.",
                why_it_matters="A narrow wedge is easier to validate than a broad product idea.",
                target_route=f"/projects/{project_id}#wedge-explorer",
                target_modal="wedge-explorer",
                risk_level="medium",
                requires_confirmation=False,
            )
        )
    if stage in {"assumptions_identified", "validation_plan_created", "experiment_running"}:
        actions.extend(
            [
                GuideActionRead(
                    id="open_validation_mission",
                    type="navigate",
                    label="Open current validation mission",
                    description="Open the current proof with steps, assets, and result logging.",
                    why_it_matters=(
                        "The mission keeps validation focused on the one proof that can "
                        "change the decision."
                    ),
                    target_route=f"/projects/{project_id}#validation-mission",
                    target_modal="validation-mission",
                    risk_level="low",
                    requires_confirmation=False,
                ),
                GuideActionRead(
                    id="draft_validation_outreach",
                    type="generate_draft",
                    label="Draft outreach for this proof",
                    description="Use the current blocker to draft validation outreach.",
                    why_it_matters="Outreach turns a plan into real user evidence.",
                    target_route=f"/projects/{project_id}#validation-mission",
                    target_modal="draft-outreach",
                    risk_level="low",
                    requires_confirmation=False,
                ),
                GuideActionRead(
                    id="open_validation_result_form",
                    type="log_result",
                    label="Open validation result form",
                    description="Open the mission result form.",
                    why_it_matters="Logged results are what should change confidence and verdicts.",
                    target_route=f"/projects/{project_id}#validation-mission",
                    target_modal="log-result",
                    risk_level="medium",
                    requires_confirmation=False,
                ),
                GuideActionRead(
                    id="interpret_validation_notes",
                    type="log_result",
                    label="Interpret validation notes",
                    description="Open the result area so pasted notes can be interpreted.",
                    why_it_matters=(
                        "Interpreting notes closes the loop from proof to confidence and decision."
                    ),
                    target_route=f"/projects/{project_id}#validation-mission",
                    target_modal="interpret-result",
                    risk_level="medium",
                    requires_confirmation=False,
                ),
                GuideActionRead(
                    id="explain_success_criteria",
                    type="explain",
                    label="Explain this proof's success criteria",
                    description="Explain what result would make the proof strong enough.",
                    why_it_matters=(
                        "Validation is only useful when success and failure are explicit "
                        "before results arrive."
                    ),
                    target_route=f"/projects/{project_id}#validation-mission",
                    risk_level="low",
                    requires_confirmation=False,
                ),
            ]
        )
    if stage in {"decision_ready", "proceeding", "paused", "killed"}:
        actions.append(
            GuideActionRead(
                id="prepare_decision_record",
                type="record_decision",
                label="Prepare decision record",
                description="Open the decision area with the recommendation context.",
                why_it_matters="Decision records preserve what changed and why.",
                target_route=f"/projects/{project_id}#record-decision-panel",
                target_modal="record-decision-panel",
                risk_level="high",
                requires_confirmation=False,
            )
        )
    return actions


def _action_type_for_next_best(action_type: str) -> str:
    if action_type in {"structure_idea"}:
        return "open_form"
    if action_type in {"generate_brief", "analyze_competitors", "create_validation_plan"}:
        return "run_workflow"
    if action_type in {"log_results", "add_results"}:
        return "log_result"
    if "decision" in action_type or action_type in {"resume_or_archive", "view_decision"}:
        return "record_decision"
    if "assumption" in action_type:
        return "explain"
    return "navigate"


def _router_copy_for_next_best(action: NextBestActionRead) -> tuple[str, str]:
    labels = {
        "structure_idea": (
            "Open thesis structure form",
            "Open the form that turns the rough idea into a testable thesis.",
        ),
        "generate_brief": (
            "Generate evidence-backed brief",
            "Run the brief workflow to ground the thesis in evidence and open questions.",
        ),
        "analyze_competitors": (
            "Run competitor analysis",
            "Open the research surface that maps direct competitors, substitutes, and wedges.",
        ),
        "review_assumptions": (
            "Open blocker assumptions",
            "Open the assumptions that explain what must be true before building.",
        ),
        "create_validation_plan": (
            "Create validation mission",
            "Open the test-planning surface for the riskiest assumption.",
        ),
        "start_experiment": (
            "Open current validation mission",
            "Open the proof that should produce the next real signal.",
        ),
        "log_results": (
            "Open validation result form",
            "Open the result form so real validation evidence can update confidence.",
        ),
        "add_results": (
            "Open validation result form",
            "Open the result form so real validation evidence can update confidence.",
        ),
        "use_suggested_decision": (
            "Prepare decision record",
            "Open the decision surface with the suggested proceed, pivot, pause, or kill path.",
        ),
        "record_decision": (
            "Prepare decision record",
            "Open the decision record form with the current evidence context.",
        ),
        "view_decision": (
            "Open recorded decision",
            "Open the decision trail that explains what was decided and why.",
        ),
        "resume_or_archive": (
            "Choose resume or archive path",
            "Open the decision area to decide whether this idea deserves another proof.",
        ),
    }
    return labels.get(action.action_type, (action.label, action.description))


def _target_modal_for_next_best(action_type: str) -> str | None:
    return {
        "structure_idea": "structured-intake",
        "log_results": "log-result",
        "add_results": "log-result",
        "record_decision": "record-decision-panel",
        "use_suggested_decision": "record-decision-panel",
    }.get(action_type)


def _action_risk(action_type: str) -> str:
    if action_type in {"use_suggested_decision", "resume_or_archive", "view_decision"}:
        return "high"
    if action_type in {"create_validation_plan", "log_results", "add_results"}:
        return "medium"
    return "low"


def _risk_level(overview: ProjectOverviewRead) -> str:
    if overview.strategic_snapshot.current_stage in {"killed"}:
        return "none"
    if any(
        assumption.kill_risk or assumption.importance in {"critical", "high"}
        for assumption in overview.key_assumptions
    ):
        return "high"
    if overview.evidence_health.unsupported_claim_count > 0 or overview.key_risks:
        return "medium"
    if overview.evidence_health.source_count == 0:
        return "medium"
    return "low"


def _biggest_unknown(overview: ProjectOverviewRead) -> str | None:
    if overview.key_assumptions:
        return overview.key_assumptions[0].text
    if overview.key_risks:
        return overview.key_risks[0].text
    if overview.idea_readiness.weakest_area:
        return overview.idea_readiness.weakest_area
    return None


def _active_validation_plan_id(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> uuid.UUID | None:
    mission_id = db.scalar(
        select(ValidationMission.id)
        .where(
            ValidationMission.workspace_id == auth.workspace_id,
            ValidationMission.project_id == project_id,
            ValidationMission.status != "closed",
        )
        .order_by(ValidationMission.updated_at.desc())
        .limit(1)
    )
    if mission_id:
        return mission_id
    experiment_id = db.scalar(
        select(Experiment.id)
        .where(
            Experiment.workspace_id == auth.workspace_id,
            Experiment.project_id == project_id,
            Experiment.status.in_(["planned", "running"]),
        )
        .order_by(Experiment.updated_at.desc())
        .limit(1)
    )
    if experiment_id:
        return experiment_id
    return db.scalar(
        select(Artifact.id)
        .where(
            Artifact.workspace_id == auth.workspace_id,
            Artifact.project_id == project_id,
            Artifact.artifact_type == "validation_plan",
        )
        .order_by(Artifact.updated_at.desc())
        .limit(1)
    )


def _latest_research_sprint_id(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> uuid.UUID | None:
    return db.scalar(
        select(ResearchSprint.id)
        .where(
            ResearchSprint.workspace_id == auth.workspace_id,
            ResearchSprint.project_id == project_id,
        )
        .order_by(ResearchSprint.created_at.desc())
        .limit(1)
    )


def _suggested_questions(context: GuideContextRead) -> list[str]:
    default_questions = [
        "What should I do next?",
        "How has this idea changed?",
        "Why is this blocked?",
        "Open the right form.",
        "What evidence is missing?",
        "Rewrite the thesis.",
        "Compare wedges.",
        "What is the next proof?",
        "Draft outreach.",
        "Interpret notes.",
        "What would make this worth building?",
    ]
    stage_questions = {
        "draft_idea": [
            "What should I do next?",
            "Open the right form.",
            "Rewrite the thesis.",
            "What evidence is missing?",
        ],
        "structured_intake": [
            "What should I do next?",
            "Why is this blocked?",
            "What evidence is missing?",
            "Compare wedges.",
        ],
        "validation_plan_created": [
            "Why is this the blocker?",
            "Open the right form.",
            "Draft outreach.",
            "What results would change the decision?",
        ],
        "experiment_running": [
            "Open the right form.",
            "Interpret notes.",
            "What would make this worth building?",
        ],
        "decision_ready": [
            "What would make this worth building?",
            "What evidence is missing?",
            "Summarize the decision for my notes.",
        ],
    }
    return stage_questions.get(context.stage, default_questions)


def _is_in_scope(message: str) -> bool:
    allowed_terms = {
        "action",
        "assumption",
        "blocker",
        "become",
        "broad",
        "build",
        "decision",
        "evidence",
        "experiment",
        "focus",
        "form",
        "idea",
        "changed",
        "directions",
        "interview",
        "kill",
        "evolution",
        "evolved",
        "missing",
        "mission",
        "next",
        "notes",
        "outreach",
        "pause",
        "pivot",
        "proceed",
        "proof",
        "recommend",
        "recommended",
        "rejected",
        "research",
        "result",
        "right",
        "risk",
        "selected",
        "source",
        "stage",
        "test",
        "criteria",
        "thesis",
        "validate",
        "validation",
        "verdict",
        "wedge",
        "worth",
    }
    return any(term in message for term in allowed_terms)


def _chat_response(
    answer: str,
    context: GuideContextRead,
    actions: list[GuideActionRead],
) -> GuideChatResponseRead:
    recommended_action = actions[0] if actions else context.available_actions[0]
    return GuideChatResponseRead(
        answer=answer,
        recommended_action=recommended_action,
        action_cards=actions[:4],
        related_entities=_related_entities(context),
    )


def _related_entities(context: GuideContextRead) -> list[GuideRelatedEntityRead]:
    entities = [
        GuideRelatedEntityRead(type="thesis", id=str(context.project_id), label="Current thesis"),
    ]
    if context.latest_research_sprint_id:
        entities.append(
            GuideRelatedEntityRead(
                type="research",
                id=str(context.latest_research_sprint_id),
                label="Latest research sprint",
            )
        )
    if context.active_validation_plan_id:
        entities.append(
            GuideRelatedEntityRead(
                type="validation_plan",
                id=str(context.active_validation_plan_id),
                label="Current validation mission",
            )
        )
    return entities


def _support_actions(context: GuideContextRead) -> list[GuideActionRead]:
    preferred = [
        "explain_current_focus",
        "show_blocker_evidence",
        "plan_research_sprint",
        "rewrite_thesis_with_wedge",
        "compare_wedge_options",
        "open_validation_mission",
        "draft_validation_outreach",
        "open_validation_result_form",
        "interpret_validation_notes",
        "explain_success_criteria",
        "prepare_decision_record",
        "show_idea_story",
        "show_project_history",
    ]
    return [
        action
        for action_id in preferred
        for action in context.available_actions
        if action.id == action_id
    ]


def _action_by_id(context: GuideContextRead, action_id: str) -> GuideActionRead:
    for action in context.available_actions:
        if action.id == action_id:
            return action
    canonical_action_id = _canonical_action_id(action_id)
    for action in context.available_actions:
        if action.id == canonical_action_id:
            return action
    return context.available_actions[0]


def _canonical_action_id(action_id: str) -> str:
    return {
        "show_evidence": "show_blocker_evidence",
        "update_thesis": "rewrite_thesis_with_wedge",
        "idea_story": "show_idea_story",
        "show_evolution": "show_project_history",
        "compare_wedges": "compare_wedge_options",
        "draft_outreach": "draft_validation_outreach",
        "log_results": "open_validation_result_form",
        "record_decision": "prepare_decision_record",
    }.get(action_id, action_id)


def _fallback_stage_copy(stage: str) -> _StageGuideCopy:
    return _StageGuideCopy(
        focus="Choose the next strategic step.",
        why=(
            f"The project is in {stage}, so the guide should route the user to the "
            "highest-leverage action."
        ),
        summary="Use the next recommended action to keep the idea moving.",
    )


def _after_that_for_action(context: GuideContextRead, action: GuideActionRead) -> str:
    if action.type == "open_form" or "thesis" in action.id:
        return (
            "I will use the sharper thesis to route you toward research, wedge choice, or a proof."
        )
    if action.type == "compare_wedges" or "wedge" in action.id:
        return "The selected wedge becomes the basis for the current thesis and validation mission."
    if action.type == "run_workflow" or "research" in action.id or "evidence" in action.id:
        return "I will use the evidence to update the blocker, recommendation, and next proof."
    if action.type == "log_result" or "result" in action.id or "validation" in action.id:
        return "I will interpret the signal and recommend continue, pivot, pause, kill, or proceed."
    if action.type == "record_decision" or "decision" in action.id:
        return (
            "The decision trail will preserve what changed, what evidence mattered, "
            "and what to revisit."
        )
    if context.stage == "decision_ready":
        return "I will help translate the current proof into a decision record."
    return (
        "I will route you to the next focused step and keep the project history tied to the action."
    )


def _join_list(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + f", and {items[-1]}"
