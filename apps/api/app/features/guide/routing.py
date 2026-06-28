"""Deterministic intent and action routing helpers for Ask Thesys."""

from app.schemas.guide import (
    GuideActionRead,
    GuideChatResponseRead,
    GuideContextRead,
    GuideRelatedEntityRead,
)


def proposal_tool_for_message(normalized: str) -> str | None:
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


def proposal_payload(
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


def proposal_action(context: GuideContextRead, tool_name: str) -> GuideActionRead:
    preferred = {
        "propose_research_plan": "plan_research_sprint",
        "propose_validation_plan": "create_validation_plan",
        "propose_memory_update": "show_project_history",
        "propose_decision": "use_suggested_decision",
    }
    return action_by_id(context, preferred.get(tool_name, "explain_current_focus"))


def is_in_scope(message: str) -> bool:
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


def chat_response(
    answer: str,
    context: GuideContextRead,
    actions: list[GuideActionRead],
) -> GuideChatResponseRead:
    recommended_action = actions[0] if actions else context.available_actions[0]
    return GuideChatResponseRead(
        answer=answer,
        recommended_action=recommended_action,
        action_cards=actions[:4],
        related_entities=related_entities(context),
    )


def out_of_scope_chat_response(context: GuideContextRead) -> GuideChatResponseRead:
    return GuideChatResponseRead(
        answer=(
            "I can help with this idea's thesis, evidence, blockers, validation, "
            "and decisions. Try asking what to validate next or why the current "
            "verdict is blocked."
        ),
        recommended_action=action_by_id(context, "explain_current_focus"),
        action_cards=[action_by_id(context, "explain_current_focus")],
        related_entities=related_entities(context),
        confidence_level=context.confidence_level,
        unsupported_or_missing_evidence=context.missing_context[:3],
    )


def related_entities(context: GuideContextRead) -> list[GuideRelatedEntityRead]:
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


def related_entities_with_evidence(
    context: GuideContextRead,
    evidence_ids: list[str],
) -> list[GuideRelatedEntityRead]:
    entities = related_entities(context)
    for source_id in evidence_ids[:3]:
        entities.append(
            GuideRelatedEntityRead(
                type="evidence",
                id=source_id,
                label="Retrieved evidence",
            )
        )
    return entities


def grounded_confidence(context: GuideContextRead, has_citations: bool) -> str:
    if not has_citations:
        return "low" if context.confidence_level != "unknown" else "unknown"
    return context.confidence_level if context.confidence_level != "unknown" else "medium"


def support_actions(context: GuideContextRead) -> list[GuideActionRead]:
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


def actions_from_ids(context: GuideContextRead, action_ids: list[str]) -> list[GuideActionRead]:
    actions: list[GuideActionRead] = []
    seen: set[str] = set()
    for action_id in action_ids:
        action = find_action_by_id(context, action_id)
        if action is None:
            continue
        if action.id in seen:
            continue
        seen.add(action.id)
        actions.append(action)
    return actions


def find_action_by_id(
    context: GuideContextRead,
    action_id: str,
) -> GuideActionRead | None:
    for action in context.available_actions:
        if action.id == action_id:
            return action
    canonical_action_id = canonical_action_id_for(action_id)
    for action in context.available_actions:
        if action.id == canonical_action_id:
            return action
    return None


def action_by_id(context: GuideContextRead, action_id: str) -> GuideActionRead:
    action = find_action_by_id(context, action_id)
    return action or context.available_actions[0]


def canonical_action_id_for(action_id: str) -> str:
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
