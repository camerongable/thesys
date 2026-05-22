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
    elif output_schema.__name__ == "OpportunityBriefDraft":
        payload = _fake_opportunity_brief(subject)
    elif output_schema.__name__ == "CompetitorAnalysisDraft":
        payload = _fake_competitor_analysis(subject)
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


def _fake_opportunity_brief(subject: str) -> dict[str, Any]:
    request_payload = _extract_json_payload(subject)
    project_state = request_payload.get("project_state") or {}
    evidence_bundles = request_payload.get("evidence_bundles") or []
    project_name = str(project_state.get("name") or "Founder project")
    thesis = str(
        project_state.get("current_thesis")
        or project_state.get("short_description")
        or "The project needs a clearer evidence-backed thesis."
    )
    target_users = project_state.get("customer_segments") or []
    target_user_text = (
        ", ".join(str(user) for user in target_users[:3]) or "the initial target user"
    )
    first_evidence = _first_evidence_bundle(evidence_bundles)
    citations = [_citation_from_bundle(first_evidence)] if first_evidence else []

    supported_claims = []
    if first_evidence:
        source_title = str(first_evidence.get("title") or "the strongest available evidence")
        supported_claims.append(
            {
                "text": (
                    f"{source_title} provides project evidence that should shape the initial "
                    f"opportunity brief for {project_name}."
                ),
                "claim_type": "evidence_summary",
                "confidence_score": 0.72,
                "support_level": "supported",
                "citations": citations,
            }
        )

    supported_claims.append(
        {
            "text": "The initial wedge still needs direct validation with the buyer segment.",
            "claim_type": "validation_gap",
            "confidence_score": 0.55,
            "support_level": "inference",
            "citations": [],
        }
    )

    return {
        "executive_summary": (
            f"{project_name} is currently best treated as a focused validation project. "
            "The available evidence is useful, but the brief should separate supported "
            "claims from assumptions that still need customer proof."
        ),
        "product_hypothesis": thesis,
        "target_user": target_user_text,
        "problem_analysis": (
            "The project appears to address a workflow where users convert scattered "
            "inputs into decisions. The strongest next step is to confirm frequency, "
            "urgency, and willingness to pay with the initial segment."
        ),
        "current_alternatives": ["Manual spreadsheets and notes", "Generic AI chats"],
        "market_context": (
            "Market context should remain conservative until more external evidence is "
            "added. Avoid broad TAM claims at this stage."
        ),
        "competitor_landscape": (
            "Competitor understanding is preliminary. User-seeded competitor evidence "
            "should be added before treating positioning as validated."
        ),
        "differentiation_and_wedge": (
            "The most defensible wedge is a narrow workflow that combines project memory, "
            "evidence, assumptions, and decisions in one stateful workspace."
        ),
        "risks_and_kill_assumptions": (
            "The main kill-risk assumption is that the target user has recurring enough "
            "pain to return to the workspace and pay for it."
        ),
        "validation_plan": (
            "Run five customer interviews focused on current workflow, time spent, "
            "existing alternatives, willingness to pay, and trust requirements."
        ),
        "recommendation": (
            "Proceed with validation only after adding more evidence and testing the "
            "highest-uncertainty assumptions."
        ),
        "confidence_score": 0.45 if citations else 0.25,
        "claims": supported_claims,
        "assumptions": [
            {
                "text": (
                    "The target user experiences the problem frequently enough to seek a "
                    "new tool."
                ),
                "category": "problem_urgency",
                "importance": "critical",
                "uncertainty": "high",
                "kill_risk": True,
                "confidence_score": 0.35,
                "recommended_test": (
                    "Interview target users and ask them to reconstruct the last three times "
                    "they handled this workflow."
                ),
            },
            {
                "text": "The initial segment is willing to pay for a stateful workflow product.",
                "category": "willingness_to_pay",
                "importance": "high",
                "uncertainty": "high",
                "kill_risk": True,
                "confidence_score": 0.3,
                "recommended_test": (
                    "Test pricing during discovery calls and collect pre-commitment signals."
                ),
            },
        ],
        "risks": [
            {
                "text": (
                    "The product could feel like a generic AI report generator if citations "
                    "and structured state are weak."
                ),
                "category": "product_differentiation",
                "severity": "high",
                "likelihood": "medium",
                "mitigation": (
                    "Keep the workspace, evidence graph, assumptions, and decision log primary."
                ),
            }
        ],
        "citations": citations,
        "unsupported_claims": [
            (
                "Market size, buying urgency, and competitor gaps remain unvalidated until "
                "more evidence is added."
            )
        ],
    }


def _first_evidence_bundle(evidence_bundles: Any) -> dict[str, Any] | None:
    if not isinstance(evidence_bundles, list):
        return None
    for bundle in evidence_bundles:
        if isinstance(bundle, dict) and bundle.get("source_id"):
            return bundle
    return None


def _fake_competitor_analysis(subject: str) -> dict[str, Any]:
    request_payload = _extract_json_payload(subject)
    seed_competitors = request_payload.get("seed_competitors") or []
    evidence_bundles = request_payload.get("evidence_bundles") or []
    project_state = request_payload.get("project_state") or {}
    project_name = str(project_state.get("name") or "the project")
    first_evidence = _first_evidence_bundle(evidence_bundles)
    citations = [_citation_from_bundle(first_evidence)] if first_evidence else []

    competitors = []
    for index, seeded in enumerate(seed_competitors[:5]):
        if not isinstance(seeded, dict):
            continue
        name = str(seeded.get("name") or f"Competitor {index + 1}")
        url = seeded.get("url")
        seeded_category = seeded.get("category")
        category = seeded_category if seeded_category and seeded_category != "unknown" else None
        competitors.append(
            {
                "name": name,
                "url": str(url) if url else None,
                "category": category or ("direct" if index == 0 else "adjacent"),
                "target_user": "Founders and operators evaluating a similar workflow.",
                "positioning": (
                    f"{name} appears to position around a narrower workflow that should be "
                    "compared against the project's evidence-backed workspace thesis."
                ),
                "pricing_summary": (
                    "Pricing needs verification from source evidence."
                    if not citations
                    else "Pricing should be treated as source-dependent and checked manually."
                ),
                "key_features": [
                    "Workflow capture",
                    "AI-assisted synthesis",
                    "Project or client workspace",
                ],
                "strengths": [
                    "Clearer existing category familiarity",
                    "Focused feature surface",
                ],
                "weaknesses": [
                    "May not preserve a full evidence-to-decision graph",
                    "Citation coverage needs inspection",
                ],
                "differentiation_notes": (
                    "Avoid competing on generic generation. Emphasize persistent evidence, "
                    "assumptions, experiments, and decisions."
                ),
                "threat_level": "high" if index == 0 else "medium",
                "citations": citations,
            }
        )

    if not competitors:
        competitors.append(
            {
                "name": "Generic AI assistants",
                "url": None,
                "category": "substitute",
                "target_user": "Founders doing one-off research and drafting.",
                "positioning": (
                    "Flexible AI chat and drafting rather than structured strategy memory."
                ),
                "pricing_summary": "Pricing varies and is not validated by project evidence.",
                "key_features": ["Chat", "Draft generation", "Summarization"],
                "strengths": ["Low-friction adoption", "Broad task coverage"],
                "weaknesses": ["Weak structured memory", "Weak decision traceability"],
                "differentiation_notes": (
                    "Compete by making the workspace, citations, assumptions, and decision "
                    "ledger primary."
                ),
                "threat_level": "medium",
                "citations": citations,
            }
        )

    supported_claims = []
    if citations:
        supported_claims.append(
            {
                "text": (
                    "The competitor landscape should be grounded in the ingested competitor "
                    "and project evidence."
                ),
                "claim_type": "competitor_evidence",
                "confidence_score": 0.7,
                "support_level": "supported",
                "citations": citations,
            }
        )
    supported_claims.append(
        {
            "text": (
                "Positioning should avoid generic AI generation and focus on structured "
                "strategic memory."
            ),
            "claim_type": "positioning_recommendation",
            "confidence_score": 0.55,
            "support_level": "inference",
            "citations": [],
        }
    )

    return {
        "summary": (
            f"{project_name} should treat the current competitor set as an initial landscape. "
            "The useful comparison is whether competitors preserve evidence, assumptions, "
            "experiments, and decisions as structured state."
        ),
        "competitors": competitors,
        "clusters": [
            {
                "name": "AI workflow and research substitutes",
                "competitors": [competitor["name"] for competitor in competitors],
                "positioning_summary": (
                    "Most alternatives are easier to adopt than a new workspace but are "
                    "weaker as a durable strategy system of record."
                ),
            }
        ],
        "positioning_gaps": [
            "Evidence-backed strategy memory",
            "Assumption-to-experiment workflow",
            "Decision traceability tied to cited sources",
        ],
        "wedge_recommendations": [
            "Lead with one founder validation workflow rather than broad research automation.",
            "Make citations and unsupported claims visible in every strategic artifact.",
        ],
        "where_not_to_compete": [
            "Generic brainstorming",
            "Uncited market-size claims",
            "Broad autonomous crawling in the MVP",
        ],
        "claims": supported_claims,
        "citations": citations,
        "unsupported_claims": [
            (
                "Competitor pricing, feature completeness, and threat level need direct "
                "source verification before being treated as facts."
            )
        ],
    }


def _citation_from_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": str(bundle.get("source_id")),
        "chunk_id": str(bundle.get("chunk_id")) if bundle.get("chunk_id") else None,
        "title": bundle.get("title"),
        "url": bundle.get("url"),
        "quote": str(bundle.get("text") or "")[:500],
        "retrieved_at": bundle.get("retrieved_at"),
        "relevance_score": bundle.get("score"),
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
