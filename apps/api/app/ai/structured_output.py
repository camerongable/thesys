import json
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from types import UnionType
from typing import Any, Literal, TypeVar, Union, get_args, get_origin

from pydantic import BaseModel, ValidationError

from app.ai.litellm_client import ChatMessage, LiteLLMClient, LLMCompletion
from app.core.config import Settings

StructuredModel = TypeVar("StructuredModel", bound=BaseModel)


@dataclass(frozen=True)
class StructuredOutputResult:
    parsed: BaseModel
    completion: LLMCompletion


class StructuredOutputError(RuntimeError):
    pass


def generate_structured_output(
    settings: Settings,
    output_schema: type[StructuredModel],
    messages: Sequence[ChatMessage],
    *,
    model: str | None = None,
    temperature: float = 0.0,
) -> StructuredOutputResult:
    if settings.should_use_llm_stub:
        return _stub_structured_output(output_schema, messages, model or settings.litellm_model)

    schema_instruction = ChatMessage(
        role="system",
        content=(
            "Return only valid JSON. The JSON must validate against this JSON Schema: "
            f"{json.dumps(output_schema.model_json_schema(), separators=(',', ':'))}"
        ),
    )
    completion = LiteLLMClient(settings).complete(
        [schema_instruction, *messages],
        model=model,
        temperature=temperature,
        response_format_json=True,
    )

    try:
        parsed = output_schema.model_validate_json(completion.content)
    except ValidationError as exc:
        raise StructuredOutputError("LLM output failed Pydantic validation.") from exc

    return StructuredOutputResult(parsed=parsed, completion=completion)


def _stub_structured_output(
    output_schema: type[StructuredModel],
    messages: Sequence[ChatMessage],
    model_name: str,
) -> StructuredOutputResult:
    subject = _last_user_message(messages)
    if output_schema.__name__ == "StructuredProjectIntake":
        payload = _fake_structured_project_intake(subject)
    else:
        payload = {
            name: _fake_value(field.annotation, name=name, subject=subject)
            for name, field in output_schema.model_fields.items()
        }
    parsed = output_schema.model_validate(payload)
    content = parsed.model_dump_json()
    prompt_tokens = sum(len(message.content.split()) for message in messages)
    completion_tokens = len(content.split())
    completion = LLMCompletion(
        content=content,
        model_provider="stub",
        model_name=f"deterministic-dev-stub:{model_name}",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        total_cost=Decimal("0"),
        raw_response={"stub": True, "content": parsed.model_dump(mode="json")},
        used_stub=True,
    )
    return StructuredOutputResult(parsed=parsed, completion=completion)


def _last_user_message(messages: Sequence[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return message.content
    return "the provided strategic idea"


def _fake_structured_project_intake(subject: str) -> dict[str, Any]:
    request_payload = _extract_json_payload(subject)
    raw_idea = str(request_payload.get("raw_idea") or subject)
    answers = request_payload.get("clarifying_answers") or []
    answer_text = " ".join(
        str(answer.get("answer", "")) for answer in answers if isinstance(answer, dict)
    )
    combined_text = f"{raw_idea} {answer_text}".casefold()

    if "fitness" in combined_text or "coach" in combined_text or "trainer" in combined_text:
        target_users = ["Independent online fitness coaches", "Solo personal trainers"]
        if "gym" in combined_text:
            target_users.append("Small boutique gym operators")
        return {
            "project_name": "Fitness Coach Intelligence OS",
            "one_sentence_summary": (
                "Independent fitness coaches need a faster way to turn client check-ins, "
                "wearable data, and workout logs into specific coaching actions."
            ),
            "target_users": _dedupe(target_users),
            "buyer_type": "prosumer",
            "problem_hypotheses": [
                (
                    "Coaches spend too much time reviewing check-ins and translating them "
                    "into next steps."
                ),
                (
                    "Client progress data is scattered across messages, spreadsheets, apps, "
                    "and wearables."
                ),
                (
                    "Generic coaching software stores data but does not synthesize decisions "
                    "for the coach."
                ),
            ],
            "proposed_solution": (
                "A coach-facing workspace that synthesizes check-ins, wearable signals, "
                "and workout logs into adaptive training recommendations and client "
                "communication drafts."
            ),
            "market_category": "Fitness coaching software",
            "business_model_guess": "Monthly subscription for independent coaches",
            "suspected_competitors": ["Trainerize", "TrueCoach", "Everfit", "Google Sheets"],
            "key_uncertainties": [
                (
                    "Whether coaches trust AI-generated recommendations enough to use "
                    "them with clients."
                ),
                "Whether solo coaches feel enough weekly time pain to pay for another tool.",
                "Which integrations are required for a credible first version.",
            ],
            "clarifying_questions": _clarifying_questions(
                [
                    (
                        "Which coach segment should be tested first: online coaches, "
                        "in-person trainers, or small gyms?"
                    ),
                    (
                        "What weekly workflow is most painful today: programming, "
                        "check-ins, or client messaging?"
                    ),
                    "Which data sources are must-have for the first version?",
                ],
                answers,
            ),
        }

    return {
        "project_name": _fallback_project_name(raw_idea),
        "one_sentence_summary": (
            "The target user may need a structured workflow to turn scattered information "
            "into clearer strategic decisions."
        ),
        "target_users": ["Early-stage founders", "Solo operators"],
        "buyer_type": "unknown",
        "problem_hypotheses": [
            "The target user currently relies on fragmented notes, tabs, and generic AI chats.",
            "Important assumptions and decisions are not tracked in a reusable system of record.",
        ],
        "proposed_solution": (
            "A focused workspace that converts rough inputs into structured project state, "
            "assumptions, next actions, and decision history."
        ),
        "market_category": "Strategic workflow software",
        "business_model_guess": "Subscription software",
        "suspected_competitors": ["ChatGPT", "Notion", "Perplexity"],
        "key_uncertainties": [
            "Whether the target user has urgent enough pain to pay.",
            "Which workflow creates recurring usage rather than one-time report generation.",
            "What evidence is needed to validate the first wedge.",
        ],
        "clarifying_questions": _clarifying_questions(
            [
                "Which user segment has the most urgent pain and budget?",
                "What decision should this product help the user make first?",
                "What evidence would make this opportunity worth pursuing?",
            ],
            answers,
        ),
    }


def _extract_json_payload(content: str) -> dict[str, Any]:
    start = content.find("{")
    if start == -1:
        return {}
    try:
        payload, _ = json.JSONDecoder().raw_decode(content[start:])
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _clarifying_questions(questions: list[str], answers: Any) -> list[str]:
    answered = {
        str(answer.get("question", "")).strip().casefold()
        for answer in answers
        if isinstance(answer, dict)
    }
    remaining = [question for question in questions if question.casefold() not in answered]
    return remaining or [
        "What evidence should be added first to validate the highest-risk assumption?",
        "What would make this project a clear no-go?",
        "What is the next decision this project needs to support?",
    ]


def _fallback_project_name(raw_idea: str) -> str:
    words = [word.strip(".,:;!?()[]{}\"'") for word in raw_idea.split()]
    meaningful = [word for word in words if len(word) > 2][:5]
    return " ".join(meaningful).title() or "Structured Founder Project"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _fake_value(annotation: Any, *, name: str, subject: str) -> Any:
    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in (UnionType, Union):
        non_null_args = [arg for arg in args if arg is not type(None)]
        return _fake_value(non_null_args[0], name=name, subject=subject) if non_null_args else None

    if origin is Literal:
        return args[0] if args else None

    if origin is list:
        inner = args[0] if args else str
        count = 3 if "question" in name or "uncertainties" in name else 2
        return [
            _fake_value(
                inner,
                name=(_singularize(name) if index == 0 else f"{index + 1} {_singularize(name)}"),
                subject=subject,
            )
            for index in range(count)
        ]

    if origin is dict:
        return {}

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return {
            child_name: _fake_value(child.annotation, name=child_name, subject=subject)
            for child_name, child in annotation.model_fields.items()
        }

    if annotation is str:
        return _fake_string(name, subject)
    if annotation is int:
        return 1
    if annotation is float:
        return 0.5
    if annotation is bool:
        return False
    if annotation is Decimal:
        return Decimal("0.5")

    return None


def _fake_string(name: str, subject: str) -> str:
    readable = name.replace("_", " ")
    compact_subject = " ".join(subject.split())[:160]
    if name == "project_name":
        return "Structured founder project"
    if name == "one_sentence_summary":
        return f"Structured summary for: {compact_subject}"
    if name == "proposed_solution":
        return (
            "A focused workflow product that turns messy founder inputs into structured strategy."
        )
    if "problem_hypoth" in name:
        return "The target user spends too much time converting scattered evidence into decisions."
    if "competitor" in name:
        return "Generic AI assistants"
    if "market_category" in name:
        return "Strategic intelligence workflow software"
    if "business_model" in name:
        return "Subscription software"
    if "question" in name:
        return "Which customer segment has the most urgent pain and budget?"
    if "summary" in name:
        return f"Deterministic summary for: {compact_subject}"
    if "uncert" in name:
        return "Whether the target user has urgent enough pain to pay."
    if "next" in name or "step" in name:
        return "Add three evidence sources, then generate the first cited brief."
    if "user" in name:
        return "Early-stage founder"
    return f"{readable.capitalize()} generated by deterministic dev stub."


def _singularize(name: str) -> str:
    return name[:-1] if name.endswith("s") else name
