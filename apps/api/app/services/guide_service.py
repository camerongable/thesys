"""Ask Thesys guide service.

The guide is a bounded project copilot: it can retrieve evidence, explain the
next action, and create approval-gated proposals, but it does not silently
mutate strategic project state from chat.
"""

import uuid
from collections.abc import Generator, Iterator
from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.litellm_client import LiteLLMClient
from app.ai.prompts import GUIDE_CHAT_PROMPT_VERSION
from app.ai.structured_output import generate_structured_output, schema_instruction_message
from app.core.auth import AuthContext
from app.core.config import Settings, get_settings
from app.db.models import ApprovalRequest, Artifact, Experiment, ResearchSprint, ValidationMission
from app.features.guide import actions as guide_actions
from app.features.guide import citations as guide_citations
from app.features.guide import context_projection as guide_context_projection
from app.features.guide import events as guide_events
from app.features.guide import grounding as guide_grounding
from app.features.guide import prompting as guide_prompting
from app.features.guide import recommendations as guide_recommendations
from app.features.guide import routing as guide_routing
from app.schemas.guide import (
    GuideActionRead,
    GuideChatResponseRead,
    GuideChatTurnRead,
    GuideContextRead,
    GuideResponseRead,
)
from app.services import (
    ai_cache_service,
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
class _GuideEvidenceSearch:
    output: dict
    cited_evidence_ids: list[str]
    retrieval_diagnostics: dict | None
    context_pack: dict | None = None


_StageGuideCopy = guide_recommendations.StageGuideCopy
_STAGE_GUIDE_COPY = guide_recommendations.STAGE_GUIDE_COPY
_GroundedGuideAnswerDraft = guide_grounding.GroundedGuideAnswerDraft


def get_guide_context(
    db: Session,
    auth: AuthContext,
    project_id: uuid.UUID,
) -> GuideContextRead:
    """Build the project state snapshot used by guide recommendations and chat."""
    overview = project_overview_service.get_project_overview(db, auth, project_id)
    return _guide_context_from_overview(
        overview,
        active_validation_plan_id=_active_validation_plan_id(db, auth, project_id),
        latest_research_sprint_id=_latest_research_sprint_id(db, auth, project_id),
    )


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


_retrieval_started_events = guide_events.retrieval_started_events
_retrieval_completed_events = guide_events.retrieval_completed_events
_retrieval_result_count = guide_events.retrieval_result_count
_answer_delta_chunks = guide_events.answer_delta_chunks
_final_stream_metadata = guide_events.final_stream_metadata


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


_schema_instruction_for_stream = schema_instruction_message
_partial_answer_from_json = guide_events.partial_answer_from_json
_json_escape_character = guide_events.json_escape_character


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


_out_of_scope_chat_response = guide_routing.out_of_scope_chat_response


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


_proposal_tool_for_message = guide_routing.proposal_tool_for_message
_proposal_payload = guide_routing.proposal_payload
_proposal_action = guide_routing.proposal_action


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
    context_pack_payload = context_pack.model_dump(mode="json")
    key_payload, family_payload, version_payload = ai_cache_service.guide_answer_cache_payloads(
        db,
        auth,
        settings,
        project_id,
        message=message,
        recent_turns=recent_turns,
        prompt_version=GUIDE_CHAT_PROMPT_VERSION,
        expected_schema=_GroundedGuideAnswerDraft.__name__,
        context_pack=context_pack_payload,
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
        cache_lookup = ai_cache_service.lookup(
            db,
            auth,
            settings,
            cache_type="guide_answer",
            key_payload=key_payload,
            family_payload=family_payload,
            version_payload=version_payload,
            project_id=project_id,
            saved_tokens=1200,
            latency_saved_ms=250,
        )
        if cache_lookup.value is not None:
            response = GuideChatResponseRead.model_validate(cache_lookup.value["response"])
            response.ai_run_id = run.id
            cache_metadata = ai_cache_service.cache_event_diagnostics(cache_lookup.event)
            response.context_pack = {
                **(response.context_pack or {}),
                "cache": cache_metadata,
            }
            ai_run_service.complete_step(
                db,
                generation_step,
                output_json={
                    "cache": cache_metadata,
                    "response": response.model_dump(mode="json"),
                },
                latency_ms=int((perf_counter() - started) * 1000),
                tokens=0,
                cost=Decimal("0"),
            )
            return response, 0, Decimal("0"), "cache", settings.litellm_model

        result = generate_structured_output(
            settings,
            _GroundedGuideAnswerDraft,
            _grounded_guide_messages(message, context_pack),
            temperature=0.1,
            max_tokens=900,
        )
        draft = _GroundedGuideAnswerDraft.model_validate(result.parsed)
        response = _response_from_grounded_draft(context, draft, search, run.id)
        response.context_pack = context_pack_payload
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
        if cache_lookup.event is None or cache_lookup.event.event_type != "disabled":
            ai_cache_service.store(
                db,
                auth,
                cache_type="guide_answer",
                key_payload=key_payload,
                family_payload=family_payload,
                version_payload=version_payload,
                value_payload={"response": response.model_dump(mode="json")},
                project_id=project_id,
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


_grounded_guide_messages = guide_prompting.grounded_guide_messages


_evidence_context_for_prompt = guide_grounding.evidence_context_for_prompt
_response_from_grounded_draft = guide_grounding.response_from_grounded_draft


_actions_from_ids = guide_routing.actions_from_ids
_find_action_by_id = guide_routing.find_action_by_id
_related_entities_with_evidence = guide_routing.related_entities_with_evidence
_grounded_confidence = guide_routing.grounded_confidence


_citation_details_from_search = guide_citations.citation_details_from_search
_citation_extraction_metadata = guide_citations.citation_extraction_metadata
_citation_provenance_metadata = guide_citations.citation_provenance_metadata
_citation_warnings = guide_citations.citation_warnings
_context_item_ids_by_source = guide_citations.context_item_ids_by_source
_memory_ids_from_context_pack = guide_citations.memory_ids_from_context_pack
_optional_float = guide_citations.optional_float
_optional_int = guide_citations.optional_int


_bounded_recent_turns = guide_context_projection.bounded_recent_turns


def _unique_strings(values) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


_guide_context_from_overview = guide_context_projection.guide_context_from_overview


_available_actions = guide_actions.available_actions
_guide_action_from_next_best = guide_actions.guide_action_from_next_best
_guide_action_from_decision_coach = guide_actions.guide_action_from_decision_coach
_support_actions_for_overview = guide_actions.support_actions_for_overview
_action_type_for_next_best = guide_actions.action_type_for_next_best
_router_copy_for_next_best = guide_actions.router_copy_for_next_best
_target_modal_for_next_best = guide_actions.target_modal_for_next_best
_action_risk = guide_actions.action_risk


_risk_level = guide_context_projection.risk_level
_biggest_unknown = guide_context_projection.biggest_unknown


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


_suggested_questions = guide_recommendations.suggested_questions
_is_in_scope = guide_routing.is_in_scope
_chat_response = guide_routing.chat_response
_related_entities = guide_routing.related_entities
_support_actions = guide_routing.support_actions
_action_by_id = guide_routing.action_by_id
_canonical_action_id = guide_routing.canonical_action_id_for
_fallback_stage_copy = guide_recommendations.fallback_stage_copy
_after_that_for_action = guide_recommendations.after_that_for_action
_join_list = guide_recommendations.join_list
