"""Prompt and deterministic fallback helpers for validation generation."""

import json
from typing import Any

from app.ai.litellm_client import ChatMessage
from app.ai.prompts import UNTRUSTED_RETRIEVED_CONTENT_RULE
from app.schemas.artifacts import AssumptionDraft, RiskDraft
from app.schemas.validation import (
    AssumptionExtractionDraft,
    ValidationPlanDraft,
    ValidationPlanSetDraft,
)


def assumption_messages(project_name: str, project_state: dict[str, Any]) -> list[ChatMessage]:
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
                f"Return structured assumptions and risks for {project_name} as JSON only.\n\n"
                f"{json.dumps(payload, indent=2, sort_keys=True)}"
            ),
        ),
    ]


def validation_plan_messages(
    project_name: str,
    project_state: dict[str, Any],
    assumptions: list[Any],
) -> list[ChatMessage]:
    payload = {
        "project_state": project_state,
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


def fallback_assumption_extraction(project_name: str | None) -> AssumptionExtractionDraft:
    project_label = project_name or "this project"
    return AssumptionExtractionDraft(
        assumptions=[
            AssumptionDraft(
                text=("Target users experience the problem frequently enough to seek a new tool."),
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
                    "The current evidence base may be too thin to support confident prioritization."
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


def fallback_validation_plan(
    project_name: str | None,
    assumptions: list[Any],
) -> ValidationPlanSetDraft:
    project_label = project_name or "this project"
    return ValidationPlanSetDraft(
        summary=(
            f"Validate {project_label} by testing the highest-risk assumptions with direct "
            "target-user conversations and lightweight prototype tasks."
        ),
        plans=[fallback_validation_plan_item(assumption) for assumption in assumptions],
    )


def fallback_validation_plan_item(assumption: Any) -> ValidationPlanDraft:
    return ValidationPlanDraft(
        assumption_id=assumption.id,
        assumption_text=assumption.text,
        method="customer_discovery_interviews",
        target_respondent=(
            "People who match the target user profile and recently tried to solve this problem."
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
