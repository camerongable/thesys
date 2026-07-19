"""Prompt and fallback helpers for research sprint planning."""

import json
from typing import Any

from app.ai.litellm_client import ChatMessage
from app.ai.prompts import UNTRUSTED_RETRIEVED_CONTENT_RULE
from app.schemas.research import ResearchPlanDraft


def planning_messages(
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


def fallback_research_plan(
    project_context: dict[str, Any],
    objective: str | None,
) -> ResearchPlanDraft:
    project_name = str(project_context.get("name") or "the opportunity").strip()
    target_users = [
        str(user).strip() for user in project_context.get("target_users", []) if str(user).strip()
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
