"""Rendering helpers for validation plans and validation missions."""

from typing import Any

from app.schemas.validation import ValidationPlanDraft, ValidationPlanSetDraft


def mission_steps(plan: ValidationPlanDraft) -> list[str]:
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


def mission_assets(plan: ValidationPlanDraft) -> list[dict[str, str]]:
    return [
        {
            "type": "interview_script",
            "title": "Interview script",
            "content": asset_content(
                [
                    f"Target respondent: {plan.target_respondent}",
                    "Interview questions:",
                    *numbered_asset_lines(plan.interview_questions),
                ]
            ),
        },
        {
            "type": "screener_questions",
            "title": "Screener questions",
            "content": asset_content(numbered_asset_lines(plan.screener_questions)),
        },
        {
            "type": "survey_questions",
            "title": "Survey questions",
            "content": asset_content(numbered_asset_lines(plan.survey_questions)),
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
            or (f"Success: {plan.success_criteria}\n\nFailure: {plan.failure_threshold}"),
        },
    ]


def numbered_asset_lines(values: list[str]) -> list[str]:
    if not values:
        return ["Not generated yet."]
    return [f"{index}. {value}" for index, value in enumerate(values, start=1)]


def asset_content(parts: list[str]) -> str:
    return "\n".join(part for part in parts if part).strip() or "Not generated yet."


def render_validation_plan_markdown(project: Any, draft: ValidationPlanSetDraft) -> str:
    sections = [f"# Validation Plan: {project.name}", f"## Summary\n{draft.summary}"]
    for index, plan in enumerate(draft.plans, start=1):
        sections.append(
            "\n\n".join(
                [
                    f"## Experiment {index}: {plan.assumption_text}",
                    f"**Method:** {plan.method}",
                    f"**Target respondent:** {plan.target_respondent}",
                    "### Screener Questions\n" + markdown_list(plan.screener_questions),
                    "### Steps\n" + markdown_list(plan.steps),
                    "### Interview Questions\n" + markdown_list(plan.interview_questions),
                    "### Survey Questions\n" + markdown_list(plan.survey_questions),
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


def render_experiment_plan(plan: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            f"Target respondent: {plan.get('target_respondent')}",
            "Screener questions:\n" + markdown_list(plan.get("screener_questions") or []),
            "Steps:\n" + markdown_list(plan.get("steps") or []),
            "Interview questions:\n" + markdown_list(plan.get("interview_questions") or []),
            "Survey questions:\n" + markdown_list(plan.get("survey_questions") or []),
            f"Landing page copy: {plan.get('landing_page_copy') or 'Not generated.'}",
            f"Outreach message: {plan.get('outreach_message') or 'Not generated.'}",
            f"Note-taking template: {plan.get('note_taking_template') or 'Not generated.'}",
            "Result interpretation rubric: "
            + str(plan.get("result_interpretation_rubric") or "Not generated."),
            f"Expected signal strength: {plan.get('expected_signal_strength')}",
        ]
    )


def markdown_list(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values) or "- None"
